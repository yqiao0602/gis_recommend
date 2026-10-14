#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0-S3 comparison on the eval set (owner round-14 step 4).

Alignment: both r5 coverage and owner score use the OWNER-ADJUDICABLE slot
universe — TERRAIN slots (owner caliber: always B) are excluded from BOTH
denominators. Empty candidates excluded. lambda grid per contract.
Metrics: the four pre-registered (task-level primary, n=24 tasks but 4
fully-abstained + 3 all-empty groups -> scorable task count reported).
"""
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402
from rl_reward_v1 import evaluate_prediction, load_vocab  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
EP = RL / "eval_procurement"
LAMBDAS = (0.0, 0.3, 0.5, 0.7, 1.0)


def main():
    preds = json.loads((EP / "preds.json").read_text(encoding="utf-8"))
    unblind = json.loads((EP / "eval_set_gate_b_unblind_v1.json").read_text(encoding="utf-8"))
    tasks = {json.loads(l)["script"]: json.loads(l)
             for l in (EP / "eval_set_24_tasks.jsonl").read_text(encoding="utf-8").splitlines()}
    vocab = load_vocab(RL / "vocab23_server_verified.json")

    # owner per-candidate covered/required over adjudicable (O/C) slots only
    own = defaultdict(lambda: {"cov": 0, "req": 0, "has_O": False})
    for r in unblind["rows"]:
        if r["owner"] in ("O", "C"):
            e = own[(r["k"], r["cand"])]
            e["req"] += 1
            e["cov"] += 1 if r["owner"] == "C" else 0
            e["has_O"] |= (r["owner"] == "O")

    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    # r5 per-candidate coverage over NON-TERRAIN required slots (aligned universe)
    cands = []
    for k, grp in sorted(by_group.items()):
        task = tasks[k]["task"]
        pr = evaluate_pair(task, {"stages": []})["parse"]
        req_slots = [s for s in pr["slots"] if s["state"] == "required"]
        for p in grp:
            try:
                b = json.loads(p["pred_text"])
            except Exception:
                continue
            if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
                continue  # empty candidate excluded
            res = evaluate_pair(task, b)["score"]
            # aligned r5 coverage: drop TERRAIN-slot entries
            rel = [s for s in res["per_slot"] if s["slot"] != "TERRAIN"]
            covered = sum(1 for s in rel if s["coverage"].startswith("covered"))
            missing = sum(1 for s in rel if s["coverage"] == "missing")
            r5_cov = (covered / (covered + missing)) if (covered + missing) else None
            formal = evaluate_prediction(p["pred_text"], vocab).training_reward
            e = own.get((k, p["cand"]), {"cov": 0, "req": 0, "has_O": False})
            owner_score = (e["cov"] / e["req"]) if e["req"] else None
            cands.append({"k": k, "cand": p["cand"], "struct": formal,
                          "cov": r5_cov, "owner": owner_score,
                          "owner_has_O": e["has_O"],
                          "adjudicable": e["req"]})

    # group by task; only tasks with >=2 candidates having adjudicable owner scores
    groups = defaultdict(list)
    for c in cands:
        if c["owner"] is not None:
            groups[c["k"]].append(c)
    scorable = {k: g for k, g in groups.items() if len(g) >= 2}

    def evaluate_scorer(key):
        disc = fr = sat = 0
        taus = []
        for k, cands in scorable.items():
            vals = {c.get(key) for c in cands if c.get(key) is not None}
            saturated = len(vals) <= 1
            sat += saturated
            conc = disc_ = total = 0
            fr_g = False
            full = [c for c in cands if c["owner"] == 1.0]
            omiss = [c for c in cands if c["owner_has_O"]]
            for a, b in itertools.combinations(cands, 2):
                if a["owner"] == b["owner"]:
                    continue
                total += 1
                sa, sb = a.get(key), b.get(key)
                if sa is None or sb is None:
                    continue
                if (sa - sb) * (a["owner"] - b["owner"]) > 0:
                    conc += 1
                else:
                    disc_ += 1
            if full and omiss:
                fr_g = max((c.get(key) or 0) for c in omiss) >= \
                       min((c.get(key) or 0) for c in full)
            fr += fr_g
            if total:
                taus.append((conc - disc_) / total)
            disc += (1 if (len(vals) > 1 and disc_ == 0) else 0)
        return {"disc": f"{disc}/{len(scorable)}",
                "mean_tau": (round(sum(taus) / len(taus), 4) if taus else None),
                "false_reward_groups": fr, "saturated_groups": sat}

    metrics = {"S0_r5_only": evaluate_scorer("cov"),
               "S1_structure_only": evaluate_scorer("struct")}
    for lam in LAMBDAS:
        key = f"comb_{lam}"
        for c in cands:
            if c["struct"] is not None and c["cov"] is not None:
                c[key] = round(lam * c["struct"] + (1 - lam) * c["cov"], 4)
        metrics[f"S1_lambda_{lam}"] = evaluate_scorer(key)

    out = {
        "label": "eval_set_S0_S3_one_shot_comparison",
        "scorable_tasks": len(scorable),
        "excluded": {"empty_candidates": 27,
                     "no_required_slot_tasks": 4,
                     "fully_abstained_tasks": 4,
                     "terrain_unadjudicable": "excluded from both denominators"},
        "metrics": metrics,
    }
    (EP / "eval_set_s0s3_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, m in metrics.items():
        print(f"{name}: disc={m['disc']} tau={m['mean_tau']} "
              f"false_reward={m['false_reward_groups']} sat={m['saturated_groups']}")


if __name__ == "__main__":
    main()
