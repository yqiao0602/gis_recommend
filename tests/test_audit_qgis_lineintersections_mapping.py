from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_qgis_lineintersections_mapping.py"
)


def _load_module():
    assert SCRIPT.exists(), "lineintersections mapping auditor is not implemented"
    spec = importlib.util.spec_from_file_location(
        "audit_qgis_lineintersections_mapping", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_quantifies_fail_closed_replay_impact() -> None:
    module = _load_module()
    stable101 = [
        {
            "qgis_ops": ["native:buffer", "native:lineintersections"],
            "proposed_l3_sequence": ["L3_BUFFER", "L3_SPLIT"],
            "record_sha256": "sha-a",
            "source": "workflow",
        },
        {
            "qgis_ops": ["native:buffer"],
            "proposed_l3_sequence": ["L3_BUFFER"],
            "record_sha256": "sha-b",
            "source": "workflow",
        },
    ]
    replay = [
        {
            "record_id": "record-a",
            "operator_ids": ["native:lineintersections"],
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "action": "defer_mapping",
            "structure_action": "auto_accept_candidate",
            "unmapped_operator_ids": ["native:lineintersections"],
            "source_sha256": "source-a",
            "source_root_id": "root-a",
            "normalized_source_body_sha256": "body-a",
        },
        {
            "record_id": "record-b",
            "operator_ids": ["native:lineintersections", "plugin:gap"],
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "action": "defer_mapping",
            "structure_action": "auto_accept_candidate",
            "unmapped_operator_ids": ["native:lineintersections", "plugin:gap"],
            "source_sha256": "source-b",
            "source_root_id": "root-a",
            "normalized_source_body_sha256": "body-b",
        },
    ]

    audit = module.audit_mapping(
        crosswalk_entry={
            "official_name": "Line intersections",
            "l3_code": "L3_02_05_06",
            "source": "auto_name_match",
            "frequency": 45,
        },
        taxonomy_entry={
            "code": "L3_02_05_06",
            "name": "Split Line at Point",
            "definition": "Split lines at point locations.",
        },
        stable101_rows=stable101,
        replay_rows=replay,
    )

    assert audit["decision"] == "exclude_mapping_and_defer_unmapped"
    assert audit["stable101_affected_rows"] == 1
    assert audit["stable110_rows_containing_operator"] == 2
    assert audit["counterfactual_bad_mapping_complete_rows_blocked"] == 1
    assert audit["counterfactual_bad_mapping_direct_rows_blocked"] == 1
    assert audit["stable110_unique_source_bodies"] == 2
    assert audit["new_l3_admission"] == "not_granted"
    assert audit["training_admission"] == "not_granted"


def test_read_taxonomy_normalizes_project_csv_columns(tmp_path: Path) -> None:
    module = _load_module()
    taxonomy = tmp_path / "taxonomy.csv"
    taxonomy.write_text(
        "l3_code,l3_name,l3_description,l2_code\n"
        "L3_02_05_06,Split Line at Point,Split lines at point locations.,L2_02_05\n",
        encoding="utf-8",
    )

    assert module._read_taxonomy(taxonomy) == [
        {
            "code": "L3_02_05_06",
            "name": "Split Line at Point",
            "definition": "Split lines at point locations.",
            "l2_code": "L2_02_05",
        }
    ]
