# -*- coding: utf-8 -*-
"""RL-line reward v1 battery tests.

Frozen battery: P1 / N1-N7 / B1-B3 per RL_LINE_PREREGISTRATION_V1_CANDIDATE.md
section 4.2, plus AUX hardening cases. All case definitions live in
scripts/rl_reward_v1.py (single source of truth); this file asserts them and a
few cross-cutting invariants (C0 masked-denominator math, gateway semantics).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rl_reward_v1 import (  # noqa: E402
    COMPONENTS,
    battery_cases,
    d4_hole_quantification,
    evaluate_prediction,
    run_battery,
)

FROZEN_IDS = {"P1", "N1", "N2", "N3", "N4", "N5", "N6", "N7",
              "B1", "B2", "B3"}
AUX_IDS = {"AUX1", "AUX2", "AUX3", "AUX4", "AUX5", "AUX6", "AUX7",
           "AUX8", "AUX9", "AUX10", "AUX11", "AUX12", "AUX13"}


def _battery():
    rows, n_pass, n_fail = run_battery([RASTER, TEMPORAL, SPATIAL])
    return rows, n_pass, n_fail


RASTER, TEMPORAL, SPATIAL = "RASTER_LOAD", "TEMPORAL_FILTER", "SPATIAL_FILTER"


def test_battery_ids_complete():
    ids = {c["id"] for c in battery_cases([RASTER, TEMPORAL, SPATIAL])}
    assert FROZEN_IDS <= ids, f"missing frozen cases: {FROZEN_IDS - ids}"
    assert AUX_IDS <= ids, f"missing aux cases: {AUX_IDS - ids}"
    assert len(ids) == len(FROZEN_IDS | AUX_IDS), "unexpected extra cases"


def test_frozen_battery_all_pass():
    rows, n_pass, n_fail = _battery()
    frozen = [r for r in rows if r["id"] in FROZEN_IDS]
    failed = [r for r in frozen if not r["pass"]]
    assert not failed, "frozen battery failures: " + "; ".join(
        f"{r['id']}: {r['mismatch_detail']}" for r in failed)
    assert len(frozen) == len(FROZEN_IDS)


def test_aux_battery_all_pass():
    rows, _, _ = _battery()
    aux = [r for r in rows if r["id"] in AUX_IDS]
    failed = [r for r in aux if not r["pass"]]
    assert not failed, "aux battery failures: " + "; ".join(
        f"{r['id']}: {r['mismatch_detail']}" for r in failed)


def test_c0_masked_exits_denominator():
    """r1a fail -> only r1a available with value 0 -> composite exactly 0.0;
    r1b fail -> {r1a=1, r1b=0} available -> composite exactly 0.5."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    res = evaluate_prediction("not json", vocab)
    assert res.components["r1a"]["value"] == 0
    assert set(res.masked) == {"r1b", "r1c", "r2", "r3", "r4"}
    assert res.composite == 0.0

    res = evaluate_prediction('{"repetition_groups": []}', vocab)
    assert res.composite == 0.5
    assert res.masked == ["r1c", "r2", "r3", "r4"]


def test_gateway_formal_path_seals_hole_and_r1_failures():
    """v1.2 formal path (gateway default ON): zero on r1 failures AND empty
    stages (D4=(b)); clean outputs keep C0. Gateway OFF preserves former
    behavior for diagnostics only."""
    vocab = [RASTER, TEMPORAL, SPATIAL]

    malformed = ('{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1},'
                 ' {"seq": 2, "family": "TEMPORAL_FILTER"}]}')
    res = evaluate_prediction(malformed, vocab)  # default = formal
    assert res.components["r1c"]["value"] == 0
    assert res.composite > 0.0 and res.composite_gateway == 0.0
    assert res.log["gateway_triggered"] == "r1_failure"

    clean = ('{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}]}')
    res = evaluate_prediction(clean, vocab)
    assert res.composite == res.composite_gateway == 1.0
    assert res.log["gateway_triggered"] is None

    # gateway OFF (diagnostic only): former behavior preserved
    res = evaluate_prediction(malformed, vocab, gateway_mode=False)
    assert res.composite_gateway == res.composite > 0.0


def test_d4_empty_stages_gateway_ruling():
    """D4=(b): empty stages -> formal reward 0 with reason empty_stages_gateway;
    C0 diagnostic (5/6) and r4 V1_empty_stages fail still recorded; non-empty
    outputs are NOT affected (no expanded penalties)."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    res = evaluate_prediction('{"stages": []}', vocab)
    assert res.composite_gateway == 0.0
    assert res.log["gateway_triggered"] == "empty_stages_gateway"
    assert res.composite == 5 / 6                       # C0 diagnostic retained
    assert res.components["r4"]["reason"] == "V1_empty_stages"  # diagnostics kept

    # non-empty minimal legal output unaffected by the ruling
    res = evaluate_prediction(
        '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}], '
        '"repetition_groups": []}', vocab)
    assert res.composite == res.composite_gateway == 1.0
    assert res.log["gateway_triggered"] is None

    # degenerate-family ordering under the formal reward: both at zero, legal above
    parse_fail = evaluate_prediction("not json", vocab)
    assert parse_fail.composite_gateway == 0.0
    assert parse_fail.composite_gateway < res.composite_gateway


def test_gateway_on_off_matrix_owner_required_cases():
    """Owner-required regression matrix: empty stages / missing stages / stages
    wrong type / minimal legal non-empty, under gateway ON (formal) and OFF."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    cases = {
        "empty_stages": '{"stages": []}',
        "missing_stages": '{"repetition_groups": []}',
        "stages_wrong_type": '{"stages": "oops"}',
        "minimal_legal": '{"stages": [{"seq": 1, "family": "RASTER_LOAD", '
                         '"repeat": 1}], "repetition_groups": []}',
    }
    for name, text in cases.items():
        formal = evaluate_prediction(text, vocab, gateway_mode=True)
        diag = evaluate_prediction(text, vocab, gateway_mode=False)
        if name == "minimal_legal":
            assert formal.composite_gateway == 1.0
            assert formal.composite == diag.composite == 1.0
        else:
            # formal path sealed: degenerate outputs cannot earn positive reward
            assert formal.composite_gateway == 0.0, name
            # diagnostic path keeps the pre-v1.2 C0 value for analysis
            assert diag.composite == formal.composite, name


