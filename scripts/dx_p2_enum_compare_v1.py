#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 enum probe comparison: frozen v0_5 arm (control) vs enum-rendered arm.

Reports, per step: decision class (POS/OOC/ABST/NODEC), selection, truncation,
whether the decision text references the newly visible enum values (dt/rf),
and whether the experiment prompt actually expanded any card's choices."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_s23 import parse_s2_v2  # noqa: E402

SHORT = REPO.parent
CTRL = SHORT / "_a1_work/runs_local"
EXP = SHORT / "_p2_enum_work/runs_local"
CTRL_TREE = SHORT / "dx50_short/runs"
OUT = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
               "dx50_full_v1/p2_enum_v1"))
STEPS = ["PCA2-T-009#S4", "PCA2-T-009#S6", "PCA2-T-056#S6"]


def top_oids(tid, snum):
    retr = json.loads((CTRL_TREE / tid / "S1" / "retrieval.json")
                      .read_text(encoding="utf-8"))
    top = next(s for s in retr["steps"] if s["step"] == int(snum))
    return [c["operator_id"] for c in top["top10"]]


def classify(parsed, raw):
    if not raw.strip():
        return "NODEC"
    if parsed.get("no_operator_for_step"):
        return "ABST"
    if parsed.get("selected_in_candidates"):
        return "POS"
    if parsed.get("selected_outside_candidates"):
        return "OOC"
    return "NODEC"


def main():
    rows = []
    for key in STEPS:
        tid, snum = key.split("#S")
        oids = top_oids(tid, snum)
        cd = CTRL / tid / "S2" / f"S{snum}"
        ed = EXP / tid / "S2" / f"S{snum}"
        craw = (cd / "raw_output.txt").read_text(encoding="utf-8")
        eraw = (ed / "raw_output.txt").read_text(encoding="utf-8")
        cpar = parse_s2_v2(craw, oids)
        epar = parse_s2_v2(eraw, oids)
        cg = json.loads((cd / "gen.json").read_text(encoding="utf-8"))
        eg = json.loads((ed / "gen.json").read_text(encoding="utf-8"))
        ref = lambda raw: [w for w in ("classifier.dt", "classifier.rf",
                                       "decision tree", "random forest")
                           if w in raw.lower()]
        rows.append({
            "step": key,
            "control_class": classify(cpar, craw),
            "experiment_class": classify(epar, eraw),
            "control_sel": cpar.get("selected_in_candidates") or [],
            "experiment_sel": epar.get("selected_in_candidates") or [],
            "control_term": cg.get("term"), "experiment_term": eg.get("term"),
            "control_tokens": cg.get("gen_tokens"),
            "experiment_tokens": eg.get("gen_tokens"),
            "control_mentions_enum": ref(craw),
            "experiment_mentions_enum": ref(eraw),
            "control_decision": cpar.get("decision_section"),
            "experiment_decision": epar.get("decision_section"),
        })

    (OUT / "P2_ENUM_PROBE_RESULTS_V1.json").write_text(
        json.dumps({"steps": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    md = ["# P1 Enum 展开探针结果 V1", "",
          "对照=A1 v0_5 臂（冻结）；实验=同提示+卡面追加 choice 值。n=3，只做逐对描述。", "",
          "| 步骤 | 对照 | 实验 | 对照选择 | 实验选择 | 对照 tokens | 实验 tokens |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['step']} | {r['control_class']} | {r['experiment_class']} | "
                  f"{', '.join(r['control_sel']) or '-'} | "
                  f"{', '.join(r['experiment_sel']) or '-'} | "
                  f"{r['control_tokens']}({r['control_term']}) | "
                  f"{r['experiment_tokens']}({r['experiment_term']}) |")
    md += ["", "## 枚举值引用（决策文本中出现的 dt/rf 等）", ""]
    for r in rows:
        md.append(f"- {r['step']}：对照 {r['control_mentions_enum'] or '无'} ｜ "
                  f"实验 {r['experiment_mentions_enum'] or '无'}")
    (OUT / "P2_ENUM_PROBE_RESULTS_V1.md").write_text("\n".join(md),
                                                     encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
