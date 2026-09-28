from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
SALVAGE_50 = REPORT_DIR / "gee_salvage_50_v1.csv"
SOURCE_SNIPPETS = REPORT_DIR / "source_evidence_snippets.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p2_v2"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP2NeedsEditResolutionTests(unittest.TestCase):
    def test_v2_rewrites_resolve_previous_needs_edit_rows(self) -> None:
        rewrite = importlib.import_module("scripts.build_gee_raster_core_description_rewrites")
        result = rewrite.build_description_rewrites(
            salvage_csv_path=SALVAGE_50,
            source_snippets_path=SOURCE_SNIPPETS,
            rewrite_version="v2",
        )

        by_id = {row["review_id"]: row for row in result.rows}
        row_016_text = (
            by_id["gee_raster_core_review_016"]["task_name"]
            + " "
            + by_id["gee_raster_core_review_016"]["task_description"]
        ).lower()
        self.assertNotIn("related image collection", row_016_text)
        self.assertIn("country-code", row_016_text)

        row_019_text = (
            by_id["gee_raster_core_review_019"]["task_name"]
            + " "
            + by_id["gee_raster_core_review_019"]["task_description"]
        ).lower()
        self.assertNotIn("cloud criteria", row_019_text)
        self.assertIn("wrs path/row", row_019_text)

    def test_v2_pipeline_writes_all_accepted_train_only_adjudication(self) -> None:
        rewrite = importlib.import_module("scripts.build_gee_raster_core_description_rewrites")
        review_packet = importlib.import_module("scripts.build_gee_p2_rewrite_review_packet")
        adjudicate = importlib.import_module("scripts.adjudicate_gee_p2_rewrite_review_packet")
        tmp = _workspace_dir("case1")
        try:
            rewrite_outputs = rewrite.main(
                [
                    "--salvage-csv",
                    str(SALVAGE_50),
                    "--source-snippets",
                    str(SOURCE_SNIPPETS),
                    "--rewrite-version",
                    "v2",
                    "--output-prefix",
                    "gee_p2_rewrite_8_v2",
                    "--output-dir",
                    str(tmp),
                ]
            )
            packet_outputs = review_packet.main(
                [
                    "--p2-rewrites",
                    str(rewrite_outputs["jsonl"]),
                    "--output-prefix",
                    "gee_p2_rewrite_8_review_packet_v2",
                    "--output-dir",
                    str(tmp),
                ]
            )
            adjudication_outputs = adjudicate.main(
                [
                    "--review-packet",
                    str(packet_outputs["jsonl"]),
                    "--decision-version",
                    "v2",
                    "--output-prefix",
                    "gee_p2_rewrite_8_review_packet_adjudicated_v2",
                    "--output-dir",
                    str(tmp),
                ]
            )

            with adjudication_outputs["summary"].open(encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["counts"]["rows"], 8)
            self.assertEqual(summary["counts"]["accepted_train_only"], 8)
            self.assertEqual(summary["counts"]["needs_edit"], 0)
            self.assertEqual(summary["counts"]["rejected"], 0)
            self.assertEqual(
                summary["decision"]["training_admission"],
                "not_granted_pending_train_only_export_gate",
            )
            self.assertFalse(summary["decision"]["validation_eligible"])
            self.assertFalse(summary["decision"]["test_eligible"])

            with adjudication_outputs["csv"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row["human_should_enter_train_only"] == "yes_train_only" for row in rows))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_v2_adjudication_rejects_unresolved_v1_packet(self) -> None:
        adjudicate = importlib.import_module("scripts.adjudicate_gee_p2_rewrite_review_packet")
        v1_packet = REPORT_DIR / "gee_p2_rewrite_8_review_packet_v1.jsonl"

        with self.assertRaisesRegex(ValueError, "v2 text guard"):
            adjudicate.build_adjudication(
                review_packet_jsonl_path=v1_packet,
                decision_version="v2",
            )


if __name__ == "__main__":
    unittest.main()
