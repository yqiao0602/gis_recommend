import hashlib
import json
from pathlib import Path

import pytest

from gis_recommend.data.gee_operator_canonicalization import MappingEntry
from gis_recommend.data.gee_source_evidence import CallEvidence, GeeSourceEvidence
from gis_recommend.data.gee_typed_canonicalization import (
    TypedL3Override,
    canonicalize_workflow_calls,
    load_typed_l3_overrides,
)
from scripts.build_gee_typed_l3_mapping_census import build_typed_l3_mapping_census


SOURCE_SHA = "a" * 64


def _candidate(operator: str) -> dict:
    return {
        "source_sha256": SOURCE_SHA,
        "source_path": "data10000/script_1.txt",
        "workflow_id": "output-workflow-1",
        "calibration_stratum": "linear_export",
        "extractor_version": "gee-source-extractor-v2.3.2",
        "fidelity_status": "passed",
        "fail_closed_reasons": [],
        "normalized_core_call_ordinals": [1],
        "normalized_core_chain": [operator],
        "training_admission": "not_granted_taxonomy_and_task_text_pending",
        "training_rows_emitted": 0,
    }


def _evidence(operator: str, *, receiver_type: str = "ee.image") -> GeeSourceEvidence:
    call = CallEvidence(
        ordinal=1,
        raw_callee=operator,
        classification="core",
        resolution="receiver_ee_binding",
        scope="top_level",
        context="direct",
        receiver_type=receiver_type,
        source_location={"start_line": 2, "end_line": 2},
    )
    return GeeSourceEvidence(
        source_path="data10000/script_1.txt",
        source_sha256=SOURCE_SHA,
        extractor_version="gee-source-extractor-v2.3.2",
        ordered_calls=[call],
        core_operator_chain=[1],
    )


def _override(
    operator: str,
    l3_code: str,
    *,
    min_arguments: int,
    max_arguments: int,
    mismatch_policy: str = "fail_closed",
) -> TypedL3Override:
    return TypedL3Override(
        canonical_operator=operator,
        receiver_type="ee.image",
        primary_l3=l3_code,
        mapping_confidence=1.0,
        min_arguments=min_arguments,
        max_arguments=max_arguments,
        signature_mismatch_policy=mismatch_policy,
        rationale="source-reviewed v8.5 test authority",
    )


@pytest.mark.parametrize(
    ("operator", "base_l3", "target_l3", "argument_count", "max_arguments"),
    [
        ("ee.image.mask", "L3_03_01_05", "L3_03_01_07", 0, 0),
        ("ee.image.reduce", "L3_03_02_05", "L3_03_02_02", 1, 1),
        ("ee.image.resample", "L3_03_05_02", "L3_03_05_01", 1, 1),
        ("ee.image.unmask", "L3_03_01_05", "L3_03_01_08", 1, 2),
        ("ee.image.max", "L3_03_01_04", "L3_03_02_02", 1, 1),
    ],
)
def test_v85_exact_signature_overrides_replace_only_l3(
    operator: str,
    base_l3: str,
    target_l3: str,
    argument_count: int,
    max_arguments: int,
) -> None:
    mapping = {operator: MappingEntry(operator, base_l3, 0.75, False)}
    overrides = {
        operator: _override(
            operator,
            target_l3,
            min_arguments=0 if operator == "ee.image.unmask" else argument_count,
            max_arguments=max_arguments,
            mismatch_policy="retain_base" if operator == "ee.image.mask" else "fail_closed",
        )
    }

    decision = canonicalize_workflow_calls(
        _candidate(operator),
        _evidence(operator),
        mapping,
        frozenset({operator}),
        l3_overrides=overrides,
        call_argument_counts={1: argument_count},
    )

    assert decision.mapping_status == "mapping_complete"
    assert decision.canonical_operator_sequence == (operator,)
    assert decision.l3_sequence == (target_l3,)
    assert decision.mapping_confidences == (1.0,)


