from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch
import torch.nn as nn


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


def _registry_payload() -> dict:
    return {
        "entries": [
            {
                "task_type": "A",
                "task_name": "Task A",
                "task_description": "Task A description",
                "references": [[-3, 1, 2, -4], [-3, 2, 9, -4]],
            }
        ]
    }


def _task_vocab() -> dict:
    return {
        "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
        "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
        "num_types": 3,
    }


class _DummyTokenizer:
    def __call__(self, *args, **kwargs):
        max_length = kwargs.get("max_length", 128)
        return {
            "input_ids": torch.zeros(1, max_length, dtype=torch.long),
            "attention_mask": torch.ones(1, max_length, dtype=torch.long),
    }


def _write_mrv_ablation_version(root: Path, *, version_name: str = "mr_all_1") -> Path:
    version_dir = root / version_name
    version_dir.mkdir(parents=True)
    data_path = version_dir / "labeled_workflows_l3_v4_quality_gate.json"
    splits_path = version_dir / "dataset_splits_v4_quality_gate.json"
    task_vocab_path = version_dir / "task_type_vocabulary_v4_quality_gate.json"
    report_path = version_dir / "mrv_training_ablation_report.json"
    data_path.write_text(
        json.dumps(
            {
                "labeled_workflows": [
                    _workflow("A", [1, 2], "a"),
                    _workflow("B", [2], "b"),
                    _workflow("A", [2, 1], "a variant"),
                ]
            }
        ),
        encoding="utf-8",
    )
    splits_path.write_text(
        json.dumps({"train_indices": [0, 2], "val_indices": [1], "test_indices": []}),
        encoding="utf-8",
    )
    task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "policy": {"train_split_only": True, "no_oversampling": True},
                "counts": {
                    "available_verified_mr_variants": 1,
                    "injected_variants": 1,
                    "train_injection_rate_vs_base_train": 1.0,
                },
                "equivalence_family_counts": {"filter_filter": 1},
                "risk_level_counts": {"low": 1},
                "guards": {"val_test_unchanged": True, "excluded_overlap": []},
            }
        ),
        encoding="utf-8",
    )
    (root / "mrv_training_ablation_manifest.json").write_text(
        json.dumps(
            {
                "versions": [
                    {
                        "version_name": version_name,
                        "output_dir": str(version_dir),
                        "paths": {
                            "data": str(data_path),
                            "splits": str(splits_path),
                            "task_vocab": str(task_vocab_path),
                            "report": str(report_path),
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


class SetPredictorQualityGateTrainingLauncherTests(unittest.TestCase):
    def test_default_paths_are_quality_gate_paths(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")

        defaults = launcher.default_paths()

        self.assertEqual(defaults["data"].name, "labeled_workflows_l3_v4_quality_gate.json")
        self.assertEqual(defaults["splits"].name, "dataset_splits_v4_quality_gate.json")
        self.assertEqual(defaults["task_vocab"].name, "task_type_vocabulary_v4_quality_gate.json")
        self.assertEqual(defaults["active_tokens"].name, "set_predictor_active_tokens_quality_gate.json")
        self.assertEqual(defaults["checkpoint_dir"].name, "set_predictor_checkpoints_v3_quality_gate_v4_6")
        self.assertIn("step8_quality_gate", str(defaults["data"]))
        self.assertNotIn("pipeline\\step8\\", str(defaults["data"]))

    def test_load_training_inputs_uses_explicit_split_and_train_only_active_tokens(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")
        workflows = [
            _workflow("A", [1], "a"),
            _workflow("B", [2], "b"),
            _workflow("A", [3, 1], "c"),
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
            self.assertEqual(loaded.active_token_ids, [1, 3])
            self.assertEqual(json.loads(splits_path.read_text(encoding="utf-8")), split_payload)

    def test_dry_run_does_not_create_checkpoint_or_active_token_file(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")
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
            active_tokens_path = root / "active_tokens.json"
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
                "--active-tokens",
                str(active_tokens_path),
                "--checkpoint-dir",
                str(checkpoint_dir),
                "--dry-run",
            ])

            self.assertEqual(result["workflows_total"], 3)
            self.assertEqual(result["train"], 1)
            self.assertEqual(result["val"], 1)
            self.assertEqual(result["test"], 1)
            self.assertEqual(result["num_task_types"], 3)
            self.assertEqual(result["num_active_tokens"], 1)
            self.assertEqual(result["mrv_training_dataset"]["status"], "disabled")
            self.assertEqual(
                result["metric_contract"]["primary"],
                ["planner_selected_set_coverage", "planner_selected_top1_usable_rate", "qgis_mapping"],
            )
            self.assertIn("set_f1", result["metric_contract"]["diagnostic_support"])
            self.assertEqual(result["set_predictor_contract"]["runtime_role"], "coverage_prior_only")
            self.assertFalse(checkpoint_dir.exists())
            self.assertFalse(active_tokens_path.exists())

    def test_explicit_missing_mr_registry_fails_instead_of_silent_disable(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")
        workflows = [_workflow("A", [1, 2], "Task A")]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1},
            "id_to_task_type": {"0": "Unknown", "1": "A"},
            "num_types": 2,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "MR registry"):
                launcher.train_quality_gate(
                    data_path=data_path,
                    splits_path=splits_path,
                    task_vocab_path=task_vocab_path,
                    active_tokens_path=root / "active_tokens.json",
                    checkpoint_dir=root / "ckpt",
                    dry_run=True,
                    mr_registry_path=root / "missing_registry.json",
                )

    def test_mr_registry_expands_active_tokens_and_set_targets(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")
        from gis_recommend.training.train_set_predictor_v3 import SetPredictorDataset, compute_pos_weight

        workflows = [_workflow("A", [1, 2], "Task A")]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1},
            "id_to_task_type": {"0": "Unknown", "1": "A"},
            "num_types": 2,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            registry_path = root / "registry.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")
            registry_path.write_text(json.dumps(_registry_payload()), encoding="utf-8")

            loaded = launcher.load_training_inputs(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                mr_registry_path=registry_path,
            )

        self.assertEqual(loaded.active_token_ids, [1, 2, 9])
        self.assertEqual(loaded.mr_registry_summary["matched_train_samples"], 1)
        self.assertEqual(loaded.mr_registry_summary["variant_active_tokens_added"], [9])

        dataset = SetPredictorDataset(
            loaded.train_workflows,
            loaded.active_token_ids,
            loaded.task_vocab,
            _DummyTokenizer(),
            mr_registry=loaded.mr_registry,
        )
        item = dataset[0]

        self.assertEqual(item["binary_targets"].tolist(), [1.0, 1.0, 1.0])
        self.assertEqual(compute_pos_weight(loaded.train_workflows, loaded.active_token_ids), 0.5)
        self.assertEqual(
            compute_pos_weight(
                loaded.train_workflows,
                loaded.active_token_ids,
                mr_registry=loaded.mr_registry,
            ),
            0.0,
        )

    def test_set_predictor_forwards_local_files_only_to_huggingface_loader(self):
        from gis_recommend.models.set_predictor_v3 import L3SetPredictor

        class FakeBert(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.config = SimpleNamespace(hidden_size=8, num_hidden_layers=2)
                self.probe = nn.Parameter(torch.zeros(1))

        calls: list[tuple[tuple, dict]] = []

        def fake_from_pretrained(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeBert()

        with patch(
            "gis_recommend.models.set_predictor_v3.BertModel.from_pretrained",
            side_effect=fake_from_pretrained,
        ):
            L3SetPredictor(
                num_task_types=2,
                active_token_ids=[1, 2],
                bert_unfreeze_layers=0,
                bert_model_name="local-test-bert",
                bert_local_files_only=True,
            )

        self.assertEqual(calls[0][0], ("local-test-bert",))
        self.assertTrue(calls[0][1]["local_files_only"])

    def test_direct_set_predictor_main_delegates_to_quality_gate_launcher(self):
        from gis_recommend.training import train_set_predictor_v3

        with patch("scripts.train_set_predictor_quality_gate.main", return_value={"dry_run": True}) as patched:
            result = train_set_predictor_v3.main(["--dry-run"])

        patched.assert_called_once_with(["--dry-run"])
        self.assertEqual(result, {"dry_run": True})

    def test_checkpoint_snapshots_keep_latest_and_metric_best_separate(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")

        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_dir = Path(tmp)
            state = {}
            state = launcher.save_metric_selection_snapshots(
                checkpoint_dir,
                {"epoch": 1},
                {
                    "set_f1": 0.30,
                    "topk_recall@5": 0.50,
                    "zero_pred_rate": 0.05,
                    "small_pred_rate_lt2": 0.10,
                },
                1,
                state,
            )
            state = launcher.save_metric_selection_snapshots(
                checkpoint_dir,
                {"epoch": 2},
                {
                    "set_f1": 0.25,
                    "topk_recall@5": 0.70,
                    "zero_pred_rate": 0.00,
                    "small_pred_rate_lt2": 0.00,
                },
                2,
                state,
            )

            best_f1 = torch.load(checkpoint_dir / "best_set_f1_model.pth", weights_only=True)
            best_top5 = torch.load(checkpoint_dir / "best_topk_recall5_model.pth", weights_only=True)

        self.assertEqual(best_f1["epoch"], 1)
        self.assertEqual(best_top5["epoch"], 2)
        self.assertEqual(state["manifest"]["selection_snapshots"]["set_f1"]["epoch"], 1)
        self.assertEqual(state["manifest"]["selection_snapshots"]["topk_recall@5"]["epoch"], 2)
        self.assertEqual(state["manifest"]["recommended_checkpoint"], "best_topk_recall5_model.pth")

    def test_mrv_ablation_version_switches_to_verified_augmented_training_data(self):
        import importlib

        launcher = importlib.import_module("scripts.train_set_predictor_quality_gate")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "base_data.json"
            splits_path = root / "base_splits.json"
            task_vocab_path = root / "base_task_vocab.json"
            active_tokens_path = root / "active_tokens.json"
            checkpoint_dir = root / "ckpt"
            data_path.write_text(json.dumps({"labeled_workflows": [_workflow("A", [1], "a"), _workflow("B", [2], "b")]}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")
            mrv_dir = _write_mrv_ablation_version(root / "mrv")

            result = launcher.train_quality_gate(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                active_tokens_path=active_tokens_path,
                checkpoint_dir=checkpoint_dir,
                dry_run=True,
                mrv_ablation_dir=mrv_dir,
                mrv_ablation_version="all",
            )

        self.assertEqual(result["mrv_training_dataset"]["status"], "enabled")
        self.assertEqual(result["mrv_training_dataset"]["version_name"], "mr_all_1")
        self.assertEqual(result["workflows_total"], 3)
        self.assertEqual(result["train"], 2)
        self.assertEqual(result["val"], 1)
        self.assertIn("mrv", result["data_path"])


if __name__ == "__main__":
    unittest.main()
