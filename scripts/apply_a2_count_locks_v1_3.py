# -*- coding: utf-8 -*-
"""Apply owner count locks (2026-10-10 audit-packet review) -> V1_3 table.
Plus evidence addendum for the three special items:
  (a) script_100145:year binding-level audit
  (b) script_217669:rescaled collector completeness check
  (c) 217669 blank->outline downstream evidence; 100110 maxValue/maxMedian
      status-confirmation contexts
"""

import json
import os
import sys
import glob
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_wp_a_detector_backtest_v1 import analyze_script  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
A2R = os.path.join(PREP, "a2_review")

# owner count locks: (sid, var) -> (final_uses, final_status, status_locked, basis)
L = {}
def l(sid, var, fu, fs=None, slock=True, basis=""):
    L[(sid, var)] = {"final_uses": fu, "final_status": fs,
                     "status_locked": slock, "basis": basis}

l("script_100110", "xValLabels", 2, "presentation_only", True, "L289/421 各一处；图表类别标签暂定展示")
l("script_100110", "maxValue", 4, "analysis_chain", False, "L279×2 + L351×2，左值不计；状态待确认是否仅用于轴范围")
l("script_100110", "maxMedian", 4, "analysis_chain", False, "L281×2 + L351×2；状态待确认")
l("script_100110", "myRows", 1, "presentation_only", False, "L329 一处；倾向展示（rows: myRows），待最终确认")
l("script_100110", "stats", 18, "analysis_chain", True, "L279/281/283/285 各2 + L293-301 各1 + L303×5 = 18")
l("script_100110", "landsatTOAcloudmask", 1, None, False,
  basis="计数锁定=1；状态暂不锁——需协议区分'unconsumed=零有效后继引用'与'未进入有效下游结果链'（owner 提出待定义）")
l("script_100133", "data", 2, "analysis_chain", True, "L307/457 各一处；一处统计构造一处传图表函数")
l("script_100133", "xVals", 2, "analysis_chain", True, "L305/457；构造图表行数据，非仅显示标签")
l("script_100133", "xValLabels", 2, "presentation_only", True, "L325/457；横轴类别标签")
l("script_100133", "xField", 2, "analysis_chain", True, "L309/457；L309 用于 ee.Filter.equals 参与数据筛选")
l("script_100133", "xLabel", 3, "presentation_only", True, "L373/379/457；标题与横轴标题")
l("script_100133", "yField", 2, "analysis_chain", True, "L315/457；selectors:[yField] 指定统计字段")
l("script_100133", "yLabel", 3, "presentation_only", True, "L373/383/457；图表标题与纵轴标题")
l("script_100145", "IC", 9, "analysis_chain", True, "9 处读取/返回；L69/79/87/185 左值不另计")
l("script_100145", "GHSL2023releaseYear", 10, "analysis_chain", True, "L117/133/149/167/195 各两处读取 = 10")
l("script_100145", "GHSLbud", 10, "analysis_chain", True,
  basis="计数修正 human 9→10：L123/139/155/173/201 各一处右值引用 + L125/141/157/175/203 各一处展示引用；左值不计")
