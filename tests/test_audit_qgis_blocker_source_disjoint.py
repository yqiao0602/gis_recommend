from pathlib import Path

from scripts.audit_qgis_blocker_source_disjoint import audit


def _row(lane: str, digest: str, name: str = "sample.py") -> dict:
    return {
        "audit_lane": lane,
        "audit_role": "calibration",
        "source_path": f"/home/yll/{name}",
        "source_sha256": digest,
        "operator_ids": ["native:buffer", "native:dissolve"],
        "call_sites": [
            {"line_start": 1, "line_end": 1, "operator_id": "native:buffer"},
            {"line_start": 2, "line_end": 2, "operator_id": "native:dissolve"},
        ],
        "workflow_unit_scope": "whole_processing_scope",
        "downstream_data_transform_calls": [],
        "intermediate_data_transform_calls": [],
    }


def test_source_backed_recovery_is_gold(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text('processing.run("native:buffer", {})\nprocessing.run("native:dissolve", {})\n', encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    rows, summary = audit([_row("recover_call_graph", digest)], tmp_path)
    assert rows[0]["source_replay_status"] == "verified_sha256_ast"
    assert rows[0]["audit_decision"] == "gold"
    assert summary["gold_rows"] == 1


def test_missing_source_is_deferred(tmp_path: Path) -> None:
    rows, summary = audit([_row("review_api_sidecar", "0" * 64)], tmp_path)
    assert rows[0]["audit_decision"] == "deferred"
    assert summary["deferred_rows"] == 1
