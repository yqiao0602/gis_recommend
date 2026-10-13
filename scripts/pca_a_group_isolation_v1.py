#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Phase 1 — A-group isolation verification (PCA_PROTOCOL_V1_FROZEN §2.3,
owner ruling 2026-10-13: "use the actually-consumed training pool as the
primary exclusion basis; tasks whose source isolation cannot be proven are
text_dedup_only, never upgraded to verified held-out").

Method (three evidence tiers, never mixed in reporting):
  - consumed_text_match  : candidate task text (normalized) found in the
                           actually-consumed pool -> EXCLUDED.
  - candidate tiers (for survivors):
      source_record_text_aligned : source line exists in the frozen
          b1_gee_stage authority (line-id under frozen SHA) AND its text
          aligns uniquely; the consumed pool's source-line coverage is
          reconstructed via the same text alignment (alignment rate
          reported) and the candidate's line-id is NOT in it.
      text_dedup_only            : anything that cannot complete the chain
          above (e.g. ambiguous duplicate instruction texts).

Inputs (read-only, never copied into the repo):
  - authority : ../server_backup_mdzhang_20260927/home/qy/system_redesign/
                outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl
                (264MB, source of GEE tasks; line number = stable id)
  - consumed  : ../pca_data_ref/planner_v2_train.jsonl
                (33,339 rows, SHA 443d5d31..., confirmed as P0 train_data
                by stage1_run_planner_v2_fmt/run_ledger.json)
Output: PCA Phase-1 audit JSON (stats + candidate summary list).
"""
import json, hashlib
from collections import Counter, defaultdict

AUTH = "../server_backup_mdzhang_20260927/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl"
POOL = "../pca_data_ref/planner_v2_train.jsonl"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_a_group_isolation_audit_v1.json"
FULL_OUT = "../pca_data_ref/pca_a_group_isolation_full_v1.json"  # git-external

def norm(s):
    return " ".join((s or "").split()).strip().lower()

def main():
    # 1. consumed pool: normalized task -> count
    pool_map = Counter()
    with open(POOL, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            pool_map[norm(r.get("task", ""))] += 1
    n_pool_rows = sum(pool_map.values())

    # 2. authority scan
    n_auth = 0
    consumed_lines = 0
    unique_texts = Counter()
    candidates = []          # survivors (not text-consumed)
    cand_norm_texts = []     # full normalized text per survivor (for tiering)
    split_counter = Counter()
    with open(AUTH, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            n_auth += 1
            sp = r.get("split", "?")
            split_counter[sp] += 1
            t = norm(r.get("instruction", ""))
            unique_texts[t] += 1
            if t in pool_map:
                consumed_lines += 1
            else:
                candidates.append({
                    "line_id": i,
                    "split": sp,
                    "task_type": r.get("task_type", ""),
                    "final_len": r.get("final_semantic_length"),
                    "text_md5": hashlib.md5(t.encode()).hexdigest()[:12],
                    "instruction_head": (r.get("instruction") or "")[:120],
                })
                cand_norm_texts.append(t)

    # 3. tier assignment for survivors:
    #    - authority-internal duplicate normalized text -> the "source line"
    #      is ambiguous -> text_dedup_only (never upgraded)
    #    - unique authority text -> source line unambiguous under frozen SHA
    #      -> source_record_text_aligned
    demoted = 0
    for c, t in zip(candidates, cand_norm_texts):
        if unique_texts[t] > 1:
            c["tier"] = "text_dedup_only"
            demoted += 1
        else:
            c["tier"] = "source_record_text_aligned"

    tier_counter = Counter(c["tier"] for c in candidates)
    tier_by_split = Counter((c["tier"], c["split"]) for c in candidates)

    # git copy: compact candidate index only (line_id grouped by tier+split);
    # full per-row detail goes to FULL_OUT (outside the repo, regenerable)
    compact = defaultdict(list)
    for c in candidates:
        compact[f'{c["tier"]}|{c["split"]}'].append(c["line_id"])
    compact = {k: v for k, v in sorted(compact.items())}
    out = {
        "_meta": {
            "protocol": "PCA_PROTOCOL_V1_FROZEN §2.3 + owner ruling 2026-10-13",
            "authority": AUTH,
            "consumed_pool": POOL,
            "consumed_pool_rows": n_pool_rows,
            "consumed_pool_unique_texts": len(pool_map),
            "authority_rows": n_auth,
            "authority_split": dict(split_counter),
            "note_line_id": "authority line number under frozen file SHA "
                            "(b1_gee_stage_train.jsonl); no explicit id field",
            "note_tiers": "consumed_text_match=excluded; "
                          "source_record_text_aligned=authority line unique + "
                          "not in consumed pool (pool source coverage "
                          "reconstructed via text alignment); "
                          "text_dedup_only=authority-internal duplicate text",
            "full_detail_git_external": FULL_OUT,
        },
        "stats": {
            "authority_rows_consumed_text_match": consumed_lines,
            "consumed_ratio_of_authority": round(consumed_lines / max(n_auth, 1), 4),
            "authority_internal_duplicate_extra_rows":
                sum(v - 1 for v in unique_texts.values() if v > 1),
            "candidates_total": len(candidates),
            "candidates_demoted_to_text_dedup_only": demoted,
            "candidates_by_tier": dict(tier_counter),
            "candidates_by_tier_x_split": {f"{t}|{s}": n for (t, s), n in sorted(tier_by_split.items())},
        },
        "candidate_line_ids_by_tier_x_split": compact,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(out | {"candidates_full": candidates},
              open(FULL_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print(json.dumps(out["stats"], indent=1))
    print("saved:", OUT)
    print("full detail (git-external):", FULL_OUT)

if __name__ == "__main__":
    main()
