# QGIS custom embedded Processing review v2

This review corrects the v1 `.run()` overmatch. It is census evidence, not training admission.

## Corrected population

- Custom/algorithm implementation records: 4,858
- Records with genuine embedded QGIS Processing: 9
- Genuine embedded multistep records: 2
- Source failures: 0
- Training rows emitted: 0

The v1 counts of 73 embedded records and 12 multistep records included arbitrary
attribute calls named `.run()`. Direct source review of the old 12-row multistep
subset found 10 `subprocess.run()` records and only two QGIS registry-algorithm
records.

## Genuine candidates

| Role | Records | Evidence |
|---|---:|---|
| Literal single-step raster calculator | 3 | NDVI, NDWI, and mask algorithms call `qgis:rastercalculator` |
| Dynamic single-step | 4 | `algo_str` remains unresolved and fail-closed |
| Literal registry multistep | 2 | `gdal:translate -> gdal:rasterize_over` and `gdal:translate -> gdal:rasterize_over_fixed_value` |

The two multistep records are retained as source-backed sidecar candidates. Their
support is too low for a general custom-algorithm recovery rule, so this route is
frozen as a scale strategy.

Authority: server artifacts under
`/home/qy/system_redesign/diagnostics/qgis_processing_resolution_census_v2/`.
The full ledger hash is recorded in `hash_ledger_v2.json`; only the small
summary/report/hash artifacts are mirrored locally.
