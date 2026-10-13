# -*- coding: utf-8 -*-
"""Generate the source-audit packet for the 45 needs_source_audit A2 units.

Per unit: definition site(s) + EVERY identifier-use site (post/pre definition,
with line text), so counts can be locked by per-site verification (owner
ruling: counts must be verified against source, never inferred). Assignment
LHS positions are already excluded by the AST use collector; each site is
listed raw with its line text for manual classification.
"""

import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_wp_a_detector_backtest_v1 import analyze_script  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
A2R = os.path.join(PREP, "a2_review")


def main():
    table = [json.loads(l) for l in
             open(os.path.join(A2R, "A2_ADJUDICATION_TABLE_V1_2.jsonl"),
                  encoding="utf-8")]
    targets = [r for r in table if r.get("decision") == "needs_source_audit"]

    cache = {}
    def analyzed(sid):
        if sid not in cache:
            hits = glob.glob(os.path.join(REPO, ".tmp_gee_batch13_sources",
                                          "Data", "data*", sid + ".txt"))
            with open(hits[0], encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            cache[sid] = (analyze_script("\n".join(lines) + "\n"), lines)
        return cache[sid]

    packet = []
    for r in targets:
        uid = r["unit_id"]
        sid, var = uid.split(":A2:")
        analysis, lines = analyzed(sid)
        info = analysis["declared"].get(var)
        def_sites = []
        if info:
            def_sites.append({"line": info["def_line"], "kind": info["kind"]})
        # multiple definition lines (repeat var / reassignments): find them
        def_lines = sorted({u["pos"][0] for u in analysis["uses"] if False})  # placeholder
        sites = []
        for u in analysis["uses"]:
            if u["name"] != var or not u["pos"]:
                continue
            ln = u["pos"][0]
            text = lines[ln - 1].strip()[:160] if 0 < ln <= len(lines) else ""
            sites.append({"line": ln, "col": u["pos"][1],
                          "context_parent": u.get("parent_type"),
                          "line_text": text})
        sites.sort(key=lambda s: (s["line"], s["col"]))
        packet.append({
            "unit_id": uid,
            "auto_status": r["auto_status"], "auto_uses": r["auto_uses"],
            "human_status": r["human_status"], "human_uses": r["human_uses"],
            "decision": r["decision"],
            "decision_basis": r.get("decision_basis"),
            "definition_sites": def_sites,
            "all_identifier_sites": sites,
            "site_count": len(sites),
            "note": "Assignment LHS already excluded by the AST collector. "
                    "Verify per-site: def-expression-internal references do "
                    "NOT count as post-definition uses; same-call receiver "
                    "not double-counted; return counts as one use.",
        })

    out_j = os.path.join(A2R, "A2_SOURCE_AUDIT_PACKET_V1.json")
    json.dump(packet, open(out_j, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    md = ["# A2 源码审计包（45 项 needs_source_audit）", "",
          "每项列出：定义位置 + 全部标识符出现位置（含行文本）。判定规则：",
          "定义表达式内部引用不计后继；赋值左侧不计（已由采集器排除）；",
          "同一调用表达式接收对象不重复计数；return 计一次使用。", ""]
    for p in packet:
        md += [f"## {p['unit_id']}", "",
               f"自动化: {p['auto_status']}/{p['auto_uses']} ｜ 人工: "
               f"{p['human_status']}/{p['human_uses']} ｜ 出现位置数: {p['site_count']}",
               f"裁定依据: {p['decision_basis'] or '—'}", ""]
        if p["definition_sites"]:
            md.append(f"定义: {p['definition_sites']}")
        md.append("")
        md.append("| 行 | 父节点类型 | 行文本 |")
        md.append("|---|---|---|")
        for s in p["all_identifier_sites"]:
            md.append(f"| {s['line']} | {s['context_parent']} | `{s['line_text']}` |")
        md.append("")
    out_m = os.path.join(A2R, "A2_SOURCE_AUDIT_PACKET_V1.md")
    open(out_m, "w", encoding="utf-8").write("\n".join(md))

    print(json.dumps({
        "packet_units": len(packet),
        "out_json": os.path.relpath(out_j, REPO),
        "out_md": os.path.relpath(out_m, REPO),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
