from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1"


class Stable101Batch5ProposalTests(unittest.TestCase):
    def test_exact_remainder_and_fail_closed_metadata(self) -> None:
        module = importlib.import_module("scripts.build_qgis_stable101_second_batch5_proposals")
        rows, summary = module.build(
            REVIEW_DIR / "stable101_source_review_50_v1.jsonl",
            REVIEW_DIR / "second_salvage_preclass_v1.jsonl",
        )
        self.assertEqual([row["review_index"] for row in rows], [7, 9, 14, 36, 39, 40, 43, 44, 46, 48])
        self.assertEqual(summary["decision_counts"], {"exclude_current_chain": 5, "defer_api_pattern": 5})
        self.assertTrue(all(row["proposal_status"] == "proposal_only" for row in rows))
        self.assertTrue(all(row["training_admission"] == "not_granted" for row in rows))
        self.assertTrue(all(row["validation_eligible"] is False and row["test_eligible"] is False for row in rows))
        self.assertTrue(all(row["llm_called"] is False for row in rows))

    def test_does_not_mutate_review_pack(self) -> None:
        module = importlib.import_module("scripts.build_qgis_stable101_second_batch5_proposals")
        before = (REVIEW_DIR / "stable101_source_review_50_v1.jsonl").read_bytes()
        module.build(REVIEW_DIR / "stable101_source_review_50_v1.jsonl", REVIEW_DIR / "second_salvage_preclass_v1.jsonl")
        self.assertEqual(before, (REVIEW_DIR / "stable101_source_review_50_v1.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()
