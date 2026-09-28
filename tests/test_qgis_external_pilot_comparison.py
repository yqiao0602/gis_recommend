from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from gis_recommend.data.qgis_external_pilot_comparison import (
    compare_evidence,
    evaluate_hard_gate,
    evaluate_promotion_gate,
)

RUNNER = Path("scripts/run_qgis_external_analysis_pilot.py")


def _authority(verdict: str = "positive") -> dict:
    return {
        "record_id": "row-1",
        "source_sha256": "a" * 64,
        "authority_verdict": verdict,
        "dependency_edges": [[0, 1]],
        "terminal_evidence_count": 1 if verdict == "positive" else 0,
        "steps": [
            {"call_name": "geometry.buffer", "terminal_evidence": False},
            {"call_name": "sink.addFeature", "terminal_evidence": True},
        ],
        "provenance_complete": True,
    }


def _joern(status: str = "complete") -> dict:
    complete = status == "complete"
    return {
        "record_id": "row-1",
        "source_sha256": "a" * 64,
        "evidence_status": status,
        "operator_ids": [],
        "semantic_calls": ["buffer", "addFeature"] if status != "insufficient" else [],
        "dependency_edges": [[0, 1]] if status != "insufficient" else [],
        "terminal_node_ids": [9] if complete else [],
        "query_failures": [],
        "queries": [
            {
                "evidence_kinds": [
                    "cross_function_parameter",
                    "multi_hop_def_use",
                ]
            }
        ],
    }


@pytest.mark.parametrize(
    ("authority", "joern", "expected"),
    [
        (_authority("positive"), _joern("insufficient"), "existing_only"),
        (_authority("positive"), _joern("complete"), "shared_equivalent"),
        (_authority("unresolved"), _joern("partial"), "joern_only_partial"),
        (_authority("unresolved"), _joern("complete"), "joern_only_complete"),
        (
            _authority("positive"),
            {**_joern("complete"), "semantic_calls": ["centroid", "addFeature"]},
            "contradictory",
        ),
    ],
)
def test_all_evidence_delta_states(authority: dict, joern: dict, expected: str) -> None:
    assert compare_evidence(authority=authority, joern=joern).delta_status == expected


def test_missing_joern_path_is_coverage_miss_not_false_positive() -> None:
    result = compare_evidence(
        authority=_authority("positive"), joern=_joern("insufficient")
    )

    assert result.delta_status == "existing_only"
    assert result.coverage_miss is True
    assert result.false_complete_evidence is False


def test_complete_claim_missing_terminal_is_truncation() -> None:
    joern = _joern("complete")
    joern["terminal_node_ids"] = []

    result = compare_evidence(authority=_authority("positive"), joern=joern)

    assert result.delta_status == "contradictory"
    assert result.claimed_complete_truncation is True


def test_complete_claim_on_negative_is_false_complete() -> None:
    result = compare_evidence(
        authority=_authority("negative"), joern=_joern("complete")
    )

    assert result.delta_status == "joern_only_complete"
    assert result.false_complete_evidence is True


def test_source_mismatch_and_novelty_kinds_are_explicit() -> None:
    joern = _joern("partial")
    joern["source_sha256"] = "b" * 64
    joern["queries"][0]["evidence_kinds"].append("alias_propagation")

    result = compare_evidence(authority=_authority("unresolved"), joern=joern)

    assert result.source_hash_match is False
    assert result.novelty_kinds == (
        "alias_propagation",
        "cross_function_parameter",
        "multi_hop_def_use",
    )


def _passing_comparison():
    return compare_evidence(
        authority=_authority("positive"), joern=_joern("complete")
    )


def test_hard_gate_passes_only_when_every_contract_is_satisfied() -> None:
    result = evaluate_hard_gate(
        [_passing_comparison()],
        expected_source_count=1,
        registry_fallback_count=0,
        datatrove_report={"exact_reconciliation": {"matched": True}},
    )

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["metrics"]["coverage_miss_count"] == 0


