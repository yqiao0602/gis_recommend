# QGIS train-only aggregate delivery 507 v1

## Decision

- Deliver one directly loadable 507-row QGIS train-only aggregate from nine mutually deduplicated Processing and API packages.
- Preserve every row's source schema, admission, split, and source-pool identity in explicit provenance fields.
- Keep validation/test eligibility false and production merge not granted.

## Composition

- Processing: 293.
- Exact API: 6.
- Random-point API: 5.
- Create Feature Class: 28.
- Vector File Export: 18.
- Add Field -> Calculate Field: 15.
- Raster Calculator: 83.
- Set CRS Metadata: 35.
- Add Field Existing Layer: 24.
- Total: 507.

## Aggregate gates

- Unique sample IDs: 507.
- Unique source regions: 507.
- Unique call graphs: 507.
- Unique exact training pairs: 507.
- Unique source authorities: 387.
- Unique L3 codes: 56.
- Maximum stable125 content token: 124.
- Aggregate JSONL SHA256: `3709ec6f81ad711c0dec29ccf9e5034c1204dbfdbcada7a44ecc22a5fea0a3ad`.

## Verification

- Real `TaskConditionedL3DatasetV4` loader/weighted-loss/backward: 507/507 rows, 16 batches.
- Loss finite: true.
- Gradient finite: true.
- Checkpoint written: false.
- Training run: false.
- Validation/test eligibility: false.
- Production merge: not granted.

`qgis_train_only_507_v1.jsonl` is the current unified QGIS training-data entrypoint.
`source_pool_ledger_v1.jsonl` preserves the nine source package contracts, while
`hash_ledger_v1.json` binds all input packages and generated aggregate artifacts.
