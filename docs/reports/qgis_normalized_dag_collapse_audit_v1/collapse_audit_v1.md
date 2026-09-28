# QGIS normalized-DAG collapse audit v1

This read-only audit compares rows suppressed by the normalized-DAG layer. It does not modify deduplication or training admission.

- Input rows: **107**
- Duplicate groups: **2**
- Duplicate rows: **107**
- Cross-source duplicate groups: **2**
- Groups containing repeated occurrences from one source: **2**
- Potential over-merge signal: **True**

## Group Findings

| family | rows | source SHAs | unique semantic parameter signatures | unique source structures | assessment |
|---|---:|---:|---:|---:|---|
| `native:buffer|native:clip` | 34 | 24 | 10 | 18 | potential_overmerge |
| `native:dissolve|native:multiparttosingleparts` | 73 | 31 | 21 | 34 | potential_overmerge |

## Interpretation

Both groups share the same task, L3 sequence, vector I/O contract, and normalized DAG. They nevertheless contain source-backed parameter variants and different parent-source structures. This is a potential over-merge signal for parameter-aware assets, but it is not by itself a reason to change the current workflow dedup key: the current training-pair contract is task-to-L3 sequence, and the audit does not adjudicate whether parameter variants represent distinct user intent.

The result is therefore **audit required / dedup unchanged**. Parameter-aware grounding or a future parameter asset pool may use the detailed JSONL evidence, while the two workflow survivors remain candidate-only Silver and training rows remain zero.

Detailed row-level evidence is in `duplicate_group_rows_v1.jsonl`; group summaries are in `duplicate_groups_v1.jsonl`.
