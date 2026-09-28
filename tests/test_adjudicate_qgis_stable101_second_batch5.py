from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1"


class Stable101Batch5AdjudicationTests(unittest.TestCase):
    def test_final_ten_are_fail_closed(self) -> None:
        module = importlib.import_module("scripts.adjudicate_qgis_stable101_second_batch5")
        rows = module.build(REVIEW_DIR / "second_priority_review_batch5_proposals_v1.jsonl", REVIEW_DIR / "stable101_source_review_50_v1.jsonl")
        self.assertEqual(len(rows), 10)
        self.assertEqual(sum(row["final_decision"].startswith("rejected") for row in rows), 5)
        self.assertEqual(sum(row["final_decision"].startswith("deferred") for row in rows), 5)
        self.assertTrue(all(row["training_admission"] == "not_granted" for row in rows))
        self.assertTrue(all(not row["validation_eligible"] and not row["test_eligible"] for row in rows))


if __name__ == "__main__":
    unittest.main()
