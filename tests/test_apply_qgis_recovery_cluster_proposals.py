from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.apply_qgis_recovery_cluster_proposals import (
    apply_cluster_proposals,
    main,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _packet(
    *, source_sha: str, dag: str, rule_id: str, position: int
) -> dict:
    return {
        "review_position": position,
        "unit_id": f"unit-{position}",
        "parent_record_id": f"parent-{position}",
        "source_sha256": source_sha,
        "source_path": f"/{source_sha}.py",
        "normalized_dag_key": dag,
        "recovery_rule_id": rule_id,
        "operator_ids": ["native:fixgeometries", "native:retainfields"],
        "mapped_l3_chain": ["L3_FIX", "L3_RETAIN"],
        "dependency_edges": [[0, 1]],
        "task_name": "修复几何并保留字段",
        "task_description": "先修复几何，再保留字段。",
    }


def _proposal(dag: str, final: str = "valid") -> dict:
    passed = final == "valid"
    return {
        "normalized_dag_key": dag,
        "dependency_correct": passed,
        "operator_order_correct": passed,
        "boundary_correct": passed,
        "fanin_semantics_correct": passed,
        "provider_types_compatible": passed,
        "description_faithful": passed,
        "final_proposal": final,
        "notes": f"reviewed {dag}",
        "automation_rule": f"rule for {dag}",
    }


def test_replays_cluster_proposals_and_computes_rule_metrics(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        packet_path,
        [
            _packet(
                source_sha="source-a",
                dag="dag-valid",
                rule_id="recovery-connected-local-dag-v1",
                position=1,
            ),
            _packet(
                source_sha="source-b",
                dag="dag-valid",
                rule_id="recovery-connected-local-dag-v1",
                position=2,
            ),
            _packet(
                source_sha="source-c",
                dag="dag-reject",
                rule_id="recovery-multi-root-fanin-dag-v1",
                position=3,
            ),
        ],
    )
    _write_jsonl(
        proposals_path,
        [_proposal("dag-valid"), _proposal("dag-reject", "reject_current_recovery")],
    )

    ledger, summary = apply_cluster_proposals(packet_path, proposals_path)

    assert [row["final_proposal"] for row in ledger] == [
        "valid",
        "valid",
        "reject_current_recovery",
    ]
    assert all(row["proposal_only"] is True for row in ledger)
    assert all(row["training_row_emitted"] is False for row in ledger)
    assert summary["cluster_proposal_counts"] == {
        "reject_current_recovery": 1,
        "valid": 1,
    }
    assert summary["row_proposal_counts"] == {
        "reject_current_recovery": 1,
        "valid": 2,
    }
    assert summary["combined_metrics"]["support"] == 3
    assert summary["combined_metrics"]["valid"] == 2
    assert summary["combined_metrics"]["observed_precision"] == pytest.approx(2 / 3)
    assert (
        summary["rule_metrics"]["recovery-connected-local-dag-v1"]["support"]
        == 2
    )
    assert summary["rule_training_eligible"] is False
    assert summary["training_rows_emitted"] == 0


def test_missing_cluster_proposal_fails_closed(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        packet_path,
        [
            _packet(
                source_sha="source-a",
                dag="dag-a",
                rule_id="recovery-connected-local-dag-v1",
                position=1,
            )
        ],
    )
    _write_jsonl(proposals_path, [])

    with pytest.raises(ValueError, match="missing cluster proposals"):
        apply_cluster_proposals(packet_path, proposals_path)


def test_valid_proposal_requires_every_gate_to_pass(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        packet_path,
        [
            _packet(
                source_sha="source-a",
                dag="dag-a",
                rule_id="recovery-connected-local-dag-v1",
                position=1,
            )
        ],
    )
    proposal = _proposal("dag-a")
    proposal["provider_types_compatible"] = False
    _write_jsonl(proposals_path, [proposal])

    with pytest.raises(ValueError, match="valid proposal has failed checks"):
        apply_cluster_proposals(packet_path, proposals_path)


def test_cli_writes_human_readable_report_and_hashes_it(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    output_dir = tmp_path / "output"
    _write_jsonl(
        packet_path,
        [
            _packet(
                source_sha="source-a",
                dag="dag-a",
                rule_id="recovery-connected-local-dag-v1",
                position=1,
            )
        ],
    )
    _write_jsonl(proposals_path, [_proposal("dag-a")])

    outputs = main(
        [
            "--packet",
            str(packet_path),
            "--proposals",
            str(proposals_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    report = outputs["report"].read_text(encoding="utf-8")
    hashes = json.loads(outputs["hash"].read_text(encoding="utf-8"))
    assert "Recovery Cluster Proposal Replay" in report
    assert "not human adjudication" in report
    assert "Unique source authorities: 1" in report
    assert outputs["report"].name in hashes["outputs"]


def test_support_collapses_harvest_copies_by_normalized_source_body(
    tmp_path: Path,
) -> None:
    first_source = tmp_path / "first.py"
    second_source = tmp_path / "second.py"
    body = 'processing.run("native:fixgeometries", {})\n'
    first_source.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: workflow.py\n"
        "# Query used: first\n"
        "# Harvested at: first-time\n\n"
        + body,
        encoding="utf-8",
    )
    second_source.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: workflow.py\n"
        "# Query used: second\n"
        "# Harvested at: second-time\n\n"
        + body,
        encoding="utf-8",
    )
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    first = _packet(
        source_sha="file-sha-a",
        dag="dag-a",
        rule_id="recovery-connected-local-dag-v1",
        position=1,
    )
    second = _packet(
        source_sha="file-sha-b",
        dag="dag-a",
        rule_id="recovery-connected-local-dag-v1",
        position=2,
    )
    first["source_path"] = str(first_source)
    second["source_path"] = str(second_source)
    _write_jsonl(packet_path, [first, second])
    _write_jsonl(proposals_path, [_proposal("dag-a")])

    ledger, summary = apply_cluster_proposals(packet_path, proposals_path)

    assert ledger[0]["source_authority_key"] == ledger[1]["source_authority_key"]
    assert ledger[0]["source_authority_basis"] == "normalized_source_body_sha256"
    assert summary["raw_file_sha_support"] == 2
    assert summary["source_disjoint_support"] == 1
    assert summary["combined_metrics"]["raw_row_support"] == 2
    assert summary["combined_metrics"]["support"] == 1
