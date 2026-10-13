#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Phase 1 — A-group candidate selection (PCA_PROTOCOL_V1_FROZEN §2.1/§2.3).

Pool (from pca_a_group_isolation_v1.py): authority (frozen GEE 128,447-row
b1_gee_stage_train.jsonl) rows with split in {val, test} whose normalized
instruction is NOT in the actually-consumed planner_v2_train pool. 26,931
candidates, all tier source_record_text_aligned (authority val/test are
99.98%+ unconsumed; train-split candidates are NOT used here).

Frozen selection rules (seed 20261013):
  - complexity bands by final_semantic_length: <=4 / 5-7 / >=8, target 6/10/4
  - task_type diversification: round-robin over types (rarest-first),
    max 3 rows per type in the primary 20
Output: candidate file with 20 primary + 30 reserve + per-type census.
NOTE: pairing tasks (protocol §2.5) may replace some primary rows later;
the pool is large enough that replacement is loss-free.
"""
import json, random, hashlib
from collections import Counter, defaultdict

AUTH = "../server_backup_mdzhang_20260927/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl"
POOL = "../pca_data_ref/planner_v2_train.jsonl"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_a_group_candidates_v1.json"
SEED, N_PRIMARY, N_RESERVE = 20261013, 20, 30

def norm(s):
    return " ".join((s or "").split()).strip().lower()

def band(n):
    if n is None: return "?"
    return "short_<=4" if n <= 4 else ("medium_5_7" if n <= 7 else "long_>=8")

def main():
    pool = set()
    for line in open(POOL, encoding="utf-8"):
        pool.add(norm(json.loads(line).get("task", "")))
    rows = []
    for i, line in enumerate(open(AUTH, encoding="utf-8")):
        r = json.loads(line)
        if r.get("split") not in ("val", "test"):
            continue
        if norm(r.get("instruction", "")) in pool:
            continue
        rows.append({
            "line_id": i, "split": r.get("split"),
            "task_type": r.get("task_type", "?"),
            "len_band": band(r.get("final_semantic_length")),
            "final_len": r.get("final_semantic_length"),
            "instruction": r.get("instruction", ""),
            "chain_head": " -> ".join((r.get("gee_canonical_chain") or [])[:6]),
        })
    # authority-internal ambiguity check on the held-out pool
    seen = Counter(norm(r["instruction"]) for r in rows)
    for r in rows:
        r["tier"] = ("source_record_text_aligned" if seen[norm(r["instruction"])] == 1
                     else "text_dedup_only")

    cand = [r for r in rows if r["tier"] == "source_record_text_aligned"]
    rng = random.Random(SEED)
    cells = defaultdict(list)
    for r in cand:
        cells[(r["task_type"], r["len_band"])].append(r)
    for k in cells:
        rng.shuffle(cells[k])
    order = sorted(cells, key=lambda k: (len(cells[k]), k))

    primary, reserve = [], []
    per_type = Counter()
    # pass 1: complexity-band targets via round-robin, <=3 per type
    band_target = {"short_<=4": 6, "medium_5_7": 10, "long_>=8": 4}
    band_left = dict(band_target)
    i = 0
    while len(primary) < N_PRIMARY and any(cells[k] for k in order):
        k = order[i % len(order)]
        typ, lb = k
        if cells[k] and per_type[typ] < 3 and band_left.get(lb, 0) > 0:
            primary.append(cells[k].pop(0))
            per_type[typ] += 1
            band_left[lb] -= 1
        i += 1
    # pass 2: fill remaining primary ignoring band targets (keep type cap)
    i = 0
    while len(primary) < N_PRIMARY and any(cells[k] for k in order):
        k = order[i % len(order)]
        if cells[k] and per_type[k[0]] < 3:
            primary.append(cells[k].pop(0))
            per_type[k[0]] += 1
        i += 1
    flat = [r for k in order for r in cells[k]]
    rng.shuffle(flat)
    reserve = flat[:N_RESERVE]

    type_census = Counter(r["task_type"] for r in cand)
    out = {
        "_meta": {
            "protocol": "PCA_PROTOCOL_V1_FROZEN §2.1/§2.3",
            "seed": SEED,
            "pool_definition": "authority(val,test) x not-in-consumed-pool x "
                               "authority-internal-unique text",
            "pool_size": len(cand),
            "n_primary": len(primary), "n_reserve": len(reserve),
            "band_target": band_target,
            "pairing_note": "some primary rows may be replaced by paired-task "
                            "assignments later; pool is loss-free for swap",
            "tier_of_all_listed": "source_record_text_aligned",
        },
        "stats": {
            "primary_by_band": dict(Counter(r["len_band"] for r in primary)),
            "primary_by_type": dict(Counter(r["task_type"] for r in primary)),
            "primary_by_split": dict(Counter(r["split"] for r in primary)),
            "pool_by_type_top15": dict(type_census.most_common(15)),
            "pool_n_types": len(type_census),
        },
        "primary": primary, "reserve": reserve,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["stats"], indent=1))
    print("saved:", OUT)

if __name__ == "__main__":
    main()
