#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-B-TRUNC clean ablation v1: build dataset = frozen v2_2 minus the 1,766
build-time truncated core rows. Single variable: exclusion of those rows.
Everything else preserved verbatim (rows, order, aux streams untouched).
Then CPU audit per owner checklist. Output: stage1_train_v2_2_notrunc.jsonl
+ audit JSON.
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"E:/Route2_Migration_20260928/01_REPO/system_redesign")
from transformers import AutoTokenizer

TOKDIR = r"E:/Route2_Migration_20260928/04_DIAG_WORK/tok"
V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
OUT = r"E:/Route2_Migration_20260928/04_DIAG_WORK/stage1_train_v2_2_notrunc.jsonl"
OUTJ = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3btrunc_diagnosis/R3_BTRUNC_AUDIT_v1.json"

MAX_LEN = 1024
SEP = '\nWorkflow plan:'
tok = AutoTokenizer.from_pretrained(TOKDIR, trust_remote_code=True)
bos = 1 if tok.bos_token_id is not None else 0
eos = 1 if tok.eos_token_id is not None else 0
STEP_RE = re.compile(r"^Step (\d+):", re.M)

pool_by_id = {}
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pool_by_id[r["row_id"]] = r

def eff_tokens(r):
    task = tok.encode(r['task'], add_special_tokens=False)
    sep = tok.encode(r.get('separator', SEP), add_special_tokens=False)
    context = tok.encode(r.get('context', ''), add_special_tokens=False)
    target = tok.encode(' ' + r['target'], add_special_tokens=False)
    fixed = bos + len(task) + len(sep)
    if fixed >= MAX_LEN:
        return None
    room = MAX_LEN - fixed
    if len(context) + len(target) + eos > room:
        keep_context = max(0, room - eos - min(len(target), max(0, room // 2)))
        context = context[:keep_context]
    target_room = max(0, room - len(context) - eos)
    kept = target[:target_room]
    return {"eff": fixed + len(context) + len(kept) + eos,
            "ctx_trunc": 0, "tgt_trunc": len(target) - len(kept)}

rows = [json.loads(l) for l in open(V22, encoding="utf-8")]
kept_lines, removed = [], []
cat_before, cat_after = Counter(), Counter()
tok_before, tok_after = Counter(), Counter()
steps_before, steps_after = [], []
tier_removed = Counter()
for r in rows:
    cat_before[r["cat"]] += 1
    info = eff_tokens(r)
    eff = info["eff"] if info else 0
    tok_before[r["cat"]] += eff
    is_trunc_core = (r["cat"] == "core" and info and info["tgt_trunc"] > 0)
    if is_trunc_core:
        removed.append(r)
        pr = pool_by_id.get(r.get("source_row_id"))
        tier_removed[pr["tier"] if pr else "?"] += 1
        continue
    kept_lines.append(json.dumps(r, ensure_ascii=False))
    cat_after[r["cat"]] += 1
    tok_after[r["cat"]] += eff
    if r["cat"] == "core":
        steps_after.append(len(STEP_RE.findall(r["target"], re.M)))
    if r["cat"] == "core" or True:
        pass
# steps before for core (incl removed)
for r in rows:
    if r["cat"] == "core":
        steps_before.append(len(STEP_RE.findall(r["target"], re.M)))

Path(OUT).write_text("\n".join(kept_lines) + "\n", encoding="utf-8")

def pctl(xs):
    xs = sorted(xs)
    if not xs: return None
    import math
    k = lambda q: xs[min(len(xs)-1, math.ceil(q*len(xs))-1)]
    return {"p50": k(.5), "p90": k(.9), "p99": k(.99), "max": xs[-1], "mean": round(sum(xs)/len(xs),1)}

import bisect
sb = sorted(steps_before); sa = sorted(steps_after)
def cdf(xs, x): return round(bisect.bisect_right(xs, x)/len(xs), 4)
w3_points = [5, 10, 15, 20, 30, 40, 50, 58, 75, 83]

total_b, total_a = sum(tok_before.values()), sum(tok_after.values())
audit = {
    "removed_rows": len(removed),
    "removed_tier": dict(tier_removed),
    "rows_before": dict(cat_before),
    "rows_after": dict(cat_after),
    "eff_tokens_before": dict(tok_before),
    "eff_tokens_after": dict(tok_after),
    "token_share_before": {k: round(v/total_b, 4) for k, v in tok_before.items()},
    "token_share_after": {k: round(v/total_a, 4) for k, v in tok_after.items()},
    "total_tokens_before": total_b,
    "total_tokens_after": total_a,
    "core_steps_before": pctl(steps_before),
    "core_steps_after": pctl(steps_after),
    "train_cdf_at_w3_points": {
        str(x): {"before": cdf(sb, x), "after": cdf(sa, x)} for x in w3_points},
    "remaining_build_truncated_core_rows": 0,
    "note": "auxiliary streams (completion/reconstruction/w4) untouched; their own "
            "build-time truncation exists but is out of scope for this single-variable edit",
}
json.dump(audit, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(audit, ensure_ascii=False, indent=1))
