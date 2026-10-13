#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-Experiment-A verification bundle (owner ruling 2026-10-11):
  1. Spearman correction: prevalence vs recall / FP-rate over 7 families.
  2. Experiment B: frequency-only presence baselines vs model (per family).
  3. Experiment C first pass: BAND_SELECT / ITERATIVE_APPLY FN rows classified
     by gold-downstream-consistency proxy + task-keyword proxy.
"""

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))  # system_redesign/scripts
REPO = os.path.join(HERE, "..")
P0B = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                   "plan_pipeline_v1", "planner_design", "p0b_768")
A2R = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                   "plan_pipeline_v1", "planner_design")

FAMILIES = ["BAND_SELECT", "TEMPORAL_FILTER", "SPATIAL_FILTER",
            "ATTRIBUTE_FILTER", "RASTER_LOAD", "AGGREGATION",
            "ITERATIVE_APPLY"]


def expand(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                rk[order[t]] = avg
            i = j + 1
        return rk
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = (sum((a - mx) ** 2 for a in rx)) ** 0.5
    dy = (sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / (dx * dy), 4) if dx and dy else None


def bootstrap_spearman(xs, ys, n_boot=5000, seed=7):
    import random
    rng = random.Random(seed)
    vals = []
    n = len(xs)
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(spearman([xs[i] for i in idx], [ys[i] for i in idx]))
    vals = sorted(v for v in vals if v is not None)
    return [round(vals[int(0.025 * len(vals))], 3),
            round(vals[int(0.975 * len(vals))], 3)]


def main():
    # ---------- load ----------
    pred = json.load(open(os.path.join(P0B, "predictions.json"), encoding="utf-8"))
    items = pred["items"]
    dev = [json.loads(l) for l in open(os.path.join(REPO, "..", "04_DIAG_WORK",
                                                     "planner_v2_dev.jsonl"),
                                       encoding="utf-8") if l.strip()]
    diag = json.load(open(os.path.join(A2R, "EXP_A_STAGE_SELECTION_DIAGNOSIS_V1.json"),
                          encoding="utf-8"))
    out = {}

    # ---------- 1. Spearman correction ----------
    fams = [f for f in FAMILIES]
    prev = [diag["families"][f]["gold_prevalence"] for f in fams]
    rec = [diag["families"][f]["recall_presence"] for f in fams]
    fpr = [diag["families"][f]["fp_rate_when_absent"] for f in fams]
    out["spearman_correction"] = {
        "n": 7,
        "prevalence_vs_recall": {
            "rho": spearman(prev, rec),
            "bootstrap_ci95": bootstrap_spearman(prev, rec)},
        "prevalence_vs_fp_rate": {
            "rho": spearman(prev, fpr),
            "bootstrap_ci95": bootstrap_spearman(prev, fpr)},
        "note": "n=7 families — preliminary association only, not a strong "
                "causal conclusion; wording corrected from 'monotonic' to "
                "'clear overall association with family-level exceptions'",
    }

    # ---------- 2. Experiment B: frequency-only baselines ----------
    # train-split presence prevalence per family (from planner train rows)
    train = [json.loads(l) for l in open(os.path.join(REPO, "..", "04_DIAG_WORK",
                                                       "planner_v2_train.jsonl"),
                                          encoding="utf-8") if l.strip()]
    n_tr = len(train)
    tr_prev = {}
    for f in FAMILIES:
        cnt = 0
        for r in train:
            tgt = r.get("target")
            if isinstance(tgt, str):
                try:
                    tgt = json.loads(tgt)
                except Exception:
                    tgt = None
            if isinstance(tgt, dict) and any(s.get("family") == f
                                             for s in tgt.get("stages", [])):
                cnt += 1
        tr_prev[f] = cnt / n_tr

    # model presence confusion (recompute quickly from predictions+dev)
    model_conf = {f: Counter() for f in FAMILIES}
    for it, dv in zip(items, dev):
        try:
            obj = json.loads(it.get("pred_text") or "")
            ok = isinstance(obj, dict) and "stages" in obj
        except Exception:
            ok = False
        if not ok:
            continue
        tgt = dv.get("target")
        if isinstance(tgt, str):
            try:
                tgt = json.loads(tgt)
            except Exception:
                continue
        g = set(s["family"] for s in tgt.get("stages", []))
        p = set(s["family"] for s in obj.get("stages", []))
        for f in FAMILIES:
            model_conf[f]["TP" if (f in g and f in p) else
                          "FN" if f in g else
                          "FP" if f in p else "TN"] += 1

    baselines = {}
    for f in FAMILIES:
        p = tr_prev[f]
        e = model_conf[f]
        # baseline 1 "majority": predict present iff train prevalence >= 0.5
        b1_pred = p >= 0.5
        # baseline 2 "prevalence-matched": expected confusion when predicting
        # present on a `p` fraction of rows at random (expected counts)
        n_rows = sum(e.values())
        b2 = {"expected_recall": round(min(1.0, p), 4),
              "expected_fp_rate": round(p, 4)}
        b1 = {"recall": round(1.0, 4) if b1_pred else 0.0,
              "fp_rate": round(1.0, 4) if b1_pred else 0.0}
        m_rec = e["TP"] / max(1, e["TP"] + e["FN"])
        m_fpr = e["FP"] / max(1, e["FP"] + e["TN"])
        baselines[f] = {
            "train_prevalence": round(p, 4),
            "model_recall_presence": round(m_rec, 4),
            "model_fp_rate": round(m_fpr, 4),
            "baseline_majority": b1,
            "baseline_prevalence_matched": b2,
            "model_minus_baseline_recall": round(m_rec - p, 4),
            "verdict": ("model conditions on task (recall above prevalence)"
                        if m_rec > p + 0.05 else
                        "model at/below frequency prior (no task conditioning "
                        "evidence for this family)" if m_rec < p - 0.05 else
                        "model close to frequency prior"),
        }
    out["experiment_b_frequency_baseline"] = {
        "train_rows": n_tr,
        "per_family": baselines,
        "reading": ("comparison of model presence recall vs train prevalence "
                    "per family; deltas near zero => frequency-only behavior "
                    "for that family"),
    }

    # ---------- 3. Experiment C first pass ----------
    # BAND_SELECT FN rows: gold-downstream-consistency proxy
    band_fn = []
    iter_fn = []
    for it, dv in zip(items, dev):
        try:
            obj = json.loads(it.get("pred_text") or "")
            ok = isinstance(obj, dict) and "stages" in obj
        except Exception:
            continue
        if not ok:
            continue
        tgt = dv.get("target")
        if isinstance(tgt, str):
            try:
                tgt = json.loads(tgt)
            except Exception:
                continue
        gs = tgt.get("stages", [])
        gf = [s["family"] for s in gs]
        pf = set(s["family"] for s in obj.get("stages", []))
        task_head = (dv.get("task") or "").splitlines()[0][:140]
        if "BAND_SELECT" in gf and "BAND_SELECT" not in pf:
            downstream = [f for f in gf if f in ("SPECTRAL_INDEX",
                                                 "BAND_ARITHMETIC")]
            band_fn.append({
                "k": it["k"], "task_head": task_head,
                "gold_downstream_consumers": downstream,
                "gold_consistency_proxy":
                    "consistent (downstream spectral/arithmetic consumers)"
                    if downstream else "isolated BAND_SELECT (gold consistency "
                                       "questionable — possible pipeline "
                                       "artifact)",
                "category_proxy":
                    "c_likely_real_error" if downstream else "a_or_b_needs_review",
            })
        if "ITERATIVE_APPLY" in gf and "ITERATIVE_APPLY" not in pf:
            kw = re.search(r"time.series|per.year|per.month|per.image|per.pixel|"
                           r"season|monthly|daily|each", dv.get("task") or "", re.I)
            iter_fn.append({
                "k": it["k"], "task_head": task_head,
                "task_iterative_keyword": bool(kw),
                "gold_neighbors": sorted(set(gf) - {"ITERATIVE_APPLY"})[:8],
                "category_proxy":
                    "c_likely_real_error" if kw else "a_or_b_needs_review",
            })

    band_cats = Counter(r["category_proxy"] for r in band_fn)
    iter_cats = Counter(r["category_proxy"] for r in iter_fn)
    out["experiment_c_first_pass"] = {
        "BAND_SELECT_FN": {
            "total": len(band_fn),
            "category_proxy_distribution": dict(band_cats),
            "interpretation": ("rows with downstream SPECTRAL_INDEX/"
                               "BAND_ARITHMETIC consumers => gold internally "
                               "consistent => model omission likely a real "
                               "selection error (category c). Isolated "
                               "BAND_SELECT => needs review (possible "
                               "pipeline artifact or alternative workflow)."),
            "examples": band_fn[:6],
        },
        "ITERATIVE_APPLY_FN": {
            "total": len(iter_fn),
            "category_proxy_distribution": dict(iter_cats),
            "examples": iter_fn[:6],
        },
        "status": "first-pass proxy classification; final three-way ruling "
                  "requires owner/annotator semantic review",
    }

    out_path = os.path.join(A2R, "EXP_A_VERIFICATION_BUNDLE_V1.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps({
        "spearman": out["spearman_correction"],
        "experiment_b": out["experiment_b_frequency_baseline"]["per_family"],
        "experiment_c_band": out["experiment_c_first_pass"]["BAND_SELECT_FN"]["category_proxy_distribution"],
        "experiment_c_iter": out["experiment_c_first_pass"]["ITERATIVE_APPLY_FN"]["category_proxy_distribution"],
        "out": out_path,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
