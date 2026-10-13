#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C6: canonical-token agreement check for every repeat>1 stage (dev).

For each stage with repeat>1, look at the gee_canonical_chain tokens under
that run span (positional alignment semantic_chain_raw <-> gee_canonical_chain):

  all_identical        every canonical token in the run is the same call
                       -> faithful repetition candidate (true loop/invariant)
  all_distinct         every token differs -> family-level RLE collapsed
                       DISTINCT calls into one "repeat" (not a loop count)
  mixed                both present
  alignment_mismatch   chain lengths differ; positional mapping unreliable

Read-only. One pass over the b1 stage file for all needed sids.
"""

import json
import os
import sys
import itertools
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
DEV = os.path.join(DW, "planner_v2_dev.jsonl")
GOLD3 = os.path.join(DW, "blueprint_v2_gold_v3.jsonl")
SRC = os.path.join(DW, "b1_gee_stage_train.jsonl")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT = os.path.join(PD, "CANONICAL_AGREEMENT_C6_DEV_V1.json")


def main():
    dev = []
    with open(DEV, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r.get("target")
                if isinstance(t, str):
                    t = json.loads(t)
                dev.append({"task": r.get("task") or "", "tgt": t})

    # task -> sid
    task2sid = {}
    with open(GOLD3, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task2sid.setdefault(r.get("task"), r.get("source_row_id"))

    # collect sids needed (rows with >=1 repeat>1 stage)
    need = set()
    for r in dev:
        t = r["tgt"]
        if isinstance(t, dict) and any(int(s.get("repeat", 1)) > 1
                                       for s in t.get("stages", [])):
            sid = task2sid.get(r["task"])
            if sid:
                need.add(sid)

    # ONE pass over the b1 file
    chains = {}
    with open(SRC, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i in need:
                r = json.loads(line)
                sem = [x.strip() for x in
                       (r.get("semantic_chain_raw") or "").split("->")
                       if x.strip()]
                can = [x.strip() for x in
                       (r.get("gee_canonical_chain") or "").split("->")
                       if x.strip()]
                chains[i] = (sem, can)
            if len(chains) == len(need):
                break

    per_class = Counter()
    per_fam_class = defaultdict(Counter)
    row_detail = []
    n_stages_checked = 0
    joined_rows = 0

    for idx, r in enumerate(dev):
        t = r["tgt"]
        if not isinstance(t, dict) or "stages" not in t:
            continue
        stages = t.get("stages", [])
        if not any(int(s.get("repeat", 1)) > 1 for s in stages):
            continue
        sid = task2sid.get(r["task"])
        sem, can = chains.get(sid, (None, None))
        flags = []
        if sem is None:
            per_class["no_chain_join"] += 1
            flags.append({"check": "no_chain_join"})
        else:
            joined_rows += 1
            aligned = len(sem) == len(can)
            pos = 0
            runs = [(fam, len(list(g))) for fam, g in itertools.groupby(sem)]
            # rebuild run offsets
            offs = []
            p = 0
            for fam, c in runs:
                offs.append((fam, c, p))
                p += c
            for s in stages:
                rep = int(s.get("repeat", 1))
                if rep <= 1:
                    continue
                n_stages_checked += 1
                fam = s["family"]
                # find the matching run: prefer run with same family & count
                m = next((o for o in offs if o[0] == fam and o[1] == rep),
                         next((o for o in offs if o[0] == fam), None))
                if m is None:
                    cls = "run_not_found"
                elif not aligned:
                    cls = "alignment_mismatch"
                else:
                    seg = can[m[2]:m[2] + m[1]]
                    u = set(seg)
                    if len(u) == 1:
                        cls = "all_identical"
                    elif len(u) == len(seg):
                        cls = "all_distinct"
                    else:
                        cls = "mixed"
                per_class[cls] += 1
                per_fam_class[fam][cls] += 1
                if cls in ("all_distinct", "mixed", "alignment_mismatch",
                           "run_not_found"):
                    seg_show = None
                    if m is not None and aligned:
                        seg_show = can[m[2]:m[2] + m[1]][:6]
                    flags.append({"check": f"C6_{cls}", "seq": s["seq"],
                                  "family": fam, "repeat": rep,
                                  "canonical_span": seg_show})
        if flags:
            row_detail.append({
                "dev_idx": idx,
                "task_head": (r["task"] or "").splitlines()[0][:100],
                "sid": sid,
                "flags": flags,
            })

    out = {
        "schema": "canonical_agreement_c6_dev_v1",
        "note": ("C6 compares the canonical API tokens under each repeat>1 "
                 "run. all_distinct = family-level RLE collapsed DISTINCT "
                 "calls (repeat is not a loop count). all_identical = "
                 "faithful repetition candidate. Positional alignment assumes "
                 "1:1 semantic<->canonical; length mismatches are flagged."),
        "rows_total_dev": len(dev),
        "rows_with_repeat_gt1": sum(
            1 for r in dev if isinstance(r["tgt"], dict) and
            any(int(s.get("repeat", 1)) > 1 for s in r["tgt"].get("stages", []))),
        "rows_joined": joined_rows,
        "stages_checked": n_stages_checked,
        "class_totals": dict(per_class),
        "class_by_family": {f: dict(c) for f, c in per_fam_class.items()},
        "rows_with_flags": len(row_detail),
        "row_detail": row_detail,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps({k: out[k] for k in
                      ("rows_total_dev", "rows_with_repeat_gt1", "rows_joined",
                       "stages_checked", "class_totals")}, indent=2))
    print("class by family (top):")
    for f, c in sorted(per_fam_class.items(),
                       key=lambda kv: -sum(kv[1].values()))[:8]:
        print(" ", f, dict(c))
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
