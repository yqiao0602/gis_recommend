"""Error audit for the Route-2 three-arm test-111 predictions (P0-6 follow-up).

Offline, read-only diagnostic: classifies each test row's prediction against
gold into mutually-exclusive primary buckets, computes parse-ok subset
metrics, and dumps the two hypothesis cells (B1: ops wrong + links right;
C0: ops right + links wrong) as wid lists for qualitative inspection.

Does NOT touch gold, scorer, benchmarks, or any training artifact.
"""

import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/reports/route2_p0_contract/test111_final_v1"
ARMS = ["C0_ep20", "A1_ep15", "B1_ep18"]


def op_set_f1(pred: set, gold: set) -> float:
    if not pred and not gold:
        return 1.0
    inter = len(pred & gold)
    if inter == 0:
        return 0.0
    return 2 * inter / (len(pred) + len(gold))


def link_f1(pred: set, gold: set) -> float:
    if not pred and not gold:
        return 1.0
    inter = len(pred & gold)
    if inter == 0:
        return 0.0
    return 2 * inter / (len(pred) + len(gold))


def classify(pred_ops: set, gold_ops: set, pred_links: set, gold_links: set,
             parse_failed: bool) -> str:
    if parse_failed:
        return "parse_failure"
    ops_eq = pred_ops == gold_ops
    links_eq = pred_links == gold_links
    if ops_eq and links_eq:
        return "exact_match"
    if ops_eq:
        return "ops_right_links_wrong"
    if links_eq:
        return "ops_wrong_links_right"
    if pred_ops < gold_ops:
        return "ops_missing_only"
    if gold_ops < pred_ops:
        return "ops_extra_only"
    return "ops_mixed"


def main() -> None:
    gold_rows = {}
    for line in (BASE / "v2a_A_test.gold.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        gold_rows[r["wid"]] = r

    report = {}
    for arm in ARMS:
        pred_rows = [json.loads(l) for l in
                     (BASE / f"{arm}_predictions.jsonl").open(encoding="utf-8")]
        buckets = Counter()
        missing_cnt = extra_cnt = 0
        f1_all, lf_all, f1_ok, lf_ok = [], [], [], []
        hypothesis_wids = []
        for p in pred_rows:
            g = gold_rows[p["wid"]]
            gold_ops = {x["operator_id"] for x in g["processes"]}
            pred_ops = {x["operator_id"] for x in p["pred_processes"]}
            gold_links = {(l["source_process_id"], l["target_process_id"]) for l in g["links"]}
            pred_links = {(l["source_process_id"], l["target_process_id"]) for l in p["pred_links"]}
            f1, lf = op_set_f1(pred_ops, gold_ops), link_f1(pred_links, gold_links)
            f1_all.append(f1)
            lf_all.append(lf)
            if not p["parse_failed"]:
                f1_ok.append(f1)
                lf_ok.append(lf)
            missing_cnt += len(gold_ops - pred_ops)
            extra_cnt += len(pred_ops - gold_ops)
            bucket = classify(pred_ops, gold_ops, pred_links, gold_links, p["parse_failed"])
            buckets[bucket] += 1
            if bucket == "ops_wrong_links_right":
                hypothesis_wids.append(p["wid"])
        n = len(pred_rows)
        report[arm] = {
            "n": n,
            "buckets": dict(buckets),
            "opF1_all": sum(f1_all) / n,
            "linkF1_all": sum(lf_all) / n,
            "opF1_parse_ok": sum(f1_ok) / len(f1_ok),
            "linkF1_parse_ok": sum(lf_ok) / len(lf_ok),
            "parse_ok_n": len(f1_ok),
            "missing_ops_total": missing_cnt,
            "extra_ops_total": extra_cnt,
            "missing_per_row": missing_cnt / n,
            "extra_per_row": extra_cnt / n,
            "ops_wrong_links_right_wids": hypothesis_wids,
        }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = BASE / "error_audit_v1.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
