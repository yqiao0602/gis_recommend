from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.build_qgis_split_unit_audit import build_audit_packet


def _row(source: Path, *, unit_id: str, status: str = "eligible") -> dict:
    return {
        "unit_id": unit_id,
        "parent_record_id": f"parent-{unit_id}",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_root_id": "test",
        "lexical_scope": "run",
        "split_class": "multi_step_local_dag",
        "local_structure_status": status,
        "local_structure_reasons": [],
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
        "call_sites": [
            {"operator_id": "native:fixgeometries", "line_start": 2, "line_end": 2},
            {"operator_id": "native:reprojectlayer", "line_start": 3, "line_end": 3},
        ],
        "normalized_dag_key": "dag-1",
        "task_name": "局部工作流",
        "task_description": "在该局部工作流中处理图层。",
        "description_fidelity_passed": True,
    }


def test_builds_full_eligible_population_with_source_evidence(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        '''def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:reprojectlayer", {"INPUT": fixed})
''',
        encoding="utf-8",
    )
    eligible = _row(source, unit_id="unit-1")
    deferred = _row(source, unit_id="unit-2", status="deferred")

    packet, summary = build_audit_packet([eligible, deferred])

    assert len(packet) == 1
    assert packet[0]["review_position"] == 1
    assert packet[0]["source_hash_verified"] is True
    assert "native:fixgeometries" in packet[0]["source_snippet"]
    assert packet[0]["human_final_decision"] == ""
    assert packet[0]["training_row_emitted"] is False
    assert summary["eligible_units"] == 1
    assert summary["unique_sources"] == 1
    assert summary["population_census"] is True
    assert summary["rule_training_eligible"] is False


def test_source_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text("pass\n", encoding="utf-8")
    row = _row(source, unit_id="unit-1")
    row["source_sha256"] = "0" * 64

    try:
        build_audit_packet([row])
    except ValueError as exc:
        assert "source SHA" in str(exc)
    else:
        raise AssertionError("expected source hash mismatch to fail closed")
