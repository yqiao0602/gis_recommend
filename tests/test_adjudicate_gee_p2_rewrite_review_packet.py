from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
REVIEW_PACKET = REPORT_DIR / "gee_p2_rewrite_8_review_packet_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p2_adjudication"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP2RewriteAdjudicationTests(unittest.TestCase):
    def test_builds_strict_human_adjudication_for_all_p2_rewrites(self) -> None:
        adjudicate = importlib.import_module("scripts.adjudicate_gee_p2_rewrite_review_packet")
        result = adjudicate.build_adjudication(review_packet_jsonl_path=REVIEW_PACKET)

        self.assertEqual(result.summary["counts"]["rows"], 8)
        self.assertEqual(result.summary["counts"]["adjudicated_rows"], 8)
        self.assertEqual(result.summary["counts"]["accepted_train_only"], 6)
        self.assertEqual(result.summary["counts"]["needs_edit"], 2)
        self.assertEqual(result.summary["counts"]["rejected"], 0)
        self.assertEqual(result.summary["counts"]["pending_human_review"], 0)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_pending_needs_edit_resolution",
        )
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])

        by_id = {row["review_id"]: row for row in result.rows}
        self.assertEqual(
            {review_id for review_id, row in by_id.items() if row["human_should_enter_train_only"] == "yes_train_only"},
            {
                "gee_raster_core_review_002",
                "gee_raster_core_review_003",
                "gee_raster_core_review_015",
                "gee_raster_core_review_025",
                "gee_raster_core_review_032",
                "gee_raster_core_review_048",
            },
        )
        self.assertEqual(by_id["gee_raster_core_review_016"]["human_task_text_faithful"], "needs_edit")
        self.assertEqual(by_id["gee_raster_core_review_019"]["human_task_text_faithful"], "needs_edit")
        self.assertTrue(all(row["review_status"] == "adjudicated" for row in result.rows))
        self.assertTrue(all(row["validation_eligible"] is False for row in result.rows))
        self.assertTrue(all(row["test_eligible"] is False for row in result.rows))

    def test_cli_writes_adjudicated_artifacts_without_modifying_review_packet(self) -> None:
        adjudicate = importlib.import_module("scripts.adjudicate_gee_p2_rewrite_review_packet")
        tmp = _workspace_dir("case1")
        try:
            before = REVIEW_PACKET.read_text(encoding="utf-8")
            outputs = adjudicate.main(
                [
                    "--review-packet",
                    str(REVIEW_PACKET),
                    "--output-dir",
                    str(tmp),
                ]
            )

            self.assertEqual(REVIEW_PACKET.read_text(encoding="utf-8"), before)
            for key in ("csv", "jsonl", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)

            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 8)
            self.assertEqual(csv_rows[0]["review_status"], "adjudicated")

            jsonl_rows = [
                json.loads(line)
                for line in outputs["jsonl"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(jsonl_rows), 8)
            self.assertEqual(
                sum(row["human_should_enter_train_only"] == "yes_train_only" for row in jsonl_rows),
                6,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
