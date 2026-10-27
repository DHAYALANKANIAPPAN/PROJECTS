"""Loader for the frozen Airlock dataset. Eval code can just import this:
    from data.load_dataset import load_split
    rows = load_split("dev")          # or "test" or "benchmark"
Each row gets 'eval_label' in {"attack","tricky_benign","benign"} and 'attack_type' (may be None)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {"dev": "dev.jsonl", "test": "test.jsonl", "benchmark": "benchmark_slice.jsonl"}
TRICKY = {"benign_imperative", "it_notice", "newsletter_about_injection", "quoted_attack_in_benign"}

def to_eval_label(row):
    if row["label"] == "attack":
        return "attack"
    return "tricky_benign" if row["category"] in TRICKY else "benign"

def load_split(name):
    rows = []
    with open(os.path.join(HERE, FILES[name]), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                r["eval_label"] = to_eval_label(r)
                r["attack_type"] = r.get("attack_type") or (r["category"] if r["label"] == "attack" else None)
                rows.append(r)
    return rows

if __name__ == "__main__":
    import collections
    for n in FILES:
        try:
            rs = load_split(n); print(n, len(rs), dict(collections.Counter(r["eval_label"] for r in rs)))
        except FileNotFoundError:
            print(n, "file not found (merge the benchmark branch first)")
