#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate B: freeze owner's blind labels for the 10 independent tasks (80
candidates), then unblind against the frozen r5 v0.5.1 outputs and compute
rule-human agreement / false-positive / false-negative rates.

Label legend (owner round-12 Gate B):
  O = omission (confirmed missing required capability)
  C = covered (visible semantic evidence at stage-family granularity)
  U = requirement_uncertain
  B = wrapper-opacity ("B*"): ITERATIVE_APPLY may wrap the capability but the
      summary cannot verify - SEPARATE audit note, NOT merged into O/C stats
      (owner directive)
  N = non_required
Blank cells in the owner tables = slot covered by visible stage (treated as C
when the owner listed the slot as required with stages noted, otherwise the
cell is only recorded for slots the owner explicitly judged).
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"

O, C, U, B, N = "O", "C", "U", "B", "N"

LABELS = {
    "2235": {"MASK": {0: O, 1: O, 2: B, 3: B, 4: O, 5: O, 6: O, 7: O}},
    "3084": {
        "TEMPORAL": {0: O, 1: C, 2: C, 3: C, 4: O, 5: C, 6: O, 7: C},
        "MASK": {0: O, 1: O, 2: B, 3: O, 4: O, 5: O, 6: O, 7: B},
        "INDEX": {c: O for c in range(8)},
        "SPATIAL": {0: O, 1: C, 2: C, 3: C, 4: O, 5: C, 6: O, 7: C},
    },
    "10540": {
        "TEMPORAL": {0: C, 1: C, 2: C, 3: O, 4: C, 5: C, 6: C, 7: O},
        "SPATIAL": {c: O for c in range(8)},
        "STATS": {0: C, 1: C, 2: C, 3: C, 4: O, 5: C, 6: C, 7: C},
    },
    "10893": {
        "TEMPORAL": {c: C for c in range(8)},
        "COMPOSITE": {0: C, 1: O, 2: C, 3: B, 4: C, 5: C, 6: C, 7: O},
    },
    "24025": {
        "TEMPORAL": {0: O, 1: C, 2: O, 3: O, 4: O, 5: C, 6: C, 7: C},
        "MASK": {c: O for c in range(8)},
    },
    "24515": {
        "TEMPORAL": {0: O, 1: C, 2: C, 3: C, 4: C, 5: C, 6: C, 7: C},
        "INDEX": {0: O, 1: O, 2: O, 3: C, 4: O, 5: C, 6: C, 7: C},
        "STATS": {0: C, 1: C, 2: C, 3: O, 4: C, 5: C, 6: C, 7: C},
        "CLASSIFY": {0: O, 1: C, 2: O, 3: C, 4: O, 5: C, 6: O, 7: O},
    },
    "25159": {
        "TEMPORAL": {0: C, 1: C, 2: C, 3: C, 4: C, 5: C, 6: O, 7: C},
        "MASK": {0: B, 1: B, 2: O, 3: B, 4: B, 5: O, 6: O, 7: B},
        "COMPOSITE": {0: C, 1: C, 2: O, 3: B, 4: C, 5: C, 6: C, 7: C},
    },
    "29444": {
        "TEMPORAL": {3: C, 4: O},
        "MASK": {c: O for c in range(8)},
        "INDEX": {c: O for c in range(8)},
        "COMPOSITE": {0: O, 1: O, 2: C, 3: O, 4: C, 5: O, 6: O, 7: O},
    },
    "31187": {
        "TEMPORAL": {0: O, 1: O, 2: O, 3: C, 4: C, 5: C, 6: C, 7: C},
        "INDEX": {c: O for c in range(8)},
        "SPATIAL": {0: O, 1: C, 2: O, 3: C, 4: O, 5: O, 6: C, 7: C},
        "COMPOSITE": {0: O, 1: O, 2: O, 3: B, 4: O, 5: O, 6: O, 7: O},
    },
    "31609": {
        "TEMPORAL": {0: C, 1: C, 2: O, 3: C, 4: O, 5: C, 6: C, 7: O},
        "MASK": {0: O, 1: O, 2: O, 3: O, 4: O, 5: B, 6: B, 7: O},
        "INDEX": {0: O, 1: O, 2: O, 3: O, 4: C, 5: O, 6: O, 7: O},
    },
}
INVALID_STAGES = {
    ("3084", 6): ["None x1"],
    ("24515", 6): ["None x2"],
    ("31187", 2): ["None x2"],
    ("10540", 7): ["TEMORAL_FILTER (misspelled family)"],
}


