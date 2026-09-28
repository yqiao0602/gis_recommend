from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Stable101CompleteRecordsTests(unittest.TestCase):
    def test_real_authorities_reproduce_reported_complete_pool(self) -> None:
        module = importlib.import_module(
            "scripts.build_qgis_stable101_complete_records"
        )
        rows, summary = module.build(
            ROOT / "outputs_v2/qgis_chain_dataset.jsonl",
            ROOT
            / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_alg_id_crosswalk_v1.json",
            ROOT
            / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_mapping_authority_stable98_delta_draft_v1.json",
            ROOT
            / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/qgis_mapping_authority_stable101_conservative_delta_draft_v1.json",
        )
        self.assertEqual(len(rows), 1442)
        self.assertEqual(summary["complete_unique_chains"], 449)
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertTrue(
            all(
                len(row["qgis_ops"]) == len(row["proposed_l3_sequence"])
                for row in rows
            )
        )


if __name__ == "__main__":
    unittest.main()
