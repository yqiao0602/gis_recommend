# GEE Semantic Authority Technical Review Proposal

Date: 2026-07-28

This is a technical review proposal, not human adjudication or training
admission. The review unit is one `source_sha256 x semantic pattern`, not one
local-unit row.

## Scope

- Census rows: 83
- Semantic accepted after dependency closure: 57
- Fail-closed: 26
- Independent accepted source authorities: 12
- Authority-pattern representatives reviewed: 14
- Training rows emitted: 0

The dependency-closure rerun removed `concat_irr_agVV@1` and
`concat_irr_agVH@1`: both depended on mean/clip units whose `irr_ag` region was
unresolved. They remain in the fail-closed census with
`semantic_dependency_not_accepted`.

## Representative Review

| Source | Representative | Pattern | Technical proposal | Note |
|---|---|---|---|---|
| `script_55543` | `s2mean@1` | annual mean/clip | complete core | multiline direct assignment |
| `script_85170` | `img@1` | annual mean/clip | complete core | `ee.Image(mean())` wrapper |
| `script_69315` | `image@1` | annual mean/clip | complete core | direct dependencies present |
| `script_244591` | `image_2016VV@1` | year/polarization preprocess | complete core | full collection/filter/select chain |
| `script_244591` | `_water2019@1` | annual mean/clip | complete core | accepted preprocess and region dependencies |
| `script_244591` | `concat_waterVV@1` | polarization concat/select | complete core | four accepted upstream mean/clip units |
| `script_64651` | `S1mean@1` | annual mean/clip | complete core | `ee.Image(mean())` wrapper |
| `script_45720` | `clip@1` | annual mean/clip | complete core | generic target name; use chain facts for text |
| `script_113500` | `S1mean@1` | annual mean/clip | complete core | `ee.Image(mean())` wrapper |
| `script_128348` | `data_2019_mean@1` | annual mean/clip | complete core | year-aligned input |
| `script_22213` | `S1_median@1` | annual mean/clip | complete core | misleading target name; source operator is `mean` |
| `script_3457` | `temperature_lake1990@1` | annual mean/clip | complete core | one of six same-source year variants |
| `script_22207` | `collectionVV_mean@1` | annual mean/clip | complete core | polarization-aligned input |
| `script_72069` | `NPP@1` | annual mean/clip | complete core | direct dependencies present |

## Support Gate

| Pattern | Accepted rows | Independent authorities | If all 14 proposals pass human review: Wilson 95% lower | Batch rule |
|---|---:|---:|---:|---|
| annual mean/clip | 43 | 12 | 0.758 for 12/12 | not yet |
| year/polarization preprocess | 8 | 1 | 0.207 for 1/1 | not yet |
| polarization concat/select | 6 | 1 | 0.207 for 1/1 | not yet |

The existing promotion gate is precision >= 0.95 and Wilson 95% lower >= 0.80.
Proposal-row volume must not replace independent-authority support.

## Decision Proposal

- Keep all 57 rows proposal-only and retain the 14 representatives as the human
  review packet. Do not export the 57 rows as training data.
- Task-text generation must use canonical operators and semantic facts, not
  target names such as `S1_median` or `clip`.
- Expand the same source-backed gate to the remaining 8,291 authoritative rows
  outside the 3,106 strict subset. This is the shortest path to determine
  whether any pattern can reach the independent-authority promotion threshold.
- Continue to propagate semantic dependency failures before counting or
  exporting downstream proposals.
