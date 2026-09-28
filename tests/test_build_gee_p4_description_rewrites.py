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
P4_ADJUDICATION = REPORT_DIR / "gee_p4_review_adjudication_28_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p4_rewrite"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP4DescriptionRewriteTests(unittest.TestCase):
    def test_builds_chain_faithful_rewrites_without_training_admission(self) -> None:
        rewrite = importlib.import_module("scripts.build_gee_p4_description_rewrites")
        result = rewrite.build_p4_description_rewrites(
            p4_adjudication_jsonl_path=P4_ADJUDICATION,
        )

        expected_ids = {
            "gee_raster_core_review_004",
            "gee_raster_core_review_005",
            "gee_raster_core_review_006",
            "gee_raster_core_review_021",
            "gee_raster_core_review_027",
            "gee_raster_core_review_029",
            "gee_raster_core_review_033",
            "gee_raster_core_review_034",
            "gee_raster_core_review_044",
            "gee_raster_core_review_047",
        }
        self.assertEqual(result.summary["counts"]["rewrite_rows"], 10)
        self.assertEqual({row["review_id"] for row in result.rows}, expected_ids)
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_pending_l3_mapping_and_export_gate",
        )
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])

        for row in result.rows:
            self.assertEqual(row["description_policy"], "rewritten_chain_faithful")
            self.assertEqual(row["training_admission"], "not_granted_pending_l3_mapping_and_export_gate")
            self.assertEqual(row["new_l3_sequence_status"], "pending_operator_l3_canonicalization")
            self.assertTrue(row["operator_sequence"])
            self.assertTrue(row["old_l3_sequence"])
            self.assertNotIn("l3_sequence", row)
            self.assertTrue(row["known_omissions"])
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])

        by_id = {row["review_id"]: row for row in result.rows}
        text_004 = (by_id["gee_raster_core_review_004"]["task_name"] + " " + by_id["gee_raster_core_review_004"]["task_description"]).lower()
        self.assertIn("water-index", text_004)
        self.assertIn("quality mosaic", text_004)
        self.assertNotIn("surface water extent", text_004)

        text_005 = (by_id["gee_raster_core_review_005"]["task_name"] + " " + by_id["gee_raster_core_review_005"]["task_description"]).lower()
        self.assertIn("training samples", text_005)
        self.assertNotIn("classify land cover", text_005)

        text_021 = by_id["gee_raster_core_review_021"]["task_description"].lower()
        self.assertNotIn("terrain correction", text_021)

        text_027 = by_id["gee_raster_core_review_027"]["task_description"].lower()
        self.assertIn("min-max", text_027)
        self.assertNotIn("cloud-masked", text_027)

    def test_cli_writes_rewrite_artifacts_without_mutating_adjudication(self) -> None:
        rewrite = importlib.import_module("scripts.build_gee_p4_description_rewrites")
        tmp = _workspace_dir("case1")
        try:
            before = P4_ADJUDICATION.read_text(encoding="utf-8")
            outputs = rewrite.main(
                [
                    "--p4-adjudication",
                    str(P4_ADJUDICATION),
                    "--output-dir",
                    str(tmp),
                ]
            )

            self.assertEqual(P4_ADJUDICATION.read_text(encoding="utf-8"), before)
            for key in ("csv", "jsonl", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)
            self.assertNotIn("train_rows_jsonl", outputs)

            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 10)
            jsonl_rows = [
                json.loads(line)
                for line in outputs["jsonl"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(jsonl_rows), 10)
            self.assertTrue(
                all(row["new_l3_sequence_status"] == "pending_operator_l3_canonicalization" for row in jsonl_rows)
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
