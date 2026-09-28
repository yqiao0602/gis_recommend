from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_qgis_processing_batch.py"
SPEC = importlib.util.spec_from_file_location("run_qgis_processing_batch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def authority(record_id: str, sha: str | None = None, root: str = "root-a") -> dict:
    return {
        "record_id": record_id,
        "source_sha256": sha or f"sha-{record_id}",
        "source_root_id": root,
        "source_path": f"/source/{record_id}.py",
        "parse_status": "parsed",
    }


def route(record_id: str, action: str, sha: str | None = None, **extra: object) -> dict:
    row = {
        "record_id": record_id,
        "source_sha256": sha or f"sha-{record_id}",
        "action": action,
        "rule_id": "rule-v1",
        "ordered_operator_ids": [],
        "mapped_l3_chain": [],
        "signature_hash": f"signature-{record_id}",
    }
    row.update(extra)
    return row


def description(record_id: str, passed: bool = True, **extra: object) -> dict:
    row = {
        "record_id": record_id,
        "source_sha256": f"sha-{record_id}",
        "description_fidelity_passed": passed,
        "task_name": f"task {record_id}",
        "task_description": f"description {record_id}",
        "operator_ids": ["native:buffer"],
        "mapped_l3_chain": ["L3_BUFFER"],
        "call_sites": [{"ordinal": 1, "operator_id": "native:buffer", "line_start": 1, "line_end": 1}],
        "dependency_edges": [],
        "workflow_unit_scope": "whole_processing_scope",
        "parameter_evidence_status": "source_file_missing",
    }
    row.update(extra)
    return row


def training(record_id: str, **extra: object) -> dict:
    row = {
        "sample_id": f"sample-{record_id}",
        "record_id": record_id,
        "source_sha256": f"sha-{record_id}",
        "operator_sequence": ["native:buffer"],
        "l3_code_sequence": ["L3_BUFFER"],
        "l3_token_ids": [7],
        "l3_sequence": [-3, 7, -4],
        "source_region_key": f"region-{record_id}",
        "call_graph_key": f"graph-{record_id}",
        "normalized_dag_key": f"dag-{record_id}",
        "task_name": f"task {record_id}",
        "task_description": f"description {record_id}",
        "training_admission": "granted_train_only_qgis_unified_pilot",
        "split": "train_only_qgis_unified_pilot",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    row.update(extra)
    return row


def test_strict_identity_join_rejects_latest_row_outside_authority() -> None:
    authorities = [authority("a")]
    base = [route("a", "defer_mapping")]
    latest = [route("a", "auto_accept_candidate", sha="wrong-sha")]

    with pytest.raises(ValueError, match="latest replay identities outside authority"):
        MODULE.build_replay_ledger(authorities, base, latest, [], [])


def test_training_identity_duplicates_outside_processing_authority_are_ignored() -> None:
    authorities = [authority("a")]
    base = [route("a", "defer_mapping")]
    unrelated = training("outside")

    rows, accepted, summary = MODULE.build_replay_ledger(
        authorities,
        base,
        [],
        [],
        [unrelated, dict(unrelated, sample_id="outside-second-unit")],
    )

    assert len(rows) == 1
    assert accepted == []
    assert summary["matched_train_authority_rows"] == 0


def test_state_machine_accepts_only_admitted_authority_and_fails_closed() -> None:
    authorities = [authority(value) for value in "abcdefg"]
    base = [route(value, "defer_mapping") for value in "abcdefg"]
    latest = [
        route("a", "auto_accept_candidate", ordered_operator_ids=["native:buffer"], mapped_l3_chain=["L3_BUFFER"]),
        route("b", "auto_accept_candidate", ordered_operator_ids=["native:buffer"], mapped_l3_chain=["L3_BUFFER"]),
        route("c", "auto_accept_candidate", ordered_operator_ids=["native:buffer"], mapped_l3_chain=["L3_BUFFER"]),
        route("d", "recover_call_graph"),
        route("e", "defer_operator_resolution"),
        route("f", "exclude_candidate_alignment_failure"),
    ]
    descriptions = [description("a"), description("b"), description("c", passed=False)]
    rows, accepted, summary = MODULE.build_replay_ledger(
        authorities,
        base,
        latest,
        descriptions,
        [training("a")],
    )

    statuses = {row["record_id"]: row["status"] for row in rows}
    assert statuses == {
        "a": "accepted_train_authority",
        "b": "deferred_source_replay",
        "c": "deferred_description_fidelity",
        "d": "deferred_boundary",
        "e": "deferred_operator",
        "f": "excluded_boundary",
        "g": "deferred_mapping",
    }
    assert [row["record_id"] for row in accepted] == ["a"]
    assert summary["quality_gate"]["uncertain_training_rows"] == 0
    assert summary["quality_gate"]["accepted_chain_mismatches"] == 0


def test_ledger_preserves_source_and_blocker_evidence() -> None:
    authorities = [authority("a")]
    base = [route("a", "defer_mapping")]
    latest = [
        route(
            "a",
            "defer_mapping",
            source_snippet="1 | processing.run('plugin:missing', {})",
            call_sites=[{"line_start": 1, "line_end": 1}],
            dependency_edges=[[1, 2]],
            workflow_unit_scope="whole_processing_scope",
            structure_class="valid_whole_processing_scope_candidate",
            normalization_status="fully_normalized",
            unmapped_operator_ids=["plugin:missing"],
            unresolved_operator_ids=[],
        )
    ]

    rows, _, _ = MODULE.build_replay_ledger(authorities, base, latest, [], [])

    assert rows[0]["source_snippet"].startswith("1 | processing.run")
    assert rows[0]["call_sites"] == [{"line_start": 1, "line_end": 1}]
    assert rows[0]["dependency_edges"] == [[1, 2]]
    assert rows[0]["unmapped_operator_ids"] == ["plugin:missing"]
    assert rows[0]["workflow_unit_scope"] == "whole_processing_scope"


def test_accepted_direct_chain_mismatch_is_rejected() -> None:
    authorities = [authority("a")]
    base = [route("a", "defer_mapping")]
    latest = [
        route(
            "a",
            "auto_accept_candidate",
            ordered_operator_ids=["native:clip"],
            mapped_l3_chain=["L3_CLIP"],
        )
    ]

    with pytest.raises(ValueError, match="accepted direct chain mismatch"):
        MODULE.build_replay_ledger(
            authorities, base, latest, [description("a")], [training("a")]
        )


def test_duplicate_direct_candidate_is_suppressed_against_train_authority() -> None:
    authorities = [authority("a"), authority("b")]
    base = [route("a", "defer_mapping"), route("b", "defer_mapping")]
    latest = [
        route("a", "auto_accept_candidate", ordered_operator_ids=["native:buffer"], mapped_l3_chain=["L3_BUFFER"]),
        route("b", "auto_accept_candidate", ordered_operator_ids=["native:buffer"], mapped_l3_chain=["L3_BUFFER"]),
    ]
    same_pair = {
        "task_name": "same task",
        "task_description": "same description",
    }
    accepted = training("a", **same_pair)
    candidate = description("b", **same_pair)

    rows, _, _ = MODULE.build_replay_ledger(
        authorities, base, latest, [description("a", **same_pair), candidate], [accepted]
    )

    assert rows[1]["status"] == "duplicate"
    assert rows[1]["duplicate_reason"] == "exact_training_pair_suppressed"


def test_calibration_selection_keeps_all_direct_and_accepted_then_stratifies() -> None:
    rows = []
    for index in range(230):
        status = "deferred_mapping" if index % 2 else "deferred_boundary"
        action = "defer_mapping" if status == "deferred_mapping" else "recover_call_graph"
        if index < 30:
            status = "deferred_source_replay"
            action = "auto_accept_candidate"
        if 30 <= index < 40:
            status = "accepted_train_authority"
        rows.append(
            {
                "record_id": f"r{index:03d}",
                "source_sha256": f"sha-{index:03d}",
                "source_root_id": f"root-{index % 5}",
                "status": status,
                "outcome": "accepted" if status.startswith("accepted") else "deferred",
                "route_action": action,
            }
        )

    selected = MODULE.select_calibration_rows(rows, size=200)

    assert len(selected) == 200
    selected_ids = {row["record_id"] for row in selected}
    assert {f"r{index:03d}" for index in range(40)} <= selected_ids
    assert {row["status"] for row in rows} <= {row["status"] for row in selected}


def test_full_gate_rejects_failed_or_stale_calibration() -> None:
    hashes = {"authority": "a", "base_replay": "b"}

    with pytest.raises(ValueError, match="calibration quality gate did not pass"):
        MODULE.validate_full_gate(
            {"quality_gate": {"calibration_passed": False}, "input_sha256": hashes, "policy_version": MODULE.POLICY_VERSION},
            input_hashes=hashes,
        )

    with pytest.raises(ValueError, match="calibration input hashes do not match"):
        MODULE.validate_full_gate(
            {"quality_gate": {"calibration_passed": True}, "input_sha256": {"authority": "stale"}, "policy_version": MODULE.POLICY_VERSION},
            input_hashes=hashes,
        )


def test_full_phase_summary_records_verified_calibration_gate() -> None:
    summary = {
        "quality_gate": {
            "one_state_per_authority": True,
            "accepted_chain_mismatches": 0,
            "uncertain_training_rows": 0,
        }
    }

    MODULE.finalize_phase_quality_gate(
        summary,
        phase="full",
        output_rows=[{"validation_eligible": False, "test_eligible": False}],
        calibration_size=200,
    )

    assert summary["quality_gate"]["calibration_passed"] is True
    assert summary["quality_gate"]["calibration_gate_verified"] is True
