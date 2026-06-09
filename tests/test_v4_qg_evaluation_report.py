from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.evaluate_v4_quality_gate import (  # noqa: E402
    build_complexity_bucket_report,
    build_five_tier_report,
    write_five_tier_markdown,
)
from scripts.evaluate_checkpoint_epochs import _extract_metrics_from_report  # noqa: E402
from scripts.evaluate_checkpoint_epochs import find_epoch_checkpoints  # noqa: E402


class V4QGEvaluationReportTests(unittest.TestCase):
    def test_five_tier_report_demotes_sequence_metrics_to_diagnostics(self) -> None:
        aggregate_l3_metrics = {
            "sequence_em": {"mean": 0.01, "min": 0.0, "max": 1.0},
            "token_accuracy": {"mean": 0.42, "min": 0.0, "max": 1.0},
            "lcs_ratio": {"mean": 0.55, "min": 0.0, "max": 1.0},
            "set_f1": {"mean": 0.62, "min": 0.0, "max": 1.0},
        }
        qgis_report = [
            {
                "coverage": 0.8,
                "validity": 1.0,
                "io_compatibility": 0.75,
                "unknown_ratio": 0.1,
                "total_steps": 5,
            },
            {
                "coverage": 0.6,
                "validity": 0.0,
                "io_compatibility": 0.25,
                "unknown_ratio": 0.4,
                "total_steps": 4,
            },
        ]
        executable_report = {
            "summary": {
                "executable_ratio": 0.5,
                "mean_io_compatibility": 0.5,
            }
        }

        report = build_five_tier_report(
            n_samples=2,
            aggregate_l3_metrics=aggregate_l3_metrics,
            qgis_report=qgis_report,
            executable_report=executable_report,
            oracle_report={"by_k": {"top3": {"best_lcs_ratio": 0.7}}},
        )

        self.assertEqual(report["primary_kpi"], "tier2_3_workflow_usability")
        self.assertIn("tier1_sequence_diagnostics", report["tiers"])
        self.assertEqual(report["tiers"]["tier1_sequence_diagnostics"]["sequence_em"]["mean"], 0.01)
        self.assertIn("qgis_chain_validity_rate", report["tiers"]["tier2_3_workflow_usability"])
        self.assertEqual(report["tiers"]["tier2_3_workflow_usability"]["qgis_chain_validity_rate"], 0.5)
        self.assertEqual(
            report["metric_interpretation"]["sequence_em"],
            "historical_workflow_reproduction_rate_not_correctness",
        )
        self.assertEqual(report["system_lineage"], "research")
        self.assertFalse(report["mainline_eligible"])
        self.assertEqual(report["data_profile"], "v4_quality_gate")
        self.assertEqual(report["model_profile"], "v4_6_quality_gate_candidate")
        self.assertEqual(report["governance"]["lineage"], "research")
        self.assertIn("Step8 + V4.6", report["governance"]["non_mainline_reason"])

    def test_five_tier_markdown_writes_usability_first_summary(self) -> None:
        tiered = build_five_tier_report(
            n_samples=1,
            aggregate_l3_metrics={"sequence_em": {"mean": 0.0}, "lcs_ratio": {"mean": 0.5}},
            qgis_report=[{"coverage": 1.0, "validity": 1.0, "io_compatibility": 1.0}],
            executable_report=None,
            oracle_report=None,
        )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "summary.md"
            write_five_tier_markdown(out, tiered)
            text = out.read_text(encoding="utf-8")

        self.assertIn("Primary KPIs - Workflow Usability", text)
        self.assertIn("Tier 1 Sequence Diagnostics", text)
        self.assertIn("historical workflow reproduction", text)

    def test_complexity_bucket_report_stratifies_length_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = Path(tmp) / "task_type_length_stats.json"
            stats_path.write_text(
                json.dumps({
                    "by_task_type": {
                        "simple": {"median": 3},
                        "extended": {"median": 10},
                    }
                }),
                encoding="utf-8",
            )

            test_set = [
                {
                    "task_metadata": {"task_type_normalized": "simple"},
                    "l3_sequence": [-1, 1, 2, 3, -2],
                },
                {
                    "task_metadata": {"task_type_normalized": "extended"},
                    "l3_sequence": [-1, 4, 5, 6, 7, 8, 9, 10, 11, -2],
                },
                {
                    "task_metadata": {"task_type_normalized": "extended"},
                    "l3_sequence": [-1, 12, 13, 14, 15, -2],
                },
            ]
            l3_results = [
                {"all_candidates": [{"tokens": [-1, 1, 2, 3, -2]}]},
                {"all_candidates": [{"tokens": [-1, 4, 5, 6, -2]}]},
                {"all_candidates": [{"tokens": [-1, 12, 13, 14, 15, 16, 17, -2]}]},
            ]
            metrics = [
                {"set_f1": 1.0, "lcs_ratio": 1.0, "token_accuracy": 1.0},
                {"set_f1": 0.5, "lcs_ratio": 0.4, "token_accuracy": 0.3},
                {"set_f1": 0.75, "lcs_ratio": 0.8, "token_accuracy": 0.6},
            ]

            report = build_complexity_bucket_report(
                test_set,
                l3_results,
                metrics,
                length_stats_path=stats_path,
            )

        self.assertEqual(
            set(report["by_bucket"].keys()),
            {"short", "medium", "long", "very_long"},
        )
        self.assertEqual(report["by_bucket"]["short"]["n"], 1)
        self.assertEqual(report["by_bucket"]["long"]["n"], 2)
        self.assertEqual(report["by_bucket"]["long"]["early_eos_rate"], 0.5)
        self.assertEqual(report["by_bucket"]["long"]["overlength_rate"], 0.5)
        self.assertEqual(report["by_bucket"]["long"]["mean_length_ratio"], 0.9375)
        self.assertEqual(report["by_bucket"]["long"]["set_f1"], 0.625)
        self.assertEqual(report["by_bucket"]["medium"]["n"], 0)
        self.assertEqual(len(report["bucket_definitions"]), 4)

    def test_five_tier_markdown_includes_complexity_bucket_table(self) -> None:
        tiered = build_five_tier_report(
            n_samples=1,
            aggregate_l3_metrics={"sequence_em": {"mean": 0.0}, "lcs_ratio": {"mean": 0.5}},
            qgis_report=[],
            executable_report=None,
            oracle_report=None,
        )
        complexity = {
            "by_bucket": {
                "short": {"n": 0},
                "medium": {"n": 0},
                "long": {"n": 2, "mean_length_ratio": 0.75, "early_eos_rate": 0.5},
                "very_long": {"n": 1, "mean_length_ratio": 0.6, "early_eos_rate": 1.0},
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "summary.md"
            write_five_tier_markdown(out, tiered, complexity)
            text = out.read_text(encoding="utf-8")

        self.assertIn("Complexity Bucket Rollout Diagnostics", text)
        self.assertIn("| long | 2 |", text)
        self.assertIn("| very_long | 1 |", text)

    def test_checkpoint_metrics_extract_complexity_bucket_summary(self) -> None:
        payload = {
            "five_tier_metrics": {
                "tiers": {
                    "tier1_sequence_diagnostics": {
                        "set_f1": {"mean": 0.6},
                        "lcs_ratio": {"mean": 0.7},
                    },
                    "tier2_3_workflow_usability": {
                        "qgis_mapping_rate": 0.8,
                        "qgis_chain_validity_rate": 0.5,
                    },
                }
            },
            "complexity_bucket_report": {
                "by_bucket": {
                    "long": {
                        "n": 4,
                        "mean_length_ratio": 0.72,
                        "early_eos_rate": 0.25,
                        "overlength_rate": 0.0,
                        "set_f1": 0.55,
                        "lcs_ratio": 0.62,
                    },
                    "very_long": {
                        "n": 2,
                        "mean_length_ratio": 0.6,
                        "early_eos_rate": 0.5,
                    },
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            metrics = _extract_metrics_from_report(report_path)

        self.assertEqual(metrics["long_n"], 4)
        self.assertEqual(metrics["long_length_ratio"], 0.72)
        self.assertEqual(metrics["long_early_eos_rate"], 0.25)
        self.assertEqual(metrics["very_long_n"], 2)
        self.assertEqual(metrics["very_long_early_eos_rate"], 0.5)
        self.assertIn("long", metrics["complexity_by_bucket"])

    def test_find_epoch_checkpoints_includes_metric_selection_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                "checkpoint_epoch_002.pth",
                "best_model.pth",
                "latest_model.pth",
                "best_gen_set_f1_model.pth",
                "best_gen_lcs_model.pth",
                "best_gen_composite_model.pth",
            ):
                (root / name).write_bytes(b"stub")

            found = find_epoch_checkpoints(root)

        labels = [label for _, _, label in found]
        self.assertEqual(
            labels,
            [
                "epoch_002",
                "best_model",
                "best_gen_set_f1",
                "best_gen_lcs",
                "best_gen_composite",
            ],
        )


if __name__ == "__main__":
    unittest.main()
