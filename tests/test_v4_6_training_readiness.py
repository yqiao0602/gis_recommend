from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _workflow(task_type: str, seq: list[int], name: str) -> dict:
    return {
        "operator_sequence": ["ee.image.select"],
        "l3_sequence": [-3, *seq, -4],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
    }


def _task_vocab() -> dict:
    return {
        "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
        "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
        "num_types": 3,
    }


def _registry_payload() -> dict:
    return {
        "entries": [
            {
                "task_type": "A",
                "task_name": "Task A",
                "task_description": "Task A description",
                "references": [[-3, 1, 2, -4], [-3, 2, 1, -4]],
            }
        ]
    }


def _length_stats_payload() -> dict:
    return {
        "schema_version": "gis_recommend.task_type_length_stats.v1",
        "sequence_length_definition": "content_l3_tokens_excluding_specials",
        "global": {"mean": 6.0, "median": 5, "p90": 9},
        "by_task_type": {
            "A": {"count": 10, "mean": 3.0, "median": 3, "p90": 4},
            "B": {"count": 10, "mean": 11.0, "median": 11, "p90": 15},
        },
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
                    _workflow("A", [1, 2], "Task A"),
                    _workflow("B", [3, 4], "Task B"),
                    _workflow("A", [2, 1], "Task A variant"),
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


class V46TrainingReadinessTests(unittest.TestCase):
    def test_dry_run_reports_training_contract_and_mr_coverage(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [
            _workflow("A", [1, 2], "Task A"),
            _workflow("B", [3, 4], "Task B"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            registry_path = root / "registry.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")
            registry_path.write_text(json.dumps(_registry_payload()), encoding="utf-8")

            result = launcher.train_quality_gate_v4_6(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                l3_embeddings_path=root / "emb.pt",
                checkpoint_dir=root / "ckpt",
                dry_run=True,
                mr_registry_path=registry_path,
                mr_ratio=0.5,
            )

        self.assertEqual(result["mr_registry"]["status"], "enabled")
        self.assertEqual(result["mr_registry"]["task_groups"], 1)
        self.assertEqual(result["mr_registry"]["matched_train_samples"], 1)
        self.assertEqual(result["metric_contract"]["primary"], ["set_f1", "usable", "executable", "qgis_mapping"])
        self.assertIn("token_acc", result["metric_contract"]["diagnostic_only"])
        self.assertEqual(result["checkpoint_policy"]["latest_snapshot"], "best_model.pth")
        self.assertIn("best_gen_set_f1_model.pth", result["checkpoint_policy"]["additional_selection_snapshots"])
        self.assertIn("length_bucket_training", result)
        self.assertEqual(result["length_bucket_training"]["status"], "disabled")
        self.assertEqual(result["mrv_training_dataset"]["status"], "disabled")

    def test_dry_run_reports_task_type_length_bucket_summary(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [
            _workflow("A", [1, 2], "Task A"),
            _workflow("B", [3, 4, 5, 6, 7, 8, 9], "Task B"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            length_stats_path = root / "length_stats.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")
            length_stats_path.write_text(json.dumps(_length_stats_payload()), encoding="utf-8")

            result = launcher.train_quality_gate_v4_6(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                l3_embeddings_path=root / "emb.pt",
                checkpoint_dir=root / "ckpt",
                dry_run=True,
                length_stats_path=length_stats_path,
                length_bucket_loss_weight=0.2,
            )

        length_summary = result["length_bucket_training"]
        self.assertEqual(length_summary["status"], "enabled")
        self.assertEqual(length_summary["loss_weight"], 0.2)
        self.assertEqual(length_summary["splits"]["train"]["bucket_counts"], {"short": 1})
        self.assertEqual(length_summary["splits"]["val"]["bucket_counts"], {"long": 1})
        self.assertEqual(length_summary["expected_length_by_bucket"]["short"], 3)
        self.assertEqual(length_summary["expected_length_by_bucket"]["long"], 8)

    def test_explicit_missing_length_stats_fails(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [_workflow("A", [1, 2], "Task A")]

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
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "length stats"):
                launcher.train_quality_gate_v4_6(
                    data_path=data_path,
                    splits_path=splits_path,
                    task_vocab_path=task_vocab_path,
                    l3_embeddings_path=root / "emb.pt",
                    checkpoint_dir=root / "ckpt",
                    dry_run=True,
                    length_stats_path=root / "missing_length_stats.json",
                    length_bucket_loss_weight=0.2,
                )

    def test_explicit_missing_mr_registry_fails_instead_of_silent_disable(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [_workflow("A", [1, 2], "Task A")]

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
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "MR registry"):
                launcher.train_quality_gate_v4_6(
                    data_path=data_path,
                    splits_path=splits_path,
                    task_vocab_path=task_vocab_path,
                    l3_embeddings_path=root / "emb.pt",
                    checkpoint_dir=root / "ckpt",
                    dry_run=True,
                    mr_registry_path=root / "missing_registry.json",
                    mr_ratio=0.5,
                )

    def test_mr_registry_requires_positive_ratio_when_explicit(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [_workflow("A", [1, 2], "Task A")]

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
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")
            registry_path.write_text(json.dumps(_registry_payload()), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "mr_ratio"):
                launcher.train_quality_gate_v4_6(
                    data_path=data_path,
                    splits_path=splits_path,
                    task_vocab_path=task_vocab_path,
                    l3_embeddings_path=root / "emb.pt",
                    checkpoint_dir=root / "ckpt",
                    dry_run=True,
                    mr_registry_path=registry_path,
                    mr_ratio=0.0,
                )

    def test_checkpoint_snapshots_keep_latest_and_metric_best_separate(self) -> None:
        from gis_recommend.training.train_v4_6 import save_metric_selection_snapshots

        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_dir = Path(tmp)
            payloads = [
                {"epoch": 1},
                {"epoch": 2},
            ]

            state = {}
            state = save_metric_selection_snapshots(
                checkpoint_dir,
                payloads[0],
                {"ar_set_f1": 0.4, "ar_lcs": 0.3},
                1,
                state,
            )
            state = save_metric_selection_snapshots(
                checkpoint_dir,
                payloads[1],
                {"ar_set_f1": 0.2, "ar_lcs": 0.5},
                2,
                state,
            )

            latest = torch.load(checkpoint_dir / "best_gen_set_f1_model.pth", weights_only=True)
            best_lcs = torch.load(checkpoint_dir / "best_gen_lcs_model.pth", weights_only=True)

        self.assertEqual(latest["epoch"], 1)
        self.assertEqual(best_lcs["epoch"], 2)
        self.assertEqual(state["manifest"]["selection_snapshots"]["gen_set_f1"]["epoch"], 1)
        self.assertEqual(state["manifest"]["selection_snapshots"]["gen_lcs"]["epoch"], 2)

    def test_direct_v46_main_delegates_to_quality_gate_launcher(self) -> None:
        from gis_recommend.training import train_v4_6

        with mock.patch("scripts.train_v4_6_quality_gate.main", return_value={"dry_run": True}) as patched:
            result = train_v4_6.main(["--dry-run"])

        patched.assert_called_once_with(["--dry-run"])
        self.assertEqual(result, {"dry_run": True})

    def test_length_bucket_targets_and_loss_are_optional(self) -> None:
        from gis_recommend.data.length_bucket_predictor import LengthBucketPredictor
        from gis_recommend.training.train_v4_6 import ScheduledSamplingTrainerV4_6

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            length_stats_path = root / "length_stats.json"
            length_stats_path.write_text(json.dumps(_length_stats_payload()), encoding="utf-8")

            trainer = object.__new__(ScheduledSamplingTrainerV4_6)
            trainer.device = torch.device("cpu")
            trainer.length_bucket_predictor = LengthBucketPredictor(length_stats_path)
            trainer.id_to_task_type = {1: "A", 2: "B", 3: "Unknown"}
            trainer.length_bucket_loss_weight = 0.25

            enabled_targets = trainer._length_bucket_targets(torch.tensor([1, 2, 3]))
            disabled_trainer = object.__new__(ScheduledSamplingTrainerV4_6)
            disabled_trainer.device = torch.device("cpu")
            disabled_trainer.length_bucket_predictor = None
            disabled_trainer.id_to_task_type = {}
            disabled_trainer.length_bucket_loss_weight = 0.0

        self.assertTrue(torch.equal(enabled_targets, torch.tensor([3.0, 8.0, 5.0])))
        self.assertIsNone(disabled_trainer._length_bucket_targets(torch.tensor([1, 2])))

        length_pred = torch.log(torch.tensor([[3.0], [8.0], [5.0]]))
        self.assertLess(trainer._length_bucket_loss(length_pred, torch.tensor([1, 2, 3])).item(), 1e-6)
        self.assertEqual(disabled_trainer._length_bucket_loss(length_pred, torch.tensor([1, 2])).item(), 0.0)

    def test_mrv_ablation_version_switches_to_verified_augmented_training_data(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [
            _workflow("A", [1, 2], "Task A"),
            _workflow("B", [3, 4], "Task B"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "base_data.json"
            splits_path = root / "base_splits.json"
            task_vocab_path = root / "base_task_vocab.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(_task_vocab()), encoding="utf-8")
            mrv_dir = _write_mrv_ablation_version(root / "mrv")

            result = launcher.train_quality_gate_v4_6(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                l3_embeddings_path=root / "emb.pt",
                checkpoint_dir=root / "ckpt",
                dry_run=True,
                mrv_ablation_dir=mrv_dir,
                mrv_ablation_version="all",
            )

        mrv_summary = result["mrv_training_dataset"]
        self.assertEqual(mrv_summary["status"], "enabled")
        self.assertEqual(mrv_summary["version_name"], "mr_all_1")
        self.assertEqual(mrv_summary["injected_variants"], 1)
        self.assertEqual(result["workflows_total"], 3)
        self.assertEqual(result["train"], 2)
        self.assertEqual(result["val"], 1)
        self.assertIn("mrv", result["data_path"])


if __name__ == "__main__":
    unittest.main()
