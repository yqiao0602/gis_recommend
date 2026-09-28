from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "lineintersections_mapping_correction_v1/training_package_v1"
    / "mapping_correction_train_only_v1.jsonl"
)


def test_loader_preflight_accepts_isolated_stable110_package() -> None:
    smoke = importlib.import_module("scripts.smoke_qgis_stable101_training_jsonl")
    rows = smoke.load_training_rows(
        PACKAGE,
        expected_rows=1,
        expected_admission="granted_train_only_mapping_correction",
        expected_split="train_only_mapping_correction",
        expected_schema="qgis_mapping_correction_training_sample_v1",
        max_content_token=109,
        verify_local_source=False,
    )
    assert len(rows) == 1
    assert max(rows[0]["l3_token_ids"]) == 108
    assert rows[0]["validation_eligible"] is False
    assert rows[0]["test_eligible"] is False
