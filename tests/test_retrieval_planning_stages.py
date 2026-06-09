from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class RetrievalPlanningStageTests(unittest.TestCase):
    def test_overlap_filtering_supports_soft_and_hard_modes(self):
        from scripts.evaluate_retrieval_planning_stages import filter_retrieval_candidates

        candidates = [
            {"tokens": [1, 2, 3], "score": 0.50, "train_index": 1},
            {"tokens": [4, 5], "score": 0.90, "train_index": 2},
        ]
        token_scores = {1: 0.9, 2: 0.8, 3: 0.7}

        soft = filter_retrieval_candidates(
            candidates,
            token_scores,
            mode="soft",
            threshold=0.50,
            set_weight=1.0,
            min_keep=1,
        )
        hard = filter_retrieval_candidates(
            candidates,
            token_scores,
            mode="hard",
            threshold=0.50,
            set_weight=1.0,
            min_keep=1,
        )

        self.assertEqual([row["tokens"] for row in soft], [[1, 2, 3], [4, 5]])
        self.assertEqual([row["tokens"] for row in hard], [[1, 2, 3]])
        self.assertGreater(soft[0]["filter_score"], soft[1]["filter_score"])
        self.assertEqual(soft[0]["set_filter"]["candidate_recall"], 1.0)

    def test_filter_metrics_measure_recall_lcs_and_diversity_before_after(self):
        from scripts.evaluate_retrieval_planning_stages import retrieval_filtering_metrics

        before = [
            {"tokens": [1, 2, 3]},
            {"tokens": [4, 5]},
            {"tokens": [1, 2, 3]},
        ]
        after = [{"tokens": [1, 2, 3]}]

        metrics = retrieval_filtering_metrics(before, after, reference=[1, 2, 4])

        self.assertEqual(metrics["before"]["candidate_count"], 3)
        self.assertEqual(metrics["after"]["candidate_count"], 1)
        self.assertAlmostEqual(metrics["before"]["candidate_recall"], 1.0)
        self.assertAlmostEqual(metrics["after"]["candidate_recall"], 2 / 3)
        self.assertLess(metrics["after"]["unique_sequences"], metrics["before"]["unique_sequences"])

    def test_local_repair_candidates_are_strictly_local(self):
        from scripts.evaluate_retrieval_planning_stages import generate_local_repair_candidates

        repairs = generate_local_repair_candidates(
            base_tokens=[1, 2, 3],
            token_scores={4: 0.95, 5: 0.90},
            neighbor_tokens=[6],
            max_edits=1,
            io_valid=lambda tokens: tokens != [1, 4, 3],
            max_candidates=20,
        )
        by_tokens = {tuple(row["tokens"]): row for row in repairs}

        self.assertIn((1, 2, 3), by_tokens)
        self.assertIn((1, 2), by_tokens)
        self.assertIn((1, 2, 4), by_tokens)
        self.assertIn((1, 2, 6, 3), by_tokens)
        self.assertNotIn((1, 4, 3), by_tokens)
        self.assertTrue(all(row["edit_distance_from_source"] <= 1 for row in repairs))

    def test_repair_summary_splits_gain_corruption_and_preservation(self):
        from scripts.evaluate_retrieval_planning_stages import summarize_repair_outcomes

        summary = summarize_repair_outcomes(
            [
                {
                    "repair_lcs_gain": 0.2,
                    "repair_token_accuracy_gain": 0.1,
                    "repair_corruption": False,
                    "edit_distance_from_retrieval": 1,
                    "retrieved_token_preservation_ratio": 0.8,
                    "executable_improvement": 1.0,
                },
                {
                    "repair_lcs_gain": -0.1,
                    "repair_token_accuracy_gain": -0.2,
                    "repair_corruption": True,
                    "edit_distance_from_retrieval": 1,
                    "retrieved_token_preservation_ratio": 0.7,
                    "executable_improvement": 0.0,
                },
            ]
        )

        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["repair_success_rate"], 0.5)
        self.assertEqual(summary["breakage_rate"], 0.5)
        self.assertAlmostEqual(summary["mean_delta_lcs"], 0.05)

    def test_execution_aware_rerank_prefers_valid_set_agreement_over_lexical_only(self):
        from scripts.evaluate_retrieval_planning_stages import execution_aware_rerank_candidates

        candidates = [
            {
                "tokens": [8, 9],
                "score": 0.95,
                "retrieval_rank": 0,
                "edit_distance_from_retrieval": 0,
                "io_validity": 0.0,
            },
            {
                "tokens": [1, 2],
                "score": 0.70,
                "retrieval_rank": 1,
                "edit_distance_from_retrieval": 0,
                "io_validity": 1.0,
            },
        ]

        ranked = execution_aware_rerank_candidates(
            candidates,
            predicted_token_scores={1: 0.9, 2: 0.8},
            expected_length=2,
            weights={"retrieval": 0.2, "io": 1.0, "set": 1.0, "length": 0.3, "agreement": 0.2, "edit_penalty": 0.1},
        )

        self.assertEqual(ranked[0]["tokens"], [1, 2])
        self.assertGreater(ranked[0]["execution_aware_score"], ranked[1]["execution_aware_score"])
        self.assertIn("set_predictor_agreement", ranked[0]["execution_features"])

    def test_stage_report_attribution_keeps_contribution_channels_separate(self):
        from scripts.evaluate_retrieval_planning_stages import stage_attribution_summary

        summary = stage_attribution_summary(
            retrieval_delta={"lcs_ratio": 0.10},
            rerank_delta={"lcs_ratio": 0.03},
            repair_delta={"lcs_ratio": -0.01},
            generation_delta={"lcs_ratio": 0.0},
        )

        self.assertEqual(summary["retrieval_contribution"]["lcs_ratio"], 0.10)
        self.assertEqual(summary["rerank_contribution"]["lcs_ratio"], 0.03)
        self.assertEqual(summary["repair_contribution"]["lcs_ratio"], -0.01)
        self.assertEqual(summary["generation_contribution"]["lcs_ratio"], 0.0)

    def test_explicit_missing_set_predictor_checkpoint_fails(self):
        import torch
        from scripts.evaluate_retrieval_planning_stages import _build_set_prediction_source

        with self.assertRaises(FileNotFoundError):
            _build_set_prediction_source(
                checkpoint=PROJECT_ROOT / "missing_set_predictor_checkpoint.pth",
                task_vocab_path=PROJECT_ROOT / "missing_task_vocab.json",
                train_items=[],
                device=torch.device("cpu"),
                bert_model_name="bert-base-uncased",
                bert_local_files_only=True,
            )

    def test_retrieval_planning_stage_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_retrieval_planning_stages.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--set-predictor-checkpoint", result.stdout)
        self.assertIn("--output-root", result.stdout)


if __name__ == "__main__":
    unittest.main()
