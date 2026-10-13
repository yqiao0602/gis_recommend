#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score the eval-set candidates with r5 v0.5.1 + build the Gate-B-style
blind packet (protocol frozen BEFORE candidate display; SHAs logged).

This is the eval-set counterpart of gate_a_freeze_and_gate_b_packet_v1.py,
for the 24 never-trained tasks (192 candidates).
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
EP = RL / "eval_procurement"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    preds = json.loads((EP / "preds.json").read_text(encoding="utf-8"))
    cfg = json.loads((EP / "config.json").read_text(encoding="utf-8"))
    tasks = {json.loads(l)["script"]: json.loads(l)
             for l in (EP / "eval_set_24_tasks.jsonl").read_text(encoding="utf-8").splitlines()}

    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    per_cand, packet_groups = [], []
    for k in sorted(by_group):
        t = tasks[k]
        parse = evaluate_pair(t["task"], {"stages": []})["parse"]
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
                res = evaluate_pair(t["task"], b)["score"]
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
        packet_groups.append({"k": k, "task": t["task"],
                              "band": t["band"],
                              "required_slots": required,
                              "requirement_uncertain_slots": uncertain,
                              "vocab_gap_signals": gaps, "candidates": cands})

    outs = {"rules": "v0.5.1",
            "parser_sha256": sha256(REPO / "scripts/r5_requirement_parser_v0.py"),
            "n_tasks": len(packet_groups), "n_candidates": len(per_cand),
            "candidates": per_cand}
    (RL / "eval_procurement/eval_set_r5_outputs_v051.json").write_text(
        json.dumps(outs, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- blind packet ----
    md = ["# 评估集盲评包 v1（24 任务 × 8 候选 = 192 候选，从未训练任务）", "",
          "> 规则 v0.5.1；**盲评：不显示 r5 判定**。判定单位 = 候选 × r5-required 槽位。",
          "> 标签口径同 Gate B：omission / covered / requirement_uncertain / "
          "representation_boundary / non_required + 候选级 unnecessary_stages。", ""]
    for g in packet_groups:
        md += [f"## 组 {g['k']}（{g['band']}）", "", "**任务全文：**", "",
               g["task"], "", "**r5-required 槽位：**",
               ", ".join(s["slot"] for s in g["required_slots"]) or "（无）", ""]
        if g["requirement_uncertain_slots"] or g["vocab_gap_signals"]:
            md += [f"（解析注：uncertain = {g['requirement_uncertain_slots'] or '无'}；"
                   f"词表边界 = {g['vocab_gap_signals'] or '无'}）", ""]
        for c in g["candidates"]:
            md += [f"### 候选 {c['cand']}", "```",
                   *[f"{s['seq']}. {s['family']} x{s['repeat']}"
                     for s in c["stages"] if isinstance(s, dict)], "```", ""]

    (RL / "eval_procurement/EVAL_SET_BLIND_PACKET_V1.md").write_text(
        "\n".join(md), encoding="utf-8")

    summary = {
        "n_candidates": len(per_cand), "n_tasks": len(packet_groups),
        "config": cfg,
        "sha": {"preds": sha256(EP / "preds.json"),
                "config": sha256(EP / "config.json"),
                "tasks": sha256(EP / "eval_set_24_tasks.jsonl"),
                "r5_outputs": sha256(RL / "eval_procurement/eval_set_r5_outputs_v051.json"),
                "blind_packet": sha256(RL / "eval_procurement/EVAL_SET_BLIND_PACKET_V1.md")},
        "groups": packet_groups,
    }
    (RL / "eval_procurement/eval_set_scored_v051.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"scored: {len(per_cand)} candidates, {len(packet_groups)} tasks")
    print("blind packet + r5 outputs written; SHAs in eval_set_scored_v051.json")


if __name__ == "__main__":
    main()
