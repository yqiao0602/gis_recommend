# GEE Workflow Source-Backed Facts And Task Text, 500-Source Pilot

## Scope

This gate consumes only the 266 receiver-typed, mapping-complete workflows from
the frozen source-disjoint 500-source pilot. It does not process the 232
core/support conflicts, 42 L3 gaps, or 6 raw-call gaps; those remain independent
recovery queues.

## Authority And Reproducibility

- Typed input: `/home/qy/system_redesign/diagnostics/gee_typed_l3_mapping_pilot500_20260730_a/mapping_complete_candidates.jsonl`
- Fidelity input: `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260730_ordinals_a/accepted_candidates.jsonl`
- AST input: `/home/qy/system_redesign/diagnostics/gee_workflow_dag_pilot500_20260729_run3/ast/`
- Source root: `/home/yll/GEE/Data` (read-only)
- Final replay outputs: `/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_i` and `_j`

The two final replays produced eight byte-identical artifacts. The final hash-ledger
SHA256 is `ee49f0219f01438cb2bbf7cf109d142a4a28274b37003c93d2652155ef1e6c8b`.

## Results

| Gate outcome | Count |
| --- | ---: |
| Mapping-complete input workflows | 266 |
| Source-backed fact bundles | 266 |
| Fact fail-closed | 0 |
| Task-text candidates before deduplication | 266 |
| Canonical task-text candidates | 208 |
| Normalized-text + L3-chain duplicates | 58 |
| Candidate source authorities | 129 |
| Source-disjoint risk-review rows | 50 |
| Training rows emitted | 0 |

Each bundle contains source-located dataset, temporal, spatial-input,
transformation, and output facts. All 266 frozen operator/L3 chains are unchanged.
The publisher verifies every source byte SHA and AST, requires an exact composite
`(source_sha256, workflow_id)` join, and rejects any missing mapped-call span or
Export sink.

Fact coverage measured in the final replay:

- Dataset: 266/266 workflows have one or more closure-backed constructor facts.
- Temporal: 170 workflows contain temporal operators; 169 are fully static and one
  (`data90000/script_81912.txt`, `output-workflow-1`) retains dynamic date arguments
  as an omission rather than a generated date.
- Spatial: 85 workflows have an exact bound resource, 166 have an external
  identifier, 6 have an opaque local expression, and 19 have no spatial fact.
  These categories may overlap within a workflow.
- Transformation: all 2,961 frozen retained calls have an ordinal, canonical
  operator, L3 code, receiver type, AST span, and safe static-argument status.
- Output: all 266 have an exact Export sink; named and legacy positional signatures
  are parsed separately.

## Text Fidelity Contract

The deterministic text renderer uses public dataset literals only when safe, redacts
private assets, emits exact static temporal constraints only, calls unresolved
regions source-defined, preserves the complete frozen operation order, and records
the fact IDs used by each clause. A replay check confirmed for all 208 canonical
candidates that every clause references a fact in the matching bundle, the operator
and L3 sequences equal their frozen inputs, and no redacted private asset appears in
task text.

## Admission Status And Next Gate

These are source-backed task-text candidates, not admitted training rows. Validation,
test, production merge, and model training remain closed. The next required gate is
a source-disjoint, risk-stratified review of the 50-row packet, followed by any
needed deterministic rule correction, replay, semantic schema validation, and an
explicit train-only admission decision. The three mapping-gap queues remain separate
and cannot block this path.

## Superseding Risk-Repair Replay

The initial 266/208 result above is retained as provenance but is superseded for the
active gate. Risk-review fixes reject callback-core workflows without structural
`map` and reused core source spans. Frozen-AST A/B replay produces 340 fidelity-passed
workflows, 209 mapping-complete workflows, 209 fact bundles, 176 canonical text
candidates, 33 duplicates, and zero fact failures. Active authority:
`/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_rulefix2_a`.

All 50 stable workflow identities were re-reviewed against exact source SHA. Results
are 47 six-dimension passes, 3 source/version ambiguity deferrals, and zero remaining
deterministic rule defects. One pass is a 155-operator workflow and must remain in a
current-loader length sidecar. Training admission is still closed until a
complete-workflow schema/export and lineage gate are implemented.
