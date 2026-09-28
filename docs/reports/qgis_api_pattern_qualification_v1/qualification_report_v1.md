# API pattern L3 qualification: 875 → 142 (frozen bindings + Predicate Policy v1)

Pattern-lane qualification over the 875 unique chain signatures, run with the
**frozen** phase-2 binding adjudication (`human_binding_review_2026_09_04`, reused
unchanged — entering a multi-step chain upgrades nothing) and the user-approved
**Predicate/Metric Step Policy v1**: a predicate step enters the workflow sequence
only when its result provably controls a later transform (it is an operand of an
`if`/`while` whose branch executes another chain call); measurements never take a
sequence slot; both remain recorded as structural evidence on the row. Predicates
reuse only already-defined taxonomy tokens (`intersects`/`contains` → L3_02_02_01);
no new L3 codes were created. Training rows 0; authority unchanged.

## The funnel

| Stage | Rows |
|---|---:|
| api_pattern | 4,880 |
| unique chain signatures (census) | 875 |
| FAIL_CLOSED / structure-invalid (census) | 45 / 2,742 |
| L3 mapping complete | 434 |
| ├─ QUALIFIED (complete + ≥2 transform steps + domain-named owner) | **142** |
| ├─ DEFERRED `task_owner_not_domain_named` | 292 |
| ├─ DEFERRED `insufficient_transform_steps_after_policy` | 127 |
| └─ DEFERRED `deferred_actions` | 76 |
| DEFERRED `unresolved` (unproven transform receiver) | 238 |
| predicate steps kept as evidence only | 1,796 |
| deferred-action steps inside chains | 451 |
| tokenizer / V4 | not yet run |
| **training rows** | **0** |

## The 142 qualified chains

- **61 of 142 carry a policy-qualified predicate control node** — the branch
  case the policy was written for (predicate drives a later transform), encoded
  with the existing Intersect token; the rest are pure transform sequences.
- Length distribution: mode 3, real spread 2–55, tail 39/46/50/55.
- L3 coverage: 11 classes — Intersect 298, Buffer 177, Reproject 168, Feature to
  Point 141, Collect 90, Erase 52, Repair 37, Min Bounding 8, Simplify 5,
  Sym Difference 3, Smooth 1.
- `qualified_l3_sequence_counts` shows **no dominant duplicate sequence** — the
  largest single L3-sequence group is a handful of rows; chain diversity survived
  qualification.

## Reading the defer reasons

1. **`unresolved` 238 rows — 647 steps, 645 of them `transform:unproven_receiver`**
   and 2 `transform:QgsGeometry`. This is the same wall as the standalone lane:
   the transform's argument/receiver type is name-bound and needs the
   dominating-assignment proof. The census's receiver tracking accepts whole-file
   assignment lookups for non-transform methods, but transform binding keeps the
   strict per-call proof — deliberately. Recovering these 645 steps with the
   sidecar-v2 argument proof rule is the single largest known unlock (238 rows).
2. **`task_owner_not_domain_named` 292 rows** — the largest deferral by count.
   These are completely mapped chains in plain-scope functions. Per the lane
   policy they wait; a future relaxed-owner adjudication could revisit them as a
   separate decision (predicted to repeat the standalone result: low survival).
3. **`insufficient_transform_steps_after_policy` 127** — Predicate Policy v1
   correctly removed predicate-only chains that survived census structure checks.
4. **`deferred_actions` 76 rows / 451 steps** — interpolate/offsetcurve/
   splitgeometry inside chains, kept deferred exactly as adjudicated.

## Stage note

The census ledger did not carry `source_path`; the qualification input was
joined by `record_id` back to the v2 normalized ledger on the server
(`pattern_census_input_v2.jsonl`, 875/875 paths resolved) before the run. The
census ledger hash pinned here is that joined input; the local census artifacts
are unchanged.

## Verification

- Focused tests 9/9: approved-binding qualification, owner gating, deferred
  action stays deferred inside a pattern, predicate-evidence-only vs
  predicate-drives-branch (slot granted), measurement never takes a slot,
  unproven transform defers, missing source defers, closed gates.
- `compileall` clean. Artifacts mirrored and hash-verified locally; taxonomy and
  census inputs pinned.

## Next

1. Cross-pool dedup of the 142 vs the 508 pool (signature + source SHA + exact
   L3-sequence) — then task-text construction from source facts, tokenizer, V4.
2. Optional unlock (user decision): dominating-assignment proof for the 645
   unproven transform steps to recover the 238 `unresolved` rows.
3. Optional (user decision): a separate owner-policy adjudication for the 292
   plain-scope complete chains.
