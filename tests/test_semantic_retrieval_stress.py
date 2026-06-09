from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class SemanticRetrievalStressTests(unittest.TestCase):
    def test_perturbation_families_are_explicit_and_evaluation_only(self):
        from scripts.evaluate_semantic_retrieval_stress import build_perturbations

        rows = build_perturbations(
            "Calculate NDVI vegetation index in QGIS",
            task_type="Vegetation indicators",
        )
        families = {row["family"] for row in rows}

        self.assertIn("semantic_paraphrase", families)
        self.assertIn("wording_reorder", families)
        self.assertIn("operator_alias_shift", families)
        self.assertIn("platform_wording_variation", families)
        self.assertIn("abstraction_shift", families)
        self.assertTrue(all(row["evaluation_only"] for row in rows))
        self.assertTrue(any("vegetation" in row["perturbed_text"].lower() for row in rows))

    def test_candidate_shift_measures_preservation_and_metric_degradation(self):
        from scripts.evaluate_semantic_retrieval_stress import evaluate_candidate_shift

        original = [
            {"train_index": 1, "tokens": [1, 2, 3], "score": 0.9},
            {"train_index": 2, "tokens": [1, 2], "score": 0.6},
        ]
        perturbed = [
            {"train_index": 3, "tokens": [4, 5, 6], "score": 0.7},
            {"train_index": 2, "tokens": [1, 2], "score": 0.5},
        ]

        shift = evaluate_candidate_shift(
            original_candidates=original,
            perturbed_candidates=perturbed,
            reference_tokens=[1, 2, 3],
            transition_allowed_next={"1": {"2": 1}, "2": {"3": 1}, "4": {"5": 1}, "5": {"6": 1}},
        )

        self.assertEqual(shift["top1_train_index_changed"], 1.0)
        self.assertEqual(shift["original_top1_retained_in_perturbed_topk"], 0.0)
        self.assertAlmostEqual(shift["topk_train_index_overlap_rate"], 1 / 3)
        self.assertLess(shift["metric_delta"]["lcs_ratio"], 0.0)
        self.assertEqual(shift["execution_validity_preserved"], 1.0)
        self.assertEqual(shift["retrieval_saturation_failure"], 1.0)

    def test_summary_keeps_empirical_boundaries_and_family_breakdowns(self):
        from scripts.evaluate_semantic_retrieval_stress import summarize_stress_rows

        rows = [
            {
                "family": "semantic_paraphrase",
                "lexical_jaccard_to_original": 0.2,
                "top1_train_index_changed": 1.0,
                "topk_train_index_overlap_rate": 0.25,
                "original_top1_retained_in_perturbed_topk": 0.0,
                "execution_validity_preserved": 1.0,
                "retrieval_saturation_failure": 1.0,
                "metric_delta": {"lcs_ratio": -0.2, "set_f1": -0.1, "token_accuracy": -0.3},
                "score_delta": -0.4,
            },
            {
                "family": "wording_reorder",
                "lexical_jaccard_to_original": 1.0,
                "top1_train_index_changed": 0.0,
                "topk_train_index_overlap_rate": 1.0,
                "original_top1_retained_in_perturbed_topk": 1.0,
                "execution_validity_preserved": 1.0,
                "retrieval_saturation_failure": 0.0,
                "metric_delta": {"lcs_ratio": 0.0, "set_f1": 0.0, "token_accuracy": 0.0},
                "score_delta": 0.0,
            },
        ]

        summary = summarize_stress_rows(rows)

        self.assertEqual(summary["perturbation_count"], 2)
        self.assertGreater(summary["retrieval_stability"]["top1_change_rate"], 0.0)
        self.assertIn("semantic_paraphrase", summary["by_family"])
        self.assertTrue(summary["interpretation_boundary"]["l2_validated"] is False)

    def test_semantic_retrieval_stress_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_semantic_retrieval_stress.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--eval-samples", result.stdout)
        self.assertIn("--output-dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
