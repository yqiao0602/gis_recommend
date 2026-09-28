from __future__ import annotations

import unittest

from scripts.export_qgis_api_train_only import export_train_only


def _candidate(candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "record_id": candidate_id,
        "source_root_id": "root",
        "source_path": "/home/yll/source.py",
        "source_sha256": candidate_id.ljust(64, "0"),
        "source_authority_key": f"body:{candidate_id}",
        "source_span": [1, 3],
        "source_snippet": "1 | geom.centroid()",
        "semantic_calls": ["geom.centroid"],
        "semantic_call_sites": [{"line_start": 1, "line_end": 1}],
        "candidate_l3_sequence": ["L3_02_05_11"],
        "dependency_edges": [[0, 1]],
        "task_name": "提取要素质心",
        "task_description": "计算输入要素几何的质心。",
        "parameter_facts": {},
        "dedup_decision": "canonical_keep",
        "source_region_key": "region",
        "call_graph_key": "graph",
        "normalized_dag_key": "dag",
        "training_pair_key": "pair",
    }


class ExportQgisApiTrainOnlyTest(unittest.TestCase):
    def test_exports_random_point_as_composite_pattern_not_api_operator(self) -> None:
        candidate = _candidate("a")
        candidate.update(
            {
                "semantic_calls": ["random_point_sampling"],
                "candidate_l3_sequence": ["L3_02_06_06"],
                "task_name": "在输入图层内随机采样点",
                "task_description": "在输入图层范围内随机采样满足最小距离的点。",
            }
        )

        rows, _, _ = export_train_only(
            [candidate], [], {"L3_02_06_06": 97}
        )

        self.assertEqual(
            rows[0]["operator_sequence"],
            ["pyqgis-pattern:random_point_sampling"],
        )
        self.assertEqual(rows[0]["api_pattern_sequence"], ["random_point_sampling"])
        self.assertEqual(
            rows[0]["call_span_verification"], "verified_composite_api_pattern"
        )
        self.assertEqual(rows[0]["task_type"], "QGIS可验证低层API复合任务")

    def test_exports_stable110_train_only_row(self) -> None:
        rows, ledger, summary = export_train_only(
            [_candidate("a")], [], {"L3_02_05_11": 18}
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["l3_token_ids"], [18])
        self.assertEqual(rows[0]["operator_sequence"], ["pyqgis:centroid"])
        self.assertEqual(rows[0]["source_verification"], "verified_sha256")
        self.assertEqual(rows[0]["call_span_verification"], "verified_api_calls")
        self.assertEqual(rows[0]["training_admission"], "granted_train_only_qgis_api_v1")
        self.assertFalse(rows[0]["validation_eligible"])
        self.assertEqual(ledger[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_suppresses_existing_exact_training_pair(self) -> None:
        existing = [{
            "task_name": "提取要素质心",
            "task_description": "计算输入要素几何的质心。",
            "l3_code_sequence": ["L3_02_05_11"],
        }]

        rows, ledger, summary = export_train_only(
            [_candidate("a")], existing, {"L3_02_05_11": 18}
        )

        self.assertEqual(rows, [])
        self.assertEqual(ledger[0]["cross_pool_decision"], "existing_training_pair_suppressed")
        self.assertEqual(summary["cross_pool_suppressed"], 1)


if __name__ == "__main__":
    unittest.main()
