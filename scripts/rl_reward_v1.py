#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RL-line reward v1.2 for Blueprint v2 (P0 planner output space).

Implements RL_LINE_PREREGISTRATION_V1_CANDIDATE.md sections 4.2-4.3, as revised
by owner review rounds of 2026-10-13 (D1-D3 round 2; D4=(b) round 3; protocol
sections 0.3-0.4; see REWARD_BATTERY_REPORT_V1_2.json):

  r1a/r1b  schema gate: JSON syntax / required `stages` field. Failure here is a
           whole-output scope failure -> full cascade mask (r1c-r4).
  r1c      entry-level schema types. Records per-entry defects; scores 0 on any
           defect, but downstream masking is now SCOPED to affected components
           (owner D1 ruling: no blanket cascade from局部 defects):
             - r2 evaluates over CLAIMED (string) families only; entries without
               a readable family make no claim and are excluded+logged.
             - r3 evaluates all DETERMINABLE sub-checks (legible repeats >= 1,
               adjacency between family-legible consecutive pairs); a determinable
               violation scores 0; otherwise any {not_dict, bad_family, bad_repeat}
               defect makes the maximal-run claim undeterminable -> r3 masked.
             - r4 evaluates determinable sub-checks (V1 empty, V5 type, and V3/V4
               over rg entries that reference well-formed stages); determinable
               violation -> 0; else entry defects break V2 -> r4 masked.
  r2       vocabulary closure over claimed families (exact, case-sensitive; no
           frequency/length bonus).
  r3       repetition FIELD semantics; absolute magnitude logged, NEVER scored
           (Contract E4 caliber).
  r4       cross-field consistency. D3 ruling: a MISSING repetition_groups key
           makes V3 undeterminable -> r4 masked (not passed), with the absence
           logged. Determinable failure elsewhere beats undeterminable -> 0.
  C0       equal-weight mean over AVAILABLE components - DIAGNOSTIC ONLY.
  gateway  THE FORMAL RL REWARD (default ON). Zeroes the final reward on
           whole-output failures (any r1*) AND on EMPTY stages (reason
           `empty_stages_gateway`, owner D4=(b) engineering ruling).
           gateway OFF is diagnostic-only and preserves pre-v1.2 behavior.

Masking rule (uniform): determinable-fail > undeterminable-mask > pass.
A component scores 0 if any determinable violation exists; otherwise, if any of
its sub-checks is undeterminable, it is masked with a reason; otherwise 1.
Final-reward rule (v1.2): formal reward = 0.0 if gateway triggers (any r1 failure
or empty stages), else C0. `composite` always carries the C0 diagnostic value;
`composite_gateway` is the reward used for training.

Schema authority: planner_design/PLANNER_V2_CONTRACT_FREEZE_v1.md (2026-10-04
FREEZE). Construction semantics verified against blueprint_v2_preflight_v1.py
(seq/stage_seq 1-based from one enumerate; maximal runs via runs_of(); rg entries
only for repeat > 1) and local P1/P2 SFT targets (2,985 rows): targets carry
{"stages", "repetition_groups"}; total_iterations/stage_count appeared in 0/2,985
targets -> presence is logged, never required.

D4 ruling (owner, round 3: option b): empty stages are a GATEWAY-level degenerate
output - the FINAL reward is 0 with reason `empty_stages_gateway`. This is an
engineering ruling sealing a known reward hole; it does NOT amend the frozen
schema contract (no minItems is being added). Component diagnostics are retained:
r4 still records the V1_empty_stages fail and C0 still carries 5/6 for analysis -
only the formal training reward is zeroed. If non-empty `stages` is ever
formalized in the Planner contract, that goes through the contract-change process.

D2 (accepted): NO code-fence stripping or repair; the raw generation is scored as
emitted and parse failures keep their reason codes.

Dialect scope: contract dialect only (stage_seq/family/repeat/iteration_hint).
The anchor dialect (anchor_seq/pattern/repeat_count/order_preserved) belongs to
the P1/P2 experiment lineage, is NOT the P0 output space, and is unsupported by
design. P0-dialect confirmation is an S1 fingerprint item.

