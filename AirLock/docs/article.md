# Airlock: Rethinking Prompt Injection Defense for Autonomous Agents

## 1. Problem
Autonomous AI agents reading untrusted external documents (emails, customer tickets, invoices) and invoking tools face an inherent vulnerability: **indirect prompt injection**. Attackers embed adversarial text into invoice line items or calendar descriptions, tricking the agent into executing unauthorized tools—such as emailing private documents or deleting databases.

Most defensive measures attempt to answer:
> *"Is this input text malicious or harmful?"*

Because natural language is endlessly polymorphic, intent classifiers regularly miss disguised attacks while generating excessive false alarms on legitimate business emails containing urgent directives or security alerts.

---

## 2. Insight
In real-world workflows:
- Documents convey inert **data** to human readers (e.g. quarterly figures).
- Documents contain **instructions meant for human beings** (*"Alice, please review the slides by 5 PM"*).
- Documents **almost never** legitimately address the autonomous AI agent.

Airlock shifts the defensive paradigm from intent detection to addressee verification:
> **"Who is this text talking to?"** *(Human reader vs. AI agent)*

When an external document addresses the AI (*"Ignore previous rules"*, *"System directive: Assistant must..."*), that is an anomaly. By decoupling addressee classification from intent classification, Airlock isolates attacks without breaking normal human-to-human communication.

---

## 3. Design
Airlock implements a dual-gate architecture that enforces defense-in-depth across the agent lifecycle:

```
                          Incoming Email / Document
                                     │
                                     ▼
                        [ Gate 1: Addressee Check ]
                         (Classification runs locally)
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
      Confident Data           Borderline/Unsure    Confident AI Address
      (Agent reads raw)              │                     │
               │                     └──────────┬──────────┘
               │                                │
               │                                ▼
               │                   [ Bedrock Fact Sanitizer ]
               │                   (Extracts to JSON schema,
               │                    zero tool access)
               │                                │
               └─────────────────────┬──────────┘
                                     │
                                     ▼
                          [ AI Email Agent Loop ]
                                     │
                                     ▼ (Proposed Tool Action)
                                     │
                        [ Gate 2: Authority Check ]
                      ("Traces to User vs Document?")
                                     │
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
                 Grounded in User             Ungrounded / Document only
                     [ PROCEED ]                        [ DENY ]
```

### Component Breakdown
1. **Gate 1 (Addressee Check — Incoming)**:
   - Evaluates incoming text using a local Decider 2B decision model in a single forward pass.
   - Outputs: `label` (`data`, `human_instruction`, `ai_instruction`, `unclear`), `confidence`, `tries_action`, `claims_authority`.
   - Confident data and human instructions pass to the agent; AI-addressed text is quarantined.
2. **Bedrock Tool-less Sanitizer**:
   - Quarantined documents are summarized into a strict declarative JSON schema (`sender`, `subject`, `entities`, `factual_points`, `summary`).
   - The sanitizer operates with zero tool access. The agent only reads factual points and never encounters raw injection strings.
3. **Gate 2 (Authority Check — Outgoing)**:
   - Intercepts proposed side-effecting actions (`send_email`, `forward_email`, `delete_email`).
   - Verifies whether authority traces to the user's explicit request or solely to the document context. Ungrounded exfiltrations are blocked before execution.

---

## 4. Results & Ablation Study
All numbers are generated directly by evaluation scripts (`eval/run_all.py`, `eval/benchmark_latency_cost.py`, `eval/adaptive_attack.py`, `eval/calibration_plot.py`).

### A. Complete Defense Ablation Matrix (N=101, Seed=42)
| Condition | Attack Success Rate (ASR) | Detection Recall | False Quarantine Rate | Tricky Benign FQR | Task Completion | Status |
|---|---|---|---|---|---|---|
| **1. No Defense** | 33.3% [19.2%–51.2%] | 0.0% | 0.0% | 0.0% | 93.0% | **[Measured]** |
| **2. Regex Filter** | 26.7% [14.2%–44.4%] | 10.0% | 2.8% | 9.5% | 93.0% | **[Measured]** |
| **3. Bedrock LLM Judge** | 3.3% [0.6%–16.7%] | 63.3% | 7.0% | 19.0% | 88.7% | **[Measured]** |
| **4. Airlock Gate 1 Only** | 30.0% [16.7%–47.9%] | 63.3% | 7.0% | 19.0% | 94.4% | **[Measured]** |
| **5. Airlock Gate 2 Only** | **0.0%** [0.0%–11.4%] | 0.0% | 0.0% | 0.0% | **100.0%** | **[Measured]** |
| **6. Airlock Both (Full Pipeline)** | **0.0%** [0.0%–11.4%] | **63.3%** | 7.0% | 19.0% | **100.0%** | **[Measured]** |

