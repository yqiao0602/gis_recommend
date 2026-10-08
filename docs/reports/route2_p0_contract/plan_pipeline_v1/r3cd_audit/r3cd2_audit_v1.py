#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-CD-2 CPU audit v1: characterize what run-cap (RLE) removes and re-test
task->length signal at full coverage.

Stages: original semantic chain (raw) -> final (RLE) -> plan steps.
Owner checklist: step counts, op/intent diversity, deleted-step nature/position,
correlations (task x orig/final/plan, multi-proxy), task-grouped length stats.
"""
import json, re, statistics as st
from collections import Counter, defaultdict

SRC = r"E:/Route2_Migration_20260928/04_DIAG_WORK/b1_gee_stage_train.jsonl"
V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3cd_audit/R3_CD2_AUDIT_v1.json"
STEP_RE = re.compile(r"^Step (\d+):", re.M)
norm = lambda s: re.sub(r"\s+", " ", s).strip()

# pass 1: SRC scan
rows = []
with open(SRC, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        r = json.loads(line)
        if r.get("split") != "train": continue
        raw = [x.strip() for x in (r.get("semantic_chain_raw") or "").split("->") if x.strip()]
        rle = [x.strip() for x in (r.get("semantic_chain_rle") or "").split("->") if x.strip()]
        rows.append({"i": i, "raw": raw, "rle": rle, "orig": r.get("original_semantic_length"),
                     "fin": r.get("final_semantic_length"), "cap": r.get("run_cap_applied"),
                     "instr": r.get("instruction", "")})

# RLE-vs-raw structural verification
prefix_ok, subseq_ok, mismatch = 0, 0, 0
run_dups_removed, removed_by_family, kept_by_family = 0, Counter(), Counter()
removed_pos_frac, run_lengths = [], defaultdict(int)
for r in rows:
    raw, rle = r["raw"], r["rle"]
    if not raw or not rle: continue
    # check RLE is order-preserving subsequence with runs collapsed
    j, ok_runs, dels, cur_run = 0, True, 0, 1
    pos_kept = []
    for k, x in enumerate(raw):
        if j < len(rle) and x == rle[j]:
            pos_kept.append(k); j += 1
        else:
            dels += 1
    if j == len(rle):
        subseq_ok += 1
        if pos_kept and pos_kept == list(range(len(rle))): prefix_ok += 1
    else:
        mismatch += 1
    # run structure of raw: count consecutive duplicates
    if r["orig"] and r["fin"] and r["orig"] > r["fin"]:
        run_dups_removed += r["orig"] - r["fin"]
        # deleted = within-run duplicates; family distribution
        c = Counter(raw); k2 = Counter(rle)
        for fam, n in c.items():
            removed_by_family[fam] += max(0, n - k2.get(fam, 0))
            kept_by_family[fam] += k2.get(fam, 0)
        # run-length distribution in raw (per maximal consecutive run)
        run = 1
        for a, b in zip(raw, raw[1:]):
            if a == b: run += 1
            else: run_lengths[run] += 1; run = 1
        run_lengths[run] += 1

res = {
    "src_train_rows": len(rows),
    "rle_is_subsequence": subseq_ok, "rle_is_prefix": prefix_ok, "mismatch": mismatch,
    "rle_duplicates_removed_total": run_dups_removed,
    "run_length_dist_top": dict(sorted(run_lengths.items(), reverse=False)[-8:]),
    "removed_family_top": removed_by_family.most_common(8),
    "kept_family_top": kept_by_family.most_common(8),
    "family_diversity": {"raw_distinct": len(kept_by_family)+len(set(removed_by_family)-set(kept_by_family)),
                          "final_distinct": len(kept_by_family)},
}

# pass 2: full-coverage join with v2_2 core + pool plan steps
pool_steps = {}
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pool_steps[r["row_id"]] = len(r["plan"]["steps"])
by_id = {r["i"]: r for r in rows}
tw_list, orig_l, fin_l, plan_l = [], [], [], []
verb_lists = []
for line in open(V22, encoding="utf-8"):
    r = json.loads(line)
    if r["cat"] != "core": continue
    sid = r.get("source_row_id")
    s = by_id.get(sid)
    if not s: continue
    n = len(STEP_RE.findall(r["target"], re.M))
    tw_list.append(len(s["instr"].split())); orig_l.append(len(s["raw"]))
    fin_l.append(len(s["rle"])); plan_l.append(n)
    verb_lists.append(len(set(re.findall(r"[a-z]{4,}", s["instr"].lower()))))

def rank(xs):
    s = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0]*len(xs); i = 0
    while i < len(s):
        j = i
        while j+1 < len(s) and xs[s[j+1]] == xs[s[i]]: j += 1
        a = (i+j)/2 + 1
        for k in range(i, j+1): r[s[k]] = a
        i = j+1
    return r
def spear(a, b):
    ra, rb = rank(a), rank(b); ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x-ma)*(y-mb) for x, y in zip(ra, rb))
    den = (sum((x-ma)**2 for x in ra) * sum((y-mb)**2 for y in rb)) ** 0.5
    return round(num/den, 3)

res["matched_core_rows"] = len(tw_list)
res["correlations"] = {
    "taskwords_x_orig": spear(tw_list, orig_l),
    "taskwords_x_final": spear(tw_list, fin_l),
    "taskwords_x_plan": spear(tw_list, plan_l),
    "taskverbs_x_orig": spear(verb_lists, orig_l),
    "taskverbs_x_plan": spear(verb_lists, plan_l),
    "orig_x_plan": spear(orig_l, plan_l),
}
res["stage_means"] = {"orig": round(st.mean(orig_l),1), "final": round(st.mean(fin_l),1), "plan": round(st.mean(plan_l),1)}

# task-word-quartile conditional means for all three stages
qs = sorted(tw_list)
def qmean(stage):
    out = []
    for qi in range(4):
        lo = qs[int(qi*len(qs)/4)]; hi = qs[int((qi+1)*len(qs)/4)-1]
        sel = [v for t, v in zip(tw_list, stage) if lo <= t <= hi]
        out.append(round(st.mean(sel), 2))
    return out
res["conditional_means_by_task_quartile"] = {"orig": qmean(orig_l), "final": qmean(fin_l), "plan": qmean(plan_l)}

# instruction iteration-language scan
iter_kw = re.compile(r"\b(each|every|per|all)\b", re.I)
n_iter = sum(1 for r in rows if iter_kw.search(r["instr"]))
res["instruction_iteration_language_share"] = round(n_iter/len(rows), 4)

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
