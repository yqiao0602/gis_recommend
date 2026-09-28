# QGIS V4-128 Train-Only 491 v1

## Decision

The current formal QGIS V4-128 train-only entrypoint contains 491 rows. It
combines the prior 454-row authority with 37 source-verified local
`QgsRasterFileWriter` GeoTIFF writer macros.

## Raster File Export increment

- 89/89 complete writer units passed source SHA replay.
- Contract classification: 55 GeoTIFF, 7 GPKG raster, 26 dynamic or unknown,
  and 1 conflicting path-format unit.
- After existing-authority exclusion, the exact GeoTIFF population contained
  53 units from 49 normalized-source-body authorities.
- Source-disjoint calibration and holdout each contained 15 rows, with zero
  source/body overlap, observed false positives, or chain truncations.
- Deterministic source-fact descriptions passed for 53/53 units. Four-layer
  deduplication retained 37 exact training pairs and suppressed 16 duplicates.
- No LLM was called and no L3 was added. The increment reuses stable125
  `L3_07_04_05` / token 68.

## Training-path gate

- Real `bert-base-uncased` tokenization retained 491/491 rows at the fixed
  128-token text limit; maximum observed prompt length was 128 tokens.
- `TaskConditionedL3DatasetV4`, weighted sequence loss, and backward covered
  491/491 rows in 16 batches with finite loss and gradients.
- No training ran and no checkpoint was written.

The dataset is train-only. Validation/test use and production merge remain
ungranted. See `admission_v1.json` for hashes and exact authority references.