Usage:
  python scripts/rl_reward_v1.py --selftest [--report OUT.json]
  python scripts/rl_reward_v1.py --input preds.jsonl --text-field target \
      --vocab vocab.json --output scored.jsonl [--gateway]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ACTIVE_HINTS = {"per_year", "per_band", "per_class", "generic_each", "unspecified"}
FORBIDDEN_HINTS = {"per_feature"}  # contract-disabled dimension (diagnostic_only)
COMPONENTS = ("r1a", "r1b", "r1c", "r2", "r3", "r4")


def _is_int(x) -> bool:
    """bool is a subclass of int in Python; the schema gate must reject booleans."""
    return isinstance(x, int) and not isinstance(x, bool)


@dataclass
class RewardResult:
    """Reward evaluation result.

    Interface contract (v1.2, owner-confirmed): the GRPO trainer must consume
    ONLY `training_reward` (alias of `composite_gateway`). `composite` is the
    C0 diagnostic value and must NEVER be passed to the optimizer. Raw component
    verdicts and `log` are for analysis/diagnostics only.
    """
    components: dict          # name -> {"value": 0|1|None, "reason": str}
    composite: float | None   # C0 mean over available - DIAGNOSTIC ONLY
    composite_gateway: float | None  # formal reward (gateway may zero it)
    log: dict

    @property
    def training_reward(self) -> float | None:
        """THE field the RL trainer consumes (formal reward; gateway applied)."""
        return self.composite_gateway

    @property
    def masked(self):
        return [k for k, v in self.components.items() if v["value"] is None]


