from __future__ import annotations

import unittest

from scripts.build_qgis_api_semantic_family_census import (
    classify_authority,
    select_source_disjoint_review,
)


def _row(
    key: str,
    methods: list[str],
    *,
    explicit_sink: int = 1,
    max_gap: int = 10,
    span: int = 20,
) -> dict:
    return {
        "record_id": key,
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "normalized_source_body_sha256": key,
        "source_sha256": f"source-{key}",
        "source_root_id": "fixture",
        "explicit_gis_sink_step_count": explicit_sink,
        "max_adjacent_call_gap": max_gap,
        "call_line_span": span,
        "steps": [
            {
                "name": f"receiver.{method}",
                "line_start": index + 1,
                "line_end": index + 1,
                "pattern_names": ["field_attribute_edit"],
            }
            for index, method in enumerate(methods)
        ],
    }


class BuildQgisApiSemanticFamilyCensusTest(unittest.TestCase):
    def test_classifies_strict_field_schema_addition_as_existing_l3_proposal(self) -> None:
        classified = classify_authority(
            _row("a", ["addAttributes", "updateFields", "addFeature"])
        )

        match = next(
            item
            for item in classified["semantic_family_matches"]
            if item["family_id"] == "field_schema_addition"
        )
        self.assertEqual(match["boundary_status"], "strict_review_eligible")
        self.assertEqual(match["proposed_l3_code"], "L3_01_02_01")
        self.assertEqual(match["mapping_status"], "existing_l3_proposal")
        self.assertFalse(classified["training_row_emitted"])

    def test_fail_closes_wide_or_sinkless_field_schema_matches(self) -> None:
        sinkless = classify_authority(
            _row(
                "sinkless",
                ["addAttribute", "updateFields"],
                explicit_sink=0,
            )
        )
        wide = classify_authority(
            _row(
                "wide",
                ["addAttributes", "updateFields", "addFeature"],
                max_gap=21,
            )
        )

        self.assertEqual(
            sinkless["semantic_family_matches"][0]["boundary_status"],
            "deferred_no_explicit_gis_sink",
        )
        self.assertEqual(
            wide["semantic_family_matches"][0]["boundary_status"],
            "deferred_wide_task_scope",
        )

    def test_spatial_index_query_requires_taxonomy_review(self) -> None:
        classified = classify_authority(
            _row("spatial", ["QgsSpatialIndex", "intersects", "addFeature"])
        )

        match = classified["semantic_family_matches"][0]
        self.assertEqual(match["family_id"], "spatial_index_intersection_query")
        self.assertEqual(match["mapping_status"], "taxonomy_review_required")
        self.assertIsNone(match["proposed_l3_code"])

    def test_review_split_is_source_disjoint_and_deterministic(self) -> None:
        rows = [
            classify_authority(
                _row(str(index), ["addAttributes", "updateFields", "addFeature"])
            )
            for index in range(12)
        ]

        first = select_source_disjoint_review(
            rows,
            family_id="field_schema_addition",
            per_split=4,
            seed=20260804,
        )
        second = select_source_disjoint_review(
            rows,
            family_id="field_schema_addition",
            per_split=4,
            seed=20260804,
        )

        self.assertEqual(first, second)
        calibration, holdout = first
        self.assertEqual(len(calibration), 4)
        self.assertEqual(len(holdout), 4)
        self.assertTrue(
            {row["source_sha256"] for row in calibration}.isdisjoint(
                row["source_sha256"] for row in holdout
            )
        )
        self.assertTrue(
            {row["normalized_source_body_sha256"] for row in calibration}.isdisjoint(
                row["normalized_source_body_sha256"] for row in holdout
            )
        )


if __name__ == "__main__":
    unittest.main()
