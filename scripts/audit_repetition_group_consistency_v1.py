#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2-P1 step 2 (owner directive 2026-10-12): repetition-group consistency audit.

Read-only audit over planner_v2_dev.jsonl blueprints. Checks each
repetition_groups entry against the literal stages sequence:

  C1 seq_identity      rg.family == stages[stage_seq-1].family
  C2 run_consistency   literal adjacent same-family run length at stage_seq
                       vs rg.repeat -> match / under_annotated /
                       over_annotated / phantom (run=1, repeat>1)
  C3 coverage          same-family adjacent runs (len>=2) not covered by any rg
  C4 singular_conflict rg.repeat>1 but family occurs exactly once in blueprint
  C5 seq_range         stage_seq outside [1, len(stages)]

No repair is performed here. Repair (three-case rules) and the before/after
diff report are separate steps.
"""

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DEV = os.path.join(REPO, "..", "04_DIAG_WORK", "planner_v2_dev.jsonl")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT = os.path.join(PD, "REP_GROUP_CONSISTENCY_AUDIT_DEV_V1.json")

LONG_RUN_REPORT = 5  # highlight uncovered runs of this length or more


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            t = r.get("target")
            if isinstance(t, str):
                t = json.loads(t)
            rows.append({"task": r.get("task") or "", "tgt": t})
    return rows


def adjacent_run(fams, i):
    """Length of the same-family adjacent run containing index i."""
    if not fams:
        return 0, i, i
    lo = i
    while lo > 0 and fams[lo - 1] == fams[i]:
        lo -= 1
    hi = i
    while hi + 1 < len(fams) and fams[hi + 1] == fams[i]:
        hi += 1
    return hi - lo + 1, lo, hi


def uncovered_runs(fams, covered_idx):
    """Maximal same-family runs with len>=2 containing no covered index."""
    runs = []
    n = len(fams)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and fams[j + 1] == fams[i]:
            j += 1
        if j > i and not any(c in covered_idx for c in range(i, j + 1)):
            runs.append({"start_seq": i + 1, "len": j - i + 1,
                         "family": fams[i]})
        i = j + 1
    return runs


def main():
    rows = load_rows(DEV)
    per_check = Counter()
    fam_c2 = defaultdict(Counter)
    fam_c4 = Counter()
    row_flags = []
    rg_total = 0
    rows_with_rg = 0

    for idx, r in enumerate(rows):
        tgt = r["tgt"]
        if not isinstance(tgt, dict) or "stages" not in tgt:
            continue
        stages = tgt["stages"]
        fams = [s["family"] for s in stages]
        fam_count = Counter(fams)
        rgs = tgt.get("repetition_groups") or []
        flags = []
        if rgs:
            rows_with_rg += 1
        rg_total += len(rgs)
        covered_idx = set()

        for g in rgs:
            seq = g.get("stage_seq")
            fam = g.get("family")
            rep = int(g.get("repeat", 1))
            if not isinstance(seq, int) or seq < 1 or seq > len(fams):
                per_check["C5_seq_range"] += 1
                flags.append({"check": "C5_seq_range", "rg": g})
                continue
            if fams[seq - 1] != fam:
                per_check["C1_seq_identity"] += 1
                flags.append({"check": "C1_seq_identity", "rg": g,
                              "literal_family": fams[seq - 1]})
            run_len, lo, hi = adjacent_run(fams, seq - 1)
            covered_idx.update(range(lo, hi + 1))
            if rep > 1:
                if run_len == 1:
                    cls = "phantom"
                elif run_len < rep:
                    cls = "over_annotated"
                elif run_len > rep:
                    cls = "under_annotated"
                else:
                    cls = "match"
                if cls != "match":
                    per_check[f"C2_{cls}"] += 1
                    fam_c2[fam][cls] += 1
                    flags.append({"check": f"C2_{cls}", "rg": g,
                                  "literal_run_len": run_len,
                                  "run_start_seq": lo + 1})
            if rep > 1 and fam_count[fam] == 1:
                per_check["C4_singular_conflict"] += 1
                fam_c4[fam] += 1
                flags.append({"check": "C4_singular_conflict", "rg": g,
                              "family_literal_count": 1})

        for run in uncovered_runs(fams, covered_idx):
            if run["len"] >= 2:
                per_check["C3_uncovered_run"] += 1
            if run["len"] >= LONG_RUN_REPORT:
                flags.append({"check": "C3_long_uncovered_run", **run})

        if flags:
            row_flags.append({
                "idx": idx,
                "task_head": (r["task"] or "").splitlines()[0][:100],
                "stages_n": len(stages), "rg_n": len(rgs),
                "flags": flags,
            })

    affected = len(row_flags)
    out = {
        "schema": "rep_group_consistency_audit_dev_v1",
        "corpus": os.path.abspath(DEV),
        "rows_total": len(rows),
        "rows_with_rg": rows_with_rg,
        "rg_total": rg_total,
        "check_totals": dict(per_check),
        "C2_by_family": {f: dict(c) for f, c in fam_c2.items()},
        "C4_by_family": dict(fam_c4),
        "rows_flagged": affected,
        "affected_pct": round(affected / max(1, len(rows)) * 100, 1),
        "row_flags": row_flags,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    print(json.dumps({k: out[k] for k in
                      ("rows_total", "rows_with_rg", "rg_total",
                       "check_totals", "rows_flagged", "affected_pct")},
                     indent=2))
    print("C2 by family:", json.dumps(out["C2_by_family"], indent=2,
                                      ensure_ascii=False))
    print("C4 by family:", json.dumps(out["C4_by_family"], ensure_ascii=False))
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
