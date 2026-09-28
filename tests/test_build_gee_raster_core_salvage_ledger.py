from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_50 = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24/adjudicated_review_50_v1.csv"
)
TMP_ROOT = ROOT / ".tmp_test_gee_salvage"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeRasterCoreSalvageLedgerTests(unittest.TestCase):
    def test_salvage_ledger_classifies_real_review_50_rows(self) -> None:
        salvage = importlib.import_module("scripts.build_gee_raster_core_salvage_ledger")
        tmp = _workspace_dir("case1")
        try:
            output_dir = tmp / "out"
            result = salvage.build_salvage_ledger(
                review_csv_path=REVIEW_50,
                output_dir=output_dir,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        self.assertEqual(result.report["counts"]["rows"], 50)
        self.assertEqual(
            result.report["salvage_buckets"],
            {
                "accept_core_now": 9,
                "rewrite_description_then_train": 8,
                "extractor_repair_required": 28,
                "taxonomy_or_mapping_gap": 3,
                "reject": 2,
            },
        )
        by_id = {row["review_id"]: row for row in result.rows}
        self.assertEqual(by_id["gee_raster_core_review_032"]["salvage_bucket"], "rewrite_description_then_train")
        self.assertEqual(by_id["gee_raster_core_review_013"]["salvage_bucket"], "taxonomy_or_mapping_gap")
        self.assertEqual(by_id["gee_raster_core_review_028"]["salvage_bucket"], "reject")
        self.assertEqual(by_id["gee_raster_core_review_006"]["salvage_bucket"], "extractor_repair_required")
        self.assertEqual(by_id["gee_raster_core_review_025"]["salvage_bucket"], "rewrite_description_then_train")
        self.assertFalse(result.report["decision"]["validation_eligible"])
        self.assertFalse(result.report["decision"]["test_eligible"])
        self.assertEqual(result.report["decision"]["training_admission"], "not_granted")

    def test_cli_writes_ledger_and_keeps_input_unchanged(self) -> None:
        salvage = importlib.import_module("scripts.build_gee_raster_core_salvage_ledger")
        tmp = _workspace_dir("case2")
        try:
            output_dir = tmp
            before = REVIEW_50.read_text(encoding="utf-8")
            outputs = salvage.main(
                [
                    "--review-csv",
                    str(REVIEW_50),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(REVIEW_50.read_text(encoding="utf-8"), before)
            self.assertTrue(outputs["csv"].exists())
            self.assertTrue(outputs["jsonl"].exists())
            self.assertTrue(outputs["report_json"].exists())
            self.assertTrue(outputs["report_md"].exists())
            self.assertTrue(outputs["hash_ledger"].exists())
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 50)
            self.assertIn("salvage_bucket", rows[0])
            payload = json.loads(outputs["report_json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "gis_recommend.gee_raster_core_salvage_ledger.v1")
            self.assertIn("reject", payload["salvage_buckets"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
