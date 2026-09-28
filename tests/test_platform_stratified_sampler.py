import math
import random

from scripts.platform_stratified_sampler import (
    SAMPLES_PER_EPOCH,
    audit_sampled_epoch,
    build_platform_stratified_sampler,
    compute_platform_stratified_weights,
)


def _wf(platform: str, task_type: str = "", codes: int = 1, idx: int = 0) -> dict:
    meta = {"task_type": task_type} if task_type else {}
    return {
        "platform": platform,
        "task_metadata": meta,
        "l3_codes": ["<START>"] + ["L3_01_01_01"] * codes + ["<END>"],
    }


def _corpus(gee: int = 8283, qgis: int = 629, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    gee_tasks = [f"gee_task_{i:02d}" for i in range(47)]
    for i in range(gee):
        rows.append(_wf("gee", gee_tasks[i % 47]))
    # QGIS: 367 single-step, 262 multi-step (paper_v1 shape)
    for i in range(367):
        rows.append(_wf("qgis", codes=1))
    for i in range(262):
        rows.append(_wf("qgis", codes=rng.choice([2, 3, 3, 4, 5, 6, 8, 9, 12])))
    return rows


def test_weights_match_target_ratio() -> None:
    rows = _corpus()
    weights, report = compute_platform_stratified_weights(rows, gee_ratio=0.7)
    gee_w = sum(w for w, r in zip(weights, rows) if r["platform"] == "gee")
    qgis_w = sum(w for w, r in zip(weights, rows) if r["platform"] == "qgis")
    assert abs(gee_w / (gee_w + qgis_w) - 0.7) < 0.01
    assert report["expected_qgis_repeats_per_epoch"] > 3
    assert report["expected_gee_usage_per_epoch"] < 1


def test_epoch_definition_is_ceil_times_batch() -> None:
    # frozen protocol: 8,817 effective train rows -> 276 steps -> 8,832 samples
    assert SAMPLES_PER_EPOCH == math.ceil(8817 / 32) * 32 == 8832


def test_pilot_audit_observes_protocol() -> None:
    rows = _corpus()
    sampler, report = build_platform_stratified_sampler(rows, gee_ratio=0.7)
    indices = list(sampler)
    assert len(indices) == 8928
    audit = audit_sampled_epoch(rows, indices)
    assert abs(audit["platform_share"]["gee"] - 0.7) < 0.02
    assert abs(audit["platform_share"]["qgis"] - 0.3) < 0.02
    # QGIS four strata approximately uniform among multi-step; '1' dominates by design share
    assert set(audit["qgis_length_strata_share"]) == {"1", "2-3", "4-7", "8+"}
    # GEE 47 task types all observed
    assert audit["gee_task_types_observed"] == 47


def test_ratio_variants_reachable() -> None:
    rows = _corpus()
    for ratio in (0.93, 0.80, 0.50):
        sampler, _ = build_platform_stratified_sampler(rows, gee_ratio=ratio)
        audit = audit_sampled_epoch(rows, list(sampler))
        assert abs(audit["platform_share"]["gee"] - ratio) < 0.02, ratio


def test_unknown_platform_rejected() -> None:
    rows = _corpus(gee=10, qgis=10) + [_wf("arcgis")]
    try:
        compute_platform_stratified_weights(rows, gee_ratio=0.7)
        raise AssertionError("should reject unknown platform")
    except ValueError as exc:
        assert "arcgis" in str(exc)


def test_missing_platform_rejected() -> None:
    rows = [_wf("gee", "t1"), _wf("gee", "t2")]
    try:
        compute_platform_stratified_weights(rows, gee_ratio=0.7)
        raise AssertionError("should reject single-platform corpus")
    except ValueError as exc:
        assert "both platforms" in str(exc)


def test_gee_row_without_stratum_key_rejected() -> None:
    empty = {"platform": "gee", "task_metadata": {}, "l3_codes": []}
    rows = [_wf("gee", "t1"), empty, _wf("qgis"), _wf("qgis")]
    try:
        compute_platform_stratified_weights(rows, gee_ratio=0.7)
        raise AssertionError("should reject GEE rows with no stratum key")
    except ValueError as exc:
        assert "task_type" in str(exc)


def test_gee_constant_task_type_falls_back_to_first_l3() -> None:
    rows = [
        {**_wf("gee"), "task_metadata": {"task_type": "GEE_COMPLETE_OUTPUT_WORKFLOW"},
         "l3_codes": ["<START>", "L3_03_09_01", "<END>"]},
        {**_wf("gee"), "task_metadata": {"task_type": "GEE_COMPLETE_OUTPUT_WORKFLOW"},
         "l3_codes": ["<START>", "L3_02_01_01", "<END>"]},
        _wf("qgis"), _wf("qgis"),
    ]
    weights, report = compute_platform_stratified_weights(rows, gee_ratio=0.5)
    assert report["gee_strata"] == 2  # two distinct entry families
