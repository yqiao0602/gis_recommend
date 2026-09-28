from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1"


class QgisConversionCalibrationLedgerTests(unittest.TestCase):
    def test_aggregates_exactly_50_source_grounded_rows(self) -> None:
        module = importlib.import_module("scripts.build_qgis_conversion_calibration_ledger")
        rows, summary = module.build(
            INPUT_DIR / "stable101_source_review_50_v1.jsonl",
            INPUT_DIR / "second_salvage_preclass_v1.jsonl",
            [INPUT_DIR / f"second_adjudications_batch{i}_v1.jsonl" for i in range(1, 6)],
        )
        self.assertEqual(len(rows), 50)
        self.assertEqual(len({row["review_index"] for row in rows}), 50)
        self.assertEqual(len({row["source_sha256"] for row in rows}), 50)
        self.assertTrue(summary["source_sha_unique"])
        self.assertTrue(summary["record_id_unique"])
        self.assertFalse(summary["validation_eligible"])
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertEqual(sum(summary["decision_counts"].values()), 50)

    def test_duplicate_or_missing_sidecar_fails_closed(self) -> None:
        module = importlib.import_module("scripts.build_qgis_conversion_calibration_ledger")
        paths = [INPUT_DIR / f"second_adjudications_batch{i}_v1.jsonl" for i in range(1, 5)]
        with self.assertRaises(ValueError):
            module.build(INPUT_DIR / "stable101_source_review_50_v1.jsonl", INPUT_DIR / "second_salvage_preclass_v1.jsonl", paths)


if __name__ == "__main__":
    unittest.main()
