#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-B2 arm evaluation: unified 7-metric eval on a predictions.json.

Same metric definitions as unified_eval_step12_v1.py (owner's 7 metrics on
expanded sequences), parameterized for the P0-B2 arms. Parse-inclusive AND
parse-exclusive bag-F1 are both reported (P0-A showed 15.77% truncation
failures at 384 tokens).

Usage:
  python eval_p0b2_arm_v1.py --pred <predictions.json> \
      --dev <planner_v2_dev.jsonl> --out <eval_metrics.json> [--tag A]
"""

import argparse
import json
import re
import statistics as st
from collections import Counter

ap = argparse.ArgumentParser()
ap.add_argument('--pred', required=True)
ap.add_argument('--dev', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--tag', default='A')
a = ap.parse_args()


def expand_v2(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y
                       else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


assert lcs_len(["A", "B", "C"], ["A", "B", "C"]) == 3
assert lcs_len(["A", "B"], ["B", "A"]) == 1


def metrics(pred_seq, gold_seq):
    pc, gc = Counter(pred_seq), Counter(gold_seq)
    tp = sum(min(pc[f], gc[f]) for f in pc)
    np_, ng = len(pred_seq), len(gold_seq)
    bag = 0.0 if np_ + ng == 0 else (2 * tp / (np_ + ng) if tp else 0.0)
    over = sum(max(0, pc[f] - gc[f]) for f in pc)
    under = sum(max(0, gc[f] - pc[f]) for f in gc)
    prec = tp / np_ if np_ else 0.0
    rec = tp / ng if ng else 0.0
    L = lcs_len(pred_seq, gold_seq)
    p = L / np_ if np_ else 0.0
    r = L / ng if ng else 0.0
    lcs = 2 * p * r / (p + r) if p + r else 0.0
    return {"bag_f1": round(bag, 4), "family_precision": round(prec, 4),
            "family_recall": round(rec, 4), "count_exact":
                all(pc.get(f, 0) == gc.get(f, 0) for f in set(pc) | set(gc)),
            "over_emission": over, "under_emission": under,
            "lcs_f1": round(lcs, 4), "exact_seq": int(pred_seq == gold_seq),
            "pred_len": np_, "gold_len": ng}


# ---- load ----
pred = json.load(open(a.pred, encoding="utf-8"))
items = pred["items"]
dev = [json.loads(l) for l in open(a.dev, encoding="utf-8") if l.strip()]
assert len(items) == len(dev), f"row misalignment {len(items)} vs {len(dev)}"

rows = []
parse_ok = 0
for it, dv in zip(items, dev):
    k = it["k"]
    text = it.get("pred_text") or ""
    # gold target: blueprint with stages
    tgt_raw = dv.get("target") or dv.get("blueprint") or dv.get("output")
    gold_seq = []
    parse_note = ""
    if isinstance(tgt_raw, str):
        try:
            tgt_raw = json.loads(tgt_raw)
        except Exception:
            parse_note = "gold-unparseable"
    if isinstance(tgt_raw, dict):
        gold_seq = expand_v2(tgt_raw.get("stages", []))
    # parse prediction
    pseq = None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "stages" in obj:
            pseq = expand_v2(obj["stages"])
    except Exception:
        pseq = None
    if pseq is not None:
        parse_ok += 1
        m = metrics(pseq, gold_seq)
        m["parsed"] = True
    else:
        m = metrics([], gold_seq)  # parse-inclusive: empty prediction
        m["parsed"] = False
    m["k"] = k
    m["cap_hit"] = it.get("hit_max_new_tokens", 0)
    m["generated_tokens"] = it.get("generated_tokens")
    m["gold_note"] = parse_note
    rows.append(m)

n = len(rows)
parsed_rows = [r for r in rows if r["parsed"]]


def avg(rs, key):
    vals = [r[key] for r in rs if isinstance(r[key], (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


def rate(rs, key):
    return round(sum(1 for r in rs if r[key]) / len(rs), 4) if rs else None


summary = {
    "tag": a.tag,
    "pred_file": a.pred,
    "dev_file": a.dev,
    "rows": n,
    "parse_rate": round(parse_ok / n, 4),
    "cap_hit_rate": rate(rows, "cap_hit"),
    "gen_len_mean": round(st.mean([r["generated_tokens"] for r in rows
                                   if r["generated_tokens"] is not None]), 1),
    "bag_f1_inclusive": avg(rows, "bag_f1"),
    "lcs_f1_inclusive": avg(rows, "lcs_f1"),
    "count_exact_inclusive": rate(rows, "count_exact"),
    "exact_seq_inclusive": rate(rows, "exact_seq"),
    "bag_f1_exclusive": avg(parsed_rows, "bag_f1"),
    "lcs_f1_exclusive": avg(parsed_rows, "lcs_f1"),
    "family_precision_exclusive": avg(parsed_rows, "family_precision"),
    "family_recall_exclusive": avg(parsed_rows, "family_recall"),
    "over_emission_mean_inclusive": avg(rows, "over_emission"),
    "under_emission_mean_inclusive": avg(rows, "under_emission"),
    "under_emission_total": sum(r["under_emission"] for r in rows),
    "over_emission_total": sum(r["over_emission"] for r in rows),
}

out = {"summary": summary, "per_row": rows}
json.dump(out, open(a.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(json.dumps(summary, indent=2, ensure_ascii=False))
