from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_capability_bridges.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adjudicate_qgis_mapping_gap_capability_bridges", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
adjudicate_bridges = MODULE.adjudicate_bridges
adjudicate_top20 = MODULE.adjudicate_top20


def _queue_row(operator_id: str, bridge: str) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "review_route": "existing_bridge_needs_taxonomy_review",
        "crosswalk_l3_code": bridge,
        "single_gap_records": 3,
        "samples": [
            {
                "record_id": f"record-{index}",
                "source_sha256": f"sha-{operator_id}-{index}",
                "source_verification": "verified_sha256",
            }
            for index in range(3)
        ],
    }


def _taxonomy() -> dict[str, object]:
    return {
        "taxonomy_id": "stable101_authority_v1",
        "l3_families": [
            {"l3_code": "L3_01_02_06", "l3_name": "Calculate Field", "token_id": 4},
            {"l3_code": "L3_01_09_03", "l3_name": "Raster-Vector Conversion", "token_id": 99},
            {"l3_code": "L3_02_06_06", "l3_name": "Sample Points", "token_id": 97},
        ],
    }


def _queue() -> list[dict[str, object]]:
    return [
        _queue_row("native:explodelines", "qgis_native:line_explode"),
        _queue_row("native:pointsalonglines", "qgis_native:point_sampling"),
        _queue_row("gdal:contour", "qgis_native:contour_generation"),
        _queue_row("native:splitwithlines", "qgis_native:line_split"),
        _queue_row("native:pixelstopoints", "qgis_native:pixels_to_points"),
        _queue_row("gdal:proximity", "qgis_native:raster_proximity"),
        _queue_row("qgis:exportaddgeometrycolumns", "qgis_native:export_geom_columns"),
    ]


def test_adjudicate_bridges_separates_existing_l3_from_taxonomy_gaps() -> None:
    rows, summary = adjudicate_bridges(_queue(), _taxonomy())

    decisions = {row["operator_id"]: row for row in rows}
    assert summary["accepted_existing_l3_count"] == 4
    assert summary["deferred_taxonomy_gap_count"] == 3
    assert summary["training_rows_emitted"] == 0
    assert decisions["native:pointsalonglines"]["candidate_l3_code"] == "L3_02_06_06"
    assert decisions["gdal:contour"]["candidate_l3_code"] == "L3_01_09_03"
    assert decisions["native:pixelstopoints"]["candidate_l3_code"] == "L3_01_09_03"
    assert decisions["qgis:exportaddgeometrycolumns"]["candidate_l3_code"] == "L3_01_02_06"
    assert decisions["native:explodelines"]["decision"] == "defer_new_taxonomy_class"
    assert decisions["native:splitwithlines"]["decision"] == "defer_new_taxonomy_class"
    assert decisions["gdal:proximity"]["decision"] == "defer_new_taxonomy_class"


def test_adjudicate_bridges_fails_closed_on_unverified_source_sample() -> None:
    queue = _queue()
    queue[0]["samples"][0]["source_verification"] = "not_checked"  # type: ignore[index]

    with pytest.raises(ValueError, match="verified source samples"):
        adjudicate_bridges(queue, _taxonomy())


def test_adjudicate_top20_keeps_nonstable_routes_out_of_mapping_admission() -> None:
    routes = {
        "native:explodelines": "existing_bridge_needs_taxonomy_review",
        "native:pointsalonglines": "existing_bridge_needs_taxonomy_review",
        "gdal:contour": "existing_bridge_needs_taxonomy_review",
        "native:splitwithlines": "existing_bridge_needs_taxonomy_review",
        "native:splitvectorlayer": "pending_source_semantic_review",
        "grass7:v.clean": "pending_source_semantic_review",
        "native:rasterlayerstatistics": "pending_source_semantic_review",
        "native:package": "pending_source_semantic_review",
        "native:pixelstopoints": "existing_bridge_needs_taxonomy_review",
        "native:geometrybyexpression": "pending_source_semantic_review",
        "gdal:proximity": "existing_bridge_needs_taxonomy_review",
        "gdal:gdal2tiles": "pending_source_semantic_review",
        "qgis:randompointsalongline": "pending_source_semantic_review",
        "qgis:exportaddgeometrycolumns": "existing_bridge_needs_taxonomy_review",
        "native:pixelstopolygons": "experimental_114_candidate_not_admitted",
        "native:smoothgeometry": "experimental_114_candidate_not_admitted",
        "qgis:delaunaytriangulation": "experimental_114_candidate_not_admitted",
        "qgis:eliminateselectedpolygons": "pending_source_semantic_review",
        "native:shortestpathpointtopoint": "pending_source_semantic_review",
        "native:createpointslayerfromtable": "pending_source_semantic_review",
    }
    queue = []
    for rank, (operator_id, route) in enumerate(routes.items(), start=1):
        row = _queue_row(operator_id, "")
        row.update({"rank": rank, "review_route": route, "single_gap_records": 1})
        queue.append(row)
    stable = _taxonomy()
    stable["l3_families"].append(  # type: ignore[union-attr]
        {"l3_code": "L3_03_02_05", "l3_name": "Global Statistics", "token_id": 33}
    )
    experimental = {
        "profile": "qgis_l3_v1_114_experimental",
        "added_classes": [
            {"code": "L3_02_05_02", "name": "Smooth", "token_id": 105},
            {"code": "L3_06_01_02", "name": "Delaunay Triangulation", "token_id": 113},
        ],
    }

    rows, summary = adjudicate_top20(queue, stable, experimental)

    decisions = {row["operator_id"]: row for row in rows}
    assert summary["reviewed_operator_count"] == 20
    assert summary["accepted_existing_l3_count"] == 7
    assert summary["new_taxonomy_proposal_count"] == 2
    assert summary["deferred_new_taxonomy_count"] == 7
    assert summary["parameter_dependent_count"] == 2
    assert summary["support_export_sidecar_count"] == 2
    assert summary["training_rows_emitted"] == 0
    assert decisions["native:rasterlayerstatistics"]["candidate_l3_code"] == "L3_03_02_05"
    assert decisions["qgis:randompointsalongline"]["candidate_l3_code"] == "L3_02_06_06"
    assert decisions["native:pixelstopolygons"]["candidate_l3_code"] == "L3_01_09_03"
    assert decisions["native:smoothgeometry"]["taxonomy_admission"] == "proposal_only_new_class"
    assert decisions["native:smoothgeometry"]["candidate_token_id"] is None
    assert decisions["native:smoothgeometry"]["reference_experimental_token_id"] == 105
    assert decisions["qgis:delaunaytriangulation"]["taxonomy_admission"] == "proposal_only_new_class"
    assert decisions["native:geometrybyexpression"]["decision"] == "defer_parameter_dependent"
    assert decisions["native:package"]["decision"] == "route_support_export_sidecar"
