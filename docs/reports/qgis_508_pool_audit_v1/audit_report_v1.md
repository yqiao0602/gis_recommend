# Existing QGIS training-pool audit: 508 → 52 GOLD / 454 SILVER / 2 REJECT

The user-ordered audit of the existing 508-row QGIS train-only aggregate, run
directly against the pool ledger (no new mining, no rerun of the 47,852 → 875
pipeline). Every check is mechanical and re-verifiable; nothing was sampled.

## The audit table

| Check | Result |
|---|---|
| Input | **508** |
| Source evidence valid (server SHA re-verification) | **508/508** — 0 missing, 0 mismatched, 0 unreadable |
| Span located in source | 453 verified / 55 rows carry no span field (single-op macro rows) |
| L3 codes valid in the 128-token taxonomy | **508/508** — 0 invalid codes |
| L3 token-ID consistency | **508/508** — 0 mismatches |
| Data-flow valid | 486 with explicit edges or single-step; 20 multi-step rows carry no `dependency_edges` but do carry `normalized_dag_key` + `call_graph_key` — dataflow was proven at admission and serialized as a sequence (V4 is a sequence model; `dependency_edges` is not consumed by `TaskConditionedL3DatasetV4`) |
| Workflow valid | as above — reclassified `sequence_serialized_dag_verified` |
| Task text present (≥15 chars) | 508/508, 0 empty, 0 very short |
| QGIS platform (no `ee.*` operators) | 508/508 |
| Duplicates (identical L3 sequence + task text) | **2** |
| Tokenizer (real bert-base-uncased, 128 gate) | **0 rejections**, max 126 tokens |
| V4 (real dataset + weighted CE + backward, 16 batches) | **0 rejections**, max content length 14/100, all losses and gradients finite |

## Verdicts

```text
508 existing QGIS
 ├── GOLD    52   (sample_weight 1.0, zero structural problems)
 ├── SILVER 454   (weight 0.7/0.8/0.6, zero structural problems)
 ├── DEFERRED 0
 └── REJECT   2   (exact L3-sequence + task-text duplicates of rows already in the pool)
```

**The pool is real: 506 structurally clean rows.** The audit's honest caveats,
which do NOT change the verdicts but should be known:

1. **Tier, not new evidence.** GOLD/SILVER here inherit the admission-time
   review tiers (`source_reviewed_gold_pilot`, `source_verified_*`,
   `source_replayed_deterministic_gold`, …). This audit re-verified structure,
   source, taxonomy, dedup, and the data path; it did not redo per-row human
   semantic review — those reviews already exist in the frozen packages each row
   came from (per `aggregate_source_pool`/`source` provenance).
2. **364 of 506 are single-step rows.** The pool's multi-step supervision is 142
   rows (length 2–14). Single-step mass (Raster Calculator 105, Project 35,
   Create Feature Class 28, Add Field 24, Vector Export 21, …) is operator-level
   supervision, not workflow composition.
3. **406 rows share only 55 distinct L3 sequences** — the pool's task-text
   diversity, not its sequence diversity, is what carries the supervision; the 2
   rejects were the only rows where both collapsed simultaneously.
4. The 2 REJECT rows are exact twins of rows already in the pool (identical L3
   sequence and identical task description) — dedup misses at original build
   time, now caught.

## Combined QGIS standing (post-audit)

```text
Audited existing pool:   506 (52 GOLD + 454 SILVER)
API pattern candidates:  120 (tokenizer+V4 passed; pending user consumption decision)
Standalone candidates:     3 (same status)
Proven operators:         56/207 (operator-grounding knowledge)
──
Potential QGIS supervision ceiling: 629 rows if the 120 are admitted
```

## Verification and artifacts

- Server-side source re-verification script over `/home/yll` (508/508 SHA pass);
  span checks for all 453 rows carrying spans.
- Structural audit ledger: `structural_audit_v1.json` (per-row checks, problems).
- Verdict ledger: `audit_verdicts_v1.json` (verdict + token counts + reclassified
  workflow status). Source verification: `source_verification_v1.json`.
- V4 smoke over the 506: real dataset, real tokenizer, 16 batches, finite
  loss/gradients, no checkpoint, no epoch.
- No authority, evaluation split, or checkpoint changed; the 2 REJECT rows are
  flagged for removal in a future package decision, not deleted here.
