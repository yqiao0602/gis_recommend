# QGIS API semantic production v2 — phase 2: L3 proof

Second phase over the 1,058 phase-1 geometry-semantic candidates (input:
`semantic_unit_facts_v1.jsonl`, hash-pinned in `hash_ledger_v1.json`; taxonomy:
the 128-token authority). This layer binds each semantic action to an L3 class
**with explicit mapping evidence**, splits standalone operations from
implementation steps using the phase-1 return-target facts, and deliberately
emits **proposals, not admissions**: every row stays `DEFERRED` with
`awaiting_independent_binding_review`, because binding review is the QUALIFIED
gate and belongs to a separate, explicitly authorized pass. Training rows 0;
authority, evaluation splits, and checkpoints unchanged.

## Mapping sources (recorded per row, never method-name-only)

| mapping_kind | rows | basis |
|---|---:|---|
| `transform_crs_receiver` | 558 | `QgsCoordinateTransform.transform` is reprojection **by type contract** — the receiver class defines the semantics; the method name is irrelevant |
| `native_operator_slug_equivalence` | 387 | the PyQIS method is the engine of the identically-named Processing algorithm (e.g. `QgsGeometry.buffer` backs `native:buffer`), whose L3 is already fixed by `composed_stable124` |
| `taxonomy_class_equivalence` | 52 | semantic equality with a taxonomy class description where no same-slug operator exists: `convexhull` → L3_02_05_12 Minimum Bounding Geometry (33, hull is an explicitly enumerated variant), `combine` → L3_02_03_05 Collect Features (19, aggregates geometries into multi-geometries) |
| `unresolved_action` | 61 | `interpolate` 40, `offsetcurve` 3, `splitgeometry` 2, geometry-flavored `transform` 16 — no L3 binding is proposed for these until each action's semantics are separately decided |

## Result

- **997 of 1,058 candidates carry an L3 proposal** across **11 distinct L3 classes**
  (L3_01_10_01 558, L3_02_05_11 174, L3_02_01_01 92, L3_02_02_01 57,
  L3_02_05_12 33, L3_02_05_01 28, L3_01_05_02 24, L3_02_03_05 19, L3_02_05_02 10,
  L3_02_02_04 1, L3_02_02_05 1).
- **137 standalone-operation rows** (result returned to caller 62, module-level
  result 75): the caller can observe the operation, so these are the rows a
  workflow-training line could eventually consume. Composition: Project/Reproject
  65, Feature to Point 25, Buffer 21, Simplify 8, Intersect 7, Smooth 5,
  Collect Features 4, Repair Geometry 1, Minimum Bounding Geometry 1.
- **860 intermediate-implementation rows** (893 function-local assignments + 17
  `self.*` stores, minus overlap with unbound): bound to an L3 action but the
  result never leaves the function — exactly the "geometry computation inside a
  larger algorithm" class the plan flagged. These are operator-semantic knowledge,
  not workflow steps.
- 61 rows deferred with an undecided action, not a failed gate.

All 1,058 rows are `DEFERRED` by design; `qualified_rows = 0`.

## What phase 2 does NOT claim

- No proposal here is a training row or an authority entry. The L3 binding table
  (`METHOD_TO_OPERATOR`, CRS-receiver rule, the two taxonomy-class equivalences)
  is **frozen in this ledger with its evidence** so an independent reviewer can
  accept or reject each binding class once, not per row.
- `interpolate` (40 rows, "point at distance along a line") has no
  same-slug operator and no unambiguous taxonomy class — it must not be quietly
  mapped. Same for `offsetcurve`, `splitgeometry`, and the 16 geometry-flavored
  `transform` rows.
- The `native_operator_slug_equivalence` table lists only methods whose
  Processing-operator engine identity is already established in the frozen
  mapping authority; the equivalence itself still needs the independent review
  pass before any QUALIFIED verdict.

## Verification

- Focused tests 9/9: candidates-only filtering, no-QUALIFIED-by-construction,
  evidence fields on slug equivalence, CRS-binding by receiver type (geometry
  `transform` stays unresolved), taxonomy-class binding for hull/combine,
  undecided actions stay unresolved, out-of-taxonomy targets deferred,
  standalone-vs-intermediate split (return/module/self/local), closed training
  gates.
- `compileall` clean. Hash ledger pins the phase-1 ledger and the taxonomy file.

## Next

1. Independent binding review of the three mapping classes (one decision each:
   slug-equivalence table, CRS-receiver rule, hull/combine taxonomy
  equivalences) + decisions for `interpolate`/`offsetcurve`/`splitgeometry`/
   geometry-`transform`. This is the QUALIFIED gate; nothing may auto-pass.
2. After review, the 137 standalone rows become the API lane's first
   training-eligible pool (still subject to dedup/tokenizer/V4 gates downstream);
   the 860 intermediate rows feed the operator-grounding corpus per the
   multi-pool policy.
3. Phase-3 decision (user): inter-procedural receiver recovery for the 1,168
   ambiguous rows, or move to `api_pattern`.
