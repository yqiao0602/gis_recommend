#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-B-1 data diagnosis v1 (owner ruling 2026-10-02, CPU-only, no training).

Questions:
  1. W2 dev probes: label(Yes/No) x tier (probe task text -> pool prefix join)
  2. Completion (W2-relevant) training stream: per-tier composition via source_row_id
  3. Actual training token distribution: A+B vs A-only arms, core tokens by tier
  4. TRUNC: builder-truncated core rows - cut position, steps lost, fields lost
Outputs R3_B1_DIAGNOSIS_v1.json.
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
sys.path.insert(0, r"E:/Route2_Migration_20260928/01_REPO/system_redesign")
from transformers import AutoTokenizer

POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
TOKDIR = r"E:/Route2_Migration_20260928/04_DIAG_WORK/tok"
V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
V22A = r"E:/Route2_Migration_20260928/04_DIAG_WORK/../02_DATA_FROZEN/stage1_train_v2_2.jsonl"
V22A_ACTUAL = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3b1_diagnosis/R3_B1_DIAGNOSIS_v1.json"
# NOTE: the A-only dataset lives only on the server; we received no local copy.
# For A-only per-tier token check we rely on its report + the fact every row's
# source_row_id maps to a Tier A pool row (verified server-side at build time).

MAX_LEN = 1024
SEP = '\nWorkflow plan:'
norm = lambda s: re.sub(r"\s+", " ", s).strip()
STEP_RE = re.compile(r"^Step (\d+):", re.M)

tok = AutoTokenizer.from_pretrained(TOKDIR, trust_remote_code=True)
bos = 1 if tok.bos_token_id is not None else 0
eos = 1 if tok.eos_token_id is not None else 0

def token_parts(ex):
    task = tok.encode(ex['task'], add_special_tokens=False)
    sep = tok.encode(ex.get('separator', SEP), add_special_tokens=False)
    context = tok.encode(ex.get('context', ''), add_special_tokens=False)
    target = tok.encode(' ' + ex['target'], add_special_tokens=False)
    return task, sep, context, target

