# QGIS Processing 180-row Train-only Delivery

## Decision

This package superseded the 177-row Processing delivery as the formal stable110
train-only authority at this stage. It is now historical provenance superseded by
the stable120 210-row source-verified delivery. Three source-replayed stable110 local workflows were
salvaged from parents routed by the Snap proposal; none of the three contains
`native:snapgeometries`, so they are not stable111 training evidence.

Final training input:

`source_replay_v1/source_verified_train_v1.jsonl`

SHA256: `df7d793acdc9b8b62b06cfb8bb7ee33b13c9a4aeec905c380f17db3b1a1061ef`

## Composition

| Source package | Rows |
|---|---:|
| Prior formal Processing authority | 177 |
| Stable110 split salvage increment | 3 |
| **Total** | **180** |

## Verified Gates

- Cross-pool deduplication: 180 input, 180 canonical; zero source-region,
  call-graph, or exact-training-pair suppressions.
- Identity: 180 unique source regions and call graphs across 152 source SHA256 values.
- Diversity: 163 normalized DAGs, 132 operator sequences, and 120 L3 sequences.
- Mapping: all rows match the corrected stable110 operator mapping and token IDs 0-109.
- Source replay: 152/152 current server files verified by SHA256, covering 180/180 rows.
- Real V4 smoke: 180/180 rows, 12 batches, finite weighted loss and gradients,
  no checkpoint, no training run.

## Snap Boundary

- Ten fidelity-pass multi-step units from the Snap-routed split replay contain only
  stable110 operators and deduplicate to the three rows delivered here.
- All seven multi-step units that actually contain `native:snapgeometries` remain
  description-fidelity deferred.
- Formal mapping authority remains stable110. stable111 remains proposal-only and
  emits zero formal training rows.
- `grass7:v.clean#tool=snap` remains parameter-conditioned deferred and is not an
  unconditional alias of `native:snapgeometries`.

Validation/test eligibility and production merge remain closed. No LLM was used.
