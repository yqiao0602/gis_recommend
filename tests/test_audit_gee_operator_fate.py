from __future__ import annotations

import csv
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _write_stage(root: Path, step: int, workflows: dict[str, list[str]]) -> None:
    step_dir = root / f"step{step}"
    step_dir.mkdir(parents=True, exist_ok=True)
    if step == 1:
        name, key = "raw_workflows.json", "workflows"
        rows = [
            {"script_id": script_id, "operations": operations}
            for script_id, operations in workflows.items()
        ]
    elif step in (2, 3):
        name = "cleaned_workflows.json" if step == 2 else "final_workflows.json"
        key = "workflows"
        rows = [
            {"script_id": script_id, "operations": operations}
            for script_id, operations in workflows.items()
        ]
    elif step == 4:
        name, key = "standardized_workflows.json", "workflows"
        rows = [
            {"script_id": script_id, "operator_sequence": operations}
            for script_id, operations in workflows.items()
        ]
    elif step == 5:
        name, key = "workflow_sequences.json", "workflow_dags"
        rows = [
            {
                "script_id": script_id,
                "nodes": [{"operator": operator} for operator in operations],
            }
            for script_id, operations in workflows.items()
        ]
    else:
        names = {
            6: "labeled_workflows_l3.json",
            7: "labeled_workflows_l3_v4.json",
            8: "labeled_workflows_l3_v4_cleaned.json",
        }
        name, key = names[step], "labeled_workflows"
        rows = [
            {
                "metadata": {"script_id": script_id},
                "operator_sequence": operations,
            }
            for script_id, operations in workflows.items()
        ]
    (step_dir / name).write_text(json.dumps({key: rows}), encoding="utf-8")


def _fixture(root: Path) -> None:
    step1 = {
        "a": [
            "ee.Image", "Map.addLayer", "Export.image.toDrive",
            "ee.Number.add", "ee.Image.select", "ee.Image.select",
        ],
        "b": ["ee.Image.clip"],
        "gone": ["custom.operation"],
    }
    step2 = {
        "a": ["Map.addLayer", "Export.image.toDrive", "ee.Image.select"],
        "b": ["ee.Image.clip"],
        "gone": ["custom.operation"],
    }
    step3 = step2
    step4 = {
        "a": [
            "map.addlayer", "export.image.todrive", "ee.image.select",
            "ee.image.chart",
        ],
        "b": ["ee.image.clip"],
        "gone": ["custom.operation"],
    }
    step5 = step4
    step6 = {
        "a": ["ee.image.select"],
        "b": ["ee.image.clip"],
        "gone": ["custom.operation"],
    }
    step7 = step6
    step8 = {"a": ["ee.image.select"]}
    for step, workflows in enumerate(
        (step1, step2, step3, step4, step5, step6, step7, step8), start=1
    ):
        _write_stage(root, step, workflows)


