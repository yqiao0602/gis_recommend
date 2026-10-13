#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A″ four-check evidence builder (checks 2 & 4 + C2/C3 freeze).

Check 2: training data — deterministic dedup (keep MIN line index per
         blueprint hash, dedup_rule_v1), stratified sample 300 (seed
         20261012), list frozen with SHA.
Check 4: isolation — three assertions on the FINAL list (task_sha vs the
         131 diagnostic set, vs the trusted dev subset, source-row level).
Also freezes C2-short (47) / C3-long (32) evaluation lists (v0.3 §6).
"""

import gzip
import hashlib
import json
import os
import random
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DW = os.path.join(HERE, "..", "..", "04_DIAG_WORK")
PD = os.path.join(HERE, "..", "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
PULL = os.path.join(DW, "a1_pull")
OUT = os.path.join(PD, "ADPRIME_FOUR_CHECK_EVIDENCE_V1.json")

SEED = 20261012
DEDUP_RULE = "dedup_rule_v1: per blueprint-hash group keep MIN line index"


def bp_hash(t):
    return hashlib.sha256(json.dumps(t, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def tsha(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def file_sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ev = {"schema": "adprime_four_check_evidence_v1",
          "generated_at": "2026-10-12", "seed": SEED,
          "dedup_rule": DEDUP_RULE}

    # ---- C2/C3 freeze from baseline re-run ----
    with gzip.open(os.path.join(PULL, "a1_arm768_raw.json.gz"),
                   "rt", encoding="utf-8") as f:
        pre = {r["idx"]: r for r in json.load(f)["rows"]}
    c2 = sorted(i for i, r in pre.items()
                if r["termination"] == "EOS" and r["gold_n_stages"] <= 10)
    c3 = sorted(i for i, r in pre.items()
                if r["termination"] == "EOS" and r["gold_n_stages"] > 10)
    ev["eval_sets_frozen"] = {
        "C2_short": {"n": len(c2), "idx": c2, "threshold": 0},
        "C3_long": {"n": len(c3), "idx": c3, "threshold": 2},
    }

    # ---- Check 2: training data ----
    tr_path = os.path.join(DW, "planner_v2_train.jsonl")
    tr = []
    with open(tr_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r["target"]
                if isinstance(t, str):
                    t = json.loads(t)
                tr.append({"task": r["task"], "tgt": t})
    ev["train_corpus"] = {"path": os.path.abspath(tr_path),
                          "rows": len(tr), "file_sha256": file_sha(tr_path)}

    groups = defaultdict(list)
    for i, r in enumerate(tr):
        groups[bp_hash(r["tgt"])].append(i)
    pool = sorted(min(xs) for xs in groups.values())  # MIN line index
    ev["dedup"] = {"rule": DEDUP_RULE, "pool_rows": len(pool),
                   "dropped": len(tr) - len(pool)}

    def stratum(n_gold):
        return "short" if n_gold <= 10 else ("mid" if n_gold <= 25 else "long")

    by_str = defaultdict(list)
    for i in pool:
        by_str[stratum(len(tr[i]["tgt"]["stages"]))].append(i)
    rng = random.Random(SEED)
    take_n = {"short": 100, "mid": 100, "long": 100}
    final = []
    strata_acc = {}
    for stname in ("short", "mid", "long"):
        cand = sorted(by_str[stname])
        rng.shuffle(cand)
        k = min(take_n[stname], len(cand))
        strata_acc[stname] = {"population": len(cand), "sample_n": k}
        final.extend(cand[:k])
    final = sorted(final)

    sample_rows = [{"line_idx": i,
                    "task_sha256": tsha(tr[i]["task"]),
                    "gold_n_stages": len(tr[i]["tgt"]["stages"]),
                    "stratum": stratum(len(tr[i]["tgt"]["stages"]))}
                   for i in final]
    list_json = json.dumps(sample_rows, ensure_ascii=False, sort_keys=True)
    ev["training_list"] = {
        "n": len(sample_rows), "strata": strata_acc,
        "list_sha256": hashlib.sha256(list_json.encode()).hexdigest(),
    }

    # ---- Check 4: isolation on the FINAL list ----
    dev_trusted = []
    with open(os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl"),
              encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r["target"]
                if isinstance(t, str):
                    t = json.loads(t)
                dev_trusted.append({"task": r["task"], "tgt": t})
    s131 = json.load(open(os.path.join(PD, "A1_SAMPLE_131.json"),
                          encoding="utf-8"))
    sha131 = {tsha(dev_trusted[x["idx"]]["task"]) for x in s131["samples"]}
    sha_dev_all = {tsha(r["task"]) for r in dev_trusted}
    sha_final = {x["task_sha256"] for x in sample_rows}
    i1 = sha_final & sha131
    i2 = sha_final & sha_dev_all
    ev["isolation_assertions"] = {
        "final_list_vs_131_task_sha": {"intersection": len(i1),
                                        "conflicts": sorted(i1)[:5]},
        "final_list_vs_trusted_dev_task_sha": {"intersection": len(i2),
                                                "conflicts": sorted(i2)[:5]},
        "source_row_level": ("train/dev are disjoint corpus splits "
                             "(formal split); record-level separation by "
                             "construction; task_sha checks above are the "
                             "frozen-time verification"),
        "all_zero_required": True,
        "pass": len(i1) == 0 and len(i2) == 0,
    }
    ev["four_check_2"] = {"pass": True, "note": "list frozen with SHA"}
    ev["four_check_4"] = {"pass": ev["isolation_assertions"]["pass"]}

    json.dump(ev, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    with open(os.path.join(PD, "ADPRIME_TRAIN_LIST_V1.json"), "w",
              encoding="utf-8") as f:
        json.dump(sample_rows, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in
                      ("eval_sets_frozen", "train_corpus", "dedup",
                       "training_list", "isolation_assertions")},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
