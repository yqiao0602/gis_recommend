#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 pre-execution verification (owner directive 2026-10-12, item 1):

- idx -> stable ID: add source_row_id (blueprint_v2_gold_v3 join) and
  task_sha256 (task text hash) to every sample row so execution does not
  depend on file line numbers.
- verify: 131 unique idx, zero missing, all within frozen trusted subset,
  strata counts match the frozen account, no duplicate (idx, sid).
- add gold_target_chars per sample for runtime budget-adequacy checking
  (owner note: stage count != token count; verify with actual output).
"""

import hashlib
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")

s = json.load(open(os.path.join(PD, "A1_SAMPLE_131.json"), encoding="utf-8"))
samples = s["samples"]
checks = {}

# 1. uniqueness / completeness
idxs = [x["idx"] for x in samples]
checks["n_samples"] = len(samples)
checks["unique_idx"] = len(set(idxs)) == len(idxs)

dual = json.load(open(os.path.join(PD, "DUAL_TRACK_EVAL_V1.json"),
                      encoding="utf-8"))
excl = {int(k) for k in dual["exclusions"]["rows"]}
checks["all_in_trusted_subset"] = all(i not in excl for i in idxs)

# strata account match
acc = Counter(x["stratum"] for x in samples)
checks["strata_match"] = all(acc[k] == v["sample_n"]
                             for k, v in s["strata_account"].items())

# 2. stable IDs
task2sid = {}
with open(os.path.join(DW, "blueprint_v2_gold_v3.jsonl"),
          encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        task2sid.setdefault(r.get("task"), r.get("source_row_id"))

rows = []
with open(os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl"),
          encoding="utf-8") as f:
    for i, line in enumerate(f):
        if line.strip():
            rows.append(json.loads(line))

missing_sid = 0
for x in samples:
    i = x["idx"]
    task = rows[i]["task"]
    sid = task2sid.get(task)
    x["source_row_id"] = sid
    x["task_sha256"] = hashlib.sha256(
        (task or "").encode("utf-8")).hexdigest()[:16]
    t = rows[i]["target"]
    if isinstance(t, str):
        t = json.loads(t)
    x["gold_target_chars"] = len(json.dumps(
        t, ensure_ascii=False, separators=(",", ":")))
    x["gold_n_stages_frozen"] = len(t["stages"])
    if x["gold_n_stages_frozen"] != x["gold_n_stages"]:
        checks["stage_count_mismatch"] = True
    if sid is None:
        missing_sid += 1
checks["missing_source_row_id"] = missing_sid
checks["stage_count_mismatch"] = checks.get("stage_count_mismatch", False)

sids = [(x["idx"], x["source_row_id"]) for x in samples]
checks["unique_idx_sid"] = len(set(sids)) == len(sids)

s["schema"] = "a1_decode_contrast_sample_v1_1"
s["changelog"] = ("v1.1 pre-execution verification (owner item 1): stable "
                  "IDs added (source_row_id + task_sha256), gold_target_chars "
                  "for runtime budget check, integrity checks recorded. "
                  "Membership/strata unchanged from frozen v1.")
s["pre_exec_verification"] = checks
json.dump(s, open(os.path.join(PD, "A1_SAMPLE_131.json"), "w",
                  encoding="utf-8"), indent=2, ensure_ascii=False)

longest = max(samples, key=lambda x: x["gold_target_chars"])
print(json.dumps({"checks": checks,
                  "n": len(samples),
                  "max_gold_target_chars": longest["gold_target_chars"],
                  "max_row": {"idx": longest["idx"],
                              "stratum": longest["stratum"],
                              "gold_n_stages": longest["gold_n_stages"]},
                  }, indent=2, ensure_ascii=False))
assert all(v is not False and v == 0 or isinstance(v, bool) and v
           for k, v in checks.items()
           if k in ("unique_idx", "all_in_trusted_subset", "strata_match",
                    "unique_idx_sid")) and missing_sid == 0 \
        and not checks["stage_count_mismatch"], checks
print("ALL PRE-EXEC CHECKS PASSED")
return_code = 0
if __name__ == "__main__":
    sys.exit(0)
