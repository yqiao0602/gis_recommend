import unittest

from scripts.expand_qgis_family_candidates import expand


class QgisFamilyExpansionTests(unittest.TestCase):
    def test_matches_contiguous_subsequence_and_preserves_parent(self):
        rows = [{"asset_type": "processing_workflow", "pool": "processing", "source_sha256": "a" * 64, "source_verified": True, "processing_operator_ids": ["native:buffer", "native:clip", "qgis:multiparttosingleparts", "native:dissolve"], "record_id": "r"}]
        candidates, summary = expand(rows, target=["native:clip", "qgis:multiparttosingleparts"])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["matched_span"], {"start_index": 1, "end_index_exclusive": 3})
        self.assertEqual(candidates[0]["full_parent_operator_sequence"][0], "native:buffer")
        self.assertEqual(summary["matched_parent_rows"], 1)
        self.assertEqual(candidates[0]["training_rows_emitted"], 0)

    def test_multiple_occurrences_are_explicit_candidates(self):
        rows = [{"asset_type": "processing_workflow", "pool": "processing", "source_sha256": "b" * 64, "source_verified": True, "processing_operator_ids": ["native:clip", "qgis:multiparttosingleparts", "native:clip", "qgis:multiparttosingleparts"], "record_id": "r"}]
        candidates, summary = expand(rows, target=["native:clip", "qgis:multiparttosingleparts"])
        self.assertEqual(len(candidates), 2)
        self.assertEqual(summary["candidate_rows"], 2)

    def test_non_workflow_is_not_promoted(self):
        rows = [{"asset_type": "processing_implementation", "pool": "processing", "source_sha256": "c" * 64, "source_verified": True, "processing_operator_ids": ["native:clip", "qgis:multiparttosingleparts"]}]
        candidates, _ = expand(rows, target=["native:clip", "qgis:multiparttosingleparts"])
        self.assertEqual(candidates, [])

    def test_processing_shaped_workflow_in_api_pool_is_retained(self):
        rows = [{"asset_type": "processing_workflow", "pool": "api", "source_sha256": "e" * 64, "source_verified": True, "processing_operator_ids": ["native:clip", "qgis:multiparttosingleparts"], "record_id": "api-r"}]
        candidates, summary = expand(rows, target=["native:clip", "qgis:multiparttosingleparts"])
        self.assertEqual(summary["processing_workflow_rows"], 1)
        self.assertEqual(candidates[0]["pool"], "api")


if __name__ == "__main__":
    unittest.main()
