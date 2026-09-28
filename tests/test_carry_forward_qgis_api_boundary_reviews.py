from __future__ import annotations

import unittest

from scripts.carry_forward_qgis_api_boundary_reviews import carry_forward


class CarryForwardQgisApiBoundaryReviewsTest(unittest.TestCase):
    def test_only_exact_candidate_and_source_identity_are_carried(self) -> None:
        old_reviews = [
            {"candidate_id": "same", "source_authority_key": "auth", "source_sha256": "sha"},
            {"candidate_id": "changed", "source_authority_key": "auth-2", "source_sha256": "sha-2"},
        ]
        old_proposals = [
            {"candidate_id": "same", "proposal_decision": "true_positive", "proposal_only": True, "human_adjudication": "not_granted", "training_row_emitted": False},
            {"candidate_id": "changed", "proposal_decision": "true_positive", "proposal_only": True, "human_adjudication": "not_granted", "training_row_emitted": False},
        ]
        new_reviews = [
            {"candidate_id": "same", "source_authority_key": "auth", "source_sha256": "sha", "training_row_emitted": False},
            {"candidate_id": "changed", "source_authority_key": "auth-2", "source_sha256": "different", "training_row_emitted": False},
        ]

        carried, pending, summary = carry_forward(new_reviews, old_reviews, old_proposals)

        self.assertEqual([row["candidate_id"] for row in carried], ["same"])
        self.assertEqual([row["candidate_id"] for row in pending], ["changed"])
        self.assertEqual(summary["carried_rows"], 1)
        self.assertTrue(all(row["training_row_emitted"] is False for row in carried))


if __name__ == "__main__":
    unittest.main()
