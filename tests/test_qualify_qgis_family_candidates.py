import json
import tempfile
import unittest
from pathlib import Path

from scripts.qualify_qgis_family_candidates import qualify


class QgisFamilyQualificationTests(unittest.TestCase):
    def test_existing_l3_and_io_are_proposals_only(self):
        row = {"candidate_id": "c", "family_sequence": ["native:clip", "qgis:multiparttosingleparts"], "source_verified": True}
        qualified, summary = qualify([row], {"clip": "L3_CLIP", "multipart to singleparts": "L3_MULTI"})
        result = qualified[0]
        self.assertEqual(result["proposed_l3_sequence"], ["L3_CLIP", "L3_MULTI"])
        self.assertEqual(result["provider_io_status"], "deterministic_vector_chain_contract")
        self.assertEqual(result["qualification_status"], "ready_for_independent_semantic_review")
        self.assertEqual(result["training_rows_emitted"], 0)
        self.assertEqual(summary["cross_pool_dedup_status"], "pending_current_corpus_replay")

    def test_unknown_operator_is_deferred(self):
        qualified, _ = qualify([{"family_sequence": ["native:unknown"]}], {})
        self.assertEqual(qualified[0]["qualification_status"], "deferred_mapping_or_contract")

    def test_dissolve_multipart_family_has_vector_contract(self):
        qualified, _ = qualify(
            [{"family_sequence": ["native:dissolve", "native:multiparttosingleparts"]}],
            {"dissolve": "L3_DISSOLVE", "multipart to singleparts": "L3_MULTI"},
        )
        result = qualified[0]
        self.assertEqual(result["proposed_l3_sequence"], ["L3_DISSOLVE", "L3_MULTI"])
        self.assertEqual(result["provider_io_status"], "deterministic_vector_chain_contract")
        self.assertEqual(result["qualification_status"], "ready_for_independent_semantic_review")

    def test_buffer_clip_family_has_vector_contract(self):
        qualified, _ = qualify(
            [{"family_sequence": ["native:buffer", "native:clip"]}],
            {"buffer": "L3_BUFFER", "clip": "L3_CLIP"},
        )
        assert qualified[0]["qualification_status"] == "ready_for_independent_semantic_review"


if __name__ == "__main__":
    unittest.main()
