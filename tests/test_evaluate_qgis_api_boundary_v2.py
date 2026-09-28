from __future__ import annotations

import unittest

from scripts.evaluate_qgis_api_boundary_v2 import evaluate


def _review(candidate_id: str, patterns: list[str]) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "source_authority_key": f"authority-{candidate_id}",
        "source_sha256": f"sha-{candidate_id}",
        "pattern_names": patterns,
        "review_strata": ["steps_2"],
        "training_row_emitted": False,
    }


def _proposal(candidate_id: str, decision: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "proposal_decision": decision,
        "proposal_only": True,
        "human_adjudication": "not_granted",
        "training_row_emitted": False,
    }


class EvaluateQgisApiBoundaryV2Test(unittest.TestCase):
    def test_precision_excludes_defer_but_defer_blocks_promotion(self) -> None:
        reviews = [
            _review("a", ["feature_geometry", "sink_output"]),
            _review("b", ["feature_geometry", "sink_output"]),
            _review("c", ["field_attribute_edit", "sink_output"]),
        ]
        proposals = [
            _proposal("a", "true_positive"),
            _proposal("b", "false_positive"),
            _proposal("c", "defer"),
        ]

        result = evaluate(
            reviews,
            proposals,
            minimum_precision=0.0,
            minimum_wilson_lower=0.0,
            minimum_family_rows=1,
        )

        self.assertEqual(result["overall"]["adjudicated_rows"], 2)
        self.assertEqual(result["overall"]["precision"], 0.5)
        self.assertEqual(result["overall"]["defer_rows"], 1)
        self.assertFalse(result["promotion_eligible"])

    def test_identity_or_proposal_contract_mismatch_fails_closed(self) -> None:
        reviews = [_review("a", ["feature_geometry", "sink_output"])]
        proposal = _proposal("a", "true_positive")
        proposal["proposal_only"] = False

        with self.assertRaisesRegex(ValueError, "proposal_only"):
            evaluate(reviews, [proposal])


if __name__ == "__main__":
    unittest.main()
