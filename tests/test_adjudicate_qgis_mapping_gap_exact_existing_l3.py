from __future__ import annotations

from scripts.adjudicate_qgis_mapping_gap_exact_existing_l3 import (
    adjudicate_exact_existing_l3,
)


def _queue_row(operator_id: str, samples: int) -> dict:
    return {
        "operator_id": operator_id,
        "single_gap_records": 4,
        "all_gap_records": 6,
        "samples": [
            {
                "record_id": f"{operator_id}-{index}",
                "source_sha256": f"{index + 1:064x}",
                "source_verification": "verified_sha256",
            }
            for index in range(samples)
        ],
    }


def test_grants_only_exact_existing_l3_with_three_verified_sources() -> None:
    queue = [
        _queue_row("native:rasterize", 3),
        _queue_row("native:convexhull", 2),
        _queue_row("native:boundary", 3),
    ]
    taxonomy = {
        "l3_families": [
            {
                "l3_code": "L3_01_09_03",
                "l3_name": "Raster-Vector Conversion",
                "token_id": 99,
            },
            {
                "l3_code": "L3_02_05_12",
                "l3_name": "Minimum Bounding Geometry",
                "token_id": 19,
            },
        ]
    }
    decisions = {
        "native:rasterize": ("L3_01_09_03", "Rasterizes vector features."),
        "native:convexhull": ("L3_02_05_12", "Builds a convex hull."),
        "native:boundary": ("", "Boundary output depends on input geometry type."),
    }

    rows, delta, summary = adjudicate_exact_existing_l3(
        queue, taxonomy, decisions=decisions, minimum_verified_sources=3
    )

    by_operator = {row["operator_id"]: row for row in rows}
    assert by_operator["native:rasterize"]["decision"] == "accept_existing_stable_l3_proposal"
    assert by_operator["native:rasterize"]["source_sample_count"] == 3
    assert by_operator["native:rasterize"]["verified_source_count"] == 3
    assert by_operator["native:convexhull"]["decision"] == "defer_insufficient_verified_support"
    assert by_operator["native:boundary"]["decision"] == "defer_no_exact_stable_l3"
    assert delta["alias_mappings"] == {"native:rasterize": "L3_01_09_03"}
    assert delta["mapping_admission"] == "proposal_only"
    assert summary["accepted_operator_count"] == 1
    assert summary["training_rows_emitted"] == 0
