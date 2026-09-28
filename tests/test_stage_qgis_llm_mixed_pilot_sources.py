from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "stage_qgis_llm_mixed_pilot_sources.py"
SPEC = importlib.util.spec_from_file_location("mixed_stage", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(pool: str, index: int, sha_suffix: str) -> dict[str, str]:
    return {
        "pool": pool,
        "record_id": f"record-{pool}-{index}",
        "source_sha256": f"{sha_suffix}{index:063d}"[:64],
        "source_path": f"/home/yll/{pool}/{index}.py",
    }


def test_select_rows_is_deterministic_and_excludes_cross_pool_sha() -> None:
    rows = [_row("processing", 2, "a"), _row("processing", 1, "a"), _row("api", 1, "b")]

    selected = MODULE.select_rows(rows, pool="processing", count=2, excluded_shas=set(), scan_limit=3)

    assert [row["record_id"] for row in selected] == ["record-processing-1", "record-processing-2"]
    with pytest.raises(ValueError, match="unable to select"):
        MODULE.select_rows(rows, pool="api", count=2, excluded_shas={selected[0]["source_sha256"]}, scan_limit=3)


def test_remote_program_requires_sha_and_ast_validation() -> None:
    program = MODULE.remote_program()

    assert "hashlib.sha256(raw).hexdigest() != expected" in program
    assert "ast.parse(source)" in program
    assert '"training_rows_emitted": False' in program