def evaluate_prediction(text, vocab, gateway_mode=True):
    """Score one raw prediction string against the Blueprint v2 structural contract.

    gateway_mode=True (default) is the FORMAL RL reward path: final reward is 0.0
    on any r1 failure or empty stages (D4=(b)). gateway_mode=False is diagnostic
    only (pre-v1.2 behavior). `composite` always carries the C0 diagnostic value.
    """
    vocab = set(vocab)
    log = {"unknown_tokens": [], "repeat_values": [], "total_iterations": None,
           "field_presence": {}, "n_stages": None, "n_rg": None,
           "mask_reasons": [], "entry_defects": [], "r2_excluded_entries": 0,
           "r4_note": None, "gateway_reason": None}
    comp = {}

    def setc(name, value, reason=""):
        comp[name] = {"value": value, "reason": reason}
        if value is None:
            log["mask_reasons"].append(f"{name}: {reason}")

    def mask_all(names, reason):
        for n in names:
            setc(n, None, reason)

    # ---- r1a: JSON syntax (no repair, D2) ----
    try:
        root = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        setc("r1a", 0, f"json_syntax_error:{e.__class__.__name__}")
        log["gateway_reason"] = "r1_failure"
        mask_all(("r1b", "r1c", "r2", "r3", "r4"), "cascade:r1a_failed")
        return _finalize(comp, log, gateway_mode)
    setc("r1a", 1)

    # ---- r1b: required field ----
    if not isinstance(root, dict) or "stages" not in root:
        setc("r1b", 0, "missing_stages_or_non_object_root")
        log["gateway_reason"] = "r1_failure"
        mask_all(("r1c", "r2", "r3", "r4"), "cascade:r1b_failed")
        return _finalize(comp, log, gateway_mode)
    stages = root["stages"]
    if not isinstance(stages, list):
        setc("r1b", 0, "stages_not_a_list")
        log["gateway_reason"] = "r1_failure"
        mask_all(("r1c", "r2", "r3", "r4"), "cascade:r1b_failed")
        return _finalize(comp, log, gateway_mode)
    setc("r1b", 1)

    # ---- D4=(b) gateway trigger: empty stages (after parse + type gate) ----
    if len(stages) == 0:
        log["gateway_reason"] = "empty_stages_gateway"

    rg_present = "repetition_groups" in root
    rg = root.get("repetition_groups")
    rg_is_list = isinstance(rg, list)
    log["field_presence"] = {
        "repetition_groups": rg_present,
        "total_iterations": "total_iterations" in root,
        "stage_count": "stage_count" in root,
    }
    log["n_stages"] = len(stages)
    if rg_is_list:
        log["n_rg"] = len(rg)

    # ---- r1c: entry-level types (defects recorded, masking is scoped per D1) ----
    defects = []  # list of (index, kind)
    if not rg_is_list and rg_present:
        defects.append((-1, "rg_not_list"))
    for i, s in enumerate(stages):
        if not isinstance(s, dict):
            defects.append((i, "not_dict"))
            continue
        if not isinstance(s.get("family"), str):
            defects.append((i, "family"))
        if not _is_int(s.get("repeat")):
            defects.append((i, "repeat"))
        if not _is_int(s.get("seq")):
            defects.append((i, "seq"))
    log["entry_defects"] = [f"stage[{i}]_{k}" for i, k in defects]
    if defects:
        setc("r1c", 0, "schema_type_violations:" + ";".join(log["entry_defects"]))
    else:
        setc("r1c", 1)

    has = {}
    for i, s in enumerate(stages):
        has[i] = (isinstance(s, dict) and isinstance(s.get("family"), str),
                  _is_int(s.get("repeat")) if isinstance(s, dict) else False,
                  _is_int(s.get("seq")) if isinstance(s, dict) else False)

    # ---- r2: vocabulary closure over CLAIMED families ----
    claimed = [s["family"] for i, s in enumerate(stages)
               if isinstance(s, dict) and isinstance(s.get("family"), str)]
    log["r2_excluded_entries"] = len(stages) - len(claimed)
    unknown = sorted(set(claimed) - vocab)
    log["unknown_tokens"] = unknown
    setc("r2", 0 if unknown else 1, "unknown_family_tokens" if unknown else "")

    # ---- r3: repetition field semantics (determinable-first) ----
    r3_violation = None
    for i, s in enumerate(stages):
        if has[i][1] and s["repeat"] < 1:
            r3_violation = f"stage[{i}]_repeat_lt_1"
            break
    if r3_violation is None:
        for i in range(1, len(stages)):
            if has[i - 1][0] and has[i][0] and \
                    stages[i - 1]["family"] == stages[i]["family"]:
                r3_violation = f"non_maximal_run_at_stage[{i}]"
                break
    if r3_violation is not None:
        setc("r3", 0, r3_violation)
    elif any(k in ("not_dict", "family", "repeat") for _, k in defects):
        setc("r3", None, "undeterminable:entry_defect_breaks_sequence_semantics")
    else:
        setc("r3", 1)
        log["repeat_values"] = sorted({s["repeat"] for s in stages}) if stages else []
        if "total_iterations" in root:
            log["total_iterations"] = root["total_iterations"]

    # ---- r4: cross-field consistency (determinable-first; D3: absent rg = undeterminable) ----
    violation = None
    undeterminable = False
    if not stages:
        violation = "V1_empty_stages"  # semantic necessity; D4 disposition pending owner
    elif all(has[i][2] for i in range(len(stages))):
        if [s["seq"] for s in stages] != list(range(1, len(stages) + 1)):
            violation = "V2_seq_not_1_to_N"
    else:
        undeterminable = True  # some seq unreadable -> continuity unverifiable
    ti = root.get("total_iterations")
    if violation is None and ti is not None and not (_is_int(ti) and ti >= 0):
        violation = "V5_total_iterations_bad_type"
    if violation is None:
        if not rg_present or not rg_is_list:
            undeterminable = True  # D3: missing/invalid rg -> V3 undeterminable
        else:
            seen = set()
            for g in rg:
                if not isinstance(g, dict):
                    violation = "V3_rg_entry_not_object"
                    break
                ss = g.get("stage_seq")
                if not _is_int(ss) or not (1 <= ss <= len(stages)):
                    violation = "V3_rg_stage_seq_out_of_range"
                    break
                st = stages[ss - 1]
                if not has[ss - 1][0] or not has[ss - 1][1]:
                    undeterminable = True  # references a defective stage
                    continue
                if g.get("family") != st["family"] or g.get("repeat") != st["repeat"]:
                    violation = "V3_rg_stage_mismatch"
                    break
                if st["repeat"] <= 1:
                    violation = "V3_rg_references_non_repeated_stage"
                    break
                if ss in seen:
                    violation = "V3_duplicate_rg_for_stage"
                    break
                seen.add(ss)
                hints = g.get("iteration_hint", [])
                if not isinstance(hints, list):
                    violation = "V4_iteration_hint_not_a_list"
                    break
                for h in hints:
                    if not isinstance(h, str):
                        violation = "V4_hint_label_not_string"
                        break
                    if h in FORBIDDEN_HINTS:
                        violation = "V4_forbidden_hint_label"
                        break
                    if h not in ACTIVE_HINTS:
                        violation = "V4_unknown_hint_label"
                        break
                if violation:
                    break
            if violation is None:
                for i, s in enumerate(stages):
                    if not has[i][1]:
                        undeterminable = True  # coverage of unreadable repeat unverifiable
                    elif not has[i][2]:
                        undeterminable = True  # coverage of unreadable-seq stage unverifiable
                    elif s["repeat"] > 1 and s["seq"] not in seen:
                        violation = "V3_repeated_stage_missing_rg"
                        break
    if violation is not None:
        setc("r4", 0, violation)
    elif undeterminable or defects:
        reason = "undeterminable:rg_key_absent" if not rg_present else \
            "undeterminable:entry_or_rg_defect_breaks_structure"
        setc("r4", None, reason)
        log["r4_note"] = reason
    else:
        setc("r4", 1)

    return _finalize(comp, log, gateway_mode)


