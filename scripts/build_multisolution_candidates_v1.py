#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-solution diagnostic set v0 — candidate retrieval (D1/D2/D3).

Owner ruling (2026-10-11): D1 natural-corpus mining primary (manual
construction only as tagged supplement); D2/D3 auto-retrieve candidates ->
manual semantic confirmation. First-version floors: D1>=10 groups,
D2>=5 pairs, D3>=5 pairs — exploratory, not statistical validation scale.

This script ONLY generates CANDIDATES for manual semantic confirmation.
No legality/equivalence ruling is made here.

  D2 candidate (granularity-equivalence pair): two rows with (nearly) the
    same task semantics but divergent representation — one unrolled (same
    adjacency run >=5, no repetition groups covering it) and one compact
    (repetition group / single range filter), matched by task-keyword bucket
    + family multiset Jaccard.
  D3 candidate (granularity non-equivalence risk): pairs whose compact
    expression DROPS semantic constraints present in the unrolled variant
    (e.g., year-distinct filters collapsed) — flagged for manual check that
    normalization does not erase year/phase conditions.
  D1 candidate (alternative-chain group): >=2 rows with high task-title
    similarity but different family multisets — candidate alternative chains
    for the same task goal.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
CORPUS = os.path.join(REPO, "..", "04_DIAG_WORK", "planner_v2_train.jsonl")
OUT = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                   "plan_pipeline_v1", "planner_design",
                   "MULTISOLUTION_CANDIDATES_V0.json")

BUCKETS = [
    ("time_series", re.compile(r"time.series|temporal|trend|season|yearly|monthly|annual", re.I)),
    ("ndvi_veg", re.compile(r"NDVI|vegetat|crop|veg|EVI|SAVI", re.I)),
    ("classify", re.compile(r"classif|land.cover|landcover|random forest", re.I)),
    ("water", re.compile(r"water|flood|drought|precipit|rain|NDWI|MNDWI|snow", re.I)),
    ("temperature", re.compile(r"temperature|LST|heat", re.I)),
    ("fire", re.compile(r"fire|burn|NBR", re.I)),
    ("terrain", re.compile(r"elevation|DEM|slope|terrain|hillshade", re.I)),
    ("urban", re.compile(r"urban|built.up|city", re.I)),
]


def buckets_of(task_text):
    t = task_text or ""
    return [n for n, rx in BUCKETS if rx.search(t)] or ["other"]


def title_of(task_text):
    return (task_text or "").splitlines()[0].replace("Task:", "").strip()


def load_rows():
    rows = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            tgt = r.get("target")
            if isinstance(tgt, str):
                try:
                    tgt = json.loads(tgt)
                except Exception:
                    continue
            if not isinstance(tgt, dict) or "stages" not in tgt:
                continue
            stages = tgt["stages"]
            fams = [s["family"] for s in stages]
            rg = tgt.get("repetition_groups", []) or []
            rows.append({
                "task": r.get("task") or "",
                "title": title_of(r.get("task")),
                "buckets": buckets_of(r.get("task")),
                "families": fams,
                "famset": set(fams),
                "stages_n": len(stages),
                "rg_n": len(rg),
                "rg_fams": [g.get("family") for g in rg if g.get("repeat", 1) > 1],
            })
    return rows


