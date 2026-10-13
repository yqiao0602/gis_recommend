#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experiment A: stage-selection diagnosis for the five high-frequency
missing glue families (+ AGGREGATION runaway family, + ITERATIVE_APPLY).

Questions (owner, 2026-10-11):
  Q-A1 Does the model fundamentally fail to select these stages, or only err
       under certain task conditions?
  Q-A2 Presence-level miss vs under-count split.
  Q-A3 Miss rate vs gold repeat count / position / gold length / task-type.

Prediction source: Arm A (768 greedy) — same as phase 1.
"""

import json
import os
import sys
import re
from collections import Counter, defaultdict

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")  # system_redesign

PRED = os.path.join(REPO, "docs", "reports",
                    "route2_p0_contract", "plan_pipeline_v1", "planner_design",
                    "p0b_768", "predictions.json")
DEV = os.path.join(REPO, "..", "04_DIAG_WORK", "planner_v2_dev.jsonl")
OUT = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                   "plan_pipeline_v1", "planner_design",
                   "EXP_A_STAGE_SELECTION_DIAGNOSIS_V1.json")

FAMILIES = ["BAND_SELECT", "TEMPORAL_FILTER", "SPATIAL_FILTER",
            "ATTRIBUTE_FILTER", "RASTER_LOAD"]
EXTRA = ["AGGREGATION", "ITERATIVE_APPLY"]

# lightweight task-type keyword buckets from the task title line
TASK_BUCKETS = [
    ("time_series", re.compile(r"time.series|temporal|trend|season", re.I)),
    ("ndvi_veg", re.compile(r"NDVI|vegetat|crop|veg", re.I)),
    ("classify", re.compile(r"classif|land.cover|landcover", re.I)),
    ("change_detect", re.compile(r"change|deforest|urban.growth", re.I)),
    ("cloud", re.compile(r"cloud", re.I)),
    ("water", re.compile(r"water|flood|drought|precipit|rain", re.I)),
    ("temperature", re.compile(r"temperature|LST|heat", re.I)),
    ("terrain", re.compile(r"elevation|DEM|slope|terrain|hillshade", re.I)),
]


def task_bucket(task_text):
    t = (task_text or "").splitlines()[0] if task_text else ""
    for name, rx in TASK_BUCKETS:
        if rx.search(t):
            return name
    return "other"


def expand(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def main():
    pred = json.load(open(PRED, encoding="utf-8"))
    items = pred["items"]
    dev = [json.loads(l) for l in open(DEV, encoding="utf-8") if l.strip()]
    assert len(items) == len(dev)

    per_family = {f: {"TP": 0, "FN_absent": 0, "FN_undercount": 0,
                      "FP": 0, "TN": 0} for f in FAMILIES + EXTRA}
    # conditioning tables
    miss_by_gold_repeat = {f: defaultdict(lambda: [0, 0]) for f in FAMILIES + EXTRA}  # [miss, total]
    miss_by_position = {f: defaultdict(lambda: [0, 0]) for f in FAMILIES + EXTRA}     # first-occurrence third
    miss_by_length = {f: defaultdict(lambda: [0, 0]) for f in FAMILIES + EXTRA}       # gold length bucket
    miss_by_bucket = {f: defaultdict(lambda: [0, 0]) for f in FAMILIES + EXTRA}
    fp_by_bucket = {}
    rg_usage = {f: {"via_repetition_group": 0, "unrolled": 0, "total_pred": 0}
                for f in FAMILIES + EXTRA}

    for it, dv in zip(items, dev):
        text = it.get("pred_text") or ""
        cap = it.get("hit_max_new_tokens", 0)
        try:
            obj = json.loads(text)
            ok = isinstance(obj, dict) and "stages" in obj
        except Exception:
            ok = False
        if not ok:
            continue  # experiment A conditions on parseable predictions
        tgt = dv.get("target")
        if isinstance(tgt, str):
            try:
                tgt = json.loads(tgt)
            except Exception:
                continue
        gold_stages = tgt.get("stages", []) if isinstance(tgt, dict) else []
        gold_seq = expand(gold_stages)
        pred_seq = expand(obj["stages"])
        gset = set(gold_stages and [g["family"] for g in gold_stages])
        gcount = Counter(g["family"] for g in gold_stages)
        pcount = Counter(pred_seq)
        prg = obj.get("repetition_groups", []) or []
        rg_fams = {g.get("family") for g in prg if g.get("repeat", 1) > 1}
        glen = len(gold_seq)
        lbucket = ("short(<=10)" if glen <= 10 else
                   "mid(11-25)" if glen <= 25 else "long(>25)")
        bucket = task_bucket(dv.get("task"))

        for f in FAMILIES + EXTRA:
            in_g = gcount.get(f, 0) > 0
            in_p = pcount.get(f, 0) > 0
            e = per_family[f]
            if in_g and in_p:
                e["TP"] += 1
                if f in rg_fams:
                    rg_usage[f]["via_repetition_group"] += 1
                elif pcount[f] > 1:
                    rg_usage[f]["unrolled"] += 1
                rg_usage[f]["total_pred"] += 1
            elif in_g and not in_p:
                e["FN_absent"] += 1
            elif (not in_g) and in_p:
                e["FP"] += 1
            else:
                e["TN"] += 1
            if in_g:
                # under-count FN subtype
                if not in_p:
                    e["FN_undercount"] += 0  # absent already counted
                # gold repeat conditioning
                gc = gcount[f]
                rb = "1" if gc == 1 else ("2" if gc == 2 else "3+")
                miss = 0 if in_p else 1
                miss_by_gold_repeat[f][rb][0] += miss
                miss_by_gold_repeat[f][rb][1] += 1
                # position conditioning: first occurrence third of gold seq
                first_pos = next(i for i, x in enumerate(gold_seq) if x == f)
                third = ("early" if first_pos < glen / 3 else
                         "middle" if first_pos < 2 * glen / 3 else "late")
                miss_by_position[f][third][0] += miss
                miss_by_position[f][third][1] += 1
                miss_by_length[f][lbucket][0] += miss
                miss_by_length[f][lbucket][1] += 1
                miss_by_bucket[f][bucket][0] += miss
                miss_by_bucket[f][bucket][1] += 1

    # under-count split: for TP rows, count-level deficit handled in experiment B;
    # here we split FN into absent vs under-counted by re-checking presence with
    # relaxed counting (present but fewer occurrences == TP-presence with count err)
    # -> presence-level FN is strictly "absent".
    result = {"families": {}}
    for f in FAMILIES + EXTRA:
        e = per_family[f]
        rel = e["TP"] + e["FN_absent"]
        result["families"][f] = {
            **e,
            "recall_presence": round(e["TP"] / rel, 4) if rel else None,
            "gold_prevalence": rel,
            "fp_rate_when_absent": round(e["FP"] / max(1, e["FP"] + e["TN"]), 4),
        }
        if f in FAMILIES:
            result["families"][f]["miss_by_gold_repeat"] = {
                k: f"{v[0]}/{v[1]} = {round(v[0]/max(1,v[1]),3)}"
                for k, v in sorted(miss_by_gold_repeat[f].items())}
            result["families"][f]["miss_by_position"] = {
                k: f"{v[0]}/{v[1]} = {round(v[0]/max(1,v[1]),3)}"
                for k, v in sorted(miss_by_position[f].items())}
            result["families"][f]["miss_by_gold_length"] = {
                k: f"{v[0]}/{v[1]} = {round(v[0]/max(1,v[1]),3)}"
                for k, v in sorted(miss_by_length[f].items())}
            result["families"][f]["miss_by_task_bucket"] = {
                k: f"{v[0]}/{v[1]} = {round(v[0]/max(1,v[1]),3)}"
                for k, v in sorted(miss_by_bucket[f].items(),
                                   key=lambda kv: -kv[1][1])[:8]}
            result["families"][f]["rg_usage"] = rg_usage[f]

    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("out:", OUT)


if __name__ == "__main__":
    sys.exit(main())
