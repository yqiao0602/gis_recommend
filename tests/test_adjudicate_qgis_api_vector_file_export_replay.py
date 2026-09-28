from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_vector_file_export_replay import adjudicate_rows


def _row(split: str, row_id: str, status: str) -> dict:
    complete = status == "verified_complete_vector_file_export"
    return {
        "review_split": split,
        "record_id": row_id,
        "source_sha256": row_id.ljust(64, "0"),
        "normalized_source_body_sha256": row_id.ljust(64, "1"),
        "source_replay_verification": "verified_sha256",
        "proposed_l3_code": "L3_07_04_01",
        "family_boundary_status": "strict_review_eligible",
        "source_replay_status": status,
        "source_region": f"{row_id}:1-2",
        "source_replay_snippet": "1 | writer()",
        "writer_evidence": (
            [
                {
                    "writer_method": "writeasvectorformatv3",
                    "input_layer_expression": "layer",
                    "output_path_expression": "path",
                    "control_flow": [],
                }
            ]
            if complete
            else [{"control_flow": ["If"]}]
        ),
    }


class AdjudicateQgisApiVectorFileExportReplayTest(unittest.TestCase):
    def test_passes_source_disjoint_complete_and_deferred_rows(self) -> None:
        rows = [
            _row("calibration", "a", "verified_complete_vector_file_export"),
            _row("holdout", "b", "deferred_control_flow_writer"),
        ]

        adjudicated, summary = adjudicate_rows(
            rows,
            expected_rows=2,
            expected_per_split=1,
        )

        self.assertEqual(adjudicated[0]["boundary_adjudication"], "accept_local_writer_macro")
        self.assertEqual(adjudicated[1]["boundary_adjudication"], "defer_fail_closed")
        self.assertEqual(summary["calibration_gate"], "passed")
        self.assertTrue(summary["full_pool_replay_granted"])
        self.assertEqual(summary["silent_fallback_count"], 0)

    def test_fails_closed_when_complete_evidence_is_truncated(self) -> None:
        rows = [
            _row("calibration", "a", "verified_complete_vector_file_export"),
            _row("holdout", "b", "deferred_control_flow_writer"),
        ]
        rows[0]["writer_evidence"][0]["output_path_expression"] = ""

        with self.assertRaisesRegex(ValueError, "missing output path"):
            adjudicate_rows(rows, expected_rows=2, expected_per_split=1)

    def test_rejects_unknown_status_instead_of_falling_back(self) -> None:
        rows = [
            _row("calibration", "a", "verified_complete_vector_file_export"),
            _row("holdout", "b", "mystery_status"),
        ]

        with self.assertRaisesRegex(ValueError, "unreviewed replay status"):
            adjudicate_rows(rows, expected_rows=2, expected_per_split=1)


if __name__ == "__main__":
    unittest.main()
