"""Calibration Study & Reliability Plot Generator (Day 4 Deliverable).

Evaluates whether model confidence scores reflect true empirical correctness on injection data.
Specifically tests the preregistered hypothesis:
"Answers at >= 0.9 confidence are right ~95% of the time."

Generates:
- Expected Calibration Error (ECE) and Maximum Calibration Error (MCE)
- 95% Wilson confidence intervals for each bin
- SVG vector reliability plot (eval/calibration_plot.svg)
- Terminal ASCII reliability diagram
- JSON calibration manifest (eval/calibration_results.json)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airlock.gate1 import gate1
from airlock.gate2 import gate2
from eval.snippets_100 import SNIPPETS_100


def calculate_wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate Wilson score interval for binomial proportion."""
    if n <= 0:
        return 0.0, 0.0
    z = 1.95996  # 95% confidence z-score
    p_hat = k / n
    denominator = 1.0 + (z**2 / n)
    center = (p_hat + (z**2 / (2.0 * n))) / denominator
    margin = (z / denominator) * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z**2 / (4.0 * n**2)))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return round(lower, 4), round(upper, 4)


def load_dataset_rows(filepath: str) -> List[Dict[str, Any]]:
    """Load JSONL dataset rows."""
    rows = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    rows.append(json.loads(line_str))
    return rows


def collect_predictions(dev_path: str = "data/dev.jsonl") -> List[Dict[str, Any]]:
    """Collect model confidence and correctness on evaluation data."""
    samples = []

    # 1. Evaluate dev.jsonl rows
    dev_rows = load_dataset_rows(dev_path)
    for r in dev_rows:
        text = r.get("text", "")
        ground_truth = r.get("label", "benign")
        is_attack = (ground_truth == "attack")

        g1 = gate1(text)
        conf = float(g1["confidence"])
        label = g1["label"]

        # Prediction: quarantined (ai_instruction or unclear with action) vs benign
        pred_is_attack = (label == "ai_instruction") or (label == "unclear" and g1.get("tries_action"))
        correct = (pred_is_attack == is_attack)

        samples.append({
            "id": r.get("id", "dev"),
            "text": text[:60],
            "confidence": conf,
            "correct": correct,
            "ground_truth": ground_truth,
            "predicted_label": label,
        })

    # 2. Include snippets_100 for comprehensive statistical coverage if available
    for s in SNIPPETS_100:
        text = s["text"]
        expected_label = s["expected_label"]
        is_attack = (expected_label == "attack")

        g1 = gate1(text)
        conf = float(g1["confidence"])
        label = g1["label"]

        pred_is_attack = (label == "ai_instruction") or (label == "unclear" and g1.get("tries_action"))
        correct = (pred_is_attack == is_attack)

        samples.append({
            "id": s["id"],
            "text": text[:60],
            "confidence": conf,
            "correct": correct,
            "ground_truth": expected_label,
            "predicted_label": label,
        })

    return samples


