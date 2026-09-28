from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_source_semantics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adjudicate_qgis_mapping_gap_source_semantics", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(operator_id: str, records: int) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "review_route": "pending_source_semantic_review",
        "single_gap_records": records,
        "samples": [
            {
                "record_id": f"record-{index}",
                "source_sha256": f"sha-{operator_id}-{index}",
                "source_verification": "verified_sha256",
            }
            for index in range(3)
        ],
    }


def _queue() -> list[dict[str, object]]:
    return [
        _row("native:splitvectorlayer", 9),
        _row("grass7:v.clean", 8),
        _row("native:rasterlayerstatistics", 8),
        _row("native:package", 7),
        _row("native:geometrybyexpression", 6),
        _row("gdal:gdal2tiles", 6),
        _row("qgis:randompointsalongline", 6),
        _row("qgis:eliminateselectedpolygons", 4),
        _row("native:shortestpathpointtopoint", 4),
        _row("native:createpointslayerfromtable", 4),
    ]


def test_source_semantic_adjudication_keeps_four_distinct_outcomes() -> None:
    taxonomy = {
        "taxonomy_id": "stable101",
        "l3_families": [
            {"l3_code": "L3_03_02_05", "l3_name": "Global Statistics", "token_id": 33},
            {"l3_code": "L3_02_06_06", "l3_name": "Sample Points", "token_id": 97},
        ],
    }

    rows, summary = MODULE.adjudicate_source_semantics(_queue(), taxonomy)

    decisions = {row["operator_id"]: row for row in rows}
    assert summary["accepted_existing_l3_count"] == 2
    assert summary["new_class_gap_count"] == 5
    assert summary["parameter_conditioned_count"] == 2
    assert summary["support_export_boundary_count"] == 1
    assert summary["reviewed_single_gap_records"] == 62
    assert decisions["native:rasterlayerstatistics"]["candidate_l3_code"] == "L3_03_02_05"
    assert decisions["qgis:randompointsalongline"]["candidate_l3_code"] == "L3_02_06_06"
    assert decisions["grass7:v.clean"]["required_resolver"] == "literal_tool_enum"
    assert decisions["native:geometrybyexpression"]["required_resolver"] == "qgis_expression_semantics"
    assert decisions["native:package"]["decision"] == "defer_support_export_boundary"
    assert summary["training_rows_emitted"] == 0


def test_source_semantic_adjudication_requires_all_ten_operators() -> None:
    with pytest.raises(ValueError, match="ten reviewed operators"):
        MODULE.adjudicate_source_semantics(_queue()[:-1], {"l3_families": []})
