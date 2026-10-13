#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate D: offline reward ranking analysis (pre-registered metrics).

Three scorings on the 10 independent tasks (80 candidates, owner Gate B
labels): structure formal reward, r5 coverage_ratio, and combined
R = lambda*struct + (1-lambda)*cov for lambda in {0.3, 0.5, 0.7}.

Pre-registered metrics (GATE_CD_PREREGISTRATION_V1.md):
  - within-task discrimination rate: groups where the scoring produces >=2
    distinct values AND pair-wise ordering agrees with owner labels (>=70%)
  - ranking consistency: pairwise concordance tau on groups with both
    varying (>=0.6)
  - false-reward rate: groups where an owner-omission-containing candidate
    scores >= an all-covered candidate (<=10%)
  - saturation: fraction of groups with all-identical scores (report only)
All metrics reported at task level; candidate counts shown as denominators.
"""
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
LAMBDAS = (0.3, 0.5, 0.7)


def main():
    preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
    scored = json.loads((RL / "s2_dryrun/S2_DRYRUN_SCORED_V1.json").read_text(encoding="utf-8"))
    formal = {(r["k"], r["cand"]): r["formal_reward"] for r in scored["rows"]}
    labels = json.loads((RL / "gate_b_labels_frozen_v1.json").read_text(encoding="utf-8"))
    tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
    tasks.update(json.loads((RL / "r5_audit_tasks_rest.json").read_text(encoding="utf-8")))

    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    out_groups = {}
    for k, grp in sorted(by_group.items()):
        lab = labels["groups"].get(str(k))
        if lab is None:
            continue  # not in the Gate B independent set
        task = tasks[str(k)]
        cands = []
        for p in grp:
            try:
                b = json.loads(p["pred_text"])
            except Exception:
                continue
            if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
                continue
            res = evaluate_pair(task, b)["score"]
            cands.append({"cand": p["cand"], "struct": formal.get((p["k"], p["cand"])),
                          "cov": res["coverage_ratio"],
                          "owner": None, "owner_has_O": False})
        # owner coverage score + has_O from Gate B labels: slot -> {cand: label}
        slot_map = lab
        for c in cands:
            covered = required = 0
            for slot, cand_labels in slot_map.items():
                owner = cand_labels.get(str(c["cand"]))
                if owner is None:
                    continue
                required += 1
                covered += 1 if owner == "C" else 0
                if owner == "O":
                    c["owner_has_O"] = True
            c["owner"] = (covered / required) if required else None
        out_groups[str(k)] = cands

    def pairwise(cands, key):
        """concordant, discordant, total over pairs with differing owner scores;
        also false-reward flag for the group."""
        conc = disc = total = 0
        fr = False
        full = [c for c in cands if c["owner"] is not None and c["owner"] == 1.0]
        omiss = [c for c in cands if c["owner"] is not None and c["owner_has_O"]]
        for (a, b) in itertools.combinations(cands, 2):
            da, db = a["owner"], b["owner"]
            if da is None or db is None or da == db:
                continue
            total += 1
            sa, sb = a[key], b[key]
            if sa is None or sb is None:
                continue
            if (sa - sb) * (da - db) > 0:
                conc += 1
            else:
                disc += 1
        if full and omiss:
            best_omiss = max(c[key] for c in omiss if c[key] is not None)
            worst_full = min(c[key] for c in full if c[key] is not None)
            fr = best_omiss >= worst_full
        return conc, disc, total, fr

    metrics = {}
    for name, key in [("structure", "struct"), ("r5_coverage", "cov")]:
        disc_groups = sat_groups = fr_groups = 0
        taus = []
        per = {}
        for k, cands in out_groups.items():
            vals = {c[key] for c in cands if c[key] is not None}
            saturated = len(vals) <= 1
            sat_groups += saturated
            conc, disc, total, fr = pairwise(cands, key)
            fr_groups += fr
            tau = ((conc - disc) / total) if total else None
            if tau is not None:
                taus.append(tau)
            distinct = len(vals) > 1
            aligned = (disc == 0) if total else False
            disc_groups += (1 if (distinct and aligned) else 0)
            per[k] = {"distinct": distinct, "aligned": aligned,
                      "concordant": conc, "discordant": disc,
                      "tau": tau, "saturated": saturated, "false_reward": fr}
        metrics[name] = {
            "within_task_discrimination": f"{disc_groups}/{len(out_groups)}",
            "mean_tau": (round(sum(taus) / len(taus), 4) if taus else None),
            "false_reward_groups": fr_groups,
            "saturated_groups": sat_groups,
            "per_task": per,
        }
    for lam in LAMBDAS:
        key = f"combined_{lam}"
        for k, cands in out_groups.items():
            for c in cands:
                if c["struct"] is not None and c["cov"] is not None:
                    c[key] = round(lam * c["struct"] + (1 - lam) * c["cov"], 4)
        disc_groups = fr_groups = sat_groups = 0
        taus = []
        for k, cands in out_groups.items():
            vals = {c.get(key) for c in cands if c.get(key) is not None}
            sat_groups += (len(vals) <= 1)
            conc = disc = total = 0
            fr = False
            full = [c for c in cands if c["owner"] == 1.0]
            omiss = [c for c in cands if c["owner_has_O"]]
            for a, b in itertools.combinations(cands, 2):
                if a["owner"] is None or b["owner"] is None or a["owner"] == b["owner"]:
                    continue
                total += 1
                sa, sb = a.get(key), b.get(key)
                if sa is None or sb is None:
                    continue
                if (sa - sb) * (a["owner"] - b["owner"]) > 0:
                    conc += 1
                else:
                    disc += 1
            if full and omiss:
                fr = max(c.get(key) or 0 for c in omiss) >= min(c.get(key) or 0 for c in full)
            fr_groups += fr
            taus.append(((conc - disc) / total) if total else None)
            disc_groups += (1 if (len(vals) > 1 and disc == 0) else 0)
        metrics[f"combined_l{lam}"] = {
            "within_task_discrimination": f"{disc_groups}/{len(out_groups)}",
            "mean_tau": (round(sum(t for t in taus if t is not None)
                               / len([t for t in taus if t is not None]), 4)
                         if any(t is not None for t in taus) else None),
            "false_reward_groups": fr_groups,
            "saturated_groups": sat_groups,
        }

    out = {"label": "gate_d_ranking_analysis_provisional_vocab23",
           "n_tasks": len(out_groups),
           "n_note": "task-level results primary; n=10 meets the contract's "
                     "minimum but remains a small sample",
           "metrics": metrics, "groups": out_groups}
    (RL / "gate_d_ranking_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, m in metrics.items():
        print(f"{name}: disc={m['within_task_discrimination']} "
              f"tau={m.get('mean_tau')} false_reward={m.get('false_reward_groups')} "
              f"saturated={m.get('saturated_groups')}")


if __name__ == "__main__":
    main()
