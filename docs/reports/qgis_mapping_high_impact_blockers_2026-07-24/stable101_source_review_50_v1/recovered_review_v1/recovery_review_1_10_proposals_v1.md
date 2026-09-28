# stable101 recovered subworkflow review proposals: 1-10

Status: `proposal_only_pending_joint_confirmation`

These recommendations do not modify the blank human-review fields in
`recovery_review_29_v1.csv/jsonl` and do not grant training admission.

| No. | unit_id | proposed decision | evidence-based reason |
|---:|---|---|---|
| 1 | `qgis_stable101_r3_chip_pair_dag` | `accept_recovered` | Four call sites are source-backed: reproject labels, rasterize the mask, then call the same clip helper separately for image and mask. The draft preserves the parallel paired outputs and excludes PNG/filter side effects. |
| 2 | `qgis_stable101_r6_processing_csv` | `accept_recovered` | One `processAlgorithm` data path connects geometry repair, independently optional attribute extraction and reprojection, two field refactors, and final save. AutoCAD SCR generation and GUI labeling remain explicit omissions. |
| 3 | `qgis_stable101_r42_cn_overlay_preprocess` | `accept_recovered` | Source call sites prove three conditional reprojections and two intersections: land-use with soils, then that result with subbasins. The corrected draft excludes low-level curve-number calculation and CSV output. |
| 4 | `qgis_stable101_r9_soil_fix_clip` | `accept_recovered` | The local chain is directly connected by `fixed_layer -> clip INPUT`. USDA acquisition and memory-layer construction remain prerequisites, not target steps. |
| 5 | `qgis_stable101_r10_basin_overlay` | `accept_recovered` | The basin is conditionally reprojected to WGS84 and then used as the intersection overlay for cached soil data. The revised draft states that condition and retained output only. |
| 6 | `qgis_stable101_r11_soil_postprocess` | `accept_recovered` | The source has a direct four-step data path: fix soil geometry, clip to AOI, reproject to target CRS, and fix geometry again. API acquisition remains outside scope. |
| 7 | `qgis_stable101_r13_classification_polygonize` | `accept_recovered` | The selected classification branch feeds its reclassified raster into polygonize. The draft does not claim the later low-level category-field update. |
| 8 | `qgis_stable101_r13_zonal_summary` | `accept_recovered` | This is a valid independent single-step unit over boundaries and the need-index raster; the revised text names only the four source parameters: mean, median, minimum, and maximum. |
| 9 | `qgis_stable101_r23_raster_preprocess` | `accept_recovered` | `_subset_raster_layer` passes the warp output directly to fill-nodata and returns the written raster path. The entrypoint is explicitly called from the base execution loop. |
| 10 | `qgis_stable101_r23_vector_mask` | `defer_missing_call_graph` | The file defines `_rasterize()` but contains no call to it. The base loop calls abstract `_process_features_for_area()` and then `_mask_raster()`, so the claimed rasterize-to-mask edge depends on a concrete subclass not present in this source. A concrete subclass source/call site is required before admission. |

## Proposed batch result

- `accept_recovered`: 9
- `defer_missing_call_graph`: 1
- `reject`: 0
- formal human fields changed: 0
- training rows granted: 0
