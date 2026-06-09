from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.empirical import (
    build_empirical_artifact,
    classify_prediction_errors,
    compute_canonicalization_audit,
)


def _workflow(
    task_type: str,
    name: str,
    desc: str,
    seq: list[int],
    ops: list[str] | None = None,
) -> dict:
    ops = ops or [f"op.{token}" for token in seq]
    return {
        "operator_sequence": ops,
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": desc,
        },
    }


class EmpiricalEvaluationTests(unittest.TestCase):
    def test_error_taxonomy_flags_decode_and_ambiguity_failures(self):
        metrics = {
            "sequence_em": 0.0,
            "set_f1": 0.9,
            "lcs_ratio": 0.4,
            "length_ratio": 1.0,
        }

        categories = classify_prediction_errors(
            pred_tokens=[1, 2, 1, 2],
            ref_tokens=[1, 1, 2, 2],
            metrics=metrics,
            retrieval_score=0.8,
            candidate_pool_size=3,
            rare_reference_tokens=set(),
            local_transition_valid=True,
            executable_valid=None,
        )

        self.assertIn("equivalent_workflow_mismatch", categories)
        self.assertIn("semantically_valid_alternative_workflow", categories)

        collapsed = classify_prediction_errors(
            pred_tokens=[5, 5, 5, 5],
            ref_tokens=[5, 6, 7, 8, 9, 10],
            metrics={
                "sequence_em": 0.0,
                "set_f1": 0.2,
                "lcs_ratio": 0.1,
                "length_ratio": 4 / 6,
            },
            retrieval_score=0.05,
            candidate_pool_size=0,
            rare_reference_tokens={10},
            local_transition_valid=False,
            executable_valid=False,
        )

        self.assertIn("repetitive_collapse", collapsed)
        self.assertIn("retrieval_miss", collapsed)
        self.assertIn("rare_operator_failure", collapsed)
        self.assertIn("local_invalid_workflow", collapsed)
        self.assertIn("executable_invalid_workflow", collapsed)

    def test_canonicalization_audit_reports_entropy_reduction_candidates(self):
        workflows = [
            _workflow("A", "one", "alpha beta", [1, 2, 3]),
            _workflow("A", "two", "alpha beta reversed", [2, 1, 3]),
            _workflow("A", "three", "duplicate", [1, 1, 2, 3]),
            _workflow("B", "four", "stable", [4, 5]),
        ]

        audit = compute_canonicalization_audit(workflows)

        self.assertGreater(audit["sequence_entropy_before_bits"], audit["sequence_entropy_after_bits"])
        self.assertGreaterEqual(audit["normalization_opportunities"]["consecutive_duplicate_workflows"], 1)
        self.assertTrue(audit["commutative_pair_candidates"])

    def test_empirical_artifact_contains_required_prediction_diagnostics(self):
        workflows = [
            _workflow("Vegetation", "NDVI", "calculate vegetation index", [1, 2, 3]),
            _workflow("Water", "NDWI", "calculate water index", [1, 4, 3]),
            _workflow("Terrain", "Slope", "calculate terrain slope", [5, 6]),
            _workflow("Vegetation", "NDVI map", "calculate vegetation index map", [1, 2, 3]),
            _workflow("Water", "Water terrain", "calculate water slope", [1, 4, 6]),
        ]
        splits = {
            "train_indices": [0, 1, 2],
            "val_indices": [],
            "test_indices": [3, 4],
        }
        id_mappings = {
            "l3": {
                "L3_01": 1,
                "L3_02": 2,
                "L3_03": 3,
                "L3_04": 4,
                "L3_05": 5,
                "L3_06": 6,
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            split_path = root / "splits.json"
            mappings_path = root / "id_mappings.json"
            out_path = root / "artifact.json"
            data_path.write_text(
                json.dumps({"labeled_workflows": workflows}, ensure_ascii=False),
                encoding="utf-8",
            )
            split_path.write_text(json.dumps(splits), encoding="utf-8")
            mappings_path.write_text(json.dumps(id_mappings), encoding="utf-8")

            artifact = build_empirical_artifact(
                data_path=data_path,
                split_path=split_path,
                id_mappings_path=mappings_path,
                output_path=out_path,
                max_samples=None,
                retrieval_top_k=3,
                embedding_dim=32,
            )

            self.assertTrue(out_path.exists())
            self.assertEqual(artifact["schema_version"], "gis_recommend.empirical_evaluation.v1")
            self.assertEqual(artifact["dataset_split_metadata"]["train_count"], 3)
            self.assertEqual(artifact["dataset_split_metadata"]["evaluated_count"], 2)
            self.assertIn("retrieval_rerank", artifact["aggregate_metrics"])
            self.assertIn("retrieval_diagnostics", artifact)
            self.assertIn("canonicalization_audit", artifact)
            self.assertIn("dataset_structure_audit", artifact)
            self.assertIn("upper_bound_analysis", artifact)
            self.assertIn("error_taxonomy_summary", artifact)
            self.assertIn("decode_policy_experiments", artifact)
            self.assertIn("bottleneck_attribution", artifact["engineering_report"])
            self.assertIn("definitely_not_work_on", artifact["engineering_report"])
            self.assertEqual(
                artifact["engineering_report"]["bottleneck_attribution"]["model_capacity"]["primary"],
                False,
            )

            sample = artifact["samples"][0]
            self.assertIn("reference_tokens", sample)
            expected_prediction_keys = {
                "lexical_retrieval",
                "embedding_retrieval",
                "nearest_neighbor_workflow",
                "retrieval_rerank",
                "retrieval_constrained",
                "markov2",
            }
            self.assertTrue(expected_prediction_keys.issubset(sample["predictions"]))

            pred = sample["predictions"]["retrieval_rerank"]
            for key in [
                "pred_tokens",
                "beam_candidates",
                "decode_trace",
                "token_probabilities",
                "end_timing",
                "repetition_statistics",
                "candidate_pool_diagnostics",
                "retrieval_diagnostics",
                "reranker_outputs",
                "metrics",
                "error_taxonomy",
            ]:
                self.assertIn(key, pred)
            self.assertTrue(pred["decode_trace"])
            self.assertEqual(len(pred["token_probabilities"]), len(pred["pred_tokens"]))

    def test_empirical_artifact_retrieval_order_is_deterministic_on_ties(self):
        workflows = [
            _workflow("A", "alpha", "same terms", [1, 2]),
            _workflow("A", "beta", "same terms", [1, 3]),
            _workflow("A", "gamma", "same terms", [1, 4]),
            _workflow("A", "delta", "same terms", [1, 5]),
        ]
        splits = {"train_indices": [0, 1, 2], "val_indices": [], "test_indices": [3]}
        id_mappings = {"l3": {f"L3_{token:02d}": token for token in range(1, 6)}}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            split_path = root / "splits.json"
            mappings_path = root / "id_mappings.json"
            data_path.write_text(
                json.dumps({"labeled_workflows": workflows}, ensure_ascii=False),
                encoding="utf-8",
            )
            split_path.write_text(json.dumps(splits), encoding="utf-8")
            mappings_path.write_text(json.dumps(id_mappings), encoding="utf-8")

            first = build_empirical_artifact(
                data_path=data_path,
                split_path=split_path,
                id_mappings_path=mappings_path,
                max_samples=None,
                retrieval_top_k=3,
                embedding_dim=16,
            )
            second = build_empirical_artifact(
                data_path=data_path,
                split_path=split_path,
                id_mappings_path=mappings_path,
                max_samples=None,
                retrieval_top_k=3,
                embedding_dim=16,
            )

        first_candidates = first["samples"][0]["predictions"]["lexical_retrieval"]["beam_candidates"]
        second_candidates = second["samples"][0]["predictions"]["lexical_retrieval"]["beam_candidates"]
        self.assertEqual(first_candidates, second_candidates)


if __name__ == "__main__":
    unittest.main()
