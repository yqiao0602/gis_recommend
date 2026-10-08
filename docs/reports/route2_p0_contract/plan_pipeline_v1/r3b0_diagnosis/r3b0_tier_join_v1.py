#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-B-0 tier join v1: join frozen Stage-1 core rows and W3 dev probes to the tier pool.

Join keys:
  - training core row.task  == pool.instruction  (exact text)
  - W3 probe.source_row_id  == pool.row_id
Outputs R3_B0_TIER_JOIN_v1.json.
"""
import json, re
from collections import Counter, defaultdict

POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
DATA = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
PROBES = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/gate_dev_probes_v3.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3b0_diagnosis/R3_B0_TIER_JOIN_v1.json"

pool_by_task = defaultdict(list)
pool_by_id = {}
tier_counts = Counter()
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        tier_counts[r["tier"]] += 1
        pool_by_task[r["instruction"]].append(r)
        pool_by_id[r["row_id"]] = r

res = {"pool_tier_counts": dict(tier_counts), "pool_rows": sum(tier_counts.values())}

rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
core = [r for r in rows if r["cat"] == "core"]

joined, ambiguous, unmatched = [], 0, 0
tier_steps = defaultdict(list)
tier_toklen = defaultdict(list)
tier_flow = defaultdict(list)
for r in core:
    cands = pool_by_task.get(r["task"], [])
    if not cands:
        unmatched += 1
        continue
    tiers = {c["tier"] for c in cands}
    if len(tiers) > 1:
        ambiguous += 1
        continue
    t = cands[0]["tier"]
    joined.append(t)
    import re as _re
    n = len(_re.findall(r"^Step (\d+):", r["target"], _re.M))
    tier_steps[t].append(n)
    tier_toklen[t].append(len(r["target"].split()))
    for c in cands[:1]:
        tier_flow[t].append(c["features"].get("flow_breaks", 0))

res["core_join"] = {
    "core_rows": len(core), "unmatched": unmatched, "ambiguous_tier": ambiguous,
    "tier_composition": dict(Counter(joined)),
}

def pctl(xs):
    xs = sorted(xs)
    if not xs: return None
    import math
    k = lambda q: xs[min(len(xs)-1, math.ceil(q*len(xs))-1)]
    return {"p50": k(0.5), "p90": k(0.9), "p99": k(0.99), "max": xs[-1], "mean": round(sum(xs)/len(xs),1)}

res["tier_profile"] = {t: {"n": len(s), "steps": pctl(s),
                           "plan_tokens": pctl(tier_toklen[t]),
                           "flow_breaks_mean": round(sum(tier_flow[t])/max(1,len(tier_flow[t])),2)}
                       for t, s in tier_steps.items()}

probes = [json.loads(l) for l in open(PROBES, encoding="utf-8")]
w3 = [p for p in probes if p.get("capability") == "W3"]
w3_tiers, w3_unmatched = Counter(), 0
w3_tier_steps = defaultdict(list)
for p in w3:
    rid = p.get("source_row_id")
    c = pool_by_id.get(rid)
    if c is None:
        w3_unmatched += 1
        continue
    w3_tiers[c["tier"]] += 1
    w3_tier_steps[c["tier"]].append(len(re.findall(r"^Step (\d+):", p.get("target",""), re.M)))
res["w3_probe_join"] = {"probes": len(w3), "unmatched": w3_unmatched,
                        "tier_composition": dict(w3_tiers),
                        "steps_by_tier": {t: pctl(s) for t, s in w3_tier_steps.items()}}

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:3500])
