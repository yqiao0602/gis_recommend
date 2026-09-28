# API semantic standalone consumption: 137 → 3

The yield-consumption pipeline over the 137 adjudicated standalone rows, executed
with no new source parsing and no pool widening. Every rejection is attributed to
a stage; the ledger (`standalone_collapse_v1.jsonl`) carries per-row reasons.

## The number

```text
137 standalone
 ├─  1  dedup_existing   (source SHA already in the 508 pool)
 ├─ 66  dedup_internal   (identical L3+method+literal-shape payload already kept)
 ├─ 67  no_independent_task_context
 │      ├─ 55  module_level_snippet_no_task_owner
 │      └─ 12  no_observable_task_semantics
 └─   3  kept
        ↓ tokenizer gate: real bert-base-uncased, max 35 tokens (≤128, no truncation)
        ↓ V4 gate: real TaskConditionedL3DatasetV4 + weighted CE + backward,
           loss and gradients finite, sample_weight emitted, no checkpoint, no epoch
        = 3 training candidates
```

**137 → 3.** Kept rows: Reproject 1, Intersect 1, Simplify 1.

| Kept row | L3 | Why it survived |
|---|---|---|
| `0c17d27e…` `ExportSettings.wgs84Center` | L3_01_10_01 | class+method scope names a user-visible operation (export center in WGS84) |
| `73d24c44…` `AddMultipleTreesTool.get_line_segment` | L3_02_02_01 | domain-named tool class doing a real intersect |
| `b7eaaefd…` `PencilMapTool._build_geometry` | L3_02_05_01 | domain-named tool class with map-unit-driven simplify |

All three survived on `domain_named_scope` — none on literal operands.

## Per-L3 retention (the requested reading)

| L3 | standalone | kept | retention |
|---|---:|---:|---:|
| Reproject (65) | 65 | 1 | 1.5% |
| Feature to Point (25) | 25 | 0 | 0% |
| Buffer (21) | 21 | 0 | 0% |
| Intersect (7) | 7 | 1 | 14% |
| Simplify (8) | 8 | 1 | 12.5% |
| Smooth (5) | 5 | 0 | 0% |
| Collect (4) | 4 | 0 | 0% |
| Repair / Min Bounding (2) | 2 | 0 | 0% |

## What actually killed the yield

1. **Homogeneity, not dedup rules (66).** 99 of the 137 rows share an identical
   `call_text` with at least one other row; 39 distinct (L3, method, function,
   scope) signatures cover all 137. The Reproject mass is dozens of scripts doing
   `transform(point)`/`crs_tras.transform(pt)` with a runtime-bound argument —
   the same payload shape, so one representative carries the information.
2. **No task owner (67).** 55 are module-level snippets — geometry math executed
   at import time with no function, no caller, no user task. Another 12 are
   helper functions with no observable task semantics (`getFlagGeometry`,
   `helper`). The user's prediction that stage ③ would be the biggest compressor
   was correct: 67 rows removed there.
3. The **1 existing-pool SHA hit** shows near-total disjointness from the 508
   pool at source level — the collapse is internal homogeneity, not overlap.

## Interpretation (the KPI question this was designed to answer)

> The API semantic **unit** lane contributes operator-semantic knowledge
> (998 qualified action bindings, 861 of them grounding-grade), **not workflow
> training data**. Its standalone training yield is 3 rows — and correctly so:
> a single geometry method call with no task context is not a user workflow.

This is the honest ceiling for *single-call* units under the locked principle
that different sources must not be dressed up as different tasks. The next yield
increment for the API side must come from **multi-step structure** —
`api_pattern` (4,880 rows, ≥2 semantic calls) and the workflow lanes — where a
task owner and a chain both exist.

## Artifacts and verification

- `standalone_collapse_v1.jsonl` — all 137 rows with per-stage outcomes.
- `training_candidates_v1.json` — the 3 candidates with task text built only
  from source facts (class.function scope + L3 action), tokenizer counts, and
  V4 smoke evidence; `training_admission = not_granted_pending_user_consumption_decision`.
- `summary_v1.json`, `hash_ledger_v1.json` (pins adjudicated/phase-1/508 inputs),
  `hash_ledger_supplement_v1.json` (candidates + script).
- Focused tests 10/10; `compileall` clean.
- V4 smoke: real `TaskConditionedL3DatasetV4` with real `bert-base-uncased`;
  batch shapes `[3,100]`/`[3,128]`; weighted CE loss finite; gradients finite;
  no checkpoint written, no epoch run.

The 3 candidates are **not** training rows: consumption into any training
package requires the user's explicit decision, and the existing 508-pool
cross-dedup has already been applied (1 SHA overlap only).
