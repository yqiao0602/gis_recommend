#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-track joint audit Q4: planner-line errors x training-pool distribution.

Owner ruling B_TRACK_Q2Q4_RULING_OWNER_V1.md Q4: which errors are inherent to the
data vs introduced/amplified by training? Method: decode gold dev blueprints and
the frozen fmt-checkpoint predictions into 30-label sequences, classify error
types, then stratify error rates by the gold template's TRAINING-POOL frequency
(support) and by chain length. Also measures high-frequency bias: mean pool
frequency of predicted vs gold templates, prediction concentration, and the
missing-family histogram (cross-checks the R5 X4 INDEX/MASKING under-emission).

READ-ONLY. Deterministic.

Outputs (diag50_v1/b_track_audit_v1/):
  Q4_PLANNER_ERROR_AUDIT_V1.json / .md
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
DEV = REPO.parent / "04_DIAG_WORK/planner_v2_dev.jsonl"
PREDS = REPO.parent / "04_DIAG_WORK/p0_failure_diag/planner_v2_fmt_dev_full_preds.json"
OUT_DIR = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                   "planning_capability_audit_v1/diag50_v1/b_track_audit_v1"))


def expand_stages(stages):
    seq = []
    for st in sorted(stages, key=lambda s: s.get("seq", 0)):
        seq.extend([st.get("family", "?")] * int(st.get("repeat", 1) or 1))
    return seq


def parse_stages(text):
    try:
        obj = json.loads(text)
        stages = obj.get("stages")
        if not isinstance(stages, list) or not stages:
            return None
        return stages
    except Exception:
        return None


def freq_bucket(c):
    if c == 0:
        return "absent(0)"
    if c == 1:
        return "singleton(1)"
    if c <= 10:
        return "low(2-10)"
    if c <= 100:
        return "mid(11-100)"
    return "high(>100)"


def len_bucket(n):
    if n <= 5:
        return "1-5"
    if n <= 10:
        return "6-10"
    if n <= 20:
        return "11-20"
    return ">20"