class GeeOperatorFateAuditTests(unittest.TestCase):
    def test_fate_is_independent_of_workflow_insertion_order(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")

        def build(root: Path, reverse: bool) -> list[dict]:
            first = [
                ("z_filtered", ["ee.Image.clip"]),
                ("a_compressed", ["ee.Image.clip", "ee.Image.clip"]),
            ]
            if reverse:
                first.reverse()
            _write_stage(root, 1, dict(first))
            remaining = {"a_compressed": ["ee.Image.clip"]}
            for step in range(2, 9):
                _write_stage(root, step, remaining)
            return audit.build_operator_fate_audit(root)[1]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normal = build(root / "normal", False)
            reversed_rows = build(root / "reversed", True)

        self.assertEqual(normal, reversed_rows)
        by_operator = {row["operator"]: row for row in normal}
        self.assertEqual(by_operator["ee.Image.clip"]["classification"], "compressed_repetition")
        self.assertEqual(by_operator["ee.Image.clip"]["example_script_ids"], [
            "a_compressed", "z_filtered",
        ])

    def test_cli_output_is_equivalent_across_pythonhashseed_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = root / "pipeline"
            _fixture(pipeline)
            outputs = []
            for seed in ("1", "9173"):
                output = root / f"out-{seed}"
                env = {**os.environ, "PYTHONHASHSEED": seed}
                subprocess.run(
                    [
                        sys.executable, "scripts/audit_gee_operator_fate.py",
                        "--pipeline-root", str(pipeline),
                        "--output-dir", str(output),
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                outputs.append((
                    (output / "step_metrics.json").read_bytes(),
                    (output / "operator_fate.csv").read_bytes(),
                ))

        self.assertEqual(outputs[0], outputs[1])

    def test_cli_uses_atomic_writers_instead_of_path_write_text(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = root / "pipeline"
            output = root / "audit"
            _fixture(pipeline)
            with mock.patch.object(
                Path, "write_text", side_effect=AssertionError("direct write forbidden")
            ):
                paths = audit.main([
                    "--pipeline-root", str(pipeline),
                    "--output-dir", str(output),
                ])

        self.assertEqual(set(paths), {"metrics", "operator_fate"})

    def test_atomic_replace_failure_preserves_existing_outputs_and_cleans_temp(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = root / "pipeline"
            output = root / "audit"
            _fixture(pipeline)
            output.mkdir()
            metrics = output / "step_metrics.json"
            fate = output / "operator_fate.csv"
            metrics.write_text("old metrics", encoding="utf-8")
            fate.write_text("old fate", encoding="utf-8")

            with mock.patch("os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    audit.main([
                        "--pipeline-root", str(pipeline),
                        "--output-dir", str(output),
                    ])

            remaining = sorted(path.name for path in output.iterdir())
            metrics_content = metrics.read_text(encoding="utf-8")
            fate_content = fate.read_text(encoding="utf-8")

        self.assertEqual(metrics_content, "old metrics")
        self.assertEqual(fate_content, "old fate")
        self.assertEqual(remaining, ["operator_fate.csv", "step_metrics.json"])

    def test_step4_ordinary_addition_retained_to_step8_is_retained_core(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for step in range(1, 9):
                operations = ["ee.Image.select"]
                if step >= 4:
                    operations.append("ee.image.newretained")
                _write_stage(root, step, {"a": operations})

            _, rows = audit.build_operator_fate_audit(root)

        by_operator = {row["operator"]: row for row in rows}
        self.assertEqual(
            by_operator["ee.image.newretained"]["classification"],
            "retained_core_mapped",
        )

    def test_step4_ordinary_addition_dropped_at_step6_is_unmapped_gis(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for step in range(1, 9):
                operations = ["ee.Image.select"]
                if step in (4, 5):
                    operations.append("ee.image.newunmapped")
                _write_stage(root, step, {"a": operations})

            _, rows = audit.build_operator_fate_audit(root)

        by_operator = {row["operator"]: row for row in rows}
        self.assertEqual(
            by_operator["ee.image.newunmapped"]["classification"],
            "dropped_unmapped_gis",
        )

    def test_build_audit_reports_invariants_and_deterministic_fates(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            metrics, rows = audit.build_operator_fate_audit(root)

        self.assertEqual(len(metrics["stages"]), 8)
        self.assertEqual(metrics["stages"][0]["workflow_count"], 3)
        self.assertEqual(metrics["stages"][0]["operator_count"], 8)
        invariants = {item["transition"]: item for item in metrics["invariants"]}
        self.assertTrue(invariants["step2_to_step3"]["passed"])
        self.assertTrue(invariants["step4_to_step5"]["passed"])
        self.assertEqual(metrics["classification_authority"], "deterministic_lexical_proxy")

        by_operator = {row["operator"]: row for row in rows}
        self.assertEqual(by_operator["ee.Image"]["classification"], "excluded_input_constructor")
        self.assertEqual(by_operator["ee.Number.add"]["classification"], "excluded_auxiliary_value")
        self.assertEqual(by_operator["map.addlayer"]["classification"], "excluded_ui_visualization")
        self.assertEqual(by_operator["export.image.todrive"]["classification"], "excluded_output_side_effect")
        self.assertEqual(by_operator["ee.image.chart"]["classification"], "normalization_corruption")
        self.assertEqual(by_operator["ee.image.select"]["classification"], "retained_core_mapped")
        self.assertEqual(by_operator["custom.operation"]["classification"], "workflow_filtered_after_pruning")
        self.assertTrue(all(
            row["classification_authority"] == "deterministic_lexical_proxy"
            for row in rows
        ))

    def test_removed_counts_first_disappearance_and_examples_are_aggregated(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            _, rows = audit.build_operator_fate_audit(root)

        by_operator = {row["operator"]: row for row in rows}
        select = by_operator["ee.Image.select"]
        self.assertEqual(select["removed_occurrences"], 1)
        self.assertEqual(select["affected_workflows"], 1)
        self.assertEqual(select["first_disappearance"], "step1_to_step2")
        self.assertEqual(select["example_script_ids"], ["a"])
        self.assertEqual(select["classification"], "compressed_repetition")

    def test_cli_writes_metrics_json_and_operator_fate_csv(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = root / "pipeline"
            output = root / "audit"
            _fixture(pipeline)
            paths = audit.main([
                "--pipeline-root", str(pipeline),
                "--output-dir", str(output),
            ])
            metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))
            with paths["operator_fate"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(paths["metrics"].name, "step_metrics.json")
        self.assertEqual(paths["operator_fate"].name, "operator_fate.csv")
        self.assertEqual(metrics["schema"], "gis_recommend.gee_operator_fate_audit.v1")
        self.assertGreater(len(rows), 0)
        self.assertIn("first_disappearance", rows[0])
        self.assertIn("added_occurrences", rows[0])

    def test_classifier_exposes_all_required_fate_categories(self):
        audit = importlib.import_module("scripts.audit_gee_operator_fate")
        observed = {
            audit.classify_operator_fate("Map.addLayer", "step5_to_step6", 1, 0, False),
            audit.classify_operator_fate("Export.image.toDrive", "step5_to_step6", 1, 0, False),
            audit.classify_operator_fate("ee.Image", "step1_to_step2", 1, 0, False),
            audit.classify_operator_fate("ee.ImageCollection.map", "step5_to_step6", 1, 0, False),
            audit.classify_operator_fate("ee.Number.add", "step1_to_step2", 1, 0, False),
            audit.classify_operator_fate("ee.Image.select", "step1_to_step2", 2, 1, False),
            audit.classify_operator_fate("ee.Unknown", "step5_to_step6", 1, 0, False),
            audit.classify_operator_fate("ee.image.chart", "step3_to_step4", 0, 1, False),
            audit.classify_operator_fate("custom.op", "step7_to_step8", 1, 0, True),
            audit.classify_operator_fate("ee.Image.clip", "retained", 0, 0, False),
            audit.classify_operator_fate("custom.op", "step3_to_step4", 1, 0, False),
        }
        required = {
            "excluded_ui_visualization", "excluded_output_side_effect",
            "excluded_input_constructor", "excluded_control_container",
            "excluded_auxiliary_value", "compressed_repetition",
            "dropped_unmapped_gis", "normalization_corruption",
            "workflow_filtered_after_pruning", "retained_core_mapped", "unresolved",
        }
        self.assertEqual(observed, required)


if __name__ == "__main__":
    unittest.main()
