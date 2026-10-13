#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2-P1 step 2, audit v2 (owner directive 2026-10-12): repetition
annotation semantics audit.

v1 lesson: rg.repeat and stage.repeat are two views of ONE annotation and are
perfectly consistent corpus-wide (2645/2645). Adjacent-run comparison was a
wrong lens (folding is per-stage via stage.repeat, not adjacent duplicates).
The real defect axis is FOLD CORRECTNESS: does repeat=N on a stage correspond
to a loop the task actually implies?

Checks:
  C1 seq_identity        rg.family == stages[stage_seq-1].family
  C2 repeat_agreement    rg.repeat == stages[stage_seq-1].repeat
  C5 seq_range           stage_seq in [1, len(stages)]
  C3 fold_justification  screen every stage with repeat>1:
                           - invariant_fold_suspect: loop-invariant semantics
                             (VECTOR_LOAD/RASTER_LOAD on static references)
                             assigned repeat>1  [k=370 VECTOR_LOAD x38 class]
                           - condition_count_suspect: ATTRIBUTE_FILTER /
                             THRESHOLD_LOGIC repeat likely counts filter
                             conditions, not executions (owner A-ruling class)
                           - task_loop_supported: iteration hint matches a
                             loop signal found in the task text
                           - unverifiable: no signal either way
  C4 unroll_without_rg   long periodic same-family-cycle unrolls (repeat=1
                         entries) not covered by any repetition group
                         [representation-granularity axis, k=370 year x sensor]

Read-only. Repair is a separate step producing corrected copies.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DEV = os.path.join(REPO, "..", "04_DIAG_WORK", "planner_v2_dev.jsonl")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT = os.path.join(PD, "REP_GROUP_CONSISTENCY_AUDIT_DEV_V2.json")

MIN_UNROLL_CYCLES = 5     # periodic unroll detector: >=5 cycles
INVARIANT_FAMILIES = {"VECTOR_LOAD"}   # structurally loop-invariant loads
CONDITION_COUNT_FAMILIES = {"ATTRIBUTE_FILTER", "THRESHOLD_LOGIC"}

YEAR_RX = re.compile(
    r"\b(19|20)\d{2}\s*[–—-]\s*(19|20)\d{2}\b|annual|yearly|"
    r"per year|each year|every year|multi[- ]?year", re.I)
MONTH_RX = re.compile(r"monthly|per month|each month", re.I)
SEASON_RX = re.compile(r"seasonal|per season|each season|wet (and|/) dry", re.I)
STATIC_REF_RX = re.compile(
    r"fixed region|study area|roi|aoi|region of interest|boundary|"
    r"admin|country|province|county|district", re.I)
BAND_RX = re.compile(r"\bbands?\b|band \d|b\d\b.*b\d\b", re.I)


def task_signals(task):
    t = task or ""
    return {
        "years": bool(YEAR_RX.search(t)),
        "months": bool(MONTH_RX.search(t)),
        "seasons": bool(SEASON_RX.search(t)),
        "static_ref": bool(STATIC_REF_RX.search(t)),
        "bands": bool(BAND_RX.search(t)),
    }


def hint_matches_task(hints, sig):
    """Does the rg iteration hint find support in the task text signals?"""
    for h in hints or []:
        hl = (h or "").lower()
        if "year" in hl and sig["years"]:
            return True
        if ("month" in hl) and sig["months"]:
            return True
        if ("season" in hl) and sig["seasons"]:
            return True
        if ("band" in hl or "spectral" in hl) and sig["bands"]:
            return True
        # generic_each / generic_loop: no task-specific evidence either way
    return False


def detect_period(fams, max_period=8, min_match=0.9):
    n = len(fams)
    for p in range(1, max_period + 1):
        if n < 2 * p:
            break
        checked = matched = 0
        for i in range(n - p):
            checked += 1
            matched += 1 if fams[i] == fams[i + p] else 0
        if checked and matched / checked >= min_match:
            return p
    return None