def _finalize(comp, log, gateway_mode):
    available = [c["value"] for c in comp.values() if c["value"] is not None]
    composite = (sum(available) / len(available)) if available else None
    # Formal reward (v1.2): gateway zeroes r1 failures AND empty stages (D4=(b)).
    triggered = None
    if gateway_mode:
        if any(comp[k]["value"] == 0 for k in ("r1a", "r1b", "r1c")):
            triggered = log.get("gateway_reason") or "r1_failure"
        elif log.get("gateway_reason"):
            triggered = log["gateway_reason"]  # empty_stages_gateway
    log["gateway_triggered"] = triggered
    gateway = 0.0 if (triggered and composite is not None) else composite
    return RewardResult(components=comp, composite=composite,
                        composite_gateway=gateway, log=log)


# ---------------------------------------------------------------- battery ----
# Frozen battery: P1 / N1-N7 / B1-B3 (V1 section 4.2), updated to the v1.1 scoped
# masking semantics (owner D1/D3 rulings). Families are real vocabulary members.

def _bp(stages, rg="ABSENT", **extra):
    root = {"stages": stages}
    if rg != "ABSENT":
        root["repetition_groups"] = rg
    root.update(extra)
    return json.dumps(root, ensure_ascii=False)


RL, TF, SP = "RASTER_LOAD", "TEMPORAL_FILTER", "SPATIAL_FILTER"


