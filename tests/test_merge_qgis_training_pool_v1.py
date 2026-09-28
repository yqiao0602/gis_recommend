import json

from scripts.merge_qgis_training_pool_v1 import merge


def _existing(sample_id: str, l3: list[str], text: str, weight: float = 0.7, sha: str = "a" * 64) -> dict:
    return {
        "sample_id": sample_id,
        "record_id": sample_id,
        "source_sha256": sha,
        "l3_codes": ["<START>"] + l3 + ["<END>"],
        "task_description": text,
        "source_span": {"segments": [{"line_start": 1, "line_end": 2}]},
        "_training_quality": {"sample_weight": weight, "tier": "source_verified"},
    }


def _pattern(record_id: str, l3: list[str], text: str, sha: str = "b" * 64) -> dict:
    return {
        "record_id": record_id,
        "sample_id": record_id,
        "source_sha256": sha,
        "l3_sequence": l3,
        "task_text": text,
    }


def test_merge_admits_all_three_origins() -> None:
    pool, summary = merge(
        [_existing("e1", ["L3_02_01_01"], "task one")],
        [_pattern("p1", ["L3_02_01_01", "L3_02_05_01"], "task two")],
        [_pattern("s1", ["L3_01_10_01"], "task three", sha="c" * 64)],
        {},
    )
    in_pool = [row for row in pool if row.get("in_pool", True)]
    assert summary["final_pool_size"] == 3
    assert summary["origin_counts"] == {"api_pattern_v2": 1, "api_standalone_v2": 1, "audited_existing_506": 1}
    assert summary["multi_step"] == 1 and summary["single_step"] == 2


def test_audit_reject_rows_are_excluded() -> None:
    audit = {"e1": {"verdict": "REJECT"}}
    pool, summary = merge([_existing("e1", ["L3_02_01_01"], "task")], [], [], audit)
    assert summary["final_pool_size"] == 0
    assert summary["input"]["audited_existing"] == 1


def test_cross_pool_l3_plus_text_twin_is_rejected() -> None:
    same = "identical task text"
    pool, summary = merge(
        [_existing("e1", ["L3_02_01_01", "L3_02_05_01"], same)],
        [_pattern("p1", ["L3_02_01_01", "L3_02_05_01"], same)],
        [],
        {},
    )
    assert summary["final_pool_size"] == 1
    assert summary["cross_pool_rejects"] == 1
    rejects = [row for row in pool if not row.get("in_pool", True)]
    assert rejects[0]["reject_reason"].startswith("l3_sequence_plus_text_duplicate_of")


def test_same_source_and_span_rejects() -> None:
    sha = "f" * 64
    pattern = {**_pattern("p1", ["L3_02_05_01"], "text B", sha=sha), "span": {"segments": [{"line_start": 1, "line_end": 2}]}}
    pool, summary = merge(
        [_existing("e1", ["L3_02_01_01"], "text A", sha=sha)],
        [pattern],
        [],
        {},
    )
    assert summary["final_pool_size"] == 1
    assert summary["cross_pool_rejects"] == 1


def test_pattern_weight_is_gold_and_gates_closed() -> None:
    pool, summary = merge([], [_pattern("p1", ["L3_02_01_01", "L3_02_05_01"], "a real text")], [], {})
    row = [r for r in pool if r.get("in_pool", True)][0]
    assert row["sample_weight"] == 1.0
    assert row["training_admission"] == "admitted_train_only_candidate_v1"
    assert row["validation_eligible"] is False and row["test_eligible"] is False
    assert row["production_merge"] == "not_granted"
    assert summary["training_rows_emitted"] == 0
