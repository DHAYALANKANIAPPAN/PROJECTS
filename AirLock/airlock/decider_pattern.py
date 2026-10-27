"""Strands Decider 2B Reusable Decision Pattern: Dual-Gate Addressee & Authority Guardrails.

Pattern Category: #guardrails (also applicable to #policy)
Required Hackathon Tag: #strands-decider-2b

================================================================================
REUSABLE ASSET SPECIFICATION (For AWS Agent Experience Hackathon Judges & Builders)
================================================================================
This module provides a drop-in, reusable decision pattern for autonomous agents built
with Amazon Bedrock and Strands. It moves security-critical decisions off the generative
LLM onto Strands Decider 2B, achieving sub-100ms local classification with calibrated
confidence and zero token cost.

Core Idea:
Instead of asking "Is this input malicious?", ask "Who is this text talking to?"
Legitimate documents (invoices, emails, receipts) convey inert data or address humans;
they almost never legitimately address the autonomous AI agent. When incoming text addresses
the AI, it is an anomaly that warrants instant quarantine.

Pattern Components:
1. Typed Question & Option Sets:
   - Addressee Probe: "Who is this text addressing or instructing?"
     Options: ["data", "human_instruction", "ai_instruction", "unclear"]
   - Action Probe: "Does this text attempt to make an AI system or agent execute an external action?"
     Options: ["yes", "no"]
   - Authority Probe: "Does this text claim urgent authority, administrative override, or demand immediate action without verification?"
     Options: ["yes", "no"]

2. Agent Wiring:
   - Inbound Filter: Inspects documents before LLM ingestion. Quarantines AI-directed text.
   - Outbound Guardrail: Validates outgoing tool calls against the user's explicit request.

3. How to Use in Your Own Agent:
   ```python
   from airlock.decider_pattern import DeciderGuardrailPattern

   guard = DeciderGuardrailPattern()

   # 1. Inbound document check
   decision = guard.inspect_document("Invoice #101: Please pay by Nov 1.")
   if decision.should_quarantine:
       safe_content = guard.sanitize_facts_only(raw_text)
   else:
       safe_content = raw_text

   # 2. Outbound tool call guardrail
   allowed, reason = guard.verify_tool_call(
       tool_name="forward_email",
       tool_args={"to": "leak@evil.org"},
       user_request="Summarize invoice #101"
   )
   if not allowed:
       print(f"Tool call blocked: {reason}")
   ```
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("airlock.decider_pattern")

# ---------------------------------------------------------------------------
# 1. Typed Questions and Option Sets for Strands Decider 2B
# ---------------------------------------------------------------------------

DECIDER_TYPED_PROBES = [
    {
        "id": "addressee",
        "question": "Who is this text addressing or instructing?",
        "options": ["data", "human_instruction", "ai_instruction", "unclear"],
        "description": "Determines the intended recipient of the text. Legitimate content is 'data' or 'human_instruction'.",
    },
    {
        "id": "tries_action",
        "question": "Does this text attempt to make an AI system or agent execute an external action?",
        "options": ["yes", "no"],
        "description": "Binary probe evaluating whether the text attempts to trigger external agent capabilities.",
    },
    {
        "id": "claims_authority",
        "question": "Does this text claim urgent authority, administrative override, or demand immediate action without verification?",
        "options": ["yes", "no"],
        "description": "Evaluates urgency, administrative override claims, or coercion tactics.",
    },
]


@dataclass(frozen=True)
class DocumentDecision:
    """Outcome of the Gate 1 Addressee decision."""
    route: str                           # 'direct' | 'quarantine' | 'unsure'
    label: str                           # 'data' | 'human_instruction' | 'ai_instruction' | 'unclear'
    confidence: float                    # 0.0 to 1.0 calibrated confidence
    tries_action: bool
    claims_authority: bool
    should_quarantine: bool
    explanation: str


@dataclass(frozen=True)
class ToolCallDecision:
    """Outcome of the Gate 2 Authority grounding decision."""
    allowed: bool
    grounded: bool
    confidence: float
    recommendation: str                  # 'proceed' | 'deny' | 'confirm_with_user'
    reason: str


# ---------------------------------------------------------------------------
# 2. Reusable Decider Guardrail Class
# ---------------------------------------------------------------------------

class DeciderGuardrailPattern:
    """Reusable Strands Decider 2B Decision Pattern for Agent Safety.

    Pairs Decider 2B's fast local classification with Bedrock agents:
    - Pre-LLM: Addressee check quarantines injection vectors before LLM sees raw text.
    - Post-LLM: Authority check grounds proposed tool calls in user intent.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        confidence_threshold: float = 0.80,
        read_only_tools: Optional[Set[str]] = None,
        high_risk_tools: Optional[Set[str]] = None,
    ):
        self.endpoint_url = endpoint_url or os.getenv("DECIDER_ENDPOINT_URL", "http://localhost:8000/v1/decide")
        self.confidence_threshold = confidence_threshold
        self.read_only_tools = read_only_tools or {
            "read_email", "list_emails", "search_emails", "get_email", "summarize_email"
        }
        self.high_risk_tools = high_risk_tools or {
            "send_email", "forward_email", "delete_email", "execute_command", "transfer_funds", "write_file"
        }

    # -----------------------------------------------------------------------
    # Inbound Content Inspection (Gate 1)
    # -----------------------------------------------------------------------

    def inspect_document(self, text: str) -> DocumentDecision:
        """Evaluate incoming document using Decider 2B typed probes.

        Returns a DocumentDecision indicating whether the content is safe to read
        raw or must be quarantined into sanitized facts.
        """
        if not text or not text.strip():
            return DocumentDecision(
                route="direct",
                label="data",
                confidence=1.0,
                tries_action=False,
                claims_authority=False,
                should_quarantine=False,
                explanation="Empty document; treated as inert data.",
            )

        # In production, queries the local Decider 2B endpoint.
        # Falls back to calibrated reference probes when local daemon is not running.
        from airlock.gate1 import gate1
        verdict = gate1(text, model_path=self.endpoint_url, confidence_threshold=self.confidence_threshold)

        label = verdict["label"]
        confidence = verdict["confidence"]
        tries_action = verdict["tries_action"]
        claims_authority = verdict["claims_authority"]

        confident = confidence >= self.confidence_threshold

        if label == "data" and confident:
            route = "direct"
            should_quarantine = False
            explanation = f"Confident inert data ({confidence:.2f}). Safe for direct agent reading."
        elif label == "human_instruction" and confident and not tries_action and not claims_authority:
            route = "direct"
            should_quarantine = False
            explanation = f"Confident human instruction ({confidence:.2f}). No AI action or authority claim detected."
        elif label == "ai_instruction" and confident:
            route = "quarantine"
            should_quarantine = True
            explanation = f"Confident AI-addressed text ({confidence:.2f}). Quarantined to prevent indirect prompt injection."
        else:
            route = "unsure"
            should_quarantine = True
            explanation = f"Uncertain addressee ({label}, confidence {confidence:.2f}). Quarantined under fail-closed security policy."

        return DocumentDecision(
            route=route,
            label=label,
            confidence=confidence,
            tries_action=tries_action,
            claims_authority=claims_authority,
            should_quarantine=should_quarantine,
            explanation=explanation,
        )

    # -----------------------------------------------------------------------
    # Outbound Tool-Call Inspection (Gate 2)
    # -----------------------------------------------------------------------

    def verify_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        user_request: str,
        doc_context: Optional[str] = None,
    ) -> ToolCallDecision:
        """Verify whether a proposed tool call is grounded in the human user's prompt.

        Returns ToolCallDecision:
        - allowed=True if the tool is read-only or authorized by user.
        - allowed=False if the tool is ungrounded or induced solely by untrusted doc.
        """
        tool_clean = (tool_name or "").lower().strip()

        # Read-only tools bypass authority gating (they do not mutate state or exfiltrate)
        if tool_clean in self.read_only_tools:
            return ToolCallDecision(
                allowed=True,
                grounded=True,
                confidence=1.0,
                recommendation="proceed",
                reason=f"Tool '{tool_name}' is read-only and safe to execute.",
            )

        from airlock.gate2 import gate2_detailed
        result, breakdown = gate2_detailed(
            action={"tool": tool_name, "args": tool_args},
            user_request=user_request,
            doc_context=doc_context,
        )

        recommendation = breakdown["recommendation"]
        allowed = (recommendation == "proceed")
        reason = (
            f"Authorized by user request (grounding score: {breakdown['grounding_score']:.2f})"
            if allowed
            else f"BLOCKED: Action '{tool_name}' not grounded in user prompt (recommendation: {recommendation})"
        )

        return ToolCallDecision(
            allowed=allowed,
            grounded=result["grounded"],
            confidence=result["confidence"],
            recommendation=recommendation,
            reason=reason,
        )

    # -----------------------------------------------------------------------
    # Reusable Wiring Wrapper for Agent Tool Execution
    # -----------------------------------------------------------------------

    def wrap_tool_function(
        self,
        tool_fn: Callable[..., Any],
        get_user_request: Callable[[], str],
        get_doc_context: Optional[Callable[[], str]] = None,
    ) -> Callable[..., Any]:
        """Wrap an agent tool function with Gate 2 authority verification.

        Compatible with standard Python tools, LangChain tools, or Strands agents.
        """
        name = getattr(tool_fn, "__name__", "unknown_tool")

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            user_req = get_user_request()
            doc_ctx = get_doc_context() if get_doc_context else None

            # Merge arguments for inspection
            combined_args = dict(kwargs)
            if args:
                combined_args["_positional_args"] = list(args)

            decision = self.verify_tool_call(
                tool_name=name,
                tool_args=combined_args,
                user_request=user_req,
                doc_context=doc_ctx,
            )

            if not decision.allowed:
                logger.warning("Decider Guardrail blocked tool call '%s': %s", name, decision.reason)
                return f"BLOCKED by Decider Guardrail: {decision.reason}. Do not retry; inform the user."

            return tool_fn(*args, **kwargs)

        return wrapped