def test_magnitude_never_scored():
    """Absolute repeat / total_iterations values must never change the score
    (Contract: magnitude not in Planner objective; E4 diagnostic only)."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    small = ('{"stages": [{"seq": 1, "family": "TEMPORAL_FILTER", "repeat": 2}],'
             ' "repetition_groups": [{"stage_seq": 1, "family": '
             '"TEMPORAL_FILTER", "repeat": 2, "iteration_hint": ["per_year"]}],'
             ' "total_iterations": 2}')
    huge = small.replace('"repeat": 2}', '"repeat": 9001}') \
                .replace('"repeat": 2,', '"repeat": 9001,') \
                .replace('"total_iterations": 2}', '"total_iterations": 9001}')
    r_small = evaluate_prediction(small, vocab)
    r_huge = evaluate_prediction(huge, vocab)
    assert r_small.composite == r_huge.composite == 1.0
    assert r_huge.log["repeat_values"] == [9001]
    assert r_huge.log["total_iterations"] == 9001


def test_formal_reward_interface():
    """Interface contract: the trainer consumes ONLY training_reward
    (alias of composite_gateway); composite is diagnostic and differs from it
    exactly when the gateway triggers."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    empty = evaluate_prediction('{"stages": []}', vocab)
    assert empty.training_reward == 0.0 == empty.composite_gateway
    assert empty.composite == 5 / 6 and empty.composite != empty.training_reward

    legal = evaluate_prediction(
        '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}], '
        '"repetition_groups": []}', vocab)
    assert legal.training_reward == legal.composite_gateway == 1.0


def test_components_always_complete():
    """Every case must produce a verdict for all six components (value or mask)."""
    for case in battery_cases([RASTER, TEMPORAL, SPATIAL]):
        res = evaluate_prediction(case["prediction"], case["vocab"])
        assert set(res.components.keys()) == set(COMPONENTS), case["id"]


def test_d4_hole_quantification():
    """Owner-ordered D4 hole test (v1.2): the formal path seals the empty
    hole (0.0) while C0 diagnostics retain 5/6; gateway OFF preserves former
    behavior. Contract has no explicit minItems:1 - engineering ruling only."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    hole = d4_hole_quantification(vocab)

    empty = hole["empty_stages"]
    assert empty["components"]["r4"] == 0  # V1_empty_stages determinable fail
    assert empty["c0_diagnostic"] == 5 / 6  # diagnostic retained (the old hole)
    assert empty["formal_reward_gateway_on"] == 0.0  # SEALED by D4=(b)
    assert empty["gateway_off_former_behavior"] == 5 / 6  # former behavior kept
    assert empty["gateway_triggered"] == "empty_stages_gateway"

    minimal = hole["minimal_legal"]
    assert minimal["formal_reward_gateway_on"] == 1.0

    parse_fail = hole["parse_fail"]
    assert parse_fail["formal_reward_gateway_on"] == 0.0
    assert parse_fail["c0_diagnostic"] == 0.0

    # formal ordering: degenerate outputs at zero, legal above
    assert parse_fail["formal_reward_gateway_on"] \
        == empty["formal_reward_gateway_on"] \
        < minimal["formal_reward_gateway_on"]


def test_d3_rg_absent_is_masked_not_passed():
    """D3 ruling: a missing repetition_groups key makes V3 undeterminable ->
    r4 masked (never silently passed), with the absence logged."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    res = evaluate_prediction(
        '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}]}', vocab)
    assert res.components["r4"]["value"] is None
    assert "rg_key_absent" in res.components["r4"]["reason"]
    assert res.log["field_presence"]["repetition_groups"] is False


def test_d1_scoped_masking_not_cascade():
    """D1 ruling: entry-level defects mask only affected components; r2 still
    evaluates over claimed families; r1a/r1b failures still cascade fully."""
    vocab = [RASTER, TEMPORAL, SPATIAL]
    res = evaluate_prediction(
        '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": true}]}', vocab)
    assert res.components["r1c"]["value"] == 0
    assert res.components["r2"]["value"] == 1   # claimed family is in vocab
    assert res.components["r3"]["value"] is None  # repeat semantics undeterminable
    assert res.components["r4"]["value"] is None  # structure undeterminable
