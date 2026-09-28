from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_qgis_processing_mapping_gap_stable106_increment.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_qgis_processing_mapping_gap_stable106_increment", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_incremental_ledger = MODULE.build_incremental_ledger
evidence_keys = MODULE.evidence_keys


def _candidate(record_id: str, source: str, description: str) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": source,
        "call_sites": [
            {
                "ordinal": 1,
                "operator_id": "native:creategrid",
                "line_start": 10,
                "line_end": 10,
            }
        ],
        "operator_ids": ["native:creategrid"],
        "dependency_edges": [],
        "mapped_l3_chain": ["L3_02_03_06"],
        "workflow_unit_scope": "whole_processing_scope",
        "task_name": "创建矢量网格",
        "task_description": description,
    }


def test_keeps_one_new_pair_after_fidelity_and_existing_authority_dedup() -> None:
    baseline = [{"record_id": "old", "action": "auto_accept_candidate"}]
    candidates = [
        _candidate("old", "sha-old", "旧描述"),
        _candidate("new-a", "sha-a", "创建规则矢量网格。"),
        _candidate("new-b", "sha-b", "创建规则矢量网格。"),
        _candidate("new-c", "sha-c", "待修复描述"),
    ]
    fidelity = [
        {"record_id": "old", "description_fidelity_passed": True},
        {"record_id": "new-a", "description_fidelity_passed": True},
        {"record_id": "new-b", "description_fidelity_passed": True},
        {"record_id": "new-c", "description_fidelity_passed": False},
    ]

    ledger, summary = build_incremental_ledger(
        baseline, candidates, fidelity, existing_train_rows=[]
    )

    assert [row["dedup_decision"] for row in ledger] == [
        "canonical_keep_candidate",
        "exact_training_pair_suppressed",
        "fidelity_deferred",
    ]
    assert summary["new_direct_rows"] == 3
    assert summary["fidelity_passed_rows"] == 2
    assert summary["canonical_candidate_rows"] == 1
    assert summary["training_rows_emitted"] == 0


def test_existing_source_region_has_priority() -> None:
    candidate = _candidate("new-a", "sha-a", "创建规则矢量网格。")
    region, _, _ = evidence_keys(candidate)
    existing = [
        {
            "sample_id": "existing-1",
            "source_region_key": region,
            "call_graph_key": "other-graph",
            "unified_training_pair_key": "other-pair",
        }
    ]

    ledger, _ = build_incremental_ledger(
        [],
        [candidate],
        [{"record_id": "new-a", "description_fidelity_passed": True}],
        existing_train_rows=existing,
    )

    assert ledger[0]["dedup_decision"] == "existing_source_region_suppressed"
    assert ledger[0]["canonical_id"] == "existing-1"


def test_exact_pair_prefers_verified_source_candidate() -> None:
    missing = _candidate("missing", "sha-missing", "创建规则矢量网格。")
    missing["parameter_evidence_status"] = "source_file_missing"
    verified = _candidate("verified", "sha-verified", "创建规则矢量网格。")
    verified["parameter_evidence_status"] = "verified_source_ast"

    ledger, _ = build_incremental_ledger(
        [],
        [missing, verified],
        [
            {"record_id": "missing", "description_fidelity_passed": True},
            {"record_id": "verified", "description_fidelity_passed": True},
        ],
        existing_train_rows=[],
    )

    by_id = {row["record_id"]: row for row in ledger}
    assert by_id["verified"]["dedup_decision"] == "canonical_keep_candidate"
    assert by_id["missing"]["dedup_decision"] == "source_replay_deferred"


def test_merges_multiple_existing_train_authorities() -> None:
    rows = MODULE.merge_existing_train_groups(
        [[{"sample_id": "old-1"}], [{"sample_id": "stable106-1"}]]
    )

    assert [row["sample_id"] for row in rows] == ["old-1", "stable106-1"]
