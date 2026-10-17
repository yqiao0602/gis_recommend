#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 adjudication (agent pass V1, pending owner spot-check).

Applies the frozen rules (A1_OWNER_ADJUDICATION_V1.md) to the 52 dossiers:
decision_quality in {correct, wrong, reasonable_abst, wrong_abst, indeterminate}
+ orthogonal output_validity; mechanism per preregistered buckets. NODEC never
enters the four metrics. Fills LEDGER_V1.json and emits A1_ADJUDICATION_V1.md.
"""
import json
from collections import Counter
from pathlib import Path

P = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/a1_short/A1_FULL_EVIDENCE_PACKET_V1")
LEDGER = P / "LEDGER_V1.json"

# (control, experiment, mechanism, note)   quality keys:
#   C correct, W wrong, RA reasonable abstention, WA wrong abstention,
#   IND indeterminate, NODEC handled separately
A = {
"PCA2-T-009#S3": ("RA","W","补卡诱发错误选择（间接/上下文）",
 "multibandvariation 卡输出仅 MEAN/STDDEV/DIFF（纯统计），步骤要求 NDVI/NDSI 波段运算；所选算子卡未变——其余 OTB 候选卡面变化诱发错误选择"),
"PCA2-T-009#S6": ("RA","IND","其他（待 P2 enum 证据）",
 "卡面证明分类器训练+模型文件输出+矢量/特征/类别字段；classifier(Choice) 选项未展开（CART 不可见）——owner 的'足以证明算法选择'门槛未达成，不能凭外部知识升级为正确"),
"PCA2-T-042#S1": ("RA","NODEC","生成波动","数据获取步骤（GPM IMERG）无算子；实验臂空输出"),
"PCA2-T-056#S5": ("RA","NODEC","生成波动","RF 训练能力候选全无记载；实验臂无判定"),
"PCA2-T-056#S6": ("RA","IND","其他（待 P2/官方文档）",
 "所选 supervisedclassificationforrasters 卡载 FILE_LOAD(file) 无语义、METHOD 枚举未展开——能否加载预训练 RF 不可由卡面证实"),
"PCA2-T-083#S6": ("RA","NODEC","生成波动","RF-from-vector 不可见；实验臂无判定"),
"PCA2-T-083#S7": ("IND","C","选择保持（算子替换、实验臂证据更充分）",
 "对照 supervisedclassificationforrasters 的'加载预训练模型'语义卡面未载（不可判）；实验 otb:imageclassifier 卡明载 'classification according to a model file' + probamap/confmap 输出，与步骤'概率或离散分类输出'完全匹配"),
"PCA2-T-084#S2": ("NODEC","RA","其他（能力边界经卡面明确化）",
 "候选无阈值重分类能力（regularization=众数平滑）；实验弃权合理"),
"PCA2-T-084#S5": ("RA","NODEC","生成波动","冷气候例外覆盖需双输出掩膜；实验臂无判定"),
"PCA2-T-090#S4": ("NODEC","W","生成波动（大小写笔误→越选）",
 "实验臂输出 'otc:ImageClassifier'（应为 otb:imageclassifier），OOC 按预注册判错"),
"PCA2-T-092#S9": ("NODEC","RA","其他（能力边界经卡面明确化）",
 "步骤同时要求平滑+混淆矩阵/精度报告；候选仅覆盖平滑——弃权合理"),

"PCA2-T-001#S3": ("NODEC","C","补卡解锁正确选择",
 "concatenateimages v0_5 卡：'list of images of the same size into a single multi-channel image'——正是逐像元跨时相堆叠；所选算子卡面变化"),
"PCA2-T-001#S4": ("RA","NODEC","生成波动","候选无 SAR 斑点滤波；实验臂无判定"),
"PCA2-T-001#S5": ("NODEC","RA","其他","候选无跨影像中值合成（镶嵌≠中值）；弃权合理"),
"PCA2-T-001#S6": ("W","RA","其他（对照错误被纠正为合理弃权）",
 "对照选 mosaicking（属上一步功能，非资产打包/导出）→ 错误；实验合理弃权（候选无栅格资产导出）"),
"PCA2-T-025#S5": ("NODEC","C","补卡解锁正确选择",
 "contrastenhancement v0_5 卡含 minmax.manual.min/max——与步骤 -25/5 dB 线性拉伸精确匹配；所选算子卡面变化"),
"PCA2-T-046#S4": ("C","NODEC","生成波动（正确→无判定）",
 "对照 joinattributestable 一对多展开与步骤匹配；实验臂 think 未闭合截断"),
"PCA2-T-046#S5": ("C","C","选择保持（实验臂增加冗余算子）",
 "mergevectorlayers 与 concatenatevectordata 均满足展平合并；双选冗余但皆正确"),
"PCA2-T-056#S3": ("NODEC","W","补卡诱发错误选择（部分匹配/上下文）",
 "步骤含 Band Stacking + Mosaic 两半；mosaicking 卡仅空间镶嵌（FILE_LIST/TARGET_OUT_GRID），无波段堆叠证据——所选算子未变，属上下文诱发"),
"PCA2-T-060#S1": ("RA","NODEC","生成波动","无可做 tile 划分的候选；实验臂无判定"),
"PCA2-T-062#S4": ("RA","NODEC","生成波动","交互式查看属架构层；实验臂无判定"),
"PCA2-T-073#S1": ("RA","NODEC","生成波动","无昼夜均值合成算子；实验臂无判定"),
"PCA2-T-079#S5": ("NODEC","RA","其他","可视化制图超出处理算子；弃权合理"),
"PCA2-T-086#S4": ("RA","NODEC","生成波动","无堆叠+逐像元计数的复合能力；实验臂无判定"),
"PCA2-T-089#S5": ("RA","NODEC","生成波动","无掩膜+DEM 条件精化；实验臂无判定"),
"PCA2-T-092#S5": ("RA","NODEC","生成波动","无相干性计算；实验臂无判定"),

"PCA2-T-003#S2": ("NODEC","C","补卡解锁正确选择",
 "opticalcalibration v0_5 卡：TOA/TOC 定标+手动参数通路（Landsat 不在内置传感器列表但有手动通路）；所选算子卡面变化"),
"PCA2-T-005#S3": ("NODEC","RA","其他","云量百分比不可得（clouddetection 仅二值掩膜）；弃权合理"),
"PCA2-T-005#S5": ("IND","IND","生成波动（自相矛盾输出）",
 "实验臂同时输出 SELECT r.mask.vect 与 NO OPERATOR（语义自相矛盾）；对照 r.mask.vect 卡无参数/输出记载（不可判）"),
"PCA2-T-012#S3": ("NODEC","RA","其他","候选无跨时相均值；弃权合理"),
"PCA2-T-021#S4": ("RA","NODEC","生成波动","无多掩膜融合；实验臂无判定"),
"PCA2-T-022#S6": ("RA","IND","其他（待输入结构）",
 "r.blend.rgb 为三栅格混合成 RGB；若输入为多波段合成体则需波段提取而非混合——取决于步骤 5 输出结构"),
"PCA2-T-025#S4": ("NODEC","C","其他（上下文诱发正确选择）",
 "statisticsforrasters 卡：GRIDS 多层输入 + MEAN 输出——跨栅格均值成立（所选算子卡未变）"),
"PCA2-T-026#S4": ("W","NODEC","生成波动（对照错误→无判定）",
 "对照 native:rasterize 卡描述=渲染地图画布，并非多栅格合成；判错"),
"PCA2-T-032#S2": ("RA","C","补卡解锁正确选择（owner 核心判据命中）",
 "步骤要求定标+大气校正；opticalcalibration 卡载 TOA/TOC（TOC 覆盖大气校正通路）；所选算子卡面变化——本对=合理弃权→正确选择"),
"PCA2-T-033#S1": ("NODEC","C","其他（上下文诱发正确选择）",
 "rearrange_bands 卡含 BANDS 波段索引参数——波段提取成立（所选算子卡未变）"),
"PCA2-T-052#S2": ("RA","NODEC","生成波动",
 "候选 native:polygonize 卡面 accepts=vector（栅格→矢量未由卡面证实）——弃权与卡面一致；实验臂无判定"),
"PCA2-T-056#S2": ("NODEC","RA","其他","候选中值合成能力缺（averagewithmask1=均值）；弃权合理"),
"PCA2-T-056#S4": ("NODEC","RA","其他","候选无样点光谱提取到特征表；弃权合理"),
"PCA2-T-057#S4": ("NODEC","C","补卡解锁正确选择",
 "compareimages v0_5 卡含 ref.in/meas.in 双输入与 mse/mae/psnr 输出参数——MSD 计算成立；所选算子卡面变化"),
"PCA2-T-068#S4": ("NODEC","WA","上下文诱发误弃权",
 "候选 grass7:r.statistics 卡载 base+cover+method（分区统计），完全满足按公园多边形统计类别像元数——弃权错误（对照臂 think 内已自行找到该算子后截断）"),
"PCA2-T-068#S6": ("NODEC","C","其他（上下文诱发正确选择）",
 "native:aggregate 卡 GROUP_BY+AGGREGATES——按公园分区聚合损失成立(所选算子卡未变)"),
"PCA2-T-070#S1": ("NODEC","C","其他（上下文诱发正确选择）",
 "saga:resampling 卡含 TARGET_USER_* extent 参数——可达 ROI 对齐裁剪（所选算子卡未变，注意重采样≠裁剪的语义差）"),
"PCA2-T-079#S3": ("RA","NODEC","生成波动",
 "variabledistancebuffer=单缓冲按字段距离，非多级同心环；弃权合理；实验臂无判定"),
"PCA2-T-080#S4": ("RA","NODEC","生成波动","候选无 BAI/BAIS2/TBR 指数；弃权合理；实验臂无判定"),
"PCA2-T-081#S5": ("NODEC","RA","其他","无掩膜+DEM 条件精化；弃权合理"),
"PCA2-T-084#S4": ("NODEC","RA","其他","候选与 hs_ratio+纬度带输入不匹配；弃权合理"),
"PCA2-T-086#S5": ("RA","NODEC","生成波动","无逐像元观测频次统计；实验臂无判定"),
"PCA2-T-089#S4": ("C","NODEC","生成波动（正确→无判定）",
 "对照 saga:morphologicalfilter 卡含 METHOD/KERNEL——形态学滤波与步骤匹配；实验臂 think 未闭合"),
"PCA2-T-092#S2": ("C","NODEC","生成波动（正确→无判定）",
 "对照 saga:clouddetection 卡输出 CLOUDS 掩膜（云识别核心能力；掩膜应用属平凡组合）；实验臂 think 未闭合"),
"PCA2-T-098#S1": ("RA","NODEC","生成波动","候选无 QA 条件去云；弃权合理"),
"PCA2-T-098#S6": ("W","NODEC","生成波动（对照错误→无判定）",
 "对照 resamplingfilter=LOPASS/HIPASS 空间滤波（SCALE 参数），非时间序列平滑；判错"),
}

VALIDITY = {"NODEC": "no_decision", "IND": "valid_but_indeterminate"}
DEC = {"C": "correct_selection", "W": "wrong_selection",
       "RA": "reasonable_abstention", "WA": "wrong_abstention",
       "IND": "indeterminate", "NODEC": "n/a_no_decision"}


def main():
    d = json.loads(LEDGER.read_text(encoding="utf-8"))
    for e in d["entries"]:
        ctl, exp, mech, note = A[e["step_key"]]
        e["ledger_fields_pending_owner"] = {
            "status": "agent_adjudication_v1_pending_owner_spotcheck",
            "decision_quality": {"control": DEC[ctl], "experiment": DEC[exp]},
            "output_validity": {
                "control": "valid" if ctl in ("C", "W", "RA", "WA", "IND")
                else "no_decision",
                "experiment": ("self_contradictory"
                               if e["step_key"] == "PCA2-T-005#S5"
                               else ("valid" if exp in ("C", "W", "RA", "WA", "IND")
                                     else "no_decision"))},
            "mechanism": mech, "final_note": note, "confidence": "medium-high",
        }
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    # metrics
    def tally(arm):
        c = Counter(e["ledger_fields_pending_owner"]["decision_quality"][arm]
                    for e in d["entries"])
        return c

    ctl, exp = tally("control"), tally("experiment")
    def rates(c):
        formed = c["correct_selection"] + c["wrong_selection"] + \
                 c["reasonable_abstention"] + c["wrong_abstention"]
        return {
            "n_formed": formed,
            "correct": c["correct_selection"],
            "wrong": c["wrong_selection"],
            "reasonable_abst": c["reasonable_abstention"],
            "wrong_abst": c["wrong_abstention"],
            "indeterminate": c["indeterminate"],
            "no_decision": c["n/a_no_decision"],
            "correct_rate": round(c["correct_selection"] / formed, 4) if formed else None,
            "wrong_rate": round(c["wrong_selection"] / formed, 4) if formed else None,
            "reasonable_abst_rate": round(c["reasonable_abstention"] / formed, 4) if formed else None,
            "wrong_abst_rate": round(c["wrong_abstention"] / formed, 4) if formed else None,
            "indeterminate_rate": round(c["indeterminate"] / formed, 4) if formed else None,
        }

    trans = Counter()
    for e in d["entries"]:
        q = e["ledger_fields_pending_owner"]["decision_quality"]
        trans[(q["control"], q["experiment"])] += 1

    mech = Counter(e["ledger_fields_pending_owner"]["mechanism"].split("（")[0]
                   for e in d["entries"])
    summary = {"control": rates(ctl), "experiment": rates(exp),
               "transitions": {f"{a} -> {b}": n for (a, b), n in trans.items()},
               "mechanisms": dict(mech)}
    (P / "A1_ADJUDICATION_SUMMARY_V1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    rows = []
    for e in d["entries"]:
        q = e["ledger_fields_pending_owner"]
        rows.append(f"| {e['step_key']} | {e['batch']} | "
                    f"{q['decision_quality']['control']} | "
                    f"{q['decision_quality']['experiment']} | {q['mechanism']} |")
    md = ["# A1 逐对裁决 V1（agent 裁决，待 owner 抽检）", "",
          "规则：A1_OWNER_ADJUDICATION_V1.md（POS≠正确、ABST≠合理、NODEC 不入四指标、OOC=错误）。"
          "裁决依据=全证据卷宗（任务/候选/双版本卡面/双臂完整决策）。", "",
          "## 四指标", "",
          "| 指标 | 对照 v0_4 | 实验 v0_5 |", "|---|---|---|",
          f"| 形成判定步数 | {summary['control']['n_formed']} | {summary['experiment']['n_formed']} |",
          f"| 正确选择 | {ctl['correct_selection']} ({summary['control']['correct_rate']:.1%}) | "
          f"{exp['correct_selection']} ({summary['experiment']['correct_rate']:.1%}) |",
          f"| 错误选择 | {ctl['wrong_selection']} ({summary['control']['wrong_rate']:.1%}) | "
          f"{exp['wrong_selection']} ({summary['experiment']['wrong_rate']:.1%}) |",
          f"| 合理弃权 | {ctl['reasonable_abstention']} ({summary['control']['reasonable_abst_rate']:.1%}) | "
          f"{exp['reasonable_abstention']} ({summary['experiment']['reasonable_abst_rate']:.1%}) |",
          f"| 误弃权 | {ctl['wrong_abstention']} ({summary['control']['wrong_abst_rate']:.1%}) | "
          f"{exp['wrong_abstention']} ({summary['experiment']['wrong_abst_rate']:.1%}) |",
          f"| 证据不足不可判 | {ctl['indeterminate']} ({summary['control']['indeterminate_rate']:.1%}) | "
          f"{exp['indeterminate']} ({summary['experiment']['indeterminate_rate']:.1%}) |",
          f"| 无判定（不计入四指标） | {ctl['n/a_no_decision']} | {exp['n/a_no_decision']} |",
          "", "## 配对转移（裁决后）", ""]
    for k, v in sorted(trans.items(), key=lambda x: -x[1]):
        md.append(f"- {k}: {v}")
    md += ["", "## 机制分布", ""]
    for k, v in mech.most_common():
        md.append(f"- {k}: {v}")
    md += ["", "## 逐对裁决", "",
           "| 步骤 | 批次 | 对照 | 实验 | 机制 |", "|---|---|---|---|---|"] + rows
    md += ["", "## 对 owner 核心判据的回应", "",
           "**核心判据**：找到可复核证据组，证明卡面变化使模型从合理弃权转向正确选择，"
           "且错误选择不明显增加。", "",
           "- 直接命中 1 对：**T-032#S2**（ABST→POS opticalcalibration，卡面新增 TOA/TOC "
           "与手动参数通路）——合理弃权→正确选择。",
           "- 另有 4 对由从未形成判定（NODEC）→正确选择且所选算子卡面确有变化："
           "T-001#S3、T-025#S5、T-003#S2、T-057#S4（补卡解锁正确选择 5 对含 T-032#S2）。",
           "- 4 对正确选择来自**未改卡算子**（上下文诱发：T-033#S1、T-025#S4、T-068#S6、"
           "T-070#S1）——不是补卡解锁，须单列。",
           "- **错误选择数不变（3→3），但为完全置换**：对照的 3 个错误全部消失"
           "（T-001#S6 以 mosaicking 做打包→纠正为合理弃权；T-026#S4 native:rasterize 与"
           "T-098#S6 空间低通冒充时间平滑→实验臂因无判定未形成决策）；实验的 3 个错误全为新出现"
           "（T-009#S3 补卡诱发、T-090#S4 笔误越选、T-056#S3 部分匹配）。"
           "**无正确选择被破坏为错误选择**；3 个对照正确步变为无判定"
           "（生成侧截断：T-046#S4、T-089#S4、T-092#S2）。",
           "- **新增 1 例误弃权**（T-068#S4：grass7:r.statistics 卡面已足够，候选未变，"
           "上下文变化诱发弃权）。",
           "- 结论（预注册解释表第一行，附边界）：正确选择 4→11、错误选择 3→3——支持"
           "『卡片知识补全对当前样本有帮助』；但增益大部分来自『无判定→正确』，"
           "『合理弃权→正确』仅 1 对直接成立；同时 NODEC 略增（21→22）且出现 1 例新误弃权。"]
    (P / "A1_ADJUDICATION_V1.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
