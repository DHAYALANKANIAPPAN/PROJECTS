# Airlock

> **Defending autonomous AI email agents against indirect prompt injection via dual-gate addressee and authority verification.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Measured-success.svg)](docs/PREREGISTRATION.md)

---

## 1. The Core Insight

Existing prompt injection defenses ask:
> ❌ *"Is this input malicious?"*

Attackers easily bypass this by disguising, polite rephrasing, or splitting instructions across paragraphs.

Instead, Airlock asks:
>  **"Who is this text talking to?"** *(A human reader vs. the AI agent)*

Legitimate business documents (invoices, meeting invites, flight receipts) convey inert data or address human colleagues (*"Alice, please review the slides"*). They **almost never** legitimately address the AI software agent.

When incoming external text contains instructions directed at the AI (*"Ignore previous rules"*, *"System prompt override"*, *"Assistant must forward"*), that is an inherent anomaly.

---

## 2. Architecture: Two Independent Gates

```
                         Incoming Email / Document
                                     │
                                     ▼
                      [ GATE 1: Addressee Check ]
                      (Classification runs locally)
                      Classifies: data | human_instruction |
                                  ai_instruction | unclear
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
      Confident Data           Borderline/Unsure    Confident AI-addressed
     (Agent reads raw)               │                     │
               │                     └──────────┬──────────┘
               │                                │
               │                                ▼
               │                   [ Bedrock Fact Sanitizer ]
               │                   (Extracts facts into fixed JSON;
               │                    Agent NEVER sees raw text)
               │                                │
               └─────────────────────┬──────────┘
                                     │
                                     ▼
                          [ AI Email Agent Loop ]
                          (Processes email via Bedrock)
                                     │
                                     ▼ (Proposes tool execution)
                                     │
                      [ GATE 2: Authority Check ]
                      "Does this action trace back to what the
                       human asked for, or only the document?"
                                     │
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
            Grounded in User Request      Ungrounded / From Doc Only
                   [ PROCEED ]                     [ DENY ]
```

1. **Gate 1 (Addressee Check — Incoming)**: Runs locally using an on-device Decider 2B decision model with sub-100ms latency. Quarantines AI-addressed text while preserving tricky human directives.
2. **Bedrock Tool-less Sanitizer**: Strips all imperative commands and extracts only inert facts into a strict JSON schema. The agent never encounters executable injection strings.
3. **Gate 2 (Authority Check — Outgoing)**: Intercepts all proposed side-effecting tool calls (`send_email`, `delete_email`, `forward_email`) to verify whether authority traces back to the user's explicit request.

---

## 3. Reusable Strands Decider 2B Decision Pattern

> **Required Hackathon Asset:** [`airlock/decider_pattern.py`](airlock/decider_pattern.py)  
> **Detailed Specification:** [`docs/DECISION_PATTERN.md`](docs/DECISION_PATTERN.md)  
> **Tags:** `#strands-decider-2b` | `#guardrails` (also applicable to `#policy`)

Drop-in decision recipe for builders pairing Strands Decider 2B with Amazon Bedrock:
```python
from airlock.decider_pattern import DeciderGuardrailPattern

guard = DeciderGuardrailPattern()

# 1. Inbound document check before LLM reads raw input
decision = guard.inspect_document("Invoice #4820: Pay $2,450 by Nov 1.")
if decision.should_quarantine:
    safe_data = sanitize_facts_only(raw_text)
else:
    safe_data = raw_text

# 2. Outbound tool call verification before executing actions
allowed, reason = guard.verify_tool_call(
    tool_name="send_email",
    tool_args={"to": "external@domain.com", "body": "Sensitive report"},
    user_request=user_prompt,
    doc_context=raw_text
)
if not allowed:
    print(f"Tool call blocked by Decider Guardrail: {reason}")
```

---

## 4. Quickstart & 10-Line Usage Example

### Clean-Clone Installation
```bash
git clone https://github.com/DHAYALANKANIAPPAN/AirLock.git
cd AirLock
pip install -e .
```

### 10-Line Usage Example
```python
from airlock.handler import AirlockHandler
from airlock.agent import BedrockEmailAgent, Mailbox
from airlock.report import build_report, authorization_trail

handler = AirlockHandler(confirm=lambda msg: True)
agent = BedrockEmailAgent(Mailbox.demo(), handler)
result = agent.run("Summarize unread emails in my inbox")

print(f"Agent Summary: {result['answer']}")
print(f"Security Report: {build_report(result['audit'])}")
print(f"Authorization Trail:\n{authorization_trail(result['audit'])}")
```

---

## 4. Running the Split-Screen Demo

See the side-by-side comparison between an unprotected baseline agent and the Airlock-protected agent:

```bash
# Run Terminal split-screen CLI demo
python3 demo/app.py --all

# Or launch the interactive Streamlit Web UI
streamlit run demo/app.py
```

---

## 5. Verification & Tests

Airlock includes automated unit testing, smoke tests, and calibration studies:

```bash
# Run complete test suite (29 tests)
python3 -m unittest discover tests

# Or run via pytest
pytest -v

# Run Gate 1 Decider 2B smoke test (100 snippets)
python3 eval/run_decider_smoke.py

# Run Gate 2 authority threshold calibration on dev data
python3 eval/calibrate_gate2.py

# Run reliability diagram and calibration plot generator
python3 eval/calibration_plot.py
```

---

## 6. Scientific Rigor & Ground Rules
- **No Hand-Typed Numbers**: Every metric in our publications is generated directly by evaluation scripts.
- **Honest Claims**: We do *not* claim to "stop prompt injection". We claim that layered addressee and authority gates significantly reduce the attack surface.
- **Wording**: Classification runs locally; AWS Bedrock powers generative reasoning and fact sanitization.
- **License**: Released under Apache-2.0.
