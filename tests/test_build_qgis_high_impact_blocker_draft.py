import unittest

from scripts.build_qgis_high_impact_blocker_draft import (
    DEFAULT_HIGH_IMPACT_DECISIONS,
    analyze_scenarios,
    build_high_impact_mappings,
)


class HighImpactBlockerDraftTest(unittest.TestCase):
    def test_build_mappings_separates_conservative_and_support_boundary(self) -> None:
        stable_codes = {"L3_STABLE_EXPORT"}
        legacy_codes = {
            "L3_REPROJECT",
            "L3_REPAIR",
            "L3_RASTER_VECTOR",
            "L3_INDEX",
        }
        decisions = [
            {
                "operator_id": "native:reprojectlayer",
                "candidate_l3_code": "L3_REPROJECT",
                "mapping_kind": "restore_old350_l3",
                "scenario": "conservative",
            },
            {
                "operator_id": "native:createspatialindex",
                "candidate_l3_code": "L3_INDEX",
                "mapping_kind": "restore_old350_l3",
                "scenario": "support_boundary",
            },
            {
                "operator_id": "native:saveselectedfeatures",
                "candidate_l3_code": "L3_STABLE_EXPORT",
                "mapping_kind": "alias_existing_stable94",
                "scenario": "support_boundary",
            },
        ]

        result = build_high_impact_mappings(
            decisions,
            stable_codes=stable_codes,
            legacy_codes=legacy_codes,
        )

        self.assertEqual(result["conservative_mapping"], {"native:reprojectlayer": "L3_REPROJECT"})
        self.assertEqual(
            result["extended_mapping"],
            {
                "native:reprojectlayer": "L3_REPROJECT",
                "native:createspatialindex": "L3_INDEX",
                "native:saveselectedfeatures": "L3_STABLE_EXPORT",
            },
        )
        self.assertEqual(result["new_legacy_codes_conservative"], ["L3_REPROJECT"])
        self.assertEqual(result["new_legacy_codes_extended"], ["L3_INDEX", "L3_REPROJECT"])

    def test_scenarios_count_unique_chains_without_treating_native_bridge_as_l3(self) -> None:
        records = [
            {"qgis_ops": ["native:a"]},
            {"qgis_ops": ["native:a", "native:reprojectlayer"]},
            {"qgis_ops": ["native:a", "native:reprojectlayer"]},
            {"qgis_ops": ["native:a", "native:createspatialindex"]},
            {"qgis_ops": ["native:a", "native:saveselectedfeatures"]},
            {"qgis_ops": ["native:a", "gdal:unknown"]},
        ]
        baseline = {"native:a": "L3_A"}
        stable98 = {"native:a": "L3_A"}
        conservative = {"native:reprojectlayer": "L3_REPROJECT"}
        extended = {
            "native:reprojectlayer": "L3_REPROJECT",
            "native:createspatialindex": "L3_INDEX",
            "native:saveselectedfeatures": "L3_EXPORT",
        }

        summary = analyze_scenarios(
            records,
            baseline_mapping=baseline,
            stable98_mapping=stable98,
            conservative_mapping=conservative,
            extended_mapping=extended,
        )

        self.assertEqual(summary["baseline"], {"complete_records": 1, "complete_unique_chains": 1})
        self.assertEqual(summary["stable98_draft"], {"complete_records": 1, "complete_unique_chains": 1})
        self.assertEqual(summary["high_impact_conservative"], {"complete_records": 3, "complete_unique_chains": 2})
        self.assertEqual(summary["high_impact_extended"], {"complete_records": 5, "complete_unique_chains": 4})
        self.assertEqual(summary["increment_vs_stable98_conservative"], {"records": 2, "unique_chains": 1})
        self.assertEqual(summary["increment_vs_stable98_extended"], {"records": 4, "unique_chains": 3})

    def test_default_decisions_cover_expected_high_impact_blockers(self) -> None:
        self.assertEqual(
            {row["operator_id"] for row in DEFAULT_HIGH_IMPACT_DECISIONS},
            {
                "native:reprojectlayer",
                "native:fixgeometries",
                "gdal:polygonize",
                "gdal:rasterize",
                "native:createspatialindex",
                "native:saveselectedfeatures",
            },
        )


if __name__ == "__main__":
    unittest.main()
