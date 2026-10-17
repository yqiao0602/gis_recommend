#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 experiment step 1: compute the OTB-affected step set + control-arm
alignment proof.

A1 design (owner ruling 2026-10-17, "冻结 v0_5，立即开始 A1 配对实验"):
  - Control arm = the frozen dx50_full_v1 S2 records (v0_4 cards, committed).
  - Experiment arm = same steps, same S1 Top-10 order, same prompts EXCEPT the
    OTB operator cards, now rendered from profile v0_5.
  - A step is AFFECTED iff any of its Top-10 cards differs between v0_4 and
    v0_5. Unaffected steps have byte-identical prompts, so the frozen run IS
    their control - they are excluded by construction, not re-run.

For every affected step this script re-renders the CONTROL prompt (v0_4 cards)
and checks sha16 == the frozen record.json prompt_sha16 - proving the frozen
record is exactly the v0_4 arm of the pair (alignment proof, preregistered).

Output: dx50_full_v1/a1_v1/A1_AFFECTED_SET_V1.json
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_common import PCA2  # noqa: E402
from dx_s23 import S2_PROMPT  # noqa: E402
from diag50_b3_build_pack_v1 import full_card  # noqa: E402

FULL = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
                "dx50_full_v1"))
RUNS = FULL / "runs"
A1 = FULL / "a1_v1"


def load_profile_path(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "_meta"}


def sha16(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def main():
    prof4 = load_profile_path(REPO / "route2_training/profile/"
                              "qgis_operator_capability_profile_v0_4.json")
    prof5 = load_profile_path(REPO / "route2_training/profile/"
                              "qgis_operator_capability_profile_v0_5.json")
    tasks = {}
    for line in (PCA2 / "pca2_taskset_100.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        tasks[r["pid"]] = r["instruction"]

    affected, unaffected = [], []
    align_fail = []
    n_steps_total = 0
    for task_dir in sorted(RUNS.glob("PCA2-T-*")):
        tid = task_dir.name
        s0p = task_dir / "S0" / "parsed.json"
        r1p = task_dir / "S1" / "retrieval.json"
        if not s0p.exists() or not r1p.exists():
            continue
        s0 = json.loads(s0p.read_text(encoding="utf-8"))
        if s0.get("parse") != "ok":
            continue
        retr = {x["step"]: x for x in json.loads(
            r1p.read_text(encoding="utf-8")).get("steps", [])}
        for st in s0.get("steps", []):
            n_steps_total += 1
            cands = retr.get(st["num"], {}).get("top10") or []
            oids = [c["operator_id"] for c in cands]
            cards4 = "\n\n".join(full_card(o, prof4)[0] for o in oids)
            cards5 = "\n\n".join(full_card(o, prof5)[0] for o in oids)
            step_key = f"{tid}#S{st['num']}"
            row = {"step_key": step_key, "n_candidates": len(oids),
                   "has_otb_candidate": any(o.startswith("otb:") for o in oids),
                   "cards_identical": cards4 == cards5}
            if cards4 == cards5:
                unaffected.append(row)
                continue
            # affected: prove the control arm alignment with the frozen record
            rec_path = task_dir / "S2" / f"S{st['num']}" / "record.json"
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            prompt4 = S2_PROMPT.format(
                k=st["num"], name=st["name"],
                purpose=st["fields"].get("purpose", "-"),
                inp=st["fields"].get("input", "-"),
                out=st["fields"].get("output", "-"), cards=cards4)
            prompt5 = S2_PROMPT.format(
                k=st["num"], name=st["name"],
                purpose=st["fields"].get("purpose", "-"),
                inp=st["fields"].get("input", "-"),
                out=st["fields"].get("output", "-"), cards=cards5)
            row["control_prompt_sha16"] = sha16(prompt4)
            row["frozen_prompt_sha16"] = rec.get("prompt_sha16")
            row["experiment_prompt_sha16"] = sha16(prompt5)
            row["aligned"] = (row["control_prompt_sha16"]
                              == row["frozen_prompt_sha16"])
            if not row["aligned"]:
                align_fail.append(step_key)
            row["changed_oids"] = [o for o, c4, c5 in zip(
                oids, cards4.split("\n\n"), cards5.split("\n\n")) if c4 != c5]
            affected.append(row)

    result = {
        "date": "2026-10-17",
        "definition": "affected = any Top-10 card differs between v0_4 and v0_5",
        "n_steps_total": n_steps_total,
        "n_affected": len(affected),
        "n_unaffected_excluded": len(unaffected),
        "alignment_failures": align_fail,
        "alignment_ok": len(align_fail) == 0,
        "affected_steps": affected,
        "arms": {
            "control": "frozen dx50_full_v1 S2 records (v0_4 cards, committed)",
            "experiment": "A1 v0_5 pack (same steps/Top-10/template; only "
                          "OTB cards re-rendered from v0_5)",
        },
    }
    A1.mkdir(parents=True, exist_ok=True)
    (A1 / "A1_AFFECTED_SET_V1.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in
                      ("n_steps_total", "n_affected",
                       "n_unaffected_excluded", "alignment_ok",
                       "alignment_failures")}, ensure_ascii=False))
    otb_affected = sum(1 for r in affected if r["has_otb_candidate"])
    print("affected with otb candidate:", otb_affected,
          "| affected without otb (indirect):", len(affected) - otb_affected)


if __name__ == "__main__":
    main()
