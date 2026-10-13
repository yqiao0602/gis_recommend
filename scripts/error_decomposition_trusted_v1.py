#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Error-type decomposition on the TRUSTED SUBSET (owner directive
2026-10-12, step 2): locate the capability bottleneck with existing
predictions — distinguish operator-selection / stage-omission / order /
repeat-count / parse failures, not just aggregate F1.

Multi-label row rates (a row can carry several types) + single primary
attribution (priority: parse > wholesale > selection_miss > over_emission >
repeat_count > order > partial_other > good). Strata: weak families
(BAND_SELECT / GEOMETRY_DEFINE / TERRAIN_DERIVED gold rows), long chains,
repeat-heavy rows.
"""

import json
import os
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
TRUST = os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl")
PRED = os.path.join(PD, "p0b_768", "predictions.json")
DUAL = os.path.join(PD, "DUAL_TRACK_EVAL_V1.json")
OUT = os.path.join(PD, "ERROR_DECOMPOSITION_TRUSTED_V1.json")

WEAK = {"BAND_SELECT", "GEOMETRY_DEFINE", "TERRAIN_DERIVED"}
ORDER_GAP = 0.15


def expand(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def parse_pred(text):
    try:
        obj = json.loads(text or "")
        if isinstance(obj, dict) and isinstance(obj.get("stages"), list) \
                and obj["stages"]:
            return expand(obj["stages"])
    except Exception:
        pass
    return None


def main():
    dual = json.load(open(DUAL, encoding="utf-8"))
    excl = {int(k) for k in dual["exclusions"]["rows"]}
    rows = []
    with open(TRUST, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if line.strip():
                r = json.loads(line)
                t = r["target"]
                if isinstance(t, str):
                    t = json.loads(t)
                rows.append({"task": r["task"], "tgt": t})
    items = json.load(open(PRED, encoding="utf-8"))["items"]

    sub = [i for i in range(len(rows)) if i not in excl]

    recs = []
    for i in sub:
        r = rows[i]
        gold_stages = r["tgt"]["stages"]
        gold_seq = expand(gold_stages)
        gold_fams = set(s["family"] for s in gold_stages)
        gold_counts = Counter(gold_seq)
        pseq = parse_pred(items[i].get("pred_text") or "")
        hit_cap = bool(items[i].get("hit_max_new_tokens"))
        types = set()
        rec = {"idx": i,
               "task_head": (r["task"] or "").splitlines()[0][:80],
               "gold_n_stages": len(gold_stages),
               "gold_len": len(gold_seq),
               "repeat_heavy": any(int(s.get("repeat", 1)) > 1
                                   for s in gold_stages),
               "weak_fam_gold": sorted(gold_fams & WEAK)}
        if pseq is None:
            types.add("parse_failure")
            if hit_cap:
                types.add("hit_max_tokens")
            rec.update({"pred_len": None, "types": sorted(types)})
            recs.append(rec)
            continue
        pred_fams = set(pseq)
        pred_counts = Counter(pseq)
        miss = gold_fams - pred_fams
        over = pred_fams - gold_fams
        cnt_err = {f for f in (gold_fams & pred_fams)
                   if pred_counts[f] != gold_counts[f]}
        pc, gc = Counter(pseq), Counter(gold_seq)
        tp = sum(min(pc[x], gc[x]) for x in pc)
        bag = 2 * tp / (len(pseq) + len(gold_seq)) if (pseq or gold_seq) else 0.0
        L = lcs(pseq, gold_seq)
        lf = 2 * L / (len(pseq) + len(gold_seq)) if (pseq or gold_seq) else 0.0
        if bag < 0.10:
            types.add("wholesale_mismatch")
        if miss:
            types.add("stage_selection_miss")
        if over:
            types.add("over_emission")
        if cnt_err:
            types.add("repeat_count_error")
        if bag - lf > ORDER_GAP:
            types.add("order_error")
        if not types:
            types.add("good_match" if bag >= 0.8 else "partial_other")
        if bag >= 0.8 and "order_error" not in types:
            types.add("good_match")
        first_ok = bool(pseq) and bool(gold_seq) and pseq[0] == gold_seq[0]
        rec.update({"pred_len": len(pseq), "bag": round(bag, 4),
                    "lcs_f1": round(lf, 4),
                    "miss_families": sorted(miss), "over_families": sorted(over),
                    "count_err_families": sorted(cnt_err),
                    "first_stage_ok": first_ok,
                    "types": sorted(types)})
        recs.append(rec)

    # multi-label rates + primary attribution
    ml = Counter()
    for rec in recs:
        for t in rec["types"]:
            ml[t] += 1
    PRIO = ["parse_failure", "wholesale_mismatch", "stage_selection_miss",
            "over_emission", "repeat_count_error", "order_error",
            "partial_other", "good_match"]
    primary = Counter()
    for rec in recs:
        for p in PRIO:
            if p in rec["types"]:
                primary[p] += 1
                rec["primary"] = p
                break

    # strata
    def rate(rows_, t):
        return round(sum(1 for r in rows_ if t in r["types"])
                     / max(1, len(rows_)), 4)

    strata = {}
    groups = {
        "all_trusted": recs,
        "band_select_gold": [r for r in recs if "BAND_SELECT" in r["weak_fam_gold"]],
        "geometry_terrain_gold": [r for r in recs
                                  if set(r["weak_fam_gold"]) & {"GEOMETRY_DEFINE", "TERRAIN_DERIVED"}],
        "long_gt25": [r for r in recs if r["gold_n_stages"] > 25],
        "repeat_heavy": [r for r in recs if r["repeat_heavy"]],
    }
    TYPES = ["parse_failure", "wholesale_mismatch", "stage_selection_miss",
             "over_emission", "repeat_count_error", "order_error",
             "partial_other", "good_match", "hit_max_tokens"]
    for name, g in groups.items():
        strata[name] = {"n": len(g),
                        **{t: rate(g, t) for t in TYPES}}

    # top missed families among selection misses
    miss_fam = Counter()
    for r in recs:
        for f in r.get("miss_families", []):
            miss_fam[f] += 1
    cnt_err_fam = Counter()
    for r in recs:
        for f in r.get("count_err_families", []):
            cnt_err_fam[f] += 1
    # repeat-count error: relative direction
    over_n = under_n = 0
    for r in recs:
        if "repeat_count_error" not in r["types"]:
            continue
        gold_seq = expand(rows[r["idx"]]["tgt"]["stages"])
        pseq = parse_pred(items[r["idx"]].get("pred_text") or "") or []
        gc, pc = Counter(gold_seq), Counter(pseq)
        for f in r["count_err_families"]:
            if pc[f] > gc[f]:
                over_n += 1
            else:
                under_n += 1

    # parse-failure breakdown
    pf = [r for r in recs if "parse_failure" in r["types"]]
    pf_hit = sum(1 for r in pf if "hit_max_tokens" in r["types"])

    out = {
        "schema": "error_decomposition_trusted_v1",
        "basis": ("trusted subset (n=%d), trusted gold (fix1), frozen "
                  "p0b_768 predictions" % len(sub)),
        "n": len(recs),
        "multilabel_row_rates": {t: round(ml[t] / len(recs), 4) for t in TYPES},
        "primary_attribution": {p: round(primary[p] / len(recs), 4)
                                for p in PRIO},
        "strata_rates": strata,
        "top_missed_families": dict(miss_fam.most_common(12)),
        "top_count_error_families": dict(cnt_err_fam.most_common(12)),
        "count_error_direction": {"over_emission_runs": over_n,
                                   "under_emission_runs": under_n},
        "parse_failure": {"n": len(pf), "hit_max_tokens": pf_hit,
                           "note": "hit_max_tokens = generation budget "
                                   "exhausted (termination control issue)"},
        "row_records": recs,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    print(json.dumps({k: out[k] for k in
                      ("n", "multilabel_row_rates", "primary_attribution",
                       "count_error_direction", "parse_failure")},
                     indent=2, ensure_ascii=False))
    print("strata:")
    for name, s in strata.items():
        print(" ", name, s)
    print("top missed:", out["top_missed_families"])
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
