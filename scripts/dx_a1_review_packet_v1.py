#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 review packet: paired evidence for human adjudication of changed steps,
in the preregistered priority order (A1_PREREGISTRATION_V1.md):
  P1 T-009 failure family (classifier-training steps)
  P2 classifier-Choice steps whose classification changed
  P3 IO-corrected steps (input_types_norm fixes)
  P4 all remaining decision-discordant pairs (incl. NODEC <-> decision)

Each entry shows both arms' raw excerpts (decision section), the paired
classification, selections, and WHICH candidate cards changed (oid list) so
the reviewer can judge against the actual card text.

Reads a1_v1/A1_PAIRED_RESULTS_V1.json (+ run dirs for raw text).
Writes a1_v1/A1_REVIEW_PACKET_V1.md (+ .json index).
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

FULL = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
                "dx50_full_v1"))
A1 = FULL / "a1_v1"
SHORT_BASE = REPO.parent  # Algorithm_classification/
CTRL_RUNS = SHORT_BASE / "dx50_short" / "runs"
EXP_RUNS = SHORT_BASE / "_a1_work" / "runs_local"

CLS_FAMILY = re.compile(r"otb:\w*(trainimagesclassifier|trainvectorclassifier|"
                        r"vectorclassifier|imageclassifier|kmeansclassification|"
                        r"somclassification|fusionofclassifications)")


def decision_excerpt(raw, max_chars=700):
    """Post-think decision section when present, else head/tail of raw."""
    raw = raw or ""
    if "</think>" in raw:
        seg = raw.split("</think>", 1)[1].strip()
    else:
        head = raw.strip()[:200]
        tail = raw.strip()[-300:] if len(raw) > 500 else ""
        seg = (f"[no closed think | head] {head}\n[tail] {tail}").strip()
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    return seg[:max_chars] + ("…" if len(seg) > max_chars else "")


def main():
    results = json.loads((A1 / "A1_PAIRED_RESULTS_V1.json").read_text(
        encoding="utf-8"))
    affected = {r["step_key"]: r for r in json.loads(
        (A1 / "A1_AFFECTED_SET_V1.json").read_text(encoding="utf-8")
    )["affected_steps"]}
    io_fixed = set(json.loads(
        (A1.parent / "a_track_p0_v1/V05_BUILD_MANIFEST_V1.json").read_text(
            encoding="utf-8"))["input_types_norm_corrections"].keys())

    def changed_oids(key):
        return affected.get(key, {}).get("changed_oids") or []

    entries = []
    for p in results["pairs"]:
        key = p["step_key"]
        tid, snum = key.split("#S")
        discord = p["cls_control"] != p["cls_experiment"] or p["sel_changed"]
        if not discord:
            continue
        oids = changed_oids(key)
        entry = {
            "step_key": key, "task": tid,
            "cls_control": p["cls_control"], "cls_experiment": p["cls_experiment"],
            "sel_control": p["sel_control"], "sel_experiment": p["sel_experiment"],
            "changed_oids": oids,
            "sel_contains_unverified_exp": p["sel_contains_unverified_exp"],
        }
        # raw excerpts
        tid2, snum = key.split("#S")
        cd = CTRL_RUNS / tid2 / "S2" / f"S{snum}"
        ed = EXP_RUNS / tid2 / "S2" / f"S{snum}"
        entry["raw_control_excerpt"] = decision_excerpt(
            (cd / "raw_output.txt").read_text(encoding="utf-8"))
        entry["raw_experiment_excerpt"] = decision_excerpt(
            (ed / "raw_output.txt").read_text(encoding="utf-8")) if ed.exists() else "(missing)"
        # priority
        changed_txt = " ".join(oids)
        if tid == "PCA2-T-009" or CLS_FAMILY.search(changed_txt):
            pri, pri_why = "P1", "T-009 family / classifier-training card changed"
        elif any(o in io_fixed for o in oids):
            pri, pri_why = "P3", "input_types_norm corrected operator involved"
        else:
            pri, pri_why = "P4", "decision discordant"
        entry["priority"], entry["priority_why"] = pri, pri_why
        entries.append(entry)

    order = {"P1": 0, "P3": 1, "P4": 2}
    entries.sort(key=lambda e: (order[e["priority"]], e["step_key"]))

    (A1 / "A1_REVIEW_PACKET_INDEX_V1.json").write_text(
        json.dumps({"n_entries": len(entries),
                    "by_priority": {p: sum(1 for e in entries
                                          if e["priority"] == p)
                                    for p in order},
                    "entries": entries}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    md = ["# A1 变化样本复核包 V1（预注册优先序）", "",
          f"决策不一致或选择集合变化的对：{len(entries)}。判读口径：对照 v0_5 卡面"
          "（changed_oids 所列算子）判断每臂决策是否被卡证据支持。", ""]
    for e in entries:
        md.append(f"## [{e['priority']}] {e['step_key']} — "
                  f"{e['cls_control']} → {e['cls_experiment']}")
        md.append(f"- 优先理由：{e['priority_why']}")
        if e["changed_oids"]:
            md.append(f"- 卡面变化算子：{', '.join(e['changed_oids'])}")
        if e["sel_contains_unverified_exp"]:
            md.append("- ⚠ 实验臂选中 provenance_unverified 算子")
        md.append(f"- 对照臂选择：{e['sel_control'] or '(无)'} ｜ "
                  f"实验臂选择：{e['sel_experiment'] or '(无)'}")
        md.append("### 对照臂 (v0_4) 决策摘录")
        md.append("```")
        md.append(e["raw_control_excerpt"])
        md.append("```")
        md.append("### 实验臂 (v0_5) 决策摘录")
        md.append("```")
        md.append(e["raw_experiment_excerpt"])
        md.append("```")
        md.append("")
    (A1 / "A1_REVIEW_PACKET_V1.md").write_text("\n".join(md), encoding="utf-8")
    print("packet entries:", len(entries),
          "| by priority:",
          {p: sum(1 for e in entries if e['priority'] == p) for p in order})


if __name__ == "__main__":
    main()
