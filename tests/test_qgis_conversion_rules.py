from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_rules import route_candidate, validate_rule_fields


class QgisConversionRuleTests(unittest.TestCase):
    def test_direct_connected_dag_is_only_an_auto_accept_candidate(self) -> None:
        row = {"mapped_l3_chain": ["L3_A", "L3_B"], "api_pattern_calls": [], "call_graph_status": "single_scope"}
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer", "native:fixgeometries"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": [],
            "workflow_unit_scope": "whole_processing_scope",
        }
        decision = route_candidate(row, features)
        self.assertEqual(decision.rule_id, "direct-explicit-dag-v1")
        self.assertEqual(decision.action, "auto_accept_candidate")
        self.assertEqual(
            decision.evidence["structure_class"],
            "valid_whole_processing_scope_candidate",
        )
        self.assertEqual(
            decision.evidence["description_requirement"],
            "whole_scope_task_description_required",
        )

    def test_missing_data_edge_recovers_instead_of_accepting(self) -> None:
        row = {"mapped_l3_chain": ["L3_A", "L3_B"], "api_pattern_calls": [], "call_graph_status": "single_scope"}
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer", "native:fixgeometries"],
            "dependency_edges": [],
            "control_flow_kinds": [],
        }
        self.assertEqual(route_candidate(row, features).action, "recover_call_graph")

    def test_api_and_disconnected_scopes_fail_closed(self) -> None:
        base = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer"],
            "dependency_edges": [],
            "control_flow_kinds": [],
        }
        api_row = {"mapped_l3_chain": ["L3_A"], "api_pattern_calls": ["edit@1"], "call_graph_status": "single_scope"}
        split_row = {"mapped_l3_chain": ["L3_A"], "api_pattern_calls": [], "call_graph_status": "disconnected_candidate_scopes"}
        self.assertEqual(route_candidate(api_row, base).action, "review_api_sidecar")
        self.assertEqual(route_candidate(split_row, base).action, "split_subworkflow")

    def test_rule_identity_fields_are_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            validate_rule_fields({"review_index", "parse_status"})

    def test_intermediate_custom_transform_is_blocked_from_direct_admission(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer", "native:buffer"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": [],
            "intermediate_data_transform_calls": [
                "CartogramFeatures.from_polygon_layer",
                "cartogram_features.transform",
            ],
        }
        decision = route_candidate(row, features)
        self.assertEqual(decision.rule_id, "review-intermediate-data-transform-v1")
        self.assertEqual(decision.action, "review_api_sidecar")
        self.assertEqual(decision.evidence["structure_class"], "blocked_custom_transform")

    def test_non_transforming_raster_wrappers_do_not_block_a_connected_dag(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:reclassifybytable", "qgis:rastercalculator"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": [],
            "intermediate_data_transform_calls": ["QgsRasterLayer", "print"],
            "workflow_unit_scope": "whole_processing_scope",
        }

        decision = route_candidate(row, features)

        self.assertEqual(decision.action, "auto_accept_candidate")
        self.assertEqual(
            decision.evidence["non_transforming_intermediate_calls"],
            ["QgsRasterLayer", "print"],
        )

    def test_non_transforming_wrapper_allowlist_does_not_hide_real_transforms(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:reclassifybytable", "qgis:rastercalculator"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": [],
            "intermediate_data_transform_calls": ["QgsRasterLayer", "ReadAsArray"],
            "workflow_unit_scope": "whole_processing_scope",
        }

        decision = route_candidate(row, features)

        self.assertEqual(decision.action, "review_api_sidecar")
        self.assertEqual(
            decision.evidence["intermediate_data_transform_calls"],
            ["ReadAsArray"],
        )

    def test_valid_local_subworkflow_requires_a_scoped_description(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer", "native:fixgeometries"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": [],
            "intermediate_data_transform_calls": [],
            "workflow_unit_scope": "local_subworkflow",
        }
        decision = route_candidate(row, features)
        self.assertEqual(decision.action, "auto_accept_candidate")
        self.assertEqual(
            decision.evidence["structure_class"],
            "valid_local_subworkflow_candidate",
        )
        self.assertEqual(
            decision.evidence["description_requirement"],
            "local_subworkflow_description_required",
        )

    def test_unresolved_output_reference_fails_closed_to_recovery(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:intersection", "native:difference"],
            "dependency_edges": [[0, 1]],
            "unresolved_output_references": [
                {
                    "consumer_index": 1,
                    "reference": "name:intersection.key:OUTPUT",
                }
            ],
            "control_flow_kinds": [],
            "workflow_unit_scope": "whole_processing_scope",
        }
        decision = route_candidate(row, features)
        self.assertEqual(decision.rule_id, "recover-unresolved-output-reference-v1")
        self.assertEqual(decision.action, "recover_call_graph")

    def test_downstream_transform_and_unused_terminal_fail_closed(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        base = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer", "native:fixgeometries"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": [],
            "workflow_unit_scope": "whole_processing_scope",
        }
        downstream = dict(base, downstream_data_transform_calls=["custom_helper"])
        decision = route_candidate(row, downstream)
        self.assertEqual(decision.rule_id, "review-downstream-data-transform-v1")
        self.assertEqual(decision.action, "review_api_sidecar")

        unused = dict(base, unused_temporary_terminal_indices=[0])
        decision = route_candidate(row, unused)
        self.assertEqual(decision.rule_id, "recover-unused-temporary-terminal-v1")
        self.assertEqual(decision.action, "recover_call_graph")

    def test_existing_recovery_reason_precedes_direct_boundary_checks(self) -> None:
        row = {
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "api_pattern_calls": [],
            "call_graph_status": "single_scope",
        }
        features = {
            "parse_status": "parsed",
            "candidate_alignment_status": "candidate_alignment_matched",
            "operator_ids": ["native:buffer", "native:fixgeometries"],
            "dependency_edges": [[0, 1]],
            "control_flow_kinds": ["for"],
            "downstream_data_transform_calls": ["custom_helper"],
            "workflow_unit_scope": "whole_processing_scope",
        }
        decision = route_candidate(row, features)
        self.assertEqual(decision.rule_id, "recover-control-flow-v1")
        self.assertEqual(decision.action, "recover_call_graph")


if __name__ == "__main__":
    unittest.main()
