#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Phase 1 — B-group screening (PCA_PROTOCOL_V1_FROZEN §2.1/§2.4).

Frozen screening rules (committed BEFORE viewing any E2E Step-1 prediction):
  1. Source: docs/reports/v2a_manifest/v2a_A_dev.jsonl (dev-120, Tier-1).
  2. Operator-ID scan: reject task_text containing provider:slug operator IDs
     (native:*/gdal:*/grass7:*/qgis:*/saga:*).
  3. Operator-word flag: flag (do NOT hard-reject) task_text containing any of
     the frozen common-operator lexicon; flagged rows go to owner review.
  4. Stratified seeded pick: strata = taskType x chain-length band (processes
     count: short 2-3 / medium 4-6 / long >=7); select 20 primary + 10
     reserve with seed 20261013, maximizing taskType diversity.
Audit trail: every row records scan verdict + flags + stratum. Zero reference
to any prediction file (E2E Step-1 outputs are not read).
"""
import json, re, random
from collections import Counter, defaultdict

DEV = "docs/reports/v2a_manifest/v2a_A_dev.jsonl"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_candidates_v1.json"
SEED = 20261013
N_PRIMARY, N_RESERVE = 20, 10

# Frozen common-operator lexicon (Phase-1 freeze; flagged only, never auto-reject)
LEXICON = [
    "buffer", "clip", "merge", "dissolve", "intersect", "union", "difference",
    "reproject", "reprojected", "slope", "aspect", "hillshade", "contour",
    "classify", "reclassify", "resample", "mosaic", "zonal statistics",
    "raster calculator", "interpolate", "simplify",
    "smooth", "spatial join", "extract by", "select by location",
    "select by expression", "polygonize", "proximity", "grid", "warp",
    "near(", "vignette", "pan-sharpen", "triangulation", "idw", "kriging",
]
OPID_RE = re.compile(r"\b(?:native|gdal|grass7|qgis|saga):[a-z0-9_]+", re.I)

def length_band(n):
    return "short_2_3" if n <= 3 else ("medium_4_6" if n <= 6 else "long_7p")

def main():
    rows = [json.loads(l) for l in open(DEV, encoding="utf-8")]
    assert len(rows) == 120
    cand = []
    for r in rows:
        tt = r["task_text"]
        opids = sorted(set(m.group(0).lower() for m in OPID_RE.finditer(tt)))
        flags = sorted({w for w in LEXICON if w in tt.lower()})
        n_proc = len(r["processes"])
        cand.append({
            "wid": r["wid"], "taskType": r["taskType"],
            "chain_len": n_proc, "len_band": length_band(n_proc),
            "op_id_hits": opids, "lexicon_flags": flags,
            "pass_opid_scan": not opids,
            "task_head": tt[:160],
            "source_sha256": r["source_sha256"][:16],
        })
    pool = [c for c in cand if c["pass_opid_scan"]]
    # Stratified pick: taskType x len_band, one per cell first, then fill
    rng = random.Random(SEED)
    cells = defaultdict(list)
    for c in pool:
        cells[(c["taskType"], c["len_band"])].append(c)
    for k in cells:
        rng.shuffle(cells[k])
    # round-robin across cells ordered by rarest first for diversity
    order = sorted(cells, key=lambda k: (len(cells[k]), k))
    primary, reserve = [], []
    i = 0
    while len(primary) < N_PRIMARY and any(cells[k] for k in order):
        k = order[i % len(order)]
        if cells[k]:
            primary.append(cells[k].pop(0))
        i += 1
    flat = [c for k in order for c in cells[k]]
    rng.shuffle(flat)
    reserve = flat[:N_RESERVE]
    out = {
        "_meta": {
            "protocol": "PCA_PROTOCOL_V1_FROZEN §2.1/§2.4",
            "seed": SEED, "n_source": 120, "n_pass_opid_scan": len(pool),
            "n_rejected_opid": 120 - len(pool),
            "n_primary": len(primary), "n_reserve": len(reserve),
            "screening_precedes_prediction_review": True,
            "lexicon_frozen": LEXICON,
            "note": "lexicon_flags are advisory for owner review, not rejections",
        },
        "primary": primary, "reserve": reserve,
        "rejected_by_opid": [c for c in cand if not c["pass_opid_scan"]],
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("saved:", OUT)

if __name__ == "__main__":
    main()
