# -*- coding: utf-8 -*-
"""Apply batch-3 owner decisions (63 items, 2026-10-10) -> V1_2 table.
Then the 19 remaining needs_source_audit units get a source-context packet
in a separate script."""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
A2R = os.path.join(PREP, "a2_review")

D = {}
def d(sid, var, decision, fs=None, fu=None, gr=None, basis=""):
    D[(sid, var)] = {"decision": decision, "final_status": fs,
                     "final_uses": fu, "globally_reachable": gr, "basis": basis}

# ---- script_100110 (17) ----
d("script_100110", "LandsatColl", "accept_human", "analysis_chain", 4, basis="月份过滤/打印/exImage/LSTmean 共 4 处")
d("script_100110", "landsatTOAcloudmask", "needs_source_audit", basis="静态引用 1（别名未续用）；须先厘清 unconsumed 判定口径：无后继引用 vs 未进入最终结果，不得混用")
d("script_100110", "emptyImage", "accept_human", "analysis_chain", 3, basis="同一绑定重复赋值，三次 paint() 引用累计")
d("script_100110", "data", "accept_human_scope", "analysis_chain", basis="图表数据构造输入；计数须区分全局变量与函数内同名形参")
d("script_100110", "xVals", "accept_human_scope", "analysis_chain", basis="图表数据取值；函数内同名形参为独立绑定")
d("script_100110", "xValLabels", "needs_source_audit", "presentation_only", basis="暂定展示（横轴标签）；计数待核绑定与作用域")
d("script_100110", "xField", "accept_human_scope", "analysis_chain", basis="分组字段选择，具数据分组语义")
d("script_100110", "xLabel", "accept_human", "presentation_only", basis="横轴标题配置")
d("script_100110", "yField", "accept_human_scope", "analysis_chain", basis="统计字段选择语义")
d("script_100110", "yLabel", "accept_human", "presentation_only", basis="纵轴标题配置")
d("script_100110", "getTheChart", "reject_proposed_resolution", "presentation_only", 1, basis="生成界面展示图表；不因参与图表构造即归分析链")
d("script_100110", "maxValue", "needs_source_audit", "analysis_chain", basis="暂保留；需核对更新最大值的读取次数及是否仅用于轴范围")
d("script_100110", "maxMedian", "needs_source_audit", "analysis_chain", basis="暂保留；需核对实际引用位置后定状态与计数")
d("script_100110", "myRows", "needs_source_audit", "presentation_only", basis="暂保留；需确认行数据是纯呈现还是承担后续分析构造")
d("script_100110", "stats", "needs_source_audit", "analysis_chain", basis="暂保留；引用数 18 vs 9 差异必须逐处核对")
d("script_100110", "chart", "reject_proposed_resolution", "presentation_only", 1, basis="图表对象交面板展示")
d("script_100110", "chartPanel", "reject_proposed_resolution", "presentation_only", 3, basis="样式/添加图表/界面挂载均展示")

# ---- script_100133 (22) ----
d("script_100133", "BACKGROUND", "reject_proposed_resolution", "presentation_only", 1, basis="底图类型配置，维持此前裁定")
d("script_100133", "image", "needs_scope_audit", "analysis_chain", basis="回调形参；先确认绑定及其有效引用")
d("script_100133", "legend", "reject_proposed_resolution", "presentation_only", 2, basis="两次构建图例属展示")
d("script_100133", "Ppctfills", "accept_human", "analysis_chain", 1, basis="paint 生成后展示；分析结果构造优先")
d("script_100133", "Afills", "accept_human", "analysis_chain", 1, basis="区域统计绘制生成后展示")
d("script_100133", "AQrange", "accept_human", "presentation_only", 1, basis="仅 PM2.5 图例")
d("script_100133", "empty", "accept_human", "analysis_chain", 4, basis="同作用域重复 var 绑定，四处引用累计")
d("script_100133", "AOIimage", "accept_human", "analysis_chain", 1, basis="paint 生成的分析对象随后展示")
d("script_100133", "data", "needs_source_audit", "analysis_chain", basis="图表数据输入；状态建议待计数审计，不批量接受")
d("script_100133", "xVals", "needs_source_audit", "analysis_chain", basis="图表取值输入；逐绑定核对引用")
d("script_100133", "xValLabels", "needs_source_audit", "presentation_only", basis="暂定展示；计数待核")
d("script_100133", "xField", "needs_source_audit", "analysis_chain", basis="字段选择用途；计数待核")
d("script_100133", "xLabel", "needs_source_audit", "presentation_only", basis="横轴标题；计数待核")
d("script_100133", "yField", "needs_source_audit", "analysis_chain", basis="统计字段选择；计数待核")
d("script_100133", "yLabel", "needs_source_audit", "presentation_only", basis="纵轴标题；计数待核")
d("script_100133", "getTheChart", "reject_proposed_resolution", "presentation_only", 1, basis="生成界面统计图表")
d("script_100133", "maxMedian", "accept_human", "analysis_chain", 3, basis="采用修订后计数 3；旧批次不覆盖修订记录")
d("script_100133", "stats", "accept_human", "analysis_chain", 10, basis="采用修订后计数 10")
d("script_100133", "binary", "accept_human", "analysis_chain", 1, basis="相关性结果；打印不改变分析用途")
d("script_100133", "pop_pctsFiltSort", "accept_human", "analysis_chain", 1, basis="排序数据作散点图分组输入，具数据处理语义")
d("script_100133", "chart", "accept_human_scope", "presentation_only", 1, basis="全局 chart 与函数内局部 chart 为不同绑定")
d("script_100133", "chartPanel", "accept_human", "presentation_only", 3, basis="文件级记录采用目标绑定；另一重复声明裁定记录保留")

