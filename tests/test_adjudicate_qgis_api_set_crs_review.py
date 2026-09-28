from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_set_crs_review import adjudicate, build_summary


def _row(split: str, key: str) -> dict:
    return {
        "review_split": split,
        "family_rule_id": "qgis-api-local-layer-set-crs-metadata-v1",
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "mapping_status": "exact_stable125",
        "candidate_l3_sequence": ["L3_01_10_02"],
        "receiver_constructor": "QgsVectorLayer",
        "source_snippet": "layer = QgsVectorLayer(...)\nlayer.setCrs(crs)",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"body-{key}",
        "unit_id": key,
    }


class AdjudicateQgisApiSetCrsReviewTest(unittest.TestCase):
    def test_adjudicates_complete_local_layer_macro(self) -> None:
        reviewed = adjudicate([_row("calibration", "a")], "calibration")

        self.assertEqual(
            reviewed[0]["technical_boundary_decision"],
            "accept_local_layer_set_crs_macro",
        )
        self.assertEqual(reviewed[0]["whole_function_semantics_admission"], "not_granted")

    def test_rejects_non_layer_receiver(self) -> None:
        row = _row("holdout", "b")
        row["receiver_constructor"] = "QgsProject"

        with self.assertRaisesRegex(ValueError, "receiver_not_qgis_layer"):
            adjudicate([row], "holdout")

    def test_summary_requires_source_disjoint_splits(self) -> None:
        calibration = adjudicate([_row("calibration", "a")], "calibration")
        holdout = adjudicate([_row("holdout", "b")], "holdout")

        summary = build_summary(calibration, holdout)

        self.assertEqual(summary["observed_false_positive_count"], 0)
        self.assertEqual(summary["observed_chain_truncation_count"], 0)


if __name__ == "__main__":
    unittest.main()
