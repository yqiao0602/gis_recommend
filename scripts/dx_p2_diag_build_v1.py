#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 generation-failure diagnostic (owner-approved, read-only).

Population: the 158 A1 affected steps x 2 arms (control v0_4 / experiment v0_5).
Events are deduplicated per item; the 52 review pairs are a SUBSET reported
separately (paired failure states preserved).

Outputs:
  _p2_diag_work/prompts.json        prompts for server-side Qwen tokenization
  p2_diag_v1/P2_DIAGNOSTIC_RAW_V1.json  per-item facts (no interpretation)
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_s23 import S2_PROMPT, parse_s2_v2  # noqa: E402
from diag50_b3_build_pack_v1 import full_card  # noqa: E402

SHORT = REPO.parent
CTRL_TREE = SHORT / "dx50_short/runs"
A1_CTRL = SHORT / "_a1_work/runs_local"
A1 = SHORT / "a1_short"
WORK = SHORT / "_p2_diag_work"
OUT = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
               "dx50_full_v1/p2_diag_v1"))


def load(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "_meta"}


def arm_facts(run_dir, oids, prof_for_prompt, step, task_text):
    raw = (run_dir / "raw_output.txt").read_text(encoding="utf-8")
    g = json.loads((run_dir / "gen.json").read_text(encoding="utf-8"))
    parsed = parse_s2_v2(raw, oids)
    cards = "\n\n".join(full_card(o, prof_for_prompt)[0] for o in oids)
    prompt = S2_PROMPT.format(k=step["num"], name=step["name"],
                              purpose=step["fields"].get("purpose", "-"),
                              inp=step["fields"].get("input", "-"),
                              out=step["fields"].get("output", "-"),
                              cards=cards)
    return {"raw_bytes": len(raw.encode()), "empty": not raw.strip(),
            "has_think_open": "<think>" in raw, "has_think_close": "</think>" in raw,
            "decision_section": parsed.get("decision_section"),
            "no_operator": bool(parsed.get("no_operator_for_step")),
            "sel_in": parsed.get("selected_in_candidates") or [],
            "sel_out": parsed.get("selected_outside_candidates") or [],
            "term": g.get("term"), "gen_tokens": g.get("gen_tokens"),
            "maxnew": g.get("maxnew"),
            "prompt_chars": len(prompt), "card_chars": len(cards),
            "task_chars": len(task_text), "prompt": prompt}


def main():
    prof4 = load(REPO / "route2_training/profile/"
                 "qgis_operator_capability_profile_v0_4.json")
    prof5 = load(REPO / "route2_training/profile/"
                 "qgis_operator_capability_profile_v0_5.json")
    affected = {r["step_key"]: r for r in json.loads(
        (A1 / "A1_AFFECTED_SET_V1.json").read_text(encoding="utf-8")
    )["affected_steps"]}
    tasks = {}
    from dx_common import PCA2
    for line in (PCA2 / "pca2_taskset_100.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        tasks[r["pid"]] = r["instruction"]

    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, prompts = [], []
    for key in sorted(affected):
        tid, snum = key.split("#S")
        snum = int(snum)
        s0 = json.loads((CTRL_TREE / tid / "S0" / "parsed.json")
                        .read_text(encoding="utf-8"))
        step = next(x for x in s0["steps"] if x["num"] == snum)
        retr = {x["step"]: x for x in json.loads(
            (CTRL_TREE / tid / "S1" / "retrieval.json").read_text(
                encoding="utf-8")).get("steps", [])}
        oids = [c["operator_id"] for c in retr[snum]["top10"]]
        n_steps = len(s0["steps"])
        meta = {"step_key": key, "task": tid, "step_num": snum,
                "n_steps": n_steps, "is_last": snum == n_steps,
                "pos_ratio": round(snum / n_steps, 3)}
        c = arm_facts(CTRL_TREE / tid / "S2" / f"S{snum}", oids, prof4,
                      step, tasks[tid])
        e = arm_facts(A1_CTRL / tid / "S2" / f"S{snum}", oids, prof5,
                      step, tasks[tid])
        prompts.append({"key": key, "arm": "control", "prompt": c.pop("prompt")})
        prompts.append({"key": key, "arm": "experiment", "prompt": e.pop("prompt")})
        rows.append({**meta, "control": c, "experiment": e})

    (WORK / "prompts.json").write_text(
        json.dumps(prompts, ensure_ascii=False), encoding="utf-8")
    (OUT / "P2_DIAGNOSTIC_RAW_V1.json").write_text(
        json.dumps({"n_items": len(rows), "items": rows},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("items:", len(rows), "| prompts:", len(prompts),
          "| chars avg:", sum(len(p["prompt"]) for p in prompts) // len(prompts))


if __name__ == "__main__":
    main()
