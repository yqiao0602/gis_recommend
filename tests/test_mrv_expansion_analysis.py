from __future__ import annotations

import unittest

from scripts.analyze_mrv_expansion import (
    analyze_rows,
    classify_pair,
    load_taxonomy,
    map_rejection_types,
)


class MRVExpansionAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.taxonomy = load_taxonomy(None)
        self.token_meta = {
            25: {"l3_name": "Clip Raster by Geometry"},
            28: {"l3_name": "Select Bands"},
            29: {"l3_name": "Update Mask"},
            34: {"l3_name": "Arithmetic & Math"},
            35: {"l3_name": "Logical & Comparison"},
            50: {"l3_name": "Filter by Date Range"},
            53: {"l3_name": "Filter by Metadata Property"},
            54: {"l3_name": "Filter by Spatial Bounds"},
            56: {"l3_name": "Temporal Reducer"},
        }

    def test_filter_filter_pair_is_low_risk(self) -> None:
        result = classify_pair([53, 50], self.token_meta, self.taxonomy)

        self.assertEqual(result["equivalence_family"], "filter_filter")
        self.assertEqual(result["risk_level"], "low")
        self.assertIn("independent_collection_filters", result["conditional_constraints"])

    def test_select_filter_pair_is_conditional_medium_risk(self) -> None:
        result = classify_pair([53, 28], self.token_meta, self.taxonomy)

        self.assertEqual(result["equivalence_family"], "select_filter")
        self.assertEqual(result["risk_level"], "medium")
        self.assertIn("collection_image_boundary", result["hidden_dependency"])

    def test_mask_or_threshold_pair_is_high_risk(self) -> None:
        result = classify_pair([29, 35], self.token_meta, self.taxonomy)

        self.assertEqual(result["equivalence_family"], "mask_threshold_or_logic")
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("mask_or_threshold_semantics", result["semantic_risk_drivers"])

    def test_qgis_landing_failure_is_auxiliary_not_primary_rejection(self) -> None:
        mapped = map_rejection_types(
            rejection_reasons=[],
            landing_rejection_reasons=["qgis_chain_unusable"],
            risk_level="low",
        )

        self.assertEqual(mapped["primary_rejection_types"], [])
        self.assertEqual(mapped["auxiliary_rejection_types"], ["landing_only_failure"])

    def test_analyze_rows_preserves_total_counts_across_family_and_risk(self) -> None:
        rows = [
            {
                "variant_id": "a",
                "swapped_pair": "[53, 50]",
                "auto_label": "verified_equivalent_candidate",
                "registry_eligible": True,
                "rejection_reasons": [],
                "landing_rejection_reasons": ["qgis_chain_unusable"],
                "passed_checks": ["semantic_usable"],
            },
            {
                "variant_id": "b",
                "swapped_pair": "[29, 35]",
                "auto_label": "invalid_variant",
                "registry_eligible": False,
                "rejection_reasons": ["sensitive_swap"],
                "landing_rejection_reasons": [],
                "passed_checks": [],
            },
        ]

        result = analyze_rows(rows, self.token_meta, self.taxonomy)

        self.assertEqual(result["summary"]["variant_count"], 2)
        self.assertEqual(sum(row["count"] for row in result["family_summary"]), 2)
        self.assertEqual(sum(row["count"] for row in result["risk_summary"]), 2)
        family_rows = {row["equivalence_family"]: row for row in result["family_summary"]}
        self.assertEqual(family_rows["filter_filter"]["verified_equivalent_candidate_count"], 1)
        self.assertEqual(family_rows["filter_filter"]["auto_pass_rate"], 1.0)
        rejection_types = {row["rejection_type"]: row["count"] for row in result["rejection_summary"]}
        self.assertEqual(rejection_types["high_risk_family"], 1)
        self.assertEqual(rejection_types["landing_only_failure"], 1)


if __name__ == "__main__":
    unittest.main()
