# GEE Workflow Source-Backed Facts And Task Text Design

## Goal

Convert the 266 receiver-typed, mapping-complete GEE workflows into auditable
workflow fact bundles and chain-faithful task-text candidates. Keep the 232
core/support conflicts, 42 L3 gaps, and 6 raw-call gaps in independent recovery
queues so they do not block this production path.

## Fixed Authority

- A row is identified by `(source_sha256, workflow_id)`, not by source SHA alone.
- The typed `canonical_operator_sequence` and `l3_sequence` are frozen targets.
- Every typed row must join exactly once to its fidelity row and SHA-keyed ESTree
  AST. Ordinals, raw callees, source locations, definition IDs, and Export sink
  must agree before facts are extracted.
- Whole-script facts descriptions and variable-name semantics are not task-text
  authority.
- `/home/yll` is read-only. Large replay artifacts are written under `/home/qy`.

## Chosen Approach

Use a deterministic-first hybrid pipeline. A pure AST-backed builder extracts
five evidence-bearing fact families, then a deterministic renderer produces a
conservative baseline text whose clauses reference fact IDs. A later LLM rewrite
may be evaluated separately, but it cannot alter the frozen chain or introduce
claims absent from the fact bundle.

Rejected alternatives:

1. Reuse whole-script descriptions. A source may contain multiple independent
   Export workflows, so the description can mix unrelated branches.
2. Ask an LLM to summarize source directly. This reintroduces chain edits,
   unsupported geography/time claims, and non-reproducible output.
3. Require all five fact families to be fully static. This would reject useful
   workflows merely because time or region is dynamic even when the complete
   transformation chain and output sink are proven.

## Fact Contract

Each fact has a stable `fact_id`, `fact_type`, normalized value, AST evidence
location, and `text_use` policy. The five families are:

- `dataset_facts`: `ee.Image`, `ee.ImageCollection`, `ee.FeatureCollection`, and
  related constructor identifiers inside the exact workflow closure. Private
  assets remain evidence but are redacted in text.
- `temporal_facts`: literal `filterDate`, date, calendar, and temporal-filter
  arguments. Dynamic values are recorded as omissions, never inferred.
- `spatial_input_facts`: literal geometry/assets, proven bound references, or
  external source-defined identifiers. External/opaque regions may only render
  as "source-defined region".
- `transformation_facts`: one fact per frozen retained call, preserving ordinal,
  raw callee, canonical operator, L3, receiver type, source location, and safe
  literal arguments. Length and order must exactly equal the frozen sequences.
- `output_facts`: exact Export sink kind and safe literal fields such as
  description, scale, folder, prefix, asset ID, CRS, and format. Output facts are
  recorded even when Export is not represented in the target L3 chain.

Unknown facts are represented in `known_omissions`; they are not invented or
silently promoted to static values.

## Text Contract

Task text describes the exact workflow-level target, not the whole source file.
The renderer uses only text-allowed facts and records `used_fact_ids` per clause.
It names public datasets when unambiguous, uses generic source imagery/data when
private or multiple, includes literal temporal bounds when exact, calls unresolved
regions source-defined, summarizes the frozen transformation sequence without
adding/deleting/reordering operations, and describes the output as a produced or
exported image/table/video.

For long chains, the text remains faithful by grouping consecutive repeated
operators while retaining an explicit clause-to-ordinal ledger. Chains longer
than the model's 98-content-token limit are routed to a length sidecar and are
not admitted to the V4 package.

## Gates And Outputs

The builder publishes atomically:

- `workflow_fact_bundles.jsonl`
- `task_text_candidates.jsonl`
- `fact_fail_closed.jsonl`
- `task_text_duplicates.jsonl`
- `risk_review_packet.jsonl`
- `summary.json`, `report.md`, and `hash_ledger.json`

Admission stages are mapping join, source/fidelity/AST verification, fact
construction, text-fact fidelity, normalized text plus L3-chain deduplication,
semantic schema validation, and risk-stratified calibration. Candidate generation
does not itself grant validation, test, production merge, or model training.

## Risk Calibration

Review selection is source-disjoint and stratified by helper/control-flow source,
chain length, repeated operators, multiple/private/dynamic datasets, omitted time,
external or opaque spatial input, uncommon Export form, and uncommon template
family. A review failure changes the deterministic rule and triggers replay; it
is not repaired manually row by row.

## Verification

- Unit tests cover exact closure scoping, static/dynamic literals, privacy
  redaction, spatial fallbacks, transformation order, Export variants, text-fact
  traceability, deduplication, and fail-closed joins.
- Replay twice against the same frozen inputs and compare all artifact bytes.
- Verify conservation across candidate, duplicate, and fail-closed partitions.
- Run the semantic train-row validator on admitted candidates and the real V4
  loader/loss smoke only after explicit train-only admission.

## Scope Boundaries

This phase changes only GEE data-processing code, tests, GEE reports/context, and
the GEE section of `task_plan.md`. It does not change QGIS, benchmark, model
training, `outputs/`, `outputs_v2/`, or legacy `train11397_*` artifacts.
