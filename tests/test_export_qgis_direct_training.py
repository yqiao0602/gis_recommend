from scripts.export_qgis_direct_training import build_direct_dedup_ledger


def _candidate(record_id: str, description: str, source_sha: str) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": source_sha,
        "source_path": f"/{record_id}.py",
        "source_root_id": "test",
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 1, "line_end": 2},
            {"operator_id": "native:centroids", "line_start": 3, "line_end": 4},
        ],
        "operator_ids": ["native:buffer", "native:centroids"],
        "dependency_edges": [[0, 1]],
        "mapped_l3_chain": ["L3_A", "L3_B"],
        "task_name": "创建缓冲区并提取质心",
        "task_description": description,
        "workflow_unit_scope": "whole_processing_scope",
        "known_omissions": [],
        "source_snippet": "processing.run(...)\nprocessing.run(...)\n",
        "parameter_facts": [{"DISTANCE": 10}, {}],
    }


def _audit(record_id: str, *, passed: bool = True) -> dict:
    return {"record_id": record_id, "description_fidelity_passed": passed}


def test_exact_training_pairs_are_suppressed_across_sources() -> None:
    description = "创建缓冲区后，将缓冲区结果用于提取质心。"
    rows, summary = build_direct_dedup_ledger(
        [_candidate("a", description, "sha-a"), _candidate("b", description, "sha-b")],
        [_audit("a"), _audit("b")],
    )

    assert [row["dedup_decision"] for row in rows] == [
        "canonical_keep",
        "exact_training_pair_suppressed",
    ]
    assert summary["canonical_rows"] == 1


def test_same_dag_with_different_task_text_is_preserved() -> None:
    rows, summary = build_direct_dedup_ledger(
        [
            _candidate("a", "创建 10 米缓冲区后提取质心。", "sha-a"),
            _candidate("b", "创建 20 米缓冲区后提取质心。", "sha-b"),
        ],
        [_audit("a"), _audit("b")],
    )

    assert all(row["dedup_decision"] == "canonical_keep" for row in rows)
    assert summary["canonical_rows"] == 2


def test_failed_fidelity_rows_are_not_dedup_candidates() -> None:
    rows, summary = build_direct_dedup_ledger(
        [_candidate("a", "创建缓冲区后提取质心。", "sha-a")],
        [_audit("a", passed=False)],
    )

    assert rows == []
    assert summary["fidelity_failed_rows"] == 1
