# QGIS API Aggregation Canary: Preliminary Semantic Audit

Date: 2026-07-15

This is an AI-assisted preliminary audit, not human adjudication. It does not change
`review_status=pending` or permit any record to enter training.

## Criteria

- **A**: proposed operators are evidence-grounded and capture the task's main ordered workflow.
- **B**: core operation is correct, but one or more material workflow steps are absent or compressed.
- **C**: a defining task operation is missing, or the resulting chain would provide misleading supervision.

## Results

| Record | Task | Grade | Preliminary finding |
| --- | --- | --- | --- |
| `35b0874bd57dd44b92cfde8b` | Convert DN to top-of-atmosphere reflectance | A | Raster calculator directly represents the stated scaling and solar-angle correction. |
| `32935f5f76360dca22c01970` | Koppel overige bronnen | A | Long processing chain is directly supported by exact processing calls for joins, repair, intersection, field work, filtering, ordering, and aggregation. |
| `cba1ac5ed3502f9cbc122d8d` | Generate attribute-based description | A | Advanced Python and standard field calculators match the two generated attribute fields. |
| `e24b3bb059e02538e1becc69` | Generate RGB quicklook visualization | B | Build VRT captures RGB composition, but STAC selection and QGIS layer/output handling are outside the proposed chain. |
| `0c2284c261bb8e81752d000b` | Detect forest stand upper layer change | A | Repeated raster calculator/rasterize sequence is present in exact processing evidence and matches the described change workflow. |
| `bc6ac67140f75dd1e0e53cfb` | Generate low-detail grid boundary | C | Proposal contains only vector export; the task-defining dissolve, buffer, and simplify operations are absent from compact semantic evidence. |
| `3abb6a5dd27d4250c95185eb` | Render QGIS map tiles | B | GDAL translate captures georeferenced export, but QGIS map rendering remains unresolved/unknown and is not represented as a semantic step. |
| `1b935d125efd4d723adab130` | Count languages per country | A | Fix geometries, intersection, and statistics by categories form the expected workflow. |
| `d892acd24d250c002bdce0c5` | Extract river headwater points and lines | C | The defining custom `identify dangles` operation is present in code evidence but absent from bounded candidates and the proposal. |
| `9a943fce45c3ace29b2498f2` | Burn vector attributes into raster | A | GDAL rasterize is directly supported by `gdal.rasterizelayer` evidence. |
| `a9fb1af26b145a6ce792ca5e` | Convert building mask to vector boundary | A | GDAL polygonize directly matches raster-to-vector conversion. |
| `51986e4aa50231a487f998d2` | Extract wind turbine locations from OSM | B | Clip, field calculation, and refactor fields cover the local vector workflow, but OSM retrieval/filtering is not represented. |
| `06f60f4372c88c77c1a5581d` | Evaluate spatial fragmentation accuracy | C | Buffer, raster calculation, and intersection are real evidence, but major segmentation, vectorization, and evaluation stages are missing. |
| `6138cfd024129132408274db` | Generate tessellation polygons from points | A | Thiessen/Voronoi, clip, Delaunay, and spatial join calls match the described alternatives and post-processing. |
| `50800e3812484a46ed247be1` | Extract forest stand data by perimeter | B | Spatial index, extract by location, buffer, and raster mask clip are correct, but the described dissolve/vector clipping branches are incomplete. |

## Aggregate

- A: 8/15 (53.3%)
- B: 4/15 (26.7%)
- C: 3/15 (20.0%)
- A or B among contract-valid proposals: 12/15 (80.0%)
- A among all 24 canary records: 8/24 (33.3%)
- A or B among all 24 canary records: 12/24 (50.0%)

## Decision

Scaling remains blocked. Contract-valid output is not sufficient for training admission:
direct-API semantic compaction and custom-operator coverage still omit defining workflow
steps. Human reviewers must adjudicate the workbook before any acceptance-rate claim is
used to size the broader dataset.