def max_same_adjacency_run(fams):
    run = best = 1
    for i in range(1, len(fams)):
        run = run + 1 if fams[i] == fams[i - 1] else 1
        best = max(best, run)
    return best if len(fams) else 0


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def main():
    rows = load_rows()
    print("blueprint rows:", len(rows))

    # ---------- representation signature ----------
    def is_periodic_unrolled(fams, max_period=8, min_cycles=2, min_match=0.9):
        """Detect k=956-style unrolling: a short family cycle repeated many
        times WITHOUT repetition_groups (e.g., 20x[RL,TF,AF,BS,AGG])."""
        n = len(fams)
        if n < min_cycles * 2:
            return False
        for p in range(1, max_period + 1):
            if n < p * min_cycles:
                break
            checked = matched = 0
            for i in range(n - p):
                checked += 1
                if fams[i] == fams[i + p]:
                    matched += 1
            if checked and matched / checked >= min_match:
                return True
        return False

    for r in rows:
        r["unrolled_flag"] = (
            r["rg_n"] == 0 and r["stages_n"] >= 10 and
            (max_same_adjacency_run(r["families"]) >= 5 or
             is_periodic_unrolled(r["families"])))
        r["compact_flag"] = (r["rg_n"] >= 1 and r["stages_n"] <= 15) or \
                            (r["rg_n"] == 0 and r["stages_n"] <= 8
                             and any(f in ("TEMPORAL_FILTER",) for f in r["families"]))

    unrolled = [r for r in rows if r["unrolled_flag"]]
    compact = [r for r in rows if r["compact_flag"]]
    print(f"unrolled-style rows: {len(unrolled)} | compact-style rows: {len(compact)}")

    # ---------- D2/D3 candidates: unrolled x compact in same bucket with
    # similar family multiset ----------
    d2 = []
    d3 = []
    by_bucket_u = defaultdict(list)
    for r in unrolled:
        for b in r["buckets"]:
            by_bucket_u[b].append(r)
    seen_pairs = set()
    for r in compact:
        cands = []
        seen = set()
        for b in r["buckets"]:
            for u in by_bucket_u.get(b, []):
                if u is r:
                    continue
                if u["famset"] != r["famset"]:
                    continue
                if id(u) in seen:
                    continue
                seen.add(id(u))
                cands.append(u)
        for u in cands[:3]:
            key = (min(u["title"], r["title"]), max(u["title"], r["title"]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            fam_j = jaccard(u["famset"], r["famset"])
            title_sim = SequenceMatcher(None, u["title"], r["title"]).ratio()
            entry = {
                "unrolled": {"title": u["title"][:120], "stages_n": u["stages_n"],
                             "rg_n": u["rg_n"],
                             "max_run": max_same_adjacency_run(u["families"])},
                "compact": {"title": r["title"][:120], "stages_n": r["stages_n"],
                            "rg_n": r["rg_n"]},
                "family_jaccard": round(fam_j, 3),
                "title_similarity": round(title_sim, 3),
            }
            # D3 risk heuristic: compact variant of a multi-year task whose
            # unrolled counterpart has year-distinct temporal filters
            if fam_j >= 0.8 and title_sim >= 0.6:
                entry["candidate_class"] = "D2_granularity_equivalence_candidate"
                d2.append(entry)
            elif fam_j >= 0.6:
                entry["candidate_class"] = "D3_granularity_nonequivalence_risk"
                entry["d3_check"] = ("verify whether the compact variant drops "
                                     "year/phase-distinct filters")
                d3.append(entry)

    # ---------- D1 candidates: similar task titles, different family sets ----------
    by_bucket_t = defaultdict(list)
    for r in rows:
        for b in r["buckets"][:2]:
            by_bucket_t[b].append(r)
    d1 = []
    seen_pairs = set()
    for r in rows:
        fams_key = ",".join(sorted(r["famset"]))
        for b in r["buckets"][:2]:
            for o in by_bucket_t.get(b, []):
                if o is r or id(o) in seen_pairs:
                    continue
                tj = SequenceMatcher(None, r["title"], o["title"]).ratio()
                if tj < 0.72:
                    continue
                fj = jaccard(r["famset"], o["famset"])
                if fj >= 0.9 or len(r["famset"] & o["famset"]) == 0:
                    continue  # near-identical or totally different: not informative
                key = (min(r["title"], o["title"]), max(r["title"], o["title"]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                d1.append({
                    "task_a": {"title": r["title"][:120],
                               "families": sorted(r["famset"])},
                    "task_b": {"title": o["title"][:120],
                               "families": sorted(o["famset"])},
                    "title_similarity": round(tj, 3),
                    "family_jaccard": round(fj, 3),
                })
                if len(d1) >= 40:
                    break
            if len(d1) >= 40:
                break
        if len(d1) >= 40:
            break

    d1 = d1[:40]
    d2 = d2[:20]
    d3 = d3[:20]

    out = {
        "schema": "multisolution_candidates_v0",
        "note": "CANDIDATES ONLY — no legality/equivalence ruling made; "
                "manual semantic confirmation required (owner 2026-10-11)",
        "floors": {"D1_groups": 10, "D2_pairs": 5, "D3_pairs": 5},
        "counts": {"D1_groups": len(d1), "D2_pairs": len(d2),
                   "D3_pairs": len(d3)},
        "D1_alternative_chain_groups": d1,
        "D2_granularity_equivalence_pairs": d2,
        "D3_granularity_nonequivalence_pairs": d3,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps({"counts": out["counts"], "out": OUT}, indent=2,
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
