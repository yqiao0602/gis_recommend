#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate A1_ADJUDICATION_V1.md from the post-owner-ruling ledger and emit
A1_OWNER_RULINGS_V1.md (six ruled pairs + five cross-cutting rules)."""
import json
from collections import Counter
from pathlib import Path

P = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/a1_short/A1_FULL_EVIDENCE_PACKET_V1")
OWNER_PAIRS = ["PCA2-T-009#S3", "PCA2-T-009#S6", "PCA2-T-032#S2",
               "PCA2-T-068#S4", "PCA2-T-092#S9", "PCA2-T-090#S4"]

RULES = [
 ("R1 复合步骤闭合原则",
  "复合步骤（如定标+大气校正）中部分能力命中不升级为整体正确；卡面须证明整步闭合（T-032#S2）。"),
 ("R2 截断 ≠ 无判定",
  "截断但含推理的 think → output_validity=截断 + decision_quality=证据不足不可判；"
  "只有真正空输出才是无判定（不计入四指标），且不得把无判定追溯补写成弃权或选择"
  "（T-068#S4/T-092#S9/T-090#S4 对照臂）。"),
 ("R3 大小写笔误不改变算子身份",
  "'otb:ImageClassifier' 按 otb:imageclassifier 计（在候选内）；文本异常单独记录（T-090#S4）。"),
 ("R4 卡面字段完整度 ≠ 决策证据完整度",
  "参数名/类型/数量齐备不证明枚举选项、算法能力与输出语义已披露（T-009#S6）。"),
 ("R5 因果归因保守",
  "实验臂结果更好不等于补卡解锁；直接因果要求对照臂形成闭合决策且卡面为唯一变量"
  "（T-090#S4、T-009#S3 均不得直接归因）。"),
]


def main():
    d = json.loads((P / "LEDGER_V1.json").read_text(encoding="utf-8"))
    c = Counter()
    for e in d["entries"]:
        q = e["ledger_fields_pending_owner"]
        c[("c", q["decision_quality"]["control"])] += 1
        c[("e", q["decision_quality"]["experiment"])] += 1

    def fmt(counter, arm):
        keys = ["correct_selection", "wrong_selection", "reasonable_abstention",
                "wrong_abstention"]
        return {k: counter[(arm, k)] for k in keys}, \
            counter[(arm, "indeterminate")], counter[(arm, "n/a_no_decision")]

    ctl, ci, cn = fmt(c, "c")
    exp, ei, en = fmt(c, "e")
    nf_c = sum(ctl.values()); nf_e = sum(exp.values())

    rows = []
    for e in d["entries"]:
        q = e["ledger_fields_pending_owner"]
        mark = "★owner" if e["step_key"] in OWNER_PAIRS else ""
        rows.append(f"| {e['step_key']} | {e['batch']} | "
                    f"{q['decision_quality']['control']} | "
                    f"{q['decision_quality']['experiment']} | "
                    f"{q['output_validity']['control']}/{q['output_validity']['experiment']} | "
                    f"{q['mechanism']} | {mark} |")

    md = ["# A1 逐对裁决 V1.1（owner 六条裁决已并入；其余 46 对=agent 裁决待抽检）", "",
          "规则：A1_OWNER_ADJUDICATION_V1.md + owner 五条横切规则（R1-R5，见 "
          "A1_OWNER_RULINGS_V1.md）。NODEC（空输出）不入四指标；截断=不可判（R2）。", "",
          "## 四指标（owner 裁决后）", "",
          "| 指标 | 对照 v0_4 | 实验 v0_5 |", "|---|---|---|",
          f"| 形成判定步数 | {nf_c} | {nf_e} |",
          f"| 正确选择 | {ctl['correct_selection']} ({ctl['correct_selection']/nf_c:.1%}) | "
          f"{exp['correct_selection']} ({exp['correct_selection']/nf_e:.1%}) |",
          f"| 错误选择 | {ctl['wrong_selection']} ({ctl['wrong_selection']/nf_c:.1%}) | "
          f"{exp['wrong_selection']} ({exp['wrong_selection']/nf_e:.1%}) |",
          f"| 合理弃权 | {ctl['reasonable_abstention']} ({ctl['reasonable_abstention']/nf_c:.1%}) | "
          f"{exp['reasonable_abstention']} ({exp['reasonable_abstention']/nf_e:.1%}) |",
          f"| 误弃权 | {ctl['wrong_abstention']} | {exp['wrong_abstention']} |",
          f"| 证据不足不可判（截断等） | {ci} | {ei} |",
          f"| 无判定（空输出，不计入） | {cn} | {en} |",
          "", "## 逐对裁决（★owner=owner 已裁决；其余待抽检）", "",
          "| 步骤 | 批次 | 对照 | 实验 | validity 对照/实验 | 机制 | 状态 |",
          "|---|---|---|---|---|---|---|"] + rows

    md += ["", "## 六条 owner 裁决要点", ""]
    for key in OWNER_PAIRS:
        e = next(x for x in d["entries"] if x["step_key"] == key)
        q = e["ledger_fields_pending_owner"]
        md.append(f"- **{key}**：control={q['decision_quality']['control']} / "
                  f"experiment={q['decision_quality']['experiment']}（validity "
                  f"{q['output_validity']['control']}/{q['output_validity']['experiment']}）"
                  f"——{q['mechanism']}")
    (P / "A1_ADJUDICATION_V1.md").write_text("\n".join(md), encoding="utf-8")

    rr = ["# A1 owner 裁决 V1（2026-10-18，六样本两批）", "",
          "> 状态：owner 已裁决 6/52；其余 46 对为 agent 裁决（pending spot-check）。", "",
          "## 五条横切规则（后续核验沿用）", ""]
    for name, body in RULES:
        rr.append(f"### {name}")
        rr.append(body)
        rr.append("")
    rr += ["## 六条裁决", ""]
    for key in OWNER_PAIRS:
        e = next(x for x in d["entries"] if x["step_key"] == key)
        q = e["ledger_fields_pending_owner"]
        rr.append(f"### {key}")
        rr.append(f"- decision_quality：control=**{q['decision_quality']['control']}**，"
                  f"experiment=**{q['decision_quality']['experiment']}**")
        rr.append(f"- output_validity：control={q['output_validity']['control']}，"
                  f"experiment={q['output_validity']['experiment']}")
        rr.append(f"- 机制：{q['mechanism']}")
        rr.append(f"- 依据：{q['final_note']}")
        rr.append("")
    (P / "A1_OWNER_RULINGS_V1.md").write_text("\n".join(rr), encoding="utf-8")
    print("regenerated A1_ADJUDICATION_V1.md + A1_OWNER_RULINGS_V1.md")
    print(f"control formed={nf_c} {ctl} | indeterminate={ci} | nodec={cn}")
    print(f"experiment formed={nf_e} {exp} | indeterminate={ei} | nodec={en}")


if __name__ == "__main__":
    main()
