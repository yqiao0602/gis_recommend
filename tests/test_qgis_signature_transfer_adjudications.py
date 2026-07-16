import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_qgis_signature_transfer_adjudications import (
    TransferAdjudicationError,
    validate_and_summarize,
)


class QgisSignatureTransferAdjudicationTests(unittest.TestCase):
    def _write_review(self, path):
        rows = [
            {
                "review_order": "1",
                "record_id": "record-1",
                "candidate_status": "candidate",
                "top1_operator_id": "qgis:buffer",
                "review_status": "pending",
                "training_admission": "not_a_training_artifact",
            },
            {
                "review_order": "2",
                "record_id": "record-2",
                "candidate_status": "abstain",
                "top1_operator_id": "",
                "review_status": "pending",
                "training_admission": "not_a_training_artifact",
            },
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def _write_decisions(self, path, review_path, decisions):
        review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for decision in decisions:
                payload = {
                    "schema_version": "qgis_signature_transfer_adjudication_v1",
                    "source_review_sha256": review_hash,
                    "batch_id": "batch_01",
                    "reviewer": "joint_user_codex",
                    "reviewed_on": "2026-07-16",
                    "review_basis": "Task semantics and predicted operator reviewed.",
                    "training_admission": "not_a_training_artifact",
                    **decision,
                }
                handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def test_validates_candidate_and_abstention_and_reports_partial_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review = root / "review.csv"
            decisions = root / "decisions.jsonl"
            summary_path = root / "summary.json"
            self._write_review(review)
            self._write_decisions(
                decisions,
                review,
                [
                    {
                        "review_order": 1,
                        "record_id": "record-1",
                        "candidate_status": "candidate",
                        "top1_operator_id": "qgis:buffer",
                        "top1_correct": True,
                        "abstention_correct": None,
                        "expected_operator_ids": ["qgis:buffer"],
                    },
                    {
                        "review_order": 2,
                        "record_id": "record-2",
                        "candidate_status": "abstain",
                        "top1_operator_id": "",
                        "top1_correct": None,
                        "abstention_correct": False,
                        "expected_operator_ids": ["qgis:centroids"],
                    },
                ],
            )

            summary = validate_and_summarize(review, decisions, summary_path)
            summary_bytes = summary_path.read_bytes()

        self.assertEqual(summary["decisions_validated"], 2)
        self.assertEqual(summary["candidate_review"]["top1_precision"], 1.0)
        self.assertEqual(summary["abstention_review"]["accuracy"], 0.0)
        self.assertEqual(summary["overall_review"]["accuracy"], 0.5)
        self.assertTrue(summary["human_review_complete"])
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertNotIn(b"\r\n", summary_bytes)

    def test_rejects_stale_row_binding_and_duplicate_decisions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review = root / "review.csv"
            decisions = root / "decisions.jsonl"
            self._write_review(review)
            base = {
                "review_order": 1,
                "record_id": "record-1",
                "candidate_status": "candidate",
                "top1_operator_id": "qgis:clip",
                "top1_correct": False,
                "abstention_correct": None,
                "expected_operator_ids": [],
            }
            self._write_decisions(decisions, review, [base])
            with self.assertRaisesRegex(TransferAdjudicationError, "top-1 operator mismatch"):
                validate_and_summarize(review, decisions)

            base["top1_operator_id"] = "qgis:buffer"
            self._write_decisions(decisions, review, [base, base])
            with self.assertRaisesRegex(TransferAdjudicationError, "duplicate decision"):
                validate_and_summarize(review, decisions)

    def test_rejects_status_specific_fields_and_inconsistent_expected_operator(self):
        invalid = [
            {
                "review_order": 1,
                "record_id": "record-1",
                "candidate_status": "candidate",
                "top1_operator_id": "qgis:buffer",
                "top1_correct": True,
                "abstention_correct": True,
                "expected_operator_ids": ["qgis:buffer"],
            },
            {
                "review_order": 1,
                "record_id": "record-1",
                "candidate_status": "candidate",
                "top1_operator_id": "qgis:buffer",
                "top1_correct": True,
                "abstention_correct": None,
                "expected_operator_ids": ["qgis:clip"],
            },
        ]
        for decision in invalid:
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                review = root / "review.csv"
                decisions = root / "decisions.jsonl"
                self._write_review(review)
                self._write_decisions(decisions, review, [decision])
                with self.assertRaises(TransferAdjudicationError):
                    validate_and_summarize(review, decisions)


if __name__ == "__main__":
    unittest.main()
