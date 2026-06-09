from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.evaluate_canonicalized_metrics import (  # noqa: E402
    collect_prediction_records,
    discover_commutative_pairs,
    evaluate_records,
    forbidden_pattern_scan,
)


def _workflow(task_type: str, seq: list[int]) -> dict:
    return {
        "l3_sequence": [-3, *seq, -4],
        "task_metadata": {"task_type": task_type, "task_name": task_type, "task_description": task_type},
    }


class CanonicalizedMetricsTests(unittest.TestCase):
    def test_commutative_training_pairs_can_recover_exact_match(self) -> None:
        workflows = [
            _workflow("Vegetation", [1, 2, 3]),
            _workflow("Vegetation", [2, 1, 3]),
        ]
        pairs = discover_commutative_pairs(workflows, [0, 1])
        self.assertEqual(pairs, {(1, 2)})

        records = [
            {
                "sample_id": "s0",
                "task_type": "Vegetation",
                "method": "retrieval_only",
                "method_family": "retrieval_centered",
                "reference_tokens": [1, 2, 3],
                "pred_tokens": [2, 1, 3],
                "topk_candidates": [[2, 1, 3]],
            }
        ]

        report = evaluate_records(records, pairs, bootstrap_iterations=50, seed=7)
        method = report["methods"]["retrieval_only"]

        self.assertEqual(method["raw_metrics"]["sequence_em"], 0.0)
        self.assertEqual(method["canonicalized_metrics"]["sequence_em"], 1.0)
        self.assertEqual(method["reorder_recovery"]["canonical_exact_recovered_count"], 1)
        self.assertGreater(method["metric_deltas"]["token_accuracy"], 0.0)

    def test_collect_prediction_records_handles_empirical_and_hybrid_artifacts(self) -> None:
        empirical_artifact = {
            "schema_version": "gis_recommend.empirical_evaluation.v1",
            "samples": [
                {
                    "index": 10,
                    "task_type": "A",
                    "reference_tokens": [1, 2],
                    "predictions": {
                        "lexical_retrieval": {
                            "pred_tokens": [2, 1],
                            "beam_candidates": [{"tokens": [2, 1]}, {"tokens": [1, 2]}],
                        }
                    },
                }
            ],
        }
        hybrid_artifact = {
            "schema_version": "gis_recommend.v5_final.hybrid_planner_prototype.v1",
            "samples": [
                {
                    "source_test_index": 11,
                    "task_type": "B",
                    "reference_tokens": [3, 4],
                    "hybrid": {"tokens": [4, 3]},
                    "retrieval_only": {"tokens": [3, 4]},
                    "retrieval_pool": [{"tokens": [4, 3]}, {"tokens": [3, 4]}],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empirical_path = root / "empirical.json"
            hybrid_path = root / "hybrid.json"
            empirical_path.write_text(json.dumps(empirical_artifact), encoding="utf-8")
            hybrid_path.write_text(json.dumps(hybrid_artifact), encoding="utf-8")

            records = collect_prediction_records([empirical_path, hybrid_path])

        by_method = {record["method"]: record for record in records}
        self.assertEqual(by_method["lexical_retrieval"]["topk_candidates"], [[2, 1], [1, 2]])
        self.assertEqual(by_method["hybrid"]["pred_tokens"], [4, 3])
        self.assertEqual(by_method["retrieval_only"]["pred_tokens"], [3, 4])

    def test_topk_canonical_recovery_is_reported(self) -> None:
        pairs = {(1, 2)}
        records = [
            {
                "sample_id": "s0",
                "task_type": "A",
                "method": "v5_final",
                "method_family": "generation",
                "reference_tokens": [1, 2, 3],
                "pred_tokens": [9],
                "topk_candidates": [[9], [2, 1, 3]],
            }
        ]

        report = evaluate_records(records, pairs, bootstrap_iterations=50, seed=9)
        topk = report["methods"]["v5_final"]["topk_recovery"]

        self.assertEqual(topk["raw_topk_exact_rate"], 0.0)
        self.assertEqual(topk["canonical_topk_exact_rate"], 1.0)
        self.assertEqual(topk["canonical_topk_recovered_count"], 1)

    def test_forbidden_pattern_scan_reports_clean_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text("VALUE = 1\n", encoding="utf-8")

            scan = forbidden_pattern_scan([clean])

        self.assertEqual(scan["status"], "pass")
        self.assertEqual(scan["match_count"], 0)


if __name__ == "__main__":
    unittest.main()
