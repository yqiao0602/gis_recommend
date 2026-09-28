from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_qgis_mapping_correction_training.py"
SPEC = importlib.util.spec_from_file_location("export_qgis_mapping_correction_training", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_exports_only_correction_authority_rows() -> None:
    codes = {f"L3_BASE_{index}": index for index in range(110)}
    codes["L3_INTERSECT"] = codes.pop("L3_BASE_9")
    extension = {
        "proposed_taxonomy": "stable110",
        "proposed_class_count": 110,
        "existing_code_to_id": codes,
        "proposed_code_to_id_additions": {},
        "existing_token_ids_unchanged": True,
    }
    ledger = [
        {
            "record_id": "record-1",
            "dedup_decision": "canonical_keep_candidate",
            "source_sha256": "sha-1",
            "operator_ids": ["native:lineintersections"],
            "mapped_l3_chain": ["L3_INTERSECT"],
            "source_region_key": "region-1",
            "call_graph_key": "graph-1",
            "normalized_dag_key": "dag-1",
            "training_pair_key": "pair-1",
        }
    ]
    candidate = {
        "record_id": "record-1",
        "source_root_id": "root",
        "source_sha256": "sha-1",
        "operator_ids": ["native:lineintersections"],
        "mapped_l3_chain": ["L3_INTERSECT"],
        "description_fidelity_passed": True,
        "task_name": "计算线交点",
        "task_description": "计算两个线图层的交点。",
        "workflow_unit_scope": "whole_processing_scope",
        "dependency_edges": [],
    }
    replay = {
        "record_id": "record-1",
        "source_path": "/home/yll/source.py",
        "source_sha256": "sha-1",
        "operator_ids": ["native:lineintersections"],
        "mapped_l3_chain": ["L3_INTERSECT"],
        "call_sites": [{"line_start": 10, "line_end": 12, "operator_id": "native:lineintersections"}],
        "source_snippet": "10 | processing.run('native:lineintersections', {})\n",
        "source_authority_key": "authority-1",
        "source_authority_basis": "sha256",
        "source_verification": "verified_sha256",
        "call_span_verification": "verified_processing_calls",
    }
    authority = {
        "schema": "gis_recommend.qgis_mapping_correction_authority.v1",
        "status": "granted_source_reviewed_existing_l3_correction",
        "correction_mappings": {
            "native:lineintersections": {"from_l3": None, "to_l3": "L3_INTERSECT"}
        },
    }

    result = MODULE.build_training_rows(
        ledger=ledger,
        candidates=[candidate],
        replay=[replay],
        extension=extension,
        correction_authority=authority,
        existing_train=[],
    )

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["l3_token_ids"] == [9]
    assert row["taxonomy_profile"] == "stable110_authority_v1"
    assert row["training_admission"] == "granted_train_only_mapping_correction"
    assert row["validation_eligible"] is False
    assert result.summary["counts"]["exported_rows"] == 1


def test_accepts_verified_normalized_source_body_carry_forward() -> None:
    module = MODULE
    codes = {f"L3_BASE_{index}": index for index in range(110)}
    extension = {
        "proposed_taxonomy": "stable110",
        "proposed_class_count": 110,
        "existing_code_to_id": codes,
        "proposed_code_to_id_additions": {},
        "existing_token_ids_unchanged": True,
    }
    ledger = [{
        "record_id": "record-1", "dedup_decision": "canonical_keep_candidate",
        "source_sha256": "sha-1", "operator_ids": ["native:lineintersections"],
        "mapped_l3_chain": ["L3_BASE_9"], "source_region_key": "region-1",
        "call_graph_key": "graph-1", "normalized_dag_key": "dag-1",
        "training_pair_key": "pair-1",
    }]
    candidate = {
        **ledger[0], "description_fidelity_passed": True,
        "source_root_id": "root", "task_name": "计算线交点",
        "task_description": "计算两个线图层的交点。",
        "workflow_unit_scope": "whole_processing_scope", "dependency_edges": [],
    }
    replay = [{
        "record_id": "record-1", "source_path": "/home/yll/source.py",
        "source_sha256": "sha-1", "operator_ids": ["native:lineintersections"],
        "mapped_l3_chain": ["L3_BASE_9"],
        "call_sites": [{"line_start": 10, "line_end": 12, "operator_id": "native:lineintersections"}],
        "source_snippet": "10 | processing.run('native:lineintersections', {})\n",
        "source_authority_key": "normalized_source_body_sha256:body-1",
        "source_authority_basis": "carried_forward_verified_normalized_source_body_authority",
        "source_verification": "carried_forward_verified_normalized_source_body",
        "call_span_verification": "carried_forward_cached_processing_calls",
    }]
    authority = {
        "status": "granted_source_reviewed_existing_l3_correction",
        "correction_mappings": {
            "native:lineintersections": {"from_l3": None, "to_l3": "L3_BASE_9"}
        },
    }

    result = module.build_training_rows(
        ledger=ledger, candidates=[candidate], replay=replay,
        extension=extension, correction_authority=authority, existing_train=[]
    )

    assert result.rows[0]["source_verification"] == (
        "carried_forward_verified_normalized_source_body"
    )
