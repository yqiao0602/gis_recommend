import unittest

from scripts.build_qgis_family_calibration_packet import build_packet


class QgisFamilyCalibrationPacketTests(unittest.TestCase):
    def test_source_split_is_disjoint_and_keeps_all_occurrences(self):
        normalized = []
        miner = []
        for i in range(4):
            sha = f"{i + 1:x}" * 64
            normalized.append({"record_id": f"r{i}", "pool": "processing", "asset_type": "processing_workflow", "source_sha256": sha, "source_verified": True, "parent_source_sha256": sha, "source_path": f"/tmp/{i}.py", "processing_operator_ids": ["native:dissolve", "native:multiparttosingleparts"], "dedup_keys": {"operator_sequence": "native:dissolve|native:multiparttosingleparts"}})
            miner.append({"record_id": f"r{i}", "processing_calls": [{"operator_id": "native:dissolve"}, {"operator_id": "native:multiparttosingleparts"}]})
        packet, summary = build_packet(normalized, miner, target=["native:dissolve", "native:multiparttosingleparts"], calibration_sources=2, holdout_sources=2)
        self.assertEqual(summary["source_sha_overlap"], 0)
        self.assertEqual(summary["calibration_source_count"], 2)
        self.assertEqual(len(packet), 4)
        self.assertEqual(packet[0]["processing_calls"][0]["operator_id"], "native:dissolve")

    def test_insufficient_sources_fails_closed(self):
        with self.assertRaises(ValueError):
            build_packet([], [], target=["native:dissolve", "native:multiparttosingleparts"], calibration_sources=1, holdout_sources=1)


if __name__ == "__main__":
    unittest.main()
