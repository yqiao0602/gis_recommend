#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S2 full offline audit v1 (owner round-7 deliverable 2).

Scores the frozen 192 S2 candidates (24 groups x 8) with r5 rules v0.3.
No new generation, no parameter updates.

Owner requirements implemented:
  - scorable classification per task: scorable / partially_scorable /
    abstained - coverage numerators are NEVER pooled across classes;
  - per-group r5 verdict distribution vs the S2 formal-reward baseline
    (6/24 non-constant groups), with the explicit caveat that more
    non-constant groups != better quality signal;
  - three bias audits: length (coverage vs plan length), template
    (identical family multisets must produce identical verdicts), family
    (per-family requirement/coverage rates, broad families flagged).
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"


def main():
    preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
    scored = json.loads((RL / "s2_dryrun/S2_DRYRUN_SCORED_V1.json").read_text(encoding="utf-8"))
    formal_by_key = {(r["k"], r["cand"]): r["formal_reward"] for r in scored["rows"]}
    tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
    tasks.update(json.loads((RL / "r5_audit_tasks_rest.json").read_text(encoding="utf-8")))

    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    groups_out = {}
    class_counter = Counter()
    cov_by_class = {"scorable": [], "partially_scorable": []}
    template_violations = []
    fam_required = Counter()
    fam_covered = Counter()
    length_pairs = []  # (n_stages, missing_count, coverage_ratio)

    for k, grp in sorted(by_group.items()):
        task = tasks.get(str(k))
        if task is None:
            continue
        pr = evaluate_pair(task, {"stages": []})["parse"]
        if pr["abstain"]:
            cls = "abstained"
        elif pr["vocab_gap_signals"]:
            cls = "partially_scorable"
        else:
            cls = "scorable"
        class_counter[cls] += 1
        gaps = [g["signal"] for g in pr["vocab_gap_signals"]]
        required_slots = [s["id"] for s in pr["slots"]]
        for s in pr["slots"]:
            for f in s["families"]:
                if s.get("primary_family") == f or len(s["families"]) == 1:
                    fam_required[f] += 1

        cand_out, verdicts, formal = [], [], []
        for p in grp:
            try:
                b = json.loads(p["pred_text"])
            except Exception:
                b = None
            if b is None or not isinstance(b.get("stages"), list):
                cand_out.append({"cand": p["cand"], "verdict": "unparseable",
                                 "formal_reward": formal_by_key.get((p["k"], p["cand"]))})
                verdicts.append("unparseable")
                formal.append(formal_by_key.get((p["k"], p["cand"])))
                continue
            res = evaluate_pair(task, b)["score"]
            n_stages = len(b["stages"])
            miss = sum(1 for s in res["per_slot"] if s["coverage"] == "missing")
            length_pairs.append((n_stages, miss, res["coverage_ratio"]))
            for s in res["per_slot"]:
                if s["coverage"] in ("covered", "covered_coarse"):
                    matched = s.get("matched_family")
                    if matched:
                        fam_covered[matched] += 1
            verdicts.append(res["coverage_verdict"])
            formal.append(formal_by_key.get((p["k"], p["cand"])))
            cand_out.append({"cand": p["cand"], "verdict": res["coverage_verdict"],
                             "missing": [s["slot"] for s in res["per_slot"]
                                         if s["coverage"] == "missing"],
                             "coarse": [s["slot"] for s in res["per_slot"]
                                        if s["coverage"] == "covered_coarse"],
                             "n_stages": n_stages,
                             "formal_reward": formal_by_key.get((p["k"], p["cand"]))})
        r5_splits = len(set(verdicts)) > 1
        formal_splits = len(set(v for v in formal if v is not None)) > 1
        # template check: identical family multisets within the group
        ms = defaultdict(list)
        for idx, p in enumerate(grp):
            try:
                b = json.loads(p["pred_text"])
            except Exception:
                continue
            if isinstance(b, dict) and isinstance(b.get("stages"), list):
                key = tuple(sorted(s.get("family", "?") for s in b["stages"]))
                ms[key].append((p["cand"], verdicts[idx]))
        for key, entries in ms.items():
            vs = {v for _, v in entries}
            if len(vs) > 1:
                template_violations.append({"k": k, "multiset": list(key),
                                            "verdicts": vs})
        groups_out[str(k)] = {
            "class": cls, "gap_signals": gaps,
            "required_slots": required_slots,
            "verdicts": verdicts, "r5_splits": r5_splits,
            "formal_splits": formal_splits,
            "formal_values": formal,
            "candidates": cand_out,
        }

    # ---- aggregations ----
    scorable_groups = {k: g for k, g in groups_out.items() if g["class"] == "scorable"}
    partial_groups = {k: g for k, g in groups_out.items() if g["class"] == "partially_scorable"}
    abstain_groups = {k: g for k, g in groups_out.items() if g["class"] == "abstained"}

    def split_stats(groups):
        r5 = sum(1 for g in groups.values() if g["r5_splits"])
        both = sum(1 for g in groups.values() if g["r5_splits"] and g["formal_splits"])
        return {"groups": len(groups), "r5_splits": r5,
                "formal_splits": both,
                "r5_split_rate": round(r5 / len(groups), 4) if groups else None}

    # length bias: correlation proxy - mean missing count per length bucket
    buckets = defaultdict(list)
    for n_stages, miss, ratio in length_pairs:
        b = "1-4" if n_stages <= 4 else ("5-8" if n_stages <= 8 else "9+")
        buckets[b].append((miss, ratio))
    length_bias = {b: {"n": len(v),
                       "mean_missing": round(sum(x[0] for x in v) / len(v), 3),
                       "mean_coverage_ratio": round(
                           sum(x[1] for x in v if x[1] is not None)
                           / max(1, sum(1 for x in v if x[1] is not None)), 4)}
                   for b, v in sorted(buckets.items())}

    fam_bias = {f: {"required_slots": n,
                    "covered_when_required": fam_covered.get(f, 0)}
                for f, n in fam_required.most_common()}

    out = {
        "label": "r5_v0.3_offline_audit_provisional_vocab23_no_training",
        "rules_version": "v0.3 (frozen)",
        "scorable_classification": dict(class_counter),
        "coverage_numerators_by_class": {
            "scorable": split_stats(scorable_groups),
            "partially_scorable": split_stats(partial_groups),
            "abstained": {"groups": len(abstain_groups),
                          "note": "excluded from all coverage numerators"},
        },
        "baseline_comparison": {
            "s2_formal_reward_nonconstant_groups": 6,
            "r5_split_groups_total": sum(1 for g in groups_out.values() if g["r5_splits"]),
            "caveat": "more non-constant groups != better quality signal; "
                      "interpretation requires the owner's case review",
        },
        "bias_audits": {
            "length": {"buckets": length_bias,
                       "note": "mean_missing should not simply grow with length "
                               "unless longer plans genuinely omit more"},
            "template": {"violations": template_violations,
                         "note": "identical family multisets must give identical "
                                 "verdicts (r5 is a set-semantic scorer)"},
            "family": {"required_and_covered": fam_bias,
                       "note": "broad families (AGGREGATION/ATTRIBUTE_FILTER) "
                               "scrutiny required"},
        },
        "groups": groups_out,
    }
    (RL / "s2_dryrun/R5_S2_OFFLINE_AUDIT_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("scorable classification:", dict(class_counter))
    print("coverage numerators:", json.dumps(out["coverage_numerators_by_class"], indent=2))
    print("baseline:", json.dumps(out["baseline_comparison"], indent=2))
    print("length bias:", json.dumps(length_bias, indent=2))
    print("template violations:", len(template_violations))
    print("family bias:", json.dumps(fam_bias, indent=2))


if __name__ == "__main__":
    main()
