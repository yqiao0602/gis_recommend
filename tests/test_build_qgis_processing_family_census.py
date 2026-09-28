import unittest

from scripts.build_qgis_processing_family_census import census


class QgisProcessingFamilyCensusTests(unittest.TestCase):
    def test_counts_exact_subworkflow_and_transition_levels(self):
        rows = [
            {"asset_type": "processing_workflow", "source_sha256": "a" * 64, "processing_operator_ids": ["native:buffer", "native:clip", "native:dissolve"]},
            {"asset_type": "processing_workflow", "source_sha256": "b" * 64, "processing_operator_ids": ["native:buffer", "native:clip", "native:fixgeometries"]},
        ]
        families, summary = census(rows, l3_lookup={"native:buffer": "L1", "native:clip": "L2"})
        transition = next(item for item in families if item["family_level"] == "transition" and item["family_sequence_key"] == "native:buffer|native:clip")
        self.assertEqual(transition["support_count"], 2)
        self.assertEqual(transition["unique_full_workflow_count"], 2)
        self.assertEqual(transition["l3_status"], "fully_resolvable")
        self.assertEqual(summary["processing_workflow_rows"], 2)

    def test_unknown_contract_is_not_marked_valid(self):
        families, _ = census([{"asset_type": "processing_workflow", "source_sha256": "c" * 64, "processing_operator_ids": ["vendor:a", "vendor:b"]}])
        self.assertEqual(families[0]["io_status"], "unknown_operator_contract")
        self.assertEqual(families[0]["training_rows_emitted"], 0)

    def test_priority_penalizes_repeated_operator_family(self):
        rows = [{"asset_type": "processing_workflow", "source_sha256": str(i) * 64, "processing_operator_ids": ["native:buffer", "native:buffer"]} for i in range(1, 6)]
        families, _ = census(rows, l3_lookup={"native:buffer": "L1"})
        self.assertTrue(families[0]["repeated_operator"])
        self.assertLess(families[0]["quality_factor"], 1.0)


if __name__ == "__main__":
    unittest.main()
