# -*- coding: utf-8 -*-
"""Apply owner's 81 unit-level A2 adjudication decisions (2026-10-10).

Produces A2_ADJUDICATION_TABLE_V1_1.jsonl: full 676-unit table; decision
column filled ONLY where the owner ruled; labels (human_status/human_uses)
are NEVER modified here — corrections are recorded as decision metadata
(correct_count etc.) for a future annotation revision. Old V1 table kept.
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
A2R = os.path.join(PREP, "a2_review")

# owner decisions: unit suffix (sid, var) -> dict(decision, final_status,
# final_uses, globally_reachable, basis)
D = {}
def d(sid, var, decision, fs=None, fu=None, gr=None, basis=""):
    D[(sid, var)] = {"decision": decision, "final_status": fs,
                     "final_uses": fu, "globally_reachable": gr,
                     "basis": basis}

for v, c in [("map1", 6)] + [(f"map{i}", 5) for i in range(2, 13)]:
    d("script_101353", v, "accept_human", "presentation_only", c,
      basis="地图对象：图层添加/控件/Linker/面板/定位均属展示")
for v in ("mapPanel", "title", "legendPanel"):
    d("script_101353", v, "accept_human", "presentation_only", 1, basis="界面组件")
d("script_101353", "modis_chlor_a", "needs_scope_audit",
  basis="先确认 12 处声明是否同一绑定，再按绑定统计")

d("script_100110", "BACKGROUND", "reject_proposed_resolution", "presentation_only", 1,
  basis="owner 明确裁定: 仅设置地图底图样式，保留 presentation_only；不因进入 UI 配置接口改判 analysis_chain")

d("script_116725", "grad", "accept_human", "presentation_only", 1, basis="调色板反转，无分析链证据")
d("script_116725", "fractions", "accept_human", "analysis_chain", 5, basis="重命名/表达式/加波段")
d("script_116725", "image", "accept_human", "analysis_chain", 1, basis="rescale 内局部绑定，与外层同名形参分开")
d("script_116725", "score", "correct_count", "analysis_chain", 5,
  basis="备注列 4×score.min + 1×score.lt = 5；human_uses=6 为笔误，以逐处源码为准")

d("script_184426", "filtered_area", "accept_human", "analysis_chain", 3, basis="定义 roi + 展示，双重用途优先 analysis")
d("script_184426", "roi", "accept_human", "analysis_chain", 4, basis="裁剪/定位/图表区域/导出区域")
d("script_184426", "image", "accept_human", "analysis_chain", 2, basis="subtract 形参自身作用域 2 处")
d("script_184426", "anomalies", "accept_human", "analysis_chain", 4, basis="图层/iterate/sum×2")
d("script_184426", "chartParam", "reject_proposed_resolution", "presentation_only", 1, basis="图表参数对象仅配置图表——驳回一刀切 analysis 提案")
d("script_184426", "chart", "reject_proposed_resolution", "presentation_only", 1, basis="图表对象仅展示")

d("script_191158", "timeField", "needs_source_audit", "analysis_chain", basis="状态无争议，计数待源码核验")
d("script_191158", "image", "accept_human_scope", "analysis_chain", basis="按 maskClouds 内绑定单独统计")
d("script_191158", "date", "needs_source_audit", "analysis_chain")
d("script_191158", "filteredLandsat", "needs_source_audit", "analysis_chain")
d("script_191158", "independents", "needs_source_audit", "analysis_chain")
d("script_191158", "dependent", "needs_source_audit", "analysis_chain")
d("script_191158", "harmonicIndependents", "needs_source_audit", "analysis_chain")
d("script_191158", "current", "accept_human_scope", "analysis_chain", basis="按 fill 内绑定单独统计")
d("script_191158", "covariance", "accept_human_scope", "analysis_chain", basis="按 correlation 内绑定单独统计")
d("script_191158", "covariance34", "accept_human", "presentation_only", 1)
d("script_191158", "list", "accept_human_scope", "analysis_chain", basis="按 fill 内绑定单独统计")
d("script_191158", "start", "needs_source_audit", "analysis_chain")
d("script_191158", "end", "needs_source_audit", "analysis_chain")
d("script_191158", "ndvi", "needs_source_audit", "analysis_chain")

d("script_216850", "img", "accept_human", "analysis_chain", 4)
d("script_216850", "image", "accept_human_scope", "analysis_chain", 1)
d("script_216850", "bands", "needs_source_audit", "analysis_chain")
d("script_216850", "classified", "needs_source_audit", "analysis_chain")
d("script_216850", "qa", "accept_human", "analysis_chain", 3)
d("script_216850", "ClassChart", "accept_human", "presentation_only", 2)
d("script_216850", "label", "accept_human", "presentation_only", 2)
d("script_216850", "classification", "accept_human", "presentation_only", 1)
d("script_216850", "SARimage", "accept_human", "presentation_only", 1)

d("script_217669", "grids", "reject_proposed_resolution", "presentation_only", 1, basis="后继用途为绘制网格轮廓")
d("script_217669", "myGrid", "reject_proposed_resolution", "presentation_only", 1, basis="仅生成网格轮廓")
d("script_217669", "names", "reject_proposed_resolution", "presentation_only", 2, basis="图例类别名称及循环展示")
d("script_217669", "colors", "reject_proposed_resolution", "presentation_only", 1, basis="仅读取图例颜色")
d("script_217669", "palettes", "accept_human", "presentation_only", 1)
d("script_217669", "legend", "reject_proposed_resolution", "presentation_only", 3, basis="构建并添加图例面板")
d("script_217669", "legendTitle", "accept_human", "presentation_only", 1)
d("script_217669", "makeRow", "accept_human", "presentation_only", 1)
d("script_217669", "colorBox", "accept_human", "unconsumed", 0, basis="变量名无后继引用；对象被构造不构成引用")
d("script_217669", "description", "accept_human", "unconsumed", 0, basis="同 colorBox")
d("script_217669", "i", "reject_proposed_resolution", "presentation_only", 4, basis="循环变量用于图例名称/颜色访问")
d("script_217669", "blank", "needs_source_audit", "presentation_only", 1, basis="暂定；需确认是否还有其他分析操作")
d("script_217669", "collection", "needs_source_audit", "analysis_chain")
d("script_217669", "rescaled", "needs_source_audit", "analysis_chain")
d("script_217669", "year", "needs_source_audit", "analysis_chain")

d("script_35821", "img", "accept_human_scope", "analysis_chain", basis="按 illuminationCondition 内绑定计数")
d("script_35821", "illuminationCondition", "accept_human_scope", "analysis_chain", 1,
  gr=False, basis="静态引用层=1（未调用函数体内）；主流程可达层=false")
d("script_35821", "SZ_rad", "needs_source_audit", "analysis_chain")
d("script_35821", "cosZ", "needs_source_audit", "analysis_chain")
d("script_35821", "sinZ", "needs_source_audit", "analysis_chain")
d("script_35821", "illuminationCorrection", "correct_count", "analysis_chain", 1,
  gr=False, basis="两层报告：静态引用 1（非 unconsumed）；globally_reachable=false；修正 batch-5 的 unconsumed 状态")
d("script_35821", "img_plus_ic_mask2", "needs_source_audit", "analysis_chain")
d("script_35821", "band", "needs_source_audit", "analysis_chain")
d("script_35821", "out", "needs_source_audit", "analysis_chain")
d("script_35821", "SCSc_output", "accept_human", "unconsumed", 0, basis="无有效后继引用且未被有效返回")
d("script_35821", "img_SCSccorr", "needs_source_audit", "analysis_chain")
d("script_35821", "aero", "needs_source_audit", "analysis_chain")
d("script_35821", "collection", "needs_scope_audit", "analysis_chain", basis="重复声明需先确认作用域归属再计数")

d("script_45485", "image", "needs_source_audit", "analysis_chain")

d("script_7900", "image", "accept_human_scope", "analysis_chain", 2,
  basis="仅 cloudMask 形参绑定；NDVI/EVI/NBR 同名形参为不同绑定不得合并")
d("script_7900", "dem", "needs_source_audit", "analysis_chain")
d("script_7900", "img", "accept_human_scope", "analysis_chain", basis="按所属函数形参计数")
d("script_7900", "ic", "needs_source_audit", "analysis_chain")


def main():
    v1_path = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1.jsonl")
    sealed = json.load(open(os.path.join(PREP, "automation_sealed_v1.json"),
                            encoding="utf-8"))
    ann = {}
    for l in open(os.path.join(PREP, "annotator1_workspace_v1", "results",
                               "annotation_results_v1_20261010T1716.jsonl"),
                  encoding="utf-8"):
        r = json.loads(l)
        if r.get("human"):
            ann[r["unit_id"]] = r
    v1 = {}
    for l in open(v1_path, encoding="utf-8"):
        r = json.loads(l)
        v1[r["unit_id"]] = r

    rows = []
    decided = applied = 0
    for sid, s in sealed["scripts"].items():
        if not isinstance(s.get("A2"), list):
            continue
        auto_by_var = {c["variable"]: c for c in s["A2"]}
        for var, c in auto_by_var.items():
            uid = f"{sid}:A2:{var}"
            r = ann.get(uid)
            if not r:
                continue
            row = v1.get(uid) or {
                "unit_id": uid, "dimension": None,
                "auto_status": c["status"], "auto_uses": c["post_definition_uses"],
                "human_status": r["human"], "human_uses": r.get("uses_count"),
                "candidate_cause_category": "consistent" if (
                    r["human"] == c["status"] and r.get("uses_count") is not None
                    and int(r["uses_count"]) == int(c["post_definition_uses"]))
                    else "unlisted",
                "proposed_resolution": None, "human_note": (r.get("note") or "")[:200],
            }
            dec = D.get((sid, var))
            if dec:
                row = dict(row)
                row["decision"] = dec["decision"]
                row["final_status"] = dec["final_status"]
                row["final_uses"] = dec["final_uses"]
                row["globally_reachable"] = dec["globally_reachable"]
                row["decision_basis"] = dec["basis"]
                row["old_label_modified"] = bool(
                    dec["final_status"] and dec["final_status"] != r["human"])
                decided += 1
                applied += 1 if row["old_label_modified"] else 0
            rows.append(row)

    out = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_1.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    from collections import Counter
    dc = Counter()
    for row in rows:
        if row.get("decision"):
            dc[row["decision"]] += 1
    summary = {
        "units_total": len(rows),
        "units_decided": decided,
        "decision_distribution": dict(dc),
        "old_label_modification_flagged": applied,
        "note": "labels untouched in annotation_results file; corrections "
                "(correct_count etc.) queued for future annotation revision; "
                "no new A2 agreement number published (protocol v0.1 freeze "
                "condition)",
        "pending": [row["unit_id"] for row in rows if not row.get("decision")
                    and row.get("candidate_cause_category") != "consistent"],
    }
    json.dump(summary, open(os.path.join(A2R, "A2_ADJUDICATION_V1_1_SUMMARY.json"),
                            "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
