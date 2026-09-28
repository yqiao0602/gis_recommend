from __future__ import annotations

import unittest

from scripts.build_qgis_api_polyline_geometry_train_only import (
    build_candidates,
    build_four_layer_dedup,
    export_train_only,
)


def _row(unit: str, vertex_count: int = 2) -> dict:
    return {
        "unit_id": unit, "record_id": unit, "source_root_id": "fixture", "source_path": f"/{unit}.py",
        "source_sha256": f"sha-{unit}", "source_authority_key": f"normalized_source_body_sha256:{unit}",
        "source_verification": "verified_sha256", "macro_status": "complete",
        "polyline_geometry_rule_id": "qgis-api-polyline-geometry-local-macro-v1",
        "proposed_l3_code": "L3_01_01_06", "proposed_l3_token_id": 126,
        "vertex_count": vertex_count, "vertex_sequence_kind": "literal_point_sequence",
        "polyline_factory_call": "QgsGeometry.fromPolylineXY", "polyline_factory_line": 2, "setgeometry_line": 3, "sink_line": 4,
        "source_span": [2, 4],
        "evidence_snippet": "2 | QgsGeometry.fromPolylineXY([QgsPointXY(1, 2), QgsPointXY(3, 4)])\n3 | feature.setGeometry(line)\n4 | sink.addFeature(feature)",
    }


class BuildQgisApiPolylineGeometryTrainOnlyTest(unittest.TestCase):
    def test_maps_explicit_vertex_facts_without_llm(self) -> None:
        candidate = build_candidates([_row("a", 3)])[0]

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["candidate_l3_sequence"], ["L3_01_01_06"])
        self.assertIn("3个顶点", candidate["task_description"])
        self.assertFalse(candidate["llm_called"])

    def test_accepts_instance_style_factory_after_ast_replay(self) -> None:
        row = _row("instance")
        row["evidence_snippet"] = row["evidence_snippet"].replace(
            "QgsGeometry.fromPolylineXY", "QgsGeometry().fromPolyline"
        )

        candidate = build_candidates([row])[0]

        self.assertTrue(candidate["description_fidelity_passed"])

    def test_suppresses_exact_training_pair_copies(self) -> None:
        ledger, summary = build_four_layer_dedup(build_candidates([_row("a"), _row("b")]))

        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual([row["dedup_decision"] for row in ledger], ["canonical_keep", "exact_training_pair_suppressed"])

    def test_exports_stable127_token(self) -> None:
        ledger, _ = build_four_layer_dedup(build_candidates([_row("a")]))
        canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
        training, cross_pool, summary = export_train_only(canonical, [], {"L3_01_01_06": 126})

        self.assertEqual(len(training), 1)
        self.assertEqual(training[0]["l3_sequence"], [-3, 126, -4])
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)


if __name__ == "__main__":
    unittest.main()