l("script_100145", "GHSLueyear", 4, "analysis_chain", True, "L161/207/209/211；L209 右侧 GHSLueyear.map 为有效读取——除展示外参与缓冲处理")
l("script_191158", "timeField", 9, "analysis_chain", True, "审计包 9 处均有效引用")
l("script_191158", "date", 2, "analysis_chain", True, "L29/419 各一处")
l("script_191158", "filteredLandsat", 11, "analysis_chain", True, "11 处均计数；L333 作为两个实参出现计 2")
l("script_191158", "independents", 4, "analysis_chain", True, "L77/79/85/91")
l("script_191158", "dependent", 9, "analysis_chain", True, "L77/89/93/129/257/259/291×2/345")
l("script_191158", "harmonicIndependents", 4, "analysis_chain", True, "L129/131/137/143")
l("script_191158", "start", 2, "analysis_chain", True, "L403/407")
l("script_191158", "end", 2, "analysis_chain", True, "L403/409")
l("script_191158", "ndvi", 2, "analysis_chain", True, "L473 两处独立引用")
l("script_216850", "bands", 4, "analysis_chain", True, "L47/57/73/77")
l("script_216850", "classified", 5, "analysis_chain", True, "L85/87/91/115/139；既展示又构造后续分析结果")
l("script_35821", "SZ_rad", 2, "analysis_chain", True, "L29/39；human 3→2")
l("script_35821", "cosZ", 2, "analysis_chain", True, "L35/55；human 3→2")
l("script_35821", "sinZ", 2, "analysis_chain", True, "L45/47；human 1→2")
l("script_35821", "img_plus_ic_mask2", 7, "analysis_chain", True, "L91/105/117/121/123/125/127")
l("script_35821", "band", 3, "analysis_chain", True, "L91/105/121")
l("script_35821", "out", 4, "analysis_chain", True, "L103×2 + L111/113")
l("script_35821", "img_SCSccorr", 2, "analysis_chain", True, "L143/145；human 3→2")
l("script_35821", "aero", 1, "analysis_chain", True, "L161；human 2→1")
l("script_217669", "blank", 1, "presentation_only", False, "暂定展示；待确认 outline 下游用途（见证据附册）")
l("script_217669", "collection", 4, "analysis_chain", True, "L183(左值不计)/205/209/211；human 6→4")
l("script_217669", "rescaled", 1, "analysis_chain", True,
  basis="当前列表仅 L197 return feature.set('new_id', rescaled)；human 3 无位置表支持（附采集器完整性核验，见证据附册）")
l("script_217669", "year", 4, "analysis_chain", True, "L247/249/253/255；human 3→4")
l("script_45485", "image", 6, "analysis_chain", True, "形参绑定 L7/9/13/15/17/21；human 8→6")
l("script_7900", "dem", 3, "analysis_chain", True, "L65/67/69；human 2→3")
l("script_7900", "ic", 1, "analysis_chain", True, "L97；human 2→1")


