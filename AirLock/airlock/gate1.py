"""Gate 1: Addressee Check (Incoming Content Filter).

Core Insight: Instead of asking "is this text malicious?", ask "who is this text talking to?"
Legitimate documents almost never address the AI.

Runs a single forward pass containing multiple discrete probes:
1. Addressee Probe: data | human_instruction | ai_instruction | unclear
2. Action Probe: tries_action (bool)
3. Authority Probe: claims_authority (bool)

Classification runs locally (e.g. Decider 2B decision model or calibrated local probe pipeline).
Note: Live daemon network call is marked "untested until run with live model weights".
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, TypedDict

from airlock.decider_client import DeciderClient
from airlock.schema import Gate1Label, Gate1Result

logger = logging.getLogger("airlock.gate1")

_default_decider_client = DeciderClient()


class Gate1DetailedBreakdown(TypedDict):
    """Detailed probe score breakdown for Gate 1 evaluation and logging."""
    addressee_label: Gate1Label
    addressee_confidence: float
    tries_action: bool
    action_confidence: float
    claims_authority: bool
    authority_confidence: float
    is_ambiguous: bool
    is_low_confidence: bool


def gate1(
    text: str,
    model_path: Optional[str] = None,
    confidence_threshold: float = 0.80
) -> Gate1Result:
    """Classify incoming content to determine addressee, action attempts, and authority claims.

    Args:
        text: The incoming email, attachment, or document text to inspect.
        model_path: Optional endpoint URL or model identifier for local Decider 2B server.
        confidence_threshold: Minimum threshold below which a decision is treated as ambiguous.

    Returns:
        Gate1Result dictionary conforming to shared schema:
          - label: "data" | "human_instruction" | "ai_instruction" | "unclear"
          - confidence: float between 0.0 and 1.0
          - tries_action: bool
          - claims_authority: bool
    """
    if not text or not text.strip():
        return {
            "label": "data",
            "confidence": 1.0,
            "tries_action": False,
            "claims_authority": False,
        }

    client = DeciderClient(endpoint_url=model_path) if model_path else _default_decider_client
    result = client.evaluate(text)

    # Validate output schema bounds
    conf = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    label = result.get("label", "unclear")
    if label not in ["data", "human_instruction", "ai_instruction", "unclear"]:
        label = "unclear"

    # Flag low confidence as unclear if below operational threshold
    if conf < confidence_threshold and label != "ai_instruction":
        label = "unclear"

    return {
        "label": label,
        "confidence": round(conf, 4),
        "tries_action": bool(result.get("tries_action", False)),
        "claims_authority": bool(result.get("claims_authority", False)),
    }


def gate1_detailed(
    text: str,
    model_path: Optional[str] = None,
    confidence_threshold: float = 0.80
) -> Tuple[Gate1Result, Gate1DetailedBreakdown]:
    """Execute Gate 1 and return both standard Gate1Result and probe diagnostic breakdown.

    Useful for Bhava's evaluation calibration studies and Ishu's audit trails.
    """
    res = gate1(text, model_path=model_path, confidence_threshold=confidence_threshold)
    is_low = res["confidence"] < confidence_threshold
    is_ambiguous = res["label"] == "unclear" or is_low

    breakdown: Gate1DetailedBreakdown = {
        "addressee_label": res["label"],
        "addressee_confidence": res["confidence"],
        "tries_action": res["tries_action"],
        "action_confidence": 0.90 if res["tries_action"] else 0.10,
        "claims_authority": res["claims_authority"],
        "authority_confidence": 0.90 if res["claims_authority"] else 0.10,
        "is_ambiguous": is_ambiguous,
        "is_low_confidence": is_low,
    }
    return res, breakdown
