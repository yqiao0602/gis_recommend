from __future__ import annotations

import hashlib
import unittest

from scripts.adjudicate_qgis_api_geometry_difference_review import (
    adjudicate,
    build_summary,
)


def _row(authority: str, source: str, split: str, *, complete: bool) -> dict:
    snippet = "1 | left.difference(right)\n2 | output.setGeometry(result)\n3 | sink.addFeature(output)"
    return {
        "candidate_id": f"{authority}-{split}",
        "contract_rule_id": "qgis-api-geometry-difference-local-macro-v1",
        "family_id": "geometry_difference",
        "review_split": split,
        "source_sha256": source,
        "source_authority_key": authority,
        "source_verification": "verified_sha256",
        "family_rule_promotion": "not_granted_support_below_30",
        "macro_status": "complete" if complete else "deferred",
        "deferred_reason": (
            "" if complete else "downstream_geometry_transform_or_mutation"
        ),
        "mapping_status": (
            "exact_stable125_existing_l3" if complete else "not_granted"
        ),
        "candidate_l3_sequence": ["L3_02_02_04"] if complete else [],
        "difference_call": "left.difference",
        "difference_call_line": 1,
        "setgeometry_call": "output.setGeometry",
        "setgeometry_call_line": 2,
        "sink_call": "sink.addFeature",
        "sink_call_line": 3,
        "receiver_operand_fact": {"status": "verified_geometry_accessor"},
        "argument_operand_fact": {"status": "verified_geometry_accessor"},
        "evidence_snippet": snippet,
        "evidence_sha256": hashlib.sha256(snippet.encode()).hexdigest(),
    }


class AdjudicateGeometryDifferenceReviewTest(unittest.TestCase):
    def test_accepts_complete_and_preserves_deferred_rows(self) -> None:
        accepted = adjudicate([_row("a", "s1", "calibration", complete=True)], "calibration")
        deferred = adjudicate([_row("b", "s2", "holdout", complete=False)], "holdout")

        self.assertTrue(
            accepted[0]["technical_boundary_decision"].startswith("accept_")
        )
        self.assertTrue(
            deferred[0]["technical_boundary_decision"].startswith("defer_")
        )
        summary = build_summary([*accepted, *deferred])
        self.assertEqual(summary["accepted_boundary_rows"], 1)
        self.assertEqual(summary["deferred_boundary_rows"], 1)

    def test_rejects_source_overlap(self) -> None:
        calibration = adjudicate(
            [_row("a", "shared", "calibration", complete=True)], "calibration"
        )
        holdout = adjudicate(
            [_row("b", "shared", "holdout", complete=True)], "holdout"
        )

        with self.assertRaisesRegex(ValueError, "source SHA leakage"):
            build_summary([*calibration, *holdout])


if __name__ == "__main__":
    unittest.main()