def battery_cases(vocab):
    v = sorted(set(vocab) | {RL, TF, SP})
    cases = [
        # ---- frozen battery (V1 section 4.2; expectations per v1.1 semantics) ----
        ("P1", "well-formed plan with one repeated stage + per_year hint",
         _bp([{"seq": 1, "family": RL, "repeat": 1},
              {"seq": 2, "family": TF, "repeat": 3}],
             rg=[{"stage_seq": 2, "family": TF, "repeat": 3,
                  "iteration_hint": ["per_year"]}], total_iterations=5),
         dict(r1a=1, r1b=1, r1c=1, r2=1, r3=1, r4=1), 1.0),
        ("N1", "adjacent same family = non-maximal run (determinable fail)",
         _bp([{"seq": 1, "family": RL, "repeat": 1},
              {"seq": 2, "family": RL, "repeat": 1}], rg=[]),
         dict(r3=0, r4=1), None),
        ("N2", "rg references a non-repeated (repeat=1) stage",
         _bp([{"seq": 1, "family": RL, "repeat": 1},
              {"seq": 2, "family": TF, "repeat": 1}],
             rg=[{"stage_seq": 2, "family": TF, "repeat": 1,
                  "iteration_hint": ["per_year"]}]),
         dict(r4=0), None),
        ("N3", "rg present but missing the entry for a repeated stage",
         _bp([{"seq": 1, "family": RL, "repeat": 1},
              {"seq": 2, "family": TF, "repeat": 3}], rg=[]),
         dict(r4=0), None),
        ("N4", "forbidden hint label per_feature",
         _bp([{"seq": 1, "family": TF, "repeat": 2}],
             rg=[{"stage_seq": 1, "family": TF, "repeat": 2,
                  "iteration_hint": ["per_feature"]}]),
         dict(r4=0), None),
        ("N5", "unparseable text -> r1a=0, full cascade (D2: no repair)",
         "this is not json",
         dict(r1a=0, r1b=None, r1c=None, r2=None, r3=None, r4=None), 0.0),
        ("N6", "JSON but stages missing -> r1b=0, cascade",
         '{"repetition_groups": []}',
         dict(r1a=1, r1b=0, r1c=None, r2=None, r3=None, r4=None), 0.5),
        ("N7", "empty stages -> r4 V1 determinable fail (D4 hole: C0=5/6)",
         _bp([]),
         dict(r4=0), 5 / 6),
        ("B1", "repeat=1, rg=[] -> legal",
         _bp([{"seq": 1, "family": RL, "repeat": 1}], rg=[]),
         dict(r3=1, r4=1), 1.0),
        ("B2", "same family separated by another family -> legal (adjacent-only)",
         _bp([{"seq": 1, "family": RL, "repeat": 1},
              {"seq": 2, "family": TF, "repeat": 1},
              {"seq": 3, "family": RL, "repeat": 1}], rg=[]),
         dict(r3=1, r4=1), 1.0),
        ("B3", "empty hint list -> legal (unspecified)",
         _bp([{"seq": 1, "family": TF, "repeat": 2}],
             rg=[{"stage_seq": 1, "family": TF, "repeat": 2,
                  "iteration_hint": []}]),
         dict(r4=1), 1.0),
        # ---- AUX hardening (beyond the frozen battery; reported separately) ----
        ("AUX1", "boolean repeat: r1c=0; r2 still evaluates (D1 scoped masking)",
         _bp([{"seq": 1, "family": RL, "repeat": True}]),
         dict(r1c=0, r2=1, r3=None, r4=None), 3 / 4),
        ("AUX2", "case-sensitive vocab: lowercase family -> r2=0 only",
         _bp([{"seq": 1, "family": "raster_load", "repeat": 1}], rg=[]),
         dict(r2=0, r3=1, r4=1), None),
        ("AUX3", "duplicate rg entries for one stage -> r4=0",
         _bp([{"seq": 1, "family": TF, "repeat": 2}],
             rg=[{"stage_seq": 1, "family": TF, "repeat": 2,
                  "iteration_hint": ["per_year"]},
                 {"stage_seq": 1, "family": TF, "repeat": 2,
                  "iteration_hint": ["per_year"]}]),
         dict(r4=0), None),
        ("AUX4", "rg present but empty with all repeat=1 -> fully legal",
         _bp([{"seq": 1, "family": RL, "repeat": 1}], rg=[]),
         dict(r4=1), 1.0),
        ("AUX5", "seq starting at 0 -> r4 V2 determinable fail",
         _bp([{"seq": 0, "family": RL, "repeat": 1}], rg=[]),
         dict(r4=0), None),
        ("AUX6", "extra top-level fields (stage_count) tolerated",
         _bp([{"seq": 1, "family": RL, "repeat": 1}], rg=[], stage_count=1),
         dict(r1b=1, r4=1), 1.0),
        ("AUX7", "root is a list -> r1b=0 cascade",
         "[1, 2, 3]",
         dict(r1a=1, r1b=0, r1c=None), 0.5),
        ("AUX8", "total_iterations as string -> r4 V5 determinable fail",
         _bp([{"seq": 1, "family": RL, "repeat": 1}], rg=[],
              total_iterations="38"),
         dict(r4=0), None),
        ("AUX9", "rg key ABSENT -> r4 MASKED (D3: missing != correct), "
                 "composite 1.0 over remaining five",
         '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}]}',
         dict(r4=None), 1.0),
        ("AUX10", "gateway_mode: malformed entry -> gateway 0 vs C0 mean > 0",
         _bp([{"seq": 1, "family": RL, "repeat": 1}, {"seq": 2, "family": TF}]),
         dict(r1c=0), None),
        ("AUX11", "unknown hint label -> r4 V4 determinable fail",
         _bp([{"seq": 1, "family": TF, "repeat": 2}],
             rg=[{"stage_seq": 1, "family": TF, "repeat": 2,
                  "iteration_hint": ["per_decade"]}]),
         dict(r4=0), None),
        ("AUX12", "rg not a list -> r1c=0; r2/r3 evaluated, r4 masked (D1 scoping)",
         '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}], '
         '"repetition_groups": "oops"}',
         dict(r1c=0, r2=1, r3=1, r4=None), 4 / 5),
        ("AUX13", "stage missing seq + rg present -> r1c=0, r4 masked, no crash "
                  "(found by S2 dry-run: real P0 samples emit seq-less stages); "
                  "r3 unaffected by seq defects per D1 scoping",
         '{"stages": [{"seq": 1, "family": "RASTER_LOAD", "repeat": 1}, '
         '{"family": "TEMPORAL_FILTER", "repeat": 2}], '
         '"repetition_groups": [{"stage_seq": 2, "family": "TEMPORAL_FILTER", '
         '"repeat": 2, "iteration_hint": []}]}',
         dict(r1c=0, r2=1, r3=1, r4=None), 4 / 5),
    ]
    out = []
    # Formal-reward expectations (v1.2 gateway semantics): 0.0 on r1 failure or
    # empty stages; otherwise equal to the C0 diagnostic value.
    gateway_expect = {"P1": 1.0, "B1": 1.0, "B2": 1.0, "B3": 1.0, "AUX4": 1.0,
                      "AUX6": 1.0, "AUX9": 1.0,
                      "N5": 0.0, "N6": 0.0, "N7": 0.0,
                      "AUX1": 0.0, "AUX7": 0.0, "AUX10": 0.0, "AUX12": 0.0}
    for cid, desc, text, expect, expect_composite in cases:
        out.append({"id": cid, "description": desc, "prediction": text,
                    "expect": expect, "expect_composite": expect_composite,
                    "expect_gateway": gateway_expect.get(cid),
                    "vocab": v})
    return out


