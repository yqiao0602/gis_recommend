# GEE Batch12 v8.9.9 Snapshot-Authority Replay and Audit

## Decision

The Batch12 failure was caused by execution-authority drift. The original AST/DAG
replay imported the live DAG gate (SHA256 `4726070472a56e46279ce36f437ead97ea8e9805d2e3522d22442a993fd507b9`),
which did not contain the already-frozen control-flow lineage predicates. The
v8.9.9 snapshot gate is SHA256
`4cb297069cd40fedebe981044fe81310f38587b457583f650d228cdfda9b3193`.

The snapshot was used without changing the predicate or adding a permissive
recovery rule. All 13 previously audited critical sources fail closed in a
directed replay, including loop-carried reassignment, list accumulation, and
map/helper return cases.

## Full Replay

The full 5,000-source Batch12 replay used the snapshot scripts, snapshot `src`,
the snapshot parser, Node 20, and the read-only source root
`/home/yll/GEE/Data`.

| Stage | Result |
| --- | --- |
| AST/DAG | 4,994 success / 6 parse failures; 135 passed, 105 partial, 4,754 fail-closed sources |
| Fidelity | 467 accepted workflows from 218 sources |
| Typed mapping | 219 mapping-complete workflows from 112 sources |
| Facts | 218 fact bundles; 162 deduplicated task-text candidates from 97 sources |
| Proposal | 70 pending proposals from 41 eligible sources; 17 duplicate sidecars; 25 reviewed-source overlaps |

All A/B business artifacts and hash ledgers are byte-identical. The proposal
ledger SHA256 is `772218209cae88a9a407bd51b9ee6c1e889a210b37bfd59c816445adc7db3223`.
No training rows were emitted.

## Replacement Audit

After the fail-closed repair only 41 eligible source hashes remained. A 50-source
sample would require reusing rejected or previously reviewed sources, so the
replacement package audits all 41 available sources exhaustively. Source hashes
were checked against `/home/yll/GEE/Data`; the reviewed audit contains 41 rows.

| Metric | Result |
| --- | --- |
| Full-source reviewed rows | 41 |
| Pass / fail / critical | 41 / 0 / 0 |
| Point precision | 1.0 |
| Wilson 95% lower bound | 0.9143324298155681 |
| Evaluator decision | `passed_for_larger_source_disjoint_replay` |

The evaluator profile is
`gee_complete_workflow_batch12_v8_9_9_snapshot_authority_exhaustive_41`.
Evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/`.

## Admission Boundary

This result authorizes the next hash-bound export and real V4 loader/loss/backward
smoke only. Batch12 remains outside the train-only authority until both gates pass;
validation/test eligibility, production merge, and model training remain closed.
