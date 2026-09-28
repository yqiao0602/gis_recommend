# GEE replacement Batch13 v8.9.9 proposal census

Using the reviewed and deduplicated 177 task-text candidates, the frozen
`build_gee_complete_workflow_expansion_batch.py` generated a proposal-only census.
The cumulative existing semantic authority combined Batch11 and Batch12 rows and
was hash-bound before execution.

| Terminal state | Count |
|---|---:|
| Canonical task-text candidates | 177 |
| Reviewed identities | 50 |
| Remaining identities | 127 |
| Reviewed-source overlap | 26 |
| Existing or batch duplicate | 25 |
| Proposal-eligible | 76 |
| Semantic fail-closed | 0 |
| Length deferred | 0 |

The 76 rows remain `pending_sampling_audit`; no export or training row was emitted.
The proposal audit packet contains 35 source-disjoint representatives with support
across the available risk strata (`external_dynamic=12`, `long_or_repeated=7`,
`multi_dataset_private=9`, `no_temporal_operation=7`). The `other` and
`spatial_omission` strata have zero available representatives in this batch.

Snapshot A was copied to B. Proposal candidates, remaining ledger, summary, and
hash ledger were byte-identical (proposal SHA256
`7af7a9319728937580a1453609fdbeadfdbff658efb0764a1c116cb58e82f468`).
Validation/test, production merge, and train-only admission remain closed pending
the next sampling-audit decision.
