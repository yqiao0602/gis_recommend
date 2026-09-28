from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_qgis_processing_blocker_batch.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_qgis_processing_blocker_batch", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(record_id: str, action: str, sha: str | None = None) -> dict:
    digest = sha or (record_id * 64)[:64]
    return {
        "record_id": record_id,
        "source_sha256": digest,
        "action": action,
        "route_action": action,
        "operator_ids": ["native:buffer"],
        "mapped_l3_chain": ["L3_02_01_01"],
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 1, "line_end": 1}
        ],
        "dependency_edges": [],
        "workflow_unit_scope": "local_subworkflow",
    }


def test_select_blocker_rows_requires_exact_identity_and_action_alignment() -> None:
    actions = [
        "recover_call_graph",
        "split_subworkflow",
        "defer_operator_resolution",
    ]
    latest = [_row(str(index), action) for index, action in enumerate(actions)]
    ledger = [
        {**row, "route_action": row["action"]}
        for row in latest
    ]

    selected = MODULE.select_blocker_rows(latest, ledger)

    assert [row["action"] for row in selected] == actions
    with pytest.raises(ValueError, match="action mismatch"):
        MODULE.select_blocker_rows(
            latest,
            [{**ledger[0], "route_action": "split_subworkflow"}, *ledger[1:]],
        )


def test_select_blocker_rows_only_adds_defer_mapping_when_requested() -> None:
    latest = [
        _row("recover", "recover_call_graph"),
        _row("mapping", "defer_mapping"),
    ]
    ledger = [{**row, "route_action": row["action"]} for row in latest]

    default_selected = MODULE.select_blocker_rows(latest, ledger)
    expanded_selected = MODULE.select_blocker_rows(
        latest, ledger, actions={*MODULE.BLOCKER_ACTIONS, "defer_mapping"}
    )

    assert [row["record_id"] for row in default_selected] == ["recover"]
    assert [row["record_id"] for row in expanded_selected] == ["mapping", "recover"]


def test_select_current_action_rows_does_not_depend_on_stale_ledger_actions() -> None:
    latest = [
        _row("new-recovery", "recover_call_graph"),
        _row("direct", "auto_accept_candidate"),
        _row("mapping", "defer_mapping"),
    ]

    selected = MODULE.select_current_action_rows(latest)

    assert [row["record_id"] for row in selected] == ["new-recovery"]


def test_select_action_transitions_keeps_only_new_routes() -> None:
    current = [
        _row("new-recovery", "recover_call_graph"),
        _row("unchanged-split", "split_subworkflow"),
    ]
    previous = [
        _row("new-recovery", "defer_mapping"),
        _row("unchanged-split", "split_subworkflow"),
    ]

    selected = MODULE.select_action_transitions(current, previous)

    assert [row["record_id"] for row in selected] == ["new-recovery"]
    with pytest.raises(ValueError, match="missing previous replay identity"):
        MODULE.select_action_transitions(current, previous[1:])


def test_select_direct_rows_requires_unique_auto_accept_records() -> None:
    latest = [
        _row("direct", "auto_accept_candidate"),
        _row("blocked", "recover_call_graph"),
    ]

    selected = MODULE.select_direct_rows(latest, ["direct"])

    assert [row["record_id"] for row in selected] == ["direct"]
    with pytest.raises(ValueError, match="is not auto_accept_candidate"):
        MODULE.select_direct_rows(latest, ["blocked"])
    with pytest.raises(ValueError, match="not found"):
        MODULE.select_direct_rows(latest, ["missing"])


def test_select_direct_rows_can_select_all_auto_accept_records() -> None:
    latest = [
        _row("direct-b", "auto_accept_candidate"),
        _row("blocked", "recover_call_graph"),
        _row("direct-a", "auto_accept_candidate"),
    ]

    selected = MODULE.select_direct_rows(latest, [], include_all=True)

    assert [row["record_id"] for row in selected] == ["direct-a", "direct-b"]


def test_validate_input_paths_fails_before_batch_work(tmp_path: Path) -> None:
    present = tmp_path / "present.json"
    present.write_text("{}", encoding="utf-8")

    MODULE.validate_input_paths([present])
    with pytest.raises(ValueError, match="missing required input"):
        MODULE.validate_input_paths([present, tmp_path / "missing.json"])


