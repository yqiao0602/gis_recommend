#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 experiment: paired analysis of the control (frozen v0_4) vs experiment
(v0_5) arms, per the frozen preregistration A1_PREREGISTRATION_V1.md.

Reads:
  control:   dx50_full_v1/runs/<task>/S2/S<n>/{raw_output.txt, parsed_v2.json}
  experiment: dx50_full_v1/a1_v1/runs/<task>/<out_sub>/{raw_output.txt, parsed.json}
             (parser v2 re-applied locally if parsed.json is v1)
Writes a1_v1/A1_PAIRED_RESULTS_V1.json + A1_PAIRED_REPORT_V1.md

Classification per step (three-way, never merged):
  POS    - SELECT with operator(s) in candidates
  ABST   - explicit NO OPERATOR FOR THIS STEP (post-think decision)
  NODEC  - empty / truncated / unparseable (incl. unterminated think)
Paired transitions are bucketed into the four preregistered categories.
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_s23 import parse_s2_v2  # noqa: E402

FULL = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
                "dx50_full_v1"))
A1 = FULL / "a1_v1"
UNVERIFIED = {"otb:aggregate", "otb:genericregionmerging",
              "otb:imagetimeseriesgapfilling", "otb:multitempfilteringfilter",
              "otb:multitempfilteringoutcore", "otb:objectsradiometricstatistics"}


def classify(parsed, raw, oids):
    if not raw or not raw.strip():
        return "NODEC", []
    sel = parsed.get("selected_in_candidates") or []
    ooc = [o for o in (parsed.get("selected") or [])
           if o.get("operator_id") not in oids]
    if parsed.get("no_operator_for_step"):
        return "ABST", []
    if sel or ooc:
        return "POS", sel + [o["operator_id"] for o in ooc]
    return "NODEC", []


def read_control(step_key, affected):
    tid, snum = step_key.split("#S")
    d = FULL / "runs" / tid / "S2" / f"S{snum}"
    raw = (d / "raw_output.txt").read_text(encoding="utf-8")
    pv2 = d / "parsed_v2.json"
    parsed = json.loads(pv2.read_text(encoding="utf-8")) if pv2.exists() else \
        json.loads((d / "parsed.json").read_text(encoding="utf-8"))
    if parsed.get("parser") != "s2_v2":
        parsed = parse_s2_v2(raw, affected[step_key]["oids"])
    return raw, parsed


def read_experiment(step_key, affected, exp_root):
    tid, snum = step_key.split("#S")
    d = exp_root / tid / "S2" / f"S{snum}"
    raw = (d / "raw_output.txt").read_text(encoding="utf-8")
    parsed = json.loads((d / "parsed.json").read_text(encoding="utf-8"))
    if parsed.get("parser") != "s2_v2":
        parsed = parse_s2_v2(raw, affected[step_key]["oids"])
    return raw, parsed


def main():
    affected_doc = json.loads((A1 / "A1_AFFECTED_SET_V1.json")
                              .read_text(encoding="utf-8"))
    exp_root = A1 / "runs_local"
    if not exp_root.exists():
        raise SystemExit("experiment runs not pulled yet (expected at "
                         f"{exp_root})")

    # candidate oids per step from the frozen retrieval
    from dx_common import PCA2  # noqa: E402
    affected = {}
    for row in affected_doc["affected_steps"]:
        tid, snum = row["step_key"].split("#S")
        retr = json.loads((FULL / "runs" / tid / "S1" / "retrieval.json")
                          .read_text(encoding="utf-8"))
        top = next(s for s in retr["steps"] if s["step"] == int(snum))
        affected[row["step_key"]] = [c["operator_id"] for c in top["top10"]]

    pairs = []
    for key in sorted(affected):
        oids = affected[key]
        craw, cpars = read_control(key, {k: {"oids": affected[k]} for k in affected})
        eraw, epars = read_experiment(key, {k: {"oids": affected[k]} for k in affected}, exp_root)
        ccls, csel = classify(cpars, craw, oids)
        ecls, esel = classify(epars, eraw, oids)
        pairs.append({
            "step_key": key, "task": key.split("#")[0],
            "cls_control": ccls, "cls_experiment": ecls,
            "sel_control": csel, "sel_experiment": esel,
            "sel_changed": csel != esel,
            "sel_contains_unverified_exp": any(o in UNVERIFIED for o in esel),
        })

    def rate(cls_list, which):
        c = Counter(cls_list)
        n = len(cls_list)
        return {k: (c.get(k, 0), round(c.get(k, 0) / n, 4)) for k in
                ("POS", "ABST", "NODEC")} | {"n": n, "arm": which}

    ctl = rate([p["cls_control"] for p in pairs], "control v0_4")
    exp = rate([p["cls_experiment"] for p in pairs], "experiment v0_5")

    def bucket(cc, ec):
        if cc == "POS" and ec == "POS":
            return "POS->POS"
        if cc != "POS" and ec == "POS":
            return "OTHER->POS(gain)"
        if cc == "POS" and ec != "POS":
            return "POS->OTHER(loss)"
        if cc == ec:
            return f"{cc}->{ec}(same)"
        return f"{cc}->{ec}(shift)"

    transitions = Counter(bucket(p["cls_control"], p["cls_experiment"])
                          for p in pairs)

    # stratification: per task, per band (task index quartile proxy via L-level
    # from the frozen sample), classifier-tree steps
    by_task = defaultdict(Counter)
    for p in pairs:
        by_task[p["task"]][bucket(p["cls_control"], p["cls_experiment"])] += 1

    results = {
        "date": "2026-10-18",
        "n_pairs": len(pairs),
        "arms": {"control": ctl, "experiment": exp},
        "transitions": dict(transitions.most_common()),
        "sel_changed_steps": sum(1 for p in pairs if p["sel_changed"]),
        "sel_contains_unverified_exp_steps":
            sum(1 for p in pairs if p["sel_contains_unverified_exp"]),
        "by_task": {t: dict(c) for t, c in sorted(by_task.items())},
        "pairs": pairs,
        "notes": "selection-correctness (正确/错误选择) requires the owner "
                 "adjudication tables; this mechanical pass reports the "
                 "three-way decision classes + paired transitions first.",
    }
    (A1 / "A1_PAIRED_RESULTS_V1.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    md = ["# A1 配对分析 V1（机械层：三分决策 + 配对转移）", "",
          f"配对数：{len(pairs)}（受影响步全集；135 个不受影响步按构造排除）", "",
          "| 臂 | 正选 | 显式弃权 | 无判定 | n |", "|---|---|---|---|---|"]
    for arm, r in (("对照 v0_4", ctl), ("实验 v0_5", exp)):
        md.append(f"| {arm} | {r['POS'][0]} ({r['POS'][1]:.1%}) | "
                  f"{r['ABST'][0]} ({r['ABST'][1]:.1%}) | "
                  f"{r['NODEC'][0]} ({r['NODEC'][1]:.1%}) | {r['n']} |")
    md += ["", "## 配对转移（预注册四类 + same/shift）", ""]
    for k, v in transitions.most_common():
        md.append(f"- {k}: {v}")
    md += ["", f"选择集合变化步数：{results['sel_changed_steps']}；实验臂选中 "
          f"provenance_unverified 算子的步数："
          f"{results['sel_contains_unverified_exp_steps']}", "",
          "## 按任务分层", ""]
    for t, c in sorted(by_task.items()):
        md.append(f"- {t}: {dict(c)}")
    (A1 / "A1_PAIRED_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"control": ctl, "experiment": exp,
                      "transitions": results["transitions"],
                      "sel_changed": results["sel_changed_steps"]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
