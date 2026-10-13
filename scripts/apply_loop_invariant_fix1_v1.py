#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2-P1 fix 1 (owner directive 2026-10-12): loop_invariant marking.

Scope: ONLY the two canonically-confirmed loop invariants in
planner_v2_dev.jsonl — dev_idx 370 (38x ee.Feature) and dev_idx 1014
(2x ee.Feature). The other three invariant-fold suspects (468/958/1181)
showed distinct canonical calls and are NOT marked here (owner precondition:
suspicion alone does not justify the marker).

Representation (owner convention):
  stage gains "iteration_hint": ["loop_invariant"], repeat -> 1.
  The corresponding repetition_groups entry is REMOVED (rg contract =
  groups with repeat>1; keeping it would break the rg<->stage.repeat
  sync invariant that holds corpus-wide).

Output: corrected COPY (original corpus never modified) + regression diff
proving only the two designated rows changed, only in designated fields.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
SRC = os.path.join(DW, "planner_v2_dev.jsonl")
OUT = os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl")

FIX_ROWS = {
    370: {"family": "VECTOR_LOAD", "seq": 723},
    1014: {"family": "VECTOR_LOAD", "seq": 5},
}


def fix_target(tgt, spec):
    """Apply one fix. Returns (new_tgt, change_summary). Raises if the
    expected stage/group is not found exactly as expected."""
    stages = tgt["stages"]
    hits = [s for s in stages
            if s["seq"] == spec["seq"] and s["family"] == spec["family"]]
    assert len(hits) == 1, f"stage not uniquely found: {spec}"
    st = hits[0]
    old_rep = int(st.get("repeat", 1))
    assert old_rep > 1, f"expected repeat>1, got {old_rep}"
    st["repeat"] = 1
    st["iteration_hint"] = ["loop_invariant"]

    rgs = tgt.get("repetition_groups") or []
    before = len(rgs)
    rgs2 = [g for g in rgs
            if not (g.get("stage_seq") == spec["seq"]
                    and g.get("family") == spec["family"])]
    assert len(rgs2) == before - 1, "expected exactly one rg entry removed"
    tgt["repetition_groups"] = rgs2
    return tgt, {"stage_seq": spec["seq"], "family": spec["family"],
                 "repeat": f"{old_rep}->1", "rg_removed": 1}


def main():
    lines = open(SRC, encoding="utf-8").read().splitlines()
    # byte-format check: canonical round-trip must reproduce the line
    probe = json.loads(lines[1])
    assert json.dumps(probe, ensure_ascii=False) == lines[1], \
        "corpus line format is not canonical json.dumps(ensure_ascii=False)"

    out_lines = []
    changes = {}
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if i in FIX_ROWS:
            row = json.loads(line)
            t = row["target"]
            if isinstance(t, str):
                t = json.loads(t)
            t2, summary = fix_target(t, FIX_ROWS[i])
            row["target"] = json.dumps(t2, ensure_ascii=False)
            out_lines.append(json.dumps(row, ensure_ascii=False))
            changes[i] = summary
        else:
            out_lines.append(line)
    assert len(changes) == len(FIX_ROWS), changes
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(out_lines) + "\n")

    # ---- checks ----
    orig = [l for l in lines if l.strip()]
    new = [l for l in open(OUT, encoding="utf-8").read().splitlines() if l.strip()]
    assert len(orig) == len(new), "row count changed"

    # check 5 (regression): every non-fix row byte-identical
    diff_rows = [i for i, (a, b) in enumerate(zip(orig, new)) if a != b]
    assert sorted(diff_rows) == sorted(FIX_ROWS), \
        f"unexpected changed rows: {diff_rows}"

    # check 4 (round-trip) + structural assertion of the two fixed rows
    for i, spec in FIX_ROWS.items():
        row = json.loads(new[i])
        t = json.loads(row["target"])
        st = next(s for s in t["stages"] if s["seq"] == spec["seq"])
        assert st["repeat"] == 1 and st.get("iteration_hint") == ["loop_invariant"]
        assert all(not (g.get("stage_seq") == spec["seq"] and
                        g.get("family") == spec["family"])
                   for g in t.get("repetition_groups", []))

    # rg<->stage sync invariant still holds on the corrected copy
    viol = 0
    for line in new:
        row = json.loads(line)
        t = json.loads(row["target"])
        by_seq = {s["seq"]: s for s in t["stages"]}
        for g in t.get("repetition_groups", []):
            s = by_seq.get(g.get("stage_seq"))
            if (s is None or s["family"] != g.get("family")
                    or int(g.get("repeat", 1)) != int(s.get("repeat", 1))):
                viol += 1
    assert viol == 0, f"sync violations after fix: {viol}"

    print(json.dumps({
        "out": OUT,
        "rows_total": len(new),
        "changed_rows": {str(k): v for k, v in changes.items()},
        "checks": {"byte_format_canonical": True,
                   "nonfix_rows_identical": True,
                   "roundtrip_preserved": True,
                   "rg_stage_sync_violations": viol},
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
