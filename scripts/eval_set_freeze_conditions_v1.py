#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Freeze the three pre-launch conditions (owner round-17) as computable
specs + E0 baselines, BEFORE any GRPO run:

  Cond-1: slot-coverage formula pinned (per-candidate -> task -> eval-set
          aggregation; no-scorable-slot tasks listed by ID; TERRAIN and
          not_required/uncertain slots excluded from both denominators).
  Cond-2: DeltaC / DeltaF definitions + simultaneous acceptance table.
  Cond-3: gaming-check rules with computable definitions and E0 baselines.

Also extracts the b1 gold semantic chains for the 24 eval tasks (the ordered
stage-F1 reference) and computes F_E0 / C_E0 / gaming baselines from the
frozen 192 candidates. NOTHING here modifies rules, labels, or the model.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys_path = str(REPO / "scripts")
import sys
sys.path.insert(0, sys_path)
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402
from rl_reward_v1 import evaluate_prediction, load_vocab  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
EP = RL / "eval_procurement"
B1 = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system"
          r"\Algorithm_classification\server_backup_mdzhang_20260927"
          r"\home\qy\system_redesign\outputs_v2\gee_b1_stage_data_v1"
          r"\b1_gee_stage_train.jsonl")


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def expand(stages):
    """repeat-expanded family sequence"""
    out = []
    for s in stages:
        fam = s.get("family")
        if isinstance(fam, str):
            out.extend([fam] * max(1, int(s.get("repeat", 1))))
    return out


def lcs_f1(a, b):
    """order-sensitive LCS F1 over two family sequences"""
    if not a or not b:
        return 0.0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    lcs = prev[-1]
    p = lcs / len(a)
    r = lcs / len(b)
    return (2 * p * r / (p + r)) if (p + r) else 0.0


