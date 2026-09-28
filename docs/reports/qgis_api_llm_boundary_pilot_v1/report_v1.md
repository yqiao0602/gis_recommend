# QGIS API LLM Boundary Pilot v1

Date: 2026-08-11

## Scope

This isolated pilot tested whether `deepseek-v4-flash-0731` can propose local
API task boundaries and dependency edges for 100 source-disjoint review rows.
The input was split into 50 calibration and 50 frozen holdout rows. Each
request contained only the bounded evidence window and AST-derived step facts;
no full source file, L3 label, description, or training row was sent.

## Result

| split | rows | schema/line/edge validated | invalid proposal | HTTP failure |
|---|---:|---:|---:|---:|
| calibration | 50 | 40 | 1 | 9 |
| holdout | 50 | 39 | 1 | 10 |
| total | 100 | 79 | 2 | 19 |

The two invalid proposals both selected multiple sinks. All 79 validated
proposals cited existing step indices and used the constrained JSON schema.
`training_rows_emitted=0` and `training_admission=not_granted_llm_boundary_pilot`.

## Interpretation

This proves the endpoint and constrained proposal protocol are operational. It
does **not** prove semantic precision: local validation currently checks that
the proposed calls, sink count, and edge references exist, but does not yet
prove every data-flow edge or task boundary is correct. The 19 HTTP failures
are an execution reliability issue and must be retried with bounded backoff
before measuring model recall.

The pilot is therefore candidate-only. No rule promotion, L3 mapping,
description generation, deduplication, authority merge, or training action is
authorized from this result.

## Next gate

1. Retry only the 19 failed requests with exponential backoff and the same
   frozen prompt hash.
2. Have an independent reviewer adjudicate all 79 validated proposals and the
   2 invalid cases, separately for calibration and holdout.
3. Promote a boundary rule only if holdout has zero wrong-chain/chain-truncation
   cases and at least 95% semantic precision; otherwise keep the LLM route
   isolated and strengthen the deterministic data-flow validator.

## Retry And Independent Audit Update

The latest complete request ledger contains 80 validated candidates, 3 invalid
proposals, and 17 HTTP failures. Those 17 were retried with the same frozen
prompt hashes: 2 became validated candidates, 1 was rejected for multiple
sinks, and 14 remained HTTP failures. The current candidate-only population is
therefore 82/100, split 41 calibration and 41 holdout. Earlier retry artifacts
are superseded by this latest complete ledger.

An independent source-backed audit packet compares every proposal with the
frozen deterministic boundary evidence. It flags 8 proposals that omit a
baseline step and 52 whose dependency-edge set differs from the baseline. The
stricter data-flow checks found no unsupported variable edges or reverse edges;
one proposal omitted its sink from the selected steps and one boundary span did
not cover all selected call lines. These are review signals, not automatic
correctness decisions: a narrower subgraph can be correct, but neither
difference may be promoted without source review. Holdout is read-only for
rule tuning.
