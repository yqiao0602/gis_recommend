# QGIS Source-Role Workflow Tiers v1

Date: 2026-08-11

This is a cheap, read-only scoring pass over the frozen 47,852-row source-role
census ledger. It does not reread source files, call an LLM, map L3, emit
training rows, or modify authority.

## Results

| tier | all pools | Processing | API |
|---|---:|---:|---:|
| tier1_multi_step_workflow | 169 | 169 | 0 |
| tier2_single_operator_workflow | 325 | 286 | 39 |
| tier3_processing_implementation | 983 | 982 | 1 |
| api_semantic_knowledge_candidate | 4,737 | 1,263 | 3,474 |
| api_plumbing_evidence_only | 11,655 | 2,139 | 9,516 |
| unclassified_deferred_cheap_filter | 29,673 | 3,332 | 26,341 |
| deferred_source_missing | 310 | 295 | 15 |

All 47,852 rows receive exactly one tier. `training_rows_emitted=0` and
`training_admission=not_granted_role_tier_scoring` are invariant outputs.

## Decision

The next deterministic admission input is the 455 Processing workflow rows
(169 tier1 + 286 tier2), split into multi-step and single-operator tracks. The 39
API-origin tier2 rows remain in the API queue. The 983
implementation rows are an auxiliary dependency corpus and must not be counted
as user workflows. The 4,737 API semantic rows should feed a separate API
knowledge-base/L2-L3 mapping queue. The 29,673 unclassified rows remain
deferred behind cheap source filtering; no unrestricted LLM replay is justified
by this census alone.

The tier counts are a prioritization result, not a train-only yield estimate.
Each selected row still requires source SHA/AST replay, boundary, stable L3,
description fidelity, four-layer deduplication, and V4 loader/loss/backward
gates.

Server output hash ledger: `hash_ledger_v1.json`.
