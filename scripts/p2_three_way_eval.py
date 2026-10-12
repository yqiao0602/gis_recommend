#!/usr/bin/env python3
"""Three-way eval: P0 vs P1 vs P2 on frozen dev-1852, unified semantic layer.

All systems' predictions are parsed with ONE parser, expanded with ONE
expander (handles old-format declarations and new-format pattern groups),
and compared against the same expanded gold. Owner reporting list:
parse rate, hit-cap, Ordered LCS-F1 incl failures, repeat structure & count
fidelity, output length distribution, itemized P0/P1/P2 deltas.

Repeat fidelity metrics (format-agnostic, computed on expanded sequences):
  count_fidelity   - over families with gold count>=2: exact count match rate
  count_abs_err    - mean |pred-gold| over those families
  run_profile_match- maximal-run length multiset (runs>=2) equals gold's
"""
import json, re, statistics as st
from collections import Counter, defaultdict

DEV = "/home/qy/planner_v2_dev.jsonl"
SYSTEMS = {
    "P0": "/home/qy/p0_fmt_dev_preds_rec.json",
    "P1": "/home/qy/p1_dev_full_preds_rec.json",
    "P2": "/home/qy/p2_dev_full_preds.json",
}
OUT = "/home/qy/p2_three_way_eval.json"


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
    pat_groups = {int(g["anchor_seq"]): g for g in
                  doc.get("repetition_groups", [])
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


def repeat_fidelity(pred, gold):
    """Per-row repeat structure & count fidelity (expanded sequences)."""
    gc, pc = Counter(gold), Counter(pred)
    rep_fams = [f for f, c in gc.items() if c >= 2]
    if not rep_fams:
        return None  # row has no repeats; excluded from repeat metrics
    exact = sum(int(pc.get(f, 0) == gc[f]) for f in rep_fams)
    abs_err = sum(abs(pc.get(f, 0) - gc[f]) for f in rep_fams)

    def runs(seq):
        out, i = [], 0
        while i < len(seq):
            j = i
            while j + 1 < len(seq) and seq[j + 1] == seq[i]:
                j += 1
            if j - i + 1 >= 2:
                out.append(j - i + 1)
            i = j + 1
        return sorted(out)

    profile = int(runs(pred) == runs(gold))
    return {"n_fams": len(rep_fams), "exact": exact, "abs_err": abs_err,
            "profile_match": profile}


BINS = [(0, 10), (11, 30), (31, 80), (81, 10 ** 9)]


def bin_of(g):
    for lo, hi in BINS:
        if lo <= g <= hi:
            return f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"


def q(vals, p):
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(p * (len(s) - 1)))], 1) if s else None


