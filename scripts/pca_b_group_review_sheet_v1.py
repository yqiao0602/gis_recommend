#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Phase 1 — B-group owner-review worksheet generator.

Builds a per-task review sheet for the 20 primary (+10 reserve) B-group
candidates, structured around the owner's four review questions:
  Q1 task leakage  : does the text name the tested operator, or only cite
                     necessary GIS concepts?
  Q2 planning value: does the model still need to infer order/dependencies/
                     conditions even if it recognizes the operation name?
  Q3 gold independence: semantic gold must derive from task goal + data
                     needs, not mechanical translation of the QGIS chain.
  Q4 alternatives  : could a different valid workflow be wrongly judged
                     wrong by the gold?
The script only assembles evidence (full task text, lexicon hit context,
gold chain); verdicts are marked PENDING-OWNER. No model runs.
"""
import json, re

DEV = "docs/reports/v2a_manifest/v2a_A_dev.jsonl"
CAND = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_candidates_v1.json"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_review_worksheet_v1.md"

def main():
    dev = {json.loads(l)["wid"]: json.loads(l)
           for l in open(DEV, encoding="utf-8")}
    d = json.load(open(CAND, encoding="utf-8"))

    def row_block(c, wid):
        r = dev[wid]
        tt = r["task_text"]
        flags = c["lexicon_flags"]
        ctx = []
        low = tt.lower()
        for w in flags:
            m = re.search(re.escape(w), low)
            if m:
                s = max(0, m.start() - 45)
                ctx.append(f"`{w}` …{tt[s:m.end()+45]}…")
        procs = [p["operator_id"] for p in r["processes"]]
        lines = [
            f"### {wid} — {c['taskType']} — 链长 {c['chain_len']} ({c['len_band']})",
            f"",
            f"**任务文本**：{tt}",
            f"",
            f"**词表命中**：{', '.join('`'+w+'`' for w in flags) if flags else '无'}",
        ]
        if ctx:
            lines.append("")
            lines.append("**命中上下文**：")
            lines += [f"- {x}" for x in ctx]
        lines += [
            f"",
            f"**gold 链（仅反推材料，非金标）**：{' -> '.join(procs)}",
            f"",
            f"**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁",
            f"",
        ]
        return "\n".join(lines)

    parts = [
        "# PCA B 组审核工作表 v1（owner 用）",
        "",
        "> 依据：PCA_PROTOCOL_V1_FROZEN §2.1/§2.4 + owner 指令（2026-10-13）。",
        "> 筛选：20 正选 + 10 备选（frozen rules，seed 20261013，零预测参考）。",
        "> 词表命中**不自动判不合格**；四问逐条裁定。",
        "",
        f"## 正选 20 条",
        "",
    ]
    for c in d["primary"]:
        parts.append(row_block(c, c["wid"]))
    parts.append("## 备选 10 条\n")
    for c in d["reserve"]:
        parts.append(row_block(c, c["wid"]))
    parts.append("## 因算子 ID 扫描被拒的 8 条（仅记录，不进入候选）\n")
    for c in d["rejected_by_opid"]:
        parts.append(f"- {c['wid']} — {c['taskType']} — 命中ID: {', '.join(c['op_id_hits'])}")
    open(OUT, "w", encoding="utf-8").write("\n".join(parts))
    print("saved:", OUT, "| primary:", len(d["primary"]),
          "| reserve:", len(d["reserve"]))

if __name__ == "__main__":
    main()
