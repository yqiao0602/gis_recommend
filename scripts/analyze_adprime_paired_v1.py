#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A″ paired verdict per A_DPRIME_PREREGISTRATION v0.3 §5/§6/§7.

pre  = a1_pull/a1_arm768_raw.json.gz  (frozen same-host baseline, 52 runaway)
post = adprime post-training 768 arm (same host/stack/decode)

Five gate conditions (ALL must pass):
  G1 runaway paired improvement: b-c >= 26 AND exact McNemar one-sided p<0.05
  G2 short-task false-stop = 0 (C2-short 47); C3-long false-stop <= 2/32
     (false_stop = early_stop AND coverage_loss, per-row deterministic)
  G3 coverage no regression: bag-excl and category-level presence F1
     >= baseline - 0.01 (BAND_SELECT headline reported)
  G4 over-generation ratio median down (post < pre)
  G5 mean generated tokens increase <= 20%
"""
import gzip
import json
import math
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DW = os.path.join(HERE, "..", "..", "04_DIAG_WORK")
PULL = os.path.join(DW, "a1_pull")


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return {r["idx"]: r for r in json.load(f)["rows"]}


def stages_of(r):
    if not r["parse_ok"]:
        return None
    try:
        return json.loads(r["pred_text"])["stages"]
    except Exception:
        return None


def expand(st):
    out = []
    for s in st or []:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def bag_excl(pred_st, gold_st):
    p, g = expand(pred_st), expand(gold_st)
    if not p:
        return 0.0
    pc, gc = Counter(p), Counter(g)
    tp = sum(min(pc[k], gc[k]) for k in pc)
    return 2 * tp / (len(p) + len(g)) if (len(p) + len(g)) else 0.0


def mcnemar_exact_one_sided(b, c):
    """P(X >= b) under Binomial(b+c, 0.5), one-sided."""
    n = b + c
    if n == 0:
        return 1.0
    p = sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n
    return min(1.0, p)


def main(post_path):
    pre = load(os.path.join(PULL, "a1_arm768_raw.json.gz"))
    post = load(post_path)
    # gold lookup from pre rows (identical rows)
    gold = {i: json.loads(open(os.path.join(
        DW, "planner_v2_dev_fix1_loopinv.jsonl"),
        encoding="utf-8").read().splitlines()[i])["target"] for i in pre}
    gold = {i: (json.loads(v) if isinstance(v, str) else v)
            for i, v in gold.items()}

    res = {"schema": "adprime_paired_verdict_v1", "n": len(pre)}

    # ---- G1 runaway paired ----
    b = sum(1 for i in pre if pre[i]["termination"] == "MAX_TOKENS"
            and post[i]["termination"] != "MAX_TOKENS")
    c = sum(1 for i in pre if pre[i]["termination"] != "MAX_TOKENS"
            and post[i]["termination"] == "MAX_TOKENS")
    run_pre = sum(1 for r in pre.values() if r["termination"] == "MAX_TOKENS")
    run_post = sum(1 for r in post.values()
                   if r["termination"] == "MAX_TOKENS")
    p = mcnemar_exact_one_sided(b, c)
    res["G1_runaway"] = {"b_improved": b, "c_worsened": c, "net": b - c,
                         "runaway_pre": run_pre, "runaway_post": run_post,
                         "mcnemar_p": round(p, 6),
                         "pass": bool(b - c >= 26 and p < 0.05)}

    # ---- G2 false stops ----
    def false_stop(i):
        pr, po = pre[i], post[i]
        early = (po["termination"] != "MAX_TOKENS"
                 and (po["pred_n_stages"] or 0) < (pr["pred_n_stages"] or 0))
        if not early:
            return False, False
        bag_pre = bag_excl(stages_of(pr), gold[i]["stages"])
        bag_post = bag_excl(stages_of(po), gold[i]["stages"])
        cov_loss = bag_post < bag_pre - 0.01
        if not cov_loss:
            pf = set(s["family"] for s in (stages_of(pr) or []))
            po_f = set(s["family"] for s in (stages_of(po) or []))
            gf = set(s["family"] for s in gold[i]["stages"])
            if (pf & gf) - po_f:
                cov_loss = True
        return True, cov_loss

    s = json.load(open(os.path.join(
        PD := os.path.join(HERE, "..", "docs", "reports",
                           "route2_p0_contract", "plan_pipeline_v1",
                           "planner_design"), "A1_SAMPLE_131.json"),
        encoding="utf-8"))
    by_idx_stratum = {x["idx"]: x["stratum"] for x in s["samples"]}
    c2 = [i for i, r in pre.items()
          if r["termination"] == "EOS" and r["gold_n_stages"] <= 10]
    c3 = [i for i, r in pre.items()
          if r["termination"] == "EOS" and r["gold_n_stages"] > 10]
    fs_c2 = [i for i in c2 if all(false_stop(i))]
    fs_c2 = [i for i in c2 if false_stop(i)[0] and false_stop(i)[1]]
    fs_c3 = [i for i in c3 if false_stop(i)[0] and false_stop(i)[1]]
    res["G2_false_stop"] = {
        "C2_short": {"n": len(c2), "false_stops": len(fs_c2), "pass":
                     len(fs_c2) == 0},
        "C3_long": {"n": len(c3), "false_stops": len(fs_c3), "pass":
                    len(fs_c3) <= 2},
        "false_stop_rows": {"C2": fs_c2, "C3": fs_c3}}

    # ---- G3 coverage ----
    def family_f1(rows):
        tp = Counter()
        fp = Counter()
        fn = Counter()
        for i, r in rows.items():
            pf = set(s["family"] for s in (stages_of(r) or []))
            gf = set(s["family"] for s in gold[i]["stages"])
            for f in gf | pf:
                if f in gf and f in pf:
                    tp[f] += 1
                elif f in pf:
                    fp[f] += 1
                else:
                    fn[f] += 1
        out = {}
        for f in set(list(tp) + list(fp) + list(fn)):
            prec = tp[f] / (tp[f] + fp[f]) if (tp[f] + fp[f]) else 0
            rec = tp[f] / (tp[f] + fn[f]) if (tp[f] + fn[f]) else 0
            out[f] = round(2 * prec * rec / (prec + rec), 4) \
                if (prec + rec) else 0.0
        return out

    f1_pre = family_f1(pre)
    f1_post = family_f1(post)
    bag_pre = [bag_excl(stages_of(pre[i]), gold[i]["stages"]) for i in pre]
    bag_post = [bag_excl(stages_of(post[i]), gold[i]["stages"]) for i in post]
    bag_pre_m = sum(bag_pre) / len(bag_pre)
    bag_post_m = sum(bag_post) / len(bag_post)
    regressions = {f: (f1_pre.get(f, 0), f1_post.get(f, 0))
                   for f in f1_pre
                   if f1_post.get(f, 0) < f1_pre.get(f, 0) - 0.01}
    res["G3_coverage"] = {
        "bag_excl_mean_pre": round(bag_pre_m, 4),
        "bag_excl_mean_post": round(bag_post_m, 4),
        "band_select_f1_pre": f1_pre.get("BAND_SELECT"),
        "band_select_f1_post": f1_post.get("BAND_SELECT"),
        "family_regressions_gt_0.01": regressions,
        "pass": bool(bag_post_m >= bag_pre_m - 0.01 and not regressions)}

    # ---- G4 over-generation ratio median ----
    def ratios(rows):
        out = []
        for i, r in rows.items():
            st = stages_of(r)
            if st:
                out.append(len(st) / max(1, gold[i]["__n"] if False else
                                         len(gold[i]["stages"])))
        return sorted(out)

    for d in gold.values():
        d.setdefault("__n", len(d["stages"]))
    r_pre = ratios(pre)
    r_post = ratios(post)
    med_pre = r_pre[len(r_pre) // 2] if r_pre else 0
    med_post = r_post[len(r_post) // 2] if r_post else 0
    res["G4_overgen"] = {"median_ratio_pre": round(med_pre, 3),
                         "median_ratio_post": round(med_post, 3),
                         "pass": bool(med_post < med_pre)}

    # ---- G5 cost ----
    t_pre = sum(r["generated_tokens"] for r in pre.values()) / len(pre)
    t_post = sum(r["generated_tokens"] for r in post.values()) / len(post)
    res["G5_cost"] = {"mean_tokens_pre": round(t_pre, 1),
                      "mean_tokens_post": round(t_post, 1),
                      "increase_pct": round((t_post - t_pre) / t_pre * 100, 2),
                      "pass": bool(t_post <= t_pre * 1.2)}

    res["VERDICT"] = "PASS" if all(
        res[g]["pass"] for g in ("G1_runaway", "G2_false_stop",
                                 "G3_coverage", "G4_overgen",
                                 "G5_cost")) else "FAIL"
    out = os.path.join(PULL, "ADPRIME_PAIRED_VERDICT_V1.json")
    json.dump(res, open(out, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("saved:", out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
