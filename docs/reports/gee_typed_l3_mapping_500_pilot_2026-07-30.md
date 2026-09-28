# GEE Typed Operator/L3 Mapping Census: 500-Source Pilot

Date: 2026-07-30

## Decision

The ordinal-aligned, receiver-typed canonicalization gate is stable on the frozen
500-source pilot. Of the 546 complete-DAG fidelity candidates, 266 workflows from
131 unique source authorities are mapping-complete. They may enter the next
source-backed task-fact gate, but they are not training rows yet.

The remaining 280 workflows stay fail-closed: 232 contain at least one retained call
whose extractor role is `core` while the canonicalizer classifies it as support, 42
use catalog operators without an admitted L3 mapping, and 6 contain unresolved raw
calls. No evidence-mismatch decision occurred, so the ordinal/AST join itself is not
the current bottleneck.

## Authority

Inputs:

- fidelity candidates:
  `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260730_ordinals_a/accepted_candidates.jsonl`
- AST authority:
  `/home/qy/system_redesign/diagnostics/gee_workflow_dag_pilot500_20260729_run3/ast`
- mapping authority:
  `/home/qy/system_redesign/outputs_v2/id_mappings_v2.json`

Typed census replays:

- `/home/qy/system_redesign/diagnostics/gee_typed_l3_mapping_pilot500_20260730_a`
- `/home/qy/system_redesign/diagnostics/gee_typed_l3_mapping_pilot500_20260730_b`

All six artifacts are byte-identical between the two replays. Input hashes are:

- accepted candidates: `9757cd90e5d264ad78b7db524ed499d6908e6fe73aa01586e6279f26dfa753f5`
- mapping authority: `7d9dde1ed6f36f0f2178d2ec535d9ecdaba9eb86639894581989b10f0b040946`
- AST files: 250 source-SHA-keyed files

## Implementation Contract

`core_call_ordinals` are normalized together with raw callees in the fidelity gate.
For each admitted workflow, the typed gate re-extracts source evidence from the
SHA-keyed AST and requires:

- non-negative, unique, strictly increasing ordinals;
- one-to-one ordinal/chain length alignment;
- a resolved `core` call at every ordinal;
- exact raw-callee agreement;
- source SHA, path, and extractor-version agreement;
- a proven EE receiver and typed canonical operator without family guessing;
- exact catalog presence, non-ambiguous mapping metadata, and an admitted L3 code.

Any retained call classified as support is rejected instead of silently removed.
This preserves workflow completeness until a separate role-boundary rule can prove
that the call belongs in a sidecar rather than the target chain.

The stable primitives now live in
`src/gis_recommend/data/gee_operator_canonicalization.py`. Production typed modules
no longer import the historical P4 CLI script. The old P4 entry point re-exports the
stable public symbols for local compatibility.

## Measured Results

| Measure | Result |
| --- | ---: |
| Workflow decisions | 546 |
| Unique workflow keys | 546 |
| Mapping-complete workflows | 266 (48.72%) |
| Mapping-complete source authorities | 131 |
| Fail-closed workflows | 280 (51.28%) |
| Distinct canonical operators | 158 |
| Distinct L3 codes | 56 |
| Retained call decisions | 7,773 |
| Mapped call decisions | 6,871 (88.40%) |
| Support-classified retained calls | 462 |
| Catalog-without-L3 calls | 223 |
| Unmapped raw calls | 217 |
| Training rows | 0 |

Workflow-level status partition:

- `mapping_complete`: 266
- `support_classified_retained_call`: 232
- `canonical_l3_gap`: 42
- `unmapped_raw_call`: 6
- `evidence_mismatch`: 0

Per-stratum mapping-complete yield:

- linear export: 219/462 (47.40%)
- helper export: 41/72 (56.94%)
- control-flow export: 6/12 (50.00%)

Every one of the 266 mapping-complete rows has a non-empty canonical chain, equal
canonical/L3 sequence lengths, no fail-closed reason, and zero emitted training rows.
The 546-row decision ledger partitions exactly and contains 546 unique
`(source_sha256, workflow_id)` keys.

## Fidelity Regression

Adding `normalized_core_call_ordinals` did not alter semantic dispositions.

- fixed-50 replays:
  `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_fixed50_20260730_ordinals_a`
  and `_b`; seven byte-identical artifacts; 35 passed, 5 duplicates, 74 fail-closed.
- pilot500 replays:
  `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260730_ordinals_a`
  and `_b`; seven byte-identical artifacts; 546 passed, 10 duplicates, 549
  fail-closed.
- old/new workflow status and fail-closed-reason projection hashes are identical:
  fixed-50 `dc65ee65...`, pilot500 `4d979789...`.
- all passed and duplicate rows satisfy ordinal/normalized-chain length equality.

## Verification

- local focused GEE regression: 116 passed;
- local `py_compile`: passed for the stable core, typed gate/builder, fidelity gate,
  and fidelity builder;
- server `unittest`: 31 passed;
- server has no `pytest`; no dependency was installed;
- typed artifacts: six files byte-identical across two independent runs;
- no LLM call, task-text generation, data split, production merge, or training.

## Next Gate

Run deterministic source-backed dataset, temporal, spatial-input, transformation,
and output-fact extraction on the 266 mapping-complete workflows. Task text may use
only those facts and cannot change the operator/L3 chain. The 232 role-boundary
conflicts, 42 L3 gaps, and 6 raw-call gaps remain separate recovery queues and must
not block first production from the already mapping-complete set.
