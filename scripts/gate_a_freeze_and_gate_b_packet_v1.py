#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate A artifact: per-candidate r5 outputs for the 10 independent tasks
(80 candidates), frozen under rules v0.5.1. Also builds the Gate B blind
labeling packet (10 tasks x 8 candidates, full required-slot matrices,
reward-blind)."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"

RULE_DEBUGGED = {"5227", "17970", "823", "29519", "13612", "5516", "6878",
                 "9210", "9854", "22822", "26102", "30160", "32593", "32751"}


def main():
    preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
    tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
    tasks.update(json.loads((RL / "r5_audit_tasks_rest.json").read_text(encoding="utf-8")))
    by_group = defaultdict_list = {}
    for p in preds:
        by_group.setdefault(p["k"], []).append(p)

    indep_tasks = sorted(k for k in by_group if str(k) not in RULE_DEBUGGED)
    per_cand, packet_groups = [], []
    for k in indep_tasks:
        task = tasks[str(k)]
        parse = evaluate_pair(task, {"stages": []})["parse"]
        required = [{"slot": s["id"], "families": s["families"],
                     "determination": s.get("requirement_determination")}
                    for s in parse["slots"] if s["state"] == "required"]
        uncertain = [s["id"] for s in parse["slots"]
                     if s["state"] == "requirement_uncertain"]
        gaps = [g["signal"] for g in parse["vocab_gap_signals"]]
        cands = []
        for p in sorted(by_group[k], key=lambda x: x["cand"]):
            try:
                b = json.loads(p["pred_text"])
            except Exception:
                b = None
            if isinstance(b, dict) and isinstance(b.get("stages"), list):
                stages = [{"seq": s.get("seq"), "family": s.get("family"),
                           "repeat": s.get("repeat")}
                          for s in b["stages"] if isinstance(s, dict)]
                res = evaluate_pair(task, b)["score"]
                r5 = {"verdict": res["coverage_verdict"],
                      "missing": [s["slot"] for s in res["per_slot"]
                                  if s["coverage"] == "missing"],
                      "coarse": [s["slot"] for s in res["per_slot"]
                                 if s["coverage"] == "covered_coarse"],
                      "uncertain_slots": res.get("requirement_uncertain_slots", [])}
            else:
                stages, r5 = "<UNPARSEABLE>", {"verdict": "unparseable"}
            rec = {"k": k, "cand": p["cand"], "stages": stages, "r5_v051": r5}
            cands.append(rec)
            per_cand.append(rec)
        packet_groups.append({"k": k, "task": task, "required_slots": required,
                              "requirement_uncertain_slots": uncertain,
                              "vocab_gap_signals": gaps, "candidates": cands})

    (RL / "independent_set_r5_outputs_v051.json").write_text(
        json.dumps({"rules": "v0.5.1",
                    "sha256_parser": "bb6309807586c5dfa4e0559de3b55779b40f6b3185332c4ddc31dfc6e71ce135",
                    "n_tasks": len(indep_tasks), "n_candidates": len(per_cand),
                    "candidates": per_cand}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # ---- Gate B blind packet ----
    LBL = ("| 槽位 | 判定（omission / covered / requirement_uncertain / "
           "representation_boundary / non_required） | 证据附注 |")
    md = ["# Gate B 独立集盲评包 v1（10 任务 × 8 候选 = 80 候选）", "",
          "> 规则 v0.5.1；**盲评：不显示 r5 的 missing/covered 判定**。",
          "> 判定单位 = 候选 × r5-required 槽位；另对候选整体标注非必需步骤。", "",
          "## 槽位级判定口径（owner 十二轮）", "",
          "| 标签 | 含义 |", "|---|---|",
          "| `omission` | 任务明确要求该能力，候选无可语义替代的可见实现（真实遗漏） |",
          "| `covered` | 候选已有语义上足以实现该能力的阶段或可核验等价 |",
          "| `requirement_uncertain` | 任务文本不足以确定该能力是否必需 |",
          "| `representation_boundary` | 任务需要该能力但阶段词表无法表达（记词表缺口，不算模型遗漏） |",
          "| `non_required` | 任务根本不要求该能力 |", "",
          "## 候选级附加字段", "",
          "- `unnecessary_stages`：候选中任务无依据的冗余阶段（列名；无则空）", "",
          "---"]
    for g in packet_groups:
        md += [f"## 组 {g['k']}", "", "**任务全文：**", "", g["task"], ""]
        if g["requirement_uncertain_slots"] or g["vocab_gap_signals"]:
            md += [f"（解析注：requirement_uncertain 槽位 = "
                   f"{g['requirement_uncertain_slots'] or '无'}；词表边界信号 = "
                   f"{g['vocab_gap_signals'] or '无'}——此类不强制判定）", ""]
        req = g["required_slots"]
        md += ["**r5-required 槽位（逐候选逐槽位判定）：**", "", LBL,
               "|---|---|---|"]
        for c in g["candidates"]:
            md += [f"**候选 {c['cand']}**", ""]
            md += [f"```",
                   *[f"{s['seq']}. {s['family']} x{s['repeat']}" for s in c["stages"]
                     if isinstance(s, dict)],
                   "```", ""]
            for slot in req:
                md += [f"| {slot['slot']} | ______ | ______ |"]
            md += [f"**unnecessary_stages：** ______", ""]

    (RL / "GATE_B_INDEPENDENT_BLIND_PACKET_V1.md").write_text(
        "\n".join(md), encoding="utf-8")
    json.dump({"gate": "B", "blind": True, "tasks": len(indep_tasks),
               "candidates": len(per_cand),
               "groups": packet_groups},
              open(RL / "gate_b_independent_packet_v1.json", "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Gate A per-candidate output: {len(per_cand)} candidates, "
          f"{len(indep_tasks)} tasks")
    print(f"Gate B blind packet written ({len(packet_groups)} groups)")


if __name__ == "__main__":
    main()
