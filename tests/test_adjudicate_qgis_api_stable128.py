from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_stable128 import freeze_stable128


def _stable127() -> dict:
    return {
        "proposed_taxonomy": "stable127",
        "taxonomy_admission": "granted",
        "existing_code_to_id": {"L3_01_01_03": 0},
        "proposed_code_to_id_additions": {f"L3_X_{index}": index for index in range(1, 127)},
    }


def _proposal() -> dict:
    return {
        "base_taxonomy": "stable127", "proposed_taxonomy": "stable128",
        "operator_id": "pyqgis:create_features_from_wkt_geometry",
        "candidate_units": 30, "normalized_body_authorities": 30,
        "source_disjoint_calibration_units": 1, "source_disjoint_holdout_units": 1,
        "mapping_admission": "not_granted_taxonomy_proposal_only",
        "proposed_l3": {"code": "L3_01_01_07", "token_id": 127, "name": "Create Features from WKT Geometry", "definition": "x", "l1_code": "L1_01", "l1_name": "Data Management", "l2_code": "L2_01_01", "l2_name": "Dataset Creation"},
    }


class AdjudicateQgisApiStable128Test(unittest.TestCase):
    def test_freezes_contiguous_extension(self) -> None:
        authority, extension, summary = freeze_stable128(_stable127(), _proposal())
        self.assertEqual(authority[0]["l3_token_id"], 127)
        self.assertEqual(extension["proposed_class_count"], 128)
        self.assertEqual(summary["taxonomy_admission"], "granted")

    def test_rejects_low_support(self) -> None:
        proposal = _proposal()
        proposal["normalized_body_authorities"] = 29
        with self.assertRaisesRegex(ValueError, "below 30"):
            freeze_stable128(_stable127(), proposal)


if __name__ == "__main__":
    unittest.main()
