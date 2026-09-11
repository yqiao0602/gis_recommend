from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
module = importlib.import_module(
    "scripts.build_qgis_benchmark_v01_dag_review_queue"
)


def _candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "candidate-1",
        "provenance_class": "qgis_source_backed",
        "source_authority_key": "source_sha256:abc",
        "processes": [
            {
                "process_id": "p1",
                "operator_id": "native:buffer",
                "stable101_l3": "L3_02_01_01",
            },
            {
                "process_id": "p0",
                "operator_id": "native:fixgeometries",
                "stable101_l3": "L3_01_10_04",
            },
        ],
        "links": [
            {"source_process_id": "p0", "target_process_id": "p1"},
        ],
        "parameters_included": False,
        "quota_anchor_l3": "L3_02_01_01",
        "covered_l3": ["L3_02_01_01", "L3_01_10_04"],
        "modality": "vector",
        "topology": "linear",
        "graph_size_stratum": "two_to_three",
        "normalized_dag_key": "dag-1",
        "forbidden_near_dag_key": "near-1",
        "semantic_dag_key": "semantic-1",
    }
    row.update(overrides)
    return row


def _write_candidates(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    return path


def test_real_candidate_pool_collapses_to_52_review_units() -> None:
    result = module.build_queue(
        ROOT / "benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl"
    )

    assert len(result["rows"]) == 52
    assert result["summary"]["candidate_count"] == 149
    assert result["summary"]["distinct_dag_count"] == 52
    assert result["summary"]["modality_counts"] == {
        "mixed": 13,
        "raster": 5,
        "vector": 34,
    }
    assert result["summary"]["topology_counts"] == {
        "linear": 30,
        "multi_input_merge": 22,
    }
    assert result["summary"]["graph_size_counts"] == {
        "four_to_six": 12,
        "one_step": 1,
        "seven_plus": 7,
        "two_to_three": 32,
    }
    assert result["summary"]["queue_status"] == "pending_review"


def test_queue_contains_only_parameter_free_graph_review_authority() -> None:
    result = module.build_queue(
        ROOT / "benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl"
    )
    forbidden = {
        "task_text",
        "task_intent",
        "output_constraint",
        "process_necessity",
        "parameters",
        "rationale",
        "reason_codes",
    }
    expected_fields = {
        "schema",
        "canonical_graph_id",
        "canonical_graph_sha256",
        "normalized_dag_key",
        "semantic_dag_key",
        "forbidden_near_dag_keys",
        "candidate_ids",
        "source_authority_keys",
        "provenance_classes",
        "quota_anchor_l3",
        "covered_l3",
        "modality",
        "topology",
        "graph_size_stratum",
        "processes",
        "links",
        "parameters_included",
        "review_status",
    }

    assert all(set(row) == expected_fields for row in result["rows"])
    assert all(set(row).isdisjoint(forbidden) for row in result["rows"])
    assert all(row["parameters_included"] is False for row in result["rows"])
    assert all(row["review_status"] == "pending" for row in result["rows"])


def test_canonical_graph_normalizes_ids_and_sorts_graph_content() -> None:
    graph = module.canonical_graph(
        [
            {
                "process_id": "p9",
                "operator_id": "NATIVE:BUFFER",
                "stable101_l3": "L3_02_01_01",
            },
            {
                "process_id": "p3",
                "operator_id": "native:fixgeometries",
                "stable101_l3": "L3_01_10_04",
            },
        ],
        [{"source_process_id": "p3", "target_process_id": "p9"}],
    )

    assert graph == {
        "processes": [
            {
                "process_id": "p0",
                "operator_id": "native:fixgeometries",
                "stable101_l3": "L3_01_10_04",
            },
            {
                "process_id": "p1",
                "operator_id": "native:buffer",
                "stable101_l3": "L3_02_01_01",
            },
        ],
        "links": [
            {"source_process_id": "p0", "target_process_id": "p1"},
        ],
    }


def test_group_preserves_all_candidate_and_provenance_authorities(
    tmp_path: Path,
) -> None:
    expert = _candidate(
        candidate_id="candidate-2",
        provenance_class="expert_authored",
        source_authority_key="",
        supply_authority_key="expert_proposal:expert-v1-001",
        forbidden_near_dag_key="near-2",
    )
    path = _write_candidates(tmp_path / "candidates.jsonl", [_candidate(), expert])

    row = module.build_queue(path)["rows"][0]

    assert row["candidate_ids"] == ["candidate-1", "candidate-2"]
    assert row["source_authority_keys"] == [
        "expert_proposal:expert-v1-001",
        "source_sha256:abc",
    ]
    assert row["provenance_classes"] == [
        "expert_authored",
        "qgis_source_backed",
    ]
    assert row["forbidden_near_dag_keys"] == ["near-1", "near-2"]


def test_covered_l3_order_is_canonicalized_before_consistency_check(
    tmp_path: Path,
) -> None:
    reordered = _candidate(
        candidate_id="candidate-2",
        covered_l3=["L3_01_10_04", "L3_02_01_01"],
    )
    path = _write_candidates(tmp_path / "candidates.jsonl", [_candidate(), reordered])

    row = module.build_queue(path)["rows"][0]

    assert row["covered_l3"] == ["L3_01_10_04", "L3_02_01_01"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("modality", "mixed", "conflicting modality"),
        ("topology", "multi_input_merge", "conflicting topology"),
        ("graph_size_stratum", "four_to_six", "conflicting graph_size_stratum"),
        ("quota_anchor_l3", "L3_99", "conflicting quota_anchor_l3"),
        ("covered_l3", ["L3_99"], "conflicting covered_l3"),
        ("semantic_dag_key", "semantic-2", "conflicting semantic_dag_key"),
    ],
)
def test_conflicting_group_authority_fails_closed(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    changed = _candidate(candidate_id="candidate-2", **{field: value})
    path = _write_candidates(tmp_path / "candidates.jsonl", [_candidate(), changed])

    with pytest.raises(ValueError, match=message):
        module.build_queue(path)


def test_conflicting_canonical_graph_fails_closed(tmp_path: Path) -> None:
    changed = _candidate(
        candidate_id="candidate-2",
        processes=[
            {
                "process_id": "p0",
                "operator_id": "native:fixgeometries",
                "stable101_l3": "L3_01_10_04",
            },
            {
                "process_id": "p1",
                "operator_id": "native:centroids",
                "stable101_l3": "L3_02_03_02",
            },
        ],
    )
    path = _write_candidates(tmp_path / "candidates.jsonl", [_candidate(), changed])

    with pytest.raises(ValueError, match="conflicting canonical graph content"):
        module.build_queue(path)


def test_parameter_bearing_candidate_fails_closed(tmp_path: Path) -> None:
    path = _write_candidates(
        tmp_path / "candidates.jsonl",
        [_candidate(parameters_included=True)],
    )

    with pytest.raises(ValueError, match="must be parameter-free"):
        module.build_queue(path)


def test_write_outputs_is_deterministic_lf_json(tmp_path: Path) -> None:
    result = module.build_queue(
        ROOT / "benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl"
    )

    paths = module.write_outputs(result, tmp_path)
    first = {name: path.read_bytes() for name, path in paths.items()}
    module.write_outputs(result, tmp_path)
    second = {name: path.read_bytes() for name, path in paths.items()}

    assert set(paths) == {"queue", "summary"}
    assert first == second
    assert all(b"\r\n" not in content for content in first.values())
    assert all(content.endswith(b"\n") for content in first.values())