def main():
    outs = json.loads((RL / "independent_set_r5_outputs_v051.json").read_text(encoding="utf-8"))
    per_cand = {(c["k"], c["cand"]): c for c in outs["candidates"]}

    # ---- freeze owner labels ----
    labels_out = {
        "gate": "B", "labeler": "owner (blind)", "legend": {"O": "omission",
        "C": "covered", "U": "requirement_uncertain", "B": "wrapper-opacity "
        "(separate audit note, not merged into O/C stats)", "N": "non_required"},
        "caliber": "stage-family-level adjudication, NOT DAG-level correctness",
        "invalid_stages": {f"{k}/cand{c}": v for (k, c), v in INVALID_STAGES.items()},
        "groups": LABELS,
    }
    (RL / "gate_b_labels_frozen_v1.json").write_text(
        json.dumps(labels_out, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- unblind: contingency vs r5 ----
    # r5 side: for each (k, cand, slot) where slot is r5-required:
    #   r5_missing (verdict incomplete & slot in missing) or
    #   r5_covered (covered / covered_coarse)
    rows = []
    for k_str, slots in LABELS.items():
        for cand_str, cand_out in [(c["cand"], c) for c in outs["candidates"]
                                   if str(c["k"]) == k_str]:
            for slot_id, owner in cand_str.items() if isinstance(cand_str, dict) else []:
                pass
    # simpler: iterate labels
    for k_str, slot_map in LABELS.items():
        for slot_id, cand_labels in slot_map.items():
            for cand, owner in cand_labels.items():
                co = per_cand.get((int(k_str), cand))
                r5_missing = slot_id in (co["r5_v051"].get("missing", [])
                                         if co else [])
                r5_covered = slot_id in (co["r5_v051"].get("coarse", [])
                                         if co else [])
                # r5 "covered" also includes slots required but matched by the
                # primary family: derive from verdict+missing
                if co and r5_missing is False and r5_covered is False:
                    v = co["r5_v051"].get("verdict")
                    if v == "abstain":
                        r5_state = "abstain"
                    else:
                        r5_state = "covered_primary"
                else:
                    r5_state = ("missing" if r5_missing else
                                ("covered_alt" if r5_covered else "unknown"))
                rows.append({"k": int(k_str), "cand": cand, "slot": slot_id,
                             "owner": owner, "r5_state": r5_state})

    # ---- contingency ----
    def bucket(row):
        o, r = row["owner"], row["r5_state"]
        if r in ("missing",):
            return {O: "TP", C: "FP_false_punish", B: "UNRESOLVED_wrapper",
                    U: "requirement_disagreement", N: "false_requirement"}[o]
        if r.startswith("covered"):
            return {O: "FN_false_pass", C: "TN", B: "covered_vs_wrapper",
                    U: "covered_vs_uncertain", N: "covered_vs_not_required"}[o]
        if r == "abstain":
            return f"abstain_vs_{o}"
        return f"unknown_{r}_vs_{o}"

    for row in rows:
        row["bucket"] = bucket(row)

    cnt = Counter(r["bucket"] for r in rows)
    miss_total = sum(v for k2, v in cnt.items() if k2.startswith(("TP", "FP", "UNRESOLVED", "requirement", "false_req")))
    cov_total = sum(v for k2, v in cnt.items() if k2.startswith(("TN", "FN", "covered_")))
    fp = cnt.get("FP_false_punish", 0)
    fn = cnt.get("FN_false_pass", 0)
    tp = cnt.get("TP", 0)
    tn = cnt.get("TN", 0)
    summary = {
        "total_slot_instances": len(rows),
        "r5_missing_total": miss_total,
        "r5_covered_total": cov_total,
        "TP": tp, "FP_false_punish": fp,
        "FN_false_pass": fn, "TN": tn,
        "UNRESOLVED_wrapper": cnt.get("UNRESOLVED_wrapper", 0),
        "requirement_disagreement": cnt.get("requirement_disagreement", 0),
        "false_requirement": cnt.get("false_requirement", 0),
        "covered_vs_wrapper": cnt.get("covered_vs_wrapper", 0),
        "abstain_rows": sum(v for k2, v in cnt.items() if k2.startswith("abstain")),
        "fp_rate_among_r5_missing": round(fp / miss_total, 4) if miss_total else None,
        "fn_rate_among_r5_covered": round(fn / cov_total, 4) if cov_total else None,
    }

    # ---- task-level within-group discrimination ----
    by_group = defaultdict(list)
    for r in rows:
        by_group[r["k"]].append(r)
    task_disc = {}
    for k, rs in sorted(by_group.items()):
        owner_omission = sum(1 for r in rs if r["owner"] == O)
        r5_missing = sum(1 for r in rs if r["r5_state"] == "missing")
        owners = {r["owner"] for r in rs if r["owner"] != B}
        task_disc[k] = {"owner_labels_present": sorted(owners),
                        "owner_omission_slots": owner_omission,
                        "r5_missing_slots": r5_missing,
                        "owner_sees_any_O": owner_omission > 0,
                        "r5_sees_any_missing": r5_missing > 0}
    out = {"summary": summary, "task_discrimination": task_disc, "rows": rows}
    (RL / "gate_b_unblind_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
