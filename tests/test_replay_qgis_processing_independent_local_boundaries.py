from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.replay_qgis_processing_independent_local_boundaries import (
    replay_boundaries,
)


def _row(path: Path, source: str) -> dict[str, object]:
    path.write_text(source, encoding="utf-8")
    return {
        "record_id": "record-1",
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_path": str(path),
        "source_root_id": "fixture",
        "status": "deferred_boundary",
        "route_action": "review_api_sidecar",
        "operator_sequence": ["native:fixgeometries", "native:buffer"],
        "call_sites": [
            {"operator_id": "native:fixgeometries", "line_start": 2, "line_end": 2},
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 3},
        ],
    }


def test_recovers_structural_boundary_cluster_from_source(tmp_path: Path) -> None:
    source = """def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
"""
    units, clusters, outcome = replay_boundaries(
        [_row(tmp_path / "workflow.py", source)], excluded_source_sha256=set()
    )

    assert len(units) == 1
    assert units[0]["split_class"] == "multi_step_local_dag"
    assert units[0]["local_structure_status"] == "eligible"
    assert clusters[0]["independent_source_sha256_support"] == 1
    assert clusters[0]["boundary_signature"]["node_count"] == 2
    assert outcome["summary"]["source_verified_parents"] == 1
    assert outcome["summary"]["training_rows_emitted"] == 0


def test_rejects_mismatched_or_unsafe_rows_before_source_read(tmp_path: Path) -> None:
    source = """def run(layer):
    return processing.run("native:fixgeometries", {"INPUT": layer})
"""
    row = _row(tmp_path / "workflow.py", source)
    row["call_sites"] = [
        {"operator_id": "native:buffer", "line_start": 2, "line_end": 2}
    ]
    unsafe = dict(row)
    unsafe["record_id"] = "record-2"
    unsafe["source_sha256"] = "unsafe"
    unsafe["operator_sequence"] = ["native:createspatialindex"]
    unsafe["call_sites"] = [
        {"operator_id": "native:createspatialindex", "line_start": 2, "line_end": 2}
    ]

    units, clusters, outcome = replay_boundaries(
        [row, unsafe], excluded_source_sha256=set()
    )

    assert units == []
    assert clusters == []
    assert outcome["summary"]["source_verified_parents"] == 0
    assert (
        outcome["summary"]["exclusion_counts"]["missing_or_mismatched_call_evidence"]
        == 1
    )
    assert (
        outcome["summary"]["exclusion_counts"]["unsafe_database_or_support_operator"]
        == 1
    )


def test_reanchors_exact_qgis_to_native_alias_before_splitting(tmp_path: Path) -> None:
    source = """def run(layer):
    return processing.run("qgis:buffer", {"INPUT": layer})["OUTPUT"]
"""
    path = tmp_path / "workflow.py"
    row = _row(path, source)
    row["operator_sequence"] = ["native:buffer"]
    row["call_sites"] = [
        {"operator_id": "native:buffer", "line_start": 2, "line_end": 2}
    ]

    units, _, outcome = replay_boundaries([row], excluded_source_sha256=set())

    assert len(units) == 1
    assert units[0]["operator_ids"] == ["qgis:buffer"]
    assert units[0]["canonical_operator_ids"] == ["native:buffer"]
    assert units[0]["provider_migrations"][0]["source"] == "qgis:buffer"
    assert outcome["summary"]["provider_reanchored_parents"] == 1


def test_defers_overlong_parent_before_source_replay(tmp_path: Path) -> None:
    source = """def run(layer):
    return processing.run("native:buffer", {"INPUT": layer})["OUTPUT"]
"""
    row = _row(tmp_path / "workflow.py", source)
    row["operator_sequence"] = ["native:buffer"] * 3
    row["call_sites"] = [
        {"operator_id": "native:buffer", "line_start": 2, "line_end": 2}
        for _ in range(3)
    ]

    units, clusters, outcome = replay_boundaries(
        [row], excluded_source_sha256=set(), max_call_sites=2
    )

    assert units == []
    assert clusters == []
    assert outcome["summary"]["exclusion_counts"]["too_many_recorded_call_sites"] == 1


def test_limits_source_root_stratified_calibration_population(tmp_path: Path) -> None:
    source = """def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
"""
    rows = []
    for index in range(3):
        row = _row(tmp_path / f"workflow_{index}.py", f"{source}# {index}\n")
        row["record_id"] = f"record-{index}"
        row["source_root_id"] = f"root-{index}"
        rows.append(row)

    units, _, outcome = replay_boundaries(
        rows,
        excluded_source_sha256=set(),
        maximum_parents=2,
        seed=7,
    )

    assert outcome["summary"]["parent_population"] == 3
    assert outcome["summary"]["parent_candidates"] == 2
    assert len({row["source_sha256"] for row in units}) == 2
