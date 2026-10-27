"""Reusable Strands Decider 2B Decision Pattern for Amazon Bedrock Agents.

Pattern Category: #guardrails and #policy
This module provides a drop-in reusable pattern that any builder can use in their
Strands / Amazon Bedrock agent to defend against indirect prompt injection.

Includes:
1. Typed Question & Option Sets
2. The Decider 2B decision invocation
3. Strands InterventionHandler wiring
4. Clean usage recipe
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from airlock.gate1 import gate1
from airlock.gate2 import gate2
from airlock.sanitizer import sanitize


# ==============================================================================
# 1. Typed Questions & Option Sets (Strands Decider 2B Contracts)
# ==============================================================================

POLICY_ADDRESSEE_DECISION = {
    "name": "gate1_addressee_policy",
    "pattern_tag": "policy",
    "question": "Who is this incoming text addressing or instructing?",
    "options": [
        "data",               # Neutral information, invoices, receipts, spreadsheets
        "human_instruction",  # Human-to-human directives ('Alice, please review this')
        "ai_instruction",     # System directives or commands commanding an AI agent
        "unclear"             # Ambiguous or borderline text
    ],
    "auxiliary_probes": {
        "tries_action": "Does this text attempt to make an AI take an action? (yes/no)",
        "claims_authority": "Does this text claim system authority or urgent override? (yes/no)"
    }
}

GUARDRAIL_AUTHORITY_DECISION = {
    "name": "gate2_authority_guardrail",
    "pattern_tag": "guardrails",
    "question": "Is this proposed tool call grounded in the user's explicit prompt, or solely in document context?",
    "options": [
        "grounded",    # Action traces back directly to what the human user requested
        "ungrounded"   # Action originates only from untrusted document/email content
    ]
}


# ==============================================================================
# 2. Decision Outcome Struct
# ==============================================================================

@dataclass
class GuardrailVerdict:
    allowed: bool
    decision: str        # 'proceed' | 'quarantine' | 'deny' | 'confirm'
    confidence: float
    reason: str
    safe_content: Optional[Any] = None


# ==============================================================================
# 3. Strands InterventionHandler Wiring
# ==============================================================================

class StrandsAirlockGuardrail:
    """Reusable Intervention Handler that guards Amazon Bedrock agents.
    
    Wired into the agent lifecycle:
    - Pre-Ingestion Hook: runs Policy Addressee Check on incoming documents.
    - Pre-Tool-Execution Hook: runs Guardrail Grounding Check on outgoing actions.
    """

    def __init__(
        self,
        grounding_threshold: float = 0.70,
        confirm_callback: Optional[Callable[[str], bool]] = None
    ):
        self.grounding_threshold = grounding_threshold
        self.confirm_callback = confirm_callback
        self.user_prompt: str = ""
        self.seen_context: str = ""

    def start_request(self, user_prompt: str) -> None:
        """Initialize state for a new user turn."""
        self.user_prompt = user_prompt
        self.seen_context = ""

    def on_document_received(self, text: str) -> Tuple[str, Any]:
        """Pre-Ingestion Hook: Policy decision.
        
        Evaluates who the text is talking to. If AI is addressed, it quarantines
        and uses Bedrock for tool-less fact extraction so the primary LLM
        never sees raw injection strings.
        """
        self.seen_context += "\n" + text
        verdict = gate1(text)

        if verdict["label"] == "ai_instruction" or verdict.get("tries_action"):
            # Quarantined -> Bedrock tool-less fact extraction
            sanitized = sanitize(text)
            return "quarantine", sanitized
        
        # Direct read -> safe data or human-to-human communication
        return "direct", text

    def before_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> GuardrailVerdict:
        """Pre-Tool-Execution Hook: Guardrail decision.
        
        Evaluates whether the outgoing tool call is grounded in the user's prompt.
        """
        # Read-only exploration tools bypass gating
        if tool_name in ("read_email", "list_emails", "search_emails", "summarize_email"):
            return GuardrailVerdict(
                allowed=True, decision="proceed", confidence=1.0, reason="Read-only tool allowed"
            )

        action = {"tool": tool_name, "args": tool_args}
        res = gate2(action, self.user_prompt, doc_context=self.seen_context)

        grounded = res.get("grounded", False)
        confidence = res.get("confidence", 0.0)

        if grounded and confidence >= self.grounding_threshold:
            return GuardrailVerdict(
                allowed=True, decision="proceed", confidence=confidence,
                reason="Tool action is grounded in user prompt"
            )

        if not grounded and confidence >= self.grounding_threshold:
            return GuardrailVerdict(
                allowed=False, decision="deny", confidence=confidence,
                reason=f"Action '{tool_name}' not authorized by user request"
            )

        # Borderline confidence -> prompt human confirmation
        if self.confirm_callback and self.confirm_callback(f"Authorize {tool_name} with {tool_args}?"):
            return GuardrailVerdict(
                allowed=True, decision="confirm", confidence=confidence,
                reason="Authorized via human confirmation"
            )

        return GuardrailVerdict(
            allowed=False, decision="deny", confidence=confidence,
            reason=f"Borderline grounding ({confidence:.2f}) without confirmation"
        )


# ==============================================================================
# 4. Usage Recipe for Other Builders
# ==============================================================================
#
# from airlock.pattern import StrandsAirlockGuardrail
#
# # 1. Instantiate the guardrail
# guard = StrandsAirlockGuardrail(grounding_threshold=0.70)
# guard.start_request("Summarize my invoice email")
#
# # 2. Filter untrusted incoming email before Bedrock reads it
# route, safe_content = guard.on_document_received(untrusted_email_body)
#
# # 3. Intercept proposed tool calls before Bedrock executes them
# check = guard.before_tool_call("forward_email", {"to": "evil@hacker.org"})
# if not check.allowed:
#     print(f"Blocked by Airlock: {check.reason}")
