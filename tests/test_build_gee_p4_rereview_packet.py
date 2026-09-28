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

REPORT_ROOT = ROOT / "docs/reports"
REVIEW_DIR = REPORT_ROOT / "gee_raster_core_v1_review_split_2026-07-24"
P3B_JSONL = REPORT_ROOT / "gee_extractor_v2_p3b_deferred_reextract_impact_2026-07-25.jsonl"
SALVAGE_CSV = REVIEW_DIR / "gee_salvage_50_v1.csv"
SOURCE_SNIPPETS = REVIEW_DIR / "source_evidence_snippets.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p4_rereview"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP4RereviewPacketTests(unittest.TestCase):
    def test_builds_p4_packet_from_real_p3b_candidates_without_admission(self) -> None:
        module = importlib.import_module("scripts.build_gee_p4_rereview_packet")
        result = module.build_p4_rereview_packet(
            p3b_jsonl_path=P3B_JSONL,
            salvage_csv_path=SALVAGE_CSV,
            source_snippets_path=SOURCE_SNIPPETS,
        )

        self.assertEqual(result.report["counts"]["p4_candidate_rows"], 28)
        self.assertEqual(result.report["decision"]["training_admission"], "not_granted_pending_p4_human_review")
        self.assertFalse(result.report["decision"]["validation_eligible"])
        self.assertFalse(result.report["decision"]["test_eligible"])
        self.assertFalse(result.report["policy"]["llm_used"])
        self.assertFalse(result.report["policy"]["training_rows_emitted"])

        by_id = {row["review_id"]: row for row in result.rows}
        self.assertIn("gee_raster_core_review_010", by_id)
        row_010 = by_id["gee_raster_core_review_010"]
        self.assertIn("ml_classification", row_010["recovered_signal_categories"])
        self.assertIn("image.sampleregions", row_010["new_core_operator_sequence"])
        self.assertEqual(row_010["human_should_enter_train_only"], "")
        self.assertTrue(row_010["evidence_snippet"])

    def test_cli_writes_packet_artifacts(self) -> None:
        module = importlib.import_module("scripts.build_gee_p4_rereview_packet")
        tmp = _workspace_dir("case1")
        try:
            outputs = module.main(
                [
                    "--p3b-jsonl",
                    str(P3B_JSONL),
                    "--salvage-csv",
                    str(SALVAGE_CSV),
                    "--source-snippets",
                    str(SOURCE_SNIPPETS),
                    "--output-dir",
                    str(tmp),
                ]
            )

            for key in ("csv", "jsonl", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)
            with outputs["csv"].open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 28)
            self.assertTrue(all(row["human_should_enter_train_only"] == "" for row in rows))
            payload = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            self.assertEqual(payload["counts"]["p4_candidate_rows"], 28)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
