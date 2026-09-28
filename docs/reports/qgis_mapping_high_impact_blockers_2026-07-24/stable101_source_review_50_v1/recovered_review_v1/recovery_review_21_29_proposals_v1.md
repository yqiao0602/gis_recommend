# stable101 recovered subworkflow review proposals: 21-29

Status: `proposal_only_pending_joint_confirmation`

Batches 1 and 2 are recorded in separate confirmed adjudication sidecars. These
last nine rows remain proposals and do not change the blank review authority.

| No. | unit_id | proposed decision | evidence-based reason |
|---:|---|---|---|
| 21 | `qgis_stable101_r37_protected_sites_merge` | `defer_dynamic_loop_cardinality` | `fixgeometries` executes once per successful service response before merge. The static two-token chain compresses an unknown number of repair calls, so it is not yet a faithful fixed target sequence. |
| 22 | `qgis_stable101_r38_complete_measure` | `accept_recovered` | Selected parcel features are explicitly repaired before low-level simplification and measure-field calculation. The draft retains only the geometry-cleanup subworkflow and declares its downstream role. |
| 23 | `qgis_stable101_r38_blocks_selection` | `accept_recovered` | Geometry repair is conditionally executed only when selected features exist. Recovery metadata now marks ordinal 0 optional and the draft states the condition. |
| 24 | `qgis_stable101_r38_registered_selection` | `accept_recovered` | This independent entrypoint has the same source-backed selection condition; optional geometry repair feeds later registered-feature generation. |
| 25 | `qgis_stable101_r38_owner_layers` | `accept_recovered` | Two explicit repair calls operate on independent owner and occupant layers. The dependency graph keeps them parallel and the draft no longer linearizes them. |
| 26 | `qgis_stable101_r40_dissolve_overlap` | `accept_recovered` | The function performs one dissolve by the controlling attribute and returns that result, with an empty-result fallback. The earlier unsupported overlap-resolution omission was removed. |
| 27 | `qgis_stable101_r40_priority_stack` | `defer_dynamic_loop_cardinality` | Difference, cleanup, fix, and union calls execute across a priority loop with first-iteration exceptions and failed-union skips. Static call-site order cannot encode the runtime repetition count. |
| 28 | `qgis_stable101_r48_protected_join` | `accept_recovered` | The protected-area layer is reprojected to EPSG:2154 and used directly as the spatial-join layer for buildings. Boolean assignment remains downstream low-level logic. |
| 29 | `qgis_stable101_r48_overlap_groups` | `accept_recovered` | Multi-intersection is a valid independent intermediate step that produces building self-intersection relations; grouping and geometry merge remain explicit downstream omissions. |

## Proposed batch result

- `accept_recovered`: 7
- `defer_dynamic_loop_cardinality`: 2
- `reject`: 0
- formal human fields changed for rows 21-29: 0
- additional training rows granted: 0
