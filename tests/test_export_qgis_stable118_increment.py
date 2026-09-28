from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_qgis_stable118_increment.py"
)


def _load_module():
    assert SCRIPT.exists(), "stable118 increment exporter is not implemented"
    spec = importlib.util.spec_from_file_location(
        "export_qgis_stable118_increment", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builds_source_replayed_train_only_increment(tmp_path: Path) -> None:
    module = _load_module()
    source = tmp_path / "current" / "workflow.py"
    source.parent.mkdir()
    source.write_text(
        'import processing\nprocessing.run("native:pointstopath", {"INPUT": "points.gpkg", "OUTPUT": "memory:"})\n',
        encoding="utf-8",
    )
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    replay_rows = [
        {
            "record_id": "new-row",
            "action": "auto_accept_candidate",
            "mapping_complete": True,
            "mapping_authority": "stable118_authority_v1",
            "operator_ids": ["native:pointstopath"],
            "mapped_l3_chain": ["L3_02_07_04"],
            "call_sites": [
                {
                    "operator_id": "native:pointstopath",
                    "line_start": 2,
                    "line_end": 2,
                }
            ],
            "dependency_edges": [],
            "workflow_unit_scope": "whole_processing_scope",
            "source_root_id": "fixture",
            "source_path": str(tmp_path / "legacy" / "workflow.py"),
            "source_sha256": source_sha,
            "source_snippet": source.read_text(encoding="utf-8"),
            "source_snippet_contains_all_ops": True,
        }
    ]
    authority = [
        {
            "operator_id": "native:pointstopath",
            "l3_code": "L3_02_07_04",
            "mapping_admission": "granted",
        }
    ]
    extension = {
        "proposed_taxonomy": "stable118",
        "proposed_class_count": 118,
        "existing_token_ids_unchanged": True,
        "existing_code_to_id": {f"L3_BASE_{index}": index for index in range(110)},
        "proposed_code_to_id_additions": {
            **{f"L3_NEW_{token}": token for token in range(110, 115)},
            "L3_02_07_04": 115,
            "L3_NEW_116": 116,
            "L3_NEW_117": 117,
        },
    }

    result = module.build_increment_package(
        replay_rows=replay_rows,
        authority_rows=authority,
        extension=extension,
        existing_train_rows=[],
        source_prefix_aliases=[
            (str(tmp_path / "legacy"), str(tmp_path / "current"))
        ],
    )

    assert result.summary["selected_direct_rows"] == 1
    assert result.summary["description_fidelity_passed_rows"] == 1
    assert result.summary["canonical_rows"] == 1
    assert result.summary["exported_training_rows"] == 1
    assert result.source_replay[0]["source_verification"] == "verified_sha256"
    assert result.source_replay[0]["source_path"] == str(source)
    assert result.training_rows[0]["l3_token_ids"] == [115]
    assert result.training_rows[0]["taxonomy_profile"] == "stable118_authority_v1"
    assert result.training_rows[0]["mapping_authority"] == "stable118_authority_v1"
    assert result.training_rows[0]["validation_eligible"] is False
    assert result.training_rows[0]["test_eligible"] is False


def test_records_explicit_stable_n_profile(tmp_path: Path) -> None:
    module = _load_module()
    source = tmp_path / "workflow.py"
    source.write_text(
        'import processing\nprocessing.run("native:pointstopath", {"INPUT": "points.gpkg", "OUTPUT": "memory:"})\n',
        encoding="utf-8",
    )
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    replay_rows = [
        {
            "record_id": "stable120-row",
            "action": "auto_accept_candidate",
            "mapping_complete": True,
            "mapping_authority": "stable120_authority_v1",
            "operator_ids": ["native:pointstopath"],
            "mapped_l3_chain": ["L3_02_07_04"],
            "call_sites": [
                {
                    "operator_id": "native:pointstopath",
                    "line_start": 2,
                    "line_end": 2,
                }
            ],
            "dependency_edges": [],
            "workflow_unit_scope": "whole_processing_scope",
            "source_root_id": "fixture",
            "source_path": str(source),
            "source_sha256": source_sha,
            "source_snippet": source.read_text(encoding="utf-8"),
            "source_snippet_contains_all_ops": True,
        }
    ]
    authority = [
        {
            "operator_id": "native:pointstopath",
            "l3_code": "L3_02_07_04",
            "mapping_admission": "granted",
        }
    ]
    extension = {
        "proposed_taxonomy": "stable120",
        "proposed_class_count": 120,
        "existing_token_ids_unchanged": True,
        "existing_code_to_id": {
            **{f"L3_BASE_{index}": index for index in range(118) if index != 115},
            "L3_02_07_04": 115,
        },
        "proposed_code_to_id_additions": {
            "L3_01_07_01": 118,
            "L3_02_07_09": 119,
        },
    }

    result = module.build_increment_package(
        replay_rows=replay_rows,
        authority_rows=authority,
        extension=extension,
        existing_train_rows=[],
        profile_name="stable120",
    )

    assert result.summary["schema"] == "gis_recommend.qgis_stable120_increment_summary.v1"
    assert result.training_rows[0]["schema_version"] == "qgis_stable120_increment_v1"
    assert result.training_rows[0]["taxonomy_profile"] == "stable120_authority_v1"
    assert result.training_rows[0]["mapping_authority"] == "stable120_authority_v1"
    assert result.training_rows[0]["source_replay_authority"] == "stable120_source_replay_v1"
