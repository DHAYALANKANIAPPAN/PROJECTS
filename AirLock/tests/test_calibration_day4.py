"""Unit tests for Day 4 Calibration Study and Reliability Plotting."""
import os
import unittest

from eval.calibration_plot import (
    calculate_wilson_ci,
    compute_reliability_bins,
    generate_svg_reliability_diagram,
)


class TestCalibrationDay4(unittest.TestCase):

    def test_wilson_ci_extremes(self):
        """Wilson CI handles 0 and 100% successes gracefully within [0.0, 1.0]."""
        low_0, high_0 = calculate_wilson_ci(0, 10)
        self.assertEqual(low_0, 0.0)
        self.assertGreater(high_0, 0.0)

        low_10, high_10 = calculate_wilson_ci(10, 10)
        self.assertLess(low_10, 1.0)
        self.assertEqual(high_10, 1.0)

    def test_perfect_calibration_synthetic(self):
        """When accuracy matches confidence exactly, calibration gap and ECE are near zero."""
        synthetic_samples = []
        # Create bins at 0.6 (60% correct) and 0.9 (90% correct)
        for i in range(10):
            synthetic_samples.append({"confidence": 0.60, "correct": i < 6})
        for i in range(10):
            synthetic_samples.append({"confidence": 0.90, "correct": i < 9})

        res = compute_reliability_bins(synthetic_samples, bin_edges=[0.50, 0.70, 1.00])
        self.assertLess(res["ece"], 0.02)

    def test_high_confidence_hypothesis_reporting(self):
        """Hypothesis verification detects when high-confidence predictions meet ~95% target."""
        # 20 samples in >=0.90 bin, 19 correct (95% accuracy)
        synthetic_samples = [{"confidence": 0.95, "correct": (i < 19)} for i in range(20)]
        res = compute_reliability_bins(synthetic_samples, bin_edges=[0.50, 0.90, 1.00])

        h = res["high_confidence_eval"]
        self.assertEqual(h["sample_count"], 20)
        self.assertEqual(h["correct_count"], 19)
        self.assertAlmostEqual(h["empirical_accuracy"], 0.95, places=2)
        self.assertTrue(h["hypothesis_satisfied"])

    def test_svg_generation(self):
        """SVG generator produces valid XML file with chart elements."""
        mock_data = {
            "status": "measured",
            "sample_count": 20,
            "ece": 0.045,
            "mce": 0.08,
            "bins": [
                {
                    "bin_range": "[0.50, 0.70]",
                    "low": 0.5,
                    "high": 0.7,
                    "sample_count": 10,
                    "correct_count": 7,
                    "mean_confidence": 0.65,
                    "empirical_accuracy": 0.70,
                    "calibration_gap": 0.05,
                    "wilson_ci_95": [0.39, 0.89],
                },
                {
                    "bin_range": "[0.70, 1.00]",
                    "low": 0.7,
                    "high": 1.0,
                    "sample_count": 10,
                    "correct_count": 9,
                    "mean_confidence": 0.92,
                    "empirical_accuracy": 0.90,
                    "calibration_gap": 0.02,
                    "wilson_ci_95": [0.59, 0.98],
                },
            ]
        }
        test_svg = "eval/test_plot.svg"
        try:
            generate_svg_reliability_diagram(mock_data, test_svg)
            self.assertTrue(os.path.exists(test_svg))
            with open(test_svg, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<svg", content)
            self.assertIn("</svg>", content)
            self.assertIn("Expected Calibration Error", content)
        finally:
            if os.path.exists(test_svg):
                os.remove(test_svg)


if __name__ == "__main__":
    unittest.main()
