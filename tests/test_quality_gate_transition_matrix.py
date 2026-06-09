from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _workflow(seq: list[int]) -> dict:
    return {
        "operator_sequence": ["ee.image.select"],
        "l3_sequence": seq,
        "task_metadata": {
            "task_type": "A",
            "task_name": "task",
            "task_description": "desc",
        },
    }


class QualityGateTransitionMatrixTests(unittest.TestCase):
    def test_default_paths_target_quality_gate_input_and_v2_output(self):
        import importlib

        builder = importlib.import_module("scripts.build_quality_gate_transition_matrix")

        defaults = builder.default_paths()

        self.assertEqual(defaults["data"].name, "labeled_workflows_l3_v4_quality_gate.json")
        self.assertEqual(defaults["splits"].name, "dataset_splits_v4_quality_gate.json")
        self.assertEqual(defaults["output"].name, "transition_allowed_next.json")
        self.assertIn("step8_quality_gate", str(defaults["data"]))
        self.assertNotIn("pipeline\\step8\\", str(defaults["data"]))

    def test_build_transition_matrix_from_train_split_with_v2_special_tokens(self):
        import importlib

        builder = importlib.import_module("scripts.build_quality_gate_transition_matrix")
        workflows = [
            _workflow([-3, 1, 2, -4]),
            _workflow([-3, 1, 3, -4]),
            _workflow([-3, 9, -4]),
        ]
        split_payload = {"train_indices": [0, 1], "val_indices": [2], "test_indices": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            split_path = root / "splits.json"
            out_path = root / "transition_allowed_next.json"
            data_path.write_text(
                json.dumps({"labeled_workflows": workflows}),
                encoding="utf-8",
            )
            split_path.write_text(json.dumps(split_payload), encoding="utf-8")

            payload = builder.build_transition_matrix(
                data_path=data_path,
                splits_path=split_path,
                output_path=out_path,
                split_name="train",
            )

            allowed = payload["allowed_next"]
            self.assertEqual(allowed["96"]["1"], 2)
            self.assertEqual(allowed["1"]["2"], 1)
            self.assertEqual(allowed["1"]["3"], 1)
            self.assertEqual(allowed["2"]["97"], 1)
            self.assertEqual(allowed["3"]["97"], 1)
            self.assertNotIn("9", allowed)
            self.assertEqual(payload["metadata"]["workflow_count"], 2)
            self.assertEqual(payload["metadata"]["invalid_transition_count"], 0)
            self.assertTrue(out_path.exists())

    def test_out_of_range_tokens_are_reported_and_excluded(self):
        import importlib

        builder = importlib.import_module("scripts.build_quality_gate_transition_matrix")
        workflows = [
            _workflow([-3, 1, 352, -4]),
        ]
        split_payload = {"train_indices": [0], "val_indices": [], "test_indices": []}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            split_path = root / "splits.json"
            out_path = root / "transition_allowed_next.json"
            data_path.write_text(
                json.dumps({"labeled_workflows": workflows}),
                encoding="utf-8",
            )
            split_path.write_text(json.dumps(split_payload), encoding="utf-8")

            payload = builder.build_transition_matrix(
                data_path=data_path,
                splits_path=split_path,
                output_path=out_path,
                split_name="train",
            )

            self.assertEqual(payload["allowed_next"], {"96": {"1": 1}})
            self.assertEqual(payload["metadata"]["invalid_transition_count"], 2)
            self.assertEqual(payload["metadata"]["invalid_tokens"], [352])


if __name__ == "__main__":
    unittest.main()
