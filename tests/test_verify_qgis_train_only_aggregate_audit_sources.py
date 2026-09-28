from __future__ import annotations

import hashlib
import unittest

from scripts.verify_qgis_train_only_aggregate_audit_sources import (
    verify_audit_sources,
    verify_source_row,
)


def _row(payload: bytes) -> dict:
    return {
        "sample_id": "sample-1",
        "aggregate_source_pool": "pool-1",
        "audit_split": "calibration",
        "audit_risk_stratum": "multistep_chain_2_4",
        "source_path": "/source/a.py",
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "source_span": {
            "segments": [
                {"line_start": 1, "line_end": 1},
                {"line_start": 3, "line_end": 3},
            ]
        },
        "evidence_snippet": "1 | value = 1\n2 | \n3 | print(value)",
    }


class VerifyQgisAggregateAuditSourcesTest(unittest.TestCase):
    def test_verifies_hash_ast_spans_and_numbered_evidence(self) -> None:
        payload = b"value = 1\n\nprint(value)\n"

        result = verify_source_row(_row(payload), payload)

        self.assertEqual(result["source_replay_status"], "verified")
        self.assertTrue(result["ast_parse_ok"])
        self.assertTrue(result["source_span_ok"])
        self.assertTrue(result["evidence_snippet_ok"])
        self.assertEqual(result["evidence_lines_checked"], 3)

    def test_fails_closed_on_ast_span_and_evidence_errors(self) -> None:
        expected = b"value = 1\n"
        actual = b"value = (\n"
        row = _row(expected)
        row["source_span"] = {"line_start": 1, "line_end": 20}
        row["evidence_snippet"] = "1 | value = 1"

        result = verify_source_row(row, actual)

        self.assertEqual(result["source_replay_status"], "failed_closed")
        self.assertFalse(result["sha256_match"])
        self.assertFalse(result["ast_parse_ok"])
        self.assertFalse(result["source_span_ok"])
        self.assertFalse(result["evidence_snippet_ok"])
        self.assertGreaterEqual(
            {error["reason"] for error in result["errors"]},
            {
                "source_sha256_mismatch",
                "source_ast_parse_failed",
                "source_span_invalid",
                "evidence_source_mismatch",
            },
        )

    def test_summary_preserves_fail_closed_admission(self) -> None:
        payload = b"value = 1\n\nprint(value)\n"
        first = _row(payload)
        second = {
            **_row(payload),
            "sample_id": "sample-2",
            "source_path": "/missing.py",
        }

        _, summary = verify_audit_sources(
            [first, second], lambda path: payload if path == "/source/a.py" else None
        )

        self.assertEqual(summary["verified_rows"], 1)
        self.assertEqual(summary["failed_closed_rows"], 1)
        self.assertEqual(summary["source_replay_gate"], "failed_closed")
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertEqual(summary["production_merge"], "not_granted")

    def test_accepts_exact_raw_segment_and_numbered_ellipsis_separator(self) -> None:
        payload = b"value = 1\n\nprint(value)\n"
        raw_row = _row(payload)
        raw_row["evidence_snippet"] = "value = 1\n\nprint(value)"
        segmented_row = _row(payload)
        segmented_row["evidence_snippet"] = "1 | value = 1\n...\n3 | print(value)"

        raw_result = verify_source_row(raw_row, payload)
        segmented_result = verify_source_row(segmented_row, payload)

        self.assertEqual(raw_result["source_replay_status"], "verified")
        self.assertEqual(
            raw_result["evidence_verification_mode"], "exact_source_segment"
        )
        self.assertEqual(segmented_result["source_replay_status"], "verified")
        self.assertEqual(
            segmented_result["evidence_verification_mode"], "numbered_source_lines"
        )


if __name__ == "__main__":
    unittest.main()
