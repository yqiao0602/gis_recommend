# qgis_planner_v1 Benchmark — v0.1 Audit Errata & Freeze State Record

Date: 2026-09-10
Scope: corrections to the 2026-09-09/10 v0.1 audit report, plus the definitive
v0.1 freeze state record. No sealed artifact was opened or regenerated in
producing this document.

## Part I — Errata

The v0.1 audit (8-item table) was directionally correct; four factual claims
are corrected here. None of them overturn the `NEED REVISION → v0.2`
verdict; two of them strengthen the "repair, not rebuild" rationale.

### Errata 1 — Gate 3 family quota status

- Audit claim: "family quota 0/50 全部未达标"
- Corrected: **6/50 families meet quota_4; 2/50 meet quota_8**
  - quota_4 met: L3_01_10_01 (Project/Reproject), L3_02_01_01 (Buffer),
    L3_02_02_06 (Clip), L3_02_04_01 (Spatial Join), L3_02_06_02 (Extract by
    Attribute), L3_03_05_02 (Reproject)
  - quota_8 met: L3_01_10_01, L3_02_02_06
- Source: `authority/candidate_supply_summary.json` → `family_supply[]`
- Impact: the supply pipeline demonstrably can produce quota-eligible
  candidates; the shortage is coverage, not capability. Gate 3 still fails
  overall (44/50 families below quota_4; `gate_status:
  failed_insufficient_candidate_supply`; `family_roster_status:
  not_frozen`).

### Errata 2 — Dev ↔ Final text overlap

- Audit claim: "dev↔final 之间 ≥3 shared 6-gram 也是 0"
- Corrected: **shared 6-grams = 3**; exact task-text overlap = 0
  - All three are connective boilerplate, not task semantics:
    `to the target coordinate system, then` ·
    `vector datasets into one layer, then` ·
    `into the analysis coordinate system, then`
- Source: measured over `releases/v0.1-development-40/tasks.jsonl` and
  `releases/v0.1-final-core-120/tasks.jsonl`, lowercased whitespace tokens,
  n = 6
