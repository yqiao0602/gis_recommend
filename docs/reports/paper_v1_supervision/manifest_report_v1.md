# paper_v1 supervision manifest — corrected GEE side (8,283 + 629 = 8,912)

**v2 correction.** The first paper_v1 build mistakenly used the superseded
76,884-row legacy baseline (old step1-8 pipeline) as the GEE side. The user
corrected it: the current official GEE train-only authority is the 8,283-row
Batch12-merged cumulative package. This is the rebuild.

## The GEE file recovery

The 8,283-row package was found intact in the repo root as
`.tmp_gee_cumulative_authority_v8_9_9_batch12_20260811.json` (dated 2026-08-11,
26.8 MB) — the Batch12 merge working file that was never cleaned up and never
moved into `docs/reports`. **SHA256 matches the recorded cumulative-authority
hash exactly** (`30dbfe5cc0ea303fa2ccb5ae220ebf9ea0251388210c547e259eb0b9eb24b5ae`),
so this is the original package, not a regeneration. It has been materialized as
`docs/reports/gee_train_only_authority_v8_9_9_8283/gee_cumulative_train_only_authority_v1.json`
with a hash ledger recording the recovery provenance; the Batch4-12 server
rebuild (option B) was stopped and cleaned after the file was found.

Package verification: 8,283 V4-100 rows (the 8,284th semantic row is the
separately-recorded 155-step length sidecar, not part of this package), all
`granted_train_only_gee_complete_workflow_v1`, all validation/test=false,
production_merge=not_granted, 5,014 distinct source SHAs, zero empty task texts.
Chain provenance: seed47 + batch1 +78 + batch2 +154 + batch3 +288 + batch4 +233
+ batch5 +261 + batch6 +1,206 + batch7 +2,235 + batch8 +3,469 + batch9 +180 +
batch10 +0 (rejected) + batch11 +92 + batch12 +41 = 8,283.

## Corrected manifest numbers

| | total | train | val | test |
|---|---:|---:|---:|---:|
| **all** | **8,912** | 8,817 | 49 | 46 |
| GEE (authoritative) | 8,283 | 8,201 | 41 | 41 |
| QGIS (pool v1) | 629 | 616 | 8 | 5 |
| GEE multi-step in val/test | — | — | 37 | 35 |
| QGIS multi-step in val/test | — | — | 5 | 4 |

- **Source-disjoint verified independently**: 8,797 distinct source identities
  (GEE `sha:workflow_id`, QGIS `source_sha256`), 0/0/0 cross-split overlap.
- **Zero empty task texts** (the 17 empty rows of the legacy baseline are gone
  with it).
- L3 vocabulary: GEE 57 distinct codes, QGIS 56, **shared 25**, QGIS-only 31 —
  a materially larger transfer surface than the legacy baseline's 18.
- Weights: GEE 0.5 × 8,283 (complete-workflow authority weight); QGIS 1.0 × 172
  / 0.8 × 24 / 0.7 × 430 / 0.6 × 3.
- Evidence levels: `gee_complete_workflow_train_only_v8_9_9` × 8,283; QGIS
  GOLD 52 / SILVER 454 / NEW_SILVER_PATTERN 120 / NEW_SILVER_STANDALONE 3.

Both held-out splits now contain real multi-step supervision on both platforms,
so validation measures workflow composition everywhere, not just on QGIS.

## Superseded

The first manifest (77,513 rows built on the legacy 76,884 baseline) is invalid
and has been fully replaced by this build. Its input no longer exists in the
ledger chain: the GEE side of paper_v1 is the 8,283-row authority and nothing
else. rng seed 20260907; both inputs hash-pinned; training rows 0; manifest
only, no checkpoint.
