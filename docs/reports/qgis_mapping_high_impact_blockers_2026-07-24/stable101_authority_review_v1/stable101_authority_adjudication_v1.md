# Stable101 Taxonomy Adjudication v1

Date: 2026-07-24

This is the human/Codex adjudication layer for the stable101 authority review pack. It grants taxonomy mapping authority for the four conservative rows only. It does not update `outputs_v2`, export training rows, call an LLM, or start training.

## Decision

| operator | accepted L3 | decision | taxonomy admission | training admission |
|---|---|---|---|---|
| `gdal:polygonize` | `L3_01_09_03` Raster-Vector Conversion | accept_taxonomy_mapping | granted | not_granted |
| `gdal:rasterize` | `L3_01_09_03` Raster-Vector Conversion | accept_taxonomy_mapping | granted | not_granted |
| `native:fixgeometries` | `L3_01_05_02` Repair Geometry | accept_taxonomy_mapping | granted | not_granted |
| `native:reprojectlayer` | `L3_01_10_01` Project/Reproject | accept_taxonomy_mapping | granted | not_granted |

## Basis

- `gdal:polygonize` has AST-confirmed active calls with raster `INPUT`, `BAND`, `FIELD`, and `OUTPUT`, supporting raster-to-vector polygon conversion.
- `gdal:rasterize` has AST-confirmed active calls with vector `INPUT`, `FIELD` or `BURN`, output raster size or extent, and `OUTPUT`, supporting vector-to-raster conversion.
- `native:fixgeometries` has AST-confirmed active calls with `INPUT`, `OUTPUT`, and sometimes `METHOD`, supporting invalid-geometry repair.
- `native:reprojectlayer` has AST-confirmed active calls with `INPUT`, `TARGET_CRS`, and `OUTPUT`, supporting CRS reprojection.

## Boundary Rows

The two sidecar rows remain deferred:

- `native:createspatialindex` is a real support/performance step and is not a target training task.
- `native:saveselectedfeatures` is output-type dependent and remains excluded until export/output splitting is defined.

## Next Gate

Use this adjudication to re-evaluate the admissible QGIS multi-step Processing candidate pool under stable101. Production mapping updates, training JSONL export, and LLM task-description generation still need a separate chain-level admission step.
