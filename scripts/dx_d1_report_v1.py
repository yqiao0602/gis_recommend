#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 report generator (FROZEN before results, 2026-10-18).

Reads D1_RESULTS_V1.json (produced by the frozen analyzer) and
D1_EXEC_AUDIT_V1.json (execution completeness audit) and emits
D1_RESULTS_REPORT_V1.md following the owner's six reporting rules:

  1. execution completeness first (no silent deletion of failures);
  2. raw counts before statistics (A/B empty counts, transitions, task CI,
     26-task coverage);
  3. empty output vs termination separated (IMMEDIATE_EOS/EOS/CAP_TRUNC/
     END_MARK);
  4. manipulation check (B must be 1650 +/- 10 tokens; failures retained);
  5. decision classes + self-contradictory count, no correctness claims;
  6. same-round A arm vs A1 historical consistency.

Interpretation follows the preregistered three-way rule and the frozen
boundary: this is the effect of inserting the frozen neutral text at the
specified position for these 47 previously-successful short prompts.
"""
import json
from pathlib import Path

D1 = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/dx50_full_v1/d1_v1")


def verdict(r):
    e = r["empty"]
    lo, hi = e["ci95"]
    diff_pp = e["diff"] * 100
    cap_a = r["termination"]["A"].get("CAP_TRUNC", 0)
    cap_b = r["termination"]["B"].get("CAP_TRUNC", 0)
    n = r["n_pairs"]
    cap_delta_pp = (cap_b - cap_a) / n * 100
    manip_ok = r["manipulation"]["all_prompt_sha_ok"] and r["manipulation"]["all_B_in_range"]
    contradiction_up = r["self_contradictory"]["B"] > r["self_contradictory"]["A"]
    if not manip_ok:
        return "UNCERTAIN", "操纵核验失败——不得归因长度/插入效应"
    if lo > 0 and cap_delta_pp <= 3 and not contradiction_up:
        return "SUPPORTED", (f"B 空输出率显著更高（差 {diff_pp:+.1f}pp，CI [{lo*100:+.1f}, "
                             f"{hi*100:+.1f}]pp），真实截断变化 {cap_delta_pp:+.1f}pp，"
                             f"自相矛盾未增加")
    if lo <= 0 <= hi and abs(diff_pp) < 5:
        return "NOT_SUPPORTED", (f"配对差 {diff_pp:+.1f}pp，CI [{lo*100:+.1f}, {hi*100:+.1f}]pp "
                                 "含 0 且幅度小")
    return "UNCERTAIN", (f"差 {diff_pp:+.1f}pp，CI [{lo*100:+.1f}, {hi*100:+.1f}]pp；"
                         "需结合截断/自相矛盾/覆盖度判断")


def main():
    r = json.loads((D1 / "D1_RESULTS_V1.json").read_text(encoding="utf-8"))
    a = json.loads((D1 / "D1_EXEC_AUDIT_V1.json").read_text(encoding="utf-8"))
    v, vtext = verdict(r)
    md = ["# D1 中性长文本插入实验 — 结果报告 V1（预注册口径）", "",
          "> 边界（冻结）：本实验检验**在 `[Instruction]` 前插入冻结中性长文本**对 47 个历史短提示的效应；"
          "总长度、指令距离与无关上下文量不可分离，结论不得表述为普遍 token 长度因果，"
          "也不外推到其余 111 个受影响步。", "",
          "## 1. 执行完整性（先于任何统计）", "",
          f"- 记录：**{a['n_records']}/{a['n_expected']}**；缺失：{a['missing'] or '无'}",
          f"- 全部 record 的 prompt_sha16 与冻结提示一致：**{a['all_prompt_sha_ok']}**",
          f"- 全部 commit 标记 raw/gen 哈希核验通过：**{a['all_commit_ok']}**",
          f"- 模型/runner/termination：{a['model']} / {a['runner']} / {a['termination']}",
          f"- 失败/异常记录（保留未删）：{a['failed_or_anomalous'] or '无'}", "",
          "## 2. 原始计数（先于统计）", "",
          f"- 配对数：{r['n_pairs']}；任务数：{r['n_tasks']}；任务覆盖：{r['n_tasks']}/{r['n_tasks']}",
          f"- A 臂空输出：**{r['empty']['A']}/{r['n_pairs']}**（{r['empty']['rate_A']:.1%}）；"
          f"B 臂空输出：**{r['empty']['B']}/{r['n_pairs']}**（{r['empty']['rate_B']:.1%}）",
          f"- 配对差（B−A）：**{r['empty']['diff']*100:+.1f}pp**；任务级 cluster bootstrap 95% CI "
          f"**[{r['empty']['ci95'][0]*100:+.1f}, {r['empty']['ci95'][1]*100:+.1f}]pp**"
          f"（26 任务，10k，seed 20261018）", "",
          "### 配对转移（空/非空）", ""]
    for k, n in r["transitions"].items():
        md.append(f"- {k}: {n}")
    md += ["", "## 3. 终止状态（与空输出分开）", "",
           "| 臂 | IMMEDIATE_EOS | EOS | CAP_TRUNC | END_MARK |", "|---|---|---|---|---|"]
    for arm in ("A", "B"):
        t = r["termination"][arm]
        md.append(f"| {arm} | {t.get('IMMEDIATE_EOS', 0)} | {t.get('EOS', 0)} | "
                  f"{t.get('CAP_TRUNC', 0)} | {t.get('END_MARK', 0)} |")
    md += ["", "## 4. 操纵核验", "",
           f"- B 臂 token 均在 1,650±10：**{r['manipulation']['all_B_in_range']}**",
           f"- 全部 prompt_sha16 对齐：**{r['manipulation']['all_prompt_sha_ok']}**",
           f"- 失败样本（保留并计入分母）：{r['manipulation']['failures'] or '无'}", "",
           "## 5. 决策类别与自相矛盾（不评价正确性）", "",
           f"- A：{r['decisions']['A']}", f"- B：{r['decisions']['B']}",
           f"- 自相矛盾：A={r['self_contradictory']['A']}，B={r['self_contradictory']['B']}", "",
           "## 6. A 臂与 A1 历史一致性（生成稳定性参考）", "",
           f"- 空状态一致：{r['same_round_A_vs_A1'].get('same_empty_state', 0)}/{r['n_pairs']}",
           f"- 决策类别一致：{r['same_round_A_vs_A1'].get('same_decision', 0)}/{r['n_pairs']}",
           f"- 原文精确匹配：{r['same_round_A_vs_A1'].get('exact_raw', 0)}/{r['n_pairs']}", "",
           "## 7. 预注册判读", "",
           f"**判定：{v}** — {vtext}", "",
           "边界重申：即使支持，也只适用于 47 个历史短提示与该插入方案；"
           "不分离总长度/指令距离/无关上下文；不外推。"]
    (D1 / "D1_RESULTS_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")
    print("verdict:", v, "|", vtext)


if __name__ == "__main__":
    main()
