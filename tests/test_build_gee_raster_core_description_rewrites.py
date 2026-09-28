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
SALVAGE_50 = REPORT_DIR / "gee_salvage_50_v1.csv"
SOURCE_SNIPPETS = REPORT_DIR / "source_evidence_snippets.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p2_rewrite"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeRasterCoreDescriptionRewriteTests(unittest.TestCase):
    def test_builds_p1_valid_rewrites_for_real_rewrite_bucket(self) -> None:
        rewrite = importlib.import_module("scripts.build_gee_raster_core_description_rewrites")
        result = rewrite.build_description_rewrites(
            salvage_csv_path=SALVAGE_50,
            source_snippets_path=SOURCE_SNIPPETS,
        )

        self.assertEqual(result.report["counts"]["rewrite_rows"], 8)
        self.assertEqual(result.report["counts"]["p1_valid_rows"], 8)
        self.assertFalse(result.report["decision"]["validation_eligible"])
        self.assertFalse(result.report["decision"]["test_eligible"])
        self.assertEqual(
            result.report["decision"]["training_admission"],
            "not_granted_pending_human_text_fidelity_review",
        )

        by_id = {row["review_id"]: row for row in result.rows}
        self.assertEqual(
            set(by_id),
            {
                "gee_raster_core_review_002",
                "gee_raster_core_review_003",
                "gee_raster_core_review_015",
                "gee_raster_core_review_016",
                "gee_raster_core_review_019",
                "gee_raster_core_review_025",
                "gee_raster_core_review_032",
                "gee_raster_core_review_048",
            },
        )
        for row in result.rows:
            self.assertEqual(row["description_policy"], "rewritten_chain_faithful")
            self.assertEqual(row["admission_tier"], "gee_core_p2_rewrite")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(len(row["l3_sequence"]), len(row["operator_sequence"]))
            self.assertTrue(row["evidence_snippet"])
            self.assertTrue(row["known_omissions"])

        row_002_text = (
            by_id["gee_raster_core_review_002"]["task_name"]
            + " "
            + by_id["gee_raster_core_review_002"]["task_description"]
        ).lower()
        self.assertNotIn("volume", row_002_text)
        self.assertNotIn("top 5", row_002_text)
        self.assertIn("polygon area multiplication", by_id["gee_raster_core_review_002"]["known_omissions"])

        row_032_text = (
            by_id["gee_raster_core_review_032"]["task_name"]
            + " "
            + by_id["gee_raster_core_review_032"]["task_description"]
        ).lower()
        self.assertNotIn("clip", row_032_text)
        self.assertIn("clipping", by_id["gee_raster_core_review_032"]["known_omissions"])

        row_048_text = (
            by_id["gee_raster_core_review_048"]["task_name"]
            + " "
            + by_id["gee_raster_core_review_048"]["task_description"]
        ).lower()
        self.assertNotIn("worldclim", row_048_text)
        self.assertNotIn("2001", row_048_text)
        self.assertIn("WorldClim comparison", by_id["gee_raster_core_review_048"]["known_omissions"])

    def test_cli_writes_rewrite_artifacts_and_keeps_salvage_input_unchanged(self) -> None:
        rewrite = importlib.import_module("scripts.build_gee_raster_core_description_rewrites")
        tmp = _workspace_dir("case1")
        try:
            before = SALVAGE_50.read_text(encoding="utf-8")
            outputs = rewrite.main(
                [
                    "--salvage-csv",
                    str(SALVAGE_50),
                    "--source-snippets",
                    str(SOURCE_SNIPPETS),
                    "--output-dir",
                    str(tmp),
                ]
            )

            self.assertEqual(SALVAGE_50.read_text(encoding="utf-8"), before)
            for key in ("csv", "jsonl", "train_rows_jsonl", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 8)
            jsonl_rows = [
                json.loads(line)
                for line in outputs["train_rows_jsonl"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(jsonl_rows), 8)
            self.assertTrue(all(row["admission_tier"] == "gee_core_p2_rewrite" for row in jsonl_rows))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
