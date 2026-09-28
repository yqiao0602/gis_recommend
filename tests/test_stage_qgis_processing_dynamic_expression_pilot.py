from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "stage_qgis_processing_dynamic_expression_pilot.py"
SPEC = importlib.util.spec_from_file_location("stage_dynamic_expression", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_rows_is_source_unique_and_disjoint() -> None:
    rows = [
        {"record_id": "a", "source_sha256": "a" * 64},
        {"record_id": "b", "source_sha256": "b" * 64},
        {"record_id": "c", "source_sha256": "c" * 64},
        {"record_id": "d", "source_sha256": "d" * 64},
    ]
    selected = MODULE.select_rows(rows, 2, excluded_shas=set())

    assert len(selected) == 4
    assert len({row["source_sha256"] for row in selected}) == 4


def test_remote_program_requires_processing_module_nonliteral_first_argument() -> None:
    program = MODULE.remote_program()

    assert "dynamic_expression_facts" in program
    assert "is_processing_call" in program
    assert "source_sha256_verified" in program