# ---- script_100145 (9) ----
d("script_100145", "BU_GHSL", "accept_human", "unconsumed", 0, basis="定义后无后续引用；影像被处理不等于变量被消费")
d("script_100145", "IC", "needs_source_audit", "analysis_chain", basis="visfilter 形参；需逐处区分左值与有效引用")
d("script_100145", "maxbud", "accept_human", "analysis_chain", 2, basis="testcityfilter 输入 + visfilter 输入")
d("script_100145", "yearfilter", "accept_human", "analysis_chain", 7, basis="多分支调用计 7")
d("script_100145", "year", "needs_source_audit", "analysis_chain", basis="多次重赋值；同一绑定累计有效引用，左值不计")
d("script_100145", "GHSL2023releaseYear", "needs_source_audit", "analysis_chain", basis="同作用域多次声明/赋值，逐处核对读取")
d("script_100145", "GHSLyear", "accept_human", "presentation_only", 5, basis="各阈值分支 Map.addLayer 展示")
d("script_100145", "GHSLbud", "needs_source_audit", "analysis_chain", basis="暂定分析（进入 yearfilter/visfilter）；2 vs 9 需复核；源码确认前不锁旧标签 presentation_only")
d("script_100145", "GHSLueyear", "needs_source_audit", "analysis_chain", basis="暂定分析（末尾缓冲处理后展示，或双重用途）；需检查缓冲作用与全部引用位置")

# ---- others (15) ----
d("script_10021", "landsat", "accept_human", "analysis_chain", 2)
d("script_10021", "composite", "accept_human", "analysis_chain", 5, basis="五个读取位置")
d("script_100870", "year_cur", "accept_human", "analysis_chain", 4)
d("script_100870", "collTOres", "accept_human", "analysis_chain", 7, basis="同一全局绑定重复赋值合并，累计 7")
d("script_100870", "collTOres_im", "accept_human", "analysis_chain", 4, basis="四区块分别传入 reduceRegion")
d("script_100870", "collTOres_im_mean", "accept_human", "presentation_only", 4,
  basis="owner 修订：四次统计结果均传入 print()，纯展示（原标注 analysis_chain 修正）")
d("script_100870", "mean_cur", "accept_human", "presentation_only", 4)
d("script_100870", "chart", "accept_human", "presentation_only", 3)
d("script_100870", "l8Layer", "accept_human", "presentation_only", 1)
d("script_100916", "DayStart", "accept_human", "analysis_chain", 2, basis="构造 DayAfterEnd + 图层名称；分析优先")
d("script_101051", "regions", "accept_human", "analysis_chain", 1)
d("script_101051", "temps2013", "accept_human", "analysis_chain", 1)
d("script_101095", "image", "needs_source_audit", "analysis_chain", basis="备注计 4；需按'同一调用表达式接收对象不重复计数'复核")
d("script_101218", "imagen", "accept_human", "analysis_chain", 3, basis="select/mask/return 计 3，不重复计同一调用接收对象")
d("script_25214", "NDVI1", "accept_human", "analysis_chain", 2)


def main():
    in_path = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_1.jsonl")
    rows = [json.loads(l) for l in open(in_path, encoding="utf-8")]
    applied = revised_labels = 0
    for row in rows:
        uid = row["unit_id"]
        sid, var = uid.split(":A2:")
        dec = D.get((sid, var))
        if not dec:
            continue
        row["decision"] = dec["decision"]
        row["final_status"] = dec["final_status"]
        row["final_uses"] = dec["final_uses"]
        row["globally_reachable"] = dec["globally_reachable"]
        row["decision_basis"] = dec["basis"]
        if dec["final_status"] and dec["final_status"] != row["human_status"]:
            row["old_label_modified"] = True
            revised_labels += 1
        applied += 1

    out = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_2.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    from collections import Counter
    pending = [r for r in rows if not r.get("decision")
               and r.get("candidate_cause_category") != "consistent"]
    ns = [r for r in rows if r.get("decision") == "needs_source_audit"]
    dc = Counter(r["decision"] for r in rows if r.get("decision"))
    summary = {
        "batch3_applied": applied,
        "total_decided": sum(dc.values()),
        "decision_distribution": dict(dc),
        "pending_remaining": len(pending),
        "pending_should_be_zero": len(pending) == 0,
        "needs_source_audit_list": [r["unit_id"] for r in ns],
        "human_labels_revised_this_batch": revised_labels,
        "out": os.path.relpath(out, REPO),
    }
    json.dump(summary, open(os.path.join(A2R, "A2_ADJUDICATION_V1_2_SUMMARY.json"),
                            "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
