#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trusted dev candidate set + dual-track evaluation (owner directive
2026-10-12: stop repeat audit, start dual-track eval data prep).

Views:
  E1 original gold x full dev      (existing baseline)
  E2 trusted gold  x full dev      (only the 2 evidence-backed fix1 rows differ)
  E3 trusted gold  x trusted subset
  E4 original gold x trusted subset (reference)

Trusted subset exclusions (each with reason, frozen evidence):
  binding_error_confirmed      B1 four full-DAG-verified groups, owner NOT ACCEPTED
  duplicate_dedup              same-task / near-same blueprint groups, keep first
  binding_error_suspect        diff-task shared blueprints, unverified (strict)
  ws2_suspicious               WS2 gold_status=suspicious rows incl. k=370/994
  audited_pending              49-sample rows + 25-case rows (preliminary rulings)
  alignment_partial            3 rows with unverifiable stage alignment

No revision beyond fix1 is authorized; trusted gold != "more correct by
intuition" (owner constraint). Coverage and exclusion impact are reported so
metric changes are attributable.
"""

import json
import os
import sys
import hashlib
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
DEV_ORIG = os.path.join(DW, "planner_v2_dev.jsonl")
DEV_TRUST = os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl")
PRED = os.path.join(PD, "p0b_768", "predictions.json")


def bp_hash(t):
    return hashlib.sha256(json.dumps(t, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def load_dev(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r["target"]
                if isinstance(t, str):
                    t = json.loads(t)
                rows.append({"task": r["task"], "tgt": t})
    return rows


def expand(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def parse_pred(text):
    try:
        obj = json.loads(text or "")
        if isinstance(obj, dict) and isinstance(obj.get("stages"), list) \
                and obj["stages"]:
            return expand(obj["stages"])
    except Exception:
        pass
    return None


def eval_view(rows, preds, golds):
    n = len(rows)
    parse_ok = 0
    bag_f1s = []
    lcs_f1s = []
    fam_tp = Counter()
    fam_fp = Counter()
    fam_fn = Counter()
    per_row = []
    for i, r in enumerate(rows):
        gold_fams = set(s["family"] for s in r["tgt"]["stages"])
        gold_seq = expand(r["tgt"]["stages"])
        pseq = parse_pred(preds[i].get("pred_text") or "")
        if pseq is not None:
            parse_ok += 1
        pfams = set(pseq) if pseq is not None else set()
        for f in gold_fams | pfams:
            if f in gold_fams and f in pfams:
                fam_tp[f] += 1
            elif f in pfams:
                fam_fp[f] += 1
            else:
                fam_fn[f] += 1
        if pseq is not None:
            pc, gc = Counter(pseq), Counter(gold_seq)
            tp = sum(min(pc[x], gc[x]) for x in pc)
            bag = 2 * tp / (len(pseq) + len(gold_seq)) if (pseq or gold_seq) else 0.0
            L = lcs(pseq, gold_seq)
            lf = 2 * L / (len(pseq) + len(gold_seq)) if (pseq or gold_seq) else 0.0
        else:
            bag, lf = 0.0, 0.0
        bag_f1s.append(bag)
        lcs_f1s.append(lf)
        per_row.append({"idx": i, "parsed": pseq is not None,
                        "bag": round(bag, 4), "lcs_f1": round(lf, 4)})
    n_fam = len(rows)
    fam_metrics = {}
    for f in set(list(fam_tp) + list(fam_fn) + list(fam_fp)):
        p = fam_tp[f] / (fam_tp[f] + fam_fp[f]) if (fam_tp[f] + fam_fp[f]) else 0.0
        r_ = fam_tp[f] / (fam_tp[f] + fam_fn[f]) if (fam_tp[f] + fam_fn[f]) else 0.0
        f1 = 2 * p * r_ / (p + r_) if (p + r_) else 0.0
        fam_metrics[f] = {"support": fam_tp[f] + fam_fn[f],
                          "p": round(p, 4), "r": round(r_, 4), "f1": round(f1, 4)}
    return {
        "n": n, "parse_rate": round(parse_ok / n, 4),
        "bag_f1_mean_parse_incl": round(sum(bag_f1s) / n, 4),
        "bag_f1_mean_parse_excl": round(
            sum(b for b, p in zip(bag_f1s, per_row) if p["parsed"])
            / max(1, sum(1 for p in per_row if p["parsed"])), 4),
        "lcs_f1_mean_parse_incl": round(sum(lcs_f1s) / n, 4),
        "family_presence": fam_metrics,
        "_per_row": per_row,
    }


def main():
    orig = load_dev(DEV_ORIG)
    trust = load_dev(DEV_TRUST)
    assert len(orig) == len(trust) == 1852
    changed = [i for i in range(1852) if orig[i]["tgt"] != trust[i]["tgt"]]
    pred = json.load(open(PRED, encoding="utf-8"))
    items = pred["items"]
    assert len(items) == 1852
    preds = [items[i] for i in range(1852)]

    # ---------- exclusions ----------
    excl = defaultdict(list)

    b1 = json.load(open(os.path.join(PD, "B1_FULL_DAG_VERIFICATION_V1.json"),
                        encoding="utf-8"))
    for g in b1["groups"]:
        for row in g["rows"]:
            excl[row["idx"]].append("binding_error_confirmed")

    dup = json.load(open(os.path.join(PD, "B1_duplicate_group_report.json"),
                         encoding="utf-8"))
    groups = {}
    for i, r in enumerate(orig):
        groups.setdefault(bp_hash(r["tgt"]), []).append(i)
    for h, rows_ in groups.items():
        if len(rows_) > 1:
            tasks = set(orig[i]["task"] for i in rows_)
            nfam = len(set(s["family"] for s in orig[rows_[0]]["tgt"]["stages"]))
            if len(tasks) == 1:
                kind = "duplicate_dedup"
            elif nfam <= 4:
                kind = "binding_error_suspect"
            else:
                kind = "shared_valid_unverified"
            for i in rows_[1:]:
                excl[i].append(kind if kind != "shared_valid_unverified"
                               else "shared_valid_unverified")

    ws2 = json.load(open(os.path.join(PD, "WS2_BAND_ISOLATED_181.json"),
                         encoding="utf-8"))
    for r in ws2:
        if r.get("gold_status") == "suspicious" or r.get("k") in (370, 994):
            excl[r["k"]].append("ws2_suspicious")

    s49 = json.load(open(os.path.join(PD, "ALL_IDENTICAL_SAMPLE49_V1.json"),
                         encoding="utf-8"))
    for s in s49["samples"]:
        excl[s["dev_idx"]].append("audited_pending")
    s25 = json.load(open(os.path.join(PD, "COND_COUNT_FINAL_RULING_25_V1.json"),
                         encoding="utf-8"))
    for c in s25["cases"]:
        excl[c["dev_idx"]].append("audited_pending")
    sc6 = json.load(open(os.path.join(PD, "C6_V2_STAGE_CLASSES_DEV.json"),
                         encoding="utf-8"))
    partial_rows = sorted({x["dev_idx"] for x in sc6["stages"]
                           if x["c6_class"] == "alignment_partial"})
    for i in partial_rows:
        excl[i].append("alignment_partial")

    excl_summary = Counter()
    for i, reasons in excl.items():
        excl_summary["|".join(sorted(set(reasons)))] += 1
    trusted_idx = [i for i in range(1852) if i not in excl]
    n_excl = 1852 - len(trusted_idx)

    # ---------- coverage stats ----------
    def bucket(n):
        return "short<=10" if n <= 10 else ("mid11-25" if n <= 25 else "long>25")

    cov = {}
    for name, idxs in (("full_dev", list(range(1852))), ("trusted", trusted_idx)):
        fam_rows = Counter()
        lens = Counter()
        for i in idxs:
            for f in set(s["family"] for s in orig[i]["tgt"]["stages"]):
                fam_rows[f] += 1
            lens[bucket(len(orig[i]["tgt"]["stages"]))] += 1
        cov[name] = {"n": len(idxs),
                     "families_row_count": dict(fam_rows),
                     "length_buckets": dict(lens)}

    # ---------- dual eval ----------
    e1 = eval_view(orig, preds, None)
    e2 = eval_view(trust, preds, None)
    sub = trusted_idx
    e3 = eval_view([trust[i] for i in sub], [preds[i] for i in sub], None)
    e4 = eval_view([orig[i] for i in sub], [preds[i] for i in sub], None)

    # changed cases + exclusion impact
    changed_cases = [{"idx": i, "bag_orig": e1["_per_row"][i]["bag"],
                      "bag_trust": e2["_per_row"][i]["bag"],
                      "lcs_orig": e1["_per_row"][i]["lcs_f1"],
                      "lcs_trust": e2["_per_row"][i]["lcs_f1"]}
                     for i in changed]
    excl_bag_mean = sum(e1["_per_row"][i]["bag"] for i in excl) / max(1, n_excl)
    keep_bag_mean = sum(e1["_per_row"][i]["bag"] for i in trusted_idx) / max(1, len(trusted_idx))

    def strip(e):
        e = dict(e)
        e.pop("_per_row", None)
        return e

    out = {
        "schema": "trusted_dev_candidate_and_dual_eval_v1",
        "trusted_gold": ("04_DIAG_WORK/planner_v2_dev_fix1_loopinv.jsonl = "
                         "original + fix1 (2 canonically-confirmed "
                         "loop_invariant rows). No other revision authorized."),
        "changed_rows": changed,
        "exclusions": {
            "n_excluded": n_excl,
            "n_trusted": len(trusted_idx),
            "coverage_pct": round(len(trusted_idx) / 1852 * 100, 1),
            "reason_summary": dict(excl_summary),
            "rows": {str(i): sorted(set(r)) for i, r in sorted(excl.items())},
        },
        "coverage": cov,
        "exclusion_impact": {
            "mean_bag_orig_excluded_rows": round(excl_bag_mean, 4),
            "mean_bag_orig_trusted_rows": round(keep_bag_mean, 4),
            "note": ("checks the 'exclude hard rows to inflate metrics' risk; "
                     "reported explicitly per owner requirement"),
        },
        "E1_original_gold_full_dev": strip(e1),
        "E2_trusted_gold_full_dev": strip(e2),
        "E3_trusted_gold_trusted_subset": strip(e3),
        "E4_original_gold_trusted_subset": strip(e4),
        "changed_cases_metrics": changed_cases,
        "_per_row_E1": e1["_per_row"],
        "_per_row_E3": e3["_per_row"],
    }
    outp = os.path.join(PD, "DUAL_TRACK_EVAL_V1.json")
    json.dump(out, open(outp, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    for k in ("E1_original_gold_full_dev", "E2_trusted_gold_full_dev",
              "E3_trusted_gold_trusted_subset",
              "E4_original_gold_trusted_subset"):
        e = out[k]
        print(k, "| n", e["n"], "| parse", e["parse_rate"],
              "| bag(incl)", e["bag_f1_mean_parse_incl"],
              "| bag(excl)", e["bag_f1_mean_parse_excl"],
              "| lcs", e["lcs_f1_mean_parse_incl"])
    bs1 = e1["family_presence"].get("BAND_SELECT")
    bs3 = e3["family_presence"].get("BAND_SELECT")
    print("BAND_SELECT presence F1: full-dev orig", bs1 and bs1["f1"],
          "| trusted-subset", bs3 and bs3["f1"])
    print("exclusions:", n_excl, "trusted:", len(trusted_idx),
          "| reason summary:", dict(excl_summary))
    print("length buckets trusted:", cov["trusted"]["length_buckets"])
    print("exclusion impact: excluded mean bag", round(excl_bag_mean, 4),
          "vs trusted mean bag", round(keep_bag_mean, 4))
    print("saved:", outp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
