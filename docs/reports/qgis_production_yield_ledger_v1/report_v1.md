# QGIS Production Yield Ledger v1

This is a read-only inventory of existing QGIS packages and candidate packets.
It does not grant admission, alter authority, or modify training/evaluation data.
The machine-readable ledger is `ledger_v1.json`; rerun
`scripts/build_qgis_production_yield_ledger.py` when a new package is added.

## Observed lanes

| Lane | Kind | Rows | Unique sources | Unique lineage groups | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| `aggregate_508` | package | 508 | 392 | 392 | Existing cumulative aggregate; retained for provenance |
| `aggregate_539` | package | 539 | 422 | 422 | Superseding cumulative aggregate; includes 31 isolated rows |
| `processing_delivery_293` | package | 293 | 237 | 237 | Processing-focused cumulative delivery; overlaps aggregate packages |
| `seed_subworkflow_31` | candidate | 31 | 6 | 6 | Candidate-only; source hash is inherited from `seed_source_sha256` |

These are historical/cumulative package inventories, not a first-pass recall
from the 47,852-source census. The aggregate packages are not additive: the ledger reports 392 source-hash
overlaps between 508 and 539, and 235/236 overlaps between the Processing 293
package and the aggregate packages. They must not be summed as new yield.

## Production decision

The fastest next action is not another broad gate or an unconstrained LLM run.
First, reconcile the superseding aggregate against the current target profile
and deduplicate it against the active corpus. Then select one deterministic
family with a bounded replay population and measure accepted rows, review cost,
and coverage gain. The 31 subworkflow packet remains useful as a separate,
reviewed-lineage lane but is not evidence of 31 trainable rows until its
candidate decisions and source provenance are complete.

## Guardrails

- Keep authority, validation/test, benchmark, and production profiles unchanged.
- Do not sum overlapping package counts.
- Treat missing source hashes or pending decisions as deferred, not accepted.
- Report Gold, Silver, other weights, Reject, and Deferred separately.
- Track unique source and parent groups alongside row counts.
