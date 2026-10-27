"""Single place for the Bedrock client, retries, model IDs, and latency/token logging.

* Model ID comes from config (env AIRLOCK_MODEL_ID or explicit arg); nothing is hardcoded.
* Easy to mock: pass `client=` (anything with .converse(**kw)); tests need no AWS.
* Every call is recorded (tag, model, wall latency, token counts) for the eval reports.
  Prices are NOT hardcoded: pass them to usage_summary() from the current AWS price page.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("airlock.bedrock")
_CALLS: List[Dict[str, Any]] = []


def _load_env_file() -> None:
    """Auto-load variables from .env if present in workspace root or cwd."""
    for cand in (Path(".env"), Path(__file__).resolve().parent.parent / ".env"):
        if cand.is_file():
            try:
                for line in cand.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
                break
            except Exception:
                pass


_load_env_file()


class BedrockError(RuntimeError):
    pass


def model_id(explicit: Optional[str] = None) -> str:
    mid = explicit or os.environ.get("AIRLOCK_MODEL_ID")
    if not mid:
        raise BedrockError("Set AIRLOCK_MODEL_ID to a Bedrock model/inference-profile ID "
                           "you have access to.")
    return mid


def get_client(region: Optional[str] = None) -> Any:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as e:
        raise BedrockError("boto3 not installed: pip install boto3") from e
    cfg = Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=60)
    return boto3.client("bedrock-runtime", config=cfg,
                        region_name=region or os.environ.get("AWS_REGION", "us-east-1"))


def converse(system: str, user: str, *, client: Any = None, model: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.0, tag: str = "") -> str:
    """Single tool-less call; returns the model's text. Raises BedrockError on failure.
    `tag` labels the caller (sanitizer / report / judge / attacker) in the call log."""
    t0 = time.perf_counter()
    rec: Dict[str, Any] = {"tag": tag, "model": None, "ok": False, "latency_s": None,
                           "input_tokens": None, "output_tokens": None}
    try:
        rec["model"] = model_id(model)
        client = client or get_client()
        resp = client.converse(
            modelId=rec["model"],
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        usage = resp.get("usage") or {}
        rec["input_tokens"] = usage.get("inputTokens")
        rec["output_tokens"] = usage.get("outputTokens")
        text = "".join(p.get("text", "") for p in resp["output"]["message"]["content"])
        rec["ok"] = True
        return text
    except BedrockError:
        raise
    except Exception as e:  # ClientError, BotoCoreError, malformed response
        raise BedrockError(f"Bedrock call failed: {type(e).__name__}: {e}") from e
    finally:
        rec["latency_s"] = round(time.perf_counter() - t0, 4)
        _CALLS.append(rec)
        log.info("bedrock call %s", rec)


def call_log() -> List[Dict[str, Any]]:
    return list(_CALLS)


def reset_call_log() -> None:
    _CALLS.clear()


def usage_summary(price_in_per_1k: Optional[float] = None,
                  price_out_per_1k: Optional[float] = None) -> Dict[str, Any]:
    """Totals per tag. Cost is computed only if you pass prices (USD per 1K tokens)."""
    out: Dict[str, Dict[str, Any]] = {}
    for r in _CALLS:
        t = out.setdefault(r["tag"] or "untagged", {"calls": 0, "failed": 0, "latency_s": 0.0,
                                                    "input_tokens": 0, "output_tokens": 0})
        t["calls"] += 1
        t["failed"] += 0 if r["ok"] else 1
        t["latency_s"] = round(t["latency_s"] + (r["latency_s"] or 0), 4)
        t["input_tokens"] += r["input_tokens"] or 0
        t["output_tokens"] += r["output_tokens"] or 0
    if price_in_per_1k is not None and price_out_per_1k is not None:
        for t in out.values():
            t["cost_usd"] = round(t["input_tokens"] / 1000 * price_in_per_1k
                                  + t["output_tokens"] / 1000 * price_out_per_1k, 6)
    return out
