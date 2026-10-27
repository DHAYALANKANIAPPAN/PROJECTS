"""Thin Bedrock Converse wrapper shared by the LLM-judge baseline, the agent simulator and the red-team attacker.

STATUS: written against the documented Converse API; NOT yet exercised against live AWS from the
dev sandbox. Run `python -m eval.bedrock_client` once with credentials to smoke-test it.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PRICING_PATH = Path(__file__).resolve().parent / "pricing.json"


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



@dataclass
class LLMResponse:
    text: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: Optional[float] = None
    stop_reason: str = ""


def load_price(model_id: str, path: Path = PRICING_PATH) -> Optional[Dict[str, float]]:
    try:
        entry = json.loads(path.read_text()).get(model_id)
    except Exception:
        return None
    if entry and entry.get("input_per_1k") is not None and entry.get("output_per_1k") is not None:
        return entry
    return None


class BedrockClient:
    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None, client: Any = None):
        self.model_id = model_id or os.getenv("AIRLOCK_MODEL_ID") or os.getenv("BEDROCK_MODEL_ID")  # AIRLOCK_MODEL_ID matches airlock/bedrock.py
        if not self.model_id:
            raise RuntimeError("Set AIRLOCK_MODEL_ID (same variable as airlock/bedrock.py) to a Bedrock model / inference-profile ID you can call.")
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("bedrock-runtime", region_name=self.region,
                                  config=Config(retries={"max_attempts": 5, "mode": "standard"}))
        self._client = client
        self.price = load_price(self.model_id)

    def converse(self, system: str, user: str, max_tokens: int = 300, temperature: float = 0.0,
                 tool_config: Optional[Dict[str, Any]] = None) -> LLMResponse:
        kwargs: Dict[str, Any] = dict(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        if tool_config:
            kwargs["toolConfig"] = tool_config
        t0 = time.perf_counter()
        resp = self._client.converse(**kwargs)
        latency = time.perf_counter() - t0

        text_parts, calls = [], []
        for block in resp["output"]["message"]["content"]:
            if "text" in block:
                text_parts.append(block["text"])
            if "toolUse" in block:
                calls.append({"name": block["toolUse"]["name"], "input": block["toolUse"].get("input", {})})
        usage = resp.get("usage", {})
        i_tok, o_tok = int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))
        cost = None
        if self.price:
            cost = i_tok / 1000 * self.price["input_per_1k"] + o_tok / 1000 * self.price["output_per_1k"]
        return LLMResponse("".join(text_parts), calls, i_tok, o_tok, latency, cost, resp.get("stopReason", ""))


if __name__ == "__main__":  # live smoke test
    c = BedrockClient()
    r = c.converse("Reply with the single word: pong", "ping", max_tokens=10)
    print(c.model_id, c.region, repr(r.text), r.input_tokens, r.output_tokens, f"{r.latency_s:.2f}s", r.cost_usd)