def test_resolve_source_rows_accepts_only_sha_verified_exact_or_prefix_alias(
    tmp_path: Path,
) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    exact = old_root / "exact.py"
    alias = new_root / "alias.py"
    exact.write_text("exact\n", encoding="utf-8")
    alias.write_text("alias\n", encoding="utf-8")
    exact_sha = hashlib.sha256(exact.read_bytes()).hexdigest()
    alias_sha = hashlib.sha256(alias.read_bytes()).hexdigest()
    rows = [
        {**_row("exact", "recover_call_graph", exact_sha), "source_path": str(exact)},
        {
            **_row("alias", "split_subworkflow", alias_sha),
            "source_path": str(old_root / "alias.py"),
        },
        {
            **_row("bad", "defer_operator_resolution", "0" * 64),
            "source_path": str(old_root / "missing.py"),
        },
    ]

    resolved, failures = MODULE.resolve_source_rows(
        rows, [(str(old_root), str(new_root))]
    )

    assert resolved[0]["source_path_resolution"] == "verified_exact"
    assert resolved[1]["source_path"] == str(alias)
    assert resolved[1]["source_path_resolution"] == "verified_prefix_alias"
    assert [row["record_id"] for row in failures] == ["bad"]


def test_build_candidate_pool_applies_lane_specific_fail_closed_gates() -> None:
    recovery = [
        {
            **_row("r1", "recover_call_graph"),
            "description_fidelity_passed": True,
            "local_structure_status": "eligible",
            "local_structure_reasons": [],
            "source_authority_key": "body:r1",
        },
        {
            **_row("r2", "recover_call_graph"),
            "description_fidelity_passed": False,
            "local_structure_status": "eligible",
            "local_structure_reasons": [],
            "source_authority_key": "body:r2",
        },
        {
            **_row("r3", "recover_call_graph"),
            "description_fidelity_passed": True,
            "local_structure_status": "deferred",
            "local_structure_reasons": ["missing_data_edges"],
            "source_authority_key": "body:r3",
        },
    ]
    split = [
        {
            **_row("s1", "split_subworkflow"),
            "split_class": "multi_step_local_dag",
            "local_structure_status": "eligible",
            "description_fidelity_passed": True,
            "local_structure_reasons": [],
            "source_authority_key": "body:s1",
        },
        {
            **_row("s2", "split_subworkflow"),
            "split_class": "single_step_local_unit",
            "local_structure_status": "single_step_not_training_target",
            "description_fidelity_passed": True,
            "local_structure_reasons": [],
            "source_authority_key": "body:s2",
        },
        {
            **_row("s3", "split_subworkflow"),
            "split_class": "single_step_local_unit",
            "description_fidelity_passed": True,
            "local_structure_reasons": ["control_flow:if"],
            "source_authority_key": "body:s3",
        },
    ]
    operators = [
        {
            **_row("o1", "auto_accept_candidate"),
            "mapping_complete": True,
            "description_fidelity_passed": True,
            "parameter_evidence_status": "verified_source_ast",
            "source_authority_key": "body:o1",
        },
        {
            **_row("o2", "auto_accept_candidate"),
            "mapping_complete": True,
            "description_fidelity_passed": True,
            "parameter_evidence_status": "source_file_missing",
            "source_authority_key": "body:o2",
        },
    ]
    direct = [
        {
            **_row("d1", "auto_accept_candidate"),
            "mapping_complete": True,
            "description_fidelity_passed": True,
            "parameter_evidence_status": "verified_source_ast",
            "source_authority_key": "body:d1",
        }
    ]

    operator_recovery = [
        {
            **_row("or1", "recover_call_graph"),
            "description_fidelity_passed": True,
            "local_structure_status": "eligible",
            "local_structure_reasons": [],
            "source_authority_key": "body:or1",
        },
        {
            **_row("or2", "recover_call_graph"),
            "description_fidelity_passed": True,
            "local_structure_status": "deferred",
            "local_structure_reasons": ["missing_data_edges"],
            "source_authority_key": "body:or2",
        },
    ]
    operator_split = [
        {
            **_row("os1", "split_subworkflow"),
            "split_class": "single_step_local_unit",
            "local_structure_status": "single_step_not_training_target",
            "description_fidelity_passed": True,
            "local_structure_reasons": [],
            "source_authority_key": "body:os1",
        }
    ]

    candidates = MODULE.build_candidate_pool(
        recovery,
        split,
        operators,
        direct_rows=direct,
        operator_recovery_rows=operator_recovery,
        operator_split_rows=operator_split,
    )

    assert sorted(row["record_id"] for row in candidates) == [
        "d1",
        "o1",
        "or1",
        "os1",
        "r1",
        "s1",
        "s2",
    ]
    assert {row["candidate_lane"] for row in candidates} == {
        "direct",
        "recovery_multistep",
        "split_multistep",
        "split_single_step",
        "operator_resolution_direct",
        "operator_resolution_recovery",
        "operator_resolution_split_single",
    }
    assert all(row["training_admission"] == "not_granted" for row in candidates)


