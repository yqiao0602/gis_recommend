from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_experimental_candidates.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adjudicate_qgis_mapping_gap_experimental_candidates", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _queue_row(operator_id: str, candidate_l3: str) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "review_route": "experimental_114_candidate_not_admitted",
        "experimental_114_candidate_l3": candidate_l3,
        "single_gap_records": 5,
        "samples": [
            {
                "record_id": f"record-{index}",
                "source_sha256": f"sha-{operator_id}-{index}",
                "source_verification": "verified_sha256",
            }
            for index in range(3)
        ],
    }


def test_adjudicates_one_existing_l3_and_two_new_class_proposals() -> None:
    queue = [
        _queue_row("native:pixelstopolygons", "L3_01_09_07"),
        _queue_row("native:smoothgeometry", "L3_02_05_02"),
        _queue_row("qgis:delaunaytriangulation", "L3_06_01_02"),
    ]
    stable = {
        "taxonomy_id": "stable101",
        "l3_families": [
            {"l3_code": "L3_01_09_03", "l3_name": "Raster-Vector Conversion", "token_id": 99}
        ],
    }
    experimental = {
        "profile": "qgis_l3_v1_114",
        "added_classes": [
            {"code": "L3_01_09_07", "name": "Polygonize Raster", "token_id": 100},
            {"code": "L3_02_05_02", "name": "Smooth", "token_id": 105},
            {"code": "L3_06_01_02", "name": "Delaunay Triangulation", "token_id": 113},
        ],
    }

    rows, summary = MODULE.adjudicate_candidates(queue, stable, experimental)

    decisions = {row["operator_id"]: row for row in rows}
    assert summary["accepted_existing_l3_count"] == 1
    assert summary["new_class_proposal_count"] == 2
    assert decisions["native:pixelstopolygons"]["candidate_l3_code"] == "L3_01_09_03"
    assert decisions["native:smoothgeometry"]["candidate_l3_code"] == "L3_02_05_02"
    assert decisions["qgis:delaunaytriangulation"]["candidate_l3_code"] == "L3_06_01_02"
    assert summary["training_rows_emitted"] == 0


def test_fails_closed_when_experimental_candidate_does_not_match_queue() -> None:
    queue = [_queue_row("native:smoothgeometry", "L3_WRONG")]

    with pytest.raises(ValueError, match="three reviewed operators"):
        MODULE.adjudicate_candidates(queue, {"l3_families": []}, {"added_classes": []})
