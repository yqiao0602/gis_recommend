#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-B-0 data diagnosis v1 (owner ruling 2026-10-01): training-data slicing, no training.

Reads frozen artifacts only:
  - 02_DATA_FROZEN/stage1_train_v2_2.jsonl   (frozen Stage-1 v2_2 dataset)
  - 02_DATA_FROZEN/gate_dev_probes_v3.jsonl  (frozen Gate-v3 dev probes)
Outputs R3_B0_DIAGNOSIS_v1.json next to this script.

Dimensions (owner list): plan length, step count, operator diversity, task complexity,
task<->plan correspondence (exact-task duplication, weak-task heuristic), and
training-vs-W3-probe distribution gap. Tier A/B join handled separately when the
tier pool copy finishes transferring.
"""
import json, re, sys
from collections import Counter, defaultdict

DATA = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
PROBES = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/gate_dev_probes_v3.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3b0_diagnosis/R3_B0_DIAGNOSIS_v1.json"

STEP_RE = re.compile(r"^Step (\d+):", re.M)
VERB_RE = re.compile(r"perform an operation that will ([a-z]+(?: [a-z]+)*)")

def pct(p, xs):
    xs = sorted(xs)
    if not xs: return None
    import math
    k = lambda q: xs[min(len(xs)-1, math.ceil(q*len(xs))-1)]
    return {"p50": k(0.5), "p90": k(0.9), "p99": k(0.99), "max": xs[-1], "mean": round(sum(xs)/len(xs), 1)}

def parse_plan(t):
    steps = STEP_RE.findall(t)
    n = len(steps)
    verbs = VERB_RE.findall(t)
    ops = Counter(verbs)
    # io types flow
    ios = re.findall(r"(?:Input accepts|Produces): ([a-z_]+)", t)
    return n, ops, ios

def main():
    rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    core = [r for r in rows if r["cat"] == "core"]
    res = {"core_rows": len(core)}

    # --- plan-side structure ---
    nsteps, tok_len, uniq_ops_rows, op_global = [], [], [], Counter()
    for r in core:
        t = r["target"]
        n, ops, _ = parse_plan(t)
        nsteps.append(n)
        tok_len.append(len(t.split()))
        uniq_ops_rows.append(len(ops))
        op_global.update(ops)
    res["plan_steps"] = pct(None, nsteps)
    res["plan_steps_hist"] = dict(sorted(Counter(nsteps).items()))
    res["plan_token_len"] = pct(None, tok_len)
    res["plan_ops_per_row"] = pct(None, uniq_ops_rows)
    res["global_op_diversity"] = {"distinct_ops": len(op_global), "top10": op_global.most_common(10)}

    # --- task side ---
    task_lens, task_dup = [], 0
    task_to_targets = defaultdict(set)
    for r in core:
        task = r["task"]
        task_lens.append(len(task.split()))
        task_to_targets[task].add(r["target"])
    res["task_token_len"] = pct(None, task_lens)
    dup_groups = {t: len(v) for t, v in task_to_targets.items() if len(v) > 1}
    res["task_correspondence"] = {
        "unique_tasks": len(task_to_targets),
        "rows": len(core),
        "tasks_with_multiple_distinct_plans": len(dup_groups),
        "rows_in_multi_plan_groups": sum(len(v) for v in task_to_targets.values() if len(v) > 1),
        "max_plans_per_task": max(task_to_targets.values(), key=len) and max(len(v) for v in task_to_targets.values()),
    }
    # weak-task heuristic: very short task + long plan
    weak = [(r["task"], r["target"]) for r in core if len(r["task"].split()) <= 12 and len(r["target"].split()) >= 150]
    res["weak_task_strong_plan"] = {"count": len(weak), "share": round(len(weak)/len(core), 4),
                                    "examples": [{"task": w[0][:200], "plan_len_words": len(w[1].split())} for w in weak[:3]]}

    # --- truncation footprint (builder side, from dataset report) ---
    rep = json.load(open(r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/stage1_dataset_report_v2_2.json", encoding="utf-8"))
    res["builder_truncation_core"] = rep["truncation_by_cat"]["core"]["target"]
    # which rows are the long tail? steps>=p99 count
    p99 = sorted(nsteps)[int(0.99*len(nsteps))-1]
    res["long_tail"] = {"steps_ge_p99": p99, "rows": sum(1 for x in nsteps if x >= p99)}

    # --- W3 dev probes vs training distribution ---
    probes = [json.loads(l) for l in open(PROBES, encoding="utf-8")]
    w3 = [p for p in probes if p.get("capability") == "W3"]
    keys = sorted(w3[0].keys()) if w3 else []
    res["w3_probe_keys"] = keys
    w3_steps, w3_ops_all = [], Counter()
    for p in w3:
        gold = p.get("gold") or p.get("plan") or ""
        if gold:
            n, ops, _ = parse_plan(gold)
            w3_steps.append(n)
            w3_ops_all.update(ops)
    res["w3_probe_gold_steps"] = pct(None, w3_steps)
    res["w3_probe_gold_steps_hist"] = dict(sorted(Counter(w3_steps).items()))
    # coverage gap: W3 gold step counts vs training step-count CDF at same points
    nsteps_sorted = sorted(nsteps)
    import bisect
    def cdf(x): return round(bisect.bisect_right(nsteps_sorted, x)/len(nsteps_sorted), 4)
    res["train_cdf_at_w3_points"] = {str(k): cdf(k) for k in sorted(set(w3_steps))[:12]}

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])

if __name__ == "__main__":
    main()
