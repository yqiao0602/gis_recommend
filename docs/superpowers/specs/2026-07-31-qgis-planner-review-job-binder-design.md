# QGIS Planner v0.1 Review-Job Binder Design

## Goal

Make independent QGIS DAG reviews schema-safe without asking reviewers to copy
graph identity fields. Reviewers decide semantics; deterministic code binds
those decisions to the immutable 52-DAG queue.

## Minimal Architecture

Extend the existing adjudicator instead of adding a review framework. It emits
deterministic review jobs from the queue and binds reviewer drafts back to those
jobs. One generated JSONL authority stores the jobs; the existing formal review
ledger continues to store bound semantic reviews.

Each review job contains a deterministic `review_job_id`, queue hash, canonical
graph ID/hash, topology, exact process IDs, reviewer ID, and fixed review time.
Each draft contains only `review_job_id`, decision, task intent, output
constraint, process necessity, type verdict, and rationale.

## Type Compatibility Contract

`type_compatibility_attested=true` means only that the reviewer completed the
type-compatibility check. Its outcome is recorded separately as:

```text
type_compatibility_verdict=compatible|incompatible|uncertain
```

An `approve` decision requires `compatible`. `reject` and
`return_for_revision` may use any of the three explicit verdicts. This permits
a reviewed, type-incompatible graph to be rejected without falsely stating
that the check was not performed.

## Binding And Failure Rules

The binder copies queue-controlled identity and provenance fields into the
formal review record and fixes `reviewer_kind`,
`independent_review_attested=true`, and
`type_compatibility_attested=true`. It fails closed for an unknown or duplicate
job, stale queue hash, wrong reviewer, missing or extra process IDs, malformed
draft, invalid verdict, or approval with a non-compatible verdict.

The binder does not accept aliases, infer a verdict, repair reviewer semantic
fields, or weaken the existing adjudicator. Existing hash and reviewer
independence checks remain authoritative.

## Verification

Tests must first demonstrate failure under the old contract, then cover all
three verdicts, the approval constraint, deterministic job generation, binding,
and fail-closed identity/process checks. The real queue must generate the same
job bytes twice. No formal review record is admitted until it passes both the
binder and existing adjudication state machine.

## Scope

This design changes only v0.1 DAG-review authority. It does not alter graph
gold, stable101, candidate supply, task text, Gate 2, training data, GEE data,
or roster selection.
