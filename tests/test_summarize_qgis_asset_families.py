import unittest

from scripts.summarize_qgis_asset_families import summarize


class QgisAssetFamilySummaryTests(unittest.TestCase):
    def test_processing_and_api_families_are_separate(self):
        base = {"pool": "processing", "source_sha256": "a" * 64, "next_gate": "io_task_l3_dedup_review", "record_id": "p1", "asset_type": "processing_workflow", "dedup_keys": {"operator_sequence": "native:buffer|native:dissolve", "semantic_operation_sequence": "buffer|dissolve"}}
        api = {"pool": "api", "source_sha256": "b" * 64, "next_gate": "io_task_l3_dedup_review", "record_id": "a1", "asset_type": "api_pattern", "dedup_keys": {"operator_sequence": "", "semantic_operation_sequence": "buffer|dissolve", "api_method_sequence": "buffer|centroid"}}
        families, summary = summarize([base, {**base, "record_id": "p2", "source_sha256": "c" * 64}, api])
        self.assertEqual(len(families), 2)
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertEqual({item["pool"] for item in families}, {"processing", "api"})

    def test_min_count_filters_rare_families(self):
        row = {"pool": "api", "source_sha256": "d" * 64, "record_id": "r", "asset_type": "api_semantic_unit", "dedup_keys": {"semantic_operation_sequence": "buffer"}}
        families, summary = summarize([row], min_count=2)
        self.assertEqual(families, [])
        self.assertEqual(summary["family_count"], 0)


if __name__ == "__main__":
    unittest.main()
