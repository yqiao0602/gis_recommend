from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_raster_calculator_review import (
    adjudicate,
    build_summary,
)


def _row(split: str, identity: str) -> dict:
    return {
        "review_split": split,
        "family_id": "raster_calculator",
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "mapping_status": "exact_stable125",
        "candidate_l3_sequence": ["L3_03_03_A"],
        "constructor_signature": "without_output_crs",
        "expression_fact": {"status": "literal", "source": "'A@1 + B@1'"},
        "source_snippet": "calc = QgsRasterCalculator(...)\ncalc.processCalculation()",
        "source_sha256": f"source-{identity}",
        "source_authority_key": f"body-{identity}",
        "unit_id": identity,
    }


class RasterCalculatorReviewTest(unittest.TestCase):
    def test_adjudicates_hash_bound_complete_macro(self) -> None:
        reviewed = adjudicate([_row("calibration", "a")], "calibration")

        self.assertEqual(
            reviewed[0]["technical_boundary_decision"],
            "accept_complete_local_macro",
        )
        self.assertFalse(reviewed[0]["training_row_emitted"])

    def test_rejects_unreviewable_expression_provenance(self) -> None:
        row = _row("holdout", "b")
        row["expression_fact"] = {"status": "dynamic_subscript", "source": "d['formula']"}

        with self.assertRaisesRegex(ValueError, "expression_fidelity_not_reviewable"):
            adjudicate([row], "holdout")

    def test_summary_requires_source_and_body_disjoint_splits(self) -> None:
        calibration = adjudicate([_row("calibration", "a")], "calibration")
        holdout = adjudicate([_row("holdout", "b")], "holdout")

        summary = build_summary(calibration, holdout)

        self.assertEqual(summary["observed_false_positive_count"], 0)
        self.assertEqual(summary["observed_chain_truncation_count"], 0)
        self.assertEqual(
            summary["family_rule_promotion"],
            "granted_for_raster_calculator_local_terminal_macro",
        )


if __name__ == "__main__":
    unittest.main()
