from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_qgis_custom_scope_training.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_qgis_custom_scope_training", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_training_package = MODULE.build_training_package


def _candidate(path: Path, *, status: str = "canonical_candidate") -> dict:
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "record_id": "custom-demo",
        "algorithm_id": "script:demo",
        "source_root_id": "fixture",
        "source_path": str(path),
        "source_sha256": source_sha256,
        "call_sites": [
            {
                "line_start": 3,
                "line_end": 3,
                "operator_id": "native:buffer",
            },
            {
                "line_start": 4,
                "line_end": 4,
                "operator_id": "qgis:fieldcalculator",
            },
        ],
        "operator_ids": ["native:buffer", "native:fieldcalculator"],
        "mapped_l3_chain": ["L3_BUFFER", "L3_FIELD"],
        "dependency_edges": [[0, 1]],
        "parameter_facts": [{"DISTANCE": 10}, {"FIELD_NAME": "id"}],
        "known_omissions": [],
        "workflow_unit_scope": "whole_processing_scope",
        "task_name": "缓冲并计算字段",
        "task_description": "先创建缓冲区，再计算字段。",
        "description_fidelity_passed": True,
        "mapping_complete": True,
        "parameter_evidence_status": "verified_source_ast",
        "dedup_status": status,
        "dedup_source_region_key": "region-key",
        "dedup_call_graph_key": "graph-key",
        "dedup_normalized_dag_key": "dag-key",
        "dedup_training_pair_key": "pair-key",
    }


def _extension() -> dict:
    return {
        "proposed_taxonomy": "stable110",
        "proposed_class_count": 2,
        "existing_code_to_id": {"L3_BUFFER": 0, "L3_FIELD": 1},
        "proposed_code_to_id_additions": {},
        "existing_token_ids_unchanged": True,
    }


def test_exports_only_canonical_source_replayed_custom_scopes(tmp_path: Path) -> None:
    source = tmp_path / "custom.py"
    source.write_text(
        "def run(parameters):\n"
        "    import processing\n"
        "    buffered = processing.run('native:buffer', parameters)\n"
        "    return processing.run('qgis:fieldcalculator', {'INPUT': buffered['OUTPUT']})\n",
        encoding="utf-8",
    )
    canonical = _candidate(source)
    duplicate = {**_candidate(source, status="duplicate_training_pair"), "record_id": "duplicate"}

    package = build_training_package(
        [canonical, duplicate],
        extension=_extension(),
        mapping_authority="stable110_test_authority",
    )

    assert len(package.source_replay_rows) == 1
    assert package.source_replay_rows[0]["ast_verification"] == "verified_python_ast"
    assert package.source_replay_rows[0]["literal_operator_verification"] == "verified"
    assert len(package.training_rows) == 1
    row = package.training_rows[0]
    assert row["l3_token_ids"] == [0, 1]
    assert row["l3_sequence"] == [-3, 0, 1, -4]
    assert row["mapping_authority"] == "stable110_test_authority"
    assert row["training_admission"] == "granted_train_only_custom_scope"
    assert package.summary["counts"]["duplicate_rows"] == 1


def test_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "custom.py"
    source.write_text(
        "import processing\nprocessing.run('native:buffer', {})\n",
        encoding="utf-8",
    )
    candidate = _candidate(source)
    candidate["source_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source SHA mismatch"):
        build_training_package(
            [candidate],
            extension=_extension(),
            mapping_authority="stable110_test_authority",
        )


def test_defers_canonical_rows_that_lack_quality_evidence(tmp_path: Path) -> None:
    source = tmp_path / "custom.py"
    source.write_text(
        "def run(parameters):\n"
        "    import processing\n"
        "    buffered = processing.run('native:buffer', parameters)\n"
        "    return processing.run('qgis:fieldcalculator', {'INPUT': buffered['OUTPUT']})\n",
        encoding="utf-8",
    )
    valid = _candidate(source)
    deferred = {
        **_candidate(source),
        "record_id": "missing-evidence",
        "mapping_complete": None,
        "parameter_evidence_status": None,
    }

    package = build_training_package(
        [valid, deferred],
        extension=_extension(),
        mapping_authority="stable110_test_authority",
    )

    assert [row["record_id"] for row in package.training_rows] == ["custom-demo"]
    assert package.summary["counts"]["quality_deferred_rows"] == 1
