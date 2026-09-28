# GEE Typed Canonicalization Design

Date: 2026-07-30
Status: approved for implementation

## Goal

Convert the 546 complete-DAG, fidelity-passed GEE workflow candidates into a
deterministic operator/L3 mapping census. The output separates mapping-complete
next-stage candidates from evidence mismatches and mapping gaps. It does not generate
task text or training rows.

## Inputs And Authority

- Frozen fidelity candidates from the source-disjoint 500-source pilot.
- The matching SHA-keyed ESTree AST files.
- `outputs_v2/id_mappings_v2.json` as the current GEE operator catalog and GEE-to-L3
  mapping authority.
- `GeeSourceEvidence.ordered_calls` as the receiver-type and resolution authority.

Every output row remains bound to `source_sha256`, `source_path`, `workflow_id`, the
fidelity candidate manifest hash, its AST hash, and the mapping authority hash.

## Ordinal-Preserving Fidelity Contract

The current fidelity record retains the original `core_call_ordinals` but may remove
auxiliary spatial calls from `normalized_core_chain`. A scalable typed join cannot
infer the surviving ordinals by string matching because repeated call strings are
legal.

The fidelity decision therefore gains `normalized_core_call_ordinals`. The fidelity
normalizer processes `(ordinal, raw_callee)` pairs and removes both members together.
For every passed or duplicate decision:

```text
len(normalized_core_call_ordinals) == len(normalized_core_chain)
```

The fixed-50 and 500-source fidelity artifacts must be rebuilt twice and remain
byte-identical within each pair. Their semantic disposition counts must not change.

## Typed Canonicalization

For each fidelity-passed workflow:

1. Load the AST named by `source_sha256` and re-extract `GeeSourceEvidence`.
2. Require ordinals to be non-negative, unique, strictly increasing, and aligned in
   length with the normalized chain. Resolve every ordinal to exactly one
   `CallEvidence` classified as `core`.
3. Require the extracted `raw_callee` to equal the aligned
   `normalized_core_chain` value. Missing ordinals, duplicate ordinals, or callee
   mismatches fail closed.
4. Set `receiver_is_proven_ee` only when the call resolution is `ee_namespace` or
   `receiver_ee_binding`, or the raw callee starts with `ee.`.
5. Pass the raw callee, proven-EE flag, and extracted `receiver_type` to the existing
   strict `canonicalize_operator_sequence` implementation. Supplying receiver types
   disables family-name guessing.
6. Record the canonical operator, L3 code, mapping confidence, ambiguity flag,
   receiver type, resolution, and source location for every mapped call.

Mapping confidence is reported but is not silently converted into a new threshold in
this census. An entry with `has_ambiguity=true` is fail-closed. Unknown raw calls and
catalog operators without an L3 mapping are separate failure classes. A retained core
call that the legacy canonicalizer classifies as support is fail-closed as
`support_classified_retained_call`; it cannot be silently removed because methods such
as `sort`, `copyProperties`, and `toImage` may change output semantics. Only calls
already removed by the fidelity gate with normalized-ordinal evidence are absent from
the typed input.

## Decision States

- `mapping_complete`: at least one canonical operator/L3 remains and every normalized
  core call maps exactly once; no support skip, ambiguity, or mapping gap exists.
- `evidence_mismatch`: source/AST identity, ordinal alignment, raw callee, or accepted
  fidelity contract is invalid.
- `canonical_l3_gap`: a recognized catalog operator lacks an L3 mapping.
- `unmapped_raw_call`: a call cannot be proven as a canonical GEE operator.
- `ambiguous_mapping`: the current mapping authority marks a used entry ambiguous.
- `support_classified_retained_call`: a retained core call would otherwise be skipped.
- `empty_canonical_chain`: all calls were skipped and no target operation remains.

Rows may contain more than one fail-closed reason, but exactly one top-level status is
assigned by fixed precedence: evidence mismatch, ambiguity, retained-support call,
canonical gap, raw gap, empty chain, then mapping complete.

## Artifacts

The builder emits atomically and deterministically:

- `typed_mapping_decisions.jsonl`
- `mapping_complete_candidates.jsonl`
- `mapping_fail_closed.jsonl`
- `summary.json`
- `report.md`
- `hash_ledger.json`

The report includes workflow/source yield, per-stratum yield, canonical operator and
L3 coverage, confidence distribution, skipped-support prevalence, and fail-closed
reason counts. All decisions use
`training_admission=not_granted_task_text_and_final_dedup_pending` and
`training_rows_emitted=0`.

## Verification

- TDD covers ordinal preservation, repeated-call alignment, missing ordinals, callee
  mismatch, typed receiver disambiguation, unknown receivers, catalog-without-L3,
  ambiguous mappings, support skips, deterministic artifacts, and ledger partition.
- Existing DAG, fidelity, extractor, and P4 canonicalization regressions remain green.
- Server replay runs twice on the same frozen inputs; all six artifacts are
  byte-identical and their hash ledgers bind every input.
- No task text, validation/test split, production merge, or model training is created.

## Next Boundary

Only `mapping_complete_candidates.jsonl` can enter source-backed dataset/temporal/
spatial/output fact extraction and task-text construction. Mapping-complete status is
still not train-only admission.
