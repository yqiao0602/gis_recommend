from __future__ import annotations

import csv
import importlib
import json
import shutil
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
P4_GATE = REPORT_DIR / "gee_p4_l3_canonicalization_gate_24_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p4_export"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP4L3ReadyTrainOnlyExportTests(unittest.TestCase):
    def test_exports_only_l3_ready_rows_as_schema_valid_train_only_candidates(self) -> None:
        export = importlib.import_module("scripts.export_gee_p4_l3_ready_train_only")
        result = export.build_p4_l3_ready_train_only_export(p4_gate_jsonl_path=P4_GATE)

        self.assertEqual(result.summary["counts"]["input_gate_rows"], 24)
        self.assertEqual(result.summary["counts"]["exported_rows"], 18)
        self.assertEqual(result.summary["counts"]["source_status_counts"]["l3_ready"], 18)
        self.assertEqual(result.summary["counts"]["source_status_counts"]["needs_canonicalization_rules"], 6)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_train_only_export_gate_passed",
        )
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["training_run_started"])

        exported_ids = {row["review_id"] for row in result.rows}
        self.assertNotIn("gee_raster_core_review_027", exported_ids)
        self.assertIn("gee_raster_core_review_004", exported_ids)
        self.assertIn("gee_raster_core_review_050", exported_ids)

        for row in result.rows:
            self.assertEqual(row["schema"], "gis_recommend.gee_raster_core_train_row.v1")
            self.assertEqual(row["source_platform"], "GEE")
            self.assertEqual(row["target_platform"], "L3")
            self.assertEqual(row["training_scope"], "core_subworkflow")
            self.assertEqual(row["admission_tier"], "gee_core_p4_reviewed")
            self.assertEqual(row["review_split"], "train")
            self.assertLessEqual(row["sample_weight"], 0.5)
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(len(row["operator_sequence"]), len(row["l3_sequence"]))
            self.assertTrue(row["operator_sequence"])
            self.assertTrue(row["l3_sequence"])

    def test_cli_writes_export_artifacts_without_mutating_gate(self) -> None:
        export = importlib.import_module("scripts.export_gee_p4_l3_ready_train_only")
        tmp = _workspace_dir("case1")
        try:
            before = P4_GATE.read_text(encoding="utf-8")
            outputs = export.main(
                [
                    "--p4-gate",
                    str(P4_GATE),
                    "--output-dir",
                    str(tmp),
                ]
            )

            self.assertEqual(P4_GATE.read_text(encoding="utf-8"), before)
            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 18)
            jsonl_rows = [
                json.loads(line)
                for line in outputs["jsonl"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(jsonl_rows), 18)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
