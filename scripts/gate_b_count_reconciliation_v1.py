#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate B pure count reconciliation (owner round-13 directive).

No label changes, no rule changes. Answers exactly:
  (a) where is the 14th owner-B* label (13 vs 14 accounting gap)?
  (b) what is the exact bucket composition of 25159's +10 task-level delta?
  (c) per-group B*-label census with bucket distribution.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

RL = Path(__file__).resolve().parents[1] / \
    "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"

d = json.loads((RL / "gate_b_unblind_v1.json").read_text(encoding="utf-8"))
rows = d["rows"]

print("=" * 70)
print("(a) owner-B* label census: where did each B land?")
b_rows = [r for r in rows if r["owner"] == "B"]
print(f"total owner-B labels in rows: {len(b_rows)}")
by_group = defaultdict(list)
for r in b_rows:
    by_group[r["k"]].append((r["cand"], r["slot"], r["bucket"]))
for k, items in sorted(by_group.items()):
    print(f"  k={k}: {len(items)}")
    for cand, slot, bucket in sorted(items):
        print(f"     cand{cand} {slot}: {bucket}")

print("=" * 70)
print("(b) 25159 delta decomposition (r5_missing=15 vs owner_O=5)")
g15 = [r for r in rows if r["k"] == 25159 and r["r5_state"] == "missing"]
print(f"r5_missing rows for 25159: {len(g15)}")
comp = Counter((r["slot"], r["bucket"]) for r in g15)
for (slot, bucket), n in sorted(comp.items()):
    print(f"  {slot} x {bucket}: {n}")
also = [r for r in rows if r["k"] == 25159 and r["r5_state"] != "missing"]
print(f"25159 non-missing rows: {len(also)} -> "
      f"{Counter((r['slot'], r['bucket']) for r in also)}")

print("=" * 70)
print("(c) full bucket table per group")
groups = sorted({r["k"] for r in rows})
for k in groups:
    rs = [r for r in rows if r["k"] == k]
    c = Counter(r["bucket"] for r in rs)
    print(f"  k={k}: total={len(rs)} {dict(c)}")
