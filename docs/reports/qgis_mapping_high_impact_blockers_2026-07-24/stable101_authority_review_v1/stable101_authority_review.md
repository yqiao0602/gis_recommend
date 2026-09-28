# Stable101 Taxonomy Review Pack

This package is review-only. It contains only the four source-reviewed conservative mappings from the stable101 draft.

## Scope

- Base taxonomy: stable98 (98 L3).
- Draft taxonomy: stable101 (101 L3).
- Coverage gain: +640 records / +179 chains.

## Review Rows

| operator | candidate L3 | samples | unique hits | recommendation |
|---|---|---:|---:|---|
| `gdal:polygonize` | `L3_01_09_03` Raster-Vector Conversion | 3 | 512 | accept_mapping_after_authority |
| `gdal:rasterize` | `L3_01_09_03` Raster-Vector Conversion | 3 | 576 | accept_mapping_after_authority |
| `native:fixgeometries` | `L3_01_05_02` Repair Geometry | 3 | 924 | accept_mapping_after_authority |
| `native:reprojectlayer` | `L3_01_10_01` Project/Reproject | 3 | 1292 | accept_mapping_after_authority |

## Boundary Sidecar

| operator | candidate L3 | reason |
|---|---|---|
| `native:createspatialindex` | `L3_01_07_01` Add Spatial Index | support/export boundary confirmed by source review; excluded from the conservative stable-N training-target draft |
| `native:saveselectedfeatures` | `L3_07_04_01` Export To Shapefile | support/export boundary confirmed by source review; excluded from the conservative stable-N training-target draft |

## Review Contract

- Accept only if the four conservative mappings are approved as formal taxonomy entries.
- Keep the two boundary operators deferred until a separate support/export strategy exists.
- Do not write review rows into `outputs_v2` or any training export before approval.
