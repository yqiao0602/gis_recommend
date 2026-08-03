from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pytest

from scripts.build_qgis_external_pilot_manifest import _review_index
from gis_recommend.data.qgis_external_pilot_manifest import (
    build_api_baseline,
    build_regression_baseline,
    build_target_manifest,
    select_processing,
    write_pilot_artifacts,
)


def _row(index: int, stratum: str, *, corpus_kind: str = "processing") -> dict:
    body = f"{index:064x}"
    source = f"{index + 10_000:064x}"
    return {
        "record_id": f"record-{index:04d}",
        "candidate_id": f"candidate-{index:04d}",
        "source_path": f"/home/yll/source-{index:04d}.py",
        "source_sha256": source,
        "normalized_source_body_sha256": body,
        "source_authority_key": f"normalized_source_body_sha256:{body}",
        "primary_stratum": stratum,
        "corpus_kind": corpus_kind,
    }


def test_processing_priority_is_mainline_order() -> None:
    rows = [
        _row(4, "cross_function_helper"),
        _row(3, "missing_data_edges"),
        _row(2, "control_flow:for"),
        _row(1, "conditional_early_exit"),
    ]

    selected = select_processing(rows, limit=4, excluded_bodies=set())

    assert [row["primary_stratum"] for row in selected] == [
        "conditional_early_exit",
        "control_flow:for",
        "missing_data_edges",
        "cross_function_helper",
    ]


def test_selection_is_body_unique_and_excludes_holdout() -> None:
    duplicate = _row(9, "output_alias")
    duplicate["record_id"] = "record-duplicate"
    duplicate["source_sha256"] = "f" * 64
    excluded = _row(10, "result_dictionary")

    selected = select_processing(
        [_row(9, "output_alias"), duplicate, excluded],
        limit=1,
        excluded_bodies={excluded["normalized_source_body_sha256"]},
    )

    assert [row["record_id"] for row in selected] == ["record-0009"]


def test_selection_has_stable_tie_breaking() -> None:
    rows = [_row(index, "fill") for index in range(8)]
    expected = [row["record_id"] for row in select_processing(rows, limit=8)]

    random.Random(20260803).shuffle(rows)

    assert [row["record_id"] for row in select_processing(rows, limit=8)] == expected


def test_processing_mainline_strata_are_balanced_before_fill() -> None:
    rows = [_row(index, "control_flow:for") for index in range(200)]
    rows.extend(_row(index + 1_000, "missing_data_edges") for index in range(30))

    selected = select_processing(rows, limit=100)

    counts = Counter(row["primary_stratum"] for row in selected)
    assert counts == {"control_flow:for": 70, "missing_data_edges": 30}


def test_target_manifest_requires_exactly_100_plus_100() -> None:
    processing = [_row(index, "fill") for index in range(120)]
    api = [
        _row(index + 1_000, "cross_function_geometry", corpus_kind="api")
        for index in range(120)
    ]

    manifest = build_target_manifest(processing, api)

    assert len(manifest) == 200
    assert sum(row["corpus_kind"] == "processing" for row in manifest) == 100
    assert sum(row["corpus_kind"] == "api" for row in manifest) == 100
    assert len({row["normalized_source_body_sha256"] for row in manifest}) == 200


def test_target_manifest_fails_when_a_quota_cannot_be_filled() -> None:
    processing = [_row(index, "fill") for index in range(99)]
    api = [
        _row(index + 1_000, "terminal_sink", corpus_kind="api")
        for index in range(100)
    ]

    with pytest.raises(ValueError, match="100 Processing"):
        build_target_manifest(processing, api)


def test_target_manifest_does_not_embed_source_content() -> None:
    processing = [_row(index, "fill") for index in range(100)]
    processing[0]["source_snippet"] = "processing.run('native:buffer', {})"
    processing[0]["source_windows"] = [{"text": "source body"}]
    processing[0]["steps"] = [{"call_name": "processing.run"}]
    api = [
        _row(index + 1_000, "terminal_sink", corpus_kind="api")
        for index in range(100)
    ]

    manifest = build_target_manifest(processing, api)

    assert "source_snippet" not in manifest[0]
    assert "source_windows" not in manifest[0]
    assert "steps" not in manifest[0]


