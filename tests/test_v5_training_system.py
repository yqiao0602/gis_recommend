from __future__ import annotations

import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _workflow(seq: list[int], name: str = "unit") -> dict:
    return {
        "l3_sequence": [-3, *seq, -4],
        "task_metadata": {
            "task_type": "unit",
            "task_name": name,
            "task_description": f"{name} workflow",
        },
    }


class V5TrainingSystemTests(unittest.TestCase):
    def test_io_mask_annealing_schedule_is_deterministic(self):
        from gis_recommend.training.train_v5 import io_mask_bias_for_epoch

        self.assertEqual(io_mask_bias_for_epoch(0), 3.0)
        self.assertEqual(io_mask_bias_for_epoch(20), 10.0)
        self.assertEqual(io_mask_bias_for_epoch(30), 10.0)
        self.assertAlmostEqual(io_mask_bias_for_epoch(10), 6.5)
        self.assertEqual(io_mask_bias_for_epoch(10), io_mask_bias_for_epoch(10))

    def test_training_io_masks_use_soft_bias_and_keep_end_allowed(self):
        from gis_recommend.models.v5_final import IOMaskBuilder
        from gis_recommend.training.train_v5 import build_training_io_masks

        operator_ids = torch.tensor([[1, 2, 7, 6]])
        pad_mask = torch.tensor([[False, False, False, True]])
        builder = IOMaskBuilder(vocab_size=8, end_token_id=7, allowed_next={1: {3}, 2: {7}})

        masks = build_training_io_masks(
            operator_ids=operator_ids,
            pad_mask=pad_mask,
            io_mask_builder=builder,
            bias=4.25,
        )

        self.assertEqual(tuple(masks.shape), (1, 4, 8))
        self.assertTrue(torch.all(masks[0, 0] == 0.0))
        self.assertEqual(float(masks[0, 1, 3]), 0.0)
        self.assertEqual(float(masks[0, 1, 7]), 0.0)
        self.assertEqual(float(masks[0, 1, 4]), -4.25)
        self.assertTrue(torch.all(masks[0, 3] == 0.0))

    def test_deterministic_subset_selection_is_seeded_and_sorted(self):
        from gis_recommend.training.train_v5 import select_deterministic_subset

        indices = list(range(20))
        first = select_deterministic_subset(indices, subset_size=5, seed=123)
        second = select_deterministic_subset(indices, subset_size=5, seed=123)
        third = select_deterministic_subset(indices, subset_size=5, seed=124)

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(first, sorted(first))
        self.assertEqual(select_deterministic_subset(indices, subset_size=None, seed=123), indices)

    def test_monitoring_and_collapse_detection_are_report_only(self):
        from gis_recommend.models.v5_final import DecodeResult, V5ForwardOutput
        from gis_recommend.training.train_v5 import detect_collapses, summarize_stability

        alpha = torch.zeros(2, 4, 5)
        for t in range(4):
            alpha[:, t, t] = 1.0
        output = V5ForwardOutput(
            logits_op=torch.zeros(2, 4, 8),
            logits_end=torch.tensor([[[5.0], [5.0], [5.0], [5.0]], [[5.0], [5.0], [5.0], [5.0]]]),
            alpha=alpha,
            hidden_states=torch.zeros(2, 4, 8),
        )
        pad_mask = torch.zeros(2, 4, dtype=torch.bool)
        decoded = [
            DecodeResult(operator_ids=[1], repetition_statistics={"max_run": 1, "repeated_bigram_events": 0}, end_timing={"generated_end_step": 2, "predicted_content_length": 1}),
            DecodeResult(operator_ids=[2, 2, 2, 2], repetition_statistics={"max_run": 4, "repeated_bigram_events": 2}, end_timing={"generated_end_step": 5, "predicted_content_length": 4}),
        ]

        summary = summarize_stability(
            output=output,
            pad_mask=pad_mask,
            decode_results=decoded,
            memory_grad_norm=0.0,
        )
        collapses = detect_collapses(
            summary,
            loss_history=[1.0, 1.1, 3.0],
        )

        self.assertLess(summary["alpha_entropy_mean"], 0.01)
        self.assertGreater(summary["recency_mass_mean"], 0.95)
        self.assertTrue(collapses["memory_ignore_collapse"])
        self.assertTrue(collapses["recency_collapse"])
        self.assertTrue(collapses["early_end_collapse"])
        self.assertTrue(collapses["repetition_loop_collapse"])
        self.assertTrue(collapses["unstable_loss_spike"])
        self.assertTrue(collapses["dead_memory_slots"])
        self.assertFalse(collapses["mutates_runtime"])

    def test_ablation_flags_change_runtime_config_without_governance_layers(self):
        from gis_recommend.models.v5_final import V5FinalConfig, V5FinalModel

        config = V5FinalConfig(
            vocab_size=8,
            d_model=16,
            d_key=4,
            n_layers=1,
            n_heads=4,
            d_ff=32,
            max_seq_len=4,
            bert_hidden_size=12,
            dropout=0.0,
            end_token_id=7,
            pad_token_id=6,
            no_pvm=True,
            no_qk_decoupling=True,
            no_fixed_gamma=True,
            no_alpha_noise=True,
        )
        model = V5FinalModel(config)
        model.train()
        out = model(
            operator_input_ids=torch.tensor([[1, 2, 7, 6]]),
            task_embeddings=torch.ones(1, 2, 12),
            return_diagnostics=True,
        )

        self.assertTrue(model.config.no_pvm)
        self.assertTrue(model.config.no_qk_decoupling)
        self.assertTrue(model.config.no_fixed_gamma)
        self.assertTrue(model.config.no_alpha_noise)
        self.assertEqual(tuple(out.logits_op.shape), (1, 4, 8))

    def test_train_v5_smoke_writes_checkpoints_and_evaluation_report(self):
        from gis_recommend.training.train_v5 import V5TrainConfig, train_v5

        workflows = [
            _workflow([1, 2], "a"),
            _workflow([1, 3], "b"),
            _workflow([2, 3], "c"),
            _workflow([3, 1], "d"),
            _workflow([2, 1], "e"),
            _workflow([3, 2], "f"),
        ]
        splits = {"train_indices": [0, 1, 2, 3], "val_indices": [4], "test_indices": [5]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            split_path = root / "splits.json"
            ckpt_dir = root / "checkpoints"
            report_path = root / "evaluation.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            split_path.write_text(json.dumps(splits), encoding="utf-8")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", FutureWarning)
                result = train_v5(
                    V5TrainConfig(
                        data_path=data_path,
                        splits_path=split_path,
                        checkpoint_dir=ckpt_dir,
                        evaluation_report_path=report_path,
                        vocab_size=8,
                        d_model=16,
                        d_key=4,
                        n_layers=1,
                        n_heads=4,
                        d_ff=32,
                        bert_hidden_size=12,
                        max_seq_len=4,
                        batch_size=2,
                        num_epochs=2,
                        patience=1,
                        subset_size=4,
                        eval_samples=1,
                        beam_width=2,
                        use_amp=False,
                        seed=7,
                    )
                )

            self.assertTrue((ckpt_dir / "latest_model.pt").exists())
            self.assertTrue((ckpt_dir / "best_model.pt").exists())
            self.assertTrue((ckpt_dir / "training_history_v5.json").exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(report_path.with_suffix(".md").exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "gis_recommend.v5_final.evaluation.v1")
            self.assertIn("stability", report)
            self.assertIn("collapse_summary", report)
            self.assertIn("empirical_artifact", report)
            self.assertIn("checkpoint_metadata", report)
            self.assertEqual(report["checkpoint_metadata"]["evaluated_checkpoint_kind"], "best")
            required_metrics = {
                "sequence_em",
                "token_accuracy",
                "top3_token_accuracy",
                "lcs_ratio",
                "set_f1",
                "length_accuracy",
                "io_validity",
                "perplexity",
            }
            self.assertTrue(required_metrics.issubset(report["metrics"]))
            self.assertIn("decode_failure_taxonomy", report)
            self.assertIn("retrieval_generation_attribution", report)
            self.assertEqual(report["retrieval_generation_attribution"]["generation_only_samples"], 1)
            self.assertEqual(report["samples"][0]["reference_tokens"], [3, 2])
            self.assertEqual(report["runtime_contract"]["diagnostics_gate_execution"], False)
            self.assertEqual(result["train_count"], 4)
            self.assertEqual(result["best_checkpoint"], str(ckpt_dir / "best_model.pt"))
            self.assertFalse([item for item in caught if issubclass(item.category, FutureWarning)])

    def test_full_training_script_dry_run_uses_train_v5_engine(self):
        from scripts.train_v5 import main

        workflows = [_workflow([1, 2], "a"), _workflow([2, 1], "b")]
        splits = {"train_indices": [0], "val_indices": [], "test_indices": [1]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            split_path = root / "splits.json"
            checkpoint_dir = root / "checkpoints"
            report_path = root / "evaluation.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            split_path.write_text(json.dumps(splits), encoding="utf-8")

            result = main(
                [
                    "--data",
                    str(data_path),
                    "--splits",
                    str(split_path),
                    "--checkpoint-dir",
                    str(checkpoint_dir),
                    "--evaluation-report",
                    str(report_path),
                    "--vocab-size",
                    "8",
                    "--dry-run",
                ]
            )

            self.assertTrue(result["dry_run"])
            self.assertEqual(result["workflow_count"], 2)
            self.assertEqual(result["train_count"], 1)
            self.assertFalse(checkpoint_dir.exists())

    def test_disable_pvm_cli_alias_sets_no_pvm_runtime_flag(self):
        from scripts import train_v5 as train_script

        captured = {}

        def fake_train(config):
            captured["config"] = config
            return {"dry_run": True, "no_pvm": config.no_pvm}

        with mock.patch.object(train_script, "train_v5", side_effect=fake_train):
            result = train_script.main(["--disable-pvm", "--dry-run"])

        self.assertTrue(result["no_pvm"])
        self.assertTrue(captured["config"].no_pvm)


if __name__ == "__main__":
    unittest.main()
