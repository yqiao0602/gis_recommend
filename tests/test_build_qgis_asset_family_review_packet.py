import unittest

from scripts.build_qgis_asset_family_review_packet import build_packet


class QgisAssetFamilyReviewPacketTests(unittest.TestCase):
    def test_packet_is_source_disjoint_and_joins_miner_evidence(self):
        normalized = []
        miner = []
        for i, sha in enumerate(("a" * 64, "b" * 64, "c" * 64, "d" * 64)):
            normalized.append({"record_id": f"r{i}", "asset_type": "processing_workflow", "pool": "processing", "source_sha256": sha, "source_verified": True, "dedup_keys": {"operator_sequence": "native:clip|qgis:multiparttosingleparts"}, "processing_operator_ids": ["native:clip", "qgis:multiparttosingleparts"]})
            miner.append({"record_id": f"r{i}", "processing_calls": [{"line_start": 1 + i, "operator_id": "native:clip"}]})
        packet, summary = build_packet(normalized, miner, asset_type="processing_workflow", pool="processing", sequence="native:clip|qgis:multiparttosingleparts", calibration_count=2, holdout_count=2)
        self.assertEqual(len(packet), 4)
        self.assertEqual(summary["source_sha_overlap"], 0)
        self.assertEqual(packet[0]["processing_calls"][0]["line_start"], 1)
        self.assertTrue(all(item["training_rows_emitted"] == 0 for item in packet))

    def test_missing_family_fails_closed(self):
        with self.assertRaises(ValueError):
            build_packet([], [], asset_type="processing_workflow", pool="processing", sequence="native:buffer", calibration_count=1, holdout_count=1)


if __name__ == "__main__":
    unittest.main()
