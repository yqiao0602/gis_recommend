#!/usr/bin/env python3
"""Per-format-class breakdown of P1@768 parsed rows on the 208 pairs."""
import json, re, statistics as st
from collections import Counter, defaultdict

PAIRS = "/home/qy/pairs_with_task_208.json"
P1 = "/home/qy/p0_fit_diag_768/paired_fit_diagnostic.json"


def parse_pred(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    return j if isinstance(j, dict) and "stages" in j else None


def classify(doc):
    for g in doc.get("repetition_groups", []):
        if isinstance(g, dict) and g.get("pattern"):
            return "newrep"
    if doc.get("repetition_groups"):
        return "oldrep_groups"
    if any(int(s.get("repeat", 1)) > 1 for s in doc["stages"]):
        return "stage_repeat"
    return "plain"


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


def seq_metrics(pred, gold):
    pc, gc = Counter(pred), Counter(gold)
    tp = sum((pc & gc).values())
    np_, ng = len(pred), len(gold)
    bag = (2 * tp / (np_ + ng)) if (np_ + ng) and tp else 0.0
    if not pred or not gold:
        lf1 = 0.0
    else:
        prev = [0] * (len(gold) + 1)
        for i in range(1, len(pred) + 1):
            cur = [0] * (len(gold) + 1)
            ai = pred[i - 1]
            for j in range(1, len(gold) + 1):
                cur[j] = prev[j - 1] + 1 if ai == gold[j - 1] else max(prev[j], cur[j - 1])
            prev = cur
        L = prev[-1]
        lp, lr = L / len(pred), L / len(gold)
        lf1 = 2 * lp * lr / (lp + lr) if lp + lr else 0.0
    return bag, lf1


pairs = json.load(open(PAIRS, encoding="utf-8"))["rows"]
rows = json.load(open(P1, encoding="utf-8"))["rows"]

by_fmt = defaultdict(lambda: defaultdict(list))
for i, r in enumerate(rows):
    doc = parse_pred(r["pred_text"])
    if doc is None:
        continue
    f = classify(doc)
    try:
        pred = expand(doc)
    except Exception:
        continue
    go = expand(pairs[i]["old_target_json"])
    gn = expand(pairs[i]["new_target_json"])
    bag_o, lcs_o = seq_metrics(pred, go)
    bag_n, lcs_n = seq_metrics(pred, gn)
    by_fmt[f]["n"].append(1)
    by_fmt[f]["bag_vs_old"].append(bag_o)
    by_fmt[f]["lcs_vs_old"].append(lcs_o)
    by_fmt[f]["bag_vs_new"].append(bag_n)
    by_fmt[f]["lcs_vs_new"].append(lcs_n)

out = {}
for f, d in by_fmt.items():
    out[f] = {"n": sum(d["n"]),
              "bag_vs_old": round(st.mean(d["bag_vs_old"]), 4),
              "lcs_vs_old": round(st.mean(d["lcs_vs_old"]), 4),
              "bag_vs_new": round(st.mean(d["bag_vs_new"]), 4),
              "lcs_vs_new": round(st.mean(d["lcs_vs_new"]), 4)}
print(json.dumps(out, indent=1))