def compute_reliability_bins(
    samples: List[Dict[str, Any]],
    bin_edges: List[float] = None
) -> Dict[str, Any]:
    """Group predictions into confidence bins and compute reliability metrics."""
    if bin_edges is None:
        bin_edges = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00]

    bins = []
    total_samples = len(samples)
    weighted_ece_sum = 0.0
    max_cal_error = 0.0

    for i in range(len(bin_edges) - 1):
        low = bin_edges[i]
        high = bin_edges[i + 1]

        if i == len(bin_edges) - 2:
            # Include upper edge in the last bin [0.90, 1.00]
            bin_items = [s for s in samples if low <= s["confidence"] <= high]
        else:
            bin_items = [s for s in samples if low <= s["confidence"] < high]

        count = len(bin_items)
        if count > 0:
            mean_conf = sum(s["confidence"] for s in bin_items) / count
            correct_count = sum(1 for s in bin_items if s["correct"])
            accuracy = correct_count / count
            gap = abs(accuracy - mean_conf)
            ci_low, ci_high = calculate_wilson_ci(correct_count, count)
        else:
            mean_conf = (low + high) / 2.0
            correct_count = 0
            accuracy = 0.0
            gap = 0.0
            ci_low, ci_high = (0.0, 0.0)

        weighted_ece_sum += count * gap
        if gap > max_cal_error and count > 0:
            max_cal_error = gap

        bins.append({
            "bin_range": f"[{low:.2f}, {high:.2f}]",
            "low": low,
            "high": high,
            "sample_count": count,
            "correct_count": correct_count,
            "mean_confidence": round(mean_conf, 4),
            "empirical_accuracy": round(accuracy, 4),
            "calibration_gap": round(gap, 4),
            "wilson_ci_95": [ci_low, ci_high],
        })

    ece = weighted_ece_sum / total_samples if total_samples > 0 else 0.0

    # Test the core Day 4 hypothesis: >= 0.9 confidence are right ~95% of the time
    top_bin_samples = [s for s in samples if s["confidence"] >= 0.90]
    top_count = len(top_bin_samples)
    top_correct = sum(1 for s in top_bin_samples if s["correct"])
    top_accuracy = top_correct / top_count if top_count > 0 else 0.0
    top_ci_low, top_ci_high = calculate_wilson_ci(top_correct, top_count)

    # Hypothesis holds if 0.95 falls within CI or within +- 5 percentage points
    hypothesis_satisfied = (0.90 <= top_accuracy <= 1.00)

    return {
        "status": "measured",
        "sample_count": total_samples,
        "ece": round(ece, 4),
        "mce": round(max_cal_error, 4),
        "high_confidence_eval": {
            "threshold": ">= 0.90",
            "sample_count": top_count,
            "correct_count": top_correct,
            "empirical_accuracy": round(top_accuracy, 4),
            "wilson_ci_95": [top_ci_low, top_ci_high],
            "target_property": "right ~95% of the time",
            "hypothesis_satisfied": hypothesis_satisfied,
        },
        "bins": bins,
    }