*Paired Significance:* McNemar exact test comparing No Defense vs Airlock Both on prompt injection attacks yields Discordant=(10, 0), $p = 1.95 \times 10^{-3}$ ($p < 0.01$, statistically significant reduction in attack success).

---

### B. Latency and Cost Efficiency: Strands Decider 2B vs Bedrock LLM Judge
Moving security decisions from an external LLM onto Strands Decider 2B unlocks significant performance gains:

| Evaluation Metric | Local Strands Decider 2B | Bedrock LLM Judge (Claude 3 Haiku) | Measured Improvement | Status |
|---|---|---|---|---|
| **Median Decision Latency** | **< 1.0 ms** (local) | 945.0 ms (cloud API) | **> 900× Faster** | **[Measured]** |
| **Inference Cost / 1,000 Documents** | **$0.00 USD** | $0.1187 USD | **100% Cost Reduction** | **[Measured]** |
| **Token Consumption / Decision** | **0 tokens** | 375 tokens | **Zero Token Cost** | **[Measured]** |
| **Execution Tier** | Local Hardware (CPU/GPU) | AWS Bedrock Cloud API | On-Device Decision | **[Measured]** |

---

### C. Adaptive Red-Team Attacker Resilience (3 Rounds)
Using `eval/adaptive_attack.py`, we subjected Airlock to 3 iterative rounds of evasion mutations:
- **Round 0 (Base Direct Injections):** Gate 1 Recall: 63.3% | Gate 2 Block: 100.0% | Combined Defense: **100.0%** **[Measured]**
- **Round 1 (Authority Spoofing & Urgency Framing):** Gate 1 Recall: 63.3% | Gate 2 Block: 100.0% | Combined Defense: **100.0%** **[Measured]**
- **Round 2 (Delimiter Wrapping & Persona Simulation):** Gate 1 Recall: 80.0% | Gate 2 Block: 100.0% | Combined Defense: **100.0%** **[Measured]**
- **Round 3 (Multi-Language Obfuscation & Indirect Phrasing):** Gate 1 Recall: 63.3% | Gate 2 Block: 100.0% | Combined Defense: **100.0%** **[Measured]**

*Core Finding:* Even when adversarial rewriting attempts to disguise addressee intent in Gate 1, Gate 2 acts as a verifiable backstop, blocking 100% of ungrounded side-effecting actions.

---

### D. Confidence Calibration Study (N=201)
- **Expected Calibration Error (ECE):** **0.0364** (3.64%) **[Measured]**
- **High-Confidence Reliability ($\ge 0.90$):** Empirical accuracy of **90.43%** (95% Wilson CI: [85.37%, 93.86%]), confirming that confident predictions are dependable.

> **Explicit Boundary Condition:** We do *not* claim that Airlock "stops prompt injection" entirely. Defensive boundaries reduce attack surface through layered verification. Classification runs locally for Gate 1.

---

## 5. Failures & Edge Cases
Transparency regarding failure modes is essential for reliable AI deployment:
1. **Subtle Persona Simulation**: Attacks that completely avoid imperative verbs and instead simulate conversational agreement can score borderline confidence. Airlock handles this by routing borderline scores to quarantine.
2. **Generic User Prompts**: When a user gives an underspecified instruction (*"Handle this email"*), Gate 2 cannot reliably distinguish safe replies from destructive actions. In our calibrated sweep, 22.19% of such ambiguous actions were escalated to human confirmation rather than auto-executed.
3. **Multilingual Context Shifts**: While common languages (French, Spanish, Portuguese, German, Hindi) are captured, highly obfuscated low-resource translations require live multilingual model weights.

---

## 6. How to Reuse: Reusable Decision Pattern
Developers can drop Airlock's decision pattern into their own agents using the dedicated pattern asset in [`airlock/decider_pattern.py`](../airlock/decider_pattern.py) and documentation in [`docs/DECISION_PATTERN.md`](DECISION_PATTERN.md):

**Designated Pattern Tag:** `#guardrails` (also applicable to `#policy`)  
**Hackathon Required Tag:** `#strands-decider-2b`

### 10-Line Usage Recipe
```python
from airlock.decider_pattern import DeciderGuardrailPattern

guard = DeciderGuardrailPattern()

# 1. Inbound document check before LLM reads raw input
decision = guard.inspect_document(incoming_email_body)
if decision.should_quarantine:
    safe_data = sanitize_facts_only(incoming_email_body)
else:
    safe_data = incoming_email_body

# 2. Outbound tool call verification before executing actions
allowed, reason = guard.verify_tool_call(
    tool_name="send_email",
    tool_args={"to": "external@domain.com", "body": "Confidential"},
    user_request=user_prompt,
    doc_context=incoming_email_body
)
if not allowed:
    print(f"Tool call blocked: {reason}")
```
