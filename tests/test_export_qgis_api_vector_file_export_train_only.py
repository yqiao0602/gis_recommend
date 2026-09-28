from __future__ import annotations

import unittest

from scripts.export_qgis_api_vector_file_export_train_only import export_train_only


def _candidate(candidate_id: str = "a") -> dict:
    return {
        "candidate_id": candidate_id,
        "record_id": candidate_id,
        "source_root_id": "root",
        "source_path": "/home/yll/source.py",
        "source_sha256": candidate_id.ljust(64, "0"),
        "source_authority_key": f"body:{candidate_id}",
        "source_span": {"segments": [{"line_start": 1, "line_end": 3}]},
        "source_snippet": "1 | writer(layer, path)",
        "candidate_l3_sequence": ["L3_07_04_01"],
        "dependency_edges": [[0, 1]],
        "task_name": "保存矢量图层为 GPKG",
        "task_description": "将已准备的矢量图层写入GPKG数据集。",
        "parameter_facts": {"writer_format": "GPKG"},
        "workflow_scope": "source_verified_local_api_macro",
        "whole_function_semantics_admission": "not_granted",
        "known_omissions": ["upstream_layer_preparation_outside_local_writer_boundary"],
        "dedup_decision": "canonical_keep",
        "source_region_key": "region",
        "call_graph_key": "graph",
        "normalized_dag_key": "dag",
    }


class ExportQgisApiVectorFileExportTrainOnlyTest(unittest.TestCase):
    def test_exports_stable125_local_writer_macro(self) -> None:
        rows, ledger, summary = export_train_only(
            [_candidate()],
            [],
            {"L3_07_04_01": 63},
        )

        self.assertEqual(rows[0]["l3_token_ids"], [63])
        self.assertEqual(
            rows[0]["operator_sequence"],
            ["pyqgis:save_vector_features_to_file"],
        )
        self.assertEqual(rows[0]["taxonomy_profile"], "stable125_authority_v1")
        self.assertFalse(rows[0]["validation_eligible"])
        self.assertEqual(ledger[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_suppresses_existing_exact_training_pair(self) -> None:
        existing = [
            {
                "task_name": "保存矢量图层为 GPKG",
                "task_description": "将已准备的矢量图层写入GPKG数据集。",
                "l3_code_sequence": ["L3_07_04_01"],
            }
        ]

        rows, ledger, summary = export_train_only(
            [_candidate()],
            existing,
            {"L3_07_04_01": 63},
        )

        self.assertEqual(rows, [])
        self.assertEqual(
            ledger[0]["cross_pool_decision"],
            "existing_training_pair_suppressed",
        )
        self.assertEqual(summary["cross_pool_suppressed"], 1)


if __name__ == "__main__":
    unittest.main()