def test_mask_setter_signature_retains_base_update_mask_mapping() -> None:
    operator = "ee.image.mask"
    decision = canonicalize_workflow_calls(
        _candidate(operator),
        _evidence(operator),
        {operator: MappingEntry(operator, "L3_03_01_05", 0.95, False)},
        frozenset({operator}),
        l3_overrides={
            operator: _override(
                operator,
                "L3_03_01_07",
                min_arguments=0,
                max_arguments=0,
                mismatch_policy="retain_base",
            )
        },
        call_argument_counts={1: 1},
    )

    assert decision.mapping_status == "mapping_complete"
    assert decision.l3_sequence == ("L3_03_01_05",)


def test_mask_without_argument_evidence_fails_closed() -> None:
    operator = "ee.image.mask"
    decision = canonicalize_workflow_calls(
        _candidate(operator),
        _evidence(operator),
        {operator: MappingEntry(operator, "L3_03_01_05", 0.95, False)},
        frozenset({operator}),
        l3_overrides={
            operator: _override(
                operator,
                "L3_03_01_07",
                min_arguments=0,
                max_arguments=0,
                mismatch_policy="retain_base",
            )
        },
        call_argument_counts={},
    )

    assert decision.mapping_status == "l3_override_signature_mismatch"
    assert decision.l3_sequence == ()
    assert decision.fail_closed_reasons == (
        "l3_override_signature_mismatch:ee.image.mask:arguments=unknown",
    )


def test_mask_receiver_mismatch_fails_closed_instead_of_retaining_base() -> None:
    operator = "ee.image.mask"
    decision = canonicalize_workflow_calls(
        _candidate(operator),
        _evidence(operator, receiver_type="ee.feature"),
        {operator: MappingEntry(operator, "L3_03_01_05", 0.95, False)},
        frozenset({operator}),
        l3_overrides={
            operator: _override(
                operator,
                "L3_03_01_07",
                min_arguments=0,
                max_arguments=0,
                mismatch_policy="retain_base",
            )
        },
        call_argument_counts={1: 0},
    )

    assert decision.mapping_status == "l3_override_signature_mismatch"
    assert decision.l3_sequence == ()
    assert decision.fail_closed_reasons == (
        "l3_override_signature_mismatch:ee.image.mask:arguments=unknown",
    )


def test_non_mask_override_signature_mismatch_fails_closed() -> None:
    operator = "ee.image.max"
    decision = canonicalize_workflow_calls(
        _candidate(operator),
        _evidence(operator),
        {operator: MappingEntry(operator, "L3_03_01_04", 0.875, False)},
        frozenset({operator}),
        l3_overrides={
            operator: _override(
                operator,
                "L3_03_02_02",
                min_arguments=1,
                max_arguments=1,
            )
        },
        call_argument_counts={1: 0},
    )

    assert decision.mapping_status == "l3_override_signature_mismatch"
    assert decision.l3_sequence == ()
    assert decision.fail_closed_reasons == (
        "l3_override_signature_mismatch:ee.image.max:arguments=0",
    )


