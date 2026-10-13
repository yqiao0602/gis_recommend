#!/usr/bin/env python3
"""P0 planning-quality error taxonomy on dev-1852 parsed rows (Layer-1 view).

Separates workflow-planning quality from parse reliability: conditional on
the blueprint parsing, classify each row's error type:
  perfect            - exact expanded family sequence match
  order_only         - same family multiset, sequence differs (pure ordering)
  count_error_only   - all families present, some count off, order otherwise ok
  missing_only       - under-emission without extra emission
  extra_only         - over-emission without missing
  missing+extra      - both
  order+count mix    - multiset equal broken AND order broken etc.
Aggregated shares + stratified by gold length. This is the Layer-1 (planning)
baseline that grounding (Layer-2) will inherit."""
import json, re
from collections import Counter

DEV = "/home/qy/planner_v2_dev.jsonl"
PREDS = "/home/qy/p0_fmt_dev_preds_rec.json"


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
    pg = {int(g["anchor_seq"]): g for g in doc.get("repetition_groups", [])
          if isinstance(g, dict) and g.get("pattern")}
    out, i = [], 0
    while i < len(stages):
        s = stages[i]
        if (i + 1) in pg:
            g = pg[i + 1]
            pat = g.get("pattern") or [s["family"]]
            n = int(g.get("repeat_count", 1))
            out += pat * n
            i += len(pat)
        else:
            out += [s["family"]] * int(s.get("repeat", 1))
            i += 1
    return out


def lcs_len(a, b):
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


dev = [json.loads(l) for l in open(DEV, encoding="utf-8")]
preds = json.load(open(PREDS, encoding="utf-8"))["items"]

tax = Counter()
tax_by_len = {}
prec_sum = rec_sum = 0.0
n_parsed = n_total = 0
order_only_short = 0
for dv, it in zip(dev, preds):
    gj = json.loads(dv["target"])
    gold = []
    for s in gj["stages"]:
        gold += [s["family"]] * int(s.get("repeat", 1))
    n_total += 1
    doc = parse_pred(it["pred_text"])
    if doc is None:
        continue
    n_parsed += 1
    pred = expand(doc)
    gc, pc = Counter(gold), Counter(pred)
    glen = len(gold)
    b = "0-10" if glen <= 10 else ("11-30" if glen <= 30 else "31+")
    tax_by_len.setdefault(b, Counter())
    tp = sum((pc & gc).values())
    prec_sum += tp / len(pred) if pred else 0.0
    rec_sum += tp / len(gold) if gold else 0.0
    if pred == gold:
        tax["perfect"] += 1
        tax_by_len[b]["perfect"] += 1
        continue
    over = sum(max(0, pc[f] - gc[f]) for f in pc)
    under = sum(max(0, gc[f] - pc[f]) for f in gc)
    same_multiset = over == 0 and under == 0
    L = lcs_len(pred, gold)
    order_ok = (L == len(pred) == len(gold))
    counts_ok = same_multiset
    if same_multiset and order_ok:
        tax["identical_count_order_but_not_exact"] += 1  # defensive, unlikely
    elif same_multiset:
        tax["order_error_only"] += 1
        tax_by_len[b]["order_error_only"] += 1
        if glen <= 10:
            order_only_short += 1
    elif order_ok:
        tax["count_error_only"] += 1
        tax_by_len[b]["count_error_only"] += 1
    elif over == 0:
        tax["missing_only_plus_order"] += 1
        tax_by_len[b]["missing_only_plus_order"] += 1
    elif under == 0:
        tax["extra_only_plus_order"] += 1
        tax_by_len[b]["extra_only_plus_order"] += 1
    else:
        tax["missing_and_extra_mixed"] += 1
        tax_by_len[b]["missing_and_extra_mixed"] += 1

out = {"n_total": n_total, "n_parsed": n_parsed,
       "family_precision_mean": round(prec_sum / n_parsed, 4),
       "family_recall_mean": round(rec_sum / n_parsed, 4),
       "taxonomy_parsed": {k: v for k, v in tax.most_common()},
       "taxonomy_share": {k: round(v / n_parsed, 4) for k, v in tax.most_common()},
       "by_gold_len": {b: dict(c) for b, c in sorted(tax_by_len.items())}}
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open("/home/qy/p0_error_taxonomy_v1.json", "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)
