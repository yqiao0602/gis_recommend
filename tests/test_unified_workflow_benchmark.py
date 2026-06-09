from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class UnifiedWorkflowBenchmarkTests(unittest.TestCase):
    def test_metric_row_separates_task_mode_and_metric_scope(self):
        from scripts.build_unified_workflow_benchmark import build_metric_row

        row = build_metric_row(
            system="v4_quality_gate",
            task="operator_token_prediction",
            prediction_mode="teacher_forced",
            metric_scope="token",
            vocabulary="v2_l3_98",
            metrics={"top1_accuracy": 0.483},
            source={"type": "external_reported_metric"},
        )

        self.assertEqual(row["task"], "operator_token_prediction")
        self.assertEqual(row["prediction_mode"], "teacher_forced")
        self.assertEqual(row["metric_scope"], "token")
        self.assertFalse(row["retrieval_based"])
        self.assertFalse(row["set_based"])
        self.assertEqual(row["metrics"]["top1_accuracy"], 0.483)

    def test_comparability_groups_prevent_tf_vs_rollout_metric_mixing(self):
        from scripts.build_unified_workflow_benchmark import build_comparison_groups, build_metric_row

        rows = [
            build_metric_row(
                system="v4_tf",
                task="operator_token_prediction",
                prediction_mode="teacher_forced",
                metric_scope="token",
                vocabulary="v2_l3_98",
                metrics={"top1_accuracy": 0.483},
                source={"type": "external_reported_metric"},
            ),
            build_metric_row(
                system="v4_ar",
                task="autoregressive_workflow_generation",
                prediction_mode="rollout",
                metric_scope="sequence",
                vocabulary="v2_l3_98",
                metrics={"token_accuracy": 0.211},
                source={"type": "external_reported_metric"},
            ),
        ]

        groups = build_comparison_groups(rows)

        self.assertEqual(len(groups), 2)
        self.assertTrue(all(group["direct_comparison_allowed"] for group in groups))
        self.assertNotEqual(groups[0]["group_id"], groups[1]["group_id"])

    def test_unified_artifact_contains_required_benchmark_families(self):
        from scripts.build_unified_workflow_benchmark import build_unified_benchmark

        artifact = build_unified_benchmark(
            v5_report_path=PROJECT_ROOT / "outputs_v2" / "v5_final_reports" / "stage1" / "evaluation_report.json",
            hybrid_report_path=PROJECT_ROOT
            / "outputs_v2"
            / "v5_final_reports"
            / "v5_hybrid_planner_multistage"
            / "hybrid_planner_report.json",
            output_path=None,
        )

        systems = {row["system"] for row in artifact["benchmark_rows"]}

        self.assertIn("v4_quality_gate_teacher_forced", systems)
        self.assertIn("v4_quality_gate_autoregressive", systems)
        self.assertIn("v5_final_pure_generation", systems)
        self.assertIn("retrieval_centered_planner_retrieval_only", systems)
        self.assertIn("retrieval_centered_planner_hybrid", systems)
        self.assertIn("set_predictor_quality_gate", systems)
        self.assertEqual(artifact["benchmark_protocol"]["cross_task_metric_mixing_allowed"], False)

    def test_unified_benchmark_script_runs_as_file_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "unified.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_unified_workflow_benchmark.py",
                    "--out",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=60,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "gis_recommend.workflow_benchmark.unified.v1")


if __name__ == "__main__":
    unittest.main()
