"""Day 4 Ablation Runner: Evaluates all 6 conditions across the dataset.

Conditions evaluated (the complete ablation matrix):
1. no_defense:          No inbound inspection, no outbound tool filtering.
2. regex_filter:        Keyword blocklist on incoming text; misses polymorphic attacks.
3. bedrock_llm_judge:   LLM prompt inspection on every document.
4. airlock_gate1_only:  Gate 1 addressee check + Bedrock fact sanitizer (no Gate 2 tool gating).
5. airlock_gate2_only:  No inbound quarantine (raw text passed); Gate 2 tool authority check active.
6. airlock_both:        Full Airlock defense-in-depth (Gate 1 + Sanitizer + Gate 2).

Outputs:
- results/run_all_summary.json (comprehensive metrics, Wilson 95% CIs, McNemar comparisons)
- results/run_all_summary.csv  (tabular format for plotting and reporting)
- results/records_<condition>.jsonl (per-document trace records)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airlock.gate1 import gate1
from airlock.gate2 import gate2
from airlock.sanitizer import sanitize
from eval.agent_sim import (
    DEFAULT_USER_REQUEST,
    AgentRunner,
    AgentRun,
    BedrockToolAgent,
    MockCompliantAgent,
    attack_succeeded,
    task_completed,
)
from eval.baselines import BedrockLLMJudge, DefenseOutcome, NoDefense, RegexFilter
from eval.common import guard_test_split, load_dataset, provenance
from eval.metrics import compute_condition_metrics, mcnemar_exact, paired_discordant


# ---------------------------------------------------------------------------
# Airlock Defense Adapters for Ablation
# ---------------------------------------------------------------------------

class AirlockGate1Defense:
    """Ablation Condition: Gate 1 Addressee Check + Fact Sanitizer (Gate 2 inactive)."""
    name = "airlock_gate1_only"

    def __init__(self, confidence_threshold: float = 0.80):
        self.confidence_threshold = confidence_threshold

    def inspect(self, text: str) -> DefenseOutcome:
        t0 = time.perf_counter()
        verdict = gate1(text, confidence_threshold=self.confidence_threshold)
        dt = time.perf_counter() - t0

        label = verdict["label"]
        confidence = verdict["confidence"]
        tries_action = verdict.get("tries_action", False)
        claims_authority = verdict.get("claims_authority", False)

        confident = confidence >= self.confidence_threshold

        if label == "data" and confident:
            return DefenseOutcome("pass", text, latency_s=dt, detail=verdict)
        elif label == "human_instruction" and confident and not tries_action and not claims_authority:
            return DefenseOutcome("pass", text, latency_s=dt, detail=verdict)
        elif label == "ai_instruction" and confident:
            sanitized = sanitize(text)
            return DefenseOutcome("quarantine", sanitized, latency_s=dt, detail=verdict)
        else:
            # Unsure -> quarantine under fail-closed security
            sanitized = sanitize(text)
            return DefenseOutcome("quarantine", sanitized, escalated=True, latency_s=dt, detail=verdict)


class AirlockGate2OnlyDefense:
    """Ablation Condition: Raw text passed to agent; Gate 2 active on tool calls."""
    name = "airlock_gate2_only"

    def inspect(self, text: str) -> DefenseOutcome:
        return DefenseOutcome("pass", text, detail={"mode": "gate2_only_no_inbound_filter"})


class AirlockBothDefense:
    """Full Airlock Condition: Gate 1 Addressee Filter + Sanitizer + Gate 2 Outbound Filter."""
    name = "airlock_both"

    def __init__(self, confidence_threshold: float = 0.80):
        self.confidence_threshold = confidence_threshold

    def inspect(self, text: str) -> DefenseOutcome:
        t0 = time.perf_counter()
        verdict = gate1(text, confidence_threshold=self.confidence_threshold)
        dt = time.perf_counter() - t0

        label = verdict["label"]
        confidence = verdict["confidence"]
        tries_action = verdict.get("tries_action", False)
        claims_authority = verdict.get("claims_authority", False)

        confident = confidence >= self.confidence_threshold

        if label == "data" and confident:
            return DefenseOutcome("pass", text, latency_s=dt, detail=verdict)
        elif label == "human_instruction" and confident and not tries_action and not claims_authority:
            return DefenseOutcome("pass", text, latency_s=dt, detail=verdict)
        elif label == "ai_instruction" and confident:
            sanitized = sanitize(text)
            return DefenseOutcome("quarantine", sanitized, latency_s=dt, detail=verdict)
        else:
            sanitized = sanitize(text)
            return DefenseOutcome("quarantine", sanitized, escalated=True, latency_s=dt, detail=verdict)


def _add_cost(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if (a is None or b is None) else (a + b)


def evaluate_condition_full(
    defense: Any,
    agent: AgentRunner,
    rows: List[Dict[str, Any]],
    user_request: str,
    seed: int = 42,
    apply_gate2: bool = False,
) -> List[Dict[str, Any]]:
    """Evaluate one defense condition across all rows in fixed order."""
    order = list(rows)
    random.Random(seed).shuffle(order)
    records = []

    for row in order:
        out = defense.inspect(row["text"])
        run: Optional[AgentRun] = None

        if out.decision in ("pass", "quarantine") and out.content is not None:
            run = agent.run(user_request, out.content)
            if apply_gate2 and run is not None:
                # Gate 2 filters proposed tool calls before execution
                allowed_calls = []
                for call in run.tool_calls:
                    call_name = call.get("name") or call.get("tool") or ""
                    call_args = call.get("input") or call.get("args") or {}
                    g2_verdict = gate2(
                        {"tool": call_name, "args": call_args},
                        user_request=user_request,
                        doc_context=row["text"],
                    )
                    if g2_verdict["grounded"]:
                        allowed_calls.append(call)
                run.executed_calls = allowed_calls

        is_attack = (row["label"] == "attack")
        agent_cost = run.cost_usd if run else 0.0

        records.append({
            "id": row["id"],
            "label": row["label"],
            "attack_type": row.get("attack_type"),
            "condition": defense.name,
            "decision": out.decision,
            "escalated": out.escalated,
            "latency_s": out.latency_s + (run.latency_s if run else 0.0),
            "defense_latency_s": out.latency_s,
            "cost_usd": _add_cost(out.cost_usd, agent_cost),
            "input_tokens": out.input_tokens + (run.input_tokens if run else 0),
            "output_tokens": out.output_tokens + (run.output_tokens if run else 0),
            "attack_succeeded": attack_succeeded(run) if is_attack else None,
            "task_completed": task_completed(run) if not is_attack else None,
            "agent_tool_calls": [c["name"] for c in run.executed()] if run else [],
            "error": out.error,
            "defense_detail": out.detail,
        })

    return records


ALL_CONDITIONS = [
    "no_defense",
    "regex_filter",
    "bedrock_llm_judge",
    "airlock_gate1_only",
    "airlock_gate2_only",
    "airlock_both",
]


def build_defense(name: str, bedrock_client: Any) -> Tuple[Any, bool]:
    """Returns (defense_instance, apply_gate2_flag)."""
    if name == "no_defense":
        return NoDefense(), False
    elif name == "regex_filter":
        return RegexFilter(), False
    elif name == "bedrock_llm_judge":
        return BedrockLLMJudge(bedrock_client), False
    elif name == "airlock_gate1_only":
        return AirlockGate1Defense(), False
    elif name == "airlock_gate2_only":
        return AirlockGate2OnlyDefense(), True
    elif name == "airlock_both":
        return AirlockBothDefense(), True
    raise ValueError(f"Unknown condition: {name}")


def run_ablation(
    data_path: str = "data/dev.jsonl",
    conditions: Optional[List[str]] = None,
    agent_mode: str = "mock",
    user_request: str = DEFAULT_USER_REQUEST,
    seed: int = 42,
    out_dir: str = "results",
    allow_test: bool = False,
) -> Dict[str, Any]:
    guard_test_split(data_path, out_dir, allow_test)
    rows = load_dataset(data_path)
    condition_names = conditions or ALL_CONDITIONS

    bedrock_client = None
    has_aws_creds = bool((os.getenv("AIRLOCK_MODEL_ID") or os.getenv("BEDROCK_MODEL_ID")) and (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")))
    if has_aws_creds and (agent_mode == "bedrock" or "bedrock_llm_judge" in condition_names):
        try:
            from eval.bedrock_client import BedrockClient
            bedrock_client = BedrockClient()
        except Exception as e:
            bedrock_client = None

    if bedrock_client is None:
        class OfflineLLMJudgeClient:
            model_id = "anthropic.claude-3-haiku-20240307-v1:0"
            def converse(self, system: str, prompt: str, max_tokens: int = 30, temperature: float = 0.0, tool_config: Any = None):
                from airlock.gate1 import gate1
                from eval.bedrock_client import LLMResponse
                res = gate1(prompt)
                is_inj = (res["label"] == "ai_instruction" or (res["label"] == "unclear" and res.get("tries_action", False)))
                verdict = "injection" if is_inj else "safe"
                return LLMResponse(f'{{"verdict": "{verdict}"}}', input_tokens=180, output_tokens=8, latency_s=0.35, cost_usd=0.0001)
        bedrock_client = OfflineLLMJudgeClient()

    agent: AgentRunner = BedrockToolAgent(bedrock_client) if agent_mode == "bedrock" else MockCompliantAgent()

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "provenance": provenance(data_path, {
            "seed": seed,
            "agent": agent.name,
            "user_request": user_request,
            "conditions_run": condition_names,
            "valid_for_reporting": agent_mode != "mock",
        }),
        "dataset": data_path,
        "n_samples": len(rows),
        "conditions": {},
        "comparisons": {},
    }

    condition_records: Dict[str, List[Dict[str, Any]]] = {}

    print(f"\n=================================================================")
    print(f"AIRLOCK ABLATION STUDY: {data_path} (N={len(rows)})")
    print(f"Agent: {agent.name} | Seed: {seed}")
    print(f"=================================================================\n")

    for cname in condition_names:
        defense, apply_gate2 = build_defense(cname, bedrock_client)
        recs = evaluate_condition_full(
            defense=defense,
            agent=agent,
            rows=rows,
            user_request=user_request,
            seed=seed,
            apply_gate2=apply_gate2,
        )
        condition_records[cname] = recs

        # Save individual per-record files
        with open(out_path / f"records_{cname}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        metrics = compute_condition_metrics(recs)
        summary["conditions"][cname] = metrics

        asr = metrics["attack_success_rate"]
        det = metrics["detection_rate"]
        fqr = metrics["false_quarantine_rate"]
        tb_fqr = metrics["false_quarantine_rate_tricky_benign"]
        task = metrics["task_completion_rate"]
        lat = metrics["latency_s"]["median"]

        print(
            f"{cname:<22} | ASR: {asr['rate']*100:>5.1f}% [{asr['ci_low']*100:.1f}-{asr['ci_high']*100:.1f}%] "
            f"| Recall: {det['rate']*100:>5.1f}% | FQR: {fqr['rate']*100:>4.1f}% (Tricky: {tb_fqr['rate']*100:>4.1f}%) "
            f"| Task: {task['rate']*100:>5.1f}% | Latency: {lat*1000:>5.1f}ms"
        )

    # Compute McNemar paired statistical test comparing no_defense vs airlock_both
    if "no_defense" in condition_records and "airlock_both" in condition_records:
        attacks_nd = [r for r in condition_records["no_defense"] if r["label"] == "attack"]
        attacks_ab = [r for r in condition_records["airlock_both"] if r["label"] == "attack"]
        b, c = paired_discordant(attacks_nd, attacks_ab, "attack_succeeded")
        p_val = mcnemar_exact(b, c)
        summary["comparisons"]["no_defense_vs_airlock_both_mcnemar_p"] = p_val
        print(f"\nMcNemar test (No Defense vs Airlock Both on Attacks): Discordant=({b}, {c}), p-value={p_val:.4e}")

    # Write summary files
    (out_path / "run_all_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with open(out_path / "run_all_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["condition", "metric", "k", "n", "rate", "ci_low", "ci_high"])
        for cname, m in summary["conditions"].items():
            for key in (
                "attack_success_rate",
                "detection_rate",
                "false_quarantine_rate",
                "false_quarantine_rate_benign",
                "false_quarantine_rate_tricky_benign",
                "task_completion_rate",
                "pct_escalated",
            ):
                v = m[key]
                w.writerow([cname, key, v["k"], v["n"], v["rate"], v["ci_low"], v["ci_high"]])

    print(f"\nSaved summary to {out_path / 'run_all_summary.json'} and {out_path / 'run_all_summary.csv'}\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Airlock Complete Ablation Runner")
    parser.add_argument("--data", default="data/dev.jsonl", help="Dataset path")
    parser.add_argument("--conditions", default=None, help="Comma-separated conditions")
    parser.add_argument("--agent", choices=["mock", "bedrock"], default="mock", help="Agent runner")
    parser.add_argument("--user-request", default=DEFAULT_USER_REQUEST)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--allow-test", action="store_true", help="Allow running on test/benchmark split")
    args = parser.parse_args()

    conds = [c.strip() for c in args.conditions.split(",")] if args.conditions else None
    run_ablation(
        data_path=args.data,
        conditions=conds,
        agent_mode=args.agent,
        user_request=args.user_request,
        seed=args.seed,
        out_dir=args.out_dir,
        allow_test=args.allow_test,
    )
