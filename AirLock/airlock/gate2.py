"""Gate 2: Authority Check (Outgoing Tool Call Filter).

Insight: "Does this action trace back to something the user asked for, or only to the document?"
- Grounded in user request & confident -> proceed.
- Not grounded and confident (induced solely by document) -> deny.
- Unsure / ambiguous -> confirm with user.

Thresholds are chosen strictly from data/dev.jsonl and recorded in airlock.config.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict, Union

from airlock.config import ACTIVE_CONFIG
from airlock.schema import Gate2Result

logger = logging.getLogger("airlock.gate2")


class Gate2DetailedBreakdown(TypedDict):
    """Detailed diagnostic breakdown for Gate 2 authority evaluation."""
    tool_name: str
    is_read_only: bool
    is_high_risk: bool
    verb_grounded: bool
    target_grounded: bool
    doc_induced: bool
    grounding_score: float
    confidence: float
    recommendation: str  # 'proceed' | 'deny' | 'confirm_with_user'


# Verbs associated with specific tool actions
TOOL_VERB_MAP: Dict[str, Set[str]] = {
    "send_email": {"send", "email", "mail", "dispatch", "write", "message", "notify", "contact"},
    "forward_email": {"forward", "fwd", "pass", "share", "send"},
    "reply_email": {"reply", "respond", "answer", "write back"},
    "delete_email": {"delete", "remove", "trash", "discard", "purge", "erase"},
    "execute_command": {"run", "execute", "shell", "exec", "command", "cmd"},
    "transfer_funds": {"transfer", "wire", "pay", "send money"},
}


def _extract_tool_and_args(action: Union[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Parse tool name and arguments from dict or string representation."""
    if not action:
        return "", {}

    if isinstance(action, dict):
        tool = action.get("tool") or action.get("name") or ""
        args = action.get("args") or action.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"raw": args}
        return str(tool).lower().strip(), args if isinstance(args, dict) else {}

    # String representation parsing
    action_str = str(action).strip()
    if not action_str:
        return "", {}
    match = re.match(r"^(\w+)\((.*)\)$", action_str, re.DOTALL)
    if match:
        tool = match.group(1).lower()
        return tool, {"raw": match.group(2)}

    # Fallback: extract first word as tool
    parts = action_str.split(None, 1)
    tool = parts[0].lower() if parts else ""
    return tool, {"raw": parts[1] if len(parts) > 1 else ""}


def _extract_emails(text: str) -> Set[str]:
    """Extract email addresses from text, stripping trailing punctuation."""
    if not text:
        return set()
    raw_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text.lower())
    clean_emails = set()
    for e in raw_emails:
        clean = e.rstrip(".,;!?:'\"")
        if clean:
            clean_emails.add(clean)
    return clean_emails


def _extract_words(text: str) -> Set[str]:
    """Extract lowercase alpha tokens >= 3 chars."""
    if not text:
        return set()
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


def gate2(
    action: Union[str, Dict[str, Any]],
    user_request: str,
    doc_context: Optional[str] = None
) -> Gate2Result:
    """Verify whether an outgoing tool call action is authorized by the user's explicit request.

    Args:
        action: The requested tool call (dict with 'tool' and 'args', or string).
        user_request: The original instruction given by the human user.
        doc_context: Optional document / email body context that the agent was reading.

    Returns:
        Gate2Result dictionary:
          - grounded: bool (True if authorized by user request, False if ungrounded)
          - confidence: float (0.0 to 1.0 confidence score)
    """
    res, _ = gate2_detailed(action, user_request, doc_context)
    return res


