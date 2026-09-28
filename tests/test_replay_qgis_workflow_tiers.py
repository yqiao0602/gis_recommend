from __future__ import annotations

from pathlib import Path

from scripts.replay_qgis_workflow_tiers import replay


def _row(path: Path, sha256: str, tier: str) -> dict[str, object]:
    return {
        "record_id": "record-1",
        "source_sha256": sha256,
        "source_path": str(path),
        "pool": "processing",
        "source_role": "user_workflow",
        "workflow_value_tier": tier,
        "processing_run_count": 2,
        "task_semantic_signal": True,
        "input_output_signal": True,
        "data_dependency_signal": True,
    }


def test_replay_admits_only_structural_candidate_and_keeps_training_closed(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "buffered = processing.run('native:buffer', {'INPUT': 'roads', 'OUTPUT': 'TEMPORARY_OUTPUT'})\n"
        "processing.run('native:dissolve', {'INPUT': buffered['OUTPUT'], 'OUTPUT': 'out'})\n",
        encoding="utf-8",
    )
    from scripts.replay_qgis_workflow_tiers import sha256_file

    rows, summary = replay(
        [_row(source, sha256_file(source), "tier1_multi_step_workflow")],
        {"native:buffer", "native:dissolve"},
        {"native:buffer": "L3_BUFFER", "native:dissolve": "L3_DISSOLVE"},
    )
    assert rows[0]["status"] == "candidate_pending_description"
    assert rows[0]["dependency_edges"] == [[0, 1]]
    assert rows[0]["training_rows_emitted"] == 0
    assert summary["candidate_rows_pending_description"] == 1


def test_replay_defers_unmapped_literal_operator(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text("import processing\nprocessing.run('native:buffer', {'INPUT': 'roads'})\n", encoding="utf-8")
    from scripts.replay_qgis_workflow_tiers import sha256_file

    rows, summary = replay(
        [_row(source, sha256_file(source), "tier2_single_operator_workflow")],
        {"native:buffer"},
        {},
    )
    assert rows[0]["status"] == "deferred_mapping"
    assert rows[0]["unmapped_operator_ids"] == ["native:buffer"]
    assert summary["training_rows_emitted"] == 0


def test_replay_keeps_unsupported_processing_entrypoint_out_of_boundary_counts(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text("import processing\nprocessing.runalg('native:buffer', {})\n", encoding="utf-8")
    from scripts.replay_qgis_workflow_tiers import sha256_file

    rows, _ = replay(
        [_row(source, sha256_file(source), "tier2_single_operator_workflow")],
        {"native:buffer"},
        {"native:buffer": "L3_BUFFER"},
    )
    assert rows[0]["status"] == "deferred_extractor_unsupported"
    assert rows[0]["reason"] == "processing_entrypoint_not_supported_by_structural_extractor"


def test_replay_extracts_source_provider_before_alias_normalization(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\nprocessing.run('qgis:buffer', {'INPUT': 'roads'})\n",
        encoding="utf-8",
    )
    from scripts.replay_qgis_workflow_tiers import sha256_file

    rows, _ = replay(
        [_row(source, sha256_file(source), "tier2_single_operator_workflow")],
        {"native:buffer"},
        {"native:buffer": "L3_BUFFER"},
    )
    assert rows[0]["candidate_alignment_status"] == "candidate_alignment_matched"
    assert rows[0]["canonical_operator_ids"] == ["native:buffer"]
