# QGIS Processing Unified Replay Design

## Scope

Build one deterministic entry point for the 8,466-row QGIS Processing authority.
The driver consolidates the already source-verified full replay with the latest
stable110/`lineintersections` mapping overlay, deterministic description evidence,
four-layer duplicate evidence, and the existing admitted QGIS train-only authority.
It does not infer operators, mappings, descriptions, or training admission.

## Data flow

1. Use `processing_source_manifest_v1.jsonl` as the only row authority.
2. Require exact one-to-one coverage from `processing_full_replay_manifest_v2.jsonl`.
3. Overlay the latest 3,163-row L3 replay only by `(record_id, source_sha256)`.
4. Join description and admitted training evidence by the same identity.
5. Assign exactly one final outcome per authority row: `accepted`, `deferred`,
   `excluded`, or `duplicate`, with a more specific status and reason.
6. Export training rows only when they already exist in the admitted train-only
   authority and pass alignment checks. All new direct candidates remain deferred
   until source replay/admission is available.

## Calibration and full replay

The calibration phase emits 200 deterministic, stratified rows. It includes every
latest direct candidate and every already accepted row when they fit, then balances
the remaining states and source roots. Its automatic gate checks identity coverage,
one-state-per-input, accepted chain alignment, closed validation/test admission, and
zero uncertain training exports.

The full phase accepts a calibration summary only when the gate passed and all input
hashes plus the policy version match. It then writes all 8,466 ledger rows using the
same code path and frozen inputs.

## Quality policy

- Strict identity joins; no path, filename, or record-ID-only fallback.
- Latest evidence may overlay but may never introduce a non-authority identity.
- Existing admitted train-only authority is stronger evidence than an older routing
  status, but direct rows must still match the replayed operator and L3 sequences.
- Description fidelity failure or missing description remains deferred.
- Source-unavailable but otherwise ready direct rows remain deferred.
- Duplicate source region, call graph, or exact training pair is suppressed.
- No LLM call, model training, production merge, or validation/test admission.

## Outputs

- `processing_replay_ledger_v1.jsonl`: one state per selected/full authority row.
- `accepted_train_only_v1.jsonl`: only pre-admitted, revalidated training rows.
- `calibration_review_v1.csv`: audit packet with blank human-review columns.
- `summary_v1.json`: state counts, coverage, and quality-gate evidence.
- `hash_ledger_v1.json`: immutable input and artifact hashes.

