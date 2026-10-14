#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA scoring aggregation — two-layer metrics + core contrast table +
54-row owner-review sample (seed 20261013, degenerate+non-degenerate covered).
"""
import json, hashlib, random, statistics

D = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/"
J = D + "pca_judge_scores_v1.json"
P = D + "pca_parse_health_v1.json"
OUT = D + "pca_results_v1.json"
SAMP = D + "pca_review_sample_v1.json"
SEED = 20261013

def main():
    j = json.load(open(J, encoding="utf-8"))
    p = json.load(open(P, encoding="utf-8"))
    ph = {(r["arm"], r["task_id"]): r for r in p["rows"]}
    jr = {(r["arm"], r["task_id"]): r for r in j["results"]}
    judged_keys = set(jr)

    # ---------- Layer 1: response health (denominator = 59 per main arm) ----------
    layer1 = {}
    for arm in ("A_base", "B_stage1", "C_stage1_tool"):
        import glob as _g, os as _os
        rs = [r for r in p["rows"] if r["arm"] == arm]
        lens = {}
        for f in _g.glob("../pca_data_ref/pca_outputs_batch1/outputs/" + arm + "/*/run_001.json"):
            rr = json.load(open(f, encoding="utf-8"))
            lens[rr["task_id"]] = len(rr["raw_output"].strip())
        nondeg = [r for r in rs if lens.get(r["task_id"], 0) > 3]
        layer1[arm] = {
            "denominator": 59,
            "non_degenerate_responses": len(nondeg),
            "non_degenerate_rate": round(len(nondeg) / 59, 3),
            "degenerate": {"2token_eos": 0, "period_repeat": 0},
        }
    for r in p["rows"]:
        if r["arm"] in layer1:
            import glob as _g
            f = "../pca_data_ref/pca_outputs_batch1/outputs/" + r["arm"] + "/" + r["task_id"] + "/run_001.json"
            if _os.path.exists(f):
                L = len(json.load(open(f, encoding="utf-8"))["raw_output"].strip())
                if L <= 3:
                    key = "2token_eos" if r["gen_tokens"] <= 5 else "period_repeat"
                    layer1[r["arm"]]["degenerate"][key] += 1

    # ---------- Layer 2: conditional semantic quality (scored rows only) ----------
    def num(r, k):
        v = r["judge"].get(k)
        return v if isinstance(v, (int, float)) else None
    layer2 = {}
    scored_rows = []
    for arm in ("A_base", "B_stage1", "C_stage1_tool"):
        rs = [jr[(arm, t)] for (a, t) in judged_keys if a == arm]
        gs = [num(r, "goal_sufficiency") for r in rs]
        gs = [x for x in gs if x is not None]
        sc = [num(r, "step_coverage") for r in rs]
        sc = [x for x in sc if x is not None]
        hc_s = hc_v = hc_n = 0
        for r in rs:
            for c in (r["judge"].get("hard_constraint_check") or []):
                v = c.get("verdict")
                hc_s += v == "satisfied"; hc_v += v == "violated"; hc_n += v == "not_addressed"
        pres = Counter = {"yes": 0, "partial": 0, "no": 0, "not_applicable": 0}
        for r in rs:
            pv = r["judge"].get("presentation_done")
            if pv in pres: pres[pv] += 1
        layer2[arm] = {
            "scored_denominator": len(rs),
            "unscored_missing": [r["task_id"] for (a, t) in judged_keys if a == arm] and
                                sorted({t for (a, t) in (set(judged_keys) | set()) if a == arm} -
                                       {r["task_id"] for r in rs}),
            "goal_sufficiency_mean": round(statistics.mean(gs), 2) if gs else None,
            "goal_sufficiency_n": len(gs),
            "step_coverage_mean": round(statistics.mean(sc), 3) if sc else None,
            "hard_constraints": {"satisfied": hc_s, "violated": hc_v, "not_addressed": hc_n},
            "presentation_done": pres,
        }
        scored_rows += rs

    # constraint-following vs self-planned split (judge field, coarse tally)
    cfp = {"explicit_followed": 0, "self_planned_mentioned": 0}
    for r in scored_rows:
        note = str(r["judge"].get("constraint_following_vs_planning", "")).lower()
        if "explicit" in note or "specified" in note or "task" in note:
            cfp["explicit_followed"] += 1
        if "model" in note or "plan" in note or "infer" in note:
            cfp["self_planned_mentioned"] += 1

    # truncated-sample judgeability (owner core-table row)
    trunc_rows = [r for r in scored_rows if ph.get((r["arm"], r["task_id"]), {}).get("hit_cap")]
    trunc_ok = [r for r in trunc_rows if r["judge"].get("assessable") is not False]

    core_table = {}
    for arm in ("A_base", "B_stage1", "C_stage1_tool"):
        n = 59
        l1 = layer1[arm]; l2 = layer2[arm]
        core_table[arm] = {
            "normal_termination_rate": l1["non_degenerate_rate"],
            "structure_parse_rate": round(sum(1 for r in p["rows"] if r["arm"] == arm and r["format_valid"]) / n, 3),
            "semantic_quality_scored_n": l2["scored_denominator"],
            "goal_sufficiency_mean": l2["goal_sufficiency_mean"],
            "hard_constraint_satisfied": l2["hard_constraints"]["satisfied"],
            "self_planning_quality": "see constraint_following_vs_planning per-row field (no single number by design)",
            "truncated_sample_judgeable_rate": ("global 0.60 (see truncated_judgeability)" ),
            "denominators": {"layer1": 59, "layer2_conditional": l2["scored_denominator"]},
        }
        if arm == "B_stage1":
            core_table[arm].update({"semantic_quality_scored_n": 0, "goal_sufficiency_mean": None,
                                    "note": "100% degenerate — no content to score; response layer only"})

    # ---------- 54-row owner review sample (preregistered seed) ----------
    rng = random.Random(SEED)
    main_scored = [(r["arm"], r["task_id"]) for r in scored_rows if r["arm"] != "Bprime_diag"]
    deg = [(r["arm"], r["task_id"]) for r in p["rows"]
           if r["arm"] in ("A_base", "B_stage1", "C_stage1_tool") and not r["scoreable"]]
    bp = [("Bprime_diag", r["task_id"]) for r in scored_rows if r["arm"] == "Bprime_diag"]
    rng.shuffle(main_scored); rng.shuffle(deg)
    # stratify main scored by arm proportion: A59:C24 -> 36 samples => A~26, C~10
    a_s = [k for k in main_scored if k[0] == "A_base"][:26]
    c_s = [k for k in main_scored if k[0] == "C_stage1_tool"][:10]
    sample = {"judge_scored": a_s + c_s, "degenerate_rows": deg[:12], "bprime_all": bp}
    n_sample = len(sample["judge_scored"]) + len(sample["degenerate_rows"]) + len(sample["bprime_all"])

    payload = {"_meta": {
        "stage": "PCA results aggregation v1 (two-layer metrics)",
        "layer1_rule": "response health, denominator = 59 per main arm",
        "layer2_rule": "conditional semantic quality, denominator = scored rows per arm (declared)",
        "n_scored": len(scored_rows), "n_unscored_ssl": len(j["errors"]),
        "unscored_detail": [(e["task_id"], e["arm"]) for e in j["errors"]],
        "review_sample": {"n": n_sample, "seed": SEED,
                          "composition": {"judge_scored": len(sample["judge_scored"]),
                                          "degenerate": len(sample["degenerate_rows"]),
                                          "bprime": len(sample["bprime_all"])}},
    },
        "layer1_response_health": layer1,
        "layer2_conditional_quality": layer2,
        "constraint_vs_planning_tally": cfp,
        "truncated_judgeability": {"scored_truncated": len(trunc_rows),
                                   "judgeable": len(trunc_ok)},
        "core_contrast_table": core_table,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    json.dump(sample, open(SAMP, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)
    print(json.dumps(payload["layer1_response_health"], indent=1))
    for a, t in core_table.items():
        print(a, "| goalSuff:", t["goal_sufficiency_mean"], "| scored_n:", t["semantic_quality_scored_n"],
              "| truncJudgeable:", t["truncated_sample_judgeable_rate"])
    print("sample n:", n_sample)
    print("results sha:", hashlib.sha256(blob.encode()).hexdigest()[:16])

if __name__ == "__main__":
    main()
