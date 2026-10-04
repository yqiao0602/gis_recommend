#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blueprint v2 schema audit v1 (CPU-only, no training).

Blueprint v2 = Ordered + Repetition-aware:
  stages: maximal runs of the ORIGINAL (pre-RLE) semantic chain, each
          {seq, family, repeat}  (repeat = run length >= 1)
  loops:  stages with repeat > 1  (+ iteration-hint keywords from instruction)
  total:  original workflow size (iterations), NOT a Planner target

Audit:
  A1 lossless: expand(runs) == raw chain; sum(repeat) == original_semantic_length
  A2 repetition capture: repeat-share of length by original-length bucket
  A3 loop prevalence: % workflows with >=1 loop, loops/workflow, run-length dist
  A4 iteration-condition recoverability: keyword scan of instructions
  A5 v1<->v2 relation: RLE length vs plan-family length (chain_to_plan merge map)
"""
import json, re
from collections import Counter, defaultdict
import statistics as st

SRC = r"E:/Route2_Migration_20260928/04_DIAG_WORK/b1_gee_stage_train.jsonl"
V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/BLUEPRINT_V2_AUDIT_v1.json"

# pass 1: SRC
src = {}
with open(SRC, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        r = json.loads(line)
        if r.get("split") != "train": continue
        raw = [x.strip() for x in (r.get("semantic_chain_raw") or "").split("->") if x.strip()]
        src[i] = {"raw": raw, "orig": r.get("original_semantic_length"),
                  "instr": r.get("instruction", "")}

# pass 2: core rows -> runs
ITER_KW = {
    "per_band": re.compile(r"\b(band|bands|spectral)\b", re.I),
    "per_year": re.compile(r"\b(year|years|annual|yearly)\b", re.I),
    "per_class": re.compile(r"\b(class|classes|classif|category|categories|land.?cover)\b", re.I),
    "per_feature": re.compile(r"\b(feature|features|object|objects|segment|segments|polygon)\b", re.I),
    "generic_each": re.compile(r"\b(each|every|per|all)\b", re.I),
}
def runs_of(raw):
    runs = []
    for x in raw:
        if runs and runs[-1][0] == x: runs[-1][1] += 1
        else: runs.append([x, 1])
    return runs

by_id = {r["i"]: r for r in
         ({"i": k, **{}} for k in [])}  # placeholder replaced below
# rebuild quickly: iterate core rows
res_rows = []
lossless = 0; sum_ok = 0; total = 0
loop_wf = 0; loops_total = 0; run_lens = Counter(); orig_lens = []
hint_cov = Counter()
bucket = lambda n: ("1-5" if n<=5 else "6-8" if n<=8 else "9-12" if n<=12 else
                    "13-20" if n<=20 else "21-50" if n<=50 else "51+")
prof = defaultdict(lambda: {"n":0, "repeat_share":[], "loops":[], "stages":[]})
v2_examples = []
for line in open(V22, encoding="utf-8"):
    r = json.loads(line)
    if r["cat"] != "core": continue
    sid = r.get("source_row_id")
    if sid not in src: continue
    s = src[sid]; total += 1
    runs = runs_of(s["raw"])
    # A1 lossless checks
    expand = [x for fam, c in runs for x in [fam]*c]
    if expand == s["raw"]: lossless += 1
    if s["orig"] is None or sum(c for _, c in runs) == s["orig"]: sum_ok += 1
    loops = [rn for rn in runs if rn[1] > 1]
    if loops: loop_wf += 1
    loops_total += len(loops)
    for _, c in runs: run_lens[c] += 1
    n = sum(c for _, c in runs)
    orig_lens.append(n)
    repeat_share = round(1 - len(runs)/max(1, n), 3)
    p = prof[bucket(n)]
    p["n"] += 1; p["repeat_share"].append(repeat_share)
    p["loops"].append(len(loops)); p["stages"].append(len(runs))
    # A4 iteration hints
    hints = [k for k, rx in ITER_KW.items() if rx.search(s["instr"])]
    for h in hints: hint_cov[h] += 1
    if not hints: hint_cov["none"] += 1
    res_rows.append({"source_row_id": sid, "stages": [{"seq": i, "family": f, "repeat": c}
                      for i, (f, c) in enumerate(runs, 1)],
                      "total_iterations": n, "stage_count": len(runs),
                      "loop_count": len(loops),
                      "iteration_hints": hints})
    if 21 <= n <= 50 and len(v2_examples) < 3:
        v2_examples.append(res_rows[-1])

# A5 RLE length vs plan families length
pool_fams = {}
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pool_fams[r["row_id"]] = [s.get("family") for s in r["plan"]["steps"]]
ratios = []
for rr in res_rows:
    pf = pool_fams.get(rr["source_row_id"])
    if pf: ratios.append(len(pf) / max(1, rr["stage_count"]))

res = {
    "core_rows": total,
    "A1_lossless_expand": f"{lossless}/{total}",
    "A1_sum_matches_orig_field": f"{sum_ok}/{total}",
    "A2": {},
    "A3_loop_prevalence": {"workflows_with_loop": f"{loop_wf}/{total}",
                            "loops_per_workflow_mean": round(loops_total/total, 2),
                            "run_length_dist_top": dict(sorted(run_lens.items())[-6:])},
    "A4_iteration_hints": {k: round(v/total, 3) for k, v in hint_cov.items()},
    "A5_rle_to_plan_ratio_mean": round(st.mean(ratios), 3),
    "v2_examples_21_50": v2_examples,
}
for b, p in prof.items():
    res["A2"][b] = {"n": p["n"], "repeat_share_mean": round(st.mean(p["repeat_share"]), 3),
                     "loops_mean": round(st.mean(p["loops"]), 2),
                     "stages_mean": round(st.mean(p["stages"]), 2)}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "v2_examples_21_50"}, ensure_ascii=False, indent=1))
print("example 21-50 v2 blueprint:", json.dumps(v2_examples[0] if v2_examples else None, ensure_ascii=False)[:500])
