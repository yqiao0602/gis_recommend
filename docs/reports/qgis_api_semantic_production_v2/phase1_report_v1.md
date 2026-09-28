# QGIS API semantic production v2 — phase 1: source fact extraction + semantic qualification

First production phase over the 3,209 confirmed `api_semantic_unit` rows of the v2
normalized ledger (`a13ce1a2…`, hash-pinned as this run's input). This phase
answers the priority question set before any L3 work: **how many of the 3,209
carry provable QGIS GIS semantics at all, and what are the rest?**

L3 mapping is explicitly **not attempted** here — every row carries
`l3_mapping_status = not_attempted_phase1` and `l3_candidate = null`. Only
`DEFERRED` and `FAIL_CLOSED` are reachable; `QUALIFIED` requires the phase-2 L3
proof layer. Training rows 0; authority, evaluation splits, and checkpoints
unchanged.

## Why receiver proof had to come first

The Asset Miner matched API semantic calls by **method name only**, and the method
names are not QGIS-specific: `buffer`, `centroid`, `intersection`, `contains`,
`distance`, `transform` are shared verbatim by shapely, geopandas, sklearn, pyproj,
numpy and others. Two hardening rules were added after inspecting the first run's
output, both now regression-tested:

1. **Foreign-only keyword arguments fail closed.** `cap_style`/`join_style`/
   `mitre_limit`/`single_sided`/… exist only in shapely/geopandas signatures; PyQGIS
   takes positional `(distance, segments)`. Caught 4 geopandas buffer calls whose
   receiver looked plausible.
2. **A bare `.geometry` attribute is not a QGIS receiver.** `frame.geometry.buffer()`
   is the GeoDataFrame idiom; PyQGIS exposes `QgsFeature.geometry()` as a call.
   Attribute access alone demotes the row to `ambiguous_receiver` (9 + 2 rows).

Receiver binding otherwise follows the operator lane's discipline: inline QGIS
factory/constructor/accessor call, or **one dominating same-scope assignment** of
one of those; foreign-library roots (followed transitively through proven
bindings) prove the opposite and fail closed.

## Result (3,209 rows, all source-SHA verified, all calls relocated)

| Semantic status | Rows | Meaning |
|---|---:|---|
| `candidate_geometry_semantic` | **1,058** | Receiver proven QGIS, geometry-transform role, result retained |
| `ambiguous_receiver` | 1,168 | Local name with no provable/multiple/no dominating QGIS binding |
| `not_a_workflow_step` | 527 | Proven predicate/measurement (returns scalar, not geometry) |
| `result_unused` | 362 | Result discarded or only read as a condition |
| `not_qgis_semantics` | 94 | Foreign library root (osgeo 33, pyproj 23, shapely 18, sklearn 8, geopandas 5+4, pandas 1, PIL 1, cv2 1) |

Verdicts: **DEFERRED 3,115 / FAIL_CLOSED 94 / QUALIFIED 0** (by construction).

Role distribution: `crs_or_geometry_transform` 1,261 / `geometry_transform` 978 /
`spatial_predicate` 667 / `measurement` 303. Predicate+measurement (1,070 minus
receiver-ambiguous/foreign overlap) are honest knowledge but are **not workflow
steps** — they return booleans and floats, not geometries.

## What the 1,058 candidates actually are

- **558 are `QgsCoordinateTransform.transform`** — i.e. coordinate reprojection
  (`Project/Reproject` semantics), the single largest coherent action class.
- **484 are classic geometry transforms**: centroid 174, buffer 92, intersection
  57, interpolate 40, convexhull 33, simplify 28, makevalid 24, combine 19,
  smooth 10, offsetcurve 3, splitgeometry 2, symdifference 1, difference 1.
- **16 are geometry-flavored `transform`** (receiver a `QgsGeometry`/`QgsLineString`
  factory — GCP-transformer territory, needs its own semantic review).
- 1,058 unique source SHAs — one candidate per source, no concentration.
- Parameter completeness is low, as expected: only **26** non-transform candidates
  have all-literal argument values; the rest bind runtime expressions. This layer
  records full argument facts (positional/keyword, literal or expression) so
  later parameter-asset work does not need to reparse source.

Each row carries the full fact record: `source_sha256`, `call_span`, `call_text`,
`receiver` (kind, qgis_type, binding line, foreign module), `argument_facts`,
`return_target`, `enclosing_scope`, `semantic_action` (role:method — deliberately
**not** an L3 code), `semantic_role`, `semantic_status`, `decision`,
`decision_reason`. A taxonomy change or a new L3 proof rule never requires
reparsing source.

## KPI reading (per policy: measure knowledge yield, not training rows)

```text
3,209 units
 ├─ 1,058  candidate geometry semantics  (33%)
 │    ├─ 558  CRS reproject action (one semantic action)
 │    └─ 484+16  13 distinct geometry actions
 ├─ 1,168  receiver unprovable from source alone  (needs cross-function dataflow or runtime type — the real next-capability frontier)
 ├─ 889    predicates/measurements/discarded results (knowledge, not workflow steps)
 └─ 94     foreign libraries (shapely/geopandas/pyproj/…) — fail closed, correctly
```

The 1,168 `ambiguous_receiver` rows are not noise: they are the concrete
measurement of the "hidden semantics in implementation" problem — for those rows
the receiver's type cannot be proven from the file alone (locals from other
functions, parameters, loops). Recovering them requires inter-procedural type
evidence, which is exactly the phase-3 capability decision, not a rule tweak.

## Verification

- Focused tests 13/13, including the two hardening regressions
  (`cap_style` fail-closed; bare `.geometry` attribute demoted; `.geometry()` call
  still accepted).
- `compileall` clean.
- Artifacts mirrored to the repo and re-hashed after transfer; the pinned input
  hash equals the local v2 normalized ledger exactly (`a13ce1a2…`).

## Next

- Phase 2 (L3 mapping proof) operates only on the 1,058 candidates: per-action L3
  binding with explicit mapping evidence, three verdicts, `QgsCoordinateTransform`
  handled as reproject semantics rather than a generic transform.
- Phase 3 decision point: whether to invest in inter-procedural receiver-type
  recovery to attack the 1,168 ambiguous rows, or to accept them as measured
  ceiling for this lane and move to `api_pattern` (4,880).
- GEE survival check remains parallel and non-blocking.
