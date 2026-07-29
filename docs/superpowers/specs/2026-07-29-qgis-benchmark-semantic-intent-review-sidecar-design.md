# QGIS Planner Benchmark Semantic-Intent Review Sidecar

## Scope

This design adds a review-only semantic evidence layer to the formal QGIS
planner benchmark's expert-authored proposal workflow. It does not alter the
benchmark gold contract, model input contract, Gate 1 taxonomy, Gate 2
exclusion authority, source-backed supply, or any GEE/QGIS training-data work.

The planner's sole scored output remains parameter-free QGIS `processes +
links`. The sidecar itself is never copied into a gold row or used directly as
the evaluated model prompt. A future benchmark task may express the same
reviewed intent in natural language, but only after a separate task-text/gold
fidelity gate.

## Problem

Independent graph review can establish stable101 authority, link validity, and
type compatibility, but those facts do not always establish semantic closure.
`expert-v1-008` demonstrates the gap: its final
`dissolve -> multiparttosingleparts -> centroids -> collect` segment is
executable in principle, yet no recorded purpose proves that aggregating the
resulting points is necessary.

Rejecting every complex graph without this evidence would remove needed supply.
Adding the evidence to gold would contaminate the parameter-free graph-planning
task. The sidecar separates the two concerns.

## Chosen Design

Create a versioned `semantic_intent_review` sidecar with one review record per
proposal revision. The record binds to the immutable proposal graph hash and
contains human-readable audit evidence only:

- `proposal_id` and `proposal_graph_sha256`;
- `task_intent`, stating the intended analytical outcome when evidence exists;
- `output_constraint`, naming the required output geometry/type and
  aggregation semantics without datasets, fields, thresholds, paths, or
  execution parameters when evidence exists;
- `process_necessity`, explaining each process's role in achieving the stated
  outcome when evidence exists;
- `semantic_closure_decision`: `closed`, `return_for_revision`, or `rejected`;
- `reason_codes`, a deterministic list that is empty for `closed` and identifies
  missing or contradictory evidence for non-closed decisions;
- reviewer ID, reviewer kind, timestamp, conflict declaration, expertise
  attestation, and rationale;
- a SHA-256 of the canonical sidecar record.

The primary proposal ledger remains graph-only. It may contain only the
existing parameter-free process and link schema. The semantic sidecar exists
solely for review and admission, and is excluded from candidate supply rows,
future gold outputs, direct prompt export, and primary operator-plus-links
scoring. It may later serve as bounded evidence for independently authored and
reviewed benchmark input text.

## Record Contract

Schema: `gis_recommend.qgis_benchmark_semantic_intent_review.v1`.

Required review constraints:

1. The graph hash must exactly match the current proposal revision. A graph
   edit invalidates prior semantic review.
2. A `closed` decision requires non-empty `task_intent`, `output_constraint`,
   and exactly one `process_necessity` entry for every graph process. Each entry
   must explain a role consistent with the declared intent and output.
3. A `return_for_revision` or `rejected` decision may leave missing evidence as
   null or an empty list, but must include at least one stable `reason_code` and
   a non-empty rationale. Missing evidence must never be represented by filler
   text such as `not provided`.
4. Any supplied intent, output, or necessity text must not contain dataset IDs,
   file paths, source snippets, field names, numeric values, CRS values, or
   execution parameters.
5. Only a `closed` review may be used when seeking human approval.
   `return_for_revision` and `rejected` fail closed and cannot count for supply.
6. The semantic reviewer must be an independent human QGIS expert, distinct
   from the technical graph reviewers. The existing approval reviewer may also
   perform this review only when independence from technical review remains
   true.
7. The sidecar does not substitute for technical graph review, Gate 2
   zero-overlap, proposal deduplication, or human approval.

The v1 semantic review has one authoritative record per proposal revision.
Superseding a `return_for_revision` requires a new proposal ID plus a material
graph revision that produces a new graph hash. Merely renaming the same graph
would be suppressed by canonical graph deduplication. Duplicate same-revision
decisions fail closed.

## Admission Flow

```text
graph-only proposal
  -> Gate 1 + deterministic profile
  -> independent technical graph review
  -> Gate 2 zero-overlap + canonical dedup
  -> semantic-intent sidecar review is closed
  -> independent human approval
  -> Gate 3 candidate supply
```

Simple graphs may remain eligible without a semantic sidecar only while the
v1 policy requires the sidecar for every proposal with at least four processes
and for any smaller graph carrying a reviewer-requested semantic concern. This
preserves prior valid approvals for `001/006/007` without weakening the new
long-chain guard.

## `expert-v1-008` Revision Path

The current `expert-v1-008` stays `returned_for_revision` and `proposal_only`.
It cannot be edited in place or re-approved from the existing record. A
candidate replacement must use a new proposal ID and state a task intent whose
required output is semantically closed. Its graph must be materially revised
to produce a new graph hash, and its necessity records must justify every step,
especially the relationship among dissolve, split, centroid, and any final
aggregation operation. It must then repeat independent technical review, Gate
2, semantic closure review, and human approval.

`L3_02_03_05` remains a valid platform-independent semantic class for both
`native:dissolve` and `native:collect`; the sidecar reviews the chain's task
semantics, not the frozen ontology mapping.

## Alternatives Rejected

1. Add intent fields to the proposal or gold graph: rejected because the planner
   benchmark must remain a parameter-free operator-and-links task, and gold
   should not contain reviewer rationale.
2. Require all proposals to have semantic intent text immediately: rejected for
   v1 because it would retroactively invalidate clearly scoped one-to-three-step
   graphs and delay available supply. The policy is deliberately risk-based.
3. Keep graph-only review for long chains: rejected because type compatibility
   does not prove that every step serves a coherent task.

## Artifacts

```text
benchmarks/qgis_planner_v1/authority/
  expert_semantic_intent_reviews_v1.jsonl
  expert_semantic_intent_review_summary_v1.json
```

The expert proposal hash ledger will include both new artifacts. No
development, final, refusal, or gold artifact is created by this phase.

## Verification

- Reject missing or stale proposal graph hashes, duplicate process IDs, missing
  process coverage, empty rationale, prohibited parameter/data facts,
  non-human reviewers, conflicts, and duplicate same-revision decisions.
- Prove `return_for_revision` cannot reach human approval or Gate 3.
- Prove a `closed` semantic sidecar is required for seven-plus proposals and
  reviewer-flagged semantic concerns, while existing approved one-to-three-step
  proposals remain valid.
- Rebuild sidecar, proposal ledger, and candidate supply byte-stably from the
  same inputs.
- Confirm candidate supply and every future gold row continue to contain no
  intent/output/necessity fields.
