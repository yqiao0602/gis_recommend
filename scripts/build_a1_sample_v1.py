#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 decode-contrast frozen sample (owner directive 2026-10-12).

Strata over the trusted subset (1,276), deterministic seed 20261012:
  T2 truncated_long      hit_max & >25 gold stages        (all 36)
  T1 truncated_shortmid  hit_max & <=25                   (30 of 205)
  NT_long                parsed & >25                     (15 of 32)
  NT_band_select         parsed & BAND_SELECT gold & <=25 (20)
  NT_geom_terrain        parsed & GEOMETRY/TERRAIN & <=25 (15)
  NT_control_short       parsed & <=25 & no special       (15)
Total 131. Baseline = p0b_768 (max_new_tokens=768, greedy). Experiment arm
preregistered: max_new_tokens=2048, ALL else identical.
"""

import json
import os
import random
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")

WEAK = {"BAND_SELECT", "GEOMETRY_DEFINE", "TERRAIN_DERIVED"}


def main():
    dual = json.load(open(os.path.join(PD, "DUAL_TRACK_EVAL_V1.json"),
                          encoding="utf-8"))
    excl = {int(k) for k in dual["exclusions"]["rows"]}
    sub = [i for i in range(1852) if i not in excl]

    rows = []
    with open(os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl"),
              encoding="utf-8") as f:
        for i, line in enumerate(f):
            if line.strip():
                r = json.loads(line)
                t = r["target"]
                if isinstance(t, str):
                    t = json.loads(t)
                rows.append({"task": r["task"], "tgt": t})
    items = json.load(open(os.path.join(PD, "p0b_768", "predictions.json"),
                           encoding="utf-8"))["items"]

    def gold_fams(i):
        return set(s["family"] for s in rows[i]["tgt"]["stages"])

    def n_stages(i):
        return len(rows[i]["tgt"]["stages"])

    def parse_ok(i):
        try:
            o = json.loads(items[i].get("pred_text") or "")
            return isinstance(o, dict) and o.get("stages")
        except Exception:
            return False

    strata = {"T2_truncated_long": [], "T1_truncated_shortmid": [],
              "NT_long": [], "NT_band_select": [], "NT_geom_terrain": [],
              "NT_control_short": []}
    for i in sub:
        hm = bool(items[i].get("hit_max_new_tokens"))
        st = n_stages(i)
        if hm and st > 25:
            strata["T2_truncated_long"].append(i)
        elif hm:
            strata["T1_truncated_shortmid"].append(i)
        elif st > 25:
            strata["NT_long"].append(i)
        elif "BAND_SELECT" in gold_fams(i):
            strata["NT_band_select"].append(i)
        elif gold_fams(i) & (WEAK - {"BAND_SELECT"}):
            strata["NT_geom_terrain"].append(i)
        else:
            strata["NT_control_short"].append(i)

    rng = random.Random(20261012)
    take = {"T2_truncated_long": 36, "T1_truncated_shortmid": 30,
            "NT_long": 15, "NT_band_select": 20, "NT_geom_terrain": 15,
            "NT_control_short": 15}
    sample = []
    account = {}
    for name in strata:
        pool = sorted(strata[name])
        rng.shuffle(pool)
        k = min(take[name], len(pool))
        chosen = pool[:k]
        account[name] = {"population": len(pool), "sample_n": k}
        for i in chosen:
            sample.append({
                "idx": i, "stratum": name,
                "task_head": (rows[i]["task"] or "").splitlines()[0][:90],
                "gold_n_stages": n_stages(i),
                "gold_fams": sorted(gold_fams(i)),
                "baseline_hit_max": bool(items[i].get("hit_max_new_tokens")),
            })

    out = {
        "schema": "A1_decode_contrast_sample_v1",
        "frozen_at": "2026-10-12",
        "baseline_config": {"max_new_tokens": 768, "do_sample": False,
                            "source": "p0b_768/predictions.json header"},
        "experiment_arm_preregistered": {
            "max_new_tokens": 2048,
            "justification": ("trusted gold target tokens est p99~1232 "
                              "(chars/3); 2048 covers p99 with margin; "
                              "71k-char giant row (needs ~23.7k tokens) is "
                              "a registered known exception"),
            "everything_else": "IDENTICAL to baseline (weights, prompt, "
                               "input order, greedy sampling, parser, gold)",
        },
        "strata_account": account,
        "n": len(sample),
        "samples": sample,
    }
    json.dump(out, open(os.path.join(PD, "A1_SAMPLE_131.json"), "w",
                        encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps({"n": len(sample), "strata": account}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
