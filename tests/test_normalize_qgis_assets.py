import json
import tempfile
import unittest
from pathlib import Path

from scripts.normalize_qgis_assets import normalize, normalize_row


class QgisAssetNormalizationTests(unittest.TestCase):
    def test_processing_workflow_keeps_source_and_dedup_lineage(self):
        row = {
            "schema": "gis_recommend.qgis_asset_miner.v1",
            "record_id": "r1",
            "pool": "processing",
            "status": "parsed",
            "asset_type": "processing_workflow_candidate",
            "source_sha256": "a" * 64,
            "processing_calls": [
                {"operator_id": "native:buffer"},
                {"operator_id": "native:dissolve"},
            ],
            "semantic_calls": [],
            "plumbing_calls": [],
        }
        result = normalize_row(row)
        self.assertEqual(result["asset_type"], "processing_workflow")
        self.assertEqual(result["semantic_operations"], ["buffer", "dissolve"])
        self.assertEqual(result["parent_source_sha256"], "a" * 64)
        self.assertEqual(result["training_rows_emitted"], 0)
        self.assertTrue(result["provenance"]["operation_hints_are_not_l3"])

    def test_dynamic_processing_is_deferred_without_guessing(self):
        row = {
            "status": "parsed",
            "asset_type": "dynamic_recovery_candidate",
            "source_sha256": "b" * 64,
            "dynamic_processing_call_count": 1,
            "processing_calls": [{"operator_id": None}],
            "semantic_calls": [],
            "plumbing_calls": [],
        }
        result = normalize_row(row)
        self.assertEqual(result["asset_type"], "processing_dynamic_candidate")
        self.assertEqual(result["candidate_disposition"], "deferred")
        self.assertEqual(result["processing_operator_ids"], [])
        self.assertEqual(result["semantic_operations"], [])

    def test_api_pattern_does_not_become_complete_workflow(self):
        row = {
            "status": "parsed",
            "asset_type": "api_pattern_candidate",
            "source_sha256": "c" * 64,
            "processing_calls": [],
            "semantic_calls": [{"method": "buffer"}, {"method": "centroid"}],
            "plumbing_calls": [{"method": "setGeometry"}],
        }
        result = normalize_row(row)
        self.assertEqual(result["asset_type"], "api_pattern")
        self.assertEqual(result["semantic_operations"], ["buffer", "centroid"])
        self.assertEqual(result["next_gate"], "io_task_l3_dedup_review")

    def test_summary_is_deterministic_and_never_emits_training(self):
        rows, summary = normalize([
            {"status": "parsed", "asset_type": "processing_operator_candidate", "source_sha256": "d" * 64, "processing_calls": [{"operator_id": "native:buffer"}], "semantic_calls": [], "plumbing_calls": []},
            {"status": "source_unresolved", "asset_type": "unresolved_source", "processing_calls": [], "semantic_calls": [], "plumbing_calls": []},
        ])
        self.assertEqual(summary["input_rows"], 2)
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertEqual(rows[0]["dedup_keys"]["semantic_operation_sequence"], "buffer")
        self.assertEqual(rows[1]["candidate_disposition"], "deferred")


if __name__ == "__main__":
    unittest.main()