def eval_system(path, golds, glens):
    d = json.load(open(path, encoding="utf-8"))
    items = d["items"]
    has_rec = "gen_tokens" in items[0]
    n = len(items)
    agg = defaultdict(list)
    agg_incl = defaultdict(list)
    fmt = Counter()
    strata = defaultdict(lambda: {"n": 0, "ok": 0})
    rep = {"n_fams": 0, "exact": 0, "abs_err": 0.0, "profile": 0, "rows": 0}
    rep_incl_rows = 0
    gt, hc = [], 0
    for i, it in enumerate(items):
        g_len = glens[i]
        strata[bin_of(g_len)]["n"] += 1
        if has_rec:
            gt.append(it["gen_tokens"])
            hc += int(it["hit_cap"])
        doc = parse_pred(it["pred_text"])
        gold = golds[i]
        if doc is None:
            fmt["unparsed"] += 1
            for k in ("bag_f1", "ordered_lcs_f1"):
                agg_incl[k].append(0.0)
            agg_incl["count_fid_incl"].append(0.0)
            rep_incl_rows += int(bool([f for f, c in Counter(gold).items() if c >= 2]))
            strata[bin_of(g_len)]  # already counted
            continue
        strata[bin_of(g_len)]["ok"] += 1
        fmt[classify(doc)] += 1
        try:
            pred = expand(doc)
        except Exception:
            fmt["unparsed"] += 1
            fmt[classify(doc)] -= 1
            for k in ("bag_f1", "ordered_lcs_f1"):
                agg_incl[k].append(0.0)
            agg_incl["count_fid_incl"].append(0.0)
            continue
        m = seq_metrics(pred, gold)
        for k, v in m.items():
            agg[k].append(v)
            agg_incl[k].append(v)
        rf = repeat_fidelity(pred, gold)
        if rf:
            rep["rows"] += 1
            rep["n_fams"] += rf["n_fams"]
            rep["exact"] += rf["exact"]
            rep["abs_err"] += rf["abs_err"]
            rep["profile"] += rf["profile_match"]
            agg["count_fid"].append(rf["exact"] / rf["n_fams"])
            agg_incl["count_fid_incl"].append(rf["exact"] / rf["n_fams"])
        else:
            agg["count_fid"].append(1.0)  # no-repeat row: trivially faithful
            agg_incl["count_fid_incl"].append(1.0)
        rep_incl_rows += 0

    n_parsed = sum(v for k, v in fmt.items() if k != "unparsed")
    s = {"n": n, "parse_rate": round(n_parsed / n, 4), "fmt": dict(fmt)}
    for k in ("bag_f1", "ordered_lcs_f1", "family_precision", "family_recall"):
        s[k] = round(st.mean(agg[k]), 4) if agg.get(k) else None
        s[k + "_incl"] = round(st.mean(agg_incl[k]), 4) if agg_incl.get(k) else None
    s["over_emission_mean"] = round(st.mean(agg["over_emission"]), 2) if agg.get("over_emission") else None
    s["under_emission_mean"] = round(st.mean(agg["under_emission"]), 2) if agg.get("under_emission") else None
    s["count_fidelity"] = round(st.mean(agg["count_fid"]), 4) if agg.get("count_fid") else None
    s["count_fidelity_incl"] = round(st.mean(agg_incl["count_fid_incl"]), 4)
    if rep["rows"]:
        s["repeat_struct_profile_match"] = round(rep["profile"] / rep["rows"], 4)
        s["repeat_count_exact_rate"] = round(rep["exact"] / rep["n_fams"], 4)
        s["repeat_count_abs_err_mean"] = round(rep["abs_err"] / rep["n_fams"], 3)
    s["strata_parse"] = {b: round(v["ok"] / v["n"], 4) if v["n"] else None
                         for b, v in sorted(strata.items(),
                                            key=lambda x: BINS.index(
                                                next(t for t in BINS
                                                     if x[0].startswith(str(t[0])))))}
    if has_rec:
        s["hit_cap"] = hc
        s["hit_cap_rate"] = round(hc / n, 4)
        s["gen_tokens_p50_p90_max_mean"] = [q(gt, .5), q(gt, .9), max(gt),
                                            round(st.mean(gt), 1)]
    else:
        s["hit_cap"] = "not_recorded_in_historical_file"
        s["gen_tokens_p50_p90_max_mean"] = None
    return s


def main():
    dev = [json.loads(l) for l in open(DEV, encoding="utf-8")]
    golds, glens = [], []
    for dv in dev:
        gj = json.loads(dv["target"]) if isinstance(dv["target"], str) else dv["target"]
        g = expand(gj)
        golds.append(g)
        glens.append(len(g))
    out = {}
    for name, path in SYSTEMS.items():
        try:
            out[name] = eval_system(path, golds, glens)
        except FileNotFoundError:
            out[name] = "missing: " + path
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # console comparison
    keys = ["parse_rate", "hit_cap_rate", "bag_f1", "bag_f1_incl",
            "ordered_lcs_f1", "ordered_lcs_f1_incl", "count_fidelity",
            "count_fidelity_incl", "repeat_struct_profile_match",
            "repeat_count_exact_rate", "under_emission_mean",
            "over_emission_mean"]
    hdr = f"{'metric':34s} " + " ".join(f"{k:>10s}" for k in SYSTEMS)
    print(hdr)
    print("-" * len(hdr))
    for k in keys:
        row = f"{k:34s} "
        for s in SYSTEMS:
            v = out.get(s, {})
            val = v.get(k) if isinstance(v, dict) else None
            row += f"{str(val):>10s} "
        print(row)
    for s in SYSTEMS:
        v = out.get(s, {})
        if isinstance(v, dict):
            print(f"{s} gen_tokens p50/p90/max/mean: "
                  f"{v.get('gen_tokens_p50_p90_max_mean')}")
            print(f"{s} strata parse: {v.get('strata_parse')}")
            print(f"{s} fmt: {v.get('fmt')}")
    print("saved:", OUT)


if __name__ == "__main__":
    main()