- Impact: none on independence; the commit-record claim ("zero task-text
  overlap") holds under exact match. Future reports should state:
  "Exact text overlap = 0; 6-gram overlap = 3, human-verified connective
  boilerplate, not semantic near-duplication."

### Errata 3 — Scorer size

- Audit claim: "scorer 517 行"
- Corrected: **469 lines** (`scripts/score_qgis_planner_benchmark_v01.py`)
- Impact: none (independence from the package confirmed: stdlib-only
  imports; 15 tests in
  `tests/test_score_qgis_planner_benchmark_v01.py` — both audit claims
  verified correct).

### Errata 4 — Dev-40 operator concentration

- Audit claim: "qgis:advancedpythonfieldcalculator 占 35/80 进程位" (43.8%)
- Corrected: **35/100 process slots (35.0%)** — 40 rows × variable chain
  length = 100 total operator slots, not 80
- Impact: concentration concern stands but is ~9 points weaker than
  reported. Dev-40 operator diversity (12 distinct) is unaffected.

### Audit claims verified correct (no change)

- dev-40: 8 canonical DAGs × 5 variants; 12 distinct operators; all-linear
  topology (branching = 0, merge = 0); row-level length 1×5 / 2–3×30 / 7+×5
- final queue: 52 distinct DAGs; lengths 1 / 32 / 12 / 7; linear 30 /
  multi_input_merge 22; modality vector 34 / mixed 13 / raster 5
- Gate 3: 149 candidates → 52 DAGs; six `failure_reasons`; raster
  minimum unmet
- final vs paper_v1 training text: exact overlap 0, 6-gram overlap 0
  (8,912 training rows)
- stable101 ⊆ taxonomy_128: intersection 101, stable101-only 0 (27
  128-only)
- capability matrix admits 122 operators; catalog holds 1,291
- 120 primary + 30 blind secondary reviews (final); scorer stdlib-only
- commit 693ce17 rejected step-number templates for exposing the graph
  answer
- modality/near-recall ratios: directionally confirmed (digit variance
  across keyword scopes: raster 14–19/120; operator-explicit 84–89/120)

## Part II — v0.1 Freeze State Record (definitive)

### Git state

| Item | Value |
|---|---|
| Repository | git@github.com:yqiao0602/gis_recommend.git |
| Branch | `qgis-benchmark-semantic-sidecar` (worktree: `C:\Users\qiaoyun\.config\superpowers\worktrees\system_redesign\qgis-benchmark-semantic-sidecar`) |
| Freeze commits | a5ef254 (dev-40) → 693ce17 (final-120, sealed 2026-07-31T10:39:16Z) → 358bdea (freeze contract) → **1857eca (evidence chain committed)** |
| Merge state | Branch is ahead of `main` by 12 benchmark commits; main has zero benchmark-only commits; merge-base `de591c92`. **`releases/` is NOT in main yet.** |

### Hash-bound artifacts (all in `benchmarks/qgis_planner_v1/`)

| Artifact | SHA-256 (first 12) | Tracked |
|---|---|---|
| Freeze manifest | d14bd6802200 | ✅ 358bdea |
| Final gold (sealed) | 787a9ffc6cdb | ✅ 693ce17 |
| Final authority sidecar (sealed) | 54b74be5b423 | ✅ 693ce17 |
| Final reviews (sealed) | 0866c593bdf9 | ✅ 693ce17 |
| Final tasks | 1a2f0d239f37 | ✅ 693ce17 |
| Refusal gold (sealed) | ad7712820452 | ✅ a933042 |
| Refusal tasks | acba74b73be6 | ✅ a933042 |
| Dev tasks / gold | 961c61d353b2 / 838919eb48ba | ✅ a5ef254 |
| stable101_taxonomy | 9e7f871f0222 | ✅ |
| qgis_catalog (1,291) | a0b2426205b5 | ✅ |
| qgis_operator_l3_mapping | 5c4d50361aff | ✅ |
| capability_matrix (122 admitted) | a399136bebb3 | ✅ |
| v01_dag_review_queue | 5014ee5ff807 | ✅ |
| Scorer | 5c07c58c9478 | ✅ |
| **source_exclusion_ledger** | b6202e4b0d43 | ✅ **1857eca (LFS; 104.7 MB / 106,562 rows)** |
| **routing_manifest (routing_v6)** | 1c098a41bbd4 | ✅ **1857eca** |
| **l3_gated_manifest (stable106)** | d71603719017 | ✅ **1857eca** |

Before commit 1857eca the last three rows were untracked working-copy
files: the freeze's hash claims could not be reproduced from git alone.
All three were verified byte-identical to the hashes bound in
`candidate_supply_summary.json` and
`source_exclusion_ledger_manifest_v1.json` before commit.

### Known divergences (deliberately left in place)

- The main workspace carries **uncommitted local edits** to
  `expert_proposals_v1.jsonl`, `expert_proposal_summary_v1.json`,
  `expert_proposal_hash_ledger_v1.json` (expert_proposal_reviews_v1.jsonl
  identical). These edits lack the `semantic_review_*` fields present in
  the worktree's committed version — i.e. the worktree version is the
  freeze-bound authoritative one (`expert_proposals_v1.jsonl` hash
  `eddc0052…`). Main's uncommitted edits are a stale parallel state and
  were **not** synced or discarded here; merging the branch into main will
  surface them as a conflict to resolve deliberately.

### v0.2 supply-repair priority list (agreed 2026-09-10)

- P0 family supply (44/50 below quota_4) · raster · 1-step ·
  branching/multi-output
- P1 dev canonical DAG diversity (8 → 30–40) · 4–6 / 7+ coverage ·
  task_style labels (operator_explicit / planning_oriented) as a
  reporting dimension, not a content change
- P2 remaining details

### Standing rules

- Do not open sealed final/refusal gold before final-route prediction
  hashes are locked.
- v0.1 corrections (including this errata) never regenerate sealed gold;
  benchmark fixes require a new version (v0.2).
