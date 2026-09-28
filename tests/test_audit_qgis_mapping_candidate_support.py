from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_qgis_mapping_candidate_support.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_qgis_mapping_candidate_support", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _source(path: Path, body: str, repo: str) -> tuple[Path, str]:
    path.write_text(
        f"# Source repo: {repo}\n# Source path: workflow.py\n\n{body}\n",
        encoding="utf-8",
    )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_selects_candidate_sources_once() -> None:
    rows = [
        {
            "record_id": "both",
            "source_sha256": "a" * 64,
            "unmapped_operator_ids": ["native:first", "native:second"],
        },
        {
            "record_id": "other",
            "source_sha256": "b" * 64,
            "unmapped_operator_ids": ["native:other"],
        },
    ]

    selected = MODULE.select_candidate_rows(
        rows, {"native:first": "L3_FIRST", "native:second": "L3_SECOND"}
    )

    assert [row["record_id"] for row in selected] == ["both"]


def test_support_is_counted_per_operator_by_normalized_body(tmp_path: Path) -> None:
    first, first_sha = _source(
        tmp_path / "first.py", "processing.run('native:first', {})", "a/repo"
    )
    copy, copy_sha = _source(
        tmp_path / "copy.py", "processing.run('native:first', {})", "b/repo"
    )
    both, both_sha = _source(
        tmp_path / "both.py",
        "processing.run('native:first', {'VALUE': 2})\n"
        "processing.run('native:second', {})",
        "c/repo",
    )
    rows = [
        {
            "record_id": "first",
            "source_sha256": first_sha,
            "source_path": str(first),
            "normalization_status": "fully_normalized",
            "unmapped_operator_ids": ["native:first"],
        },
        {
            "record_id": "copy",
            "source_sha256": copy_sha,
            "source_path": str(copy),
            "normalization_status": "fully_normalized",
            "unmapped_operator_ids": ["native:first"],
        },
        {
            "record_id": "both",
            "source_sha256": both_sha,
            "source_path": str(both),
            "normalization_status": "partially_normalized",
            "unmapped_operator_ids": ["native:first", "native:second"],
        },
    ]

    ledger, summary = MODULE.build_support_audit(
        rows,
        {"native:first": "L3_FIRST", "native:second": "L3_SECOND"},
        support_gate=2,
    )

    assert len(ledger) == 4
    assert summary["candidate_support"]["native:first"][
        "normalized_source_body_support"
    ] == 2
    assert summary["candidate_support"]["native:first"][
        "support_gate_passed"
    ] is True
    assert summary["candidate_support"]["native:second"][
        "normalized_source_body_support"
    ] == 1
    assert summary["candidate_support"]["native:second"][
        "support_gate_passed"
    ] is False
    assert summary["training_rows_emitted"] == 0


def test_combined_dry_run_reports_only_real_route_changes() -> None:
    rows = [
        {
            "record_id": "first-only",
            "canonical_operator_ids": ["native:first"],
            "normalization_status": "fully_normalized",
            "structure_action": "auto_accept_candidate",
            "structure_rule_id": "direct",
        },
        {
            "record_id": "both",
            "canonical_operator_ids": ["native:first", "native:second"],
            "normalization_status": "fully_normalized",
            "structure_action": "split_subworkflow",
            "structure_rule_id": "split",
        },
        {
            "record_id": "still-gap",
            "canonical_operator_ids": ["native:first", "native:unknown"],
            "normalization_status": "fully_normalized",
            "structure_action": "auto_accept_candidate",
            "structure_rule_id": "direct",
        },
    ]

    transitions, impact = MODULE.measure_dry_run(
        rows,
        {},
        {"native:first": "L3_FIRST", "native:second": "L3_SECOND"},
    )

    assert impact["by_operator"]["native:first"]["new_mapping_complete_rows"] == 1
    assert impact["by_operator"]["native:second"]["new_mapping_complete_rows"] == 0
    assert impact["combined"]["new_mapping_complete_rows"] == 2
    assert impact["combined"]["new_direct_rows"] == 1
    assert [row["record_id"] for row in transitions] == ["both", "first-only"]
    assert all(not row["training_row_emitted"] for row in transitions)
