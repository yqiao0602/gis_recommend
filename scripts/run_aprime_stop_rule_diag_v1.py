#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A′ stop-rule diagnostic (owner directive 2026-10-12) — OFFLINE, exact.

A prefix-inspecting stop rule applied offline to an already-generated stream
and truncated at its trigger point is EXACTLY equivalent to stopping at decode
time (for deterministic rules that only read the generated prefix). Hence A′
runs on CPU against the A1 arm outputs — no new inference, single host+stack.

Frozen rule R1 (structural cycle stop, params pre-registered):
  - extract complete stage objects from the (possibly truncated) generation
  - fire only at a stage boundary
  - fire iff the LAST p*3 stages (p=1..6) consist of 3 consecutive identical
    p-stage cycles  -> cut = end of stage (k - p*2), i.e. keep first cycle,
    drop repeats 2..3
  - closure to valid JSON for parse checking only (diagnostic)

Classes:
  C1 runaway   2048-arm rows with termination=MAX_TOKENS (52)
  C2 normal short  EOS rows, gold_n_stages <= 10
  C3 normal long   EOS rows, gold_n_stages > 10
  CTRL         idx=1024

Metrics (owner four + signal quality):
  M1 runaway termination: fired? kept-stage distribution vs gold; prefix
     parses after closure? ends at stage boundary (by construction)
  M2 normal-output protection: false-fire BEFORE true end on C2/C3/CTRL
  M3 stage preservation: boundary preservation (by construction) +
     closure-parse rate on C1
  M4 cost: tokens until cut vs full 2048 (inference-time saving proxy)
  S  signal quality: detector hit rate on C1; false-fire rate on C2/C3
