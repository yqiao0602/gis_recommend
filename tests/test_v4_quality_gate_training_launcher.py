from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _workflow(task_type: str, seq: list[int], name: str = "Task") -> dict:
    return {
        "operator_sequence": ["ee.image.select"],
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
    }


class V4QualityGateTrainingLauncherTests(unittest.TestCase):
    def test_default_paths_are_quality_gate_paths(self):
        import importlib

        launcher = importlib.import_module("scripts.train_v4_quality_gate")

        defaults = launcher.default_paths()

        self.assertEqual(defaults["data"].name, "labeled_workflows_l3_v4_quality_gate.json")
        self.assertEqual(defaults["splits"].name, "dataset_splits_v4_quality_gate.json")
        self.assertEqual(defaults["task_vocab"].name, "task_type_vocabulary_v4_quality_gate.json")
        self.assertEqual(defaults["transition_matrix"].name, "transition_allowed_next.json")
        self.assertEqual(defaults["checkpoint_dir"].name, "transformer_checkpoints_v4_2_quality_gate")
        self.assertIn("step8_quality_gate", str(defaults["data"]))
        self.assertNotIn("pipeline\\step8\\", str(defaults["data"]))

    def test_load_training_inputs_uses_explicit_split_without_rebuilding(self):
        import importlib

        launcher = importlib.import_module("scripts.train_v4_quality_gate")
        workflows = [
            _workflow("A", [1], "a"),
            _workflow("B", [2], "b"),
            _workflow("A", [3], "c"),
        ]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
            "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
            "num_types": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            split_payload = {"train_indices": [2, 0], "val_indices": [1], "test_indices": []}
            data_path.write_text(
                json.dumps({"num_workflows": len(workflows), "labeled_workflows": workflows}),
                encoding="utf-8",
            )
            splits_path.write_text(json.dumps(split_payload), encoding="utf-8")
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")

            loaded = launcher.load_training_inputs(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
            )

            self.assertEqual([wf["task_metadata"]["task_name"] for wf in loaded.train_workflows], ["c", "a"])
            self.assertEqual([wf["task_metadata"]["task_name"] for wf in loaded.val_workflows], ["b"])
            self.assertEqual(loaded.test_workflows, [])
            self.assertEqual(json.loads(splits_path.read_text(encoding="utf-8")), split_payload)

    def test_dry_run_does_not_create_checkpoint_dir(self):
        import importlib

        launcher = importlib.import_module("scripts.train_v4_quality_gate")
        workflows = [
            _workflow("A", [1], "a"),
            _workflow("B", [2], "b"),
            _workflow("A", [3], "c"),
        ]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
            "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
            "num_types": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            checkpoint_dir = root / "ckpt"
            data_path.write_text(
                json.dumps({"num_workflows": len(workflows), "labeled_workflows": workflows}),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": [2]}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")

            result = launcher.main([
                "--data",
                str(data_path),
                "--splits",
                str(splits_path),
                "--task-vocab",
                str(task_vocab_path),
                "--checkpoint-dir",
                str(checkpoint_dir),
                "--dry-run",
            ])

            self.assertEqual(result["workflows_total"], 3)
            self.assertEqual(result["train"], 1)
            self.assertEqual(result["val"], 1)
            self.assertEqual(result["test"], 1)
            self.assertEqual(
                result["metric_contract"]["primary"],
                ["set_f1", "usable", "executable", "qgis_mapping"],
            )
            self.assertIn("token_acc", result["metric_contract"]["diagnostic_only"])
            self.assertEqual(
                result["training_contract"]["system_objective"],
                "increase usable/executable multi-solution GIS operator chains",
            )
            self.assertEqual(result["checkpoint_policy"]["latest_snapshot"], "best_model.pth")
            self.assertFalse(checkpoint_dir.exists())

    def test_non_dry_run_requires_explicit_transition_matrix(self):
        import importlib

        launcher = importlib.import_module("scripts.train_v4_quality_gate")
        workflows = [
            _workflow("A", [1], "a"),
            _workflow("B", [2], "b"),
            _workflow("A", [3], "c"),
        ]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
            "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
            "num_types": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            embeddings_path = root / "l3_embeddings_v2.pt"
            checkpoint_dir = root / "ckpt"
            missing_transition = root / "missing_transition.json"
            data_path.write_text(
                json.dumps({"num_workflows": len(workflows), "labeled_workflows": workflows}),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": [2]}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")
            embeddings_path.write_bytes(b"not reached")

            with self.assertRaisesRegex(FileNotFoundError, "transition matrix"):
                launcher.train_quality_gate(
                    data_path=data_path,
                    splits_path=splits_path,
                    task_vocab_path=task_vocab_path,
                    l3_embeddings_path=embeddings_path,
                    transition_matrix_path=missing_transition,
                    checkpoint_dir=checkpoint_dir,
                    dry_run=False,
                )


if __name__ == "__main__":
    unittest.main()
