#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent verification of Split V3 (read-only).

Checks (no re-run of feature extraction):
  1. V3 keeps the V2 component mapping unchanged.
  2. family_ids are deterministic (sha1 of sorted member components).
  3. each component maps to exactly one family; each family to one split.
  4. the family-level 80/10/10 assignment reproduces from seed 20261018.
  5. every row split equals its family split.
  6. V2 -> V3 row/component changes are counted.

Output: B_TRACK_SPLIT_V3_VERIFICATION_V1.json
"""
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
SEED = 20261018


def family_id(members):
    return "F" + hashlib.sha1(
        ",".join(str(x) for x in sorted(members)).encode()).hexdigest()[:16]


def main():
    v2 = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V2.json").read_text(encoding="utf-8"))
    v3 = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V3.json").read_text(encoding="utf-8"))
    checks = {}
    checks["pool_rows_equal"] = len(v2["row_component"]) == len(v3["row_component"]) == v3["pool_rows"]
    checks["row_component_unchanged"] = v2["row_component"] == v3["row_component"]
    family_ids = v3["family_ids"]
    row_family = v3["row_family"]
    row_split = v3["row_split"]
    row_comp = v3["row_component"]
    comp_family = {}
    conflict = 0
    for c, fi in zip(row_comp, row_family):
        fid = family_ids[fi]
        if c in comp_family and comp_family[c] != fid:
            conflict += 1
        comp_family[c] = fid
    checks["component_single_family"] = conflict == 0
    members = defaultdict(list)
    for c, fid in comp_family.items():
        members[fid].append(c)
    checks["family_ids_deterministic"] = all(
        family_id(mem) == fid for fid, mem in members.items())
    fam_split = {}
    split_conflict = 0
    for i, (c, fid) in enumerate(zip(row_comp, [family_ids[x] for x in row_family])):
        if fid in fam_split and fam_split[fid] != row_split[i]:
            split_conflict += 1
        fam_split[fid] = row_split[i]
    checks["family_single_split"] = split_conflict == 0
    ids = sorted(family_ids)
    rng = random.Random(SEED)
    rng.shuffle(ids)
    n = len(ids)
    ntr, nv = round(n * 0.8), round(n * 0.1)
    expect = {}
    for i, fid in enumerate(ids):
        expect[fid] = "t" if i < ntr else ("v" if i < ntr + nv else "s")
    mism = sum(1 for fid, sp in fam_split.items() if expect.get(fid) != sp)
    checks["seed_reproduces_family_split"] = mism == 0
    row_mism = sum(1 for i, fid in enumerate([family_ids[x] for x in row_family])
                   if expect[fid] != row_split[i])
    checks["row_matches_family_split"] = row_mism == 0
    split_rows = Counter(row_split)
    split_fams = Counter(expect.values())
    split_comps = Counter()
    for c, fid in comp_family.items():
        split_comps[expect[fid]] += 1
    changed_rows = sum(1 for a, b in zip(v2["row_split"], row_split) if a != b)
    # component split from the first row of that component in V2/V3
    comp_split_v2, comp_split_v3 = {}, {}
    for i, c in enumerate(row_comp):
        comp_split_v2.setdefault(c, v2["row_split"][i])
        comp_split_v3.setdefault(c, row_split[i])
    changed_comps = sum(1 for c in comp_split_v2 if comp_split_v2[c] != comp_split_v3[c])
    out = {
        "artifact": "B_TRACK_SPLIT_V3_VERIFICATION_V1", "date": "2026-10-18",
        "seed": SEED,
        "checks": checks,
        "all_pass": all(checks.values()),
        "counts": {
            "pool_rows": len(row_comp),
            "components": len(comp_family),
            "families": len(members),
            "split_families": {k: split_fams[k] for k in ("t", "v", "s")},
            "split_components": {k: split_comps[k] for k in ("t", "v", "s")},
            "split_rows": {k: split_rows[k] for k in ("t", "v", "s")},
            "rows_changed_v2_to_v3": changed_rows,
            "components_changed_v2_to_v3": changed_comps,
        },
        "hashes": v3.get("hashes", {}),
    }
    (B / "B_TRACK_SPLIT_V3_VERIFICATION_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
