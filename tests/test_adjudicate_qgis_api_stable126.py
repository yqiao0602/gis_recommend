from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_stable126 import freeze_stable126


def _stable125() -> dict:
    return {
        "proposed_taxonomy": "stable125",
        "taxonomy_admission": "granted",
        "existing_code_to_id": {f"L3_BASE_{index}": index for index in range(117)},
        "proposed_code_to_id_additions": {
            f"L3_ADDED_{index}": token for index, token in enumerate(range(117, 125))
        },
    }


def _proposal(*, support: int = 54) -> dict:
    return {
        "base_taxonomy": "stable125",
        "proposed_taxonomy": "stable126",
        "operator_id": "pyqgis:create_point_features_from_coordinates",
        "candidate_units": 55,
        "normalized_body_authorities": support,
        "calibration_units": 22,
        "holdout_units": 33,
        "mapping_admission": "not_granted_taxonomy_proposal_only",
        "proposed_l3": {
            "code": "L3_01_01_05",
            "token_id": 125,
            "name": "Create Point Features from Coordinates",
            "definition": "Constructs point feature geometry from a coordinate pair.",
            "l1_code": "L1_01",
            "l1_name": "Data Management",
            "l2_code": "L2_01_01",
            "l2_name": "Dataset Creation",
        },
    }


class AdjudicateQgisApiStable126Test(unittest.TestCase):
    def test_appends_point_feature_class_without_changing_old_tokens(self) -> None:
        authority, extension, summary = freeze_stable126(_stable125(), _proposal())

        self.assertEqual(authority[0]["l3_token_id"], 125)
        self.assertEqual(
            extension["proposed_code_to_id_additions"]["L3_01_01_05"], 125
        )
        self.assertTrue(extension["existing_token_ids_unchanged"])
        self.assertEqual(summary["content_token_count"], 126)

    def test_rejects_support_below_family_gate(self) -> None:
        with self.assertRaisesRegex(ValueError, "support"):
            freeze_stable126(_stable125(), _proposal(support=29))


if __name__ == "__main__":
    unittest.main()
