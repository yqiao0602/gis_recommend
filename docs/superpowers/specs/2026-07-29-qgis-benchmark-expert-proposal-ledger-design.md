# QGIS Planner Benchmark Expert-Authored Proposal Ledger

## Scope

This design covers only the proposal layer for the formal QGIS planner
benchmark. It does not create development, final, refusal, or sealed gold rows.
It does not modify GEE or QGIS training-data authorities. Existing stable101
taxonomy, strict catalog, operator mapping, and Gate 2 exclusion ledger are
read-only inputs.

## Problem

Gate 3 currently has 146 valid `qgis_source_backed` candidates, zero
`expert_authored` candidates, and insufficient raster, branch, one-step, and
long-graph supply. The current candidate builder cannot represent an
independently authored graph, so expert supply must be designed as a separate
ledger before it can be reviewed or counted.

## Design Goals

- Represent expert-authored parameter-free QGIS graphs without pretending they
  came from source code.
- Keep proposals separate from admitted candidate supply and sealed benchmark
  rows.
- Require every process to be a strict-catalog, stable101 headline operator.
- Make the intended Gate 3 strata explicit: anchor family, modality, topology,
  and graph size.
- Preserve enough provenance and review evidence to replay Gate 2 overlap checks
  before admission.
- Fail closed on unsupported operators, incomplete links, parameters, task text,
  unresolved modality, or missing independent review.

## Non-Goals

- No LLM generation or model-assisted graph completion.
- No inference from GEE code into a QGIS graph without independent QGIS review.
- No automatic promotion based on quota pressure.
- No task descriptions, concrete datasets, field names, thresholds, paths, or
  source snippets in the proposal ledger.
- No changes to stable101 taxonomy or production vocabulary.

## Proposal Schema

Each JSONL record uses schema
`gis_recommend.qgis_benchmark_expert_proposal.v1`:

- `proposal_id`: deterministic ID from canonical graph and proposal authoring
  batch; immutable once emitted.
- `authoring_batch_id`: versioned batch identifier, not a person identity.
- `provenance_class`: always `expert_authored`; optional `inspiration_class`
  records `none`, `qgis_pattern_reference`, or `gee_semantic_reference`.
- `processes`: ordered objects with `process_id`, strict provider-qualified
  `operator_id`, and stable101 L3 code. No parameter fields are allowed.
- `links`: directed `source_process_id` to `target_process_id` edges only.
- `parameters_included`: must be `false`.
- `quota_anchor_l3` and `covered_l3`: derived only from the listed stable101
  L3 codes.
- `modality`, `topology`, and `graph_size_stratum`: deterministic values from
  the graph and strict catalog.
- `gate1_status`: `passed` only when every operator is headline-eligible and
  stable101-mapped.
- `gate2_status`: initially `pending`; becomes `passed` only after the same
  nine-index exclusion check used by the source-backed builder.
- `graph_review_status`: `unreviewed`, `independent_reviewed`, or `rejected`.
- `review_refs`: IDs of independent graph reviews; empty until review exists.
- `supply_admission`: initially `proposal_only`; only
  `gate3_candidate_admitted` can enter the candidate supply ledger.
- `training_admission`, `validation_eligible`, `test_eligible`, and
  `production_merge`: permanently false/closed in this layer.

The schema rejects `task_text`, `task_description`, `source_path`,
`source_snippet`, `parameter_facts`, and concrete data identifiers.

## Review Contract

Independent strict-QGIS graph review must verify:

1. Every operator ID exists in the Gate 1 strict catalog and maps to the listed
   stable101 L3.
2. Links form one connected, acyclic directed graph with valid process IDs.
3. The graph is executable in principle without relying on omitted parameters
   to change operator identity or topology.
4. Modality, topology, and graph-size labels match deterministic recomputation.
5. The graph is not a copied or near-duplicate authority already indexed by
   Gate 2.
6. Any GEE inspiration is treated as semantic inspiration only and does not
   provide QGIS graph authority.

Each review records reviewer ID, review timestamp, decision, checked operator
IDs, checked links, modality/topology/size verdicts, exclusion verdict, and a
reason for rejection or required revision. A single review is not enough for a
complex branch, multi-input merge, or graph with an alternative subgraph;
those require a second independent review before admission.

## Admission Flow

`proposal -> schema validation -> Gate 1 authority -> deterministic graph
profile -> independent graph review -> Gate 2 nine-index overlap check ->
four-layer proposal dedup -> Gate 3 candidate supply`

Admission is monotone and fail-closed:

- `proposal_only` rows are never counted in family supply.
- A failed or missing review cannot be overridden by family quota needs.
- A Gate 2 collision rejects the proposal or keeps it as an audit sidecar; it
  cannot be relabeled as expert-authored to bypass the collision.
- Candidate admission does not generate task text or open any benchmark split.
- Only after the combined pool satisfies family, provenance, modality, topology,
  and graph-size constraints may the Gate 3 roster be proposed.

## Gate 3 Accounting

The expert ledger reports both proposal counts and admitted counts separately.
Supply calculations use only rows with:

- `graph_review_status=independent_reviewed`;
- `gate1_status=passed`;
- `gate2_status=passed`;
- `supply_admission=gate3_candidate_admitted`; and
- unique source-independent graph and authority keys.

The existing 146 source-backed rows remain unchanged. Expert proposals are
added as a disjoint provenance class and must supply the final-core expert
share without being counted as QGIS source-backed. Gate 3 remains failed until
the aggregate pool satisfies all exact quota and reserve constraints jointly.

## Artifacts

The implementation will create only proposal/review artifacts at first:

```text
benchmarks/qgis_planner_v1/authority/
  expert_proposals_v1.jsonl
  expert_proposal_reviews_v1.jsonl
  expert_proposal_summary_v1.json
```

No `development/`, `final_core/`, `extension/`, `refusal/`, or sealed gold file
is created by this phase.

## Verification

- Unit tests cover schema rejection, stable101/headline enforcement, graph
  connectivity and acyclicity, deterministic strata, prohibited fields,
  review-state transitions, and Gate 2 collision handling.
- Rebuilding the proposal ledger from the same authoring batch is byte-stable.
- A proposal-only ledger cannot change the existing Gate 3 candidate summary.
- An admitted expert row is counted only after independent review and a clean
  nine-index Gate 2 check.
- All training, validation, test, production, and LLM flags remain closed.

## Open Decision

The first implementation batch should target strata that are currently absent
or under-supplied: raster, branch/multi-output, one-step, four-to-six, and
seven-plus graphs. The batch must be reviewed as proposals and may remain
insufficient without any synthetic padding.
