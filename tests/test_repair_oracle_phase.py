from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class RepairOraclePhaseTests(unittest.TestCase):
    def test_controlled_edit_candidates_include_only_local_operations(self):
        from scripts.evaluate_repair_oracle_phase import generate_controlled_edit_candidates

        rows = generate_controlled_edit_candidates(
            base_tokens=[1, 2, 3],
            substitution_tokens=[4],
            bridge_tokens=[5],
            io_valid=lambda tokens: tokens != [1, 4, 3],
            max_candidates=30,
        )
        by_tokens = {tuple(row["tokens"]): row for row in rows}

        self.assertIn((1, 2, 3), by_tokens)
        self.assertIn((1, 3), by_tokens)
        self.assertIn((1, 2, 5, 3), by_tokens)
        self.assertIn((1, 3, 2), by_tokens)
        self.assertNotIn((1, 4, 3), by_tokens)
        self.assertEqual(by_tokens[(1, 3, 2)]["repair_operation"], "local_swap")
        self.assertTrue(all(row["full_regeneration"] is False for row in rows))
        self.assertTrue(all(row["edit_distance_from_identity"] <= 2 for row in rows))

    def test_repair_attribution_reports_metric_deltas_and_retention(self):
        from scripts.evaluate_repair_oracle_phase import repair_candidate_attribution

        attribution = repair_candidate_attribution(
            identity_tokens=[1, 2, 3],
            candidate_tokens=[1, 2, 4],
            reference_tokens=[1, 2, 4],
            identity_io_validity=1.0,
            candidate_io_validity=1.0,
        )

        self.assertEqual(attribution["edit_distance"], 1)
        self.assertAlmostEqual(attribution["lcs_retention"], 2 / 3)
        self.assertGreater(attribution["set_f1_delta"], 0.0)
        self.assertGreater(attribution["token_accuracy_delta"], 0.0)
        self.assertEqual(attribution["execution_validity_delta"], 0.0)

    def test_oracle_analysis_separates_repair_win_and_selection_failure(self):
        from scripts.evaluate_repair_oracle_phase import analyze_repair_oracle

        analysis = analyze_repair_oracle(
            identity_candidate={"tokens": [1, 2, 3], "score": 0.9},
            repaired_candidates=[
                {"tokens": [1, 2, 3], "execution_aware_score": 1.0, "repair_operation": "identity"},
                {"tokens": [1, 2, 4], "execution_aware_score": 0.5, "repair_operation": "operator_substitution"},
            ],
            retrieval_pool=[
                {"tokens": [1, 2, 3]},
                {"tokens": [9, 9]},
            ],
            selected_candidate={"tokens": [1, 2, 3], "repair_operation": "identity"},
            reference_tokens=[1, 2, 4],
        )

        self.assertGreater(analysis["oracle_repair_gain"]["lcs_ratio"], 0.0)
        self.assertTrue(analysis["repair_selection_failed"])
        self.assertEqual(analysis["repair_win"], 1.0)
        self.assertEqual(analysis["repair_corruption"], 0.0)
        self.assertEqual(analysis["best_repaired_candidate"]["tokens"], [1, 2, 4])

    def test_failure_taxonomy_distinguishes_saturation_quality_and_rerank(self):
        from scripts.evaluate_repair_oracle_phase import classify_repair_failure

        self.assertEqual(
            classify_repair_failure(identity_lcs=0.8, retrieval_oracle_lcs=0.8, repair_oracle_lcs=0.8, selected_lcs=0.8),
            "retrieval_saturation",
        )
        self.assertEqual(
            classify_repair_failure(identity_lcs=0.3, retrieval_oracle_lcs=0.7, repair_oracle_lcs=0.3, selected_lcs=0.3),
            "repair_quality_failure",
        )
        self.assertEqual(
            classify_repair_failure(identity_lcs=0.3, retrieval_oracle_lcs=0.7, repair_oracle_lcs=0.6, selected_lcs=0.3),
            "rerank_failure",
        )
        self.assertEqual(
            classify_repair_failure(identity_lcs=0.4, retrieval_oracle_lcs=0.4, repair_oracle_lcs=0.6, selected_lcs=0.6),
            "repair_success",
        )

    def test_summary_aggregates_oracle_and_corruption_rates(self):
        from scripts.evaluate_repair_oracle_phase import summarize_oracle_rows

        summary = summarize_oracle_rows(
            [
                {
                    "oracle_repair_gain": {"lcs_ratio": 0.2, "set_f1": 0.1, "token_accuracy": 0.1},
                    "repair_selection_failed": True,
                    "repair_corruption": 0.0,
                    "repair_win": 1.0,
                },
                {
                    "oracle_repair_gain": {"lcs_ratio": -0.1, "set_f1": -0.1, "token_accuracy": 0.0},
                    "repair_selection_failed": False,
                    "repair_corruption": 1.0,
                    "repair_win": 0.0,
                },
            ]
        )

        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["repair_selection_failure_rate"], 0.5)
        self.assertEqual(summary["repair_corruption_rate"], 0.5)
        self.assertEqual(summary["repair_win_rate"], 0.5)
        self.assertAlmostEqual(summary["mean_oracle_repair_gain"]["lcs_ratio"], 0.05)

    def test_candidate_attribution_summary_counts_wins_and_corruptions(self):
        from scripts.evaluate_repair_oracle_phase import summarize_candidate_attributions

        summary = summarize_candidate_attributions(
            [
                {"lcs_delta": 0.2, "edit_distance": 1, "lcs_retention": 0.8},
                {"lcs_delta": -0.1, "edit_distance": 1, "lcs_retention": 0.7},
                {"lcs_delta": 0.0, "edit_distance": 0, "lcs_retention": 1.0},
            ]
        )

        self.assertEqual(summary["candidate_count"], 3)
        self.assertAlmostEqual(summary["candidate_repair_win_rate"], 1 / 3)
        self.assertAlmostEqual(summary["candidate_corruption_rate"], 1 / 3)

    def test_repair_oracle_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_repair_oracle_phase.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--output-dir", result.stdout)
        self.assertIn("--max-repair-candidates", result.stdout)


if __name__ == "__main__":
    unittest.main()
