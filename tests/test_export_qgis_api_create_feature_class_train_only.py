from __future__ import annotations

import unittest

from scripts.export_qgis_api_create_feature_class_train_only import export_train_only


def _candidate(key: str) -> dict:
    return {
        "candidate_id": key,
        "record_id": key,
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "source_span": {"segments": [{"line_start": 2, "line_end": 8}]},
        "source_snippet": "2 | create\n8 | write",
        "semantic_calls": ["create_feature_class"],
        "candidate_l3_sequence": ["L3_01_01_01"],
        "dependency_edges": [[0, 1], [1, 2], [2, 3]],
        "parameter_facts": {"geometry_type": "point"},
        "task_name": "创建点要素类",
        "task_description": "创建新的点要素类，使用已准备的字段结构，创建空要素类，并保存为 GPKG 数据。",
        "workflow_scope": "source_verified_local_api_macro",
        "known_omissions": ["whole_function_task_semantics_not_claimed"],
        "source_region_key": f"region-{key}",
        "call_graph_key": f"graph-{key}",
        "normalized_dag_key": "dag",
        "training_pair_key": "pair",
        "dedup_decision": "canonical_keep",
    }


class ExportQgisApiCreateFeatureClassTrainOnlyTest(unittest.TestCase):
    def test_exports_stable125_local_macro_row(self) -> None:
        exported, ledger, summary = export_train_only(
            [_candidate("a")], [], {"L3_01_01_01": 124}
        )

        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["l3_token_ids"], [124])
        self.assertEqual(exported[0]["operator_sequence"], ["pyqgis:create_feature_class"])
        self.assertEqual(exported[0]["taxonomy_profile"], "stable125_authority_v1")
        self.assertEqual(
            exported[0]["workflow_scope"], "source_verified_local_api_macro"
        )
        self.assertEqual(ledger[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_suppresses_existing_training_pair(self) -> None:
        candidate = _candidate("a")
        existing = {
            "task_name": candidate["task_name"],
            "task_description": candidate["task_description"],
            "l3_code_sequence": ["L3_01_01_01"],
        }

        exported, ledger, _ = export_train_only(
            [candidate], [existing], {"L3_01_01_01": 124}
        )

        self.assertEqual(exported, [])
        self.assertEqual(
            ledger[0]["cross_pool_decision"], "existing_training_pair_suppressed"
        )


if __name__ == "__main__":
    unittest.main()
