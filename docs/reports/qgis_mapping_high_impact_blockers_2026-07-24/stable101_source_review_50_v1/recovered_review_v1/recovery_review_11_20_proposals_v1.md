# stable101 recovered subworkflow review proposals: 11-20

Status: `proposal_only_pending_joint_confirmation`

Batch 1 is already recorded in a separate confirmed adjudication sidecar. These
rows remain proposals and do not change `recovery_review_29_v1.csv/jsonl`.

| No. | unit_id | proposed decision | evidence-based reason |
|---:|---|---|---|
| 11 | `qgis_stable101_r24_vector_mask` | `accept_recovered` | `_process_features_for_area` proves the point-only buffer branch and the shared clip-to-rasterize path for point/polygon/GHSL modes. The revised description states the buffer condition. |
| 12 | `qgis_stable101_r24_raster_mask` | `accept_recovered` | The execution loop calls warp/subset first and passes its output path into raster calculator; the formula converts valid pixels to 1 and NoData to 0. |
| 13 | `qgis_stable101_r29_dem_baseline` | `accept_recovered` | In the DEM baseline branch, warp writes the aligned baseline used as raster-calculator input B; `A-B` is then clipped by the target polygon mask. |
| 14 | `qgis_stable101_r29_polygon_baseline` | `accept_recovered` | The alternate branch calls the polygon-baseline helper, whose rasterize output becomes calculator input B before the same mask clip. The branch call site is source-backed. |
| 15 | `qgis_stable101_r34_fix_geometries` | `accept_recovered` | The standalone utility function has one explicit geometry-repair call with direct input/output parameters. |
| 16 | `qgis_stable101_r34_singleparts` | `accept_recovered` | The standalone utility function directly converts multipart input to singlepart output. |
| 17 | `qgis_stable101_r34_clip` | `accept_recovered` | The standalone utility function directly clips an input shapefile by an overlay shapefile. |
| 18 | `qgis_stable101_r34_extract_expression` | `accept_recovered` | The function is an independent expression-extraction unit; unrelated dynamic GDAL helpers elsewhere in the module remain excluded. |
| 19 | `qgis_stable101_r36_watershed_outputs` | `defer_mapping_gap` | The ten-step source DAG is explicit, but `grass7:r.watershed`, `grass7:r.water.outlet`, and `grass7:r.to.vect` have no admitted L3 mapping/token in stable101. |
| 20 | `qgis_stable101_r37_web_vector_fix` | `accept_recovered` | After a successful Web response is materialized and contains features, the downloaded vector is passed directly to geometry repair. Fetch/materialization remains a prerequisite. |

## Proposed batch result

- `accept_recovered`: 9
- `defer_mapping_gap`: 1
- `reject`: 0
- formal human fields changed for rows 11-20: 0
- additional training rows granted: 0