def main():
    preds = json.loads((EP / "preds.json").read_text(encoding="utf-8"))
    tasks = {json.loads(l)["script"]: json.loads(l)
             for l in (EP / "eval_set_24_tasks.jsonl").read_text(encoding="utf-8").splitlines()}
    vocab = load_vocab(RL / "vocab23_server_verified.json")

    # ---- gold chains from b1 for the 24 eval scripts ----
    want = set(tasks)
    gold = {}
    with open(B1, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("script") in want:
                gold[r["script"]] = [x.strip() for x in
                                     (r.get("semantic_chain_rle") or "").split("->")
                                     if x.strip()]
    missing_gold = sorted(want - set(gold))
    print(f"gold chains: {len(gold)}/24; missing: {missing_gold}")

    # ---- per-candidate: C (coverage, adjudicable universe) + F (ordered LCS-F1
    #      vs gold) + gaming measures ----
    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    rows = []
    for k, grp in sorted(by_group.items()):
        task = tasks[k]["task"]
        gold_seq = gold.get(k, [])
        parse = evaluate_pair(task, {"stages": []})["parse"]
        req_scored = [s["id"] for s in parse["slots"]
                      if s["state"] == "required"
                      and s.get("scoring") != "unscored_representation_boundary"]
        for p in grp:
            try:
                b = json.loads(p["pred_text"])
            except Exception:
                b = None
            if b is None or not isinstance(b.get("stages"), list):
                rows.append({"k": k, "cand": p["cand"], "band": p["band"],
                             "C_cand": None, "F_cand": None,
                             "parse_ok": False, "n_stages": 0,
                             "adjacent_dup": 0, "unlinked_stages": 0})
                continue
            stages = b.get("stages") or []
            fams = [s.get("family") for s in stages if isinstance(s, dict)
                    and isinstance(s.get("family"), str)]
            fam_set = set(fams)
            res = evaluate_pair(task, b)["score"]
            covered = missing = 0
            for s in res["per_slot"]:
                if s["slot"] in req_scored:
                    if s["coverage"].startswith("covered"):
                        covered += 1
                    elif s["coverage"] == "missing":
                        missing += 1
            c_cand = (covered / (covered + missing)) if (covered + missing) else None
            f_cand = (lcs_f1(fams, gold_seq) if gold_seq else None)
            # gaming measures
            n_stages = len(stages)
            adj_dup = sum(1 for i in range(1, len(fams)) if fams[i] == fams[i - 1])
            unlinked = res.get("unlinked_content_families_audit_only", [])
            unlinked_n = sum(1 for f in fams if f in set(unlinked))
            rows.append({"k": k, "cand": p["cand"], "band": p["band"],
                         "C_cand": c_cand, "F_cand": round(f_cand, 4) if gold_seq else None,
                         "parse_ok": b is not None,
                         "n_stages": n_stages, "adjacent_dup": adj_dup,
                         "unlinked_stages": unlinked_n})

    # ---- aggregations (pinned formulas) ----
    task_c, task_f = {}, {}
    for k in tasks:
        rs = [r for r in rows if r["k"] == k]
        cs = [r["C_cand"] for r in rs if r["C_cand"] is not None]
        fs = [r["F_cand"] for r in rs if r["F_cand"] is not None]
        if cs:
            task_c[k] = sum(cs) / len(cs)
        if fs:
            task_f[k] = sum(fs) / len(fs)
    no_scorable = sorted(k for k in tasks if k not in task_c)
    C_E0 = (sum(task_c.values()) / len(task_c)) if task_c else None
    F_E0 = (sum(task_f.values()) / len(task_f)) if task_f else None

    empty_rate = sum(1 for r in rows if not r["parse_ok"]) / len(rows)
    adj_dup_rate = (sum(r["adjacent_dup"] for r in rows)
                    / max(1, sum(r["n_stages"] for r in rows)))
    unlinked_rate = (sum(r["unlinked_stages"] for r in rows)
                     / max(1, sum(r["n_stages"] for r in rows)))
    overgen = sum(r["n_stages"] for r in rows) / len(rows)

    gaming = [
        {"metric": "empty_or_unparseable_rate", "baseline_E0": round(empty_rate, 4),
         "trigger": "increase > 5pp vs E0 -> DIRECT FAIL (same as parse safety line)"},
        {"metric": "adjacent_duplicate_family_rate", "baseline_E0": round(adj_dup_rate, 4),
         "trigger": "increase > 5pp -> HUMAN REVIEW; > 10pp -> DIRECT FAIL"},
        {"metric": "irrelevant_unlinked_stage_rate", "baseline_E0": round(unlinked_rate, 4),
         "trigger": "increase > 10pp -> HUMAN REVIEW"},
        {"metric": "overgeneration_mean_stages", "baseline_E0": round(overgen, 2),
         "trigger": "relative increase > 25% -> HUMAN REVIEW"},
    ]

    # ---- frozen spec ----
    spec = {
        "label": "eval_set_frozen_formulas_and_E0_baselines (owner round-17)",
        "cond1_coverage_formula": {
            "candidate_level": ("C_cand = covered_required / (covered_required + "
                                "missing_required), over v0.6 `required` slots "
                                "EXCLUDING TERRAIN (unscored) and "
                                "not_required/requirement_uncertain; covered "
                                "includes covered + covered_coarse"),
            "task_level": "C_task = mean(C_cand over the task's 8 candidates)",
            "eval_level": "C_eval = mean(C_task over tasks WITH scorable slots)",
            "no_scorable_slot_tasks_excluded": no_scorable,
            "same_frozen_eval_set_and_v06_parser_for_E0_E1": True,
        },
        "cond2_delta_definitions": {
            "dC": "C_eval(E1) - C_eval(E0)  [percentage points]",
            "dF": "F_eval(E1) - F_eval(E0)  [percentage points]",
            "acceptance_all_simultaneous": [
                "dC >= +5pp",
                "dF >= -3pp",
                "parse-rate drop <= 5pp",
                "invalid-rate rise <= 5pp",
                "no gaming red line"],
            "no_tradeoff": "no single-metric gain offsets another metric's "
                           "degradation",
            "reporting": "task-level change distribution + per-task counts "
                         "attached; 5pp = engineering threshold, NOT "
                         "statistical significance",
        },
        "cond3_gaming_checks_frozen": gaming,
        "E0_baselines": {
            "C_E0_task_level_mean": round(C_E0, 4) if C_E0 is not None else None,
            "F_E0_task_level_mean": round(F_E0, 4) if F_E0 is not None else None,
            "gold_reference": "b1 semantic_chain_rle of the same scripts "
                              "(the tasks' true chains; degradation co-gate "
                              "reference, NOT a multisolution-improvement "
                              "reference)",
            "gold_missing": missing_gold,
        },
        "task_table": {"C_task": {k: round(v, 4) for k, v in task_c.items()},
                       "F_task": {k: round(v, 4) for k, v in task_f.items()}},
        "rows": rows,
    }
    out_path = EP / "eval_set_frozen_spec_v1.json"
    out_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"C_E0 = {C_E0:.4f} | F_E0 = {F_E0:.4f}")
    print(f"no-scorable-slot tasks ({len(no_scorable)}): {no_scorable}")
    print(json.dumps(gaming, ensure_ascii=False, indent=2))
    print("written:", out_path)


if __name__ == "__main__":
    from collections import defaultdict
    main()
