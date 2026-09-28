from __future__ import annotations

import unittest

from scripts.build_qgis_api_set_crs_train_only import (
    ADMISSION,
    build_candidate,
    build_four_layer_dedup,
    export_train_only,
)


def _row(key: str, value: str = "EPSG:4326") -> dict:
    return {
        "unit_id": key,
        "record_id": key,
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"body-{key}",
        "family_rule_id": "qgis-api-local-layer-set-crs-metadata-v1",
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "mapping_status": "exact_stable125",
        "candidate_l3_sequence": ["L3_01_10_02"],
        "receiver_constructor": "QgsVectorLayer",
        "crs_fact": {
            "status": "crs_constructor",
            "constructor": "QgsCoordinateReferenceSystem",
            "source": f"QgsCoordinateReferenceSystem('{value}')",
            "value_fact": {"status": "literal", "value": value},
        },
        "source_span": [3, 3],
        "source_snippet": "layer = QgsVectorLayer(...)\nlayer.setCrs(crs)",
    }


class BuildQgisApiSetCrsTrainOnlyTest(unittest.TestCase):
    def test_builds_normalized_epsg_description(self) -> None:
        candidate = build_candidate(_row("a", "4326"))

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertIn("EPSG:4326", candidate["task_description"])
        self.assertIn("不变换", candidate["task_description"])

    def test_dedup_suppresses_equivalent_epsg_spelling(self) -> None:
        candidates = [build_candidate(_row("a", "4326")), build_candidate(_row("b"))]

        ledger, summary = build_four_layer_dedup(candidates)

        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual(
            {row["dedup_decision"] for row in ledger},
            {"canonical_keep", "exact_training_pair_suppressed"},
        )

    def test_exports_stable125_train_only_row(self) -> None:
        ledger, _ = build_four_layer_dedup([build_candidate(_row("a"))])

        exported, cross_pool, summary = export_train_only(
            ledger, [], {"L3_01_10_02": 121}
        )

        self.assertEqual(exported[0]["l3_sequence"], [-3, 121, -4])
        self.assertEqual(exported[0]["training_admission"], ADMISSION)
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)


if __name__ == "__main__":
    unittest.main()
