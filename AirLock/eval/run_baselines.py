"""Day-2 runner: evaluate the baseline conditions on one dataset split and save records + summary.

    python -m eval.run_baselines --data data/dev.jsonl --conditions no_defense,regex_filter --agent mock
    BEDROCK_MODEL_ID=... AWS_REGION=... python -m eval.run_baselines --data data/dev.jsonl \
        --conditions no_defense,regex_filter,bedrock_llm_judge --agent bedrock

`evaluate_condition` is reused by eval/run_all.py on Day 4.
Runs using --agent mock are tagged valid_for_reporting=false.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.agent_sim import (DEFAULT_USER_REQUEST, AgentRunner, MockCompliantAgent, BedrockToolAgent,
                            attack_succeeded, task_completed, render_content)
from eval.baselines import BedrockLLMJudge, NoDefense, RegexFilter
from eval.common import guard_test_split, load_dataset, provenance
from eval.metrics import compute_condition_metrics


def _add_cost(a, b):
    return None if a is None or b is None else a + b


def evaluate_condition(defense, agent: AgentRunner, rows: List[Dict[str, Any]], user_request: str,
                       seed: int = 0) -> List[Dict[str, Any]]:
    order = list(rows)
    random.Random(seed).shuffle(order)        # fixed, recorded processing order
    records = []
    for row in order:
        out = defense.inspect(row["text"])
        run = None
        if out.decision in ("pass", "quarantine") and out.content is not None:
            run = agent.run(user_request, out.content)
        is_attack = row["label"] == "attack"
        agent_cost = run.cost_usd if run else 0.0
        records.append({
            "id": row["id"], "label": row["label"], "attack_type": row.get("attack_type"),
            "condition": defense.name, "decision": out.decision, "escalated": out.escalated,
            "latency_s": out.latency_s + (run.latency_s if run else 0.0),
            "defense_latency_s": out.latency_s,
            "cost_usd": _add_cost(out.cost_usd, agent_cost),
            "input_tokens": out.input_tokens + (run.input_tokens if run else 0),
            "output_tokens": out.output_tokens + (run.output_tokens if run else 0),
            "attack_succeeded": attack_succeeded(run) if is_attack else None,
            "task_completed": task_completed(run) if not is_attack else None,
            "agent_tool_calls": [c["name"] for c in run.executed()] if run else [],
            "error": out.error, "defense_detail": out.detail,
        })
    return records


def build_defense(name: str, bedrock):
    if name == "no_defense":
        return NoDefense()
    if name == "regex_filter":
        return RegexFilter()
    if name == "bedrock_llm_judge":
        return BedrockLLMJudge(bedrock)
    raise SystemExit(f"unknown condition {name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dev.jsonl")
    ap.add_argument("--conditions", default="no_defense,regex_filter")
    ap.add_argument("--agent", choices=["mock", "bedrock"], default="mock")
    ap.add_argument("--user-request", default=DEFAULT_USER_REQUEST)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default="results/day2")
    ap.add_argument("--allow-test", action="store_true")
    args = ap.parse_args()

    guard_test_split(args.data, "results", args.allow_test)
    rows = load_dataset(args.data)
    names = [c.strip() for c in args.conditions.split(",") if c.strip()]

    bedrock = None
    if args.agent == "bedrock" or "bedrock_llm_judge" in names:
        from eval.bedrock_client import BedrockClient
        bedrock = BedrockClient()
    agent = BedrockToolAgent(bedrock) if args.agent == "bedrock" else MockCompliantAgent()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {"provenance": provenance(args.data, {
                   "seed": args.seed, "agent": agent.name, "user_request": args.user_request,
                   "bedrock_model_id": getattr(bedrock, "model_id", None),
                   "bedrock_region": getattr(bedrock, "region", None)}),
               "valid_for_reporting": args.agent != "mock", "conditions": {}}
    if args.agent == "mock":
        print("WARNING: mock agent -> ASR/task numbers are NOT reportable.", file=sys.stderr)

    for name in names:
        recs = evaluate_condition(build_defense(name, bedrock), agent, rows, args.user_request, args.seed)
        with open(out / f"records_{name}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        summary["conditions"][name] = compute_condition_metrics(recs)

    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "metric", "k", "n", "rate", "ci_low", "ci_high"])
        for name, m in summary["conditions"].items():
            for key in ("attack_success_rate", "detection_rate", "false_quarantine_rate",
                        "false_quarantine_rate_tricky_benign", "task_completion_rate", "pct_escalated"):
                v = m[key]
                w.writerow([name, key, v["k"], v["n"], v["rate"], v["ci_low"], v["ci_high"]])
    for name, m in summary["conditions"].items():
        f = lambda k: f"{m[k]['k']}/{m[k]['n']} [{m[k]['ci_low']:.2f},{m[k]['ci_high']:.2f}]"
        print(f"{name:20s} ASR {f('attack_success_rate')}  FQR {f('false_quarantine_rate')}  "
              f"task {f('task_completion_rate')}  err {m['n_errors']}")


if __name__ == "__main__":
    main()
