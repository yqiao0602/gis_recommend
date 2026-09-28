from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_qgis_stable118_structure_increment.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_qgis_stable118_structure_increment", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _parent(record_id: str, action: str) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": (record_id * 64)[:64],
        "action": action,
    }


def _unit(operator: str, l3_code: str, *, description_ok: bool = True) -> dict:
    return {
        "parent_record_id": f"parent-{operator}",
        "source_sha256": hashlib.sha256(operator.encode()).hexdigest(),
        "source_authority_key": f"body:{operator}",
        "operator_ids": [operator],
        "mapped_l3_chain": [l3_code],
        "call_sites": [
            {"operator_id": operator, "line_start": 1, "line_end": 1}
        ],
        "dependency_edges": [],
        "split_class": "single_step_local_unit",
        "local_structure_status": "single_step_not_training_target",
        "local_structure_reasons": [],
        "description_fidelity_passed": description_ok,
        "task_name": operator,
        "task_description": f"Run {operator}.",
    }


def test_selects_only_new_structure_routes_from_defer_mapping() -> None:
    baseline = [
        _parent("split", "defer_mapping"),
        _parent("recovery", "defer_mapping"),
        _parent("direct", "defer_mapping"),
        _parent("unchanged", "split_subworkflow"),
    ]
    proposal = [
        _parent("split", "split_subworkflow"),
        _parent("recovery", "recover_call_graph"),
        _parent("direct", "auto_accept_candidate"),
        _parent("unchanged", "split_subworkflow"),
    ]

    rows = MODULE.select_structure_transitions(baseline, proposal)

    assert [row["record_id"] for row in rows] == ["recovery", "split"]
    assert {row["proposal_action"] for row in rows} == {
        "recover_call_graph",
        "split_subworkflow",
    }
    assert all(row["baseline_action"] == "defer_mapping" for row in rows)


def test_structure_transition_selection_requires_matching_identity_sets() -> None:
    with pytest.raises(ValueError, match="identity sets differ"):
        MODULE.select_structure_transitions(
            [_parent("one", "defer_mapping")],
            [_parent("two", "split_subworkflow")],
        )


def test_classifies_only_stable110_units_as_mapping_eligible() -> None:
    stable = _unit("native:buffer", "L3_BUFFER")
    proposal_only = _unit("native:new", "L3_NEW")
    bad_description = _unit(
        "native:fixgeometries", "L3_FIX", description_ok=False
    )

    eligible, deferred = MODULE.classify_units_for_stable_mapping(
        [stable, proposal_only, bad_description],
        stable_mapping={
            "native:buffer": "L3_BUFFER",
            "native:fixgeometries": "L3_FIX",
        },
    )

    assert [row["operator_ids"] for row in eligible] == [["native:buffer"]]
    reasons = {row["operator_ids"][0]: row["stable_mapping_gate_reasons"] for row in deferred}
    assert reasons["native:new"] == ["proposal_only_operator:native:new"]
    assert reasons["native:fixgeometries"] == ["description_fidelity_failed"]


def test_materializes_remote_sources_once_per_sha_and_verifies_bytes(
    tmp_path: Path,
) -> None:
    payload = b"print('source')\n"
    digest = hashlib.sha256(payload).hexdigest()
    calls: list[str] = []

    def fetch(path: str) -> bytes:
        calls.append(path)
        return payload

    rows = [
        {"record_id": "a", "source_path": "/home/yll/a.py", "source_sha256": digest},
        {"record_id": "b", "source_path": "/home/yll/b.py", "source_sha256": digest},
    ]

    materialized = MODULE.materialize_sources(rows, tmp_path, fetch)

    assert calls == ["/home/yll/a.py"]
    assert len(materialized) == 2
    assert materialized[0]["source_path_original"] == "/home/yll/a.py"
    assert Path(materialized[0]["source_path"]).read_bytes() == payload
    assert materialized[0]["source_path"] == materialized[1]["source_path"]


def test_materialize_rejects_remote_sha_mismatch(tmp_path: Path) -> None:
    rows = [
        {
            "record_id": "bad",
            "source_path": "/home/yll/bad.py",
            "source_sha256": "0" * 64,
        }
    ]

    with pytest.raises(ValueError, match="source SHA mismatch"):
        MODULE.materialize_sources(rows, tmp_path, lambda _: b"wrong")


def test_materialize_uses_explicit_remote_prefix_alias(tmp_path: Path) -> None:
    payload = b"print('moved')\n"
    digest = hashlib.sha256(payload).hexdigest()
    requested: list[str] = []

    def fetch(path: str) -> bytes:
        requested.append(path)
        if path == "/old/source.py":
            raise FileNotFoundError(path)
        return payload

    rows = [
        {
            "record_id": "moved",
            "source_path": "/old/source.py",
            "source_sha256": digest,
        }
    ]

    materialized = MODULE.materialize_sources(
        rows,
        tmp_path,
        fetch,
        path_aliases=[("/old", "/new")],
    )

    assert requested == ["/old/source.py", "/new/source.py"]
    assert materialized[0]["source_path_resolved_remote"] == "/new/source.py"
