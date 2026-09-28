from __future__ import annotations

import unittest

from scripts.build_qgis_api_point_geometry_train_only import (
    build_candidates,
    build_four_layer_dedup,
    export_train_only,
)


def _row(unit: str, origin: str = "literal_coordinate_pair") -> dict:
    return {
        "unit_id": unit,
        "record_id": unit,
        "source_root_id": "fixture",
        "source_path": f"/{unit}.py",
        "source_sha256": f"sha-{unit}",
        "source_authority_key": f"normalized_source_body_sha256:{unit}",
        "source_verification": "verified_sha256",
        "macro_status": "complete",
        "point_geometry_rule_id": "qgis-api-point-geometry-local-macro-v1",
        "description_fidelity": "passed_source_fact_only",
        "proposed_l3_code": "L3_01_01_05",
        "proposed_l3_token_id": 125,
        "coordinate_origin_kind": origin,
        "coordinate_component_expressions": ["x", "y"],
        "point_factory_call": "QgsGeometry.fromPoint",
        "point_factory_line": 2,
        "setgeometry_line": 3,
        "sink_line": 4,
        "source_span": [2, 4],
        "evidence_snippet": (
            "2 | QgsGeometry.fromPoint(QgsPoint(x, y))\n"
            "3 | feature.setGeometry(point)\n4 | sink.addFeature(feature)"
        ),
    }


class BuildQgisApiPointGeometryTrainOnlyTest(unittest.TestCase):
    def test_maps_source_facts_without_llm(self) -> None:
        candidate = build_candidates([_row("a")])[0]

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["candidate_l3_sequence"], ["L3_01_01_05"])
        self.assertFalse(candidate["llm_called"])

    def test_suppresses_exact_training_pair_copies(self) -> None:
        candidates = build_candidates([_row("a"), _row("b")])
        ledger, summary = build_four_layer_dedup(candidates)

        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual(
            [row["dedup_decision"] for row in ledger],
            ["canonical_keep", "exact_training_pair_suppressed"],
        )

    def test_exports_stable126_token(self) -> None:
        ledger, _ = build_four_layer_dedup(build_candidates([_row("a")]))
        canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
        training, cross_pool, summary = export_train_only(
            canonical, [], {"L3_01_01_05": 125}
        )

        self.assertEqual(len(training), 1)
        self.assertEqual(training[0]["l3_sequence"], [-3, 125, -4])
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)


if __name__ == "__main__":
    unittest.main()
