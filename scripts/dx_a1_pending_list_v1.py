#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit A1_PENDING_ADJUDICATION_V1.md: the 46 pairs still on agent verdicts,
tiered by consequence, each with dossier path + agent verdict + the question for
the owner."""
import json
from pathlib import Path

P = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/a1_short/A1_FULL_EVIDENCE_PACKET_V1")

TIER_A = {
 # verdict moves the core conclusion / non-obvious agent call
 "PCA2-T-083#S7": "算子替换判定：对照'加载预训练模型'卡面未载(不可判)、实验 imageclassifier 卡明确(model file + probamap)——请确认实验=正确/对照=不可判",
 "PCA2-T-001#S3": "补卡解锁候选①：concatenateimages 卡新增'同尺寸图像列表→多通道图像'；请确认正确选择",
 "PCA2-T-025#S5": "补卡解锁候选②：contrastenhancement 卡新增 minmax.manual.min/max；请确认正确选择",
 "PCA2-T-003#S2": "补卡解锁候选③：opticalcalibration 卡新增 TOA/TOC+手动参数；请确认（参照 T-032 的 R1 尺度：本步仅要 DN→反射率，无大气校正附加要求）",
 "PCA2-T-057#S4": "补卡解锁候选④：compareimages 卡新增 ref.in/meas.in + mse/mae/psnr；请确认正确选择",
 "PCA2-T-046#S5": "正确→正确（选择保持但实验臂双选 concatenatevectordata+mergevectorlayers，冗余）——请确认双选是否仍算正确",
 "PCA2-T-001#S6": "对照判错（mosaicking 做资产打包）→实验合理弃权；请确认对照的'错误选择'标签",
 "PCA2-T-056#S3": "实验判错（部分匹配：镶嵌≠波段堆叠）；请确认是否按 R1 复合步骤口径判错",
 "PCA2-T-026#S4": "对照判错（native:rasterize 卡=渲染地图画布，非多栅格合成）；请确认",
 "PCA2-T-098#S6": "对照判错（resamplingfilter=空间低通，非时间序列平滑）；请确认",
 "PCA2-T-046#S4": "对照正确（joinattributestable 一对多展开）→实验截断；请确认对照正确",
 "PCA2-T-089#S4": "对照正确（morphologicalfilter 卡含 METHOD/KERNEL）→实验截断；请确认",
 "PCA2-T-092#S2": "对照正确（clouddetection 输出 CLOUDS 掩膜）→实验截断；请确认（掩膜应用属平凡组合的尺度是否接受）",
 "PCA2-T-033#S1": "实验正确但所用算子卡未变（gdal:rearrange_bands）——上下文诱发，按 R5 不能归因补卡；请确认判定",
 "PCA2-T-025#S4": "实验正确但所用算子卡未变（saga:statisticsforrasters GRIDS→MEAN）——上下文诱发；请确认",
 "PCA2-T-068#S6": "实验正确但所用算子卡未变（native:aggregate GROUP_BY）——上下文诱发；请确认",
 "PCA2-T-070#S1": "实验正确但所用算子卡未变（saga:resampling extent 参数）——'有条件正确'是否成立；请确认",
 "PCA2-T-022#S6": "实验不可判（r.blend.rgb 混合三栅格 vs 从多波段提取 RGB，取决于步骤 5 输出结构）；请确认判不可判或错误",
}


def main():
    d = json.loads((P / "LEDGER_V1.json").read_text(encoding="utf-8"))
    pend = [e for e in d["entries"]
            if e["ledger_fields_pending_owner"].get("status") != "owner_ruled"]

    def line(e):
        q = e["ledger_fields_pending_owner"]
        dossier = f"{e['batch']}_{e['step_key'].replace('#', '_')}.md"
        return (f"| {e['step_key']} | {q['decision_quality']['control']} | "
                f"{q['decision_quality']['experiment']} | "
                f"{q['output_validity']['control']}/{q['output_validity']['experiment']} | "
                f"[{dossier}]({dossier}) | {q['final_note'][:90]} |")

    a = [e for e in pend if e["step_key"] in TIER_A]
    b = [e for e in pend if e["step_key"] not in TIER_A]

    md = ["# A1 待 owner 裁决清单 V1（46 对）", "",
          "位置：本目录 `A1_FULL_EVIDENCE_PACKET_V1/`。每对一卷宗（任务全文/步骤定义/Top-10/"
          "双版本卡面/双臂完整决策）。裁决写入 `LEDGER_V1.json` 对应条目的 "
          "`ledger_fields_pending_owner`（decision_quality × output_validity × mechanism）。", "",
          f"已裁决 6/52（owner_ruled）；待裁决 {len(pend)} 对。", "",
          "## A 级：裁决会改变结论或 agent 判定非显然（18 对，建议先做）", "",
          "| 步骤 | 对照(agent) | 实验(agent) | validity | 卷宗 | 待你裁的问题 |",
          "|---|---|---|---|---|---|"]
    for e in sorted(a, key=lambda x: (x["batch"], x["step_key"])):
        q = e["ledger_fields_pending_owner"]
        dossier = f"{e['batch']}_{e['step_key'].replace('#', '_')}.md"
        md.append(f"| {e['step_key']} | {q['decision_quality']['control']} | "
                  f"{q['decision_quality']['experiment']} | "
                  f"{q['output_validity']['control']}/{q['output_validity']['experiment']} | "
                  f"[{dossier}]({dossier}) | {TIER_A[e['step_key']]} |")
    md += ["", "## B 级：低杠杆（多为弃权/截断标签确认，28 对）", "",
           "| 步骤 | 对照(agent) | 实验(agent) | validity | 卷宗 | agent 依据 |",
           "|---|---|---|---|---|---|"]
    for e in sorted(b, key=lambda x: (x["batch"], x["step_key"])):
        md.append(line(e))
    md += ["", "## 裁决口径（已冻结）", "",
           "R1 复合步骤闭合；R2 截断≠无判定（截断→validity=截断+不可判，空输出才是无判定，"
           "不得追溯补答）；R3 笔误不改算子身份；R4 卡面字段完整度≠证据完整度；"
           "R5 因果归因保守（改善≠补卡解锁）。", "",
           "裁决不需要重写卷宗：在回复中按『步骤 | control | experiment | mechanism』"
           "给出即可，由账本脚本落库。"]
    (P / "A1_PENDING_ADJUDICATION_V1.md").write_text("\n".join(md), encoding="utf-8")
    print("pending:", len(pend), "| tier A:", len(a), "| tier B:", len(b))


if __name__ == "__main__":
    main()
