#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply owner preliminary rulings to the all_identical sample; fix sampling
accounting (population_n vs sample_n per stratum); unify naming to v49.

Rulings are PRELIMINARY SEMANTIC JUDGMENTS, not gold repair actions.
Same seed/method as the superseded file -> identical 49 IDs.
"""

import json
import random
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")

# (dev_idx, seq_or_None, repeat_meaning, granularity_disposition, note, confidence)
R = [
 (589, None, "multi_call_likely", "keep_pending",
  "水体面积提取可能不同对象/统计；仅凭方法名不能确定", "低"),
 (1576, None, "multi_call_likely", "keep_pending", "NDVI/EVI 时间序列可能分别聚合", "中低"),
 (1774, None, "multi_call_likely", "keep_pending", "多个植被指数与时序产生多个均值统计", "中低"),
 (979, None, "multi_call_likely", "keep_pending", "地类分类可能多类别/分区计数", "中低"),
 (17, None, "insufficient_evidence", "unresolved_granularity",
  "15 次可能多时段/指数/分组或生成式重复", "低"),
 (657, None, "insufficient_evidence", "unresolved_granularity",
  "地表温度估算多窗口/分区无法推 8 次语义", "低"),
 (716, None, "multi_rule_candidate", "keep_pending", "K-means 水体可能多属性条件或预筛选", "低"),
 (1223, None, "multi_rule_candidate", "keep_pending", "城市区域识别多属性条件可能", "低"),
 (1204, None, "insufficient_evidence", "unresolved_granularity",
  "9 次同方法：9 规则/重复执行/筛选不可证", "低"),
 (1732, None, "multi_call_likely", "keep_pending", "pixelLonLat 可能构造多个坐标变量", "低"),
 (1144, None, "multi_call_likely", "keep_pending", "城市化分析多个常量影像/参数层", "低"),
 (557, None, "multi_call_likely", "keep_pending", "NDVI 趋势多常量/参数", "低"),
 (1145, None, "multi_call_likely", "keep_pending", "建成区变化多时期/常量", "低"),
 (648, None, "multi_call_likely", "keep_pending", "CN 径流组合输入影像", "低"),
 (1195, None, "multi_call_likely", "keep_pending", "雷达森林损失多波段组合", "低"),
 (1102, None, "multi_call_likely", "keep_pending", "风倒木多波段/中间影像", "低"),
 (1806, None, "multi_call_likely", "keep_pending", "可能分别训练不同分类器/配置", "低"),
 (1266, None, "multi_call_likely", "keep_pending", "干旱森林不同样本/模型配置", "低"),
 (306, None, "multi_call_likely", "keep_pending", "植被与水体指数分别导出", "中低"),
 (1121, None, "multi_call_likely", "keep_pending", "SATVI 百分位多输出产品", "中低"),
 (951, 5, "multi_call_likely", "keep_pending", "植被/沙丘变化多产品", "低"),
 (951, 24, "multi_call_likely", "keep_pending",
  "同任务第二导出阶段；须核实与 seq5 输出语义是否不同", "低"),
 (448, None, "multi_call_likely", "keep_pending", "两个点/空间位置定义", "低"),
 (1732, None, "loop_candidate_unverified", "keep_pending",
  "两 map 调用不代表同一循环执行两次", "中"),
 (514, None, "loop_candidate_unverified", "keep_pending", "水体与气候变量分别映射", "中低"),
 (1006, None, "multi_call_likely", "keep_pending", "森林覆盖/损失多层掩膜", "低"),
 (691, None, "multi_call_likely", "keep_pending", "花生种植区多筛选/多阶段掩膜", "低"),
 (18, None, "repeated_data_source_candidate", "keep_pending", "1995 地类分类多输入影像", "低"),
 (53, None, "repeated_data_source_candidate", "keep_pending", "分类修正原图+辅助影像", "低"),
 (826, None, "repeated_data_source_candidate", "keep_pending", "多源地类支持多输入；数量未证", "中低"),
 (564, None, "repeated_data_source_candidate", "keep_pending", "水体/阴影多波段或多幅；7 次来源不明", "低"),
 (1243, None, "repeated_data_source_candidate", "unresolved_granularity",
  "SAR 多幅可能；标题不足解释 8 次", "低"),
 (603, None, "repeated_data_source_candidate", "unresolved_granularity",
  "火后恢复多时期；输入数/粒度未确认", "低"),
 (1448, None, "multi_rule_candidate", "keep_pending", "月最大 kNDVI 月份/季节条件", "低"),
 (1470, None, "multi_rule_candidate", "keep_pending", "最热月投影多时间范围", "低"),
 (504, None, "multi_rule_candidate", "keep_pending", "水量平衡多窗口；未必 6 独立阶段", "中低"),
 (744, None, "multi_rule_candidate", "keep_pending", "湿地损失/增长多时段筛选", "中低"),
 (697, None, "insufficient_evidence", "unresolved_granularity",
  "14 次不能直接解释为 14 时期/循环", "低"),
 (467, None, "insufficient_evidence", "unresolved_granularity",
  "夏季后向散射多窗口缺参数", "低"),
 (674, None, "multi_rule_candidate", "keep_pending", "洪水识别多分类/掩膜规则", "中低"),
 (1088, None, "multi_rule_candidate", "keep_pending", "树冠覆盖多条件赋值", "中低"),
 (1196, None, "multi_rule_candidate", "keep_pending", "水稻多阈值/分类规则；不与 41 合并", "中低"),
 (673, None, "multi_rule_candidate", "keep_pending", "植被密度/水体指数多分类规则", "中低"),
 (854, None, "multi_rule_candidate", "keep_pending",
  "NDVI 分级支持多阈值；20 次是否独立规则需参数", "中"),
 (114, None, "insufficient_evidence", "unresolved_granularity",
  "风蚀多等级可能；10 次含义无法证明", "低"),
 (958, None, "repeated_data_source_candidate", "keep_pending", "小麦产量多空间/辅助数据集", "低"),
 (1204, None, "repeated_data_source_candidate", "keep_pending", "甘蔗识别多要素构造", "低"),
 (631, None, "insufficient_evidence", "unresolved_granularity",
  "10 次要素构造：几何/记录/结构不可断为循环", "低"),
 (994, None, "insufficient_evidence", "unresolved_granularity",
  "38 次要素构造存疑但无参数/源码，不认定虚假重复", "低"),
]


def band(r):
    return "r2_3" if r <= 3 else ("r4_7" if r <= 7 else "r8plus")


def main():
    stages = json.load(open(os.path.join(PD, "C6_V2_STAGE_CLASSES_DEV.json"),
                            encoding="utf-8"))["stages"]
    ai = [x for x in stages if x["c6_class"] == "all_identical"]
    per_task = defaultdict(list)
    for x in ai:
        per_task[x["dev_idx"]].append(x)
    capped = []
    for idx in sorted(per_task):
        capped.extend(per_task[idx][:2])
    cells = defaultdict(list)
    for x in capped:
        cells[(x["family"], band(x["repeat"]))].append(x)
    rng = random.Random(20261012)
    per_cell = max(1, 60 // max(1, len(cells)))
    sample, strata_acc = [], {}
    for k in sorted(cells):
        pool = cells[k][:]
        rng.shuffle(pool)
        take = pool[:per_cell]
        sample.extend(take)
        strata_acc[f"{k[0]}|{k[1]}"] = {
            "population_n": len(cells[k]), "sample_n": len(take),
            "method": "per_cell=min(2, cell size), rng=Random(20261012), "
                      "task-cap<=2 runs/task"}
    sample = sample[:60]

    # verify identity with superseded file's 49 IDs
    old = json.load(open(os.path.join(PD, "ALL_IDENTICAL_SAMPLE60_V1.json"),
                         encoding="utf-8"))
    old_ids = [(s["dev_idx"], s["seq"]) for s in old["samples"][:49]]
    new_ids = [(s["dev_idx"], s["seq"]) for s in sample[:49]]
    assert old_ids == new_ids, "sample set drifted from frozen v60 file"

    # mechanical ruling match
    used = set()
    unmatched_rulings = []
    for (idx, seq, rm, gd, note, conf) in R:
        cands = [i for i, s in enumerate(sample)
                 if s["dev_idx"] == idx and i not in used]
        if seq is not None:
            cands = [i for i in cands if sample[i]["seq"] == seq] or cands
        if not cands:
            unmatched_rulings.append((idx, seq))
            continue
        i = cands[0]
        used.add(i)
        s = sample[i]
        span = s.get("canonical_span") or []
        s["ruling"] = {
            "repeat_meaning": rm, "granularity_disposition": gd,
            "evidence_note": note, "confidence": conf,
            "status": "preliminary_semantic_ruling_NOT_repair_action",
            "canonical_api_first": span[0] if span else None,
            "canonical_span_full": span}

    # duplicate dev_idx rows (1732 twice, 951 twice, 1204 twice, 744 twice,
    # 1204 also in B+M etc.) consume distinct runs in listed order; any
    # leftover rulings for a task beyond available runs land in unmatched.
    n_ruled = len(used)
    out = {
        "schema": "all_identical_sample49_v1",
        "supersedes": "ALL_IDENTICAL_SAMPLE60_V1.json (naming unified; same "
                      "seed/method, identical 49 IDs)",
        "sampling": {
            "pool": "all_identical runs (C6 v2 aligned), 491 total",
            "task_cap": "max 2 runs per source task -> 372",
            "strata": strata_acc,
            "note": "population_n vs sample_n reported separately "
                    "(owner caliber fix)",
        },
        "statistics_unit": "run-level; same-task runs (e.g. dev 951 seq5+"
                           "seq24) ruled individually but grouped by "
                           "dev_idx for aggregate evidence weighting",
        "ruling_status": "PRELIMINARY semantic rulings by owner "
                         "(2026-10-12). NOT gold repair actions. No batch "
                         "rewrite authorized.",
        "source_priority_check_list": [854, 114, 994, 631, 697, 1204,
                                       "951.seq5", "951.seq24"],
        "granularity_priority_families": [
            "ee.Image.where", "ee.Filter.calendarRange",
            "ee.ImageCollection.map", "high-repeat ee.Image/ee.Feature"],
        "mechanical_check": {
            "ruling_rows": len(R),
            "samples_ruled": n_ruled,
            "unmatched_rulings": unmatched_rulings,
            "samples_without_ruling": [
                (sample[i]["dev_idx"], sample[i]["seq"])
                for i in range(len(sample)) if i not in used],
        },
        "n": len(sample[:49]),
        "samples": sample[:49],
    }
    json.dump(out, open(os.path.join(PD, "ALL_IDENTICAL_SAMPLE49_V1.json"),
                        "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    old["superseded_by"] = "ALL_IDENTICAL_SAMPLE49_V1.json"
    json.dump(old, open(os.path.join(PD, "ALL_IDENTICAL_SAMPLE60_V1.json"),
                        "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("sample n:", len(sample[:49]), "| identity with frozen v60: OK")
    print("ruling rows:", len(R), "| samples ruled:", n_ruled)
    print("unmatched rulings:", unmatched_rulings)
    print("samples without ruling:", out["mechanical_check"]["samples_without_ruling"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
