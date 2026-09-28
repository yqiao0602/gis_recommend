from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "resolve_qgis_geometry_expression.py"
SPEC = importlib.util.spec_from_file_location("resolve_qgis_geometry_expression", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_buffer_expression_resolves_only_with_explicit_geometry_input() -> None:
    result = MODULE.resolve_geometry_expression('buffer( $geometry, "distance" )')
    assert result["status"] == "resolved_candidate"
    assert result["candidate_l3_code"] == "L3_02_01_01"
    assert result["mapping_admission"] == "proposal_only"
    assert result["training_row_emitted"] is False

    rejected = MODULE.resolve_geometry_expression('buffer("geom", 10)')
    assert rejected["status"] == "deferred"
    assert rejected["reason"] == "buffer_input_not_explicit_geometry"


def test_point_and_simplify_whitelist_use_existing_l3_only() -> None:
    assert MODULE.resolve_geometry_expression("centroid($geometry)")["candidate_l3_code"] == "L3_02_05_11"
    assert MODULE.resolve_geometry_expression("simplify($geometry, 2)")["candidate_l3_code"] == "L3_02_05_01"
    assert MODULE.resolve_geometry_expression("start_point(geometry(@feature))")["status"] == "resolved_candidate"


def test_unsupported_geometry_operations_fail_closed() -> None:
    for expression in (
        "extend(make_line($geometry, project($geometry, 10, 0)), 10, 0)",
        "translate($geometry, 1, 2)",
        "buffer($geometry, 2) || centroid($geometry)",
        "buffer($geometry, QgsProperty.fromExpression('distance'))",
        "buffer($geometry, 2) + 1",
    ):
        result = MODULE.resolve_geometry_expression(expression)
        assert result["status"] == "deferred", expression
        assert result["candidate_l3_code"] == ""
        assert result["mapping_admission"] == "not_granted"


def test_queue_census_is_report_only_and_counts_missing_snippets() -> None:
    queue = [
        {
            "operator_id": "native:geometrybyexpression",
            "single_gap_records": 2,
            "samples": [
                {
                    "record_id": "r1",
                    "source_sha256": "sha1",
                    "source_snippet": "params = {'EXPRESSION': 'buffer($geometry, 5)'}",
                },
                {
                    "record_id": "r2",
                    "source_sha256": "sha2",
                    "source_snippet": "processing.run('native:geometrybyexpression', alg_params)",
                },
            ],
        }
    ]
    rows, summary = MODULE.build_queue_census(queue)
    assert len(rows) == 2
    assert summary["queue_single_gap_records"] == 2
    assert summary["expression_observed_count"] == 1
    assert summary["resolved_candidate_count"] == 1
    assert summary["deferred_count"] == 1
    assert summary["training_rows_emitted"] == 0
    assert rows[1]["reason"] == "expression_not_present_in_queue_snippet"


def test_source_replay_resolves_nearest_reused_parameter_dictionary() -> None:
    source = """def process(layer):
    alg_params = {'INPUT': layer, 'EXPRESSION': 'buffer($geometry, 5)'}
    processing.run('native:geometrybyexpression', alg_params)
    alg_params = {'INPUT': layer, 'EXPRESSION': 'centroid($geometry)'}
    processing.run('native:geometrybyexpression', alg_params)
"""

    rows = MODULE.resolve_source_expressions(source)

    assert [row["candidate_l3_code"] for row in rows] == [
        "L3_02_01_01",
        "L3_02_05_11",
    ]
    assert all(row["status"] == "resolved_candidate" for row in rows)