def classify(gold, pred):
    """Error taxonomy for gold vs pred 30-label sequences."""
    if pred is None:
        return "PARSE_FAIL"
    if gold == pred:
        return "EXACT"
    gs, ps = set(gold), set(pred)
    if gs == ps:
        return "SAME_SET_DIFF_ORDER"
    missing, extra = sorted(gs - ps), sorted(ps - gs)
    if missing and not extra:
        return "ONLY_MISSING:" + ",".join(missing[:4])
    if extra and not missing:
        return "ONLY_EXTRA:" + ",".join(extra[:4])
    return "MIXED:" + ",".join(missing[:3]) + "|" + ",".join(extra[:3])


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # pool template frequencies over the TRAIN split only (the model's actual
    # training surface: 101,513 rows; val/test excluded)
    pool_freq = Counter()
    n_pool = 0
    with POOL.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("split") != "train":
                continue
            pool_freq[re.sub(r"\s+", " ", r["semantic_chain_rle"].strip())] += 1
            n_pool += 1

    # dev gold + preds (join by order; sanity-check task_head alignment)
    dev = [json.loads(l) for l in DEV.open(encoding="utf-8")]
    pd = json.loads(PREDS.read_text(encoding="utf-8"))
    items = pd["items"]
    assert len(dev) == len(items) == pd["rows"], \
        f"row mismatch dev={len(dev)} preds={len(items)}"

    n_head_match = sum(
        1 for d, it in zip(dev, items)
        if norm_head(d["task"])[:60] in norm_head(it.get("task_head", ""))
        or norm_head(it.get("task_head", ""))[:60] in norm_head(d["task"]))

    rows = []
    for d, it in zip(dev, items):
        try:
            tgt = json.loads(d["target"])
            gold_stages = tgt.get("stages")
        except Exception:
            gold_stages = None
        gold = expand_stages(gold_stages) if gold_stages else None
        pred_stages = parse_stages(it.get("pred_text") or "")
        pred = expand_stages(pred_stages) if pred_stages else None
        gtpl = " -> ".join(gold) if gold else None
        ptpl = " -> ".join(pred) if pred else None
        gfreq = pool_freq.get(gtpl, 0) if gtpl else 0
        pfreq = pool_freq.get(ptpl, 0) if ptpl else 0
        rows.append({
            "gold": gold, "pred": pred,
            "err_class": classify(gold, pred),
            "gold_len": len(gold) if gold else 0,
            "pred_len": len(pred) if pred else 0,
            "gold_freq": gfreq, "pred_freq": pfreq,
            "first_div": next((i for i, (a, b) in
                               enumerate(zip(gold or [], pred or [])) if a != b),
                              None),
        })

    n = len(rows)
    parsed = sum(1 for r in rows if r["pred"] is not None)
    exact = sum(1 for r in rows if r["err_class"] == "EXACT")

    # stratifications
    by_freq = defaultdict(lambda: Counter())
    by_len = defaultdict(lambda: Counter())
    for r in rows:
        cls = r["err_class"].split(":")[0]
        by_freq[freq_bucket(r["gold_freq"])][cls] += 1
        by_len[len_bucket(r["gold_len"])][cls] += 1

    def rates(cnt):
        tot = sum(cnt.values())
        return {"n": tot,
                "exact_rate": round(cnt["EXACT"] / tot, 4) if tot else None,
                "parse_fail_rate": round(cnt["PARSE_FAIL"] / tot, 4) if tot else None}

    # bias measures
    gold_freqs = [r["gold_freq"] for r in rows]
    pred_freqs = [r["pred_freq"] for r in rows if r["pred"] is not None]
    pred_tpl_counter = Counter(" -> ".join(r["pred"]) for r in rows
                               if r["pred"] is not None)
    top10_share = sum(c for _t, c in pred_tpl_counter.most_common(10)) / max(1, parsed)
    missing_fam = Counter()
    for r in rows:
        if r["gold"] and r["pred"]:
            gs, ps = set(r["gold"]), set(r["pred"])
            for fam in gs - ps:
                missing_fam[fam] += 1

    results = {
        "predictions_file": PREDS.name,
        "n_dev": n, "n_taskhead_aligned": n_head_match,
        "n_pred_parsed": parsed, "parse_fail_rate": round(1 - parsed / n, 4),
        "n_exact": exact, "exact_rate": round(exact / n, 4),
        "err_class_hist": Counter(r["err_class"].split(":")[0] for r in rows),
        "err_class_top_detail": Counter(r["err_class"] for r in rows).most_common(12),
        "by_gold_pool_freq": {b: {**rates(c), "hist": dict(c)}
                              for b, c in sorted(by_freq.items())},
        "by_gold_len": {b: {**rates(c), "hist": dict(c)}
                        for b, c in sorted(by_len.items())},
        "mean_pool_freq_gold": round(sum(gold_freqs) / n, 2),
        "mean_pool_freq_pred": round(sum(pred_freqs) / max(1, len(pred_freqs)), 2),
        "n_distinct_pred_templates": len(pred_tpl_counter),
        "pred_top10_share": round(top10_share, 4),
        "pred_top10": [{"template": t, "n": c,
                        "pool_freq": pool_freq.get(t, 0)}
                       for t, c in pred_tpl_counter.most_common(10)],
        "missing_family_hist": missing_fam.most_common(),
        "pool_rows": n_pool, "pool_templates": len(pool_freq),
        "first_divergence_hist": Counter(
            "0" if r["first_div"] == 0 else
            ("1-3" if r["first_div"] is not None and r["first_div"] <= 3 else
             ("4+" if r["first_div"] is not None else "na"))
            for r in rows).most_common(),
    }
    (OUT_DIR / "Q4_PLANNER_ERROR_AUDIT_V1.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=dict),
        encoding="utf-8")

    md = ["# Q4 规划错误 × 池分布审计 V1", "",
          f"预测源：`{PREDS.name}`（fmt 检查点，dev-1852）；task_head 对齐 {n_head_match}/{n}。",
          f"解析成功 {parsed}/{n}（parse_fail {results['parse_fail_rate']}）；"
          f"精确匹配 {exact}（{results['exact_rate']}）。", "",
          "## 按金标模板的池频（训练支持度）分层的错误率", "",
          "| 池频桶 | n | exact 率 | parse_fail 率 |", "|---|---|---|---|"]
    for b, v in sorted(by_freq.items()):
        md.append(f"| {b} | {v and sum(v.values())} | {rates(v)['exact_rate']} | "
                  f"{rates(v)['parse_fail_rate']} |")
    md += ["", "## 按金标链长分层的错误率", "",
           "| 长度桶 | n | exact 率 | parse_fail 率 |", "|---|---|---|---|"]
    for b, v in sorted(by_len.items()):
        md.append(f"| {b} | {sum(v.values())} | {rates(v)['exact_rate']} | "
                  f"{rates(v)['parse_fail_rate']} |")
    md += ["", "## 高频偏置证据", "",
           f"- 金标模板平均池频：{results['mean_pool_freq_gold']}；"
           f"预测模板平均池频：{results['mean_pool_freq_pred']}",
           f"- 预测去重模板数：{results['n_distinct_pred_templates']}；"
           f"预测 Top-10 集中度：{results['pred_top10_share']}", "",
           "## 金标家族缺失直方图（对照 R5 X4 INDEX/MASKING 欠发射）", ""]
    for fam, c in missing_fam.most_common():
        md.append(f"- {fam}: {c}")
    (OUT_DIR / "Q4_PLANNER_ERROR_AUDIT_V1.md").write_text(
        "\n".join(md), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items()
                      if k in ("n_dev", "n_taskhead_aligned", "n_pred_parsed",
                               "parse_fail_rate", "n_exact", "exact_rate",
                               "mean_pool_freq_gold", "mean_pool_freq_pred",
                               "n_distinct_pred_templates", "pred_top10_share")},
                     ensure_ascii=False, indent=1))
    print("by_gold_pool_freq:")
    for b, v in sorted(by_freq.items()):
        print(f"  {b}: n={sum(v.values())} exact={rates(v)['exact_rate']} "
              f"parse_fail={rates(v)['parse_fail_rate']}")
    print("missing_family_hist:", missing_fam.most_common(8))


def norm_head(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())[:120]


if __name__ == "__main__":
    main()
