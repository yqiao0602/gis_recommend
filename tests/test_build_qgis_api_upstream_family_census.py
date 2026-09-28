from __future__ import annotations

import unittest

from scripts.build_qgis_api_upstream_family_census import (
    build_anchor_candidate_units,
    build_anchor_census,
    build_discovery_census,
    build_family_census,
    build_reviewed_exclusion_provenance,
    normalize_call_name,
    reviewed_candidate_ids,
)


def _row(
    candidate_id: str,
    authority: str,
    calls: list[str],
    *,
    status: str = "resolved_local_call_chain",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "source_authority_key": f"normalized_source_body_sha256:{authority}",
        "slice_status": status,
        "upstream_calls": [
            {"call_name": call, "call_family": "geometry_method"}
            for call in calls
        ],
        "upstream_signature": [call.lower() for call in calls],
        "training_row_emitted": False,
    }


class BuildQgisApiUpstreamFamilyCensusTest(unittest.TestCase):
    def test_normalizes_receivers_but_retains_qgis_static_factory(self) -> None:
        self.assertEqual(normalize_call_name("feature.geometry"), "geometry")
        self.assertEqual(normalize_call_name("f.geometry"), "geometry")
        self.assertEqual(
            normalize_call_name("QgsGeometry.fromPointXY"),
            "qgsgeometry.frompointxy",
        )

    def test_collects_original_identity_from_reviewed_candidates(self) -> None:
        reviewed = reviewed_candidate_ids(
            [
                {"candidate_id": "generated", "baseline_candidate_id": "original"},
                {"candidate_id": "sidecar"},
            ]
        )

        self.assertEqual(reviewed, {"original", "sidecar"})

    def test_ranks_resolved_families_by_unique_source_authority(self) -> None:
        rows = [
            _row("a", "body-a", ["feature.geometry", "custom.buildShape"]),
            _row("b", "body-b", ["f.geometry", "other.buildShape"]),
            _row("c", "body-c", ["geom.centroid"]),
            _row(
                "d",
                "body-d",
                ["payload.dynamic"],
                status="ambiguous_multiple_reaching_definitions",
            ),
            _row("reviewed", "body-e", ["feature.geometry", "custom.buildShape"]),
        ]

        families, priorities, excluded, summary = build_family_census(
            rows,
            excluded_candidate_ids={"reviewed"},
            minimum_authority_support=2,
        )

        self.assertEqual(len(excluded), 1)
        self.assertEqual(summary["remaining_units"], 4)
        self.assertEqual(summary["resolved_units"], 3)
        self.assertEqual(summary["priority_family_count"], 1)
        self.assertEqual(priorities[0]["normalized_signature"], ["geometry", "buildshape"])
        self.assertEqual(priorities[0]["source_authority_count"], 2)
        self.assertEqual(priorities[0]["review_priority"], "calibration_required")
        centroid = next(
            family
            for family in families
            if family["normalized_signature"] == ["centroid"]
        )
        self.assertEqual(
            centroid["review_priority"],
            "defer_known_training_semantic_overlap",
        )
        self.assertEqual(summary["training_rows_emitted"], 0)

    def test_defers_geometry_access_and_factory_only_families(self) -> None:
        rows = [
            _row("a", "body-a", ["feature.geometry"]),
            _row("b", "body-b", ["f.geometry"]),
            _row("c", "body-c", ["QgsGeometry.fromWkt"]),
            _row("d", "body-d", ["QgsGeometry.fromWkt"]),
        ]

        families, priorities, _, summary = build_family_census(
            rows,
            excluded_candidate_ids=set(),
            minimum_authority_support=2,
        )

        self.assertEqual(priorities, [])
        self.assertEqual(summary["priority_family_count"], 0)
        self.assertEqual(
            {family["review_priority"] for family in families},
            {"defer_support_only_signature"},
        )

    def test_aggregates_receiver_independent_semantic_anchors(self) -> None:
        rows = [
            _row(
                "a",
                "body-a",
                [
                    "source.sourceExtent",
                    "random.random",
                    "QgsGeometry.fromPointXY",
                ],
            ),
            _row(
                "b",
                "body-b",
                [
                    "geom.boundingBox",
                    "random.random",
                    "QgsGeometry.fromPoint",
                ],
            ),
            _row(
                "c",
                "body-c",
                ["math.cos", "math.sin", "QgsGeometry.fromPolygonXY"],
            ),
            _row(
                "reviewed",
                "body-d",
                [
                    "source.sourceExtent",
                    "random.random",
                    "QgsGeometry.fromPointXY",
                ],
            ),
        ]

        anchors, priorities, summary = build_anchor_census(
            rows,
            excluded_candidate_ids={"reviewed"},
            minimum_authority_support=2,
        )

        self.assertEqual(len(priorities), 1)
        self.assertEqual(priorities[0]["anchor_family"], "random_point_construction")
        self.assertEqual(priorities[0]["source_authority_count"], 2)
        candidate_units = build_anchor_candidate_units(
            rows,
            excluded_candidate_ids={"reviewed"},
            priority_anchor_families={"random_point_construction"},
        )
        self.assertEqual(len(candidate_units), 2)
        self.assertEqual(
            candidate_units[0]["semantic_anchor_families"],
            ["random_point_construction"],
        )
        self.assertFalse(candidate_units[0]["training_row_emitted"])
        trig = next(
            anchor
            for anchor in anchors
            if anchor["anchor_family"] == "trigonometric_polygon_construction"
        )
        self.assertEqual(trig["review_priority"], "defer_support_below_threshold")
        self.assertEqual(summary["training_rows_emitted"], 0)

    def test_preserves_reviewed_family_provenance_on_exclusion(self) -> None:
        provenance = build_reviewed_exclusion_provenance(
            [
                (
                    "geometry_return_alias_candidates",
                    [{"candidate_id": "shared"}],
                ),
                (
                    "random_point_reviewed_units",
                    [{"baseline_candidate_id": "shared"}],
                ),
            ]
        )
        _, _, excluded, _ = build_family_census(
            [_row("shared", "body-a", ["maker.create"])],
            excluded_candidate_ids=set(provenance),
            excluded_candidate_provenance=provenance,
            minimum_authority_support=1,
        )

        self.assertEqual(
            excluded[0]["family_exclusion_reason"],
            "previously_reviewed_family",
        )
        self.assertEqual(
            excluded[0]["reviewed_family_provenance"],
            ["geometry_return_alias_candidates", "random_point_reviewed_units"],
        )
        self.assertFalse(excluded[0]["training_row_emitted"])

    def test_discovers_shared_call_pairs_by_unique_source_authority(self) -> None:
        rows = [
            _row("a", "body-a", ["feature.geometry", "maker.create", "sink.write"]),
            _row("b", "body-b", ["f.geometry", "maker.create", "sink.write"]),
            _row("c", "body-c", ["f.geometry", "maker.create", "helper.log"]),
            _row("duplicate-a", "body-a", ["f.geometry", "maker.create", "sink.write"]),
        ]

        calls, pairs, summary = build_discovery_census(
            rows,
            excluded_candidate_ids=set(),
            minimum_authority_support=2,
        )

        create = next(row for row in calls if row["normalized_call"] == "create")
        self.assertEqual(create["source_authority_count"], 3)
        create_write = next(
            row
            for row in pairs
            if row["normalized_call_cooccurrence"] == ["create", "write"]
        )
        self.assertEqual(create_write["source_authority_count"], 2)
        self.assertEqual(create_write["review_priority"], "calibration_required")
        self.assertEqual(summary["priority_cooccurrence_count"], 2)
        self.assertEqual(summary["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
