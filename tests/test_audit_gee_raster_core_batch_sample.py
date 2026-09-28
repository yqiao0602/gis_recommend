from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
AUDIT_SAMPLE = BATCH_PACKAGE_DIR / "audit_sample_50.jsonl"
TMP_ROOT = ROOT / ".tmp_test_audit_gee_batch_sample"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class AuditGeeRasterCoreBatchSampleTests(unittest.TestCase):
    def test_precheck_prioritizes_risky_audit_rows_without_emitting_training(self) -> None:
        audit = importlib.import_module("scripts.audit_gee_raster_core_batch_sample")

        result = audit.build_audit_precheck(audit_sample_path=AUDIT_SAMPLE)

        self.assertEqual(len(result.rows), 50)
        self.assertEqual(result.summary["counts"]["input_rows"], 50)
        self.assertEqual(result.summary["counts"]["precheck_rows"], 50)
        self.assertEqual(result.summary["decision"]["training_rows_emitted"], 0)
        self.assertFalse(result.summary["decision"]["mutated_training_package"])
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertEqual(result.summary["decision"]["review_role"], "sampling_audit_rule_calibration")

        rank1 = next(row for row in result.rows if row["audit_rank"] == 1)
        self.assertIn("classification_text_without_classifier_operator", rank1["risk_flags"])
        self.assertIn("vector_or_training_label_text_without_vector_sampling_operator", rank1["risk_flags"])
        self.assertEqual(rank1["source_evidence_status"], "server_path_hash_only")
        self.assertTrue(rank1["requires_source_lookup_for_final_adjudication"])

        self.assertTrue(any(row["risk_level"] == "high" for row in result.rows))
        self.assertTrue(all(row["precheck_status"] == "pending_human_sampling_audit" for row in result.rows))
        for row in result.rows:
            for field in audit.HUMAN_FIELDS:
                self.assertEqual(row[field], "")
            self.assertEqual(len(row["operator_sequence"]), len(row["l3_code_sequence"]))

        review_priorities = [row["review_priority"] for row in result.rows]
        self.assertEqual(review_priorities, list(range(1, 51)))
        self.assertEqual(
            result.summary["counts"]["requires_source_lookup_rows"],
            50,
        )
        self.assertGreater(
            result.summary["risk_flag_counts"].get("classification_text_without_classifier_operator", 0),
            0,
        )

    def test_cli_writes_precheck_packet_without_mutating_sample(self) -> None:
        audit = importlib.import_module("scripts.audit_gee_raster_core_batch_sample")
        output_dir = _workspace_dir("cli")
        before = hashlib.sha256(AUDIT_SAMPLE.read_bytes()).hexdigest()
        try:
            outputs = audit.main(
                [
                    "--audit-sample",
                    str(AUDIT_SAMPLE),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)
            self.assertEqual(len(_jsonl(outputs["jsonl"])), 50)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 50)
            self.assertEqual(_json(outputs["summary"])["counts"]["precheck_rows"], 50)
            self.assertIn(outputs["jsonl"].name, _json(outputs["hash_ledger"])["artifacts"])
        finally:
            self.assertEqual(hashlib.sha256(AUDIT_SAMPLE.read_bytes()).hexdigest(), before)
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