def run_battery(vocab, gateway_mode=True):
    """Runs all cases under the FORMAL path (gateway default ON); returns
    (rows, n_pass, n_fail). Asserts component verdicts, C0 values where given,
    and formal-reward (gateway) values where given."""
    rows = []
    for case in battery_cases(vocab):
        res = evaluate_prediction(case["prediction"], case["vocab"], gateway_mode)
        got = {k: v["value"] for k, v in res.components.items()}
        ok = True
        detail = []
        for k, want in case["expect"].items():
            if got.get(k) != want:
                ok = False
                detail.append(f"{k}: want {want}, got {got.get(k)} "
                              f"({res.components[k]['reason']})")
        if case["expect_composite"] is not None and \
                abs(res.composite - case["expect_composite"]) > 1e-9:
            ok = False
            detail.append(f"composite: want {case['expect_composite']}, "
                          f"got {res.composite}")
        if case["expect_gateway"] is not None and \
                abs(res.composite_gateway - case["expect_gateway"]) > 1e-9:
            ok = False
            detail.append(f"gateway: want {case['expect_gateway']}, "
                          f"got {res.composite_gateway} "
                          f"({res.log.get('gateway_triggered')})")
        rows.append({"id": case["id"], "description": case["description"],
                     "pass": ok, "got": got, "composite": res.composite,
                     "composite_gateway": res.composite_gateway,
                     "gateway_triggered": res.log.get("gateway_triggered"),
                     "masked": res.masked, "mismatch_detail": detail,
                     "log": res.log})
    n_pass = sum(1 for r in rows if r["pass"])
    return rows, n_pass, len(rows) - n_pass


