# QGIS Processing 177-row Train-only Delivery

## Decision

The cumulative Processing authority is now materialized as one usable train-only
JSONL. This closes the ledger-to-dataset gap; it does not grant validation/test use,
production merge, or a training run.

Final training input:

`source_replay_v1/source_verified_train_v1.jsonl`

## Composition

| Source package | Rows |
|---|---:|
| Base unified Processing authority | 107 |
| Stable106 increment | 9 |
| Top20 existing-L3 increment | 1 |
| Line-intersections correction | 1 |
| Processing second batch v3 | 47 |
| Stable110 alias increment | 3 |
| Corrected runtime-parameter increment | 4 |
| Literal-alias increment | 4 |
| Corrected custom-scope increment | 1 |
| **Total** | **177** |

## Verified Gates

- Cross-package deduplication: 177 input, 177 canonical; zero source-region,
  call-graph, or exact-training-pair suppressions.
- Identity: 177 unique sample IDs, source regions, and call graphs; 150 unique
  source SHA256 values.
- Diversity: 160 normalized DAGs, 129 operator sequences, and 117 L3 sequences.
- Mapping: every operator/L3 pair matches the corrected 153-operator stable110
  mapping; every L3 code/token pair matches stable110 tokens 0-109.
- Task schema: non-empty task name/description, exact `task_metadata` agreement,
  aligned operator/L3/token sequences, one unified training schema.
- Source replay: 150/150 remote files verified by current SHA256, covering 177/177
  rows. Two stale model-tutorial paths were relocated to `downloaded_scripts 清洗后`
  and matched their expected hashes exactly.
- Real V4 smoke: 177/177 rows loaded by `TaskConditionedL3DatasetV4`; 12 batches,
  finite weighted loss and gradients, no checkpoint, no training.

## Boundaries

- `split=train_only_qgis_unified_pilot`.
- Validation/test eligibility remains false.
- Production merge remains not granted.
- No LLM was used to infer chains or descriptions.
- Next Processing stage must add at least 23 independently admitted rows before the
  200-300 delivery gate is reached; quality gates remain unchanged.
