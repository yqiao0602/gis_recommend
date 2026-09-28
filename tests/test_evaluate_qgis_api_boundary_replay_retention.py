from __future__ import annotations

import unittest

from scripts.evaluate_qgis_api_boundary_replay_retention import evaluate_retention


def _review(candidate_id: str, authority: str, line: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "source_authority_key": authority,
        "steps": [
            {
                "line_start": line,
                "call_name": "sink.addFeature",
                "terminal_evidence": True,
            }
        ],
    }


class EvaluateQgisApiBoundaryReplayRetentionTest(unittest.TestCase):
    def test_reports_exact_revised_lost_and_false_positive_suppression(self) -> None:
        reviews = [
            _review("exact", "source:1", 10),
            _review("revised", "source:2", 20),
            _review("lost", "source:3", 30),
            _review("false-positive", "source:4", 40),
        ]
        proposals = [
            {"candidate_id": "exact", "proposal_decision": "true_positive"},
            {"candidate_id": "revised", "proposal_decision": "true_positive"},
            {"candidate_id": "lost", "proposal_decision": "true_positive"},
            {
                "candidate_id": "false-positive",
                "proposal_decision": "false_positive",
            },
        ]
        candidates = [
            _review("exact", "source:1", 10),
            _review("new-revised-id", "source:2", 20),
        ]

        result = evaluate_retention(reviews, proposals, candidates)

        self.assertEqual(
            result["true_positive_retention"],
            {
                "reviewed": 3,
                "exact_candidate_id": 1,
                "revised_same_terminal": 1,
                "lost_terminal": 1,
                "retained_rate": 2 / 3,
            },
        )
        self.assertEqual(
            result["false_positive_suppression"],
            {"reviewed": 1, "suppressed": 1, "still_emitted": 0},
        )
        self.assertEqual(result["lost_true_positive_ids"], ["lost"])
        self.assertEqual(result["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