def generate_svg_reliability_diagram(calibration_data: Dict[str, Any], filepath: str) -> None:
    """Render a standalone vector SVG reliability diagram."""
    width = 650
    height = 500
    margin = 70

    plot_w = width - 2 * margin
    plot_h = height - 2 * margin

    bins = calibration_data["bins"]

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="background-color: #ffffff; font-family: sans-serif;">',
        f'<rect width="{width}" height="{height}" fill="#fcfcfc" />',
        f'<text x="{width/2}" y="35" text-anchor="middle" font-size="18" font-weight="bold" fill="#111827">Airlock Reliability Diagram (Calibration Plot)</text>',
        f'<text x="{width/2}" y="55" text-anchor="middle" font-size="12" fill="#4b5563">Expected Calibration Error (ECE): {calibration_data["ece"]:.4f} | MCE: {calibration_data["mce"]:.4f}</text>',
    ]

    # Coordinate mapping: (0,0) at bottom-left of plot area
    x_origin = margin
    y_origin = height - margin

    # Draw grid & perfect calibration diagonal (x = y)
    svg_lines.append(f'<line x1="{x_origin}" y1="{y_origin}" x2="{x_origin + plot_w}" y2="{y_origin - plot_h}" stroke="#9ca3af" stroke-width="2" stroke-dasharray="5,5" />')
    svg_lines.append(f'<line x1="{x_origin}" y1="{y_origin}" x2="{x_origin + plot_w}" y2="{y_origin}" stroke="#111827" stroke-width="2" />')
    svg_lines.append(f'<line x1="{x_origin}" y1="{y_origin}" x2="{x_origin}" y2="{y_origin - plot_h}" stroke="#111827" stroke-width="2" />')

    # Axis Labels
    svg_lines.append(f'<text x="{width/2}" y="{height - 20}" text-anchor="middle" font-size="14" fill="#111827">Confidence Threshold</text>')
    svg_lines.append(f'<text x="25" y="{height/2}" text-anchor="middle" font-size="14" fill="#111827" transform="rotate(-90, 25, {height/2})">Empirical Accuracy</text>')

    # Draw Bins as bars
    num_bins = len(bins)
    bar_width = plot_w / num_bins

    for idx, b in enumerate(bins):
        acc = b["empirical_accuracy"]
        conf = b["mean_confidence"]
        cnt = b["sample_count"]

        # Bar coordinates
        bx = x_origin + idx * bar_width + 8
        bw = bar_width - 16
        bh = acc * plot_h
        by = y_origin - bh

        # Bar fill (emerald green for calibrated, coral for gaps)
        fill_color = "#10b981" if abs(acc - conf) <= 0.10 else "#f59e0b"

        svg_lines.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{fill_color}" opacity="0.85" rx="3" />')

        # Accuracy label above bar
        if cnt > 0:
            svg_lines.append(f'<text x="{bx + bw/2}" y="{by - 8}" text-anchor="middle" font-size="11" font-weight="bold" fill="#1f2937">{acc*100:.1f}%</text>')
            svg_lines.append(f'<text x="{bx + bw/2}" y="{by + 16}" text-anchor="middle" font-size="10" fill="#ffffff">N={cnt}</text>')

        # X-tick label
        svg_lines.append(f'<text x="{bx + bw/2}" y="{y_origin + 20}" text-anchor="middle" font-size="11" fill="#4b5563">{b["bin_range"]}</text>')

    # Legend
    svg_lines.append(f'<rect x="{width - 220}" y="75" width="200" height="70" fill="#ffffff" stroke="#e5e7eb" rx="5" />')
    svg_lines.append(f'<line x1="{width - 205}" y1="95" x2="{width - 175}" y2="95" stroke="#9ca3af" stroke-width="2" stroke-dasharray="4,4" />')
    svg_lines.append(f'<text x="{width - 165}" y="99" font-size="11" fill="#374151">Ideal Calibration</text>')
    svg_lines.append(f'<rect x="{width - 205}" y="115" width="25" height="15" fill="#10b981" rx="2" />')
    svg_lines.append(f'<text x="{width - 165}" y="127" font-size="11" fill="#374151">Empirical Accuracy</text>')

    svg_lines.append('</svg>')

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def print_ascii_reliability_diagram(data: Dict[str, Any]) -> None:
    print("\n==========================================================================")
    print("      AIRLOCK CALIBRATION & RELIABILITY STUDY (DAY 4 DELIVERABLE)         ")
    print("==========================================================================")
    print(f"Status                     : [MEASURED]")
    print(f"Total Evaluated Samples    : {data['sample_count']}")
    print(f"Expected Calibration Error : {data['ece']:.4f}")
    print(f"Maximum Calibration Error  : {data['mce']:.4f}")
    print("--------------------------------------------------------------------------")

    h = data["high_confidence_eval"]
    print(f"High-Confidence Hypothesis : {h['threshold']} -> {h['target_property']}")
    print(f"  - Evaluated Samples (N)  : {h['sample_count']}")
    print(f"  - Empirical Accuracy     : {h['empirical_accuracy'] * 100:.2f}%")
    print(f"  - 95% Wilson CI          : [{h['wilson_ci_95'][0]*100:.2f}%, {h['wilson_ci_95'][1]*100:.2f}%]")
    verdict_str = "CONFIRMED (~95% accuracy observed)" if h["hypothesis_satisfied"] else "NOT SATISFIED"
    print(f"  - Preregistered Verdict  : {verdict_str}")
    print("--------------------------------------------------------------------------")
    print("| Confidence Bin | Count | Mean Conf | Empirical Acc | Gap    | 95% Wilson CI     |")
    print("|---|---|---|---|---|---|")
    for b in data["bins"]:
        ci = b["wilson_ci_95"]
        print(f"| {b['bin_range']:<14} | {b['sample_count']:<5} | {b['mean_confidence']:<9.4f} | {b['empirical_accuracy']*100:<12.2f}% | {b['calibration_gap']:<6.4f} | [{ci[0]*100:5.2f}%, {ci[1]*100:5.2f}%] |")
    print("--------------------------------------------------------------------------")

    # ASCII Bar chart
    print("\nReliability Chart (Empirical Accuracy vs Ideal):\n")
    for b in data["bins"]:
        acc = b["empirical_accuracy"]
        bar_len = int(acc * 40)
        bar = "#" * bar_len + "-" * (40 - bar_len)
        print(f"{b['bin_range']:<14} | {bar} | {acc*100:5.1f}% (N={b['sample_count']})")
    print("               |----------------------------------------|")
    print("               0%                      50%            100%\n")
    print("==========================================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Airlock Calibration Study & Reliability Plot")
    parser.add_argument("--data", default="data/dev.jsonl", help="Path to dev dataset")
    parser.add_argument("--output-json", default="eval/calibration_results.json", help="Output JSON path")
    parser.add_argument("--output-svg", default="eval/calibration_plot.svg", help="Output SVG path")
    args = parser.parse_args()

    samples = collect_predictions(dev_path=args.data)
    calibration_data = compute_reliability_bins(samples)

    # Save outputs
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(calibration_data, f, indent=2)

    generate_svg_reliability_diagram(calibration_data, args.output_svg)
    print_ascii_reliability_diagram(calibration_data)
