from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    module_path = PROJECT_ROOT / "scripts" / "analyze_reranker_degraded.py"
    spec = importlib.util.spec_from_file_location("analyze_reranker_degraded", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AnalyzeRerankerDegradedTests(unittest.TestCase):
    def test_analyze_report_counts_groups_and_length_buckets(self):
        mod = _load_module()
        report = {
            "experiment_meta": {"eval_mode": "dev"},
            "per_sample": [
                {
                    "index": 1,
                    "task_name": "a",
                    "task_type": "TypeA",
                    "ref_len": 6,
                    "reranker_effect": "improved",
                    "baseline_set_f1": 0.4,
                    "baseline_lcs_ratio": 0.3,
                    "baseline_length_ratio": 0.8,
                    "delta_set_f1": 0.2,
                    "delta_lcs_ratio": 0.1,
                    "delta_length_ratio": 0.1,
                    "reranker_pool_size": 5,
                    "reranker_features": {"l3_score": 0.8, "qgis_confidence": 0.7, "set_overlap": 0.6},
                },
                {
                    "index": 2,
                    "task_name": "b",
                    "task_type": "TypeB",
                    "ref_len": 12,
                    "reranker_effect": "degraded",
                    "baseline_set_f1": 0.6,
                    "baseline_lcs_ratio": 0.5,
                    "baseline_length_ratio": 1.0,
                    "delta_set_f1": -0.2,
                    "delta_lcs_ratio": -0.1,
                    "delta_length_ratio": -0.2,
                    "reranker_pool_size": 8,
                    "reranker_features": {"l3_score": 0.3, "qgis_confidence": 0.9, "set_overlap": 0.2},
                },
                {
                    "index": 3,
                    "task_name": "c",
                    "task_type": "TypeB",
                    "ref_len": 18,
                    "reranker_effect": "unchanged",
                    "baseline_set_f1": 0.5,
                    "baseline_lcs_ratio": 0.4,
                    "baseline_length_ratio": 1.0,
                    "delta_set_f1": 0.0,
                    "delta_lcs_ratio": 0.0,
                    "delta_length_ratio": 0.0,
                    "reranker_pool_size": 2,
                    "reranker_features": {"l3_score": 0.4, "qgis_confidence": 0.5, "set_overlap": 0.4},
                },
            ],
        }

        analysis = mod.analyze_report_data(report, top_n=3)

        summary = analysis["summary"]
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["improved"], 1)
        self.assertEqual(summary["degraded"], 1)
        self.assertEqual(summary["unchanged"], 1)
        self.assertEqual(analysis["degraded_length_buckets"]["medium"], 1)
        self.assertEqual(analysis["task_type_degraded_counts"]["TypeB"], 1)

    def test_analyze_report_compares_features_and_ranks_worst_degraded(self):
        mod = _load_module()
        report = {
            "per_sample": [
                {
                    "index": 10,
                    "task_name": "worse",
                    "task_type": "TypeA",
                    "ref_len": 9,
                    "reranker_effect": "degraded",
                    "baseline_set_f1": 0.9,
                    "baseline_lcs_ratio": 0.8,
                    "baseline_length_ratio": 1.0,
                    "delta_set_f1": -0.4,
                    "delta_lcs_ratio": -0.2,
                    "delta_length_ratio": 0.0,
                    "reranker_pool_size": 7,
                    "reranker_features": {
                        "l3_score": 0.2,
                        "qgis_confidence": 0.95,
                        "set_overlap": 0.1,
                        "unknown_ratio": 0.0,
                    },
                },
                {
                    "index": 11,
                    "task_name": "less-worse",
                    "task_type": "TypeA",
                    "ref_len": 7,
                    "reranker_effect": "degraded",
                    "baseline_set_f1": 0.8,
                    "baseline_lcs_ratio": 0.8,
                    "baseline_length_ratio": 1.0,
                    "delta_set_f1": -0.1,
                    "delta_lcs_ratio": -0.1,
                    "delta_length_ratio": 0.0,
                    "reranker_pool_size": 4,
                    "reranker_features": {
                        "l3_score": 0.3,
                        "qgis_confidence": 0.85,
                        "set_overlap": 0.2,
                        "unknown_ratio": 0.1,
                    },
                },
                {
                    "index": 12,
                    "task_name": "better",
                    "task_type": "TypeB",
                    "ref_len": 5,
                    "reranker_effect": "improved",
                    "baseline_set_f1": 0.3,
                    "baseline_lcs_ratio": 0.2,
                    "baseline_length_ratio": 0.7,
                    "delta_set_f1": 0.3,
                    "delta_lcs_ratio": 0.2,
                    "delta_length_ratio": 0.2,
                    "reranker_pool_size": 9,
                    "reranker_features": {
                        "l3_score": 0.9,
                        "qgis_confidence": 0.6,
                        "set_overlap": 0.8,
                        "unknown_ratio": 0.0,
                    },
                },
            ]
        }

        analysis = mod.analyze_report_data(report, top_n=2)

        worst = analysis["top_degraded"][0]
        self.assertEqual(worst["index"], 10)
        feature_compare = analysis["feature_compare"]
        self.assertAlmostEqual(feature_compare["l3_score"]["degraded_avg"], 0.25)
        self.assertAlmostEqual(feature_compare["l3_score"]["improved_avg"], 0.9)
        self.assertIn("delta_composite", worst)


if __name__ == "__main__":
    unittest.main()
