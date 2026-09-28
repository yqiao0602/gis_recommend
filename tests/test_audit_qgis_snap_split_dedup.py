from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_qgis_snap_split_dedup.py"
SPEC = importlib.util.spec_from_file_location("audit_qgis_snap_split_dedup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _candidate(
    unit_id: str,
    source_sha256: str,
    task_description: str,
    *,
    line_start: int = 1,
) -> dict:
    return {
        "unit_id": unit_id,
        "parent_record_id": f"parent-{unit_id}",
        "source_sha256": source_sha256,
        "source_path": f"/{unit_id}.py",
        "split_class": "multi_step_local_dag",
        "local_structure_status": "eligible",
        "description_fidelity_passed": True,
        "call_sites": [
            {
                "operator_id": "native:fixgeometries",
                "line_start": line_start,
                "line_end": line_start,
            },
            {
                "operator_id": "native:extractbyexpression",
                "line_start": line_start + 1,
                "line_end": line_start + 1,
            },
        ],
        "operator_ids": ["native:fixgeometries", "native:extractbyexpression"],
        "mapped_l3_chain": ["L3_01_05_02", "L3_02_06_02"],
        "dependency_edges": [[0, 1]],
        "workflow_unit_scope": "local_subworkflow",
        "task_name": "修复并筛选",
        "task_description": task_description,
    }


def test_dedup_keeps_only_net_new_exact_pairs_without_granting_training() -> None:
    first = _candidate("first", "a" * 64, "修复几何并筛选有效要素。")
    duplicate_pair = _candidate("copy", "b" * 64, "修复几何并筛选有效要素。")
    same_dag_new_text = _candidate("new-text", "c" * 64, "修复几何并筛选目标要素。")
    existing_pair = _candidate("existing-pair", "d" * 64, "正式池已有任务。")
    existing = [
        {
            "sample_id": "existing-1",
            "source_region_key": "unrelated-region",
            "call_graph_key": "unrelated-graph",
            "normalized_dag_key": MODULE._normalized_dag_key(existing_pair),
            "task_name": existing_pair["task_name"],
            "task_description": existing_pair["task_description"],
            "operator_sequence": existing_pair["operator_ids"],
            "l3_code_sequence": existing_pair["mapped_l3_chain"],
        }
    ]

    ledger, canonical, summary = MODULE.build_snap_split_dedup(
        [first, duplicate_pair, same_dag_new_text, existing_pair], existing
    )

    assert [row["dedup_decision"] for row in ledger] == [
        "canonical_proposal_keep",
        "candidate_exact_training_pair_suppressed",
        "canonical_proposal_keep",
        "existing_exact_training_pair_suppressed",
    ]
    assert [row["unit_id"] for row in canonical] == ["first", "new-text"]
    assert canonical[1]["normalized_dag_relation"] == "existing_overlap_preserved"
    assert summary["eligible_candidates"] == 4
    assert summary["net_new_canonical_proposals"] == 2
    assert summary["net_new_by_taxonomy_route"] == {"stable110_existing": 2}
    assert summary["training_rows_emitted"] == 0
    assert all(row["taxonomy_route"] == "stable110_existing" for row in canonical)
    assert all(row["taxonomy_profile"] == "stable110_authority_v1" for row in canonical)
    assert all(row["proposal_only"] for row in ledger)
    assert all(not row["training_row_emitted"] for row in ledger)
