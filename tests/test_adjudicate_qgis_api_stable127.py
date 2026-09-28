from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_stable127 import freeze_stable127


def _stable126() -> dict:
    return {
        "proposed_taxonomy": "stable126",
        "taxonomy_admission": "granted",
        "existing_code_to_id": {f"L3_BASE_{index}": index for index in range(117)},
        "proposed_code_to_id_additions": {f"L3_ADDED_{index}": token for index, token in enumerate(range(117, 126))},
    }


def _proposal(*, support: int = 34) -> dict:
    return {
        "base_taxonomy": "stable126", "proposed_taxonomy": "stable127",
        "operator_id": "pyqgis:create_polyline_features_from_vertices",
        "candidate_units": 54, "normalized_body_authorities": support,
        "source_disjoint_calibration_units": 9, "source_disjoint_holdout_units": 9,
        "mapping_admission": "not_granted_taxonomy_proposal_only",
        "proposed_l3": {"code": "L3_01_01_06", "token_id": 126, "name": "Create Polyline Features from Vertices", "definition": "Constructs polylines.", "l1_code": "L1_01", "l1_name": "Data Management", "l2_code": "L2_01_01", "l2_name": "Dataset Creation"},
    }


class AdjudicateQgisApiStable127Test(unittest.TestCase):
    def test_appends_polyline_class_without_changing_old_tokens(self) -> None:
        authority, extension, summary = freeze_stable127(_stable126(), _proposal())

        self.assertEqual(authority[0]["l3_token_id"], 126)
        self.assertEqual(extension["proposed_code_to_id_additions"]["L3_01_01_06"], 126)
        self.assertTrue(extension["existing_token_ids_unchanged"])
        self.assertEqual(summary["content_token_count"], 127)

    def test_rejects_support_below_family_gate(self) -> None:
        with self.assertRaisesRegex(ValueError, "support"):
            freeze_stable127(_stable126(), _proposal(support=29))


if __name__ == "__main__":
    unittest.main()
