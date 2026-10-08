#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-B-0 tier join v2: prefix-aware join.

Pool `instruction` is a ~400-char truncation of the full task text used by the
dataset builder, so training task == pool instruction + continuation. Join rule:
normalized pool instruction is a PREFIX of normalized training task.
W3 probes: extract the task text from probe prompt, same prefix rule.
"""
import json, re
from collections import Counter, defaultdict

POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
DATA = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
PROBES = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/gate_dev_probes_v3.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3b0_diagnosis/R3_B0_TIER_JOIN_v2.json"

norm = lambda s: re.sub(r"\s+", " ", s).strip()

pool_by_prefix = defaultdict(list)
tier_counts = Counter()
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        tier_counts[r["tier"]] += 1
        pool_by_prefix[norm(r["instruction"])].append(r)

res = {"pool_tier_counts": dict(tier_counts)}

def join_task(task, steps_n=None):
    t = norm(task)
    # candidate pool rows: those whose instruction is a prefix of t (or equal).
    # index by first 50 chars for speed; try progressively shorter prefixes.
    cands = []
    for L in (400, 200, 80, 50):
        bucket = pool_by_prefix.get(t[:L])
        if bucket:
            for r in bucket:
                if t.startswith(r["_n"]):
                    cands.append(r)
        if cands:
            break
    return cands

# attach normalized text once
for v in pool_by_prefix.values():
    for r in v:
        r["_n"] = norm(r["instruction"])

rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
core = [r for r in rows if r["cat"] == "core"]
STEP_RE = re.compile(r"^Step (\d+):", re.M)

tier_of_row, ambiguous, unmatched = [], 0, 0
tier_steps, tier_toklen, tier_branch = defaultdict(list), defaultdict(list), defaultdict(list)
for r in core:
    cands = join_task(r["task"])
    if not cands:
        unmatched += 1
        continue
    tiers = {c["tier"] for c in cands}
    if len(tiers) > 1:
        ambiguous += 1
        continue
    t = cands[0]["tier"]
    tier_of_row.append(t)
    n = len(STEP_RE.findall(r["target"], re.M))
    tier_steps[t].append(n)
    tier_toklen[t].append(len(r["target"].split()))
    tier_branch[t].append(cands[0]["features"].get("branch_ratio", 0))

res["core_join"] = {"rows": len(core), "unmatched": unmatched, "ambiguous_tier": ambiguous,
                    "tier_composition": dict(Counter(tier_of_row))}

def pctl(xs):
    xs = sorted(xs)
    if not xs: return None
    import math
    k = lambda q: xs[min(len(xs)-1, math.ceil(q*len(xs))-1)]
    return {"p50": k(0.5), "p90": k(0.9), "p99": k(0.99), "max": xs[-1], "mean": round(sum(xs)/len(xs),1)}

res["tier_profile"] = {t: {"n": len(s), "steps": pctl(s), "plan_tokens": pctl(tier_toklen[t]),
                           "branch_ratio_mean": round(sum(tier_branch[t])/max(1,len(tier_branch[t])),3)}
                       for t, s in tier_steps.items()}

# W3 probes: extract task from prompt
probes = [json.loads(l) for l in open(PROBES, encoding="utf-8")]
w3 = [p for p in probes if p.get("capability") == "W3"]
print("W3 prompt sample:", repr(w3[0]["prompt"][:300]))
res["w3_prompt_sample"] = w3[0]["prompt"][:300]

w3_tiers, w3_unmatched, w3_ambiguous = Counter(), 0, 0
w3_tier_steps = defaultdict(list)
for p in w3:
    m = re.search(r"Task:(.*?)(?:\nGenerate|\nWrite|\nOutput|\nPlan|$)", p["prompt"], re.S)
    task = ("Task: " + m.group(1)) if m else p["prompt"]
    cands = join_task(task)
    if not cands:
        w3_unmatched += 1
        continue
    tiers = {c["tier"] for c in cands}
    if len(tiers) > 1:
        w3_ambiguous += 1
        continue
    t = cands[0]["tier"]
    w3_tiers[t] += 1
    w3_tier_steps[t].append(len(STEP_RE.findall(p.get("target",""), re.M)))

res["w3_probe_join"] = {"probes": len(w3), "unmatched": w3_unmatched, "ambiguous": w3_ambiguous,
                        "tier_composition": dict(w3_tiers),
                        "gold_steps_by_tier": {t: pctl(s) for t, s in w3_tier_steps.items()}}

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "w3_prompt_sample"}, ensure_ascii=False, indent=1)[:2500])