@pytest.mark.parametrize(
    "row",
    [
        {"review_status": "pending_human_review"},
        {"true_positive": 99, "false_positive": 1},
    ],
)
def test_pending_or_aggregate_api_reviews_cannot_become_baseline(row: dict) -> None:
    with pytest.raises(ValueError, match="persisted verdict"):
        build_api_baseline([row])


def test_api_baseline_accepts_only_hash_bound_item_verdicts() -> None:
    row = _row(1, "reviewed", corpus_kind="api")
    row.update(
        {
            "proposal_decision": "true_positive",
            "unit_id": "unit-1",
        }
    )

    baseline = build_api_baseline([row])

    assert baseline[0]["authority_verdict"] == "positive"
    assert baseline[0]["baseline_role"] == "api_reviewed_boundary"


def test_artifacts_are_atomic_and_byte_stable(tmp_path: Path) -> None:
    processing = [_row(index, "fill") for index in range(100)]
    api = [
        _row(index + 1_000, "terminal_sink", corpus_kind="api")
        for index in range(100)
    ]
    manifest = build_target_manifest(processing, api)
    baseline_row = _row(3_000, "reviewed", corpus_kind="api")
    baseline_row.update({"proposal_decision": "false_positive", "unit_id": "u"})
    baseline = build_api_baseline([baseline_row])

    first = tmp_path / "first"
    second = tmp_path / "second"
    write_pilot_artifacts(first, manifest, baseline, input_hashes={"input": "a" * 64})
    write_pilot_artifacts(second, manifest, baseline, input_hashes={"input": "a" * 64})

    expected = {
        "target_manifest_200_v1.jsonl",
        "regression_baseline_v1.jsonl",
        "selection_summary_v1.json",
        "hash_ledger_v1.json",
    }
    assert {path.name for path in first.iterdir()} == expected
    assert not list(first.glob("*.tmp"))
    for name in expected:
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert b"\r\n" not in (first / name).read_bytes()


def test_regression_baseline_preserves_roles_without_source_text() -> None:
    accepted = _row(1, "accepted")
    accepted.update({"chain": ["native:buffer"], "source_snippet": "secret body"})
    same_if = _row(2, "same_if")
    same_if.update({"source_sha256s": [same_if.pop("source_sha256")]})
    downstream = _row(3, "downstream")
    downstream.update(
        {"downstream_role_status": "semantic_continuation", "operator_ids": ["native:buffer"]}
    )
    api = _row(4, "api", corpus_kind="api")
    api.update(
        {
            "proposal_decision": "true_positive",
            "unit_id": "api-unit",
            "steps": [{"call_name": "sink.addFeature"}],
            "boundary_source": "secret body",
        }
    )
    postfilter = _row(5, "postfilter", corpus_kind="api")
    postfilter.update({"unit_id": "negative-unit", "reason": "overmerged"})

    rows = build_regression_baseline(
        processing_accepted=[accepted],
        same_if_deferred=[same_if],
        downstream_negatives=[downstream],
        api_reviewed=[api],
        api_postfilter_negatives=[postfilter],
    )

    assert {row["baseline_role"] for row in rows} == {
        "processing_accepted_chain",
        "processing_same_if_support_deferred",
        "processing_downstream_boundary_negative",
        "api_reviewed_boundary",
        "api_postfilter_boundary_negative",
    }
    assert all("source_snippet" not in row for row in rows)
    assert all("boundary_source" not in row for row in rows)


def test_review_index_allows_same_row_candidate_alias() -> None:
    row = {"candidate_id": "candidate", "authority_candidate_ids": ["candidate"]}

    assert _review_index([row]) == {"candidate": row}


def test_review_index_rejects_candidate_reused_across_rows() -> None:
    with pytest.raises(ValueError, match="duplicate review evidence"):
        _review_index(
            [
                {"candidate_id": "candidate"},
                {"authority_candidate_ids": ["candidate"]},
            ]
        )
