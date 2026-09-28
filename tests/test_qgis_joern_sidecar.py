from __future__ import annotations

import json
from copy import deepcopy

import pytest

from gis_recommend.data.qgis_joern_sidecar import (
    main as qgis_joern_sidecar_main,
)
from gis_recommend.data.qgis_joern_sidecar import (
    normalize_joern_jsonl,
    normalize_joern_record,
    normalized_joern_record_dict,
)


def _nodes(*codes: str) -> list[dict]:
    return [
        {
            "node_id": index,
            "label": "CALL" if "(" in code else "IDENTIFIER",
            "code": code,
            "source_path": "fixture.py",
            "line": index,
            "column": 1,
        }
        for index, code in enumerate(codes, start=1)
    ]


def _queries(prefix: str, path: list[int], terminal: int) -> list[dict]:
    return [
        {
            "query_id": f"{prefix}{index}",
            "status": "complete",
            "source_node_ids": [path[0]],
            "sink_node_ids": [terminal],
            "flow_paths": [path],
            "control_path_node_ids": [],
            "terminal_node_ids": [terminal] if index == 5 else [],
            "evidence_kinds": [f"{prefix.lower()}_{index}"],
        }
        for index in range(1, 6)
    ]


def _processing_record() -> dict:
    nodes = _nodes(
        "algorithm_id",
        "processing.run(algorithm_id, parameters)",
        'buffered["OUTPUT"]',
        'processing.run("native:dissolve", parameters)',
    )
    return {
        "record_id": "processing-helper",
        "source_sha256": "1" * 64,
        "corpus_kind": "processing",
        "query_version": "qgis-flow-v1",
        "evidence_status": "complete",
        "nodes": nodes,
        "queries": _queries("P", [1, 2, 3, 4], 4),
        "operator_ids": ["native:buffer", "native:dissolve"],
        "semantic_calls": ["processing.run", "processing.run"],
        "dependency_edges": [[0, 1]],
        "ambiguity_reasons": [],
    }


def _api_record() -> dict:
    nodes = _nodes(
        "feature.geometry()",
        "geometry.buffer(10, 8)",
        "feature.setGeometry(buffered)",
        "sink.addFeature(feature)",
    )
    return {
        "record_id": "api-to-sink",
        "source_sha256": "2" * 64,
        "corpus_kind": "api",
        "query_version": "qgis-flow-v1",
        "evidence_status": "complete",
        "nodes": nodes,
        "queries": _queries("A", [1, 2, 3, 4], 4),
        "operator_ids": [],
        "semantic_calls": ["geometry", "buffer", "setGeometry", "addFeature"],
        "dependency_edges": [],
        "ambiguity_reasons": [],
    }


def test_complete_processing_flow_is_normalized() -> None:
    row = normalize_joern_record(_processing_record())

    assert row.evidence_status == "complete"
    assert row.operator_ids == ("native:buffer", "native:dissolve")
    assert row.dependency_edges == ((0, 1),)
    assert row.query_ids == ("P1", "P2", "P3", "P4", "P5")
    assert row.terminal_node_ids == (4,)


def test_complete_api_to_sink_flow_is_normalized() -> None:
    row = normalize_joern_record(_api_record())

    assert row.evidence_status == "complete"
    assert row.semantic_calls == (
        "geometry",
        "buffer",
        "setGeometry",
        "addFeature",
    )
    assert row.terminal_node_ids == (4,)


def test_flow_path_preserves_dataflow_direction() -> None:
    record = _processing_record()
    record["queries"][0]["flow_paths"] = [[3, 1, 4]]

    row = normalize_joern_record(record)

    assert row.queries[0].flow_paths == ((3, 1, 4),)


