from __future__ import annotations

import sys
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class V5EmpiricalExperimentScriptTests(unittest.TestCase):
    def test_beam_oracle_metrics_include_token_accuracy_and_lcs(self):
        from scripts.evaluate_v5_beam_search import beam_oracle_metrics

        candidates = [
            {"tokens": [1, 2, 3], "score": -3.0},
            {"tokens": [1, 4, 3], "score": -2.0},
            {"tokens": [8, 9], "score": -1.0},
        ]

        metrics = beam_oracle_metrics(candidates, [1, 2, 4])

        self.assertEqual(metrics["beam_count"], 3)
        self.assertAlmostEqual(metrics["best_oracle_token_accuracy"], 2 / 3, places=6)
        self.assertAlmostEqual(metrics["best_oracle_lcs_ratio"], 2 / 3, places=6)
        self.assertFalse(metrics["reference_in_beam"])

    def test_beam_diversity_counts_unique_sequences_and_pairwise_lcs_distance(self):
        from scripts.evaluate_v5_beam_search import beam_diversity_metrics

        metrics = beam_diversity_metrics(
            [
                {"tokens": [1, 2, 3]},
                {"tokens": [1, 2, 3]},
                {"tokens": [3, 2, 1]},
            ]
        )

        self.assertEqual(metrics["candidate_count"], 3)
        self.assertEqual(metrics["unique_sequences"], 2)
        self.assertAlmostEqual(metrics["unique_sequence_ratio"], 2 / 3)
        self.assertGreater(metrics["avg_pairwise_lcs_distance"], 0.0)

    def test_length_normalized_selection_is_explicit_and_optional(self):
        from scripts.evaluate_v5_beam_search import select_candidate

        candidates = [
            {"tokens": [1, 2, 3, 4], "score": -2.0},
            {"tokens": [1], "score": -1.0},
        ]

        raw = select_candidate(candidates, length_norm_alpha=0.0)
        normalized = select_candidate(candidates, length_norm_alpha=1.0)

        self.assertEqual(raw["tokens"], [1])
        self.assertEqual(normalized["tokens"], [1, 2, 3, 4])

    def test_retrieval_attribution_separates_copied_and_novel_operators(self):
        from scripts.evaluate_v5_retrieval_assisted import retrieval_copy_attribution

        attribution = retrieval_copy_attribution(
            generated_tokens=[1, 2, 4, 4],
            retrieved_sequences=[[1, 3], [2, 5]],
        )

        self.assertEqual(attribution["copied_operators"], [1, 2])
        self.assertEqual(attribution["novel_operators"], [4, 4])
        self.assertEqual(attribution["copied_operator_count"], 2)
        self.assertEqual(attribution["novel_operator_count"], 2)

    def test_retrieval_conditioning_text_contains_task_and_top3_sequences(self):
        from scripts.evaluate_v5_retrieval_assisted import build_retrieval_conditioning_text

        text = build_retrieval_conditioning_text(
            task_text="classify water bodies",
            retrieved_sequences=[[1, 2], [3], [4, 5, 6], [7]],
        )

        self.assertIn("classify water bodies", text)
        self.assertIn("retrieved_workflow_1: 1 2", text)
        self.assertIn("retrieved_workflow_3: 4 5 6", text)
        self.assertNotIn("retrieved_workflow_4", text)

    def test_retrieval_assisted_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_v5_retrieval_assisted.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--retrieval-top-k", result.stdout)

    def test_hybrid_candidate_expansion_preserves_retrieved_identity_and_one_edit(self):
        from scripts.evaluate_v5_hybrid_planner import expand_retrieved_candidate

        variants = expand_retrieved_candidate(
            base_tokens=[1, 2, 3],
            retrieval_rank=0,
            retrieval_score=0.9,
            substitute_tokens_by_position={1: [4]},
            insert_tokens_by_position={2: [5]},
            io_valid=lambda tokens: tokens != [1, 4, 3],
            max_variants=10,
        )
        rows = {tuple(row["tokens"]): row for row in variants}

        self.assertIn((1, 2, 3), rows)
        self.assertIn((1, 3), rows)
        self.assertIn((1, 2, 5, 3), rows)
        self.assertNotIn((1, 4, 3), rows)
        self.assertTrue(all(row["edit_distance_from_retrieval"] <= 1 for row in variants))

    def test_hybrid_preservation_metrics_measure_structure_retention(self):
        from scripts.evaluate_v5_hybrid_planner import retrieval_preservation_metrics

        metrics = retrieval_preservation_metrics(
            selected_tokens=[1, 2, 4],
            retrieved_tokens=[1, 2, 3],
        )

        self.assertAlmostEqual(metrics["retrieval_lcs_ratio"], 2 / 3, places=6)
        self.assertAlmostEqual(metrics["retrieved_token_preservation_ratio"], 2 / 3, places=6)
        self.assertEqual(metrics["edit_distance_from_retrieval"], 1)

    def test_hybrid_score_combines_retrieval_v5_io_length_and_modification_penalty(self):
        from scripts.evaluate_v5_hybrid_planner import hybrid_score_candidate

        identity = hybrid_score_candidate(
            retrieval_score=0.8,
            v5_plausibility=0.3,
            io_validity=1.0,
            length_prior=1.0,
            edit_distance=0,
            weights={"retrieval": 1.0, "v5": 0.5, "io": 0.25, "length": 0.25, "modification_penalty": 0.2},
        )
        modified = hybrid_score_candidate(
            retrieval_score=0.8,
            v5_plausibility=0.3,
            io_validity=1.0,
            length_prior=1.0,
            edit_distance=1,
            weights={"retrieval": 1.0, "v5": 0.5, "io": 0.25, "length": 0.25, "modification_penalty": 0.2},
        )

        self.assertGreater(identity["hybrid_score"], modified["hybrid_score"])
        self.assertEqual(identity["components"]["retrieval"], 0.8)

    def test_hybrid_source_retrieved_tokens_use_selected_retrieval_rank(self):
        from scripts.evaluate_v5_hybrid_planner import source_retrieved_tokens_for_candidate

        tokens = source_retrieved_tokens_for_candidate(
            retrieval_pool=[
                {"tokens": [1, 2, 3]},
                {"tokens": [4, 5, 6]},
            ],
            selected_candidate={"retrieval_rank": 1, "tokens": [4, 5, 6]},
        )

        self.assertEqual(tokens, [4, 5, 6])

    def test_hybrid_topk_sequence_accuracy_uses_candidate_pool(self):
        from scripts.evaluate_v5_hybrid_planner import topk_sequence_accuracy

        self.assertEqual(
            topk_sequence_accuracy(
                candidates=[{"tokens": [1]}, {"tokens": [2, 3]}, {"tokens": [4]}],
                reference=[2, 3],
                k=2,
            ),
            1.0,
        )
        self.assertEqual(
            topk_sequence_accuracy(
                candidates=[{"tokens": [1]}, {"tokens": [2, 3]}, {"tokens": [4]}],
                reference=[4],
                k=2,
            ),
            0.0,
        )

    def test_hybrid_retrieval_fusion_deduplicates_and_records_source_attribution(self):
        from scripts.evaluate_v5_hybrid_planner import fuse_retrieval_candidates

        fused = fuse_retrieval_candidates(
            {
                "lexical": [
                    {"tokens": [1, 2], "score": 0.8, "train_index": 10, "lexical_score": 0.8},
                    {"tokens": [3], "score": 0.4, "train_index": 11},
                ],
                "embedding": [
                    {"tokens": [1, 2], "score": 0.6, "train_index": 10, "embedding_score": 0.6},
                    {"tokens": [4], "score": 0.5, "train_index": 12},
                ],
            },
            top_k=3,
            source_weights={"lexical": 1.0, "embedding": 0.5},
        )

        self.assertEqual(fused[0]["tokens"], [1, 2])
        self.assertEqual(fused[0]["source_methods"], ["embedding", "lexical"])
        self.assertEqual(fused[0]["source_ranks"], {"embedding": 0, "lexical": 0})
        self.assertGreater(fused[0]["retrieval_confidence"], fused[1]["retrieval_confidence"])

    def test_hybrid_repair_outcome_separates_gain_corruption_and_preservation(self):
        from scripts.evaluate_v5_hybrid_planner import repair_outcome_metrics

        improved = repair_outcome_metrics(
            retrieval_tokens=[1, 2, 3],
            selected_tokens=[1, 2, 4],
            reference_tokens=[1, 2, 4],
        )
        corrupted = repair_outcome_metrics(
            retrieval_tokens=[1, 2, 4],
            selected_tokens=[1, 2, 3],
            reference_tokens=[1, 2, 4],
        )

        self.assertGreater(improved["repair_lcs_gain"], 0.0)
        self.assertFalse(improved["repair_corruption"])
        self.assertLess(corrupted["repair_lcs_gain"], -0.01)
        self.assertTrue(corrupted["repair_corruption"])
        self.assertLess(corrupted["retrieved_token_preservation_ratio"], 1.0)

    def test_hybrid_attribution_reports_retrieval_rerank_and_repair_contribution(self):
        from scripts.evaluate_v5_hybrid_planner import contribution_attribution

        attribution = contribution_attribution(
            retrieval_only_metrics={"lcs_ratio": 0.4, "token_accuracy": 0.2},
            selected_source_metrics={"lcs_ratio": 0.5, "token_accuracy": 0.25},
            hybrid_metrics={"lcs_ratio": 0.55, "token_accuracy": 0.3},
        )

        self.assertEqual(attribution["retrieval_contribution"]["lcs_ratio"], 0.4)
        self.assertAlmostEqual(attribution["rerank_contribution"]["lcs_delta"], 0.1)
        self.assertAlmostEqual(attribution["repair_contribution"]["token_accuracy_delta"], 0.05)

    def test_hybrid_safe_rerank_keeps_low_confidence_candidate_from_overriding_anchor(self):
        from scripts.evaluate_v5_hybrid_planner import select_hybrid_candidate

        selected = select_hybrid_candidate(
            [
                {"tokens": [9], "retrieval_rank": 1, "retrieval_score": 0.2, "hybrid_score": 2.0},
                {"tokens": [1, 2], "retrieval_rank": 0, "retrieval_score": 0.9, "hybrid_score": 1.0},
            ],
            rerank_confidence_floor_ratio=0.8,
        )

        self.assertEqual(selected["tokens"], [1, 2])

    def test_hybrid_safe_rerank_uses_neural_score_only_as_confidence_tiebreaker(self):
        from scripts.evaluate_v5_hybrid_planner import select_hybrid_candidate

        selected = select_hybrid_candidate(
            [
                {"tokens": [9], "retrieval_rank": 1, "retrieval_score": 0.88, "hybrid_score": 2.0},
                {"tokens": [1, 2], "retrieval_rank": 0, "retrieval_score": 0.91, "hybrid_score": 1.0},
            ],
            rerank_confidence_floor_ratio=0.8,
        )

        self.assertEqual(selected["tokens"], [1, 2])

    def test_hybrid_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_v5_hybrid_planner.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--dry-run", result.stdout)


if __name__ == "__main__":
    unittest.main()