def test_override_authority_is_bound_to_base_mapping_and_existing_tokens(tmp_path: Path) -> None:
    base = tmp_path / "id_mappings.json"
    base.write_text(
        json.dumps(
            {
                "gee_op": {"ee.image.mask": 1},
                "l3": {"L3_03_01_05": 1, "L3_03_01_07": 2},
                "mapping_metadata": {
                    "gee_to_l3": {
                        "ee.image.mask": {
                            "primary_l3": "L3_03_01_05",
                            "mapping_confidence": 0.95,
                            "has_ambiguity": False,
                        }
                    }
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    base_sha = hashlib.sha256(base.read_bytes()).hexdigest()
    authority = tmp_path / "overrides.json"
    authority.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.gee_typed_l3_override_authority.v1",
                "version": "v8.5",
                "base_mapping_sha256": base_sha,
                "overrides": [
                    {
                        "canonical_operator": "ee.image.mask",
                        "receiver_type": "ee.image",
                        "primary_l3": "L3_03_01_07",
                        "mapping_confidence": 1.0,
                        "min_arguments": 0,
                        "max_arguments": 0,
                        "signature_mismatch_policy": "retain_base",
                        "rationale": "mask() is the zero-argument mask getter",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    loaded = load_typed_l3_overrides(authority, base)

    assert loaded.version == "v8.5"
    assert loaded.overrides["ee.image.mask"].primary_l3 == "L3_03_01_07"

    payload = json.loads(authority.read_text(encoding="utf-8"))
    payload["base_mapping_sha256"] = "0" * 64
    authority.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="base_mapping_sha256"):
        load_typed_l3_overrides(authority, base)


def test_builder_reconnects_ast_arity_and_hash_binds_override_authority(tmp_path: Path) -> None:
    def loc(start_column: int, end_column: int) -> dict:
        return {
            "start": {"line": 1, "column": start_column},
            "end": {"line": 1, "column": end_column},
        }

    image_call = {
        "type": "CallExpression",
        "callee": {
            "type": "MemberExpression",
            "computed": False,
            "object": {"type": "Identifier", "name": "ee"},
            "property": {"type": "Identifier", "name": "Image"},
        },
        "arguments": [{"type": "Literal", "value": 1}],
        "loc": loc(0, 11),
    }
    mask_call = {
        "type": "CallExpression",
        "callee": {
            "type": "MemberExpression",
            "computed": False,
            "object": image_call,
            "property": {"type": "Identifier", "name": "mask"},
        },
        "arguments": [],
        "loc": loc(0, 18),
    }
    ast = {
        "type": "Program",
        "body": [{"type": "ExpressionStatement", "expression": mask_call}],
    }
    ast_dir = tmp_path / "ast"
    ast_dir.mkdir()
    (ast_dir / f"{SOURCE_SHA}.json").write_text(json.dumps(ast), encoding="utf-8")

    accepted = tmp_path / "accepted.jsonl"
    accepted.write_text(
        json.dumps(_candidate("ee.Image.mask"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    base = tmp_path / "id_mappings.json"
    base.write_text(
        json.dumps(
            {
                "gee_op": {"ee.image.mask": 1},
                "l3": {"L3_03_01_05": 1, "L3_03_01_07": 2},
                "mapping_metadata": {
                    "gee_to_l3": {
                        "ee.image.mask": {
                            "primary_l3": "L3_03_01_05",
                            "mapping_confidence": 0.95,
                            "has_ambiguity": False,
                        }
                    }
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    authority = tmp_path / "overrides.json"
    authority.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.gee_typed_l3_override_authority.v1",
                "version": "v8.5",
                "base_mapping_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
                "overrides": [
                    {
                        "canonical_operator": "ee.image.mask",
                        "receiver_type": "ee.image",
                        "primary_l3": "L3_03_01_07",
                        "mapping_confidence": 1.0,
                        "min_arguments": 0,
                        "max_arguments": 0,
                        "signature_mismatch_policy": "retain_base",
                        "rationale": "mask() is the zero-argument mask getter",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    skip = tmp_path / "skip.json"
    skip.write_text(
        json.dumps({"skip_operators": ["ee.image.get"]}),
        encoding="utf-8",
    )
    output = tmp_path / "out"

    summary = build_typed_l3_mapping_census(
        accepted_candidates_path=accepted,
        ast_dir=ast_dir,
        id_mappings_path=base,
        skip_list_path=skip,
        output_dir=output,
        l3_overrides_path=authority,
    )

    assert summary["mapping_complete_count"] == 1
    assert summary["l3_override_version"] == "v8.5"
    assert summary["l3_override_count"] == 1
    row = json.loads((output / "mapping_complete_candidates.jsonl").read_text())
    assert row["canonical_operator_sequence"] == ["ee.image.mask"]
    assert row["l3_sequence"] == ["L3_03_01_07"]
    ledger = json.loads((output / "hash_ledger.json").read_text())
    assert ledger["inputs"]["l3_overrides"]["sha256"] == hashlib.sha256(
        authority.read_bytes()
    ).hexdigest()
