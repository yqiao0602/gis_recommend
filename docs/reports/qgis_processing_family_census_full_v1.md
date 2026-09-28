# QGIS Processing Family Census v1

The census was run on the complete normalized Asset Miner ledger. It covers
all 1,236 `processing_workflow` candidates, including Processing-shaped rows
from either manifest pool, and does not create subworkflow rows or training
data. It reports four views: exact full workflow, contiguous 2-step and 3-step
subworkflow, and 2-step transition.

## Population

| family level | families (support >= 2) |
|---|---:|
| exact workflow | 363 |
| 2-step subworkflow | 2,427 |
| 3-step subworkflow | 3,113 |
| transition | 2,427 |
| **total family records** | **8,330** |

Each family records support, unique source and parent counts, distinct full
parent structures, provider spread, dynamic count, read-only L3 resolvability,
and known provider/I/O contract status. Repeated same-operator families are
marked and receive a priority penalty. The priority score is a scheduling
heuristic, not a quality or admission score.

## Highest-value next lane

The leading non-repeated, contract-complete family is:

`native:dissolve -> native:multiparttosingleparts`

It has support 86, 40 unique sources, 40 parents, and 18 distinct full parent
operator sequences; both operators are resolvable through the current L3
authority and the vector I/O contract is known. The next candidate is
`native:buffer -> native:clip` (support 54, 36 sources, 19 structures, fully
resolvable L3/I/O). The already-calibrated
`native:clip -> qgis:multiparttosingleparts` family has support 7 and is not a
priority expansion lane.

Task and normalized-template counts are explicitly marked unavailable from the
Asset Miner normalization ledger; they must be measured during family review,
not inferred from source count. Full family JSONL and hash ledger remain on the
server at `/home/qy/system_redesign/diagnostics/qgis_processing_family_census_full_v1/`;
the copied summary is `qgis_processing_family_census_full_v1_summary.json`.

No L3 authority, training, validation/test, or production state was changed.
