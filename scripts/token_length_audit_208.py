#!/usr/bin/env python3
"""Stage-1 addendum: real-tokenizer length audit for the 208 paired rows.
Old target (literal expansion, planner_v2_train) vs new target (folded spec).
Also reconciles the 116 (folded stage entries) vs 516 (raw expanded ops)
unit discrepancy, and reports training/inference budget thresholds."""
import json, statistics as st
from collections import Counter
from transformers import AutoTokenizer

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
TRAIN = "/home/qy/planner_v2_train.jsonl"
REBUILD = "/home/qy/rebuild_report_v2.json"
OUT = "/home/qy/token_length_audit_208.json"

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

d = json.load(open(REBUILD, encoding="utf-8"))
rebuilt = d["rows"]["rebuilt"]
train_by = {}
for line in open(TRAIN, encoding="utf-8"):
    t = json.loads(line)
    train_by[t["task"]] = t

def toks(s):
    return len(tok(s, add_special_tokens=False)["input_ids"])

rows, missing = [], []
for rec in rebuilt:
    t = train_by.get(rec["task"])
    if t is None:
        missing.append(rec["source_row_id"]); continue
    o = json.loads(t["target"]) if isinstance(t["target"], str) else t["target"]
    old_s = json.dumps(o.get("stages", []), ensure_ascii=False)
    new_payload = {"stages": rec["target_json"]["stages"],
                   "repetition_groups": rec["target_json"]["repetition_groups"]}
    new_s = json.dumps(new_payload, ensure_ascii=False)
    task = rec["task"]
    sep = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."
    prompt_n = toks(task + sep)
    rows.append({
        "source_row_id": rec["source_row_id"],
        "old_stages_n": len(o.get("stages", [])),
        "new_stages_n": len(rec["target_json"]["stages"]),
        "old_stage_json_tokens": toks(old_s),
        "new_stage_json_tokens": toks(new_s),
        "prompt_tokens": prompt_n,
        "old_prompt_plus_target": prompt_n + toks(old_s),
        "new_prompt_plus_target": prompt_n + toks(new_s),
        "old_target_tokens_only": toks(old_s),
    })

def dist(key):
    vals = sorted(r[key] for r in rows)
    n = len(vals)
    def q(p): return vals[min(n - 1, int(p * n))]
    return {"n": n, "p50": q(.5), "p90": q(.9), "p95": q(.95),
            "p99": q(.99), "max": vals[-1]}

summary = {
    "rows_paired": len(rows), "rows_missing_in_train": len(missing),
    "old_stage_json_tokens": dist("old_stage_json_tokens"),
    "new_stage_json_tokens": dist("new_stage_json_tokens"),
    "prompt_tokens": dist("prompt_tokens"),
    "old_prompt_plus_target": dist("old_prompt_plus_target"),
    "new_prompt_plus_target": dist("new_prompt_plus_target"),
    "budget_counts": {
        "train_max_len_1024_old": sum(1 for r in rows if r["old_prompt_plus_target"] > 1024),
        "train_max_len_1024_new": sum(1 for r in rows if r["new_prompt_plus_target"] > 1024),
        "gen_budget_384_old_target_only": sum(1 for r in rows if r["old_target_tokens_only"] > 384),
        "gen_budget_384_new_target_only": sum(1 for r in rows if r["new_stage_json_tokens"] > 384),
        "gen_budget_768_new_target_only": sum(1 for r in rows if r["new_stage_json_tokens"] > 768),
    },
}
# unit reconciliation for the max-stage discrepancy
unit_recon = {
    "question": "old P50/P90/max=25/68/116 vs earlier 28/76/516",
    "resolution": "different units and scopes: 116 = folded literal STAGE entries "
                  "in old gold (max over the 208 paired rows, sid with 116 stages "
                  "is the largest folded old gold); 516 = RAW EXPANDED OPS of the "
                  "largest raw chain (sid 104512, now 97 folded stages in new gold). "
                  "516 raw ops fold to 97 stages; both numbers are real, units differ.",
    "largest_old_gold_116_sid": max(rows, key=lambda r: r["old_stages_n"])["source_row_id"],
    "largest_old_gold_116_stages": max(r["old_stages_n"] for r in rows),
    "largest_raw_ops_row": {"sid": 104512, "raw_ops": 516, "new_stages": 97},
}
summary["unit_reconciliation"] = unit_recon
json.dump({"summary": summary, "rows": rows}, open(OUT, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
