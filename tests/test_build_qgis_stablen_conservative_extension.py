import unittest

from scripts.build_qgis_stablen_conservative_extension import (
    analyze_conservative_impact,
    build_extension_proposal,
    build_mapping_delta,
    conservative_decision_rows,
    stable98_code_to_id,
    validate_source_review,
)


class StableNConservativeExtensionTest(unittest.TestCase):
    def test_stable98_code_to_id_combines_existing_and_additions(self) -> None:
        extension = {
            "existing_code_to_id": {"L3_A": 0, "L3_B": 1},
            "proposed_code_to_id_additions": {"L3_C": 2},
            "proposed_class_count": 3,
            "existing_token_ids_unchanged": True,
        }

        self.assertEqual(stable98_code_to_id(extension), {"L3_A": 0, "L3_B": 1, "L3_C": 2})

    def test_conservative_decisions_exclude_support_boundary_operators(self) -> None:
        decisions = [
            {
                "operator_id": "native:reprojectlayer",
                "candidate_l3_code": "L3_REPROJECT",
                "scenario": "conservative",
                "confidence": "high",
                "mapping_kind": "restore_old350_l3",
                "review_reason": "ok",
            },
            {
                "operator_id": "native:fixgeometries",
                "candidate_l3_code": "L3_REPAIR",
                "scenario": "conservative",
                "confidence": "high",
                "mapping_kind": "restore_old350_l3",
                "review_reason": "ok",
            },
            {
                "operator_id": "gdal:polygonize",
                "candidate_l3_code": "L3_RASTER_VECTOR",
                "scenario": "conservative",
                "confidence": "high",
                "mapping_kind": "restore_old350_l3",
                "review_reason": "ok",
            },
            {
                "operator_id": "gdal:rasterize",
                "candidate_l3_code": "L3_RASTER_VECTOR",
                "scenario": "conservative",
                "confidence": "high",
                "mapping_kind": "restore_old350_l3",
                "review_reason": "ok",
            },
            {
                "operator_id": "native:createspatialindex",
                "candidate_l3_code": "L3_INDEX",
                "candidate_l3_name": "Index",
                "scenario": "support_boundary",
                "confidence": "medium",
                "mapping_kind": "restore_old350_l3",
                "training_role": "support_step_deferred",
            },
            {
                "operator_id": "native:saveselectedfeatures",
                "candidate_l3_code": "L3_EXPORT",
                "candidate_l3_name": "Export",
                "scenario": "support_boundary",
                "confidence": "medium",
                "mapping_kind": "alias_existing_stable94",
                "training_role": "export_step_deferred",
            },
        ]
        legacy = {
            "L3_REPROJECT": {"l3_code": "L3_REPROJECT", "l3_name": "Project"},
            "L3_REPAIR": {"l3_code": "L3_REPAIR", "l3_name": "Repair"},
            "L3_RASTER_VECTOR": {"l3_code": "L3_RASTER_VECTOR", "l3_name": "Raster Vector"},
        }

        accepted, excluded = conservative_decision_rows(
            decisions,
            base_codes={"L3_A", "L3_EXPORT"},
            legacy_by_code=legacy,
        )
        delta = build_mapping_delta(accepted, excluded)

        self.assertEqual(delta["operator_count"], 4)
        self.assertEqual(delta["excluded_boundary_operator_count"], 2)
        self.assertEqual(delta["alias_mappings"], {})
        self.assertNotIn("native:createspatialindex", delta["restored_l3_mappings"])
        self.assertNotIn("native:saveselectedfeatures", delta["restored_l3_mappings"])
        self.assertEqual(delta["restored_l3_mappings"]["gdal:polygonize"], "L3_RASTER_VECTOR")
        self.assertEqual(delta["restored_l3_mappings"]["gdal:rasterize"], "L3_RASTER_VECTOR")

    def test_source_review_gate_requires_three_active_home_yll_samples(self) -> None:
        accepted = [
            {"operator_id": "native:reprojectlayer", "l3_code": "L3_REPROJECT"},
        ]
        rows = [
            {
                "operator_id": "native:reprojectlayer",
                "candidate_l3_code": "L3_REPROJECT",
                "source_review_verdict": "accept_mapping_after_authority",
                "active_processing_call": True,
                "source_path": f"/home/yll/sample_{index}.py",
                "content_sha256": f"hash{index}",
                "call": {"line_start": index, "line_end": index, "param_keys": ["INPUT"]},
            }
            for index in range(1, 4)
        ]
        summary = {
            "date": "2026-07-24",
            "selected_per_operator": {"native:reprojectlayer": 3},
            "unique_layer_hits": {"native:reprojectlayer": 99},
            "artifact_sha256": {"review": "abc"},
        }

        gate = validate_source_review(rows, summary, accepted)

        self.assertEqual(gate["status"], "passed")
        self.assertEqual(gate["accepted_operator_count"], 1)
        self.assertEqual(gate["reviewed_operators"]["native:reprojectlayer"]["selected_samples"], 3)

    def test_extension_appends_new_codes_after_stable98(self) -> None:
        stable98_extension = {
            "existing_code_to_id": {"L3_A": 0, "L3_B": 1},
            "proposed_code_to_id_additions": {"L3_C": 2},
            "proposed_class_count": 3,
            "proposed_taxonomy": "stable3",
            "existing_token_ids_unchanged": True,
        }
        accepted = [
            {"operator_id": "gdal:rasterize", "l3_code": "L3_E"},
            {"operator_id": "native:fixgeometries", "l3_code": "L3_D"},
        ]
        legacy = {
            "L3_D": {"l3_code": "L3_D", "l3_name": "D"},
            "L3_E": {"l3_code": "L3_E", "l3_name": "E"},
        }
        gate = {
            "status": "passed",
            "review_date": "2026-07-24",
            "required_samples_per_operator": 3,
            "accepted_operator_count": 2,
        }

        proposal = build_extension_proposal(
            stable98_extension=stable98_extension,
            accepted_entries=accepted,
            legacy_by_code=legacy,
            source_review_gate=gate,
        )

        self.assertEqual(proposal["base_class_count"], 3)
        self.assertEqual(proposal["proposed_class_count"], 5)
        self.assertEqual(proposal["proposed_taxonomy"], "stable5")
        self.assertEqual(proposal["proposed_code_to_id_additions"], {"L3_D": 3, "L3_E": 4})
        self.assertTrue(proposal["existing_token_ids_unchanged"])
        self.assertEqual(proposal["taxonomy_admission"], "not_granted")

    def test_impact_is_measured_against_stable98_mapping(self) -> None:
        records = [
            {"qgis_ops": ["native:a"]},
            {"qgis_ops": ["native:a", "native:reprojectlayer"]},
            {"qgis_ops": ["native:a", "native:reprojectlayer"]},
            {"qgis_ops": ["native:a", "native:fixgeometries"]},
            {"qgis_ops": ["native:a", "native:fixgeometries", "native:x"]},
            {"qgis_ops": ["native:a", "native:createspatialindex"]},
        ]

        summary, details = analyze_conservative_impact(
            records,
            stable98_mapping={"native:a": "L3_A"},
            conservative_mapping={
                "native:reprojectlayer": "L3_REPROJECT",
                "native:fixgeometries": "L3_REPAIR",
            },
        )

        self.assertEqual(summary["stable98_draft"], {"complete_records": 1, "complete_unique_chains": 1})
        self.assertEqual(
            summary["stablen_conservative_draft"],
            {"complete_records": 4, "complete_unique_chains": 3},
        )
        self.assertEqual(summary["increment_vs_stable98"], {"records": 3, "unique_chains": 2})
        self.assertEqual(summary["still_incomplete_records"], 1)
        self.assertEqual(
            [row["impact_stage"] for row in details],
            [
                "newly_complete_stablen_conservative",
                "newly_complete_stablen_conservative",
                "newly_complete_stablen_conservative",
                "still_incomplete_after_stablen",
            ],
        )


if __name__ == "__main__":
    unittest.main()