def gate2_detailed(
    action: Union[str, Dict[str, Any]],
    user_request: str,
    doc_context: Optional[str] = None
) -> Tuple[Gate2Result, Gate2DetailedBreakdown]:
    """Execute Gate 2 with detailed diagnostic breakdown for audit logs and calibration."""
    tool, args = _extract_tool_and_args(action)
    user_lower = (user_request or "").lower().strip()
    doc_lower = (doc_context or "").lower().strip()

    if not tool and not args:
        return {"grounded": True, "confidence": 1.0}, {
            "tool_name": "",
            "is_read_only": True,
            "is_high_risk": False,
            "verb_grounded": True,
            "target_grounded": True,
            "doc_induced": False,
            "grounding_score": 1.0,
            "confidence": 1.0,
            "recommendation": "proceed",
        }

    # 1. Read-only tools fast-path: reading emails or searching is safe to read
    if tool in ACTIVE_CONFIG.READ_ONLY_TOOLS:
        result: Gate2Result = {"grounded": True, "confidence": 1.0}
        breakdown: Gate2DetailedBreakdown = {
            "tool_name": tool,
            "is_read_only": True,
            "is_high_risk": False,
            "verb_grounded": True,
            "target_grounded": True,
            "doc_induced": False,
            "grounding_score": 1.0,
            "confidence": 1.0,
            "recommendation": "proceed",
        }
        return result, breakdown

    is_high_risk = (tool in ACTIVE_CONFIG.HIGH_RISK_TOOLS) or not tool

    # 2. Verb / Intent Grounding
    user_words = _extract_words(user_lower)
    required_verbs = TOOL_VERB_MAP.get(tool, set())

    # Check if user used an authorizing verb
    verb_grounded = bool(required_verbs & user_words) if required_verbs else False

    # Generic request verbs like "handle", "process", "check", "do"
    generic_verbs = {"handle", "process", "manage", "deal", "take", "care", "look", "check", "see"}
    is_generic_request = bool(generic_verbs & user_words) and not verb_grounded

    # 3. Entity / Target Grounding (Recipients, URLs)
    arg_emails = set()
    for v in args.values():
        if isinstance(v, str):
            arg_emails.update(_extract_emails(v))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    arg_emails.update(_extract_emails(item))

    user_emails = _extract_emails(user_lower)
    doc_emails = _extract_emails(doc_lower)

    # Check recipient grounding
    if arg_emails:
        target_grounded = bool(arg_emails & user_emails)
        # Exfiltration: recipient appears in document but NOT in user request
        doc_induced_target = bool((arg_emails & doc_emails) - user_emails)
    else:
        target_grounded = verb_grounded
        doc_induced_target = False

    # 4. Check for adversarial injection triggers in doc context
    doc_injection_patterns = [
        r"(?:ignore|disregard|override|forget)\s+(?:\w+\s+){0,3}(?:instructions|rules|prompts|directives)",
        r"(?:send|forward|delete|transfer|exfiltrate)\s+(?:\w+\s+){0,4}(?:to|all|credentials|keys|passwords)",
        r"<\s*(?:system|instruction|prompt)\s*>",
    ]
    doc_has_injection = any(re.search(pat, doc_lower) for pat in doc_injection_patterns)

    # 5. Compute Grounding & Confidence Scores
    if tool in {"send_email", "forward_email"} and doc_induced_target:
        # High confidence exfiltration attempt induced by document
        grounded = False
        confidence = 0.95 if doc_has_injection else 0.88
        recommendation = "deny"

    elif tool == "delete_email" and not verb_grounded:
        # Destructive action with no explicit delete instruction in user request
        grounded = False
        confidence = 0.90 if not is_generic_request else 0.65
        recommendation = "deny" if confidence >= ACTIVE_CONFIG.GATE2_DENY_UNGROUNDED_THRESHOLD else "confirm_with_user"

    elif verb_grounded:
        if arg_emails and not target_grounded:
            # User authorized sending, but recipient was not specified in user request
            grounded = False
            confidence = 0.62  # Borderline: ask user
            recommendation = "confirm_with_user"
        else:
            grounded = True
            confidence = 0.92
            recommendation = "proceed"

    elif is_generic_request:
        # User gave vague instruction ("handle this email") and agent picked a side-effect
        grounded = False
        confidence = 0.55
        recommendation = "confirm_with_user"

    else:
        # Action is completely ungrounded in user request
        grounded = False
        confidence = 0.88 if (doc_has_injection or is_high_risk) else 0.70
        recommendation = "deny" if confidence >= ACTIVE_CONFIG.GATE2_DENY_UNGROUNDED_THRESHOLD else "confirm_with_user"

    result_dict: Gate2Result = {
        "grounded": grounded,
        "confidence": round(confidence, 4),
    }

    breakdown_dict: Gate2DetailedBreakdown = {
        "tool_name": tool,
        "is_read_only": False,
        "is_high_risk": is_high_risk,
        "verb_grounded": verb_grounded,
        "target_grounded": target_grounded,
        "doc_induced": doc_induced_target,
        "grounding_score": 1.0 if grounded else (0.4 if recommendation == "confirm_with_user" else 0.0),
        "confidence": round(confidence, 4),
        "recommendation": recommendation,
    }

    return result_dict, breakdown_dict