def test_conflicting_branch_is_not_complete() -> None:
    record = _api_record()
    record["record_id"] = "ambiguous-branch"
    record["evidence_status"] = "ambiguous"
    record["queries"][-1]["status"] = "ambiguous"
    record["queries"][-1]["flow_paths"] = [[1, 2, 3, 4], [1, 3, 4]]
    record["ambiguity_reasons"] = ["incompatible_branch_definitions"]

    row = normalize_joern_record(record)

    assert row.evidence_status == "ambiguous"
    assert row.ambiguity_reasons == ("incompatible_branch_definitions",)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.update(source_sha256="bad"), "source_sha256"),
        (
            lambda row: row["queries"].append(deepcopy(row["queries"][0])),
            "duplicate query_id",
        ),
        (lambda row: row["queries"][0]["flow_paths"].append([1, 99]), "dangling"),
        (lambda row: row["queries"][0]["flow_paths"].append([1, 2, 1]), "duplicate"),
        (lambda row: row["nodes"].reverse(), "sorted"),
        (
            lambda row: [query.update(terminal_node_ids=[]) for query in row["queries"]],
            "terminal",
        ),
    ],
)
def test_invalid_or_false_complete_records_fail_closed(mutation, message: str) -> None:
    record = _processing_record()
    mutation(record)

    with pytest.raises(ValueError, match=message):
        normalize_joern_record(record)


def test_query_failure_is_a_structured_terminal_state() -> None:
    record = _processing_record()
    record["evidence_status"] = "query_failure"
    record["queries"][2].update(
        status="query_failure",
        flow_paths=[],
        sink_node_ids=[],
        terminal_node_ids=[],
        error="reachableByFlows failed",
    )

    row = normalize_joern_record(record)

    assert row.evidence_status == "query_failure"
    assert row.query_failures == (("P3", "reachableByFlows failed"),)


def test_insufficient_evidence_may_have_no_grounded_nodes() -> None:
    record = _processing_record()
    record["evidence_status"] = "insufficient"
    record["nodes"] = []
    record["operator_ids"] = []
    record["semantic_calls"] = ["processing.run"]
    record["dependency_edges"] = []
    for query in record["queries"]:
        query.update(
            status="insufficient",
            source_node_ids=[],
            sink_node_ids=[],
            flow_paths=[],
            terminal_node_ids=[],
        )

    row = normalize_joern_record(record)

    assert row.evidence_status == "insufficient"
    assert row.nodes == ()
    assert row.terminal_node_ids == ()


def test_normalized_dict_is_byte_order_stable() -> None:
    record = _processing_record()
    first = normalized_joern_record_dict(normalize_joern_record(record))
    second = normalized_joern_record_dict(normalize_joern_record(deepcopy(record)))

    assert first == second
    assert first["training_row_emitted"] is False
    assert first["training_admission"] == "not_granted_external_analysis_pilot_only"


def test_jsonl_normalization_is_order_independent_and_byte_stable(tmp_path) -> None:
    input_one = tmp_path / "raw-one.jsonl"
    input_two = tmp_path / "raw-two.jsonl"
    output_one = tmp_path / "normalized-one.jsonl"
    output_two = tmp_path / "normalized-two.jsonl"
    records = [_processing_record(), _api_record()]
    input_one.write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
    )
    input_two.write_text(
        "".join(json.dumps(row) + "\n" for row in reversed(records)), encoding="utf-8"
    )

    normalize_joern_jsonl(input_one, output_one)
    normalize_joern_jsonl(input_two, output_two)

    assert output_one.read_bytes() == output_two.read_bytes()
    assert output_one.read_text(encoding="utf-8").count("\n") == 2


def test_jsonl_normalization_does_not_replace_output_on_failure(tmp_path) -> None:
    raw = tmp_path / "raw.jsonl"
    output = tmp_path / "normalized.jsonl"
    invalid = _processing_record()
    invalid["source_sha256"] = "bad"
    raw.write_text(json.dumps(invalid) + "\n", encoding="utf-8")
    output.write_text("existing\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source_sha256"):
        normalize_joern_jsonl(raw, output)

    assert output.read_text(encoding="utf-8") == "existing\n"


def test_jsonl_normalization_cli_writes_output(tmp_path) -> None:
    raw = tmp_path / "raw.jsonl"
    output = tmp_path / "normalized.jsonl"
    raw.write_text(json.dumps(_processing_record()) + "\n", encoding="utf-8")

    exit_code = qgis_joern_sidecar_main(
        ["--input", str(raw), "--output", str(output)]
    )

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["evidence_status"] == "complete"
