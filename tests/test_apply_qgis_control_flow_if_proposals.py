import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "apply_qgis_control_flow_if_proposals.py"
)
SPEC = importlib.util.spec_from_file_location(
    "apply_qgis_control_flow_if_proposals", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _packet(position: int, authority: str) -> dict[str, object]:
    return {
        "review_position": position,
        "source_authority_key": authority,
        "human_final_decision": "",
        "training_row_emitted": False,
    }


def _proposal(
    position: int,
    authority: str,
    *,
    final: str = "valid_candidate",
    boundary: bool = True,
) -> dict[str, object]:
    return {
        "review_position": position,
        "source_authority_key": authority,
        "dependency_correct": True,
        "operator_order_correct": True,
        "boundary_correct": boundary,
        "branch_semantics_recoverable": True,
        "description_scope_correct": boundary,
        "provider_type_decision": "unknown",
        "final_proposal": final,
        "proposal_reason": "source-backed reason",
        "automation_rule": "conditional_passthrough_rule",
    }


def test_replay_computes_authority_metrics_without_training_admission(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        packet_path,
        [_packet(1, "authority-a"), _packet(2, "authority-b")],
    )
    _write_jsonl(
        proposals_path,
        [
            _proposal(1, "authority-a"),
            _proposal(
                2,
                "authority-b",
                final="defer",
                boundary=False,
            ),
        ],
    )

    ledger, summary = MODULE.apply_proposals(packet_path, proposals_path)

    assert len(ledger) == 2
    assert summary["source_authority_support"] == 2
    assert summary["proposal_counts"] == {"defer": 1, "valid_candidate": 1}
    assert summary["combined_metrics"]["observed_precision"] == 0.5
    assert summary["rule_training_eligible"] is False
    assert summary["training_rows_emitted"] == 0
    assert all(row["proposal_only"] for row in ledger)
    assert all(not row["training_row_emitted"] for row in ledger)


def test_valid_proposal_rejects_failed_boundary_check(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    _write_jsonl(packet_path, [_packet(1, "authority-a")])
    _write_jsonl(
        proposals_path,
        [_proposal(1, "authority-a", boundary=False)],
    )

    try:
        MODULE.apply_proposals(packet_path, proposals_path)
    except ValueError as exc:
        assert "valid proposal has failed checks" in str(exc)
    else:
        raise AssertionError("expected invalid proposal to fail closed")

