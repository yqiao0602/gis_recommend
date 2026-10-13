#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2-P1 step 3 material: stratified adjudication sample for the 1,411
condition-count suspects + corpus repeat-structure stats (owner diff-report
spec, 2026-10-12).

Mechanism finding (code-traced, blueprint_v2_preflight_v1.py):
  stage.repeat = RLE count of ADJACENT identical semantic-chain tokens.
  repetition_groups = exactly the runs with count>1; iteration_hint = row-level
  keyword match on the task text (same hint for ALL groups in a row).
  No execution semantics, no interleaved-pattern detection, no loop-invariant
  handling anywhere in the corpus generator chain:
    b1_gee_stage_train.jsonl (semantic_chain_raw)
      -> blueprint_v2_preflight_v1.py (RLE + keyword hints)
      -> blueprint_v2_gold_v2.jsonl -> v3 (per_band relabel only)
      -> planner_v2_{train,dev,test}.jsonl (schema: total_iterations dropped)

Each sample row carries the upstream chain context so the adjudicator can
judge: repeated filter CONDITION vs repeated EXECUTION vs per-year filter.
"""

import json
import os
import random
import sys
from collections import Counter, defaultdict
import itertools

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
DEV = os.path.join(DW, "planner_v2_dev.jsonl")
GOLD3 = os.path.join(DW, "blueprint_v2_gold_v3.jsonl")
SRC = os.path.join(DW, "b1_gee_stage_train.jsonl")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT = os.path.join(PD, "COND_COUNT_ADJUDICATION_SAMPLE_V1.json")

TARGET_FAMS = {"ATTRIBUTE_FILTER", "THRESHOLD_LOGIC"}
N_SAMPLES = 40


def length_class(n):
    return "short" if n <= 10 else ("mid" if n <= 25 else "long")


def repeat_band(r):
    return "r2" if r == 2 else ("r3_4" if r <= 4 else "r5plus")


def main():
    rows = []
    with open(DEV, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r.get("target")
                if isinstance(t, str):
                    t = json.loads(t)
                rows.append({"task": r.get("task") or "", "tgt": t})

    # ---- corpus repeat-structure stats (owner diff-report spec) ----
    rep1 = rep_gt1 = 0
    rep_gt1_sum = 0
    stats_rows = 0
    for r in rows:
        t = r["tgt"]
        if not isinstance(t, dict) or "stages" not in t:
            continue
        stats_rows += 1
        for s in t["stages"]:
            c = int(s.get("repeat", 1))
            if c == 1:
                rep1 += 1
            else:
                rep_gt1 += 1
                rep_gt1_sum += c
    stats = {
        "rows": stats_rows,
        "stage_entries_repeat1": rep1,
        "stage_entries_repeat_gt1": rep_gt1,
        "repeat_gt1_sum": rep_gt1_sum,
        "expanded_ops_total": rep1 + rep_gt1_sum,
    }

    # ---- task -> gold_v3 sid index (for chain context) ----
    task2sid = {}
    with open(GOLD3, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task2sid.setdefault(r.get("task"), r.get("source_row_id"))
    sid_chain = {}
    want = set(task2sid.values())

    def chain_of(sid):
        if sid in sid_chain:
            return sid_chain[sid]
        if sid is None:
            return None
        # read-on-demand with line skip (file is large; sample joins only)
        with open(SRC, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if i == sid:
                    r = json.loads(line)
                    ch = [x.strip() for x in
                          (r.get("semantic_chain_raw") or "").split("->")
                          if x.strip()]
                    sid_chain[sid] = ch
                    return ch
        sid_chain[sid] = None
        return None

    # ---- collect suspects with chain context ----
    suspects = []
    joined = 0
    for idx, r in enumerate(rows):
        t = r["tgt"]
        if not isinstance(t, dict) or "stages" not in t:
            continue
        stages = t["stages"]
        lc = length_class(len(stages))
        sids = task2sid.get(r["task"])
        for s in stages:
            fam = s["family"]
            rep = int(s.get("repeat", 1))
            if fam in TARGET_FAMS and rep > 1:
                entry = {
                    "dev_idx": idx,
                    "task_head": (r["task"] or "").splitlines()[0][:110],
                    "stages_n": len(stages),
                    "length_class": lc,
                    "family": fam,
                    "repeat": rep,
                    "repeat_band": repeat_band(rep),
                    "sid": sids,
                }
                ch = chain_of(sids)
                if ch is not None:
                    joined += 1
                    # locate the run in the chain (nth occurrence of this
                    # family among repeat>1 runs is ambiguous; take the
                    # longest run of this family as primary evidence)
                    runs = [(fam_, len(list(g)))
                            for fam_, g in itertools.groupby(ch)]
                    cand = [x for x in runs if x[0] == fam]
                    entry["chain_len"] = len(ch)
                    entry["family_runs_in_chain"] = cand[:6]
                    pos = next((i for i, (f_, c_) in enumerate(runs)
                                if f_ == fam and c_ == rep), None)
                    if pos is None:
                        pos = next((i for i, (f_, _) in enumerate(runs)
                                    if f_ == fam), None)
                    lo, hi = max(0, pos - 2), min(len(runs), pos + 3)
                    entry["chain_run_context"] = [
                        {"family": f_, "count": c_} for f_, c_ in runs[lo:hi]]
                suspects.append(entry)

    # ---- stratified sample: family x length x repeat_band ----
    cells = defaultdict(list)
    for e in suspects:
        cells[(e["family"], e["length_class"], e["repeat_band"])].append(e)
    rng = random.Random(20261012)
    keys = sorted(cells)
    per_cell = max(1, N_SAMPLES // max(1, len(keys)))
    sample = []
    for k in keys:
        pool = cells[k]
        rng.shuffle(pool)
        sample += pool[:per_cell]
    sample = sample[:N_SAMPLES]

    out = {
        "schema": "cond_count_adjudication_sample_v1",
        "mechanism_note": (
            "repeat = RLE count of adjacent identical semantic-chain tokens "
            "(code-traced to blueprint_v2_preflight_v1.py). chain_run_context "
            "shows neighboring runs so the adjudicator can rule: repeated "
            "filter CONDITION / repeated EXECUTION / per-year filter. "
            "No source scripts available locally; source-level verification "
            "stays a separate axis."),
        "suspect_total": len(suspects),
        "suspects_with_chain_join": joined,
        "corpus_repeat_stats": stats,
        "strata_cells": {("||".join(k)): len(v) for k, v in sorted(cells.items())},
        "sample_n": len(sample),
        "samples": sample,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps(stats, indent=2))
    print("suspects:", len(suspects), "| joined:", joined,
          "| sample:", len(sample), "| cells:", len(keys))
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
