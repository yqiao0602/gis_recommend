from __future__ import annotations

from scripts.build_qgis_same_if_calibration import (
    build_condition_authorities,
    partition_source_disjoint,
    summarize_package,
)


def _row(
    body: str,
    source_sha: str,
    *,
    condition_key: str = "condition-a",
    expression: str = "enabled",
    unit_id: str = "unit-1",
) -> dict:
    return {
        "unit_id": unit_id,
        "split_class": "multi_step_local_dag",
        "boundary_rule_ids": ["candidate:same-if-branch-local-dag-v1"],
        "normalized_source_body_sha256": body,
        "source_sha256": source_sha,
        "source_path": f"/source/{source_sha}.py",
        "operator_ids": ["native:fixgeometries", "native:buffer"],
        "dependency_edges": [[0, 1]],
        "mapped_l3_chain": ["L3_FIX", "L3_BUFFER"],
        "local_structure_reasons": ["control_flow:if"],
        "local_risk_evidence": {
            "control_path_status": "same_if_branch",
            "control_path": [
                {
                    "if_line": 2,
                    "branch": "body",
                    "condition_expression": expression,
                    "normalized_condition_expression": expression,
                    "normalized_condition_key": condition_key,
                    "required_condition_value": True,
                    "condition_syntax_kind": "name",
                    "condition_semantic_status": "syntax_only_not_admitted",
                }
            ],
        },
    }


def test_build_condition_authorities_counts_normalized_bodies_not_copies() -> None:
    rows = [
        _row("body-a", "sha-1", unit_id="unit-a1"),
        _row("body-a", "sha-2", unit_id="unit-a2"),
        _row("body-b", "sha-3", unit_id="unit-b"),
    ]

    authorities = build_condition_authorities(rows, minimum_support=3)

    assert len(authorities) == 2
    assert authorities[0]["normalized_source_body_sha256"] == "body-a"
    assert authorities[0]["source_sha256s"] == ["sha-1", "sha-2"]
    assert authorities[0]["family_support_authorities"] == 2
    assert authorities[0]["condition_support_status"] == (
        "deferred_insufficient_authority_support"
    )
    assert authorities[0]["training_admission"] == (
        "not_granted_insufficient_condition_support"
    )


def test_support_gate_never_grants_training_admission() -> None:
    authorities = build_condition_authorities(
        [
            _row("body-a", "sha-1"),
            _row("body-b", "sha-2"),
        ],
        minimum_support=2,
    )

    assert {row["condition_support_status"] for row in authorities} == {
        "passed_pending_semantic_calibration"
    }
    assert {row["training_admission"] for row in authorities} == {
        "not_granted_pending_condition_semantic_calibration"
    }
    assert not any(row["training_row_emitted"] for row in authorities)


def test_partition_keeps_shared_source_sha_in_one_split() -> None:
    authorities = build_condition_authorities(
        [
            _row("body-a", "sha-shared", unit_id="unit-a"),
            _row("body-b", "sha-shared", unit_id="unit-b"),
            _row(
                "body-c",
                "sha-c",
                condition_key="condition-c",
                expression="other_flag",
                unit_id="unit-c",
            ),
            _row(
                "body-d",
                "sha-d",
                condition_key="condition-d",
                expression="third_flag",
                unit_id="unit-d",
            ),
        ],
        minimum_support=30,
    )

    calibration, holdout = partition_source_disjoint(authorities, seed=20260803)
    split_by_body = {
        row["normalized_source_body_sha256"]: row["review_split"]
        for row in [*calibration, *holdout]
    }

    assert split_by_body["body-a"] == split_by_body["body-b"]
    assert calibration
    assert holdout
    calibration_sources = {
        sha for row in calibration for sha in row["source_sha256s"]
    }
    holdout_sources = {sha for row in holdout for sha in row["source_sha256s"]}
    assert calibration_sources.isdisjoint(holdout_sources)


def test_summary_reports_zero_training_rows_and_disjointness() -> None:
    authorities = build_condition_authorities(
        [
            _row("body-a", "sha-a", unit_id="unit-a"),
            _row(
                "body-b",
                "sha-b",
                condition_key="condition-b",
                expression="other_flag",
                unit_id="unit-b",
            ),
        ],
        minimum_support=30,
    )
    calibration, holdout = partition_source_disjoint(authorities, seed=7)

    summary = summarize_package(
        input_rows=2,
        authorities=authorities,
        calibration=calibration,
        holdout=holdout,
        minimum_support=30,
        seed=7,
    )

    assert summary["normalized_body_authorities"] == 2
    assert summary["calibration_holdout_source_sha_overlap"] == 0
    assert summary["calibration_holdout_normalized_body_overlap"] == 0
    assert summary["support_pass_authorities"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["next_gate"] == "downstream_data_transform_family_census"
