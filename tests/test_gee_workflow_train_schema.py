from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _valid_payload() -> dict:
    from gis_recommend.data.gee_workflow_train_schema import SCHEMA

    return {
        "schema": SCHEMA,
        "sample_id": "gee_workflow_aaaaaaaaaaaaaaaa_output_workflow_1",
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "complete_output_workflow",
        "source_sha256": "a" * 64,
        "source_path": "data10000/script_1.txt",
        "workflow_id": "output-workflow-1",
        "exact_dag_fingerprint": "a" * 64,
        "task_name": "Create an image with an ordered GEE workflow",
        "task_description": "Filter the source imagery and export the result.",
        "operator_sequence": ["ee.imagecollection.filterdate", "ee.imagecollection.mean"],
        "l3_sequence": ["L3_TEST_00", "L3_TEST_01"],
        "fact_bundle_sha256": "b" * 64,
        "task_text_candidate_sha256": "c" * 64,
        "adjudication_row_sha256": "d" * 64,
        "adjudication_decision": "pass",
        "training_admission": "granted_train_only_gee_complete_workflow_v1",
        "split": "train_only_gee_complete_workflow_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "sample_weight": 0.5,
        "known_omissions": [],
    }


def test_complete_workflow_dataclass_serializes_valid_row() -> None:
    from gis_recommend.data.gee_workflow_train_schema import (
        GeeWorkflowTrainRow,
        SCHEMA,
        validate_workflow_train_row,
    )

    payload = _valid_payload()
    row = GeeWorkflowTrainRow(
        sample_id=payload["sample_id"],
        source_sha256=payload["source_sha256"],
        source_path=payload["source_path"],
        workflow_id=payload["workflow_id"],
        exact_dag_fingerprint=payload["exact_dag_fingerprint"],
        task_name=payload["task_name"],
        task_description=payload["task_description"],
        operator_sequence=tuple(payload["operator_sequence"]),
        l3_sequence=tuple(payload["l3_sequence"]),
        fact_bundle_sha256=payload["fact_bundle_sha256"],
        task_text_candidate_sha256=payload["task_text_candidate_sha256"],
        adjudication_row_sha256=payload["adjudication_row_sha256"],
    )

    serialized = row.to_dict()

    assert serialized["schema"] == SCHEMA
    assert serialized["training_scope"] == "complete_output_workflow"
    assert serialized["operator_sequence"] == payload["operator_sequence"]
    validate_workflow_train_row(serialized)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("training_scope", "core_subworkflow", "training_scope"),
        ("source_sha256", "bad", "source_sha256"),
        ("exact_dag_fingerprint", "", "exact_dag_fingerprint"),
        ("fact_bundle_sha256", "bad", "fact_bundle_sha256"),
        ("adjudication_decision", "defer_source_ambiguity", "adjudication_decision"),
        ("validation_eligible", True, "validation_eligible"),
        ("test_eligible", True, "test_eligible"),
        ("sample_weight", 0.75, "sample_weight"),
    ],
)
def test_validator_fails_closed_on_invalid_authority_or_admission(
    field: str, value: object, message: str
) -> None:
    from gis_recommend.data.gee_workflow_train_schema import validate_workflow_train_row

    payload = _valid_payload()
    payload[field] = value

    with pytest.raises(ValueError, match=message):
        validate_workflow_train_row(payload)


def test_validator_rejects_chain_mismatch_and_non_l3_codes() -> None:
    from gis_recommend.data.gee_workflow_train_schema import validate_workflow_train_row

    payload = _valid_payload()
    payload["l3_sequence"] = ["L3_TEST_00"]
    with pytest.raises(ValueError, match="same length"):
        validate_workflow_train_row(payload)

    payload = _valid_payload()
    payload["l3_sequence"][0] = "<START>"
    with pytest.raises(ValueError, match="content L3 codes"):
        validate_workflow_train_row(payload)


@pytest.mark.parametrize("fingerprint", ["a" * 63, "A" * 64, "dag-v1:" + "a" * 57])
def test_validator_requires_strict_dag_fingerprint(fingerprint: str) -> None:
    from gis_recommend.data.gee_workflow_train_schema import validate_workflow_train_row

    payload = _valid_payload()
    payload["exact_dag_fingerprint"] = fingerprint
    with pytest.raises(ValueError, match="exact_dag_fingerprint"):
        validate_workflow_train_row(payload)


def test_stable_94_mapping_is_exact_and_type_safe() -> None:
    from gis_recommend.data.gee_workflow_train_schema import validate_stable_94_mapping

    mapping = {f"L3_TEST_{index:02d}": index for index in range(94)}
    validate_stable_94_mapping(mapping)

    duplicate = dict(mapping)
    duplicate["L3_TEST_01"] = 0
    with pytest.raises(ValueError, match="unique"):
        validate_stable_94_mapping(duplicate)

    boolean_value = dict(mapping)
    boolean_value["L3_TEST_01"] = True
    with pytest.raises(ValueError, match="non-bool int"):
        validate_stable_94_mapping(boolean_value)

    wrong_key = dict(mapping)
    wrong_key["operator"] = wrong_key.pop("L3_TEST_01")
    with pytest.raises(ValueError, match="L3"):
        validate_stable_94_mapping(wrong_key)
