# QGIS Planner Benchmark Expert Proposal Human Approval v1

Date: 2026-07-29

Status: four human decisions recorded; three proposals admitted to Gate 3 and
one returned for revision.

## Scope

The queue contains exactly four parameter-free proposals that passed Gate 1,
independent QGIS graph review, Gate 2 zero-overlap checks, and four-layer
canonical deduplication: `expert-v1-001`, `expert-v1-006`, `expert-v1-007`, and
`expert-v1-008`.

`expert_human_approval_queue_v1.jsonl` is machine-generated and includes the
exact `processes + links` snapshot, graph SHA-256, Gate 2 exclusion-ledger hash,
and technical review references. Its human fields remain null because it is an
immutable queue snapshot. `expert_human_approvals_v1.jsonl` is the separate
decision authority and contains four hash-bound decisions.

## Human Decision Contract

One independent QGIS expert must create one decision row per proposal with:

- `decision`: `approve`, `reject`, or `return_for_revision`;
- the exact queue-record, graph, and Gate 2 hashes;
- a non-empty human approver ID, timestamp, and rationale;
- `approver_kind=human_qgis_expert`;
- `qgis_expertise_attested=true`;
- `conflict_of_interest_declared=false`.

The human approver ID cannot equal either technical reviewer ID. Duplicate
decisions, stale hashes, AI reviewer identities, missing expertise attestation,
or any non-pending/overlapping proposal fail closed. An approval changes only
admission metadata; it cannot modify `processes` or `links`.

The v1 state machine permits exactly one authoritative decision row per
proposal. A second supplied expert identity was therefore not duplicated into
the machine ledger: duplicate rows would fail closed as
`approval_duplicate_decisions`. The first listed independent expert,
`qgis-expert-01`, is the recorded decision authority.

## Recorded Decisions

- `expert-v1-001`: `approve`;
- `expert-v1-006`: `approve`;
- `expert-v1-007`: `approve`;
- `expert-v1-008`: `return_for_revision`.

The final segment of `expert-v1-008`,
`dissolve -> multiparttosingleparts -> centroids -> collect`, is type-compatible
but not demonstrably necessary without a task intent and output constraint.
The proposal remains valuable as a long-chain revision candidate, but it is not
admitted supply until semantic closure is independently reviewed and approved.

This is not an ontology conflict. Stable101 is a platform-independent semantic
taxonomy: `L3_02_03_05 Collect Features` intentionally admits
`native:collect`, `native:dissolve`, `gdal:dissolve`, and
`native:promotetomulti`. Multiple QGIS operators may therefore share one L3.

## Current Authority

- Queue rows: 4
- Human decisions: 4
- Human-approved proposals: 3
- Returned for revision: 1
- Gate 3 admitted expert proposals: 3
- Queue artifact SHA-256: `c77aff1e829217253abbbfa5c2330993292a4ad614c308ce497a1e49bb015ad1`
- Decision-ledger SHA-256: `77b575e4c8900c30a3fa9ae440a457431fc486f91fb2f9c28835fc6111f99b42`
- Expert-proposal ledger SHA-256: `0c25850737d13f7daa897d09d1e3b62582a10daedad3c9ca57ee582ad38cdf82`

Only the three valid approvals enter Gate 3. The returned proposal remains
`proposal_only`; no decision creates a benchmark split or opens Gate 4.
