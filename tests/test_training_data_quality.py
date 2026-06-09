from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.data.training_data_quality import audit_training_data_quality


def _workflow(task_type: str, ops: list[str], seq: list[int], name: str = "Task") -> dict:
    return {
        "operator_sequence": ops,
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "confidences": [0.72 for _ in ops],
        "ambiguity_flags": [False for _ in ops],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
    }


class TrainingDataQualityTests(unittest.TestCase):
    def test_mapping_metadata_lookup_is_case_insensitive(self):
        workflows = [
            _workflow("A", ["ee.featurecollection.filter"], [1], name="A1"),
        ]
        splits = {"train_indices": [0], "val_indices": [], "test_indices": []}
        id_mappings = {
            "l3": {"L3_01": 1},
            "mapping_metadata": {
                "gee_to_l3": {
                    "ee.FeatureCollection.filter": {
                        "primary_l3": "L3_01",
                        "source": "auto_remap",
                        "mapping_type": "direct",
                        "all_candidates": [{"role": "direct_mapping"}],
                    }
                }
            },
        }

        report = audit_training_data_quality(
            workflows,
            splits,
            id_mappings=id_mappings,
            operator_hotlist_min_count=1,
        )

        self.assertEqual(report["mapping_source"]["missing_meta_tokens"], 0)
        self.assertEqual(report["mapping_source"]["source_counts"]["auto_remap"], 1)
        self.assertEqual(report["confidence"]["low_confidence_tokens"], 1)
        self.assertEqual(report["confidence"]["low_confidence_operators"][0]["operator"],
                         "ee.featurecollection.filter")

    def test_split_task_gaps_and_cross_split_duplicate_sequences_are_reported(self):
        workflows = [
            _workflow("A", ["op.a"], [1, 2], name="Train"),
            _workflow("B", ["op.b"], [1, 2], name="Val"),
            _workflow("C", ["op.c"], [3], name="Test"),
        ]
        splits = {"train_indices": [0], "val_indices": [1], "test_indices": [2]}
        id_mappings = {
            "l3": {"L3_01": 1, "L3_02": 2, "L3_03": 3},
            "mapping_metadata": {
                "gee_to_l3": {
                    "op.a": {"primary_l3": "L3_01", "source": "manual_override"},
                    "op.b": {"primary_l3": "L3_01", "source": "manual_override"},
                    "op.c": {"primary_l3": "L3_03", "source": "manual_override"},
                }
            },
        }

        report = audit_training_data_quality(workflows, splits, id_mappings=id_mappings)

        self.assertEqual(report["split_quality"]["val_tasks_not_in_train"], ["B"])
        self.assertEqual(report["split_quality"]["test_tasks_not_in_train"], ["C"])
        self.assertEqual(report["duplicates"]["cross_split_sequence_hashes"], 1)
        self.assertGreaterEqual(report["warnings"].count("val_has_tasks_not_in_train"), 1)
        self.assertGreaterEqual(report["warnings"].count("cross_split_sequence_duplicates"), 1)

    def test_cli_fail_on_warning_is_report_only(self):
        script_path = PROJECT_ROOT / "scripts" / "audit_training_data_quality.py"
        spec = importlib.util.spec_from_file_location("audit_training_data_quality_cli", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        workflows = [
            _workflow("A", ["op.a"], [1], name="Train"),
            _workflow("B", ["op.b"], [1], name="Val"),
        ]
        splits = {"train_indices": [0], "val_indices": [1], "test_indices": []}
        id_mappings = {
            "l3": {"L3_01": 1},
            "mapping_metadata": {
                "gee_to_l3": {
                    "op.a": {"primary_l3": "L3_01", "source": "manual_override"},
                    "op.b": {"primary_l3": "L3_01", "source": "manual_override"},
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            mappings_path = root / "id_mappings.json"
            out_dir = root / "audit"
            data_path.write_text(
                json.dumps({"labeled_workflows": workflows}, ensure_ascii=False),
                encoding="utf-8",
            )
            splits_path.write_text(json.dumps(splits), encoding="utf-8")
            mappings_path.write_text(json.dumps(id_mappings), encoding="utf-8")

            argv = [
                "audit_training_data_quality.py",
                "--data",
                str(data_path),
                "--splits",
                str(splits_path),
                "--id-mappings",
                str(mappings_path),
                "--out-dir",
                str(out_dir),
                "--fail-on-warning",
            ]
            with patch.object(sys, "argv", argv):
                module.main()

            report = json.loads((out_dir / "training_data_quality_audit.json").read_text(encoding="utf-8"))
            self.assertTrue(report["warnings"])


if __name__ == "__main__":
    unittest.main()
