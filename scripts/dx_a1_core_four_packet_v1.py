#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the core-four packet (owner priority: T-003#S2, T-001#S3,
T-025#S5, T-057#S4) - the four remaining candidates that could support
'card completion unlocks correct selection'. Each entry: step definition,
selected operator's v0_4 + v0_5 cards verbatim, both arms' complete decision
sections, and the precise question for the owner."""
import json
import re
from pathlib import Path

P = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/a1_short/A1_FULL_EVIDENCE_PACKET_V1")
CORE = ["PCA2-T-003#S2", "PCA2-T-001#S3", "PCA2-T-025#S5", "PCA2-T-057#S4"]
SELECTED = {"PCA2-T-003#S2": "otb:opticalcalibration",
            "PCA2-T-001#S3": "otb:concatenateimages",
            "PCA2-T-025#S5": "otb:contrastenhancement",
            "PCA2-T-057#S4": "otb:compareimages"}
QUESTION = {
 "PCA2-T-003#S2": "步骤=DN→物理反射率（单一定标，无大气校正附加要求）。v0_5 卡写明 TOA/TOC + "
                  "手动参数通路（Landsat 不在内置传感器表）。是否判『正确选择』？"
                  "（请对照 T-032 的 R1 判定：那一步复合了大气校正，故降为不可判。）",
 "PCA2-T-001#S3": "步骤=把多次获取按时相堆叠（逐像元跨通道统计的前提）。v0_5 卡：'Concatenate a "
                  "list of images of the same size into a single multi-channel image'，参数 il(InputImageList)。"
                  "是否判『正确选择』？是否接受『堆叠』由多通道拼接实现？"
                  "备注：对照臂为截断（think 内已倾向 concatenateimages，但无闭合决策）。",
 "PCA2-T-025#S5": "步骤=把 −25/5 dB 线性拉伸用于可视化。v0_5 卡：直方图均衡实现，含 "
                  "minmax.manual.min / minmax.manual.max 参数。是否判『正确选择』？"
                  "（是否存在『直方图均衡≠线性拉伸』的语义差需要扣分？）",
 "PCA2-T-057#S4": "步骤=对两幅影像计算均方误差（MSD，两个标量输出）。v0_5 卡：'Estimator between "
                  "2 images'，ref.in/meas.in 双输入，mse/mae/psnr 输出参数。是否判『正确选择』？"
                  "（注意卡面 outputs 行写 none documented，mse 以参数形式出现。）",
}


def block(text, label, cap=2600):
    m = re.search(re.escape(label) + r"\n```\n(.*?)\n```", text, re.S)
    return m.group(1).strip()[:cap] if m else "(missing)"


def card_block(text, oid, version_label):
    m = re.search(re.escape(f"#### {oid} — {version_label}") + r"\n```\n(.*?)\n```",
                  text, re.S)
    return m.group(1).strip() if m else "(missing)"


def run_facts(key):
    """gen.json facts for both arms (tokens / term / maxnew) + ledger validity."""
    import json as _j
    ctrl = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/dx50_short/runs")
    exp = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/_a1_work/runs_local")
    tid, s = key.split("#S")
    out = []
    for label, base in (("control", ctrl), ("experiment", exp)):
        d = base / tid / "S2" / f"S{s}"
        g = _j.loads((d / "gen.json").read_text(encoding="utf-8"))
        out.append(f"{label}: gen_tokens={g.get('gen_tokens')}/{g.get('maxnew')} "
                   f"term={g.get('term')}")
    return "; ".join(out)


def main():
    out = ["# A1 核心四对复核包 V1（补卡解锁正向候选）", "",
           "owner 指定优先级：T-003#S2 / T-001#S3 / T-025#S5 / T-057#S4。"
           "四对能否成立，直接决定『卡片补全是否解锁正确选择』的核心结论。", "",
           "裁决格式：`步骤 | control | experiment | mechanism`（可直接回复）。", ""]
    for key in CORE:
        f = next(P.glob(f"*_{key.replace('#', '_')}.md"))
        t = f.read_text(encoding="utf-8")
        oid = SELECTED[key]
        facts = run_facts(key)
        cap_note = ("注：gen_tokens 达 maxnew 的臂按 R2 记 output_validity=截断；"
                    "若 SELECT/NOT 行已完整出现，截断只影响尾部列表——请按 R2 裁定。")
        out += [f"# {key}", "", f"**请裁问题**：{QUESTION[key]}", "",
                f"**运行事实**：{facts}", "", cap_note, ""]
        st = re.search(r"\*\*Step (\d+)\*\*：(.+)", t)
        if st:
            out += ["## 步骤定义", "", st.group(0).replace("**Step", "Step").replace("**：", "："), ""]
        m = re.search(r"\*\*Task \w+ 全文\*\*：\n\n(.+?)\n\n\*\*Step", t, re.S)
        if m:
            out += ["## 任务全文", "", m.group(1)[:900], ""]
        m = re.search(r"## 候选集合.*?\n(.*?)\n## ", t, re.S)
        if m:
            out += ["## 候选集合（Top-10）", "", " ".join(
                x.strip() for x in m.group(1).splitlines() if x.strip()), ""]
        c4 = card_block(t, oid, "v0_4 卡（对照臂所见）")
        c5 = card_block(t, oid, "v0_5 卡（实验臂所见）")
        out += [f"## 所选算子 `{oid}` 双版本卡面", "", "### v0_4（对照臂所见）", "```", c4, "```", "",
                "### v0_5（实验臂所见）", "```", c5, "```", ""]
        out += ["## 对照臂完整决策段", "```", block(t, "对照臂 (v0_4) 完整决策段"), "```", "",
                "## 实验臂完整决策段", "```", block(t, "实验臂 (v0_5) 完整决策段"), "```", "",
                "---", ""]
    (P / "A1_CORE_FOUR_PACKET_V1.md").write_text("\n".join(out), encoding="utf-8")
    print("written:", (P / "A1_CORE_FOUR_PACKET_V1.md").name)


if __name__ == "__main__":
    main()
