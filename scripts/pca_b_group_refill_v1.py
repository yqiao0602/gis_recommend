#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Phase 1 — B-group refill screening (PCA_PROTOCOL_V1_1 §3).

From the 82 dev-120 rows not yet reviewed (120 - 30 candidates - 8 op-ID
rejects), rank by a construct-validity heuristic and emit the top 10 for
owner review. OWNER DECISION REQUIRED before any refill row enters B-group.

Heuristic (auto-scoring only; never auto-admits):
  - workflow-narration density (negative): "the script", "It <verb>",
    sequencing connectives (first/then/next/finally/after), process verbs
    (performs/computes/calculates/extracts/converts/creates/applies/exports)
    per 100 words  -> higher = more likely a workflow description, not a task
  - utility-task penalty: download/export/package/kmz/postgis/database/
    upload/convert markers (owner replaced this whole category)
  - mild preference: chain length 2-6, shorter text
"""
import json, re
from collections import Counter

DEV = "docs/reports/v2a_manifest/v2a_A_dev.jsonl"
CAND = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_candidates_v1.json"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_refill_v1.json"

SEQ = ["first", "then", "next", "finally", "after that", "subsequently", "afterwards"]
PROC = ["performs", "computes", "calculates", "extracts", "converts", "creates",
        "applies", "generates", "processes", "iterates", "loops", "writes", "saves"]
UTIL = ["download", "export", "package", "kmz", "postgis", "postgresql",
        "database", "upload", "zip", "unzip", "file name", "directory"]

def score(text, chain_len):
    low = text.lower()
    words = max(len(low.split()), 1)
    n_script = low.count("the script") + low.count("this script")
    n_seq = sum(low.count(s) for s in SEQ)
    n_proc = sum(low.count(" " + p) for p in PROC)
    n_util = sum(1 for u in UTIL if u in low)
    narr_density = 100 * (n_script + n_seq + n_proc) / words
    util_pen = 3.0 * n_util
    len_pen = 0.15 * max(0, chain_len - 6)
    short_bonus = 0.3 if words < 90 else 0.0
    return round(narr_density + util_pen + len_pen - short_bonus, 2)

def main():
    dev = {json.loads(l)["wid"]: json.loads(l) for l in open(DEV, encoding="utf-8")}
    d = json.load(open(CAND, encoding="utf-8"))
    used = {c["wid"] for c in d["primary"] + d["reserve"] + d["rejected_by_opid"]}
    rows = []
    for wid, r in dev.items():
        if wid in used:
            continue
        tt = r["task_text"]
        s = score(tt, len(r["processes"]))
        low = tt.lower()
        flags = {
            "seq_hits": [w for w in SEQ if w in low],
            "util_hits": [u for u in UTIL if u in low],
            "mentions_custom_algorithm": "custom qgis algorithm" in low or "plugin" in low,
        }
        rows.append({"wid": wid, "taskType": r["taskType"],
                     "chain_len": len(r["processes"]), "heuristic_score": s,
                     "n_words": len(tt.split()), "flags": flags,
                     "task_text": tt})
    rows.sort(key=lambda r: r["heuristic_score"])
    out = {"_meta": {
              "protocol": "PCA_PROTOCOL_V1_1_B_GROUP_RESTATEMENT §3",
              "note": "auto-ranking ONLY; owner must review and admit rows",
              "n_reviewed_pool": len(rows),
              "need": ">=1 row to restore B to 20 (19 available after owner rulings)",
              },
           "top10_for_owner_review": rows[:10],
           "remainder_sorted": [{"wid": r["wid"], "score": r["heuristic_score"]}
                                for r in rows[10:]]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("refill pool:", len(rows))
    for r in rows[:10]:
        print(f"  {r['wid']} score={r['heuristic_score']:6.2f} len={r['chain_len']:2d} "
              f"{r['taskType'][:24]:24s} util={r['flags']['util_hits'][:2]}")
    print("saved:", OUT)

if __name__ == "__main__":
    main()
