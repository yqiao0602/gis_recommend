from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.build_qgis_recovery_local_dag_audit import (
    build_audit_packet,
    filter_candidates_by_replay,
)


def _row(source: Path, *, record_id: str, dag: str) -> dict:
    return {
        "unit_id": f"unit-{record_id}",
        "parent_record_id": record_id,
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_root_id": "fixture",
        "recovery_structure_status": "eligible",
        "recovery_rule_id": "recovery-multi-root-fanin-dag-v1",
        "operator_ids": ["native:buffer", "native:buffer", "native:mergevectorlayers"],
        "mapped_l3_chain": ["L3_BUFFER", "L3_BUFFER", "L3_MERGE"],
        "dependency_edges": [[0, 2], [1, 2]],
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 3},
            {"operator_id": "native:mergevectorlayers", "line_start": 4, "line_end": 4},
        ],
        "normalized_dag_key": dag,
        "task_name": "局部工作流：缓冲并合并",
        "task_description": "在该局部工作流中创建两个缓冲区并合并。",
        "parameter_facts": [{}, {}, {}],
        "known_omissions": ["outside_recovered_local_dag_not_described"],
        "description_fidelity_passed": True,
    }


def test_builds_source_disjoint_census_with_cluster_contrast(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    source_text = '''def run(left, right):
    left_buffer = processing.run("native:buffer", {"INPUT": left})
    right_buffer = processing.run("native:buffer", {"INPUT": right})
    return processing.run("native:mergevectorlayers", {"LAYERS": [left_buffer["OUTPUT"], right_buffer["OUTPUT"]]})
'''
    first.write_text(source_text, encoding="utf-8")
    second.write_text(source_text + "\n", encoding="utf-8")

    packet, summary = build_audit_packet(
        [_row(first, record_id="first", dag="dag-a"), _row(second, record_id="second", dag="dag-a")]
    )

    assert len(packet) == 2
    assert packet[0]["cluster_size"] == 2
    assert packet[0]["comparison_parent_record_id"] == "second"
    assert "processing.run" in packet[0]["comparison_source_snippet"]
    assert packet[0]["human_final_decision"] == ""
    assert summary["eligible_units"] == 2
    assert summary["source_disjoint_support"] == 2
    assert summary["unique_normalized_dags"] == 1
    assert summary["rule_training_eligible"] is False
    assert summary["training_rows_emitted"] == 0


def test_filters_candidates_to_rule_candidate_replay_rows() -> None:
    candidates = [
        {"parent_record_id": "accepted"},
        {"parent_record_id": "partial"},
    ]
    replay = [
        {"record_id": "accepted", "replay_status": "rule_candidate"},
        {"record_id": "partial", "replay_status": "partial_rule_candidate"},
    ]

    assert filter_candidates_by_replay(candidates, replay) == [candidates[0]]
