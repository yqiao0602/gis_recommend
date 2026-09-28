# QGIS Asset Semantic Normalization v1 — full ledger

Date: 2026-09-02  
Input: `/home/qy/system_redesign/diagnostics/qgis_asset_miner_full_sharded_v1/qgis_asset_miner_sharded_v1.jsonl`  
Output: `/home/qy/system_redesign/diagnostics/qgis_asset_normalization_full_v1/`

## Scope

This is a deterministic, candidate-only preparation pass over the 47,852-row
Asset Miner discovery ledger. It does not reread or modify `/home/yll`, does not
infer L3, and emits no training rows. Operation names are explicit lexical hints
for routing/review, not authority mappings.

## Census

| normalized asset type | rows |
|---|---:|
| Processing workflow | 1,236 |
| Processing implementation | 1,088 |
| Processing operator | 591 |
| Processing dynamic candidate | 496 |
| API semantic unit | 3,209 |
| API pattern | 4,880 |
| API implementation evidence | 12,407 |
| unresolved | 23,945 |
| **total** | **47,852** |

The API split is based on observed semantic-call cardinality after explicit
method hints; it is not a claim that every API row is a complete workflow.

Source verification covers 47,542 parsed rows. The remaining 310 rows are
deferred at the source-resolution/integrity boundary. Candidate disposition is
23,411 candidate and 24,441 deferred. There are 1,411 unique literal operator
sequences and 1,729 unique hinted semantic sequences.

## Gate routing

| next gate | rows |
|---|---:|
| deferred source or operator resolution | 24,441 |
| implementation boundary review | 12,407 |
| I/O, task, L3 and dedup review | 7,787 |
| semantic review and explicit catalog extension | 3,217 |

The ledger preserves source SHA, parent SHA, operator/API sequence keys, and
candidate-only provenance for every row. Full output hashes are recorded in
`qgis_asset_normalization_full_v1_hash_ledger.json`; the normalized JSONL stays
on the server because it is a large derived ledger.

## Decision

This pass answers “what does the discovered population contain?” and creates a
stable input for the next bounded semantic-recovery lane. It does not authorize
any L3 mapping, Gold/Silver admission, training export, authority merge,
validation/test assignment, or checkpoint.
