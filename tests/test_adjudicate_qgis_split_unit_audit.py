from __future__ import annotations

import json
from pathlib import Path

from scripts.adjudicate_qgis_split_unit_audit import adjudicate


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _packet(unit_id: str, source_sha: str) -> dict:
    return {
        "review_position": int(unit_id[-1]),
        "unit_id": unit_id,
        "parent_record_id": f"parent-{unit_id}",
        "source_sha256": source_sha,
        "source_path": f"/{unit_id}.py",
        "source_root_id": "test-root",
        "source_snippet": "1: processing.run(...)\n",
        "call_sites": [
            {"operator_id": "native:fixgeometries", "line_start": 1, "line_end": 1},
            {"operator_id": "native:reprojectlayer", "line_start": 2, "line_end": 2},
        ],
        "workflow_unit_scope": "local_subworkflow",
        "parameter_facts": [{}, {}],
        "known_omissions": ["outside_explicit_processing_dag_not_described"],
        "operator_ids": ["native:fixgeometries", "native:reprojectlayer"],
        "mapped_l3_chain": ["L3_FIX", "L3_REPROJECT"],
        "dependency_edges": [[0, 1]],
        "dependency_edge_evidence": [
            {
                "producer_index": 0,
                "consumer_index": 1,
                "kinds": ["variable_or_alias"],
            }
        ],
        "normalized_dag_key": "dag-1",
        "task_name": "name",
        "task_description": "description",
    }


def _decision(unit_id: str, source_sha: str, final: str = "valid") -> dict:
    passed = final == "valid"
    return {
        "unit_id": unit_id,
        "source_sha256": source_sha,
        "dependency_correct": passed,
        "operator_order_correct": passed,
        "boundary_correct": passed,
        "description_faithful": passed,
        "final_decision": final,
        "notes": f"reviewed {unit_id}",
    }


def test_adjudicates_units_and_counts_source_groups(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(
        packet_path,
        [_packet("unit-1", "source-a"), _packet("unit-2", "source-b")],
    )
    _write_jsonl(
        decisions_path,
        [_decision("unit-1", "source-a"), _decision("unit-2", "source-b", "defer")],
    )

    ledger, summary = adjudicate(packet_path, decisions_path)

    assert len(ledger) == 2
    assert ledger[0]["source_snippet"] == "1: processing.run(...)\n"
    assert ledger[0]["workflow_unit_scope"] == "local_subworkflow"
    assert summary["decision_counts"] == {"defer": 1, "valid": 1}
    assert summary["accepted_units"] == 1
    assert summary["source_disjoint_support"] == 2
    assert summary["fully_valid_source_groups"] == 1
    assert summary["rule_training_eligible"] is False
    assert summary["census_pilot_training_eligible"] is False


def test_missing_decision_fails_closed(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(packet_path, [_packet("unit-1", "source-a")])
    _write_jsonl(decisions_path, [])

    try:
        adjudicate(packet_path, decisions_path)
    except ValueError as exc:
        assert "missing decisions" in str(exc)
    else:
        raise AssertionError("expected missing decisions to fail closed")


def test_complete_valid_census_can_grant_row_limited_pilot(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(packet_path, [_packet("unit-1", "source-a")])
    _write_jsonl(decisions_path, [_decision("unit-1", "source-a")])

    _, summary = adjudicate(packet_path, decisions_path)

    assert summary["source_disjoint_support"] == 1
    assert summary["rule_training_eligible"] is False
    assert summary["census_pilot_training_eligible"] is True
    assert summary["census_pilot_basis"] == "exhaustive_current_population_only"
