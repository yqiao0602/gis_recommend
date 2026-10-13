#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2/P3 closeout (owner directives 2026-10-12, round 2):

1. Recompute per-stage C6-v2 classes (aligned spans) for all dev repeat>1
   stages — statistical unit = (case, run occurrence), NO dedup, NO dominant
   collapse.
2. Freeze the 25-case final ruling table with run-level class profiles and
   two independent fields: semantic_ruling (diagnosis) vs repair_action
   (data change) — never mixed.
3. Build the 60-run stratified first-pass sample over the 491 all_identical
   runs: unit = independent candidate run, max 2 runs per source task,
   strata = family x repeat band.
"""

import json
import os
import sys
import random
import importlib.util
import itertools
from collections import Counter, defaultdict
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
DEV = os.path.join(DW, "planner_v2_dev.jsonl")
GOLD3 = os.path.join(DW, "blueprint_v2_gold_v3.jsonl")
SRC = os.path.join(DW, "b1_gee_stage_train.jsonl")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT_STAGES = os.path.join(PD, "C6_V2_STAGE_CLASSES_DEV.json")
OUT_RULINGS = os.path.join(PD, "COND_COUNT_FINAL_RULING_25_V1.json")
OUT_SAMPLE = os.path.join(PD, "ALL_IDENTICAL_SAMPLE60_V1.json")


def load_classify():
    spec = importlib.util.spec_from_file_location(
        "gsw", os.path.join(REPO, "scripts", "gee_route2_semantic_workflow_v1.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gsw"] = mod
    spec.loader.exec_module(mod)
    return mod.classify


# ---------------- owner final rulings (2026-10-12 round 2) ----------------
# semantic_ruling: diagnosis axis. repair_action: data-change axis.
RULINGS = {
    1773: ("non_uniform_count_confirmed", "granularity_pending",
           "Filter.lt+ImageCollection.filter 很可能构成一个逻辑过滤操作，不拆两阶段"),
    744: ("non_uniform_count_confirmed", "granularity_pending",
          "listContains+集合过滤可能为一个逻辑过滤操作"),
    1505: ("non_uniform_count_confirmed", "granularity_pending",
           "两个不同方法不能直接解释为两个独立节点"),
    738: ("non_uniform_count_confirmed", "granularity_pending",
          "日期/瓦片/云量背景支持多条件过滤，但 span 不足以定阶段数"),
    931: ("insufficient_evidence", "keep_pending", "AF×6 无 token 语义，无法判定"),
    123: ("insufficient_evidence", "keep_pending", "交错结构无按年/传感器映射"),
    1060: ("insufficient_evidence", "keep_pending", "游程 4,1,3 缺 token 级语义"),
    1069: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留，非修复确认"),
    506: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    545: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    988: ("non_uniform_count_likely", "granularity_pending",
          "AF×8 mixed（listContains/filter/eq 交替），非统一执行"),
    838: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    54: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    207: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    1182: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    1161: ("non_uniform_count_likely", "granularity_pending", "A 诊断方向保留"),
    854: ("non_uniform_count_likely", "keep_pending",
          "TL×20×5：任务描述多 NDVI 等级，多规则解释有据；repeat=20 与真实规则数是否一致待更细上下文。优先核验"),
    1844: ("loop_candidate_unverified", "keep_pending",
           "时间维度≠循环；需核验游程是否对应不同影像/时间点"),
    269: ("loop_candidate_unverified", "keep_pending",
          "over time≠循环；TL×7 可能是多条规则"),
    41: ("multi_rule_candidate", "keep_pending",
         "分类/掩膜/阈值任务；保留多规则或多阶段候选，不认定循环"),
    1196: ("multi_rule_candidate", "keep_pending",
           "与 41 文本+蓝图 hash 均不同，不按重复样本合并"),
    490: ("multi_rule_candidate", "keep_pending", "多时相水体检测；两次 where 可能不同规则"),
    673: ("multi_rule_candidate", "keep_pending", "NDVI/NDWI/NDFI 分别分类支持多规则"),
    674: ("multi_rule_candidate", "keep_pending", "干湿季对比；两次同方法调用无法区分阈值与循环"),
    1088: ("multi_rule_candidate", "keep_pending", "多一致性类别可能涉及不同判断规则"),
}


def main():
    classify = load_classify()
    dev = []
    with open(DEV, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r.get("target")
                if isinstance(t, str):
                    t = json.loads(t)
                dev.append({"task": r.get("task") or "", "tgt": t})

    task2sid = {}
    with open(GOLD3, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task2sid.setdefault(r.get("task"), r.get("source_row_id"))

    need = set()
    for r in dev:
        t = r["tgt"]
        if isinstance(t, dict) and any(int(s.get("repeat", 1)) > 1
                                       for s in t.get("stages", [])):
            sid = task2sid.get(r["task"])
            if sid:
                need.add(sid)
    chains = {}
    with open(SRC, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i in need:
                r = json.loads(line)
                sem = [x.strip() for x in
                       (r.get("semantic_chain_raw") or "").split("->")
                       if x.strip()]
                can = [x.strip() for x in
                       (r.get("gee_canonical_chain") or "").split("->")
                       if x.strip()]
                chains[i] = (sem, can)
            if len(chains) == len(need):
                break

    # ---- per-stage v2 classes, unit = (case, run occurrence) ----
    stage_classes = []   # rows: dev_idx, seq, family, repeat, c6_class, canonical_span
    by_idx = defaultdict(list)
    for idx, r in enumerate(dev):
        t = r["tgt"]
        if not isinstance(t, dict) or "stages" not in t:
            continue
        sid = task2sid.get(r["task"])
        sem, can = chains.get(sid, (None, None))
        for s in t["stages"]:
            rep = int(s.get("repeat", 1))
            if rep <= 1:
                continue
            rec = {"dev_idx": idx, "seq": s["seq"], "family": s["family"],
                   "repeat": rep}
            if sem is None:
                rec["c6_class"] = "no_chain_join"
            else:
                can_cls = [classify(c) for c in can]
                sm = SequenceMatcher(None, can_cls, sem, autojunk=False)
                blocks = sm.get_matching_blocks()
                sem2can = {}
                for bi in range(len(blocks) - 1):
                    ci, si, size = blocks[bi]
                    for k in range(size):
                        sem2can[si + k] = ci + k
                runs = []
                p = 0
                for fam_, g in itertools.groupby(sem):
                    n = len(list(g))
                    runs.append((fam_, n, p))
                    p += n
                m = next((x for x in runs
                          if x[0] == s["family"] and x[1] == rep),
                         next((x for x in runs if x[0] == s["family"]), None))
                if m is None:
                    rec["c6_class"] = "run_not_found"
                else:
                    span = range(m[2], m[2] + m[1])
                    cpos = [sem2can[i] for i in span if i in sem2can]
                    if len(cpos) < m[1]:
                        rec["c6_class"] = "alignment_partial"
                    else:
                        seg = [can[q] for q in cpos]
                        rec["canonical_span"] = seg[:10]
                        u = len(set(seg))
                        rec["c6_class"] = ("all_identical" if u == 1 else
                                           "all_distinct" if u == len(seg)
                                           else "mixed")
            stage_classes.append(rec)
            by_idx[idx].append(rec)

    json.dump({"schema": "c6_v2_stage_classes_dev",
               "unit": "(case, run occurrence) — no dedup, no dominant collapse",
               "total_stages": len(stage_classes),
               "class_totals": dict(Counter(x["c6_class"] for x in stage_classes)),
               "stages": stage_classes},
              open(OUT_STAGES, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    # ---- frozen 25-case ruling table with run-level profiles ----
    cases = []
    for idx, (sr, ra, note) in RULINGS.items():
        prof = by_idx.get(idx, [])
        profile = [f"{x['family']}x{x['repeat']}:{x['c6_class']}"
                   for x in prof]
        cases.append({
            "dev_idx": idx,
            "task_head": (dev[idx]["task"] or "").splitlines()[0][:90],
            "semantic_ruling": sr,
            "repair_action": ra,
            "ruling_note": note,
            "run_class_profile": profile,   # every run occurrence, no dedup
        })
    ruling_doc = {
        "schema": "cond_count_final_ruling_25_v1",
        "frozen_at": "2026-10-12",
        "unit_rule": ("statistical unit = (case, run occurrence); case profile "
                      "lists every repeat>1 run of AF/TL with its own C6 v2 "
                      "class. No per-case dominant-class aggregation."),
        "axis_rule": ("semantic_ruling = diagnosis axis; repair_action = data-"
                      "change axis. A diagnosis label upgrade NEVER triggers a "
                      "data rewrite by itself (owner boundary)."),
        "label_legend": {
            "non_uniform_count_confirmed": "已证非统一循环计数（canonical 全异）",
            "non_uniform_count_likely": "非循环计数/条件粒度方向，诊断保留，非修复确认",
            "multi_rule_candidate": "多规则/多阶段候选，非循环认定",
            "loop_candidate_unverified": "循环候选未证（时间维度≠循环）",
            "insufficient_evidence": "证据不足",
        },
        "cases": cases,
    }
    json.dump(ruling_doc, open(OUT_RULINGS, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    # ---- 60-run stratified sample over all_identical ----
    ai = [x for x in stage_classes if x["c6_class"] == "all_identical"]
    # cap: max 2 runs per source task (dev_idx)
    per_task = defaultdict(list)
    for x in ai:
        per_task[x["dev_idx"]].append(x)
    capped = []
    for idx, xs in per_task.items():
        capped.extend(xs[:2])
    def band(r):
        return "r2_3" if r <= 3 else ("r4_7" if r <= 7 else "r8plus")
    cells = defaultdict(list)
    for x in capped:
        cells[(x["family"], band(x["repeat"]))].append(x)
    rng = random.Random(20261012)
    per_cell = max(1, 60 // max(1, len(cells)))
    sample = []
    for k in sorted(cells):
        pool = cells[k][:]
        rng.shuffle(pool)
        sample.extend(pool[:per_cell])
    sample = sample[:60]
    for s in sample:
        s["task_head"] = (dev[s["dev_idx"]]["task"] or "").splitlines()[0][:90]
        s["stratum"] = f"{s['family']}|{band(s['repeat'])}"
        s["ruling"] = {
            "repeat_meaning": None,       # true_iteration / rule_count /
                                          # api_call_count / undetermined
            "granularity_disposition": None,  # one_stage / multi_stage /
                                              # multi_rule_one_stage /
                                              # unresolved_granularity
            "evidence_note": None,
            "confidence": None,
        }
    json.dump({
        "schema": "all_identical_sample60_v1",
        "note": ("Stratified first-pass over all_identical runs (aligned C6 "
                 "v2). Unit = independent candidate run, max 2 runs per "
                 "source task. canonical chain carries METHOD NAMES only — "
                 "no arguments locally; args-level evidence needs source. "
                 "Dual axis per owner: (a) real-iteration evidence, "
                 "(b) workflow granularity disposition. Expansion only for "
                 "ambiguous key strata."),
        "all_identical_total": len(ai),
        "after_task_cap": len(capped),
        "sample_n": len(sample),
        "strata": {f"{k[0]}|{k[1]}": len(v) for k, v in sorted(cells.items())},
        "samples": sample,
    }, open(OUT_SAMPLE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print("stage classes total:", len(stage_classes),
          dict(Counter(x["c6_class"] for x in stage_classes)))
    print("all_identical:", len(ai), "-> capped", len(capped),
          "-> sample", len(sample))
    print("strata:", json.dumps({f"{k[0]}|{k[1]}": len(v)
                                 for k, v in sorted(cells.items())},
                                ensure_ascii=False))
    print("saved:", OUT_STAGES)
    print("saved:", OUT_RULINGS)
    print("saved:", OUT_SAMPLE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
