from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_qgis_stable106_structural_increment.py"
SPEC = importlib.util.spec_from_file_location("build_qgis_stable106_structural_increment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_isolates_new_recovery_and_split_routes() -> None:
    stable106 = _jsonl(
        ROOT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
    )
    authority = _jsonl(
        ROOT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/taxonomy_authority_v1/stable106_mapping_authority_v1.jsonl"
    )

    rows, summary = MODULE.build_increment(stable106, authority)

    assert len(rows) == 51
    assert summary["new_action_counts"] == {
        "recover_call_graph": 24,
        "split_subworkflow": 27,
    }
    assert all(row["baseline_action"] != row["action"] for row in rows)
    assert all(row["training_admission"] == "not_granted_pending_structural_replay" for row in rows)
    assert summary["training_rows_emitted"] == 0
