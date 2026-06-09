from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class V5FinalRuntimeTests(unittest.TestCase):
    def _config(self, **overrides):
        from gis_recommend.models.v5_final import V5FinalConfig

        defaults = dict(
            vocab_size=8,
            d_model=16,
            d_key=4,
            n_layers=1,
            n_heads=4,
            d_ff=32,
            max_seq_len=5,
            bert_hidden_size=12,
            dropout=0.0,
            start_token_id=0,
            end_token_id=7,
            pad_token_id=6,
            alpha_noise_p=0.20,
        )
        defaults.update(overrides)
        return V5FinalConfig(**defaults)

    def test_forward_shapes_alpha_causality_and_fixed_gamma(self):
        from gis_recommend.models.v5_final import V5FinalModel

        torch.manual_seed(11)
        config = self._config()
        model = V5FinalModel(config)
        model.eval()

        operator_ids = torch.tensor([[1, 2, 3, 7, 6], [4, 5, 2, 3, 7]])
        task_embeddings = torch.randn(2, 3, config.bert_hidden_size)
        out = model(
            operator_input_ids=operator_ids,
            task_embeddings=task_embeddings,
            return_diagnostics=True,
        )

        self.assertEqual(tuple(out.logits_op.shape), (2, 5, 8))
        self.assertEqual(tuple(out.logits_end.shape), (2, 5, 1))
        self.assertEqual(tuple(out.alpha.shape), (2, 5, 6))
        self.assertEqual(tuple(out.hidden_states.shape), (2, 5, 16))

        for t in range(operator_ids.shape[1]):
            valid = out.alpha[:, t, : t + 1]
            future = out.alpha[:, t, t + 1 :]
            self.assertTrue(torch.allclose(valid.sum(dim=-1), torch.ones(2), atol=1e-5))
            self.assertTrue(torch.all(valid >= 0))
            self.assertTrue(torch.allclose(future, torch.zeros_like(future), atol=1e-7))

        parameter_names = {name for name, _ in model.named_parameters()}
        self.assertFalse(any(name.endswith("gamma") or ".gamma" in name for name in parameter_names))
        self.assertFalse(any(name.endswith("rho") or ".rho" in name for name in parameter_names))
        self.assertEqual(config.gamma, 0.3)
        self.assertEqual(config.rho, 1.5)

    def test_alpha_noise_is_training_only(self):
        from gis_recommend.models.v5_final import V5FinalModel

        torch.manual_seed(13)
        config = self._config(alpha_noise_p=0.25)
        model = V5FinalModel(config)
        operator_ids = torch.tensor([[1, 2, 3, 7]])
        task_embeddings = torch.randn(1, 2, config.bert_hidden_size)

        model.eval()
        eval_alpha_1 = model(
            operator_input_ids=operator_ids,
            task_embeddings=task_embeddings,
            return_diagnostics=True,
        ).alpha
        eval_alpha_2 = model(
            operator_input_ids=operator_ids,
            task_embeddings=task_embeddings,
            return_diagnostics=True,
        ).alpha
        self.assertTrue(torch.allclose(eval_alpha_1, eval_alpha_2))

        model.train()
        torch.manual_seed(99)
        train_alpha = model(
            operator_input_ids=operator_ids,
            task_embeddings=task_embeddings,
            return_diagnostics=True,
        ).alpha
        self.assertFalse(torch.allclose(eval_alpha_1[:, 1:, :], train_alpha[:, 1:, :]))
        self.assertTrue(torch.allclose(train_alpha[:, 2, :3].sum(dim=-1), torch.ones(1), atol=1e-5))

    def test_io_mask_blocks_illegal_tokens_and_keeps_end_allowed(self):
        from gis_recommend.models.v5_final import IOMaskBuilder

        mask_builder = IOMaskBuilder(
            vocab_size=8,
            end_token_id=7,
            allowed_next={1: {3, 4}, 3: {5}},
        )
        first = mask_builder.mask_for_previous(None)
        after_one = mask_builder.mask_for_previous(1)

        self.assertTrue(torch.all(first == 0))
        self.assertEqual(float(after_one[3]), 0.0)
        self.assertEqual(float(after_one[4]), 0.0)
        self.assertEqual(float(after_one[7]), 0.0)
        self.assertTrue(torch.isneginf(after_one[2]))

    def test_greedy_decode_respects_io_constraints_and_trace_shape(self):
        from gis_recommend.models.v5_final import IOMaskBuilder, V5FinalModel

        torch.manual_seed(17)
        config = self._config(vocab_size=6, end_token_id=5, pad_token_id=4, alpha_noise_p=0.0)
        model = V5FinalModel(config)
        model.eval()
        for param in model.parameters():
            param.data.zero_()
        model.op_head.bias.data[:] = torch.tensor([0.0, 10.0, 9.0, 8.0, -10.0, -1.0])
        model.end_head.bias.data.fill_(-10.0)

        mask_builder = IOMaskBuilder(
            vocab_size=6,
            end_token_id=5,
            allowed_next={1: {3}, 3: {5}},
        )
        result = model.decode_greedy(
            task_embeddings=torch.ones(1, 2, config.bert_hidden_size),
            io_mask_builder=mask_builder,
            max_len=4,
        )

        self.assertEqual(result.operator_ids, [1, 3])
        self.assertEqual(result.termination_reason, "end_token")
        self.assertEqual([step["selected_token"] for step in result.decode_trace], [1, 3, 5])
        self.assertEqual(len(result.alpha_trace), 2)
        self.assertAlmostEqual(sum(result.alpha_trace[1]["alpha"]), 1.0, places=5)

    def test_beam_decode_returns_io_legal_candidates_with_independent_traces(self):
        from gis_recommend.models.v5_final import IOMaskBuilder, V5FinalModel

        config = self._config(vocab_size=6, end_token_id=5, pad_token_id=4, alpha_noise_p=0.0)
        model = V5FinalModel(config)
        model.eval()
        for param in model.parameters():
            param.data.zero_()
        model.op_head.bias.data[:] = torch.tensor([0.0, 10.0, 9.5, 9.0, -10.0, -2.0])
        model.end_head.bias.data.fill_(-10.0)
        mask_builder = IOMaskBuilder(
            vocab_size=6,
            end_token_id=5,
            allowed_next={1: {2, 3}, 2: {5}, 3: {5}},
        )

        beams = model.decode_beam(
            task_embeddings=torch.ones(1, 2, config.bert_hidden_size),
            io_mask_builder=mask_builder,
            beam_width=2,
            max_len=3,
        )

        self.assertEqual(len(beams), 2)
        for beam in beams:
            self.assertTrue(beam.operator_ids)
            for prev, cur in zip(beam.operator_ids, beam.operator_ids[1:]):
                self.assertTrue(mask_builder.are_compatible(prev, cur))
            self.assertEqual(len(beam.alpha_trace), len(beam.operator_ids))
            self.assertEqual(beam.termination_reason, "end_token")
        self.assertNotEqual(beams[0].operator_ids, beams[1].operator_ids)

    def test_checkpoint_schema_is_strict_and_rejects_raw_or_v4_payloads(self):
        from gis_recommend.models.v5_final import (
            V5FinalCheckpointError,
            V5FinalModel,
            load_v5_final_checkpoint,
            save_v5_final_checkpoint,
        )

        config = self._config()
        model = V5FinalModel(config)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good_path = root / "v5.pt"
            save_v5_final_checkpoint(
                good_path,
                model=model,
                config=config,
                metric_bundle={"val_loss": 1.25},
                provenance={"run_id": "unit"},
            )
            loaded = load_v5_final_checkpoint(good_path, map_location="cpu")
            self.assertEqual(loaded["provenance"]["format_version"], "gis_recommend.checkpoint.v5")
            self.assertEqual(loaded["provenance"]["model_version"], "v5_final")

            raw_path = root / "raw.pt"
            torch.save(model.state_dict(), raw_path)
            with self.assertRaises(V5FinalCheckpointError):
                load_v5_final_checkpoint(raw_path, map_location="cpu")

            missing_pvm_path = root / "missing_pvm.pt"
            payload = torch.load(good_path, map_location="cpu", weights_only=True)
            payload["model_state_dict"] = {
                key: value for key, value in payload["model_state_dict"].items() if not key.startswith("pvm.")
            }
            torch.save(payload, missing_pvm_path)
            with self.assertRaises(V5FinalCheckpointError):
                load_v5_final_checkpoint(missing_pvm_path, map_location="cpu")

            v4_path = root / "v4.pt"
            torch.save({"model_state_dict": model.state_dict(), "model_version": "v4_2"}, v4_path)
            with self.assertRaises(V5FinalCheckpointError):
                load_v5_final_checkpoint(v4_path, map_location="cpu")

    def test_compute_v5_loss_uses_only_operator_and_end_terms(self):
        from gis_recommend.models.v5_final.losses import compute_v5_loss

        logits_op = torch.tensor([[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]])
        logits_end = torch.tensor([[[-4.0], [4.0]]])
        targets = torch.tensor([[0, 1]])
        y_end = torch.tensor([[0.0, 1.0]])
        pad_mask = torch.tensor([[0, 0]], dtype=torch.bool)

        loss, parts = compute_v5_loss(
            logits_op=logits_op,
            logits_end=logits_end,
            target_op=targets,
            target_end=y_end,
            pad_mask=pad_mask,
            lambda_end=0.3,
        )

        expected_op = torch.nn.functional.cross_entropy(
            logits_op.view(2, 3),
            targets.view(2),
        )
        expected_end = torch.nn.functional.binary_cross_entropy_with_logits(
            logits_end.view(2),
            y_end.view(2),
        )
        self.assertTrue(torch.allclose(loss, expected_op + 0.3 * expected_end))
        self.assertIn("loss_op", parts)
        self.assertIn("loss_end", parts)
        self.assertNotIn("loss_graph", parts)

    def test_diagnostic_graph_is_report_only_and_does_not_mutate_inputs(self):
        from gis_recommend.models.v5_final import IOMaskBuilder, extract_diagnostic_graph

        ops = [1, 2, 3]
        alpha_trace = [
            {"step": 1, "alpha": [1.0]},
            {"step": 2, "alpha": [0.2, 0.8]},
            {"step": 3, "alpha": [0.1, 0.7, 0.2]},
        ]
        ops_before = copy.deepcopy(ops)
        alpha_before = copy.deepcopy(alpha_trace)
        mask_builder = IOMaskBuilder(
            vocab_size=5,
            end_token_id=4,
            allowed_next={1: {2, 3}, 2: {3}},
        )

        graph = extract_diagnostic_graph(
            operator_ids=ops,
            alpha_trace=alpha_trace,
            io_mask_builder=mask_builder,
            token_names={1: "buffer", 2: "clip", 3: "dissolve"},
            threshold_tau=0.15,
        )

        self.assertEqual(ops, ops_before)
        self.assertEqual(alpha_trace, alpha_before)
        self.assertEqual(graph["__status__"], "DIAGNOSTIC_ONLY")
        self.assertIn("NOT ground-truth", graph["__warning__"])
        self.assertEqual(graph["edges"], [{"source": 0, "target": 1}, {"source": 1, "target": 2}])

    def test_empirical_prediction_record_contains_v5_traces_without_runtime_gating(self):
        from gis_recommend.models.v5_final import (
            DecodeResult,
            build_v5_empirical_prediction_record,
        )

        result = DecodeResult(
            operator_ids=[1, 3],
            operator_names=["buffer", "clip"],
            beam_candidates=[{"rank": 0, "tokens": [1, 3], "score": -0.2}],
            decode_trace=[
                {"step": 1, "selected_token": 1, "probability": 0.8},
                {"step": 2, "selected_token": 3, "probability": 0.7},
                {"step": 3, "selected_token": 7, "probability": 0.9},
            ],
            alpha_trace=[{"step": 1, "alpha": [1.0]}, {"step": 2, "alpha": [0.2, 0.8]}],
            token_probabilities=[
                {"position": 0, "token": 1, "probability": 0.8},
                {"position": 1, "token": 3, "probability": 0.7},
            ],
            end_timing={"generated_end_step": 3, "early_end": False},
            repetition_statistics={"length": 2, "unique_count": 2, "unique_ratio": 1.0},
            termination_reason="end_token",
        )
        record = build_v5_empirical_prediction_record(
            sample_id="sample-1",
            decode_result=result,
            reference_tokens=[1, 2, 3],
            retrieval_diagnostics={"top_score": 0.4},
            checkpoint_metadata={"model_version": "v5_final"},
        )

        for key in [
            "pred_tokens",
            "beam_candidates",
            "decode_trace",
            "alpha_trace",
            "token_probabilities",
            "end_timing",
            "repetition_statistics",
            "candidate_pool_diagnostics",
            "retrieval_diagnostics",
            "checkpoint_metadata",
            "diagnostic_only",
        ]:
            self.assertIn(key, record)
        self.assertTrue(record["diagnostic_only"]["alpha_trace"])
        self.assertFalse(record["runtime_gated_by_diagnostics"])
        self.assertEqual(record["pred_tokens"], [1, 3])

    def test_empirical_artifact_can_attach_v5_predictions_as_storage_only(self):
        from gis_recommend.evaluation.empirical import attach_model_predictions_to_artifact

        artifact = {
            "schema_version": "gis_recommend.empirical_evaluation.v1",
            "inference_metadata": {"model_predictions_run": False, "baselines": ["markov2"]},
            "aggregate_metrics": {"markov2": {"n": 1, "lcs_ratio": 0.5}},
            "error_taxonomy_summary": {"sequence_mismatch": 1},
            "samples": [
                {
                    "index": 10,
                    "predictions": {
                        "markov2": {
                            "pred_tokens": [1],
                            "metrics": {"set_f1": 0.0, "lcs_ratio": 0.5, "sequence_em": 0.0, "length_ratio": 1.0},
                            "error_taxonomy": ["sequence_mismatch"],
                        }
                    },
                }
            ],
        }
        v5_record = {
            "method": "v5_final",
            "pred_tokens": [1, 2],
            "metrics": {"set_f1": 1.0, "lcs_ratio": 1.0, "sequence_em": 1.0, "length_ratio": 1.0},
            "error_taxonomy": ["exact_match"],
            "runtime_gated_by_diagnostics": False,
        }

        updated = attach_model_predictions_to_artifact(
            artifact,
            prediction_records_by_index={10: v5_record},
            method="v5_final",
        )

        self.assertIn("v5_final", updated["samples"][0]["predictions"])
        self.assertEqual(updated["samples"][0]["predictions"]["markov2"]["pred_tokens"], [1])
        self.assertEqual(updated["aggregate_metrics"]["v5_final"]["sequence_em"], 1.0)
        self.assertTrue(updated["inference_metadata"]["model_predictions_run"])
        self.assertEqual(updated["inference_metadata"]["model_prediction_method"], "v5_final")
        self.assertFalse(updated["inference_metadata"]["runtime_gated_by_model_diagnostics"])


if __name__ == "__main__":
    unittest.main()
