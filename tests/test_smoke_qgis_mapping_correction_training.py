from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_correction_training_row_passes_real_loader_loss_backward(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    from scripts.smoke_qgis_mapping_correction_training import run_loader_loss_smoke

    row = {
        "schema_version": "qgis_mapping_correction_training_sample_v1",
        "sample_id": "sample-1",
        "l3_sequence": [-3, 9, -4],
        "l3_token_ids": [9],
        "task_metadata": {
            "task_type": "QGIS可验证Processing工作流",
            "task_name": "计算线交点",
            "task_description": "计算两个线图层的交点。",
        },
        "training_admission": "granted_train_only_mapping_correction",
        "split": "train_only_mapping_correction",
        "validation_eligible": False,
        "test_eligible": False,
        "source_verification": "carried_forward_verified_normalized_source_body",
        "source_authority_key": "normalized_source_body_sha256:body-1",
        "sample_weight": 1.0,
    }
    path = tmp_path / "row.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    result = run_loader_loss_smoke(path)

    assert result["rows_seen_by_loader"] == 1
    assert result["loss_finite"] is True
    assert result["gradient_finite"] is True
    assert result["checkpoint_written"] is False
    assert result["training_run"] is False