def test_annotate_dedup_accepts_direct_evidence_without_candidate_id() -> None:
    direct = {
        **_row("direct", "auto_accept_candidate"),
        "task_name": "缓冲区",
        "task_description": "创建缓冲区。",
    }

    annotated = MODULE.annotate_dedup([direct], [])

    assert annotated[0]["dedup_status"] == "canonical_candidate"
    assert annotated[0]["dedup_candidate_reference"] == "qgis_direct_direct"


def test_select_candidate_batch_is_deterministic_and_source_disjoint() -> None:
    candidates = []
    for index in range(12):
        candidates.append(
            {
                **_row(str(index), "auto_accept_candidate"),
                "candidate_id": f"candidate-{index}",
                "candidate_lane": "split_single_step" if index % 2 else "recovery_multistep",
                "source_authority_key": f"body:{index}",
                "source_root_id": f"root-{index % 3}",
                "operator_ids": [f"native:op{index % 4}"],
            }
        )

    first = MODULE.select_candidate_batch(candidates, target_count=8)
    second = MODULE.select_candidate_batch(list(reversed(candidates)), target_count=8)
    packet = MODULE.build_source_disjoint_review_packet(first, per_split=3)

    assert [row["candidate_id"] for row in first] == [
        row["candidate_id"] for row in second
    ]
    assert len(first) == 8
    calibration = {
        row["source_authority_key"]
        for row in packet
        if row["review_split"] == "calibration"
    }
    holdout = {
        row["source_authority_key"]
        for row in packet
        if row["review_split"] == "holdout"
    }
    assert len(packet) == 6
    assert calibration.isdisjoint(holdout)


def test_source_disjoint_review_packet_caps_to_available_authorities() -> None:
    candidates = [
        {
            **_row(str(index), "auto_accept_candidate"),
            "candidate_id": f"candidate-{index}",
            "candidate_lane": "split_single_step",
            "source_authority_key": f"body:{index}",
        }
        for index in range(3)
    ]

    packet = MODULE.build_source_disjoint_review_packet(candidates, per_split=5)

    assert len(packet) == 2
    assert {row["review_split"] for row in packet} == {"calibration", "holdout"}


def test_source_disjoint_review_split_is_stable_when_an_authority_is_removed() -> None:
    candidates = [
        {
            **_row(str(index), "auto_accept_candidate"),
            "candidate_id": f"candidate-{index}",
            "candidate_lane": "split_single_step",
            "source_authority_key": f"body:{index}",
        }
        for index in range(20)
    ]

    before = MODULE.build_source_disjoint_review_packet(candidates, per_split=5)
    after = MODULE.build_source_disjoint_review_packet(candidates[1:], per_split=5)
    before_split = {row["source_authority_key"]: row["review_split"] for row in before}
    after_split = {row["source_authority_key"]: row["review_split"] for row in after}

    shared = set(before_split) & set(after_split)
    assert shared
    assert all(before_split[key] == after_split[key] for key in shared)


def test_source_disjoint_review_keeps_sha_and_authority_components_together() -> None:
    candidates = [
        {
            **_row(str(index), "auto_accept_candidate", f"{index:064x}"),
            "candidate_id": f"candidate-{index}",
            "candidate_lane": "split_single_step" if index % 2 else "recovery_multistep",
            "source_authority_key": f"body:{index}",
            "dedup_status": "canonical_candidate",
        }
        for index in range(40)
    ]
    candidates.extend(
        [
            {
                **_row("same-sha-a", "auto_accept_candidate", "f" * 64),
                "candidate_id": "same-sha-a",
                "candidate_lane": "direct",
                "source_authority_key": "body:same-sha-a",
                "dedup_status": "canonical_candidate",
            },
            {
                **_row("same-sha-b", "auto_accept_candidate", "f" * 64),
                "candidate_id": "same-sha-b",
                "candidate_lane": "split_single_step",
                "source_authority_key": "body:same-sha-b",
                "dedup_status": "canonical_candidate",
            },
            {
                **_row("same-body-a", "auto_accept_candidate", "e" * 64),
                "candidate_id": "same-body-a",
                "candidate_lane": "direct",
                "source_authority_key": "body:shared",
                "dedup_status": "canonical_candidate",
            },
            {
                **_row("same-body-b", "auto_accept_candidate", "d" * 64),
                "candidate_id": "same-body-b",
                "candidate_lane": "split_single_step",
                "source_authority_key": "body:shared",
                "dedup_status": "canonical_candidate",
            },
        ]
    )

    packet = MODULE.build_source_disjoint_review_packet(
        candidates, per_split=15, review_seed=20260802
    )
    calibration = [row for row in packet if row["review_split"] == "calibration"]
    holdout = [row for row in packet if row["review_split"] == "holdout"]

    assert {row["source_sha256"] for row in calibration}.isdisjoint(
        {row["source_sha256"] for row in holdout}
    )
    assert {row["source_authority_key"] for row in calibration}.isdisjoint(
        {row["source_authority_key"] for row in holdout}
    )
    assert all(row["review_seed"] == 20260802 for row in packet)
    assert all(row["review_rule_signature"] for row in packet)


