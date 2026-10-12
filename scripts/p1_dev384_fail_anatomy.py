#!/usr/bin/env python3
"""Anatomy of P1@384 parse failures on dev-1852: parse rate by gold length
stratum. If failures concentrate in long-gold rows -> budget truncation;
if uniform -> format/selection failure. CPU only."""
import json, re, statistics as st
from collections import Counter, defaultdict

DEV = "/home/qy/planner_v2_dev.jsonl"
PREDS = "/home/qy/p1_dev_full_preds.json"


def parse_pred(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    return j if isinstance(j, dict) and "stages" in j else None


def expand(doc):
    stages = doc["stages"]
    pat_groups = {int(g["anchor_seq"]): g for g in doc.get("repetition_groups", [])
                  if isinstance(g, dict) and g.get("pattern")}
    out, i = [], 0
    while i < len(stages):
        s = stages[i]
        if (i + 1) in pat_groups:
            g = pat_groups[i + 1]
            pat = g.get("pattern") or [s["family"]]
            n = int(g.get("repeat_count", 1))
            for _ in range(n):
                out += list(pat)
            i += len(pat)
        else:
            out += [s["family"]] * int(s.get("repeat", 1))
            i += 1
    return out


def classify(doc):
    for g in doc.get("repetition_groups", []):
        if isinstance(g, dict) and g.get("pattern"):
            return "newrep"
    if doc.get("repetition_groups"):
        return "oldrep_groups"
    if any(int(s.get("repeat", 1)) > 1 for s in doc["stages"]):
        return "stage_repeat"
    return "plain"


dev = [json.loads(l) for l in open(DEV, encoding="utf-8")]
preds = json.load(open(PREDS, encoding="utf-8"))["items"]
assert len(dev) == len(preds), (len(dev), len(preds))

BINS = [(0, 10), (11, 30), (31, 80), (81, 10**9)]
strata = defaultdict(lambda: {"n": 0, "ok": 0, "fmt": Counter(),
                              "fail_len_p50": []})
fail_texts = []
for i, (dv, it) in enumerate(zip(dev, preds)):
    gold_j = json.loads(dv["target"]) if isinstance(dv["target"], str) else dv["target"]
    try:
        gold = expand(gold_j)
    except Exception:
        gold = []
    g = len(gold)
    b = next((f"{lo}-{hi}" if hi < 10**9 else f"{lo}+" for lo, hi in BINS if lo <= g <= hi))
    s = strata[b]
    s["n"] += 1
    doc = parse_pred(it["pred_text"])
    if doc is None:
        s["fail_len_p50"].append(len(it["pred_text"]))
        fail_texts.append((i, g, len(it["pred_text"]), it["pred_text"][:120]))
        continue
    s["ok"] += 1
    try:
        s["fmt"][classify(doc)] += 1
    except Exception:
        pass

out = {}
for b in sorted(strata, key=lambda x: BINS.index(next(t for t in BINS if x.startswith(str(t[0]))))):
    s = strata[b]
    fl = sorted(s["fail_len_p50"])
    out[b] = {"n": s["n"], "parse_rate": round(s["ok"] / s["n"], 4),
              "fmt": dict(s["fmt"]),
              "fail_text_len_p50": fl[len(fl) // 2] if fl else None}

print(json.dumps(out, indent=1))
print("--- 3 sample failures (idx, gold_ops, text_len, head) ---")
for t in fail_texts[:3]:
    print(t)