def truncation_info(ex):
    """Mirror builder token_truncation; return (ctx_trunc, tgt_trunc, kept_target_tokens)."""
    task, sep, context, target = token_parts(ex)
    fixed = bos + len(task) + len(sep)
    if fixed >= MAX_LEN:
        return None  # task too long (excluded at build)
    room = MAX_LEN - fixed
    if len(context) + len(target) + eos > room:
        keep_context = max(0, room - eos - min(len(target), max(0, room // 2)))
        context = context[:keep_context]
    target_room = max(0, room - len(context) - eos)
    return len(context) if False else (0, max(0, len(target) - target_room), min(len(target), target_room))

# ---------- pool ----------
pool_by_id = {}
pool_by_prefix = defaultdict(list)
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        r["_n"] = norm(r["instruction"])
        pool_by_id[r["row_id"]] = r
        pool_by_prefix[r["_n"]].append(r)

def join_prefix(text):
    t = norm(text)
    for L in (400, 200, 80, 50):
        for r in pool_by_prefix.get(t[:L], []):
            if t.startswith(r["_n"]):
                return r
    return None

res = {}

# ---------- 1. W2 dev probes: label x tier ----------
probes = [json.loads(l) for l in open(r"E:/Route2_Migration_20260928/02_DATA_FROZEN/gate_dev_probes_v3.jsonl", encoding="utf-8")]
w2 = [p for p in probes if p.get("capability") == "W2"]
w2_join = Counter(); w2_label_tier = defaultdict(Counter); w2_unmatched = 0
w2_len_by_label = defaultdict(list); w2_branch_by_label = defaultdict(list)
for p in w2:
    r = join_prefix(p["prompt"])
    lab = (p.get("gold") or "").strip()
    if r is None:
        w2_unmatched += 1
        continue
    w2_join[r["tier"]] += 1
    w2_label_tier[lab][r["tier"]] += 1
    w2_len_by_label[lab].append(r["features"]["n_steps"])
    w2_branch_by_label[lab].append(r["features"].get("branch_ratio", 0))
res["w2_probe_join"] = {
    "probes": len(w2), "unmatched": w2_unmatched,
    "tier_of_probes": dict(w2_join),
    "label_x_tier": {k: dict(v) for k, v in w2_label_tier.items()},
}
def pctl(xs):
    xs = sorted(xs)
    if not xs: return None
    import math
    k = lambda q: xs[min(len(xs)-1, math.ceil(q*len(xs))-1)]
    return {"p50": k(.5), "p90": k(.9), "mean": round(sum(xs)/len(xs),1)}
res["w2_probe_len_by_label"] = {k: pctl(v) for k, v in w2_len_by_label.items()}
res["w2_probe_branch_by_label"] = {k: round(sum(v)/len(v), 3) for k, v in w2_branch_by_label.items()}

# ---------- 2+3. training streams by tier (A+B v2_2 arm) ----------
def bucket_tier_stats(rows, cat):
    tiers, ints, state_pairs = Counter(), defaultdict(set), defaultdict(set)
    for r in rows:
        if r["cat"] != cat: continue
        pr = pool_by_id.get(r.get("source_row_id"))
        if pr is None: continue
        t = pr["tier"]
        tiers[t] += 1
        if cat == "completion":
            ints[t].add(r["target"].strip())
            state_pairs[t].add((r["task"][:80], r["context"].count("Step ")))
    out = {"tier_counts": dict(tiers)}
    if cat == "completion":
        out["distinct_next_intents_by_tier"] = {t: len(v) for t, v in ints.items()}
        out["distinct_state_pairs_by_tier"] = {t: len(v) for t, v in state_pairs.items()}
    return out

core_rows, comp_rows = [], []
for line in open(V22, encoding="utf-8"):
    r = json.loads(line)
    if r["cat"] == "core": core_rows.append(r)
    elif r["cat"] == "completion": comp_rows.append(r)
res["completion_stream_v22"] = bucket_tier_stats(comp_rows, "completion")

# core effective tokens by tier (builder formula)
tier_tokens, tier_rows = defaultdict(int), Counter()
trunc_rows = []
for r in core_rows:
    pr = pool_by_id.get(r.get("source_row_id"))
    info = truncation_info(r)
    if info is None: continue
    _, tgt_trunc, kept_tgt = info
    t = pr["tier"] if pr else "?"
    # approximate row effective tokens: fixed + context(0 for core) + kept target + eos
    task, sep, context, target = token_parts(r)
    room = MAX_LEN - (bos + len(task) + len(sep))
    keep_ctx = 0
    eff = bos + len(task) + len(sep) + keep_ctx + min(len(target), room - keep_ctx - eos) + eos
    tier_tokens[t] += eff
    tier_rows[t] += 1
    if tgt_trunc > 0:
        trunc_rows.append((r, pr, tgt_trunc, eff))
res["core_token_share_v22"] = {"rows": dict(tier_rows), "effective_tokens": dict(tier_tokens),
                               "share": {t: round(v/sum(tier_tokens.values()), 4) for t, v in tier_tokens.items()}}

# ---------- 4. TRUNC analysis ----------
pos_frac, steps_lost, last_family, lost_export, lost_constraint, lost_branch = [], [], Counter(), 0, 0, 0
n_trunc = 0
for r, pr, tgt_trunc, eff in trunc_rows:
    n_trunc += 1
    # char position of the cut within the target text (kept tokens ≈ chars via decode)
    task, sep, context, target = token_parts(r)
    room = MAX_LEN - (bos + len(task) + len(sep))
    target_room = max(0, room - 0 - eos)
    kept_ids = target[:target_room]
    kept_text = tok.decode(kept_ids)
    full_text = r["target"]
    pos_frac.append(len(kept_text)/max(1, len(full_text)))
    kept_steps = len(STEP_RE.findall(kept_text, re.M))
    full_steps = len(STEP_RE.findall(full_text, re.M))
    lost = full_steps - kept_steps
    steps_lost.append(lost)
    if pr:
        steps = pr["plan"]["steps"]
        lost_steps = steps[kept_steps:]
        if any((s.get("family") == "EXPORT_OUTPUT") for s in lost_steps): lost_export += 1
        if any(s.get("constraints") for s in lost_steps): lost_constraint += 1
        if any(len(s.get("depends_on") or []) > 1 or (s.get("depends_on") and s["depends_on"] != [s["order"]-1]) for s in lost_steps): lost_branch += 1
        if lost_steps: last_family[lost_steps[-1].get("family", "?")] += 1
res["trunc_analysis"] = {
    "truncated_rows": n_trunc,
    "kept_fraction_of_chars": pctl(pos_frac),
    "steps_lost": pctl(steps_lost),
    "lost_export_step_share": round(lost_export/n_trunc, 4),
    "lost_constraint_steps_share": round(lost_constraint/n_trunc, 4),
    "lost_branch_step_rows_share": round(lost_branch/n_trunc, 4),
    "last_lost_family_top": last_family.most_common(6),
}

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
