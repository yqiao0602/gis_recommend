# Raw-source candidate review v1

The 13 structural candidates from the 200-source server pilot were inspected
against their original `/home/yll` source files and call-site context.

| category | count | records |
|---|---:|---|
| complete-workflow candidate | 1 | `d8d9d4672d610dfd33a1b7df` |
| implementation/subworkflow candidate, needs recovery | 4 | `bb18e19d…`, `736bfb87…`, `05c8182a…`, `c9e0d269…` |
| dynamic call, defer | 3 | `9fb3db94…`, `187931b4…`, `c8c01552…` |
| generic wrapper/CLI, reject for workflow corpus | 4 | `7b7decf8…`, `d2ffe1f0…`, `41f7c46d…`, `9819fffc…` |
| detector false positive | 1 | `73f141bc…` |

No row is admitted to L3, training, authority, validation, or benchmark. The
fallback calls in the two vector-tile implementations are explicitly not counted
as separate workflow steps. The full decisions are in `adjudication_v1.json`.
