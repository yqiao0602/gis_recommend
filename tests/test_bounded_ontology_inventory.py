from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _payload(primary_l3: str, mapping_type: str = "direct", ambiguity: bool = False, candidates: int = 1) -> dict:
    return {
        "primary_l3": primary_l3,
        "mapping_type": mapping_type,
        "has_ambiguity": ambiguity,
        "num_candidates": candidates,
        "mapping_confidence": 0.95,
        "source": "unit",
        "all_candidates": [{"l3_code": primary_l3, "confidence": 0.95, "role": mapping_type, "execution_order": 1}],
    }


class BoundedOntologyInventoryTests(unittest.TestCase):
    def test_exact_pair_requires_same_l3_safe_mappings_and_action_evidence(self):
        from scripts.build_bounded_ontology_inventory import classify_platform_pair

        left = {"platform": "gee", "operator": "ee.Geometry.buffer", **_payload("L3_02_01_01")}
        right = {"platform": "qgis", "operator": "Buffer vectors", **_payload("L3_02_01_01", "audit_v2_override")}
        l3_info = {
            "l3_code": "L3_02_01_01",
            "l3_name": "Buffer",
            "l3_description": "Creates buffer polygons around input features at a specified distance.",
            "l2_code": "L2_02_01",
            "l2_name": "Proximity Analysis",
            "l1_code": "L1_02",
            "l1_name": "Vector Analysis",
        }

        row = classify_platform_pair(left, right, l3_info, qgis_io_types={"Buffer vectors": {"inputs": ["vector"], "outputs": ["vector"]}})

        self.assertEqual(row["classification"], "exact")
        self.assertTrue(row["execution_constraints"]["io_compatibility"]["compatible"])
        self.assertIn("distance/radius", row["execution_constraints"]["parameter_preservation"])
        self.assertEqual(row["governance"]["runtime_authority"], "inventory_only")

    def test_same_l2_different_l3_is_ambiguous_not_semantic_equivalence(self):
        from scripts.build_bounded_ontology_inventory import classify_platform_pair

        left = {"platform": "qgis", "operator": "Intersect", **_payload("L3_02_02_01", "audit_v2_override")}
        right = {"platform": "qgis", "operator": "Union", **_payload("L3_02_02_02", "audit_v2_override")}
        l3_info = {
            "l3_code": "L3_02_02_01",
            "l3_name": "Intersect",
            "l3_description": "Computes geometric intersection of input features.",
            "l2_code": "L2_02_02",
            "l2_name": "Overlay Analysis",
            "l1_code": "L1_02",
            "l1_name": "Vector Analysis",
        }

        row = classify_platform_pair(left, right, l3_info, qgis_io_types={})

        self.assertEqual(row["classification"], "ambiguous")
        self.assertIn("different_l3", row["risk_flags"])
        self.assertFalse(row["safe_for_equivalence_claim"])

    def test_execution_sensitive_pair_is_not_promoted_to_exact(self):
        from scripts.build_bounded_ontology_inventory import classify_platform_pair

        left = {"platform": "gee", "operator": "ee.image.rename", **_payload("L3_01_02_03", "manual_override")}
        right = {"platform": "qgis", "operator": "Assign projection", **_payload("L3_01_02_03", "audit_v2_override")}
        l3_info = {
            "l3_code": "L3_01_02_03",
            "l3_name": "Alter Field",
            "l3_description": "Modifies field properties such as name alias or data type.",
            "l2_code": "L2_01_02",
            "l2_name": "Schema Management",
            "l1_code": "L1_01",
            "l1_name": "Data Management",
        }

        row = classify_platform_pair(left, right, l3_info, qgis_io_types={"Assign projection": {"inputs": ["raster", "vector"], "outputs": ["raster", "vector"]}})

        self.assertEqual(row["classification"], "execution-sensitive")
        self.assertIn("weak_action_evidence", row["risk_flags"])
        self.assertTrue(row["execution_constraints"]["crs_sensitivity"])
        self.assertFalse(row["safe_for_equivalence_claim"])

    def test_missing_gdal_and_arcgis_assets_are_marked_unsupported(self):
        from scripts.build_bounded_ontology_inventory import build_unsupported_platform_pair_rows

        rows = build_unsupported_platform_pair_rows(["gee", "qgis"], requested_platforms=["gee", "qgis", "gdal", "arcgis"])
        pair_names = {row["platform_pair"] for row in rows}

        self.assertIn("gee<->gdal", pair_names)
        self.assertIn("qgis<->gdal", pair_names)
        self.assertIn("gee<->arcgis", pair_names)
        self.assertTrue(all(row["classification"] == "unsupported" for row in rows))
        self.assertTrue(all(row["source_status"] == "not_available_in_current_artifacts" for row in rows))

    def test_unsafe_registry_preserves_failed_equivalence_findings(self):
        from scripts.build_bounded_ontology_inventory import build_unsafe_mapping_registry

        safe_table = {
            "rows": [
                {"equivalence_type": "alias_equivalence", "subtype": "exact_alias_or_naming_variant", "decision": "stable", "false_equivalence_rate": 0.0},
                {"equivalence_type": "operator_family_equivalence", "subtype": "same_l2_family_substitution", "decision": "execution-breaking", "false_equivalence_rate": 0.68},
                {"equivalence_type": "workflow_equivalence", "subtype": "bridge_expansion", "decision": "unsafe", "false_equivalence_rate": 0.96},
            ]
        }

        registry = build_unsafe_mapping_registry(safe_table, ambiguous_pairs=[])
        keys = {(row["equivalence_type"], row["subtype"]) for row in registry["unsafe_mappings"]}

        self.assertIn(("operator_family_equivalence", "same_l2_family_substitution"), keys)
        self.assertIn(("workflow_equivalence", "bridge_expansion"), keys)
        self.assertNotIn(("alias_equivalence", "exact_alias_or_naming_variant"), keys)

    def test_workflow_equivalence_registry_is_narrow_and_marks_reorder_unsafe(self):
        from scripts.build_bounded_ontology_inventory import build_workflow_equivalence_registry

        registry = build_workflow_equivalence_registry()
        safe_names = {row["name"] for row in registry["safe_equivalence_examples"]}
        unsafe_names = {row["name"] for row in registry["unsafe_or_unproven_examples"]}

        self.assertIn("operator_identity_sequence", safe_names)
        self.assertIn("case_only_operator_alias_sequence", safe_names)
        self.assertIn("adjacent_reorder", unsafe_names)
        self.assertIn("bridge_expansion", unsafe_names)
        self.assertNotIn("adjacent_reorder", safe_names)

    def test_bounded_ontology_builder_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/build_bounded_ontology_inventory.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--output-dir", result.stdout)
        self.assertIn("--controlled-equivalence-table", result.stdout)


if __name__ == "__main__":
    unittest.main()
