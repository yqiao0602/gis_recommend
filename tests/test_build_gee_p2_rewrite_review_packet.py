from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
P2_REWRITES = REPORT_DIR / "gee_p2_rewrite_8_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_p2_review_packet"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP2RewriteReviewPacketTests(unittest.TestCase):
    def test_builds_blank_human_review_packet_for_all_p2_rewrites(self) -> None:
        review_packet = importlib.import_module("scripts.build_gee_p2_rewrite_review_packet")
        result = review_packet.build_review_packet(p2_rewrite_jsonl_path=P2_REWRITES)

        self.assertEqual(result.summary["counts"]["rows"], 8)
        self.assertEqual(result.summary["counts"]["pending_human_review"], 8)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_pending_human_text_fidelity_review",
        )

        required_human_fields = {
            "human_task_text_faithful",
            "human_known_omissions_correct",
            "human_should_enter_train_only",
            "human_review_notes",
        }
        for row in result.rows:
            self.assertTrue(required_human_fields.issubset(row))
            self.assertTrue(all(row[field] == "" for field in required_human_fields))
            self.assertEqual(row["review_status"], "pending")
            self.assertEqual(row["admission_tier"], "gee_core_p2_rewrite")
            self.assertEqual(row["validation_eligible"], False)
            self.assertEqual(row["test_eligible"], False)
            self.assertTrue(row["rewritten_task_description"])
            self.assertTrue(row["known_omissions"])
            self.assertTrue(row["evidence_snippet"])

    def test_cli_writes_packet_artifacts_without_modifying_p2_input(self) -> None:
        review_packet = importlib.import_module("scripts.build_gee_p2_rewrite_review_packet")
        tmp = _workspace_dir("case1")
        try:
            before = P2_REWRITES.read_text(encoding="utf-8")
            outputs = review_packet.main(
                [
                    "--p2-rewrites",
                    str(P2_REWRITES),
                    "--output-dir",
                    str(tmp),
                ]
            )

            self.assertEqual(P2_REWRITES.read_text(encoding="utf-8"), before)
            for key in ("csv", "jsonl", "summary", "instructions", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)

            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 8)
            self.assertEqual(rows[0]["human_should_enter_train_only"], "")

            summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"]["rows"], 8)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
