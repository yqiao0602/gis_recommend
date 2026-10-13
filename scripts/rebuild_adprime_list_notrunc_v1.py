#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the A″ training list EXCLUDING target-truncated rows (owner
label-reliability principle: only complete targets may serve as termination
labels). Deterministic collator-based filter, CPU-only. Run on mdzhang."""
import json
import random
import sys
from collections import defaultdict

sys.path.insert(0, "/home/qy/system_redesign")
sys.stdout.reconfigure(encoding="utf-8")

from route2_training.plans.stage1_collator import (Stage1PlanCollator,
                                                   TaskTooLongError)
from transformers import AutoTokenizer

SEED = 20261012
MAXLEN = 1024
TAKE = {"short": 100, "mid": 100, "long": 100}

tok = AutoTokenizer.from_pretrained("/home/qy/models/Qwen3.5/Qwen3.5-9B-Base")
if tok.pad_token is None and tok.eos_token is not None:
    tok.pad_token = tok.eos_token
col = Stage1PlanCollator(tok, MAXLEN)

rows = [json.loads(l) for l in open("/home/qy/a1/../planner_v2_train.jsonl",
                                    encoding="utf-8") if l.strip()]
import hashlib


def bp_hash(t):
    return hashlib.sha256(json.dumps(t, sort_keys=True,
                          ensure_ascii=False).encode()).hexdigest()


groups = defaultdict(list)
for i, r in enumerate(rows):
    groups[bp_hash(r["target"] if not isinstance(r["target"], str)
                   else json.loads(r["target"]))].append(i)
pool = sorted(min(xs) for xs in groups.values())

kept, n_tgt_trunc = [], 0
for i in pool:
    r = rows[i]
    try:
        e = col.encode_example(r)
    except TaskTooLongError:
        continue
    if e["target_truncated_tokens"] > 0:
        n_tgt_trunc += 1
        continue
    kept.append(i)
print(f"pool 14008 -> target-complete pool {len(kept)} "
      f"(excluded target-truncated: {n_tgt_trunc})")


def stratum(n):
    return "short" if n <= 10 else ("mid" if n <= 25 else "long")


tgt_stages = []
for i in kept:
    t = rows[i]["target"]
    if isinstance(t, str):
        t = json.loads(t)
    tgt_stages.append(len(t["stages"]))

by = defaultdict(list)
for i, n in zip(kept, tgt_stages):
    by[stratum(n)].append(i)
rng = random.Random(SEED)
final = []
acc = {}
for st in ("short", "mid", "long"):
    cand = sorted(by[st])
    rng.shuffle(cand)
    k = min(TAKE[st], len(cand))
    acc[st] = {"population": len(cand), "sample_n": k}
    final.extend(cand[:k])
final = sorted(final)


def tsha(s):
    import hashlib
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


out_rows = [{"line_idx": i, "task_sha256": tsha(rows[i]["task"]),
             "gold_n_stages": tgt_stages[kept.index(i)],
             "stratum": stratum(tgt_stages[kept.index(i)])}
            for i in final]
lst = json.dumps(out_rows, ensure_ascii=False, sort_keys=True)
print("final n =", len(out_rows), "| strata =", json.dumps(acc))
print("list_sha256 =", hashlib.sha256(lst.encode()).hexdigest())

with open("/home/qy/a1/adprime_train_v1.jsonl", "w",
          encoding="utf-8") as f:
    for i in final:
        f.write(json.dumps(rows[i], ensure_ascii=False) + "\n")
json.dump(out_rows, open("/home/qy/a1/ADPRIME_TRAIN_LIST_V2.json", "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)

# isolation re-check on the new list
dev = [json.loads(l) for l in open(
    "/home/qy/a1/planner_v2_dev_fix1_loopinv.jsonl", encoding="utf-8")
    if l.strip()]
s131 = json.load(open("/home/qy/a1/A1_SAMPLE_131.json", encoding="utf-8"))
sha131 = {tsha(dev[x["idx"]]["task"]) for x in s131["samples"]}
sha_dev = {tsha(r["task"]) for r in dev}
sha_fin = {x["task_sha256"] for x in out_rows}
print("isolation: vs131 =", len(sha_fin & sha131),
      "| vs_trusted_dev =", len(sha_fin & sha_dev))
