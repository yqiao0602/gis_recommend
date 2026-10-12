#!/usr/bin/env python3
"""P1@768 vs P0@384 paired eval on the SAME 208 rows (unified semantic layer).

Both prediction sets are expanded via ONE expander that handles old-format
repetition_groups (stage_seq/family/repeat declarations, literal stages) and
new-format pattern groups (anchor_seq/pattern/repeat_count), then compared to
the old-representation gold AND the new-representation gold separately.
No raw JSON string comparison (frozen plan rule).
"""
import json, re, statistics as st
from collections import Counter

PAIRS = "/home/qy/pairs_with_task_208.json"
P1 = "/home/qy/p0_fit_diag_768/paired_fit_diagnostic.json"
P0 = "/home/qy/p0_fit_diag/paired_fit_diagnostic.json"
TRAIN = "/home/qy/p1_sft_train_v1.jsonl"
OUT = "/home/qy/p1_768_pair_eval.json"

SCRIPT_SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."


def parse_pred(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(j, dict) or "stages" not in j:
        return None
    return j


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
    ps, gs = set(pred), set(gold)
    fp = len(ps & gs) / len(ps) if ps else 0.0
    fr = len(ps & gs) / len(gs) if gs else 0.0
    over = sum(max(0, pc.get(f, 0) - gc.get(f, 0)) for f in set(pc) | set(gc))
    under = sum(max(0, gc.get(f, 0) - pc.get(f, 0)) for f in set(pc) | set(gc))
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
    return {"bag_f1": bag, "family_precision": fp, "family_recall": fr,
            "over_emission": over, "under_emission": under,
            "ordered_lcs_f1": lf1, "exact_sequence": int(pred == gold)}


pairs = json.load(open(PAIRS, encoding="utf-8"))["rows"]

# SEP consistency check: does the diagnostic prompt equal the P1 training SEP?
sep_match, sep_n = 0, 0
for line in open(TRAIN, encoding="utf-8"):
    r = json.loads(line)
    sep_n += 1
    sep_match += int(r.get("separator") == SCRIPT_SEP)

def eval_pred_file(path):
    d = json.load(open(path, encoding="utf-8"))
    rows = d["rows"]
    agg_excl, agg_incl = {}, {}
    fmt = Counter()
    per_row = []
    n_parse = 0
    for i, r in enumerate(rows):
        gold_old = expand(pairs[i]["old_target_json"])
        gold_new = expand(pairs[i]["new_target_json"])
        doc = parse_pred(r["pred_text"])
        rec = {"i": i, "hit_cap": r["hit_cap"], "gen_tokens": r["gen_tokens"]}
        if doc is None:
            fmt["unparsed"] += 1
            rec.update(parsed=False, fmt="unparsed")
            for k in ("bag_f1", "ordered_lcs_f1"):
                agg_incl.setdefault(k, []).append(0.0)
            per_row.append(rec)
            continue
        n_parse += 1
        f = classify(doc)
        fmt[f] += 1
        rec.update(parsed=True, fmt=f)
        try:
            pred = expand(doc)
            m_old = seq_metrics(pred, gold_old)
            m_new = seq_metrics(pred, gold_new)
        except Exception:
            rec.update(parsed=False, fmt="expand_error")
            fmt["unparsed"] += 1
            fmt[f] -= 1
            for k in ("bag_f1", "ordered_lcs_f1"):
                agg_incl.setdefault(k, []).append(0.0)
            per_row.append(rec)
            continue
        for k, v in m_old.items():
            agg_excl.setdefault(k, []).append(v)
            agg_incl.setdefault(k, []).append(v)
        rec["bag_vs_old"] = m_old["bag_f1"]
        rec["lcs_vs_old"] = m_old["ordered_lcs_f1"]
        per_row.append(rec)
    n = len(rows)
    s = {"n": n, "parse_rate": round(n_parse / n, 4), "fmt": dict(fmt)}
    for k in ("bag_f1", "ordered_lcs_f1", "family_precision", "family_recall"):
        s[k + "_excl"] = round(st.mean(agg_excl[k]), 4) if agg_excl.get(k) else None
        s[k + "_incl"] = round(st.mean(agg_incl.get(k, [0.0])), 4)
    s["under_emission_mean_excl"] = round(st.mean(agg_excl["under_emission"]), 2) if agg_excl.get("under_emission") else None
    s["over_emission_mean_excl"] = round(st.mean(agg_excl["over_emission"]), 2) if agg_excl.get("over_emission") else None
    s["hit_cap"] = sum(r["hit_cap"] for r in rows)
    return s, per_row


s1, rows1 = eval_pred_file(P1)
out = {"p1_768": s1, "sep_match": f"{sep_match}/{sep_n}"}
try:
    s0, rows0 = eval_pred_file(P0)
    out["p0_384"] = s0
except FileNotFoundError:
    out["p0_384"] = "missing: " + P0

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
