import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_qgis_core_signature_adjudications import (
    AdjudicationError,
    validate_and_summarize,
)


class QgisCoreSignatureAdjudicationTests(unittest.TestCase):
    def _write_review(self, path):
        rows = [
            {
                "record_id": "script_1",
                "class_name": "Buffer",
                "trace_sha256": "a" * 64,
                "exact_candidates_json": json.dumps(
                    [{"operator_id": "gdal:buffer", "official_name": "Buffer"}]
                ),
                "ranked_candidates_json": json.dumps(
                    [
                        {"operator_id": "gdal:buffer", "official_name": "Buffer"},
                        {"operator_id": "native:buffer", "official_name": "Buffer"},
                    ]
                ),
                "review_status": "pending",
                "training_admission": "forbidden_until_reviewed",
            },
            {
                "record_id": "script_2",
                "class_name": "Helper",
                "trace_sha256": "b" * 64,
                "exact_candidates_json": "[]",
                "ranked_candidates_json": "[]",
                "review_status": "pending",
                "training_admission": "forbidden_until_reviewed",
            },
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def _review_hash(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_decisions(self, path, review_path, decisions):
        review_hash = self._review_hash(review_path)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for decision in decisions:
                payload = {
                    "schema_version": "qgis_core_signature_adjudication_v1",
                    "batch_id": "batch_01",
                    "source_review_sha256": review_hash,
                    "reviewer": "joint_user_codex",
                    "review_basis": "Class, provider, and parameter schema reviewed.",
                    **decision,
                }
                handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def test_validates_accept_and_non_anchor_decisions_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path = root / "review.csv"
            decisions_path = root / "decisions.jsonl"
            summary_path = root / "summary.json"
            self._write_review(review_path)
            self._write_decisions(
                decisions_path,
                review_path,
                [
                    {
                        "record_id": "script_1",
                        "class_name": "Buffer",
                        "trace_sha256": "a" * 64,
                        "decision": "accept",
                        "accepted_operator_id": "gdal:buffer",
                    },
                    {
                        "record_id": "script_2",
                        "class_name": "Helper",
                        "trace_sha256": "b" * 64,
                        "decision": "reject_non_anchor",
                        "accepted_operator_id": "",
                    },
                ],
            )

            summary = validate_and_summarize(review_path, decisions_path, summary_path)
            persisted = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["review_rows_total"], 2)
        self.assertEqual(summary["decisions_validated"], 2)
        self.assertEqual(summary["decision_counts"], {"accept": 1, "reject_non_anchor": 1})
        self.assertEqual(summary["remaining_review_rows"], 0)
        self.assertEqual(summary["accepted_anchor_candidates"], 1)
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertEqual(persisted, summary)

    def test_rejects_unknown_operator_and_trace_hash_mismatch(self):
        cases = [
            {
                "record_id": "script_1",
                "class_name": "Buffer",
                "trace_sha256": "a" * 64,
                "decision": "accept",
                "accepted_operator_id": "invented:buffer",
            },
            {
                "record_id": "script_1",
                "class_name": "Buffer",
                "trace_sha256": "c" * 64,
                "decision": "accept",
                "accepted_operator_id": "gdal:buffer",
            },
        ]
        for decision in cases:
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                review_path = root / "review.csv"
                decisions_path = root / "decisions.jsonl"
                self._write_review(review_path)
                self._write_decisions(decisions_path, review_path, [decision])

                with self.assertRaises(AdjudicationError):
                    validate_and_summarize(review_path, decisions_path)

    def test_rejects_duplicate_decisions_and_stale_review_hash(self):
        decision = {
            "record_id": "script_1",
            "class_name": "Buffer",
            "trace_sha256": "a" * 64,
            "decision": "accept",
            "accepted_operator_id": "gdal:buffer",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path = root / "review.csv"
            decisions_path = root / "decisions.jsonl"
            self._write_review(review_path)
            self._write_decisions(decisions_path, review_path, [decision, decision])
            with self.assertRaisesRegex(AdjudicationError, "duplicate decision"):
                validate_and_summarize(review_path, decisions_path)

            self._write_decisions(decisions_path, review_path, [decision])
            review_path.write_text(review_path.read_text(encoding="utf-8-sig") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AdjudicationError, "source review hash"):
                validate_and_summarize(review_path, decisions_path)


if __name__ == "__main__":
    unittest.main()
