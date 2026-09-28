from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/export_qgis_stable110_split_salvage.py"
SPEC = importlib.util.spec_from_file_location("export_qgis_stable110_split_salvage", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_exports_only_source_replayed_stable110_salvage() -> None:
    candidate = {
        "proposal_id": "salvage-1",
        "parent_record_id": "parent-1",
        "parent_source_root_id": "fixture",
        "source_path": "/remote/source.py",
        "source_sha256": "a" * 64,
        "taxonomy_route": "stable110_existing",
        "dedup_decision": "canonical_proposal_keep",
        "description_fidelity_passed": True,
        "operator_ids": ["native:fixgeometries", "native:extractbyexpression"],
        "mapped_l3_chain": ["L3_01_05_02", "L3_02_06_02"],
        "call_sites": [
            {"operator_id": "native:fixgeometries", "line_start": 1, "line_end": 1},
            {"operator_id": "native:extractbyexpression", "line_start": 2, "line_end": 2},
        ],
        "dependency_edges": [[0, 1]],
        "workflow_unit_scope": "local_subworkflow",
        "task_name": "修复并筛选",
        "task_description": "修复输入几何并筛选有效要素。",
        "parameter_facts": [{}, {"EXPRESSION": "is_valid($geometry)"}],
        "known_omissions": ["outside_explicit_processing_dag_not_described"],
        "source_region_key": "region-1",
        "call_graph_key": "graph-1",
        "normalized_dag_key": "dag-1",
        "training_pair_key": "pair-1",
    }
    replay = {
        "record_id": "salvage-1",
        "source_path": "/remote/source.py",
        "source_sha256": "a" * 64,
        "source_authority_key": "source_sha256:" + "a" * 64,
        "source_authority_basis": "source_sha256",
        "source_verification": "verified_sha256",
        "call_span_verification": "verified_processing_calls",
        "operator_ids": candidate["operator_ids"],
        "mapped_l3_chain": candidate["mapped_l3_chain"],
        "call_sites": candidate["call_sites"],
        "source_snippet": "1 | processing.run(...)\n...\n2 | processing.run(...)\n",
    }
    extension = {
        "proposed_taxonomy": "stable110",
        "proposed_class_count": 2,
        "existing_code_to_id": {"L3_01_05_02": 0, "L3_02_06_02": 1},
        "proposed_code_to_id_additions": {},
        "existing_token_ids_unchanged": True,
    }
    mapping = {
        "native:fixgeometries": "L3_01_05_02",
        "native:extractbyexpression": "L3_02_06_02",
    }

    rows, summary = MODULE.build_stable110_salvage_training(
        [candidate], [replay], extension, mapping, []
    )

    assert len(rows) == 1
    assert rows[0]["schema_version"] == "qgis_stable110_split_salvage_training_sample_v1"
    assert rows[0]["training_admission"] == "granted_train_only_stable110_split_salvage"
    assert rows[0]["split"] == "train_only_stable110_split_salvage"
    assert rows[0]["taxonomy_profile"] == "stable110_authority_v1"
    assert rows[0]["l3_token_ids"] == [0, 1]
    assert rows[0]["source_verification"] == "verified_sha256"
    assert rows[0]["validation_eligible"] is False
    assert rows[0]["test_eligible"] is False
    assert summary["exported_rows"] == 1
    assert summary["training_run"] is False
