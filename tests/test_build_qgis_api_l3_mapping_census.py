from __future__ import annotations

import unittest

from scripts.build_qgis_api_l3_mapping_census import classify_candidate


def _step(call_name: str, call_role: str) -> dict:
    return {
        "call_name": call_name,
        "call_role": call_role,
        "line_start": 1,
        "line_end": 1,
    }


def _candidate(*steps: dict) -> dict:
    return {
        "candidate_id": "candidate",
        "source_authority_key": "normalized_source_body_sha256:body",
        "steps": list(steps),
    }


class BuildQgisApiL3MappingCensusTest(unittest.TestCase):
    def test_maps_boundary_verified_random_point_composite_to_sample_points(self) -> None:
        row = _candidate(
            _step("random_point_sampling", "composite_algorithm"),
            _step("feature.setGeometry", "feature_mutation"),
            _step("sink.addFeature", "sink_output"),
        )
        row.update(
            {
                "random_point_recovery_rule_id": "lexical-scope-random-point-sampling-v1",
                "random_point_recovery_status": "resolved_complete_lexical_scope_workflow",
            }
        )

        classified = classify_candidate(row)

        self.assertEqual(classified["mapping_status"], "exact_existing_l3")
        self.assertEqual(classified["semantic_calls"], ["random_point_sampling"])
        self.assertEqual(classified["candidate_l3_sequence"], ["L3_02_06_06"])
        self.assertEqual(classified["unresolved_semantic_calls"], [])

    def test_defers_random_point_composite_without_frozen_recovery_provenance(self) -> None:
        classified = classify_candidate(
            _candidate(_step("random_point_sampling", "composite_algorithm"))
        )

        self.assertEqual(classified["mapping_status"], "unresolved")
        self.assertEqual(classified["candidate_l3_sequence"], [])
        self.assertEqual(
            classified["unresolved_semantic_calls"],
            [
                {
                    "call_name": "random_point_sampling",
                    "reason": "unverified_composite_pattern_provenance",
                }
            ],
        )

    def test_maps_only_exact_stable110_geometry_semantics_in_source_order(self) -> None:
        row = _candidate(
            _step("geom.buffer", "geometry_transform"),
            _step("geom.intersection", "geometry_transform"),
            {
                **_step("output.setAttributes", "attribute_mutation"),
                "consumed_names": ["attrs_a", "attrs_b", "output"],
            },
            _step("geom.simplify", "geometry_transform"),
            _step("geom.centroid", "geometry_transform"),
            _step("geom.convexHull", "geometry_transform"),
            _step("sink.addFeature", "sink_output"),
        )

        classified = classify_candidate(row)

        self.assertEqual(classified["mapping_status"], "exact_existing_l3")
        self.assertEqual(
            classified["candidate_l3_sequence"],
            [
                "L3_02_01_01",
                "L3_02_02_01",
                "L3_02_05_01",
                "L3_02_05_11",
                "L3_02_05_12",
            ],
        )
        self.assertEqual(classified["unresolved_semantic_calls"], [])
        self.assertFalse(classified["training_row_emitted"])

    def test_defers_intersection_without_two_input_attribute_evidence(self) -> None:
        row = _candidate(
            _step("geom.intersection", "geometry_transform"),
            _step("feature.setGeometry", "feature_mutation"),
            _step("writer.addFeature", "sink_output"),
        )

        classified = classify_candidate(row)

        self.assertEqual(classified["mapping_status"], "unresolved")
        self.assertEqual(classified["candidate_l3_sequence"], [])
        self.assertEqual(
            classified["unresolved_semantic_calls"],
            [{"call_name": "geom.intersection", "reason": "output_contract_insufficient"}],
        )

    def test_defers_mutation_and_export_without_algorithm_semantics(self) -> None:
        row = _candidate(
            _step("feature.setGeometry", "feature_mutation"),
            _step("feature.setAttributes", "attribute_mutation"),
            _step("writer.addFeature", "sink_output"),
        )

        classified = classify_candidate(row)

        self.assertEqual(classified["mapping_status"], "mutation_export_only")
        self.assertEqual(classified["candidate_l3_sequence"], [])
        self.assertEqual(classified["mapping_admission"], "not_granted")

    def test_fail_closes_partial_or_contract_mismatched_semantics(self) -> None:
        expected = {
            "geom.interpolate": "parameter_dependent",
            "geom.combine": "taxonomy_contract_mismatch",
            "geom.offsetCurve": "taxonomy_gap",
            "xformutil.transform": "task_scope_insufficient",
        }
        for call_name, reason in expected.items():
            with self.subTest(call_name=call_name):
                row = _candidate(
                    _step(
                        call_name,
                        "crs_transform"
                        if call_name.endswith("transform")
                        else "geometry_transform",
                    ),
                    _step("sink.addFeature", "sink_output"),
                )

                classified = classify_candidate(row)

                self.assertEqual(classified["mapping_status"], "unresolved")
                self.assertEqual(classified["candidate_l3_sequence"], [])
                self.assertEqual(
                    classified["unresolved_semantic_calls"],
                    [{"call_name": call_name, "reason": reason}],
                )

    def test_does_not_partially_map_a_mixed_exact_and_unresolved_unit(self) -> None:
        row = _candidate(
            _step("geom.buffer", "geometry_transform"),
            _step("geom.combine", "geometry_transform"),
            _step("sink.addFeature", "sink_output"),
        )

        classified = classify_candidate(row)

        self.assertEqual(classified["mapping_status"], "unresolved")
        self.assertEqual(classified["candidate_l3_sequence"], [])
        self.assertEqual(classified["resolved_l3_evidence"], ["L3_02_01_01"])


if __name__ == "__main__":
    unittest.main()
