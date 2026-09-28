from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_qgis_top20_existing_l3_training.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_qgis_top20_existing_l3_training", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_exports_source_replayed_existing_l3_increment() -> None:
    codes = {f"L3_BASE_{index}": index for index in range(108)}
    codes["L3_STATS"] = codes.pop("L3_BASE_33")
    extension = {
        "proposed_taxonomy": "stable110",
        "proposed_class_count": 110,
        "existing_code_to_id": codes,
        "proposed_code_to_id_additions": {"L3_NEW_108": 108, "L3_NEW_109": 109},
        "existing_token_ids_unchanged": True,
    }
    ledger = [
        {
            "record_id": "record-1",
            "dedup_decision": "canonical_keep_candidate",
            "source_sha256": "sha-1",
            "operator_ids": ["native:rasterlayerstatistics"],
            "mapped_l3_chain": ["L3_STATS"],
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
        "operator_ids": ["native:rasterlayerstatistics"],
        "mapped_l3_chain": ["L3_STATS"],
        "description_fidelity_passed": True,
        "task_name": "计算栅格全局统计",
        "task_description": "计算指定栅格波段的全局统计量。",
        "workflow_unit_scope": "whole_processing_scope",
        "dependency_edges": [],
    }
    replay = {
        "record_id": "record-1",
        "source_path": "/home/yll/source.py",
        "source_sha256": "sha-1",
        "operator_ids": ["native:rasterlayerstatistics"],
        "mapped_l3_chain": ["L3_STATS"],
        "call_sites": [{"line_start": 10, "line_end": 12}],
        "source_snippet": "processing.run(...)\n",
        "source_authority_key": "authority-1",
        "source_authority_basis": "sha256",
        "source_verification": "verified_sha256",
        "call_span_verification": "verified_processing_calls",
    }
    authority = [
        {
            "operator_id": "native:rasterlayerstatistics",
            "candidate_l3_code": "L3_STATS",
            "mapping_admission": "granted",
        }
    ]

    result = MODULE.build_training_rows(
        ledger=ledger,
        candidates=[candidate],
        replay=[replay],
        extension=extension,
        authority=authority,
    )

    assert len(result.rows) == 1
    assert result.rows[0]["l3_token_ids"] == [33]
    assert result.rows[0]["taxonomy_profile"] == "stable110_authority_v1"
    assert result.rows[0]["training_admission"] == "granted_train_only_existing_l3_increment"
    assert result.summary["counts"]["exported_rows"] == 1
    assert result.summary["taxonomy"]["content_token_count"] == 110


def test_exports_description_recovery_only_for_frozen_mapping_authority() -> None:
    codes = {f"L3_BASE_{index}": index for index in range(110)}
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
            "operator_ids": ["native:hillshade"],
            "mapped_l3_chain": ["L3_BASE_31"],
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
        "operator_ids": ["native:hillshade"],
        "mapped_l3_chain": ["L3_BASE_31"],
        "mapping_authority": "stable110_plus_source_reviewed_existing_l3_v1",
        "description_fidelity_passed": True,
        "task_name": "生成阴影地形",
        "task_description": "根据高程和光照参数生成阴影地形栅格。",
        "workflow_unit_scope": "whole_processing_scope",
        "dependency_edges": [],
        "parameter_facts": [],
    }
    replay = {
        "record_id": "record-1",
        "source_path": "/home/yll/source.py",
        "source_sha256": "sha-1",
        "operator_ids": ["native:hillshade"],
        "mapped_l3_chain": ["L3_BASE_31"],
        "call_sites": [{"line_start": 10, "line_end": 12}],
        "source_snippet": "processing.run(...)\n",
        "source_authority_key": "authority-1",
        "source_authority_basis": "sha256",
        "source_verification": "verified_sha256",
        "call_span_verification": "verified_processing_calls",
    }

    result = MODULE.build_training_rows(
        ledger=ledger,
        candidates=[candidate],
        replay=[replay],
        extension=extension,
        authority=[],
        expected_mapping_authority="stable110_plus_source_reviewed_existing_l3_v1",
    )

    assert len(result.rows) == 1
    assert result.rows[0]["l3_token_ids"] == [31]
    assert result.rows[0]["entrypoint"] == "source_replayed_description_recovery"
    assert result.rows[0]["training_admission"] == "granted_train_only_description_recovery"
    assert result.summary["decision"]["row_admission"] == "granted_train_only_description_recovery"

    candidate["mapping_authority"] = "unreviewed_mapping"
    with pytest.raises(ValueError, match="mapping authority mismatch"):
        MODULE.build_training_rows(
            ledger=ledger,
            candidates=[candidate],
            replay=[replay],
            extension=extension,
            authority=[],
            expected_mapping_authority="stable110_plus_source_reviewed_existing_l3_v1",
        )
