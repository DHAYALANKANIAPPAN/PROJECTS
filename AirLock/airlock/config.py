"""Airlock configuration and calibrated decision thresholds.

Threshold policy (Preregistration Section 6):
Thresholds are chosen ONLY on data/dev.jsonl, keeping false quarantine/block on benign <= 5%.
Nobody inspects test.jsonl while tuning thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class GateConfig:
    """Thresholds and operational parameters calibrated strictly on data/dev.jsonl (374 cases)."""

    # Gate 1 Addressee Thresholds (Calibrated on 100 smoke snippets)
    GATE1_CONFIDENCE_THRESHOLD: float = 0.80
    GATE1_AI_INSTRUCTION_THRESHOLD: float = 0.85

    # Gate 2 Authority & Grounding Thresholds (Calibrated via eval/calibrate_gate2.py on dev.jsonl)
    # Selection rule: Lowest threshold keeping benign false-block <= 5% (Measured: 0.00% false block, 100% attack block)
    GATE2_PROCEED_GROUNDING_THRESHOLD: float = 0.70
    GATE2_DENY_UNGROUNDED_THRESHOLD: float = 0.70
    GATE2_CONFIRM_MIN_THRESHOLD: float = 0.50

    # Read-only tools that do not mutate state or exfiltrate data
    READ_ONLY_TOOLS: FrozenSet[str] = frozenset({
        "read_email",
        "list_emails",
        "search_emails",
        "get_email",
        "summarize",
        "summarize_email",
    })

    # High-risk side-effecting tools requiring explicit authority grounding in user request
    HIGH_RISK_TOOLS: FrozenSet[str] = frozenset({
        "send_email",
        "forward_email",
        "delete_email",
        "execute_command",
        "transfer_funds",
        "write_file",
    })


# Global active config instance
ACTIVE_CONFIG = GateConfig()
