from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _planner_report(*, top1: float, score: float, lcs: float, set_f1: float, samples: list[dict]) -> dict:
    return {
        "schema_version": "test.report",
        "aggregate_metrics": {
            "selected_top1_usable_rate": top1,
            "mean_selected_usability_score": score,
            "mean_selected_qgis_mapping_rate": 0.8,
        },
        "overall": {
            "canonicalized_metrics": {
                "lcs_ratio": lcs,
                "set_f1": set_f1,
                "token_accuracy": 0.3,
                "exact_match": 0.01,
            }
        },
        "per_sample": samples,
    }


class MRVAblationComparatorTests(unittest.TestCase):
    def test_compare_reports_extracts_key_metrics_and_deltas(self) -> None:
        from scripts.compare_mrv_training_ablation import compare_reports

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = _write_json(
                root / "baseline.json",
                _planner_report(
                    top1=0.6,
                    score=0.7,
                    lcs=0.4,
                    set_f1=0.5,
                    samples=[
                        {"sample_id": "a", "metrics": {"top1_usable_rate": 0.0, "canonicalized_lcs_ratio": 0.30}},
                        {"sample_id": "b", "metrics": {"top1_usable_rate": 1.0, "canonicalized_lcs_ratio": 0.50}},
                    ],
                ),
            )
            variant = _write_json(
                root / "mr_5.json",
                _planner_report(
                    top1=0.8,
                    score=0.75,
                    lcs=0.45,
                    set_f1=0.55,
                    samples=[
                        {"sample_id": "a", "metrics": {"top1_usable_rate": 1.0, "canonicalized_lcs_ratio": 0.40}},
                        {"sample_id": "b", "metrics": {"top1_usable_rate": 1.0, "canonicalized_lcs_ratio": 0.60}},
                    ],
                ),
            )
            manifest = _write_json(
                root / "manifest.json",
                {
                    "no_training_started": True,
                    "versions": [
                        {
                            "version_name": "mr_5",
                            "counts": {"injected_variants": 5, "output_train": 61500},
                        }
                    ],
                },
            )

            report = compare_reports(
                baseline_report_path=baseline,
                variant_report_paths={"mr_5": variant},
                manifest_path=manifest,
                bootstrap_iterations=40,
                seed=7,
            )

        self.assertTrue(report["governance"]["comparison_only"])
        self.assertTrue(report["governance"]["no_training"])
        self.assertTrue(report["manifest"]["no_training_started"])
        self.assertEqual(report["baseline"]["metrics"]["top1_usable_rate"], 0.6)
        comparison = report["comparisons"][0]
        self.assertEqual(comparison["version_name"], "mr_5")
        self.assertAlmostEqual(comparison["metric_deltas"]["top1_usable_rate"], 0.2)
        self.assertAlmostEqual(comparison["metric_deltas"]["mean_usability_score"], 0.05)
        self.assertAlmostEqual(comparison["metric_deltas"]["canonicalized_lcs_ratio"], 0.05)
        self.assertEqual(comparison["manifest_counts"]["injected_variants"], 5)
        self.assertIn("top1_usable_rate", comparison["bootstrap_delta_ci"])
        self.assertEqual(comparison["bootstrap_delta_ci"]["top1_usable_rate"]["n"], 2)

    def test_missing_baseline_metrics_are_reported_not_silently_zeroed(self) -> None:
        from scripts.compare_mrv_training_ablation import compare_reports

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = _write_json(root / "baseline.json", {"schema_version": "empty"})
            variant = _write_json(
                root / "mr_10.json",
                {"aggregate_metrics": {"top1_usable_rate": 0.9}},
            )

            report = compare_reports(
                baseline_report_path=baseline,
                variant_report_paths={"mr_10": variant},
                bootstrap_iterations=10,
                seed=1,
            )

        self.assertIn("top1_usable_rate", report["baseline"]["missing_metrics"])
        self.assertNotIn("top1_usable_rate", report["comparisons"][0]["metric_deltas"])
        self.assertIn("missing baseline metric", " ".join(report["comparisons"][0]["warnings"]))

    def test_cli_writes_json_and_markdown_comparison(self) -> None:
        from scripts.compare_mrv_training_ablation import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = _write_json(
                root / "baseline.json",
                {"aggregate_metrics": {"top1_usable_rate": 0.5, "top5_any_usable_rate": 0.8}},
            )
            variant = _write_json(
                root / "mr_5.json",
                {"aggregate_metrics": {"top1_usable_rate": 0.7, "top5_any_usable_rate": 0.9}},
            )
            out_dir = root / "comparison"

            report = main(
                [
                    "--baseline-report",
                    str(baseline),
                    "--variant-report",
                    f"mr_5={variant}",
                    "--output-dir",
                    str(out_dir),
                    "--bootstrap-iterations",
                    "10",
                ]
            )

            written = json.loads((out_dir / "mrv_training_ablation_comparison.json").read_text(encoding="utf-8"))
            summary_exists = (out_dir / "mrv_training_ablation_comparison_summary.md").exists()

        self.assertEqual(report["comparisons"][0]["version_name"], "mr_5")
        self.assertEqual(written["comparisons"][0]["metric_deltas"]["top1_usable_rate"], 0.2)
        self.assertTrue(summary_exists)


if __name__ == "__main__":
    unittest.main()
