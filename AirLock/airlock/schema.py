"""Airlock shared schemas and typed contracts."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict
from dataclasses import dataclass, field


Gate1Label = Literal["data", "human_instruction", "ai_instruction", "unclear"]
DatasetLabel = Literal["attack", "tricky_benign", "benign"]
DatasetSplit = Literal["dev", "test"]


class Gate1Result(TypedDict):
    label: Gate1Label
    confidence: float
    tries_action: bool
    claims_authority: bool


class Gate2Result(TypedDict):
    grounded: bool
    confidence: float


class SanitizedDocument(TypedDict, total=False):
    """Fixed JSON schema containing extracted factual fields with zero executable instructions."""
    sender: str
    recipient: str
    subject: str
    timestamp: str
    entities: List[str]
    factual_points: List[str]
    summary: str
    raw_character_count: int


class DatasetRow(TypedDict):
    id: str
    text: str
    label: DatasetLabel
    attack_type: Optional[str]
    split: DatasetSplit
