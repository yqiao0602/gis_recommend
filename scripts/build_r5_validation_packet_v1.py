#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the r5 blind-validation packet (6 groups x 4 candidates) from S2 dry-run.

Blind: the MD labeling sheet contains task text + parsed stage lists only —
no reward scores, no gold, no letter->true-candidate mapping (kept in the JSON
for later scoring). Order shuffled with seed 20261013.
"""
import json
import random
from pathlib import Path

RL = Path(__file__).resolve().parents[1] / \
    "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
LETTERS = ["A", "B", "C", "D"]

tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
d = json.loads((RL / "s2_dryrun/S2_DRYRUN_SCORED_V1.json").read_text(encoding="utf-8"))
preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))

random.seed(20261013)
chosen = [5227, 17970, 823, 29519, 13612, 30160]
items = []
for k in chosen:
    g = d["groups"][str(k)]
    cands = [p for p in preds if p["k"] == k and p["cand"] < 4]
    order = list(range(4))
    random.shuffle(order)
    parsed = []
    for slot, ci in enumerate(order):
        p = cands[ci]
        try:
            b = json.loads(p["pred_text"])
            stages = [f"{s.get('seq', '?')}. {s.get('family', '?')} x{s.get('repeat', '?')}"
                      for s in b.get("stages", [])]
            n_rep = sum(1 for s in b.get("stages", []) if s.get("repeat", 1) > 1)
        except Exception:
            stages, n_rep = ["<UNPARSEABLE>"], 0
        parsed.append({"letter": LETTERS[slot], "true_cand": p["cand"],
                       "stages": stages, "repeated_stage_count": n_rep})
    items.append({"k": k, "band": g["band"], "task": tasks[str(k)],
                  "candidates": parsed})

json.dump({"rubric_version": "v1", "blind": True,
           "labeling_note": "owner labels each candidate; letter->true-cand mapping "
                            "kept in this file but ABSENT from the MD sheet",
           "items": items},
          open(RL / "r5_validation_packet_v1.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

md = ["# r5 人工判定包 v1（盲评）", "",
      "> 6 组 × 4 候选 = 24 判定项。每个候选给：任务全文 + 解析后的 stage 列表"
      "（乱序、无奖励分、无 gold）。",
      "> 对每个候选给**一个**主判定，必要时附注：", "",
      "| 判定 | 含义 |", "|---|---|",
      "| `omission` | 计划**缺少**任务明确需要的能力（注明缺什么，如 \"缺 NDWI 计算\"/"
      "\"缺年度聚合\"） |",
      "| `unsupported` | 计划含任务**无依据**的处理阶段（注明哪个阶段） |",
      "| `both_reasonable` | 与组内其他候选路径不同但**都满足任务需求**（多解，注明差异性质） |",
      "| `unclear` | 无法判定（宁选此项不猜） |", "",
      "---"]
for it in items:
    md += [f"## 组 {it['k']}（{it['band']}）", "", "**任务全文：**", "", it["task"], ""]
    for c in it["candidates"]:
        md += [f"### 候选 {c['letter']}"]
        if c["repeated_stage_count"]:
            md += [f"（{c['repeated_stage_count']} 个阶段带重复计数）"]
        md += ["```", *c["stages"], "```",
               "**判定：** ______（附注：______）", ""]
(RL / "R5_VALIDATION_PACKET_V1.md").write_text("\n".join(md), encoding="utf-8")
print(f"packet + MD sheet written: {len(items)} items, "
      f"{sum(len(i['candidates']) for i in items)} candidates")
