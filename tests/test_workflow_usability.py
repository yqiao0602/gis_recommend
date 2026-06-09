from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.evaluate_workflow_usability import (  # noqa: E402
    LexicalRetrieval,
    evaluate_candidate_usability,
    evaluate_records,
    forbidden_pattern_scan,
    qgis_mapped_tokens_from_id_mappings,
)


class WorkflowUsabilityTests(unittest.TestCase):
    def test_candidate_with_required_steps_and_qgis_mapping_is_usable(self) -> None:
        result = evaluate_candidate_usability(
            pred_tokens=[1, 2, 3],
            ref_tokens=[1, 2, 3],
            qgis_mapped_tokens={1, 2, 3},
        )

        self.assertEqual(result["required_step_coverage"], 1.0)
        self.assertEqual(result["harmful_step_rate"], 0.0)
        self.assertEqual(result["missing_critical_step_rate"], 0.0)
        self.assertEqual(result["executable_qgis_mapping_rate"], 1.0)
        self.assertEqual(result["workflow_logic_consistency"], 1.0)
        self.assertEqual(result["redundancy_rate"], 0.0)
        self.assertTrue(result["usable"])
        self.assertEqual(result["failure_taxonomy"], [])

    def test_candidate_with_missing_harmful_and_unmapped_steps_is_not_usable(self) -> None:
        result = evaluate_candidate_usability(
            pred_tokens=[1, 99, 99],
            ref_tokens=[1, 2, 3],
            qgis_mapped_tokens={1, 2, 3},
        )

        self.assertLess(result["required_step_coverage"], 1.0)
        self.assertGreater(result["harmful_step_rate"], 0.0)
        self.assertGreater(result["missing_critical_step_rate"], 0.0)
        self.assertLess(result["executable_qgis_mapping_rate"], 1.0)
        self.assertFalse(result["usable"])
        self.assertIn("missing_critical_steps", result["failure_taxonomy"])
        self.assertIn("harmful_steps", result["failure_taxonomy"])
        self.assertIn("qgis_unmapped_steps", result["failure_taxonomy"])

    def test_topk_usable_rate_counts_later_candidate_without_promoting_top1(self) -> None:
        records = [
            {
                "sample_id": "s0",
                "task_type": "Vegetation",
                "method": "retrieval_only",
                "method_family": "retrieval_centered",
                "reference_tokens": [1, 2, 3],
                "pred_tokens": [1, 99],
                "topk_candidates": [[1, 99], [1, 2, 3]],
            }
        ]

        report = evaluate_records(records, qgis_mapped_tokens={1, 2, 3, 99}, bootstrap_iterations=50, seed=11)
        method = report["methods"]["retrieval_only"]

        self.assertEqual(method["top1"]["usable_rate"], 0.0)
        self.assertEqual(method["top3_usable_rate"], 1.0)
        self.assertEqual(method["top5_usable_rate"], 1.0)
        self.assertEqual(method["topk_recovery_counts"]["top3_usable_not_top1"], 1)

    def test_qgis_mapping_index_uses_existing_primary_and_candidate_l3_codes(self) -> None:
        id_mappings = {
            "l3": {
                "L3_A": 1,
                "L3_B": 2,
                "L3_C": 3,
            },
            "mapping_metadata": {
                "qgis_to_l3": {
                    "Tool A": {"primary_l3": "L3_A"},
                    "Tool B": {"all_candidates": [{"l3_code": "L3_B"}]},
                }
            },
        }

        mapped = qgis_mapped_tokens_from_id_mappings(id_mappings)

        self.assertEqual(mapped, {1, 2})

    def test_lexical_retrieval_ranks_same_task_candidates_by_query_overlap(self) -> None:
        train_workflows = [
            {
                "task_metadata": {
                    "task_type_normalized": "Vegetation",
                    "task_name": "NDVI vegetation health",
                    "task_description": "compute vegetation index from red nir bands",
                },
                "l3_sequence": [1, 2, 3],
            },
            {
                "task_metadata": {
                    "task_type_normalized": "Vegetation",
                    "task_name": "Flood water mapping",
                    "task_description": "detect inundation and surface water extent",
                },
                "l3_sequence": [9, 8, 7],
            },
        ]

        retrieval = LexicalRetrieval(train_workflows)
        ranked = retrieval.retrieve(
            "Vegetation",
            query_text="water inundation flood extent",
            k=2,
        )

        self.assertEqual(ranked[0]["tokens"], [9, 8, 7])
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])
        self.assertEqual(ranked[0]["retrieval_method"], "query_jaccard")

    def test_forbidden_pattern_scan_reports_clean_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text("VALUE = 1\n", encoding="utf-8")

            scan = forbidden_pattern_scan([clean])

        self.assertEqual(scan["status"], "pass")
        self.assertEqual(scan["match_count"], 0)


if __name__ == "__main__":
    unittest.main()
