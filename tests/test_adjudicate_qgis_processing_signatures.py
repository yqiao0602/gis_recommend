import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from gis_recommend.data.qgis_task_description import (
    audit_task_description,
    build_task_description,
    extract_literal_parameter_facts,
)
from gis_recommend.data.qgis_subworkflow_splitter import (
    literalize_processing_operator_ids,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_processing_signatures.py"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_processing_signatures", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _review_row(tmp_path: Path, name: str, split: str) -> dict:
    source = (
        "import processing\n"
        f"# {name}\n"
        'processing.run("native:buffer", {"INPUT": layer, "OUTPUT": "memory:"})\n'
    )
    source_path = tmp_path / f"{name}.py"
    source_path.write_text(source, encoding="utf-8")
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    row = {
        "candidate_id": name,
        "record_id": f"record-{name}",
        "unit_id": f"unit-{name}",
        "candidate_lane": "direct",
        "policy_version": "policy-v1",
        "feature_extractor_version": "extractor-v1",
        "splitter_version": "",
        "recovery_rule_id": "",
        "parent_rule_id": "",
        "description_source": "frozen_operator_dag_only",
        "local_structure_status": "",
        "split_class": "",
        "parameter_evidence_status": "verified_source_ast",
        "workflow_unit_scope": "whole_processing_scope",
        "operator_ids": ["native:buffer"],
        "mapped_l3_chain": ["L3_02_01_01"],
        "dependency_edges": [],
        "parameter_facts": [{}],
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 3}
        ],
        "source_path": str(source_path),
        "source_sha256": source_sha,
        "source_authority_key": f"normalized_source_body_sha256:{name}",
        "normalized_source_body_sha256": name,
        "source_snippet": source,
        "dedup_status": "canonical_candidate",
        "review_split": split,
        "local_risk_evidence": {
            "provider_input_type_conflicts": [],
            "unresolved_output_references": [],
            "unused_temporary_terminal_indices": [],
        },
    }
    generated = build_task_description(row)
    row.update(generated)
    row.update(audit_task_description(row, generated))
    return row


def test_builds_hash_bound_authority_for_dual_split_supported_signature(
    tmp_path: Path,
) -> None:
    module = _module()
    calibration = _review_row(tmp_path, "calibration", "calibration")
    holdout = _review_row(tmp_path, "holdout", "holdout")
    signature = module._rule_signature_hash(calibration)
    calibration["review_rule_signature"] = signature
    holdout["review_rule_signature"] = signature
    population = [
        {**calibration, "candidate_id": f"population-{index}"}
        for index in range(30)
    ]

    adjudication = module.build_signature_adjudication(
        review_rows=[calibration, holdout],
        candidate_rows=population,
        approved_signatures={signature},
        minimum_population=30,
        package_hashes={
            "package_hash_ledger_sha256": "ledger",
            "candidate_batch_sha256": "candidate",
            "review_packet_sha256": "review",
        },
    )

    assert len(adjudication["decisions"]) == 2
    assert adjudication["rule_authority"]["approved_signatures"] == [signature]
    assert adjudication["rule_authority"]["status"] == (
        "granted_source_disjoint_zero_failure"
    )
    assert adjudication["signature_audit"][signature]["population_rows"] == 30
    assert adjudication["signature_audit"][signature]["review_splits"] == [
        "calibration",
        "holdout",
    ]


def test_rejects_approved_signature_below_population_gate(tmp_path: Path) -> None:
    module = _module()
    calibration = _review_row(tmp_path, "calibration", "calibration")
    holdout = _review_row(tmp_path, "holdout", "holdout")
    signature = module._rule_signature_hash(calibration)
    calibration["review_rule_signature"] = signature
    holdout["review_rule_signature"] = signature

    with pytest.raises(ValueError, match="population support"):
        module.build_signature_adjudication(
            review_rows=[calibration, holdout],
            candidate_rows=[
                {**calibration, "candidate_id": f"population-{index}"}
                for index in range(29)
            ],
            approved_signatures={signature},
            minimum_population=30,
            package_hashes={},
        )


def test_replays_parameter_facts_for_statically_resolved_dynamic_operator(
    tmp_path: Path,
) -> None:
    module = _module()
    source = (
        "import processing\n"
        "def run_buffer(layer, distance, segments, end_cap_style, join_style, dissolve):\n"
        '    algo_nm = "native:buffer"\n'
        '    params = {"INPUT": layer, "DISTANCE": distance, "SEGMENTS": segments, '
        '"END_CAP_STYLE": end_cap_style, "JOIN_STYLE": join_style, '
        '"DISSOLVE": dissolve, "OUTPUT": "memory:"}\n'
        "    return processing.run(algo_nm, params)\n"
    )
    source_path = tmp_path / "dynamic_buffer.py"
    source_path.write_text(source, encoding="utf-8")
    call_sites = [
        {
            "operator_id": "native:buffer",
            "line_start": 5,
            "line_end": 5,
            "original_expression": "algo_nm",
            "resolution_kind": "dynamic",
        }
    ]
    literalized = literalize_processing_operator_ids(source, call_sites=call_sites)
    facts = extract_literal_parameter_facts(literalized, call_sites=call_sites)
    row = {
        "candidate_id": "dynamic-buffer",
        "record_id": "record-dynamic-buffer",
        "unit_id": "unit-dynamic-buffer",
        "candidate_lane": "split_single_step",
        "description_source": "frozen_operator_dag_only",
        "parameter_evidence_status": "verified_source_ast",
        "workflow_unit_scope": "local_subworkflow",
        "operator_ids": ["native:buffer"],
        "mapped_l3_chain": ["L3_02_01_01"],
        "dependency_edges": [],
        "parameter_facts": [dict(fact) for fact in facts],
        "call_sites": call_sites,
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_authority_key": "normalized_source_body_sha256:dynamic-buffer",
        "normalized_source_body_sha256": "dynamic-buffer",
        "source_snippet": source,
        "dedup_status": "canonical_candidate",
        "local_risk_evidence": {
            "provider_input_type_conflicts": [],
            "unresolved_output_references": [],
            "unused_temporary_terminal_indices": [],
        },
    }
    generated = build_task_description(row)
    row.update(generated)
    row.update(audit_task_description(row, generated))

    module._audit_review_row(row)
