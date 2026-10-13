# -*- coding: utf-8 -*-
"""Transcribe annotator-1 final rulings into the results file.

MECHANICAL TRANSCRIPTION ONLY: values below are verbatim from the
annotator's finalized tables; no judgment is added, altered, or filled in.
Unfinalized units stay null in the results file.

Batch 1 (2026-10-10): script_7900 A2 finals (53/53 units), as ruled by
annotator 1 (owner). A1 and A3 for this script remain pending per the
annotator's explicit scoping.
"""

import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                  "expansion_validation_prep_v1", "annotator1_workspace_v1")

ANNOTATOR = "annotator1_owner"
BATCH_DATE = "2026-10-10"

# script_7900 A2 finals — verbatim from annotator 1's finalized table
A2_7900 = {
    "image": ("analysis_chain", 2, "形参(cloudMask)；仅统计其所属函数内引用。"
              "注意: NDVI/EVI/NBR 中另有同名形参，文件级单位与之合并——留待 F2 开封裁定"),
    "cloudMask": ("analysis_chain", 1, "传入 .map(cloudMask)"),
    "cloudShadowBitMask": ("analysis_chain", 1, "用于云影位掩膜"),
    "cloudsBitMask": ("analysis_chain", 1, "用于云位掩膜"),
    "qa": ("analysis_chain", 2, "用于两次位运算筛选"),
    "NDVI": ("analysis_chain", 1, "传入 .map(NDVI)"),
    "ndvi": ("analysis_chain", 1, "传入 addBands()"),
    "EVI": ("analysis_chain", 2, "函数先用于 .map(EVI)；之后同名变量被重新赋值为 EVI 影像并导出"),
    "evi": ("analysis_chain", 1, "传入 addBands()"),
    "NBR": ("unconsumed", 0, "函数已定义，但完整源码中没有调用"),
    "nbr": ("analysis_chain", 1, "保留区别: 仅函数内部链，父函数 NBR 未调用——局部存在、全局不可达，"
            "不描述为实际运行的分析步骤"),
    "scale": ("unconsumed", 0, "未使用；区域统计实际使用字面量 scale: 300"),
    "dem": ("analysis_chain", 2, "用于坡度和坡向计算"),
    "degree2radian": ("unconsumed", 0, "完整源码中没有引用；角度转换直接使用数值常量"),
    "img": ("analysis_chain", 8, "形参(illuminationCondition)；用于太阳角度、几何范围与输出影像构建"),
    "illuminationCondition": ("analysis_chain", 1, "传入 .map(illuminationCondition)"),
    "SZ_rad": ("analysis_chain", 2, "用于余弦、正弦计算"),
    "SA_rad": ("analysis_chain", 1, "用于方位角差计算"),
    "slp": ("analysis_chain", 1, "加入输出影像的 slope 波段"),
    "slp_rad": ("analysis_chain", 2, "用于坡面余弦、正弦计算"),
    "asp_rad": ("analysis_chain", 1, "用于方位角差计算"),
    "cosZ": ("analysis_chain", 2, "用于照度计算并加入影像"),
    "cosS": ("analysis_chain", 3, "用于照度计算并加入影像"),
    "slope_illumination": ("analysis_chain", 1, "与坡向照度相加"),
    "sinZ": ("analysis_chain", 2, "用于坡向照度计算"),
    "sinS": ("analysis_chain", 1, "用于坡向照度计算"),
    "cosAziDiff": ("analysis_chain", 1, "用于坡向照度计算"),
    "aspect_illumination": ("analysis_chain", 1, "参与合成照度计算"),
    "ic": ("analysis_chain", 2, "用于合成照度波段并加入影像"),
    "illuminationCorrection": ("analysis_chain", 1, "传入 .map(illuminationCorrection)"),
    "props": ("analysis_chain", 1, "用于 setMulti(props) 恢复影像属性"),
    "st": ("analysis_chain", 1, "用于恢复 system:time_start"),
    "img_plus_ic": ("analysis_chain", 7, "illuminationCondition 内定义；用于掩膜、波段选择及影像合成。"
                    "注意: illuminationCorrection 内另有同名局部绑定(第109行 img_plus_ic = img)——文件级单位合并，留待 F2"),
    "mask1": ("unconsumed", 0, "构建后没有使用；实际使用的是 mask2"),
    "mask2": ("analysis_chain", 1, "用于 updateMask(mask2)"),
    "img_plus_ic_mask2": ("analysis_chain", 7, "用于区域统计、校正表达式及波段选择"),
    "bandList": ("analysis_chain", 4, "用于移除波段、映射校正函数、构造波段列表及恢复波段"),
    "compositeBands": ("analysis_chain", 1, "用于 removeAll(bandList)"),
    "nonCorrectBands": ("analysis_chain", 1, "用于输出影像的 addBands()"),
    "geom": ("unconsumed", 0, "几何范围被构建，但没有后继使用"),
    "apply_SCSccorr": ("analysis_chain", 1, "传入 bandList.map()"),
    "band": ("analysis_chain", 3, "形参(apply_SCSccorr)；用于波段选择及校正表达式；按局部作用域统计"),
    "method": ("unconsumed", 0, "赋值为 'SCSc' 后未使用"),
    "out": ("analysis_chain", 4, "用于空值判断和提取拟合系数"),
    "out_a": ("analysis_chain", 1, "用于计算 out_c"),
    "out_b": ("analysis_chain", 1, "用于计算 out_c"),
    "out_c": ("analysis_chain", 1, "用于校正表达式的 cvalue 参数"),
    "SCSc_output": ("analysis_chain", 1, "用于返回校正后的影像"),
    "img_SCSccorr": ("analysis_chain", 2, "用于波段恢复并返回结果"),
    "bandList_IC": ("analysis_chain", 1, "用于恢复波段时的选择"),
    "landsat8": ("analysis_chain", 3, "包含自引用读取、打印和合成输入读取。保留区别: A2 的 analysis_chain "
                 "不代表 A1 的定义来源问题已解决"),
    "landsat8_composite": ("analysis_chain", 4, "用于构建掩膜、更新掩膜、地图展示及提取 EVI"),
    "mask": ("analysis_chain", 1, "第 217 行绑定，用于 updateMask(mask)。注意: cloudMask 函数内第 9 行"
             "另有同名绑定(用于第 13 行)——文件级单位合并，留待 F2"),
}

FILLED = {
    "script_7900:A2:": A2_7900,
}


def main():
    template_path = os.path.join(WS, "results", "annotation_results_template_v1.jsonl")
    rows = [json.loads(l) for l in open(template_path, encoding="utf-8") if l.strip()]

    filled_n = 0
    for r in rows:
        for prefix, table in FILLED.items():
            if r["unit_id"].startswith(prefix):
                var = r["unit_id"][len(prefix):]
                if var in table:
                    status, uses, note = table[var]
                    r["human"] = status
                    r["uses_count"] = uses
                    r["note"] = note
                    r["annotator"] = ANNOTATOR
                    r["date"] = BATCH_DATE
                    r["batch"] = "batch1_script_7900_A2"
                    filled_n += 1

    ts = datetime.now().strftime("%Y%m%dT%H%M")
    out = os.path.join(WS, "results", f"annotation_results_v1_{ts}.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps({
        "results_file": os.path.relpath(out, REPO),
        "units_total": len(rows),
        "units_filled_this_batch": filled_n,
        "scope": "script_7900 A2 only (annotator's explicit scoping); "
                 "A1/A3 for this script still pending",
        "transcription": "mechanical values only; no judgment added",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
