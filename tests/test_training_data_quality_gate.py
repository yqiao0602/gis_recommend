from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.data.quality_gate import (  # noqa: E402
    QualityGatePolicy,
    audit_gee_operator_aliases,
    build_quality_gate_candidate,
    write_quality_gate_outputs,
)


def _workflow(
    task_type: str,
    ops: list[str],
    seq: list[int],
    confidences: list[float] | None = None,
    name: str = "Task",
) -> dict:
    return {
        "operator_sequence": ops,
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "confidences": confidences if confidences is not None else [0.95 for _ in ops],
        "ambiguity_flags": [False for _ in ops],
        "metadata": {"script_id": f"{name}_{task_type}"},
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
    }


def _id_mappings() -> dict:
    return {
        "l3": {
            "L3_01": 1,
            "L3_02": 2,
            "L3_03": 3,
            "L3_04": 4,
            "L3_05": 5,
            "L3_06": 6,
        },
        "mapping_metadata": {
            "gee_to_l3": {
                "op.auto": {"source": "auto_remap", "primary_l3": "L3_01"},
                "op.manual": {"source": "manual_override", "primary_l3": "L3_02"},
                "op.clean": {"source": "manual_override", "primary_l3": "L3_03"},
                "op.a": {"source": "manual_override", "primary_l3": "L3_01"},
                "op.b": {"source": "manual_override", "primary_l3": "L3_02"},
                "op.c": {"source": "manual_override", "primary_l3": "L3_03"},
                "op.d": {"source": "manual_override", "primary_l3": "L3_04"},
                "op.e": {"source": "manual_override", "primary_l3": "L3_05"},
                "op.f": {"source": "manual_override", "primary_l3": "L3_06"},
            }
        },
    }