def lines_of(sid):
    hits = glob.glob(os.path.join(REPO, ".tmp_gee_batch13_sources",
                                  "Data", "data*", sid + ".txt"))
    with open(hits[0], encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def main():
    in_path = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_2.jsonl")
    rows = [json.loads(l) for l in open(in_path, encoding="utf-8")]
    applied = count_corrections = 0
    for row in rows:
        uid = row["unit_id"]
        sid, var = uid.split(":A2:")
        lk = L.get((sid, var))
        if not lk:
            continue
        row["count_locked"] = True
        row["original_uses"] = row.get("human_uses")
        row["final_uses"] = lk["final_uses"]
        if lk["final_status"] is not None:
            row["final_status"] = lk["final_status"]
        row["status_locked"] = lk["status_locked"]
        prev_dec = row.get("decision")
        row["decision"] = "count_locked" if (row.get("human_uses") is not None
                                             and int(row["human_uses"]) == lk["final_uses"]) \
            else "correct_count"
        row["count_revision"] = (f"human {row.get('human_uses')} -> final "
                                 f"{lk['final_uses']}"
                                 if row.get("human_uses") is not None and
                                 int(row["human_uses"]) != lk["final_uses"]
                                 else "human count verified per-site")
        row["decision_basis"] = (row.get("decision_basis") or "") + \
            " || " + lk["basis"]
        if int(row.get("human_uses") or -1) != lk["final_uses"]:
            count_corrections += 1
        applied += 1

    out = os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_3.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---------------- evidence addendum ----------------
    ev = {}

    # (a) 100145:year binding-level audit
    lines = lines_of("script_100145")
    a = analyze_script("\n".join(lines) + "\n")
    sites = [u for u in a["uses"] if u["name"] == "year" and u["pos"]]
    # enclosing function detection via function start/end ranges
    import esprima
    ast = esprima.parseScript("\n".join(lines) + "\n", loc=True, tolerant=True)
    fn_ranges = []
    def walk_fns(node, fname=None):
        t = getattr(node, "type", None)
        if t in ("FunctionDeclaration", "FunctionExpression",
                 "ArrowFunctionExpression"):
            nm = getattr(getattr(node, "id", None), "name", None) or "(anonymous)"
            rng = (node.loc.start.line, node.loc.end.line, nm)
            fn_ranges.append(rng)
            for c in fn_children(node):
                walk_fns(c, nm)
            return
        for c in fn_children(node):
            walk_fns(c, fname)
    def fn_children(node):
        d = getattr(node, "__dict__", {})
        for v in d.values():
            if isinstance(v, list):
                for x in v:
                    yield x
            elif hasattr(v, "__dict__") and v is not None:
                yield v
    walk_fns(ast)
    def enclosing(ln):
        for s, e, nm in fn_ranges:
            if s <= ln <= e:
                return nm
        return "(top-level)"
    grp = {}
    for u in sites:
        ln = u["pos"][0]
        grp.setdefault(enclosing(ln), []).append(
            (ln, lines[ln - 1].strip()[:120]))
    ev["script_100145:year_binding_audit"] = {
        "total_sites": len(sites),
        "grouped_by_enclosing_scope": {k: v for k, v in sorted(grp.items())},
        "question": "owner: 确认哪些组属同一绑定后才能定最终计数（29 不可直接采用，human 11 亦暂缓）",
    }

    # (b) 217669:rescaled collector completeness (regex cross-check)
    lines = lines_of("script_217669")
    rx_hits = [(i + 1, t.strip()[:120]) for i, t in enumerate(lines)
               if re.search(r"\brescaled\b", t)]
    ast_sites = []
    a2 = analyze_script("\n".join(lines) + "\n")
    for u in a2["uses"]:
        if u["name"] == "rescaled" and u["pos"]:
            ast_sites.append(u["pos"][0])
    ev["script_217669:rescaled_completeness"] = {
        "regex_lines": rx_hits,
        "ast_lines": sorted(set(ast_sites)),
        "regex_minus_ast": sorted(set(l1 for l1, _ in rx_hits) - set(ast_sites)),
        "conclusion": "collector complete iff regex_minus_ast empty",
    }

    # (c) 217669 blank->outline downstream + 100110 maxValue/maxMedian contexts
    lines = lines_of("script_217669")
    ev["script_217669:outline_downstream"] = {
        "sites": [(i + 1, t.strip()[:120]) for i, t in enumerate(lines)
                  if re.search(r"\boutline\b", t)],
        "question": "outline 仅被 Map.addLayer 消费则 blank 的展示定性可锁定",
    }
    lines = lines_of("script_100110")
    ev["script_100110:maxValue_maxMedian_contexts"] = {
        "lines_279_281_351": [(i + 1, lines[i].strip()[:140])
                              for i in (278, 280, 350)],
        "question": "确认 maxValue/maxMedian 是否仅用于图表纵轴范围设置",
    }

    ev_out = os.path.join(A2R, "A2_COUNT_LOCK_EVIDENCE_V1.json")
    json.dump(ev, open(ev_out, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    summary = {
        "count_locks_applied": applied,
        "count_corrections_vs_human": count_corrections,
        "open_after_this_batch": [
            "script_100145:year (binding audit above -> owner locks)",
            "script_100110:landsatTOAcloudmask (status: protocol unconsumed definition)",
            "status confirmations: maxValue/maxMedian/myRows (100110), blank (217669)",
        ],
        "table": os.path.relpath(out, REPO),
        "evidence": os.path.relpath(ev_out, REPO),
    }
    json.dump(summary, open(os.path.join(A2R, "A2_COUNT_LOCK_V1_3_SUMMARY.json"),
                            "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
