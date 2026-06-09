from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class SemanticIndexingSimulationTests(unittest.TestCase):
    def test_manual_grouping_normalizes_controlled_aliases_without_semantic_models(self):
        from scripts.evaluate_semantic_indexing_simulation import canonical_group_terms

        ndvi_terms = canonical_group_terms("calculate NDVI vegetation index")
        paraphrase_terms = canonical_group_terms("plant vigor extraction from normalized vegetation signal")

        self.assertIn("sem_vegetation_index", ndvi_terms)
        self.assertIn("sem_vegetation_index", paraphrase_terms)
        self.assertIn("manual_rule", ndvi_terms)
        self.assertNotIn("external_encoder", ndvi_terms)

    def test_grouped_ranking_can_restore_original_candidate_in_synthetic_case(self):
        from scripts.evaluate_semantic_indexing_simulation import (
            RetrievalItem,
            build_manual_grouping_index,
            rank_candidates,
        )

        items = [
            RetrievalItem(index=10, task_type="Vegetation", terms=frozenset({"waterbody"}), canonical_terms=frozenset({"sem_water_index"}), seq=(9, 9)),
            RetrievalItem(index=11, task_type="Vegetation", terms=frozenset({"ndvi"}), canonical_terms=frozenset({"sem_vegetation_index"}), seq=(1, 2)),
        ]
        index = build_manual_grouping_index(items)
        original = rank_candidates("calculate ndvi", "Vegetation", items, index, top_k=2, mode="lexical")
        lexical_perturbed = rank_candidates("plant vigor signal", "Vegetation", items, index, top_k=2, mode="lexical")
        grouped_perturbed = rank_candidates("plant vigor signal", "Vegetation", items, index, top_k=2, mode="manual_grouping")

        self.assertEqual(original[0]["train_index"], 11)
        self.assertEqual(lexical_perturbed[0]["train_index"], 10)
        self.assertEqual(grouped_perturbed[0]["train_index"], 11)

    def test_simulation_shift_separates_recall_gain_from_unsafe_collapse(self):
        from scripts.evaluate_semantic_indexing_simulation import compare_indexing_shift

        original = [{"train_index": 1, "tokens": [1, 2, 3], "score": 0.9}]
        lexical = [{"train_index": 2, "tokens": [4, 5], "score": 0.6}]
        grouped_good = [{"train_index": 1, "tokens": [1, 2, 3], "score": 0.8}]
        grouped_bad = [{"train_index": 3, "tokens": [7, 8], "score": 0.95}]

        good = compare_indexing_shift(
            original_candidates=original,
            lexical_candidates=lexical,
            grouped_candidates=grouped_good,
            reference_tokens=[1, 2, 3],
            transition_allowed_next={"1": {"2": 1}, "2": {"3": 1}, "7": {"8": 1}},
        )
        bad = compare_indexing_shift(
            original_candidates=original,
            lexical_candidates=lexical,
            grouped_candidates=grouped_bad,
            reference_tokens=[1, 2, 3],
            transition_allowed_next={"1": {"2": 1}, "2": {"3": 1}, "7": {"8": 1}},
        )

        self.assertGreater(good["top1_retention_delta"], 0.0)
        self.assertGreater(good["lcs_preservation_delta"], 0.0)
        self.assertEqual(good["false_equivalence"], 0.0)
        self.assertEqual(bad["false_equivalence"], 1.0)
        self.assertEqual(bad["semantic_drift_risk"], 1.0)

    def test_summary_reports_required_risk_and_interpretation_boundaries(self):
        from scripts.evaluate_semantic_indexing_simulation import summarize_simulation_rows

        rows = [
            {
                "family": "semantic_paraphrase",
                "top1_retention_delta": 1.0,
                "topk_overlap_delta": 0.5,
                "lcs_preservation_delta": 0.2,
                "set_f1_preservation_delta": 0.1,
                "retrieval_saturation_reduction": 1.0,
                "false_equivalence": 0.0,
                "semantic_drift_risk": 0.0,
                "execution_invalid_grouping": 0.0,
            },
            {
                "family": "abstraction_shift",
                "top1_retention_delta": -1.0,
                "topk_overlap_delta": -0.25,
                "lcs_preservation_delta": -0.1,
                "set_f1_preservation_delta": -0.2,
                "retrieval_saturation_reduction": -1.0,
                "false_equivalence": 1.0,
                "semantic_drift_risk": 1.0,
                "execution_invalid_grouping": 1.0,
            },
        ]

        summary = summarize_simulation_rows(rows)

        self.assertEqual(summary["perturbation_count"], 2)
        self.assertIn("improved_retrieval_recall", summary)
        self.assertIn("unsafe_semantic_collapse", summary)
        self.assertTrue(summary["interpretation_boundary"]["l2_validated"] is False)

    def test_semantic_indexing_simulation_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_semantic_indexing_simulation.py", "--help"],
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
