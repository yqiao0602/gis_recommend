from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.build_qgis_recovery_local_dag_units import (
    build_recovery_units,
    classify_recovery_unit,
)


def _unit(*, reasons: list[str], edges: list[list[int]]) -> dict:
    return {
        "split_class": "multi_step_local_dag",
        "local_structure_status": "eligible" if not reasons else "deferred",
        "local_structure_reasons": reasons,
        "operator_ids": ["native:buffer", "native:fixgeometries", "native:mergevectorlayers"],
        "dependency_edges": edges,
    }


def test_accepts_existing_low_risk_connected_dag() -> None:
    decision = classify_recovery_unit(
        _unit(reasons=[], edges=[[0, 1], [1, 2]]),
        parent_rule_id="recover-cross-scope-candidate-v1",
    )

    assert decision["recovery_structure_status"] == "eligible"
    assert decision["recovery_rule_id"] == "recovery-connected-local-dag-v1"


def test_accepts_multi_root_single_sink_fanin() -> None:
    decision = classify_recovery_unit(
        _unit(reasons=["missing_data_edges"], edges=[[0, 2], [1, 2]]),
        parent_rule_id="recover-missing-data-edges-v1",
    )

    assert decision["recovery_structure_status"] == "eligible"
    assert decision["recovery_rule_id"] == "recovery-multi-root-fanin-dag-v1"
    assert decision["root_indices"] == [0, 1]
    assert decision["sink_indices"] == [2]


def test_keeps_risky_or_multi_sink_units_deferred() -> None:
    risky = classify_recovery_unit(
        _unit(
            reasons=["control_flow:if", "missing_data_edges"],
            edges=[[0, 2], [1, 2]],
        ),
        parent_rule_id="recover-missing-data-edges-v1",
    )
    multi_sink = classify_recovery_unit(
        _unit(reasons=["missing_data_edges"], edges=[[0, 2], [1, 2], [1, 0]]),
        parent_rule_id="recover-missing-data-edges-v1",
    )

    assert risky["recovery_structure_status"] == "deferred"
    assert multi_sink["recovery_structure_status"] == "deferred"


def test_builds_source_verified_candidates_without_training_admission(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fanin.py"
    source.write_text(
        '''def run(left, right):
    left_buffer = processing.run("native:buffer", {"INPUT": left})
    right_buffer = processing.run("native:buffer", {"INPUT": right})
    return processing.run("native:mergevectorlayers", {"LAYERS": [left_buffer["OUTPUT"], right_buffer["OUTPUT"]]})
''',
        encoding="utf-8-sig",
    )
    parent = {
        "record_id": "fanin-parent",
        "source_root_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rule_id": "recover-missing-data-edges-v1",
        "action": "recover_call_graph",
        "signature_hash": "parent-signature",
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 3},
            {
                "operator_id": "native:mergevectorlayers",
                "line_start": 4,
                "line_end": 4,
            },
        ],
        "mapped_l3_chain": ["L3_BUFFER", "L3_BUFFER", "L3_MERGE"],
    }

    rows, summary = build_recovery_units([parent])

    assert summary["eligible_multi_step_units"] == 1
    assert summary["eligible_source_disjoint_support"] == 1
    assert len(rows) == 1
    assert rows[0]["recovery_rule_id"] == "recovery-multi-root-fanin-dag-v1"
    assert rows[0]["mapped_l3_chain"] == ["L3_BUFFER", "L3_BUFFER", "L3_MERGE"]
    assert rows[0]["description_fidelity_passed"] is True
    assert rows[0]["training_admission"] == "not_granted_pending_recovery_rule_audit"
    assert rows[0]["training_row_emitted"] is False


def test_builds_recovery_units_from_fixed_dynamic_operator_ids(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dynamic.py"
    source.write_text(
        '''def run(layer):
    first_id = "native:buffer"
    first = processing.run(first_id, {"INPUT": layer})["OUTPUT"]
    second_id = "native:fixgeometries"
    return processing.run(second_id, {"INPUT": first})
''',
        encoding="utf-8",
    )
    parent = {
        "schema": "gis_recommend.qgis_recovered_processing_l3_gate.v1",
        "record_id": "dynamic-recovery-parent",
        "source_root_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rule_id": "recover-control-flow-v1",
        "action": "recover_call_graph",
        "signature_hash": "parent-signature",
        "resolution_status": "fixed_chain_recovered",
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 3},
            {
                "operator_id": "native:fixgeometries",
                "line_start": 5,
                "line_end": 5,
            },
        ],
        "mapped_l3_chain": ["L3_BUFFER", "L3_FIX"],
    }

    rows, summary = build_recovery_units([parent])

    assert summary["failed_parent_rows"] == 0
    assert len(rows) == 1
    assert rows[0]["operator_ids"] == [
        "native:buffer",
        "native:fixgeometries",
    ]
    assert [site["line_start"] for site in rows[0]["call_sites"]] == [3, 5]


def test_builds_recovery_units_after_verified_provider_normalization(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy_provider.py"
    source.write_text(
        '''def run(layer):
    buffered = processing.run("qgis:buffer", {"INPUT": layer})["OUTPUT"]
    return processing.run("qgis:fixgeometries", {"INPUT": buffered})
''',
        encoding="utf-8",
    )
    parent = {
        "record_id": "legacy-provider-recovery-parent",
        "source_root_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rule_id": "recover-control-flow-v1",
        "action": "recover_call_graph",
        "signature_hash": "parent-signature",
        "provider_migrations": [
            {
                "source": "qgis:buffer",
                "target": "native:buffer",
                "rule": "qgis_to_native_same_slug",
            },
            {
                "source": "qgis:fixgeometries",
                "target": "native:fixgeometries",
                "rule": "qgis_to_native_same_slug",
            },
        ],
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
            {
                "operator_id": "native:fixgeometries",
                "line_start": 3,
                "line_end": 3,
            },
        ],
        "mapped_l3_chain": ["L3_BUFFER", "L3_FIX"],
    }

    rows, summary = build_recovery_units([parent])

    assert summary["failed_parent_rows"] == 0
    assert len(rows) == 1
    assert rows[0]["operator_ids"] == ["native:buffer", "native:fixgeometries"]
    assert rows[0]["source_sha256"] == parent["source_sha256"]
