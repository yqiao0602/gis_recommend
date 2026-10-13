#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S2 dry-run scoring + diagnostics for the RL line (provisional_vocab23).

Owner round-4 requirements implemented here:
  1. provisional main scoring   : formal reward = training_reward (gateway on),
                                  every result labeled provisional_vocab23.
  2. vocab sensitivity analysis : a DIAGNOSTIC view with r2 masked (excluded
                                  from the C0 denominator and from the formal
                                  mean) compared against the vocab23 view.
                                  Diagnostic only - does NOT alter the reward
                                  module contract.
  3. full OOV logging           : per unknown token - occurrence count, task
                                  groups, candidate count, example context, and
                                  per-row reward delta (r2-masked view minus
                                  vocab23 view). Known OOV (CLASSIFICATION_LOAD)
                                  reported separately from new unknowns.

Group-level signal diagnosis: per task group of 8 candidates - formal-reward
variance/non-constant rate, per-component variation contribution, mask rates,
empty/parse-fail rates. No parameter updates anywhere.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from rl_reward_v1 import evaluate_prediction, load_vocab  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"


def c0_without_r2(res):
    """Diagnostic C0 recomputed with r2 excluded (masked) from the denominator."""
    vals = [c["value"] for k, c in res.components.items()
            if k != "r2" and c["value"] is not None]
    return (sum(vals) / len(vals)) if vals else None


def formal_without_r2(res):
    """Diagnostic formal view with r2 excluded (gateway conditions unchanged:
    gateway depends only on r1 failures and empty stages, never on r2)."""
    c0 = c0_without_r2(res)
    if c0 is None:
        return None
    r1_failed = any(res.components[k]["value"] == 0 for k in ("r1a", "r1b", "r1c"))
    gateway = res.log.get("gateway_triggered")
    if r1_failed or gateway == "empty_stages_gateway":
        return 0.0
    return c0


def main(preds_path, out_path):
    vocab = load_vocab(RL / "vocab23_server_verified.json")
    preds = json.loads(Path(preds_path).read_text(encoding="utf-8"))

    scored = []
    for row in preds:
        res = evaluate_prediction(row["pred_text"], vocab, gateway_mode=True)
        r2_masked_formal = formal_without_r2(res)
        scored.append({
            "k": row["k"], "cand": row["cand"], "band": row["band"],
            "n_stages_gold": row["n_stages_gold"], "task_head": row["task_head"],
            "components": {k: c["value"] for k, c in res.components.items()},
            "reasons": {k: c["reason"] for k, c in res.components.items()
                        if c["reason"]},
            "c0_diagnostic": res.composite,
            "formal_reward": res.training_reward,
            "formal_reward_r2_masked_diag": r2_masked_formal,
            "reward_delta_r2": (None if r2_masked_formal is None else
                                round(r2_masked_formal - (res.training_reward or 0.0), 4)),
            "gateway_triggered": res.log.get("gateway_triggered"),
            "masked": res.masked,
            "unknown_tokens": res.log.get("unknown_tokens", []),
            "field_presence": res.log.get("field_presence"),
            "n_stages": res.log.get("n_stages"),
            "repeat_values": res.log.get("repeat_values"),
        })

    # ---- group-level signal diagnosis ----
    groups = defaultdict(list)
    for s in scored:
        groups[s["k"]].append(s)
    gdiag = {}
    for k, rows in sorted(groups.items()):
        formal = [r["formal_reward"] for r in rows]
        diag = [r["formal_reward_r2_masked_diag"] for r in rows
                if r["formal_reward_r2_masked_diag"] is not None]
        comp_var = {c: len({r["components"].get(c) for r in rows}) for c in
                    ("r1a", "r1b", "r1c", "r2", "r3", "r4")}
        gdiag[k] = {
            "band": rows[0]["band"], "n_candidates": len(rows),
            "formal_nonconstant": len(set(formal)) > 1,
            "formal_mean": round(sum(formal) / len(formal), 4),
            "formal_values": formal,
            "diag_r2masked_nonconstant": len(set(diag)) > 1 if diag else None,
            "diag_r2masked_mean": (round(sum(diag) / len(diag), 4)
                                   if diag else None),
            "component_value_counts": comp_var,
            "varying_components": [c for c, n in comp_var.items() if n > 1],
            "mask_counts": {c: sum(1 for r in rows if c in r["masked"])
                            for c in ("r1a", "r1b", "r1c", "r2", "r3", "r4")},
            "empty_stages_count": sum(1 for r in rows
                                      if r["gateway_triggered"] ==
                                      "empty_stages_gateway"),
            "parse_fail_count": sum(1 for r in rows
                                    if r["components"]["r1a"] == 0),
        }

    nonconst = sum(1 for g in gdiag.values() if g["formal_nonconstant"])
    nonconst_diag = sum(1 for g in gdiag.values()
                        if g["diag_r2masked_nonconstant"])

    # ---- full OOV record ----
    oov = defaultdict(lambda: {"count": 0, "tasks": set(), "cands": 0,
                               "examples": [], "reward_deltas": [],
                               "candidate_rows_affected": 0})
    for s in scored:
        for tok in s["unknown_tokens"]:
            o = oov[tok]
            o["count"] += 1
            o["tasks"].add(s["k"])
            o["cands"] += 1
            o["candidate_rows_affected"] += 1
            if len(o["examples"]) < 3:
                o["examples"].append({"k": s["k"], "cand": s["cand"],
                                      "task_head": s["task_head"],
                                      "n_stages": s["n_stages"]})
            if s["reward_delta_r2"] is not None:
                o["reward_deltas"].append(s["reward_delta_r2"])
    for tok, o in oov.items():
        o["tasks"] = sorted(o["tasks"])
        o["distinct_task_groups"] = len(o["tasks"])
        rd = o.pop("reward_deltas")
        o["reward_delta_r2_mean"] = (round(sum(rd) / len(rd), 4) if rd else None)
        o["known_from_s1"] = tok == "CLASSIFICATION_LOAD"

    # ---- aggregate summary ----
    n = len(scored)
    summary = {
        "label": "provisional_vocab23_diagnostic_dryrun_no_training",
        "n_rows": n,
        "n_task_groups": len(groups),
        "formal_reward_mean": round(sum(r["formal_reward"] or 0 for r in scored) / n, 4),
        "formal_nonconstant_groups": nonconst,
        "formal_nonconstant_rate": round(nonconst / len(groups), 4),
        "diag_r2masked_nonconstant_groups": nonconst_diag,
        "parse_fail_rows": sum(1 for r in scored if r["components"]["r1a"] == 0),
        "empty_stages_rows": sum(1 for r in scored
                                 if r["gateway_triggered"] == "empty_stages_gateway"),
        "component_fail_rows": {c: sum(1 for r in scored
                                       if r["components"][c] == 0)
                                for c in ("r1a", "r1b", "r1c", "r2", "r3", "r4")},
        "component_mask_rows": {c: sum(1 for r in scored if c in r["masked"])
                                for c in ("r1a", "r1b", "r1c", "r2", "r3", "r4")},
        "r1b_field_presence": {
            "repetition_groups_absent": sum(
                1 for r in scored
                if r["field_presence"] and not r["field_presence"].get("repetition_groups")),
            "total_iterations_present": sum(
                1 for r in scored
                if r["field_presence"] and r["field_presence"].get("total_iterations")),
        },
        "oov_tokens": {tok: o for tok, o in sorted(oov.items(),
                                                   key=lambda kv: -kv[1]["count"])},
    }
    out = {"summary": summary, "groups": gdiag, "rows": scored}
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:2000])
    print(f"\nwritten: {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