"""

import gzip
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DW = os.path.join(HERE, "..", "..", "04_DIAG_WORK")
PULL = os.path.join(DW, "a1_pull")
PD = os.path.join(HERE, "..", "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT = os.path.join(PD, "A_PRIME_RESULTS_V1.json")

P_MAX = 6      # max cycle period (stages)
R_MIN = 3      # min consecutive repeats
WATCH_IDX = 1024

STAGE_RX = re.compile(
    r'\{\s*"seq"\s*:\s*(\d+)\s*,\s*"family"\s*:\s*"([A-Z_]+)"\s*,\s*'
    r'"repeat"\s*:\s*(\d+)\s*\}')


def extract_stages(text):
    """Complete stage objects with their end offsets in the raw text."""
    st = []
    for m in STAGE_RX.finditer(text or ""):
        st.append({"seq": int(m.group(1)), "family": m.group(2),
                   "repeat": int(m.group(3)), "end": m.end()})
    return st


def rule_fire(st):
    """Return (fired, cut_stage_index, period) per frozen R1 spec."""
    k = len(st)
    for p in range(1, P_MAX + 1):
        if k < p * R_MIN:
            continue
        cyc = [tuple((s["family"], s["repeat"]) for s in st[k - p * R_MIN + j * p:
                                                       k - p * R_MIN + (j + 1) * p])
               for j in range(R_MIN)]
        if cyc[0] == cyc[1] == cyc[2]:
            return True, k - p * (R_MIN - 1), p   # cut after first cycle kept
    return False, None, None


def closes_to_valid_json(text, cut_pos):
    """Closure matching the actual generation structure: stages array is the
    first (and for runaway rows, only) top-level field — close array+object."""
    frag = text[:cut_pos].rstrip().rstrip(",")
    return _ok(frag + "]}")


def _ok(s):
    try:
        json.loads(s)
        return True
    except Exception:
        return False


def main():
    with gzip.open(os.path.join(PULL, "a1_arm2048_raw.json.gz"),
                   "rt", encoding="utf-8") as f:
        arm2048 = {r["idx"]: r for r in json.load(f)["rows"]}
    with gzip.open(os.path.join(PULL, "a1_arm768_raw.json.gz"),
                   "rt", encoding="utf-8") as f:
        arm768 = {r["idx"]: r for r in json.load(f)["rows"]}

    c1 = [r for r in arm2048.values() if r["termination"] == "MAX_TOKENS"]
    c2 = [r for r in arm2048.values()
          if r["termination"] == "EOS" and r["gold_n_stages"] <= 10]
    c3 = [r for r in arm2048.values()
          if r["termination"] == "EOS" and r["gold_n_stages"] > 10]
    ctrl = [arm2048[WATCH_IDX]]

    res = {"schema": "a_prime_stop_rule_diag_v1",
           "rule": {"name": "R1_structural_cycle_stop",
                    "P_max": P_MAX, "R_min": R_MIN,
                    "boundary_only": True,
                    "offline_equivalence": "prefix rule on generated stream; "
                    "offline truncation == decode-time stop"}}

    # ---- C1: runaway rows ----
    fired_rows, nofire_rows = [], []
    for r in c1:
        st = extract_stages(r["pred_text"])
        fired, cut_k, p = rule_fire(st)
        if not fired:
            nofire_rows.append({"idx": r["idx"],
                                "stages_generated": len(st),
                                "gold_n_stages": r["gold_n_stages"]})
            continue
        cut_pos = st[cut_k - 1]["end"]
        kept = st[:cut_k]
        tail_after = len(r["pred_text"]) - cut_pos
        res.setdefault("c1_rows", []).append({
            "idx": r["idx"], "period": p,
            "stages_generated": len(st), "kept_stages": cut_k,
            "gold_n_stages": r["gold_n_stages"],
            "closure_parses": closes_to_valid_json(r["pred_text"], cut_pos),
            "tokens_saved_proxy_chars": tail_after,
        })
        fired_rows.append(r)
    res["c1_summary"] = {
        "n_runaway": len(c1),
        "rule_fired": len(fired_rows),
        "rule_did_not_fire": len(nofire_rows),
        "closure_parse_rate_on_fired": round(
            sum(1 for x in res.get("c1_rows", []) if x["closure_parses"])
            / max(1, len(fired_rows)), 4),
        "kept_stages_vs_gold_examples": [
            (x["idx"], x["gold_n_stages"], x["kept_stages"])
            for x in res.get("c1_rows", [])[:12]],
        "did_not_fire_detail": nofire_rows[:10],
    }

    # ---- M2: protection on normal rows + CTRL ----
    def false_fire(r):
        st = extract_stages(r["pred_text"])
        fired, cut_k, _ = rule_fire(st)
        if not fired:
            return False, None, None
        # fired: check position vs true end — for EOS rows the true end is
        # the text end; a fire with >=1 remaining complete stage OR any
        # residual text counts as premature.
        cut_pos = st[cut_k - 1]["end"]
        premature = cut_pos < len(r["pred_text"].rstrip()) - 2
        return fired, premature, cut_k

    ff = []
    for name, cls in (("c2_normal_short", c2), ("c3_normal_long", c3),
                      ("ctrl_1024", ctrl)):
        fires = 0
        for r in cls:
            f, prem, _ = false_fire(r)
            if f and prem:
                fires += 1
                ff.append({"class": name, "idx": r["idx"],
                           "gold_n_stages": r["gold_n_stages"],
                           "pred_n_stages": r["pred_n_stages"]})
        res.setdefault("m2_protection", {})[name] = {
            "n": len(cls), "premature_fires": fires,
            "protection_rate": round(1 - fires / max(1, len(cls)), 4)}
    res["m2_false_fire_detail"] = ff

    # ---- M4: cost proxy on C1 ----
    saved = [x["tokens_saved_proxy_chars"] for x in res.get("c1_rows", [])]
    res["m4_cost_proxy"] = {
        "note": "chars of generated text dropped by the cut (token saving "
                "proxy; online time saving requires a decode-time run)",
        "mean_chars_dropped": round(sum(saved) / max(1, len(saved))),
        "zero_rows": sum(1 for x in saved if x == 0),
    }

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps({k: res[k] for k in
                      ("c1_summary", "m2_protection", "m4_cost_proxy")},
                     indent=2, ensure_ascii=False))
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
