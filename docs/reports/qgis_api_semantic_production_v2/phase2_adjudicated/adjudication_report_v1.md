# QGIS API semantic production v2 — adjudicated L3 qualification

Human binding review **2026-09-04** applied to the phase-2 proof ledger (1,058
rows; input hash-pinned). The adjudication text is frozen in
`scripts/adjudicate_qgis_api_semantic_l3.py::ADJUDICATION` and materialized by
that script into `adjudication_v1.jsonl` — the ledger, not manual arithmetic, is
the count authority.

## Adjudication summary

- **A (three mapping classes): PASS.** `native_operator_slug_equivalence` (387),
  `transform_crs_receiver` (558), `taxonomy_class_equivalence` (52) approved as
  classes; per-row evidence fields retained, not reduced to name matching.
- **B (undecided actions): interpolate 40 / offsetcurve 3 / splitgeometry 2 stay
  DEFERRED** (`action_deferred_by_adjudication`). Geometry-flavored `transform`
  split by per-row argument evidence: 1 QUALIFIED (inline
  `QgsCoordinateTransform(...)` argument, bound as `transform_crs_receiver` to
  L3_01_10_01), 1 FAIL_CLOSED (`transform(float(x), float(y))` — numeric
  transformation, not a GIS reprojection), 14 DEFERRED
  (`transform_argument_not_yet_proven` — recoverable later via the dominating-
  assignment rule on the argument, without rerunning phase 1/2).
- **C (consumption): PASS.** Standalone rows route to the workflow-training
  candidate pool (downstream gates still apply); intermediate rows route to the
  operator-grounding corpus.

## Final ledger numbers (computed, not hand-counted)

| Verdict | Rows |
|---|---:|
| **QUALIFIED** | **998** |
| DEFERRED | 59 (45 action-deferred + 14 unproven transform arguments) |
| FAIL_CLOSED | 1 |

The user's arithmetic caution was correct and is resolved by the ledger: the 16
geometry-flavored transforms were part of the 61 unresolved rows, **outside** the
997 proposals, so QUALIFIED = 997 approved + 1 proven transform = **998**, not
"997 qualified".

QUALIFIED by mapping kind: `transform_crs_receiver` 559 (558 + 1 promoted),
`native_operator_slug_equivalence` 387, `taxonomy_class_equivalence` 52. L3
coverage: 11 classes (Reproject 559, Feature to Point 174, Buffer 92, Intersect
57, Minimum Bounding 33, Simplify 28, Repair Geometry 24, Collect 19, Smooth 10,
Erase 1, Symmetrical Difference 1).

## Consumption routing (QUALIFIED rows only)

| Route | Rows | Composition |
|---|---:|---|
| `workflow_training_candidate_downstream_gates` | **137** | Reproject 65, Feature to Point 25, Buffer 21, Simplify 8, Intersect 7, Smooth 5, Collect 4, Repair 1, Minimum Bounding 1 |
| `operator_grounding_corpus` | **861** | bound L3 action inside a larger implementation (893 function-local + 17 self-stores, minus unbound overlap; 860 from approved classes + 1 proven transform) |

`training-eligible ≠ training row`: the 137 standalone rows still face
normalized-sequence construction, cross-source dedup, independent workflow/task
context, tokenizer, and stable124/V4 gates. Training rows emitted: 0. Authority,
evaluation splits, checkpoints unchanged.

## KPI transition

The lane's headline question is now: **how many independent QGIS training rows
do the 137 standalone candidates yield** — not how many more units can be
parsed. If the yield is large the lane keeps mining; if it is small, effort
moves to Processing workflow + API pattern (multi-step) production.

## Verification

- Focused tests 6/6: class approvals keep evidence; undecided actions stay
  deferred; the three-way transform split; routing separation; deferred rows
  unrouted; training gates closed.
- `compileall` clean; hash ledger pins the phase-2 proof ledger input.