def main():
    rows = []
    with open(DEV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            t = r.get("target")
            if isinstance(t, str):
                t = json.loads(t)
            rows.append({"task": r.get("task") or "", "tgt": t})

    per_check = Counter()
    c3_by_family = defaultdict(Counter)
    row_flags = []
    rg_total = 0
    rep_stages_total = 0
    expanded_ops_total = 0

    for idx, r in enumerate(rows):
        tgt = r["tgt"]
        if not isinstance(tgt, dict) or "stages" not in tgt:
            continue
        stages = tgt["stages"]
        fams = [s["family"] for s in stages]
        expanded_ops_total += sum(int(s.get("repeat", 1)) for s in stages)
        sig = task_signals(r["task"])
        rgs = tgt.get("repetition_groups") or []
        rg_total += len(rgs)
        rg_by_seq = {g.get("stage_seq"): g for g in rgs}
        flags = []

        for g in rgs:
            seq = g.get("stage_seq")
            if not isinstance(seq, int) or seq < 1 or seq > len(fams):
                per_check["C5_seq_range"] += 1
                flags.append({"check": "C5_seq_range", "rg": g})
                continue
            st = stages[seq - 1]
            if st["family"] != g.get("family"):
                per_check["C1_seq_identity"] += 1
                flags.append({"check": "C1_seq_identity", "rg": g,
                              "stage_family": st["family"]})
            if int(g.get("repeat", 1)) != int(st.get("repeat", 1)):
                per_check["C2_repeat_agreement"] += 1
                flags.append({"check": "C2_repeat_agreement", "rg": g,
                              "stage_repeat": st.get("repeat", 1)})

        for s in stages:
            rep = int(s.get("repeat", 1))
            if rep <= 1:
                continue
            rep_stages_total += 1
            fam = s["family"]
            g = rg_by_seq.get(s["seq"])
            hints = (g or {}).get("iteration_hint") or []
            # C3 fold justification
            if fam in INVARIANT_FAMILIES and sig["static_ref"]:
                cls = "invariant_fold_suspect"
            elif fam in CONDITION_COUNT_FAMILIES:
                cls = "condition_count_suspect"
            elif hint_matches_task(hints, sig):
                cls = "task_loop_supported"
            else:
                cls = "unverifiable"
            per_check[f"C3_{cls}"] += 1
            c3_by_family[fam][cls] += 1
            if cls in ("invariant_fold_suspect", "condition_count_suspect"):
                flags.append({"check": f"C3_{cls}", "seq": s["seq"],
                              "family": fam, "repeat": rep,
                              "hints": hints})

        # C4: periodic unroll among repeat=1 entries not covered by rg
        plain = [s for s in stages if int(s.get("repeat", 1)) == 1]
        if len(plain) >= 2 * MIN_UNROLL_CYCLES:
            pfams = [s["family"] for s in plain]
            p = detect_period(pfams)
            if p:
                per_check["C4_periodic_unroll_no_rg"] += 1
                flags.append({"check": "C4_periodic_unroll_no_rg",
                              "period": p, "unrolled_stages": len(plain),
                              "cycle": pfams[:p]})

        if flags:
            row_flags.append({
                "idx": idx,
                "task_head": (r["task"] or "").splitlines()[0][:100],
                "stages_n": len(stages),
                "flags": flags,
            })

    out = {
        "schema": "rep_group_consistency_audit_dev_v2",
        "corpus": os.path.abspath(DEV),
        "rows_total": len(rows),
        "rg_total": rg_total,
        "stage_entries_total": sum(len(r["tgt"].get("stages", []))
                                   for r in rows
                                   if isinstance(r["tgt"], dict)
                                   and "stages" in r["tgt"]),
        "repeat_stage_entries": rep_stages_total,
        "expanded_ops_total": expanded_ops_total,
        "note": ("C1/C2 = internal annotation consistency (rg vs stage "
                 "fields). C3 = fold semantic justification screen "
                 "(heuristic, pending spot confirmation). C4 = long "
                 "periodic unrolls without repetition-group coverage."),
        "check_totals": dict(per_check),
        "C3_by_family": {f: dict(c) for f, c in c3_by_family.items()},
        "rows_flagged": len(row_flags),
        "row_flags": row_flags,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    brief = {k: out[k] for k in ("rows_total", "rg_total",
                                 "repeat_stage_entries",
                                 "expanded_ops_total")}
    print(json.dumps(brief, indent=2))
    print(json.dumps(out["check_totals"], indent=2))
    print("C3 by family:", json.dumps(out["C3_by_family"], indent=2,
                                      ensure_ascii=False))
    print("rows_flagged:", out["rows_flagged"])
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