def d4_hole_quantification(vocab):
    """Owner-ordered D4 hole test (v1.2): exact component/C0/formal scores for
    the degenerate-vs-legal baselines, under gateway ON (formal) and OFF
    (diagnostic). Documents that the empty-sequence hole is sealed in the formal
    path while C0 diagnostics are retained."""
    scenarios = {
        "empty_stages": _bp([]),
        "minimal_legal": _bp([{"seq": 1, "family": RL, "repeat": 1}], rg=[]),
        "parse_fail": "not json at all",
    }
    out = {}
    for name, text in scenarios.items():
        formal = evaluate_prediction(text, vocab, gateway_mode=True)
        diag = evaluate_prediction(text, vocab, gateway_mode=False)
        out[name] = {
            "formal_reward_gateway_on": formal.composite_gateway,
            "c0_diagnostic": formal.composite,
            "gateway_off_former_behavior": diag.composite_gateway,
            "components": {k: v["value"] for k, v in
                           formal.components.items()},
            "reasons": {k: v["reason"] for k, v in
                        formal.components.items() if v["reason"]},
            "gateway_triggered": formal.log.get("gateway_triggered"),
        }
    out["ruling"] = (
        "D4=(b): empty stages are a gateway-level degenerate output; formal "
        "reward 0 (empty_stages_gateway). Engineering ruling only - the frozen "
        "schema contract is NOT amended (no minItems added); component "
        "diagnostics (r4 V1_empty_stages, C0) retained for analysis.")
    return out


def load_vocab(path):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    fams = obj["families"] if isinstance(obj, dict) else obj
    return list(fams)


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", help="write battery report JSON here")
    ap.add_argument("--input", help="jsonl of predictions to score")
    ap.add_argument("--text-field", default="target")
    ap.add_argument("--vocab")
    ap.add_argument("--output", help="scored jsonl output")
    ap.add_argument("--no-gateway", action="store_true",
                    help="diagnostic mode: disable the formal gateway "
                         "(pre-v1.2 behavior; NOT for RL training)")
    args = ap.parse_args(argv)

    if args.selftest:
        vocab = load_vocab(args.vocab) if args.vocab else [RL, TF, SP]
        rows, n_pass, n_fail = run_battery(vocab, not args.no_gateway)
        for r in rows:
            flag = "PASS" if r["pass"] else "FAIL"
            print(f"[{flag}] {r['id']}: {r['description']}")
            for d in r["mismatch_detail"]:
                print(f"       {d}")
        print(f"battery: {n_pass}/{n_pass + n_fail} pass")
        if args.report:
            rep = {"battery_pass": n_pass, "battery_total": n_pass + n_fail,
                   "vocab_source": args.vocab or "inline_test_vocab",
                   "d4_hole": d4_hole_quantification(vocab), "rows": rows}
            Path(args.report).write_text(
                json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1 if n_fail else 0

    if args.input:
        assert args.vocab and args.output, "--input requires --vocab and --output"
        vocab = load_vocab(args.vocab)
        n = fails = 0
        with open(args.input, encoding="utf-8") as fin, \
                open(args.output, "w", encoding="utf-8") as fout:
            for line in fin:
                if not line.strip():
                    continue
                row = json.loads(line)
                res = evaluate_prediction(str(row.get(args.text_field, "")),
                                          vocab, not args.no_gateway)
                n += 1
                if res.composite != 1.0:
                    fails += 1
                fout.write(json.dumps({
                    "row_id": row.get("row_id", row.get("source_row_id")),
                    "composite": res.composite,
                    "components": {k: v["value"] for k, v in
                                   res.components.items()},
                    "reasons": {k: v["reason"] for k, v in
                                res.components.items() if v["reason"]},
                    "masked": res.masked, "log": res.log,
                }, ensure_ascii=False) + "\n")
        print(f"scored {n} rows, {fails} with composite != 1.0")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
