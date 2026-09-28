from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_qgis_snap_taxonomy_candidate.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_qgis_snap_taxonomy_candidate", SCRIPT
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


def test_selects_snap_gap_rows_once() -> None:
    rows = [
        {
            "record_id": "snap",
            "source_sha256": "a" * 64,
            "unmapped_operator_ids": ["native:snapgeometries"],
        },
        {
            "record_id": "other",
            "source_sha256": "b" * 64,
            "unmapped_operator_ids": ["native:pointstopath"],
        },
    ]

    selected = MODULE.select_snap_rows(rows)

    assert [row["record_id"] for row in selected] == ["snap"]


def test_support_counts_normalized_bodies_not_harvest_copies(tmp_path: Path) -> None:
    first, first_sha = _source(tmp_path / "first.py", "processing.run('native:snapgeometries', {})", "a/repo")
    second, second_sha = _source(tmp_path / "second.py", "processing.run('native:snapgeometries', {})", "b/repo")
    third, third_sha = _source(tmp_path / "third.py", "processing.run('native:snapgeometries', {'TOLERANCE': 2})", "c/repo")
    rows = [
        {"record_id": "a", "source_sha256": first_sha, "source_path": str(first), "normalization_status": "fully_normalized"},
        {"record_id": "b", "source_sha256": second_sha, "source_path": str(second), "normalization_status": "fully_normalized"},
        {"record_id": "c", "source_sha256": third_sha, "source_path": str(third), "normalization_status": "partially_normalized"},
    ]

    ledger, summary = MODULE.build_support_audit(rows, support_gate=3)

    assert len(ledger) == 3
    assert summary["source_sha_verified_rows"] == 3
    assert summary["normalized_source_body_support"] == 2
    assert summary["support_gate_passed"] is False
    assert summary["taxonomy_admission"] == "not_granted_support_below_gate"
    assert summary["training_rows_emitted"] == 0


def test_builds_single_class_proposal_and_measures_only_real_route_changes() -> None:
    stable110 = {
        "proposed_taxonomy": "stable110",
        "existing_code_to_id": {"L3_BASE": 0},
        "proposed_code_to_id_additions": {"L3_LAST": 1},
    }
    hierarchy = {
        "l3_code": "L3_02_07_09",
        "l3_name": "Snap",
        "l3_description": "Moves vertices within a tolerance.",
        "l2_code": "L2_02_07",
        "l2_name": "Topology Operations",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
    }
    support = {
        "support_gate_passed": True,
        "normalized_source_body_support": 51,
        "support_gate": 30,
    }
    rows = [
        {
            "record_id": "snap-only",
            "canonical_operator_ids": ["native:snapgeometries"],
            "normalization_status": "fully_normalized",
            "structure_action": "auto_accept_candidate",
            "structure_rule_id": "direct",
        },
        {
            "record_id": "still-gap",
            "canonical_operator_ids": ["native:snapgeometries", "native:unknown"],
            "normalization_status": "fully_normalized",
            "structure_action": "auto_accept_candidate",
            "structure_rule_id": "direct",
        },
    ]

    extension, delta = MODULE.build_proposal(stable110, hierarchy, support)
    transitions, impact = MODULE.measure_dry_run(rows, {})

    assert extension["proposed_code_to_id_additions"] == {"L3_02_07_09": 2}
    assert delta["restored_l3_mappings"] == {"native:snapgeometries": "L3_02_07_09"}
    assert impact["new_mapping_complete_rows"] == 1
    assert impact["new_direct_rows"] == 1
    assert [row["record_id"] for row in transitions] == ["snap-only"]
    assert all(not row["training_row_emitted"] for row in transitions)