@pytest.mark.parametrize(
    ("mutation", "failure"),
    [
        ("source_hash", "source_hash_incomplete_or_mismatch"),
        ("query_failure", "query_or_runtime_failure"),
        ("false_complete", "false_complete_evidence"),
        ("truncation", "claimed_complete_truncation"),
        ("registry", "registry_fallback"),
        ("exact", "exact_cluster_reconciliation"),
        ("provenance", "provenance_incomplete"),
    ],
)
def test_hard_gate_fails_closed_for_each_required_contract(
    mutation: str, failure: str
) -> None:
    comparison = _passing_comparison()
    registry_fallback_count = 0
    datatrove_report = {"exact_reconciliation": {"matched": True}}
    if mutation == "source_hash":
        comparison = comparison._replace(source_hash_match=False)
    elif mutation == "query_failure":
        comparison = comparison._replace(query_runtime_failure=True)
    elif mutation == "false_complete":
        comparison = comparison._replace(false_complete_evidence=True)
    elif mutation == "truncation":
        comparison = comparison._replace(claimed_complete_truncation=True)
    elif mutation == "registry":
        registry_fallback_count = 1
    elif mutation == "exact":
        datatrove_report = {"exact_reconciliation": {"matched": False}}
    elif mutation == "provenance":
        comparison = comparison._replace(provenance_complete=False)

    result = evaluate_hard_gate(
        [comparison],
        expected_source_count=1,
        registry_fallback_count=registry_fallback_count,
        datatrove_report=datatrove_report,
    )

    assert result["passed"] is False
    assert failure in result["failures"]


def test_promotion_requires_supported_source_disjoint_zero_fp_family() -> None:
    families = [
        {
            "family_id": "too-small",
            "previously_unresolved": True,
            "support": 29,
            "source_disjoint": True,
            "calibration_false_positives": 0,
            "holdout_false_positives": 0,
        },
        {
            "family_id": "eligible",
            "previously_unresolved": True,
            "support": 30,
            "source_disjoint": True,
            "calibration_false_positives": 0,
            "holdout_false_positives": 0,
        },
        {
            "family_id": "leaky",
            "previously_unresolved": True,
            "support": 80,
            "source_disjoint": False,
            "calibration_false_positives": 0,
            "holdout_false_positives": 0,
        },
    ]

    result = evaluate_promotion_gate(families)

    assert result["passed"] is True
    assert result["eligible_family_ids"] == ["eligible"]
    assert result["training_admission"] == "not_granted_external_analysis_pilot_only"


def test_comparison_driver_is_byte_stable_and_never_emits_training_rows(
    tmp_path: Path,
) -> None:
    namespace = runpy.run_path(str(RUNNER), run_name="qgis_comparison_import_test")
    run_comparison = namespace["run_comparison"]
    authority_path = tmp_path / "authority.jsonl"
    joern_path = tmp_path / "joern.jsonl"
    registry_path = tmp_path / "registry.json"
    datatrove_path = tmp_path / "datatrove.json"
    promotion_path = tmp_path / "promotion.json"
    authority_path.write_text(
        json.dumps(_authority("unresolved")) + "\n", encoding="utf-8"
    )
    joern_path.write_text(json.dumps(_joern()) + "\n", encoding="utf-8")
    registry_path.write_text(json.dumps({"fallback_count": 0}), encoding="utf-8")
    datatrove_path.write_text(
        json.dumps({"exact_reconciliation": {"matched": True}}), encoding="utf-8"
    )
    promotion_path.write_text(json.dumps({"families": []}), encoding="utf-8")
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_summary = run_comparison(
        authority_path=authority_path,
        joern_path=joern_path,
        registry_path=registry_path,
        datatrove_path=datatrove_path,
        promotion_path=promotion_path,
        output_dir=first,
        expected_source_count=1,
    )
    second_summary = run_comparison(
        authority_path=authority_path,
        joern_path=joern_path,
        registry_path=registry_path,
        datatrove_path=datatrove_path,
        promotion_path=promotion_path,
        output_dir=second,
        expected_source_count=1,
    )

    assert first_summary == second_summary
    assert first_summary["hard_gate"]["passed"] is True
    assert first_summary["promotion_gate"]["passed"] is False
    assert first_summary["checkpoint_novelty_passed"] is True
    assert first_summary["proceed_to_200_source_pilot"] is True
    assert first_summary["training_rows_emitted"] == 0
    assert (first / "comparison_rows_v1.jsonl").read_bytes() == (
        second / "comparison_rows_v1.jsonl"
    ).read_bytes()
    assert (first / "comparison_summary_v1.json").read_bytes() == (
        second / "comparison_summary_v1.json"
    ).read_bytes()
