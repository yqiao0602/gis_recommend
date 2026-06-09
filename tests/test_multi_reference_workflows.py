from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.evaluate_multi_reference_workflows import (  # noqa: E402
    build_reference_index,
    classify_ambiguity,
    evaluate_record_against_references,
    evaluate_records,
    forbidden_pattern_scan,
)


def _workflow(task_type: str, text: str, seq: list[int]) -> dict:
    return {
        "l3_sequence": [-3, *seq, -4],
        "task_metadata": {
            "task_type": task_type,
            "task_name": text,
            "task_description": text,
        },
    }


class MultiReferenceWorkflowTests(unittest.TestCase):
    def test_best_multi_reference_recovers_alternative_valid_sequence(self) -> None:
        record = {
            "sample_id": "s0",
            "task_type": "Vegetation",
            "reference_tokens": [1, 2, 3],
            "pred_tokens": [1, 4, 3],
            "topk_candidates": [[1, 4, 3]],
        }
        refs = [[1, 2, 3], [1, 4, 3]]

        result = evaluate_record_against_references(record, refs, commutative_pairs=set())

        self.assertEqual(result["raw_single_reference_metrics"]["sequence_em"], 0.0)
        self.assertEqual(result["best_of_multi_reference_metrics"]["sequence_em"], 1.0)
        self.assertEqual(result["best_reference_rank"], 1)
        self.assertTrue(result["multi_reference_exact_recovered"])

    def test_canonicalized_multi_reference_tolerates_commutative_order(self) -> None:
        record = {
            "sample_id": "s0",
            "task_type": "Vegetation",
            "reference_tokens": [1, 2, 3],
            "pred_tokens": [2, 1, 3],
            "topk_candidates": [[2, 1, 3]],
        }

        result = evaluate_record_against_references(record, [[1, 2, 3]], commutative_pairs={(1, 2)})

        self.assertEqual(result["raw_single_reference_metrics"]["sequence_em"], 0.0)
        self.assertEqual(result["best_of_multi_reference_metrics"]["sequence_em"], 0.0)
        self.assertEqual(result["canonicalized_multi_reference_metrics"]["sequence_em"], 1.0)
        self.assertTrue(result["canonical_exact_recovered"])

    def test_reference_index_groups_exact_task_text_before_task_family(self) -> None:
        workflows = [
            _workflow("Vegetation", "calculate ndvi", [1, 2, 3]),
            _workflow("Vegetation", "calculate ndvi", [1, 4, 3]),
            _workflow("Vegetation", "classify land cover", [9, 8]),
        ]

        index = build_reference_index(workflows)
        refs = index.references_for({"task_type": "Vegetation", "task_text": "calculate ndvi", "reference_tokens": [1]})

        self.assertEqual(refs["reference_pool_scope"], "exact_task_text")
        self.assertEqual(refs["reference_count"], 2)
        self.assertIn([1, 4, 3], refs["references"])

    def test_evaluate_records_reports_retrieval_family_benefit(self) -> None:
        records = [
            {
                "sample_id": "s0",
                "task_type": "Vegetation",
                "method": "retrieval_only",
                "method_family": "retrieval_centered",
                "reference_tokens": [1, 2, 3],
                "pred_tokens": [1, 4, 3],
                "topk_candidates": [[1, 4, 3]],
                "reference_pool": [[1, 2, 3], [1, 4, 3]],
            },
            {
                "sample_id": "s1",
                "task_type": "Vegetation",
                "method": "v5_final",
                "method_family": "generation",
                "reference_tokens": [1, 2, 3],
                "pred_tokens": [9, 9],
                "topk_candidates": [[9, 9]],
                "reference_pool": [[1, 2, 3], [1, 4, 3]],
            },
        ]

        report = evaluate_records(records, commutative_pairs=set(), bootstrap_iterations=50, seed=3)

        self.assertEqual(report["methods"]["retrieval_only"]["recovery"]["multi_reference_exact_recovered_count"], 1)
        self.assertGreater(
            report["method_family_summary"]["retrieval_centered"]["metric_deltas"]["multi_vs_raw_lcs_ratio"],
            report["method_family_summary"]["generation"]["metric_deltas"]["multi_vs_raw_lcs_ratio"],
        )

    def test_classify_ambiguity_separates_reorder_and_alternative_branch(self) -> None:
        self.assertIn("local_reorder", classify_ambiguity([1, 2, 3], [2, 1, 3], commutative_pairs={(1, 2)}))
        self.assertIn("alternative_branch", classify_ambiguity([1, 2, 3], [1, 4, 3], commutative_pairs=set()))

    def test_forbidden_pattern_scan_reports_clean_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text("VALUE = 1\n", encoding="utf-8")

            scan = forbidden_pattern_scan([clean])

        self.assertEqual(scan["status"], "pass")
        self.assertEqual(scan["match_count"], 0)


if __name__ == "__main__":
    unittest.main()
