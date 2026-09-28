from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.build_qgis_split_subworkflow_units import build_split_units


def test_builds_mapped_local_units_and_keeps_training_closed(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        '''def clip_one(layer, mask):
    return processing.run("native:clip", {"INPUT": layer, "OVERLAY": mask})

def clean(layer, crs):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:reprojectlayer", {"INPUT": fixed, "TARGET_CRS": crs})
''',
        encoding="utf-8",
    )
    parent = {
        "record_id": "parent-1",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_root_id": "test",
        "signature_hash": "parent-signature",
        "rule_id": "split-disconnected-scopes-v1",
        "action": "split_subworkflow",
        "operator_ids": [
            "native:clip",
            "native:fixgeometries",
            "native:reprojectlayer",
        ],
        "mapped_l3_chain": ["L3_CLIP", "L3_FIX", "L3_REPROJECT"],
        "call_sites": [
            {"operator_id": "native:clip", "line_start": 2, "line_end": 2},
            {"operator_id": "native:fixgeometries", "line_start": 5, "line_end": 5},
            {"operator_id": "native:reprojectlayer", "line_start": 6, "line_end": 6},
        ],
    }

    rows, summary = build_split_units([parent])

    assert summary["parent_rows"] == 1
    assert summary["total_units"] == 2
    assert summary["multi_step_units"] == 1
    assert summary["multi_step_structure_eligible"] == 1
    assert summary["multi_step_structure_deferred"] == 0
    assert summary["single_step_units"] == 1
    multi = next(row for row in rows if row["split_class"] == "multi_step_local_dag")
    assert multi["mapped_l3_chain"] == ["L3_FIX", "L3_REPROJECT"]
    assert multi["local_structure_status"] == "eligible"
    assert multi["description_fidelity_passed"] is True
    assert multi["description_fidelity_status"] == "candidate"
    assert multi["parameter_facts"] == [
        {},
        {
            "TARGET_CRS": {
                "kind": "source_function_parameter",
                "name": "crs",
            }
        },
    ]
    assert not any(
        reason.startswith("parameter_resolution:1:")
        for reason in multi["known_omissions"]
    )
    assert all(row["training_row_emitted"] is False for row in rows)


def test_splits_fixed_dynamic_operator_ids_without_changing_source_identity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dynamic_split.py"
    source.write_text(
        '''def first(layer):
    algorithm = "native:clip"
    return processing.run(algorithm, {"INPUT": layer})

def second(layer):
    clean_id = "native:fixgeometries"
    fixed = processing.run(clean_id, {"INPUT": layer})["OUTPUT"]
    reproj_id = "native:reprojectlayer"
    return processing.run(reproj_id, {"INPUT": fixed})
''',
        encoding="utf-8",
    )
    parent = {
        "schema": "gis_recommend.qgis_recovered_processing_l3_gate.v1",
        "record_id": "dynamic-split-parent",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_root_id": "fixture",
        "signature_hash": "parent-signature",
        "rule_id": "split-disconnected-scopes-v1",
        "action": "split_subworkflow",
        "resolution_status": "fixed_chain_recovered",
        "mapped_l3_chain": ["L3_CLIP", "L3_FIX", "L3_REPROJECT"],
        "call_sites": [
            {"operator_id": "native:clip", "line_start": 3, "line_end": 3},
            {"operator_id": "native:fixgeometries", "line_start": 7, "line_end": 7},
            {
                "operator_id": "native:reprojectlayer",
                "line_start": 9,
                "line_end": 9,
            },
        ],
    }

    rows, summary = build_split_units([parent])

    assert summary["failed_parent_rows"] == 0
    assert summary["multi_step_structure_eligible"] == 1
    multi = next(row for row in rows if row["split_class"] == "multi_step_local_dag")
    assert multi["source_sha256"] == parent["source_sha256"]
    assert [site["line_start"] for site in multi["call_sites"]] == [7, 9]


def test_splits_after_verified_provider_normalization(tmp_path: Path) -> None:
    source = tmp_path / "legacy_provider_split.py"
    source.write_text(
        '''def first(layer):
    return processing.run("qgis:clip", {"INPUT": layer})

def second(layer):
    fixed = processing.run("qgis:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("qgis:reprojectlayer", {"INPUT": fixed})

def unrelated(layer):
    return processing.run("qgis:buffer", {"INPUT": layer})
''',
        encoding="utf-8",
    )
    parent = {
        "record_id": "legacy-provider-split-parent",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_root_id": "fixture",
        "signature_hash": "parent-signature",
        "rule_id": "split-disconnected-scopes-v1",
        "action": "split_subworkflow",
        "provider_migrations": [
            {
                "source": "qgis:clip",
                "target": "native:clip",
                "rule": "qgis_to_native_same_slug",
            },
            {
                "source": "qgis:fixgeometries",
                "target": "native:fixgeometries",
                "rule": "qgis_to_native_same_slug",
            },
            {
                "source": "qgis:reprojectlayer",
                "target": "native:reprojectlayer",
                "rule": "qgis_to_native_same_slug",
            },
        ],
        "mapped_l3_chain": ["L3_CLIP", "L3_FIX", "L3_REPROJECT"],
        "call_sites": [
            {"operator_id": "native:clip", "line_start": 2, "line_end": 2},
            {
                "operator_id": "native:fixgeometries",
                "line_start": 5,
                "line_end": 5,
            },
            {
                "operator_id": "native:reprojectlayer",
                "line_start": 6,
                "line_end": 6,
            },
        ],
    }

    rows, summary = build_split_units([parent])

    assert summary["failed_parent_rows"] == 0
    assert summary["multi_step_structure_eligible"] == 1
    multi = next(row for row in rows if row["split_class"] == "multi_step_local_dag")
    assert multi["operator_ids"] == [
        "native:fixgeometries",
        "native:reprojectlayer",
    ]
    assert multi["source_sha256"] == parent["source_sha256"]
