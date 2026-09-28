# QGIS Processing blocker expansion report v1

Date: 2026-07-31

## Decision

The 757-row blocker pool was replayed against `/home/yll` with the frozen
stable110 mapping, deterministic descriptions, and four-layer deduplication.
The resulting delivery package is a replacement for the previous 44-row
second batch. It contains 47 train-only rows; after comparison with the
previous package, 3 training pairs are net new. The other 3 new candidate
identities replace existing source identities for the same training pairs.

The Processing delivery count therefore moves from 162 to 165. No validation,
test, production merge, LLM call, or training run was performed.

## Replay delta

| metric | v3 replay | v4 custom alias | v5 wrapper routing |
|---|---:|---:|---:|
| source rows | 757 | 757 | 757 |
| source SHA failures | 0 | 0 | 0 |
| fully normalized rows | 133 | 150 | 150 |
| fully normalized + mapping complete | 108 | 125 | 125 |
| partial operator-resolution rows | 254 | 237 | 237 |
| candidate pool rows | 174 | 174 | 174 |
| canonical candidates | 47 | 47 | 47 |
| train-only replacement rows | 47 | not re-exported | not re-exported |

The v4 change is the source-reviewed equivalence
`script:copernicusrastercalculator -> qgis:rastercalculator`, backed by the
implementation SHA recorded in `provider_equivalence_authority_v1.json`.
Those 17 rows still contain dynamic raster statistics/GDAL `EXTRA` parameter
derivation and therefore route to an API sidecar; they add zero training rows.

The v5 routing refinement treats only `QgsRasterLayer` and `print` as
non-transforming wrappers. Calls such as `ReadAsArray`, `Open`, feature edits,
and geometry mutation remain blocking. The candidate pool is byte-identical
to v3, so no additional training rows are admitted by this refinement.

## Delivered package

`docs/reports/qgis_processing_second_batch_train_v3/`

- `qgis_processing_train_only_v1.jsonl`: 47 rows, 31 source authorities.
- `adjudication_export_ledger_v1.jsonl`: hash-bound export decisions.
- `summary_v1.json`: 47 accepted, 127 dedup exclusions, no cross-pool suppression.
- `smoke_v1.json`: real V4 loader/weighted-loss/backward smoke, 47/47 rows,
  finite loss and gradients, checkpoint=false, training_run=false.

The package uses the v5 source-disjoint rule authority from
`docs/reports/qgis_processing_second_batch_v5/` and the v3 replay candidate
package. The exporter now accepts `--candidate-report-dir`, so a frozen rule
authority can be replayed against a later candidate package without rebuilding
or manually re-adjudicating the old calibration rows.

## Remaining blockers

- 34 fully-normalized records still have unmapped operators. The largest
  unresolved families are `grass7:r.watershed` (11),
  `qgis:voronoipolygons` (9), `grass7:r.to.vect` (6), and `grass7:v.clean` (5).
  They remain fail-closed because the stable110 contract is missing, parameter
  dependent, or provider-version evidence is incomplete.
- 237 partial operator-resolution rows remain. `IdragraSaveAscii` is a
  specialized ASCII/nodata export, `PreCourlis lines_to_points` changes a
  domain-specific attribute schema, and `extract_subwatershed` plus the
  `computed8/filterstructures/indice*` family are nested domain workflows.
  None is an exact single-operator replacement. They require cross-file
  implementation expansion into standard Processing DAG units.
- The current Processing train-only total is 165; 35 additional unique pairs
  are needed for the 200-row milestone. No quality gate is relaxed to reach it.

## Verification

- `57` targeted recovery/blocker/description/export tests passed before replay.
- `68` QGIS conversion, recovery, blocker, description, and exporter tests
  passed after the non-transforming wrapper rule.
- v3 replay: `source_verified_rows=757`, `source_failure_rows=0`.
- V4 smoke: rows_loaded=47, rows_seen_by_loader=47, loss_finite=true,
  gradient_finite=true, checkpoint_written=false, training_run=false.
