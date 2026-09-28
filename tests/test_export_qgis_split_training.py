from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.export_qgis_split_training import (
    build_split_dedup_ledger,
    build_training_rows,
)


def _accepted(source: Path, *, unit_id: str) -> dict:
    return {
        "unit_id": unit_id,
        "parent_record_id": f"parent-{unit_id}",
        "source_root_id": "test-root",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_snippet": "1: processing.run(...)\n",
        "call_sites": [
            {"operator_id": "native:fixgeometries", "line_start": 1, "line_end": 1},
            {"operator_id": "native:reprojectlayer", "line_start": 2, "line_end": 2},
        ],
        "workflow_unit_scope": "local_subworkflow",
        "operator_ids": ["native:fixgeometries", "native:reprojectlayer"],
        "mapped_l3_chain": ["L3_FIX", "L3_REPROJECT"],
        "dependency_edges": [[0, 1]],
        "task_name": "局部工作流",
        "task_description": "在该局部工作流中修复几何并重投影。",
        "parameter_facts": [{}, {}],
        "known_omissions": ["outside_explicit_processing_dag_not_described"],
        "final_decision": "valid",
    }


def test_deduplicates_exact_pairs_and_builds_train_only_row(tmp_path: Path) -> None:
    first_source = tmp_path / "first.py"
    second_source = tmp_path / "second.py"
    first_source.write_text("processing.run(...)\n", encoding="utf-8")
    second_source.write_text("processing.run(...)\n# copy\n", encoding="utf-8")
    rows = [
        _accepted(first_source, unit_id="unit-1"),
        _accepted(second_source, unit_id="unit-2"),
    ]

    ledger, summary = build_split_dedup_ledger(rows)
    training = build_training_rows(
        ledger,
        code_to_id={"L3_FIX": 98, "L3_REPROJECT": 100},
    )

    assert summary["accepted_units"] == 2
    assert summary["canonical_rows"] == 1
    assert summary["suppressed_exact_training_pairs"] == 1
    assert len(training) == 1
    assert training[0]["training_admission"] == "granted_train_only_split_census_pilot"
    assert training[0]["split"] == "train_only_split_census_pilot"
    assert training[0]["l3_token_ids"] == [98, 100]
    assert training[0]["validation_eligible"] is False
    assert training[0]["test_eligible"] is False


def test_non_valid_unit_is_not_exported(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("processing.run(...)\n", encoding="utf-8")
    row = _accepted(source, unit_id="unit-1")
    row["final_decision"] = "defer"

    ledger, summary = build_split_dedup_ledger([row])

    assert ledger == []
    assert summary["accepted_units"] == 0
