"""Shared helpers for the evaluation harness: dataset loading, provenance, test-split guard."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_LABELS = {"attack", "tricky_benign", "benign"}
# Akshiya's files store only attack|benign + a `category`. data/load_dataset.py defines which
# benign categories count as "tricky"; we reuse that definition so there is ONE source of truth.
TRICKY_CATEGORIES = {"benign_imperative", "it_notice", "newsletter_about_injection", "quoted_attack_in_benign"}
try:  # pragma: no cover - import path depends on how the repo is launched
    from data.load_dataset import TRICKY as _TRICKY
    TRICKY_CATEGORIES = set(_TRICKY)
except Exception:
    pass


def load_dataset(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            for key in ("id", "text", "label"):
                if key not in row:
                    raise ValueError(f"{path}:{i} missing field '{key}'")
            if row["label"] not in VALID_LABELS:
                raise ValueError(f"{path}:{i} unknown label {row['label']!r}")
            # Map the 2-class gold label to the 3 evaluation classes (see data/load_dataset.py).
            row["gold_label"] = row["label"]
            if row["label"] == "benign" and row.get("category") in TRICKY_CATEGORIES:
                row["label"] = "tricky_benign"
            if not row.get("attack_type") and row["label"] == "attack":
                row["attack_type"] = row.get("category")
            rows.append(row)
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate ids")
    return rows


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else "unavailable"
    except Exception:
        return "unavailable"


def provenance(data_path: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Everything needed to reproduce a run. Saved next to every results file."""
    info = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_path": str(data_path),
        "dataset_sha256": file_sha256(data_path),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": _git("status", "--porcelain") not in ("", "unavailable"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    if extra:
        info.update(extra)
    return info


def is_test_split(data_path: str) -> bool:
    """Preregistration section 7: test.jsonl AND benchmark_slice.jsonl are evaluated exactly once."""
    name = Path(data_path).name
    return name.startswith("test") or name.startswith("benchmark")


def guard_test_split(data_path: str, results_dir: str, allow_test: bool) -> None:
    """Enforce 'run the test set ONCE'. Creates a lock file the first time the test split is run."""
    if not is_test_split(data_path):
        return
    lock = Path(results_dir) / ".test_split_used"
    if not allow_test:
        raise SystemExit("Refusing to touch the test split without --allow-test "
                         "(only do this after Akshiya has frozen the split).")
    if lock.exists():
        raise SystemExit(f"Test split already evaluated ({lock.read_text().strip()}). "
                         "It must be run exactly once; delete the lock only with team agreement.")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"first test run at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")