class TrainingDataQualityGateTests(unittest.TestCase):
    def test_auto_remap_low_confidence_is_quarantined_and_sparse_tasks_are_merged(self):
        workflows = [
            _workflow("Main", ["op.auto"], [1], [0.72], "auto-low"),
            _workflow("Main", ["op.manual"], [2], [0.72], "manual-low"),
            _workflow("Sparse", ["op.clean"], [3], [0.95], "sparse"),
        ]
        policy = QualityGatePolicy(min_task_count=2, train_ratio=0.7, val_ratio=0.15)

        result = build_quality_gate_candidate(workflows, _id_mappings(), policy)

        self.assertEqual(result.report["counts"]["input_workflows"], 3)
        self.assertEqual(result.report["counts"]["candidate_workflows"], 2)
        self.assertEqual(result.report["counts"]["quarantined_workflows"], 1)
        self.assertEqual(result.quarantined_workflows[0]["metadata"]["script_id"], "auto-low_Main")
        self.assertEqual(
            result.quarantined_workflows[0]["quality_gate"]["quarantine_reasons"][0]["operator"],
            "op.auto",
        )

        candidate_tasks = [
            wf["task_metadata"]["task_type"] for wf in result.candidate_workflows
        ]
        self.assertEqual(candidate_tasks, ["Other / Sparse", "Other / Sparse"])
        self.assertEqual(
            result.candidate_workflows[0]["task_metadata"]["quality_gate_original_task_type"],
            "Main",
        )
        self.assertEqual(
            result.candidate_workflows[1]["task_metadata"]["quality_gate_original_task_type"],
            "Sparse",
        )
        self.assertEqual(workflows[2]["task_metadata"]["task_type"], "Sparse")
        self.assertIn("Other / Sparse", result.task_vocab["task_type_to_id"])
        self.assertEqual(result.report["counts"]["sparse_merged_workflows"], 2)

    def test_grouped_split_keeps_duplicate_l3_sequences_together_and_trains_all_tasks(self):
        workflows = [
            _workflow("A", ["op.a"], [1, 2], name="a-dup"),
            _workflow("B", ["op.b"], [1, 2], name="b-dup"),
            _workflow("A", ["op.c"], [3], name="a-2"),
            _workflow("B", ["op.d"], [4], name="b-2"),
            _workflow("A", ["op.e"], [5], name="a-3"),
            _workflow("B", ["op.f"], [6], name="b-3"),
        ]
        policy = QualityGatePolicy(min_task_count=1, train_ratio=0.5, val_ratio=0.25)

        result = build_quality_gate_candidate(workflows, _id_mappings(), policy)

        split_of = {}
        for split_name, key in (("train", "train_indices"), ("val", "val_indices"), ("test", "test_indices")):
            for index in result.splits[key]:
                split_of[index] = split_name

        self.assertEqual(split_of[0], split_of[1])
        self.assertEqual(result.report["splits"]["cross_split_sequence_hashes"], 0)
        self.assertEqual(result.report["splits"]["val_tasks_not_in_train"], [])
        self.assertEqual(result.report["splits"]["test_tasks_not_in_train"], [])

    def test_write_quality_gate_outputs_uses_separate_candidate_filenames(self):
        workflows = [
            _workflow("A", ["op.a"], [1], name="a"),
            _workflow("A", ["op.b"], [2], name="b"),
        ]
        result = build_quality_gate_candidate(
            workflows,
            _id_mappings(),
            QualityGatePolicy(min_task_count=1, train_ratio=0.5, val_ratio=0.25),
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_quality_gate_outputs(result, Path(tmp))

            self.assertEqual(paths["data"].name, "labeled_workflows_l3_v4_quality_gate.json")
            self.assertEqual(paths["splits"].name, "dataset_splits_v4_quality_gate.json")
            self.assertEqual(paths["task_vocab"].name, "task_type_vocabulary_v4_quality_gate.json")
            data = json.loads(paths["data"].read_text(encoding="utf-8"))
            splits = json.loads(paths["splits"].read_text(encoding="utf-8"))
            vocab = json.loads(paths["task_vocab"].read_text(encoding="utf-8"))

        self.assertEqual(data["num_workflows"], 2)
        self.assertEqual(
            sorted(splits["train_indices"] + splits["val_indices"] + splits["test_indices"]),
            [0, 1],
        )
        self.assertEqual(vocab["num_types"], 2)

    def test_cli_writes_candidate_outputs_to_requested_directory(self):
        import importlib

        cli = importlib.import_module("scripts.build_v4_quality_gate_candidate")
        workflows = [
            _workflow("A", ["op.a"], [1], name="a"),
            _workflow("A", ["op.b"], [2], name="b"),
        ]
        payload = {"num_workflows": len(workflows), "labeled_workflows": workflows}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_path = tmp_path / "step8.json"
            mappings_path = tmp_path / "id_mappings.json"
            out_dir = tmp_path / "candidate"
            data_path.write_text(json.dumps(payload), encoding="utf-8")
            mappings_path.write_text(json.dumps(_id_mappings()), encoding="utf-8")

            cli.main([
                "--data",
                str(data_path),
                "--id-mappings",
                str(mappings_path),
                "--out-dir",
                str(out_dir),
                "--min-task-count",
                "1",
            ])

            self.assertTrue((out_dir / "labeled_workflows_l3_v4_quality_gate.json").exists())
            self.assertTrue((out_dir / "dataset_splits_v4_quality_gate.json").exists())
            self.assertTrue((out_dir / "quality_gate_report.json").exists())
            self.assertTrue(data_path.exists())

    def test_gee_operator_alias_audit_reports_official_name_gaps(self):
        workflows = [
            _workflow("A", ["ee.image.select"], [1], name="select"),
            _workflow("A", ["ee.algorithms.snic"], [2], name="snic"),
        ]
        id_mappings = {
            "mapping_metadata": {
                "gee_to_l3": {
                    "ee.Image.select": {
                        "source": "manual_override",
                        "mapping_confidence": 0.95,
                        "primary_l3": "L3_01",
                    },
                    "ee.Algorithms.SNIC": {
                        "source": "auto_remap",
                        "mapping_confidence": 0.95,
                        "primary_l3": "L3_02",
                    },
                }
            }
        }
        official = {
            "Image": [
                {
                    "name": "ee.Image.select",
                    "code_examples": ["ee.Image.select(var_args)"],
                }
            ],
            "Algorithms": [
                {
                    "name": "ee.Algorithms.Image.Segmentation.snic",
                    "code_examples": ["ee.Algorithms.Image.Segmentation.SNIC(image)"],
                }
            ],
        }

        report = audit_gee_operator_aliases(workflows, id_mappings, official)

        self.assertEqual(report["counts"]["unique_operators"], 2)
        self.assertEqual(report["counts"]["official_name_lower_matches"], 1)
        self.assertEqual(report["counts"]["unresolved_official_name"], 1)
        self.assertEqual(
            report["case_display_mismatches"][0]["official_name"],
            "ee.Image.select",
        )
        self.assertEqual(
            report["unresolved_operators"][0]["operator"],
            "ee.algorithms.snic",
        )
        self.assertEqual(
            report["unresolved_operators"][0]["mapping_key"],
            "ee.Algorithms.SNIC",
        )


if __name__ == "__main__":
    unittest.main()
