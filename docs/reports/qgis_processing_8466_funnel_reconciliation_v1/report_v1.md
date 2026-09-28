# QGIS Processing 8,466-row funnel reconciliation v1

Date: 2026-08-02

## Correction

The 8,471 source rows used by the custom implementation resolver are a lookup
index searched for implementation definitions. They are not 8,471 workflow
candidates, and the 177-row Processing authority is not their conversion output.

The 8,466-row resolution authority is also heterogeneous:

| Primary layer | Rows | Correct processing lane |
| --- | ---: | --- |
| Explicit Processing catalog miss | 3,163 | provider/operator recovery, mapping, description, dedup |
| Dynamic or blank Processing ID | 445 | static ID recovery, then the same Processing gates |
| Processing algorithm implementation or custom | 4,858 | inspect implementation boundary; usually API-pattern/custom logic |

Of the 4,858 implementation/custom rows, 4,705 define `processAlgorithm`, but
only nine contain embedded Processing calls and only two contain an embedded
multi-step Processing chain. The remaining 4,849 therefore cannot be counted as
failed `processing.run()` conversions. They require low-level API/custom task
boundary recovery.

The custom implementation resolver scanned 8,471 source-index rows and found
167 matching instances / 97 implementation variants for its target IDs. Its
zero-net-new closure is valid only for that target-family lane; it does not close
all 4,858 implementation/custom records.

## Why the full replay showed only 38 accepted

The unified 8,466 replay was a routing and invariant check. It carried forward
38 rows from the train authority available at that time, then marked 8,284 rows
deferred, 70 duplicate, and 74 excluded. It did not run a complete custom/API
task-boundary converter over all deferred rows. Its 38 rows are therefore not a
conversion yield and must not be compared with 8,466 as an acceptance rate.

## Current 177-row count ledger

| Component | Delta | Cumulative |
| --- | ---: | ---: |
| Unified Processing base | 107 | 107 |
| stable106 increment | +9 | 116 |
| top-20 existing-L3 increment | +1 | 117 |
| `lineintersections` correction | +1 | 118 |
| Reviewed second batch | +47 | 165 |
| stable110 alias increment | +3 | 168 |
| Runtime-parameter description recovery | +6 | 174 |
| Literal-alias description recovery | +4 | 178 |
| Invalid semantic mappings revoked | -2 | 176 |
| Custom-scope `filterstructures` increment | +1 | 177 |

This is a component count ledger. The next required data-delivery gate is to
materialize one hash-bound 177-row union, rerun cross-component deduplication,
and verify every row's source, task description, operator/L3 sequence, and
train-only schema. Only that union is a deliverable dataset.

## Correct next action

Do not switch to the API pool merely because 177 is below 200, and do not claim
that frozen stable110 makes 200 unreachable. First:

1. Materialize and verify the current 177-row Processing union.
2. Reconcile the remaining 3,163 catalog-miss and 445 dynamic-ID records under
   the latest rules, with exact source and dedup accounting.
3. Route the 4,858 implementation/custom records explicitly: the nine embedded
   Processing cases stay in the Processing lane; the other implementation bodies
   move to API-pattern/custom task-boundary recovery without being counted as
   Processing failures.

No LLM, training run, taxonomy relaxation, or production merge is authorized by
this reconciliation.
