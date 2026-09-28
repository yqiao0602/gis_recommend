from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1/calibration_v1/ledger.jsonl"
CONFIG = ROOT / "config/qgis_conversion_rules_v1.json"


class EvaluateQgisConversionRulesTests(unittest.TestCase):
    def test_small_perfect_rule_is_not_auto_admitted(self) -> None:
        module = importlib.import_module("scripts.evaluate_qgis_conversion_rules")
        report = module.evaluate(LEDGER, CONFIG)
        direct = report["rule_metrics"]["direct-explicit-dag-v1"]
        self.assertEqual(direct["accepted"], direct["support"])
        self.assertGreater(direct["support"], 0)
        self.assertFalse(direct["auto_accept_eligible"])
        self.assertEqual(report["auto_accept_allowlist"], [])
        self.assertFalse(report["decision"]["auto_accept_granted"])
        self.assertEqual(report["decision"]["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