def test_summarize_operator_rows_separates_full_chains_from_partial_subsets() -> None:
    rows = [
        {"normalization_status": "fully_normalized", "mapping_complete": True, "action": "auto_accept_candidate"},
        {"normalization_status": "fully_normalized", "mapping_complete": False, "action": "defer_mapping"},
        {"normalization_status": "partially_normalized", "mapping_complete": True, "action": "defer_operator_resolution"},
    ]

    summary = MODULE.summarize_operator_rows(rows)

    assert summary["fully_normalized_rows"] == 2
    assert summary["fully_normalized_mapping_complete_rows"] == 1
    assert summary["partially_normalized_rows"] == 1
    assert summary["partially_normalized_mapped_subset_rows"] == 1
    assert "mapping_complete_rows" not in summary


def test_default_mapping_includes_all_reviewed_existing_l3_authorities() -> None:
    mapping = MODULE.load_composed_mapping(
        MODULE.DEFAULT_CROSSWALK,
        MODULE.DEFAULT_STABLE98,
        MODULE.DEFAULT_STABLE101,
        additional_delta_paths=MODULE.DEFAULT_ADDITIONAL_DELTAS,
    )

    assert mapping["grass7:r.neighbors"] == "L3_03_02_03"
    assert mapping["saga:featuresbuffer"] == "L3_02_01_01"
    assert mapping["saga:polygonselfintersection"] == "L3_01_05_01"
    assert mapping["native:extractwithindistance"] == "L3_02_06_03"
    assert "qgis:basicstatisticsforfields" not in mapping
    assert "native:ruggednessindex" not in mapping


def test_current_mapping_is_applied_before_historical_recovery_routing() -> None:
    row = {
        "canonical_operator_ids": ["native:ruggednessindex"],
        "structure_action": "recover_call_graph",
        "structure_rule_id": "recover-missing-data-edges-v1",
        "action": "recover_call_graph",
    }

    gated = MODULE.apply_l3_gate(
        row, {}, mapping_authority=MODULE.MAPPING_AUTHORITY
    )

    assert gated["action"] == "defer_mapping"
    assert gated["unmapped_operator_ids"] == ["native:ruggednessindex"]
    assert MODULE.build_recovery_units([gated])[0] == []


def test_write_outputs_keeps_full_operator_ledger_separate_from_direct_descriptions(
    tmp_path: Path,
) -> None:
    source_input = tmp_path / "input.jsonl"
    source_input.write_text("{}\n", encoding="utf-8")
    operator_rows = [
        {"record_id": "one", "action": "defer_mapping"},
        {"record_id": "two", "action": "auto_accept_candidate"},
    ]
    direct_rows = [{"record_id": "two", "action": "auto_accept_candidate"}]

    artifacts = MODULE.write_outputs(
        output_dir=tmp_path / "output",
        source_rows=[],
        source_failures=[],
        direct_rows=[],
        direct_failures=[],
        recovery_rows=[],
        recovery_summary={},
        split_rows=[],
        split_summary={},
        operator_rows=operator_rows,
        operator_description_rows=direct_rows,
        operator_summary={},
        operator_recovery_rows=[],
        operator_split_rows=[],
        candidates=[],
        selected=[],
        review=[],
        inputs=[source_input],
    )

    full = [json.loads(line) for line in artifacts["operator"].read_text().splitlines()]
    direct = [
        json.loads(line)
        for line in artifacts["operator_descriptions"].read_text().splitlines()
    ]
    summary = json.loads(artifacts["summary"].read_text(encoding="utf-8"))
    assert len(full) == 2
    assert len(direct) == 1
    assert summary["review_source_sha_zero_overlap"] is True
    assert summary["review_source_authority_zero_overlap"] is True
    assert summary["candidate_rule_signature_counts"] == {}
    assert summary["review_rule_signature_counts"] == {}
