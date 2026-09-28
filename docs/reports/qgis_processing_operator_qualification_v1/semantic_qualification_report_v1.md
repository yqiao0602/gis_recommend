# Processing operator semantic/L3 qualification v1

Operator-level three-state qualification of the 207 unique Processing operator
IDs against the existing authority. This is the first measured answer to "how
many of the 207 operators can actually enter the current 128-token L3 taxonomy".
No L3 grant, training row, authority change, evaluation change, or checkpoint is
made here.

## Verdicts

| Verdict | Operators | Support rows |
|---|---:|---:|
| **QUALIFIED** | 56 | 280 |
| **DEFERRED** | 44 | 101 |
| **FAIL_CLOSED** | 107 | 210 |
| total | 207 | 591 |

Consistency gates: operator count 207 (`matched`), support rows 591
(`matched`), unique source SHA 591 — identical to the frozen v3 operator census,
so the rebuilt aggregation is the same population.

### QUALIFIED (56) — two proof paths

- `exact_mapping` (15 operators, 39 rows): the literal operator ID is a key of
  `composed_stable124_mapping_v1` (170 operators) and the L3 target is a class of
  `taxonomy_128_v1`. Examples: `gdal:rastercalculator` (10) → L3_03_03_A,
  `native:dissolve` (4) → L3_02_03_05, `native:buffer` (2) → L3_02_01_01.
- `verified_alias_same_slug` (41 operators, 241 rows): every backing row
  independently proved the `qgis:<slug>` → `native:<same slug>` migration by
  rereading the source, re-verifying its SHA256, and re-locating the exact
  literal call at the span recorded by sidecar v7 — across `processing.run`
  (198), `processing.runalg` (30), and `processing.runAndLoadResults` (13).
  Highest support: `qgis:reprojectlayer` (26) → L3_01_10_01,
  `qgis:joinattributestable` (19) → L3_01_03_05,
  `qgis:mergevectorlayers` (19) → L3_01_03_04.

Precedent cross-check: the existing
`scripts/verify_qgis_processing_provider_aliases.py` independently verified the
198-row `processing.run` attribute-form subset — 198/198 verified, 0 failures,
record-ID set identical to this prover. The prover additionally covers 43 rows
(30 `runalg`, 13 `runAndLoadResults`) that the precedent verifier cannot see;
those use the same `qgis_to_native_same_slug` rule with the same span-and-literal
discipline.

The 56 qualified operators ground **37 distinct L3 codes** of the 128-token
taxonomy.

### DEFERRED (44)

- `no_mapping_authority` (36 operators, 85 rows): catalog providers
  (native/qgis/gdal/gdalogr/grass/grass7/saga/otb) with no mapping key reachable
  directly or by a same-slug alias. These are observation-list candidates for a
  future minimal-extension L3 decision, not failures. Top:
  `native:rastercalc` (15), `qgis:filedownloader` (12),
  `native:dtmslopebasedfilter` (4), `qgis:importintopostgis` (4), `qgis:package`
  (4).
- `alias_deferred_no_precedent` (8 operators, 16 rows): `gdalogr:<slug>` with a
  `gdal:<same slug>` mapping key (7) and `sagang:fillsinksxxlwangliu` with a
  `saga:` key (1). A same-slug provider alias without precedent authority is not
  assumed to carry identical semantics, parameters, or I/O contracts; promotion
  requires a new, separately frozen precedent decision.

### FAIL_CLOSED (107)

Non-catalog third-party plugin providers (210 rows), permanently closed under the
2026-08-08 third-provider rule: `r:` (20), `model:` (8), `umep:` (7), `script:`
(6), `pts tools` (4), plus `fct`, `omm`, `tbk`, `brdrqprovider`, `hrisk`, `pff`,
`threedi`, and others, including one ID with no provider prefix at all
(`omsberg & preston project creator`).

## Scope facts carried into the ledger

- Parameter and I/O evidence is recorded per operator as coverage (status and
  completeness counts from sidecar v7) but does **not** gate this verdict: this
  layer decides taxonomy groundability, not training eligibility.
- Every backing row of every QUALIFIED operator is `source_verified_ast` with
  `literal_source_evidence`; an operator with any unverified row stays DEFERRED.
- All 591 rows carry exactly one literal call; statically resolvable dynamic
  forms remain outside this pool (separate 496-row dynamic candidate lane).
- `56` is the operator-level ceiling under current authority, not a promise of
  280 training rows. Downstream gates (parameter/I-O qualification, semantic
  fidelity, cross-pool dedup, training admission) are all still closed.

## Provenance and infrastructure notes

Inputs: sidecar v7 ledger (SHA256 `f2559835…`, hash-verified after transfer),
`composed_stable124_mapping_v1.json`, `taxonomy_128_v1.json` (all hash-pinned in
`hash_ledger_v1.json`).

The alias proof ran on the compute server because source files live under
`/home/yll` (intact, read-only). Between 2026-09-03 and 2026-09-04 the entire
`/home/qy/system_redesign/diagnostics/` tree — including the server-side v3
operator-asset census, the frozen normalized ledger input
(`45a1c12d…`), and all GEE batch evidence — was deleted outside this session
(roughly 450G freed on `/`, 590G on `/data`). This qualification therefore
rebuilt the operator aggregation deterministically from the local v7 sidecar
ledger; the 207/591/591 checks above confirm it reproduces the frozen census
exactly. The authoritative chain for the operator lane now lives in this
repository: v7 sidecar ledger + this qualification ledger. If the normalized
ledger is ever needed again it can be regenerated from `/home/yll` through
`scripts/mine_qgis_assets.py` and `scripts/normalize_qgis_assets.py`, but that
regeneration has not been run.

## Verification

- Focused tests: 8/8 alias prover, 8/8 qualification
  (`tests/test_prove_qgis_operator_alias_bindings.py`,
  `tests/test_qualify_qgis_processing_operator_semantics.py`); sidecar tests
  remain 15/15.
- `compileall` clean.
- Alias-proof artifacts re-hashed after transfer; all digests match
  `hash_ledger_v1.json`; precedent cross-check files mirrored and re-compared
  locally (198/198 agreement).
- Training rows emitted: 0. Authority, evaluation splits, checkpoints: unchanged.
