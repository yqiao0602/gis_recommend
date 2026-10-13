#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build owner review worksheets for Experiment C (2026-10-11 ruling):

  WS-1  ITERATIVE_APPLY 93 c_likely_real_error rows: pre-classified iteration
        type (repeated_execution / loop_structure / batch_same_op) + owner
        ruling columns. These three differ in workflow expression and must
        not be conflated.
  WS-2  BAND_SELECT 181 isolated-stage FN rows: three-category ruling
        (gold_inconsistent / alternative_workflow / clearly_necessary).

No labels are modified; worksheets are adjudication inputs only.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
P0B = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                   "plan_pipeline_v1", "planner_design", "p0b_768")
A2R = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                   "plan_pipeline_v1", "planner_design")

KW_REPEATED = re.compile(r"time.series|per.year|per.month|per.season|each year|"
                         r"every year|daily|monthly|seasonal", re.I)
KW_LOOP = re.compile(r"iterate|loop|recursi|cumulative|accumulate|running", re.I)
KW_BATCH = re.compile(r"for each|every|all (bands|classes|regions|polygons)|"
                      r"multiple|each (band|class|region|feature|polygon)", re.I)


def guess_iteration_type(task_text, gold_stages):
    t = task_text or ""
    scores = {
        "repeated_execution(same op over time/objects)": len(KW_REPEATED.findall(t)) * 2
                                                      + len(KW_BATCH.findall(t)),
        "loop_structure(cumulative/iterative computation)": len(KW_LOOP.findall(t)) * 3,
        "batch_same_op(apply op to multiple objects)": len(KW_BATCH.findall(t)),
    }
    order = sorted(scores.items(), key=lambda kv: -kv[1])
    return order[0][0] if order[0][1] > 0 else "undetermined", scores


def main():
    pred = json.load(open(os.path.join(P0B, "predictions.json"), encoding="utf-8"))
    items = pred["items"]
    dev = [json.loads(l) for l in open(os.path.join(REPO, "..", "04_DIAG_WORK",
                                                    "planner_v2_dev.jsonl"),
                                       encoding="utf-8") if l.strip()]

    ws1 = []
    ws2 = []
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
        task = dv.get("task") or ""
        task_head = task.splitlines()[0][:160]
        full_task_head = "\n".join(task.splitlines()[:4])[:500]

        if "ITERATIVE_APPLY" in gf and "ITERATIVE_APPLY" not in pf:
            kw = re.search(r"time.series|per.year|per.month|per.image|per.pixel|"
                           r"season|monthly|daily|each", task, re.I)
            idx = [i for i, s in enumerate(gf) if s == "ITERATIVE_APPLY"] if kw else []
            neighbors = []
            for i in idx:
                neighbors.append({
                    "seq": gs[i].get("seq"), "repeat": gs[i].get("repeat", 1),
                    "prev": gf[i - 1] if i > 0 else None,
                    "next": gf[i + 1] if i + 1 < len(gf) else None})
            guess, scores = guess_iteration_type(task, gs)
            if kw:
                ws1.append({
                    "k": it["k"], "task_head": task_head,
                    "task_excerpt": full_task_head,
                    "gold_ITERATIVE_positions": neighbors,
                    "gold_stage_count": len(gs),
                    "pre_classified_type": guess,
                    "keyword_scores": scores,
                    "owner_ruling": None,   # repeated_execution / loop_structure /
                                            # batch_same_op / not_an_error
                    "notes": None,
                })

        if "BAND_SELECT" in gf and "BAND_SELECT" not in pf:
            idx = [i for i, s in enumerate(gs) if s["family"] == "BAND_SELECT"]
            neighbors = []
            for i in idx:
                neighbors.append({
                    "seq": gs[i].get("seq"),
                    "prev": gf[i - 1] if i > 0 else None,
                    "next": gf[i + 1] if i + 1 < len(gf) else None})
            downstream = [f for f in gf if f in ("SPECTRAL_INDEX", "BAND_ARITHMETIC")]
            if downstream:
                continue  # owner scope: isolated stages only (181); downstream
                          # rows already classified c_likely_real_error
            ws2.append({
                "k": it["k"], "task_head": task_head, "task_excerpt": full_task_head,
                "gold_BAND_SELECT_positions": neighbors,
                "downstream_consumers": downstream,
                "isolated": not downstream,
                "owner_ruling": None,  # gold_inconsistent / alternative_workflow /
                                       # clearly_necessary
                "notes": None,
            })

    ws1.sort(key=lambda r: r["k"])
    ws2.sort(key=lambda r: r["k"])
    for name, rows in (("WS1_ITERATIVE_93", ws1), ("WS2_BAND_ISOLATED_181", ws2)):
        json.dump(rows, open(os.path.join(A2R, name + ".json"), "w",
                             encoding="utf-8"), indent=2, ensure_ascii=False)
        md = [f"# {name}", ""]
        for r in rows[:200]:
            md.append(f"## k={r['k']} — {r['task_head']}")
            md.append(f"\n{r.get('task_excerpt','')}\n")
            if "pre_classified_type" in r:
                md.append(f"- 预分类: **{r['pre_classified_type']}**")
                md.append(f"- gold ITERATIVE 位置: {r['gold_ITERATIVE_positions']}")
                md.append(f"- owner_ruling: ______（repeated_execution / "
                          f"loop_structure / batch_same_op / not_an_error）")
            else:
                md.append(f"- gold BAND_SELECT 位置: {r['gold_BAND_SELECT_positions']}")
                md.append(f"- 下游消费者: {r['downstream_consumers'] or '（无——isolated）'}")
                md.append(f"- owner_ruling: ______（gold_inconsistent / "
                          f"alternative_workflow / clearly_necessary）")
            md.append("")
        open(os.path.join(A2R, name + ".md"), "w", encoding="utf-8").write("\n".join(md))
        print(name, len(rows))

    print("worksheets written to", A2R)
    return 0


if __name__ == "__main__":
    sys.exit(main())
