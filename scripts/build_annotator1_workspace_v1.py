# -*- coding: utf-8 -*-
"""Build annotator-1 workspace: per-script annotation sheets + results
template from the FROZEN blind_annotation_units_v1.json.

Sheets contain source excerpts and annotation slots ONLY — no automation
conclusions. The annotator must not open automation_sealed_v1.json until
their annotation is complete and saved.
"""

import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
WS = os.path.join(PREP, "annotator1_workspace_v1")


def find_path(sid):
    import glob
    hits = glob.glob(os.path.join(REPO, ".tmp_gee_batch13_sources",
                                  "Data", "data*", sid + ".txt"))
    return hits[0] if hits else None


def excerpt(lines, centers, pad=2, max_lines=14):
    wanted = set()
    for c in centers:
        if c is None:
            continue
        for l in range(max(1, c - pad), min(len(lines), c + pad) + 1):
            wanted.add(l)
    if len(wanted) > max_lines and centers:
        c = centers[0]
        wanted = set(range(max(1, c - 3), min(len(lines), c + 4) + 1))
    out = []
    for l in sorted(wanted):
        out.append(f"{l:>5} | {lines[l - 1].rstrip()[:150]}")
    return "\n".join(out) if out else "  (line not available)"


def main():
    bu = json.load(open(os.path.join(PREP, "blind_annotation_units_v1.json"),
                        encoding="utf-8"))
    os.makedirs(os.path.join(WS, "annotation_sheets"), exist_ok=True)
    os.makedirs(os.path.join(WS, "results"), exist_ok=True)

    template = []
    sheets = 0
    for sid in sorted(bu["scripts"]):
        s = bu["scripts"][sid]
        if not s["parse_ok"]:
            template.append({
                "unit_id": f"{sid}:PARSE_FAILED", "annotator": None,
                "date": None, "human": "not_judgeable",
                "reason": "not JavaScript (parse failed) — skip",
            })
            continue
        p = find_path(sid)
        with open(p, encoding="utf-8", errors="replace") as f:
            src_lines = f.read().splitlines()

        rows = []
        md = [f"# 标注单 {sid}", "",
              f"源码 SHA-256: `{s['source_sha256']}`",
              f"完整源码路径: `{os.path.relpath(p, REPO).replace(os.sep, '/')}`"
              if p else "完整源码路径: (未找到)",
              "",
              "## A1 未声明候选变量（三分类裁定）", "",
              "分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| "
              "`missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| "
              "`undeterminable`（无法裁定）", ""]
        for u in s["A1_units"]:
            md += [f"### {u['unit_id']}", "",
                   f"变量: `{u['variable']}`  使用行: {u['use_lines']}  "
                   f"证据线索: {u['evidence_hints'] or '（无）'}", "",
                   "```javascript", excerpt(src_lines, u["use_lines"]),
                   "```", "", "裁定: ______________________  备注: ____________",
                   ""]
            rows.append({"unit_id": u["unit_id"], "annotator": None,
                         "date": None, "human": None, "note": None})

        md += ["## A2 声明变量使用分类", "",
               "状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| "
               "`analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数", ""]
        for u in s["A2_units"]:
            md += [f"### {u['unit_id']}", "",
                   f"变量: `{u['variable']}`  定义行: {u['def_line']}", "",
                   "```javascript", excerpt(src_lines, [u["def_line"]], pad=1),
                   "```", "",
                   "状态: ____________  后继使用数: ______  备注: ____________",
                   ""]
            rows.append({"unit_id": u["unit_id"], "annotator": None,
                         "date": None, "human": None, "uses_count": None,
                         "note": None})

        md += ["## A3 调用语句角色", "",
               "角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，"
               "按你的判断给出应属角色）| `undeterminable`", ""]
        # group A3 units by line for compact presentation
        by_line = {}
        for u in s["A3_units"]:
            by_line.setdefault(u["line"], []).append(u)
        for line in sorted(by_line):
            ids = [u["unit_id"] for u in by_line[line]]
            md += [f"### 行 {line}（{'、'.join(ids)}）", "",
                   "```javascript", excerpt(src_lines, [line], pad=0, max_lines=1),
                   "```", "", "角色: ____________", ""]
            for uid in ids:
                rows.append({"unit_id": uid, "annotator": None,
                             "date": None, "human": None, "note": None})

        out_md = os.path.join(WS, "annotation_sheets", f"{sid}.md")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        sheets += 1
        template.extend(rows)

    with open(os.path.join(WS, "results",
                           "annotation_results_template_v1.jsonl"), "w",
              encoding="utf-8") as f:
        for r in template:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    readme = f"""# 标注者 1 工作区（owner）

生成时间: {datetime.now().isoformat(timespec='seconds')}
依据: blind_annotation_units_v1.json（冻结，不含自动化结论）
判定单位规范: EXECUTION_CHECKLIST_JUDGMENT_UNITS_V1.md

## 纪律（owner 裁定 2026-10-10）

1. **只看**源码节选与本说明，**不得打开** `automation_sealed_v1.json`；
2. 独立完成，结果保存到 `results/`，文件名带时间戳（如
   `annotation_results_v1_20261010T1530.jsonl`）；
3. 单人探索性标注阶段：结果**不得**称为双盲验证或双标一致性；
4. 遇 `undeterminable` 如实标记，不强行判定；
5. script_10 非 JS（解析失败），按 `not_judgeable` 跳过。

## 材料

- `annotation_sheets/script_XXXXXX.md` × {sheets}：每脚本标注单
  （A1 三分类 / A2 状态+计数 / A3 角色四分类，附源码节选）；
- `results/annotation_results_template_v1.jsonl`：结果模板，共
  {len(template)} 条判定单位，填 `human` 字段即可。

## 提交后流程

两名标注者均提交 → 记录时间戳 → 解封 automation_sealed_v1.json（记录开封
时间戳）→ compute_expansion_metrics_v1.py 计算分检测器一致率与分歧归因。
"""
    with open(os.path.join(WS, "README_ANNOTATION_PROTOCOL.md"), "w",
              encoding="utf-8") as f:
        f.write(readme)

    print(json.dumps({
        "sheets": sheets,
        "template_units": len(template),
        "workspace": os.path.relpath(WS, REPO),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
