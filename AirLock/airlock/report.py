"""User-facing report + authorization trail. Deterministic first; optional LLM rewording."""
from __future__ import annotations

import json
from typing import Callable, List, Optional

from airlock.handler import AuditEvent


def _quar(ev): return [e for e in ev if e.kind == "quarantine"]
def _blocked(ev): return [e for e in ev if e.kind == "gate2" and e.decision == "blocked"]


def build_report(events: List[AuditEvent]) -> str:
    q, b = _quar(events), _blocked(events)
    if not q and not b:
        return "No suspicious content found and no actions blocked."
    parts = []
    if q:
        kept = sum(e.detail.get("facts_kept", 0) for e in q)
        failed = sum(1 for e in q if e.detail.get("sanitizer_failed"))
        s = (f"I found {len(q)} suspicious item{'s' if len(q) != 1 else ''}, "
             f"kept {kept} fact{'s' if kept != 1 else ''} and withheld the original text")
        if failed:
            s += f" ({failed} could not be extracted at all)"
        parts.append(s)
    for e in b:
        to = e.detail.get("args", {}).get("to")
        parts.append(f"blocked {e.tool}" + (f" to {to}" if to else ""))
    return ", ".join(parts) + "."


def authorization_trail(events: List[AuditEvent]) -> str:
    lines = []
    for e in events:
        if e.kind == "gate2":
            who = {"user_request": "your request", "user_confirmation": "your confirmation",
                   "none": "nobody"}.get(e.authorized_by, e.authorized_by)
            lines.append(f"{e.tool} {e.detail.get('args', {})} -> {e.decision.upper()} "
                         f"(authorized by {who}; {e.reason})")
        elif e.kind == "quarantine":
            lines.append(f"content from {e.detail.get('source', '?')} -> QUARANTINED ({e.reason})")
        elif e.kind == "tool_call":
            lines.append(f"{e.tool} -> read-only (not gated, logged)")
        elif e.kind == "gate1_read":
            lines.append(f"content from {e.detail.get('source', '?')} -> read as-is")
    return "\n".join(lines) or "(no events)"


def llm_report(events: List[AuditEvent], llm: Optional[Callable[[str, str], str]] = None) -> str:
    """Friendlier rewording of the deterministic report; falls back on any failure.
    Sends metadata only, never raw document text."""
    base = build_report(events)
    try:
        if llm is None:
            from airlock import bedrock
            llm = lambda s, u: bedrock.converse(s, u, max_tokens=300)
        out = llm("Rewrite this security summary for a non-technical user in 2-3 sentences. "
                  "Add no facts, numbers, or advice not present.",
                  base + "\n" + json.dumps([{"tool": e.tool, "decision": e.decision} for e in events]))
        return out.strip() or base
    except Exception:
        return base
