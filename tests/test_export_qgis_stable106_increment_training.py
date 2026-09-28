from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_qgis_stable106_increment_training.py"
SPEC = importlib.util.spec_from_file_location("export_qgis_stable106_increment_training", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_exports_nine_source_replayed_train_only_rows() -> None:
    report = ROOT / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    result = MODULE.build_training_rows(
        ledger=_jsonl(report / "direct_increment_dedup_v1/incremental_dedup_ledger_v1.jsonl"),
        candidates=_jsonl(report / "direct_descriptions_v1/direct_description_candidates_v1.jsonl"),
        replay=_jsonl(report / "source_replay_v1/source_replay_v1.jsonl"),
        extension=_json(report / "stable106_extension_proposal_v1.json"),
        authority=_jsonl(report / "taxonomy_authority_v1/stable106_mapping_authority_v1.jsonl"),
        existing_train=_jsonl(ROOT / "docs/reports/qgis_unified_train_v3/qgis_unified_train_v1.jsonl"),
    )

    assert len(result.rows) == 9
    assert result.summary["counts"]["exported_rows"] == 9
    assert all(row["training_admission"] == "granted_train_only_stable106_increment" for row in result.rows)
    assert all(row["validation_eligible"] is False and row["test_eligible"] is False for row in result.rows)
    assert all(row["source_verification"] == "verified_sha256" for row in result.rows)
    assert all(row["l3_sequence"] == [-3, *row["l3_token_ids"], -4] for row in result.rows)
    assert max(token for row in result.rows for token in row["l3_token_ids"]) == 105
    assert result.summary["decision"]["production_merge"] == "not_granted"
    assert result.summary["decision"]["training_run"] is False
