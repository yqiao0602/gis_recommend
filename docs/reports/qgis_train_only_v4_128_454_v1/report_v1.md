# QGIS V4-128 train-only delivery 454 v1

## Decision

- Promote 454 rows from the 507-row aggregate as the current QGIS train-only
  entrypoint for the existing V4 text contract.
- Defer 53 rows whose real `bert-base-uncased` prompts exceed the fixed
  128-token input limit. Do not silently truncate them and do not revoke their
  source provenance.
- Keep validation/test eligibility false and production merge not granted.

## Evidence

- Real-tokenizer full-population audit: 507 rows checked, 454 no-truncation
  eligible, 53 deferred, eligible maximum exactly 128 tokens.
- Deferred composition: Processing 35, Raster Calculator API 17, Add Field ->
  Calculate Field API 1.
- Source-disjoint audit: 50 rows, calibration 25 and holdout 25, source SHA and
  authority overlap both zero.
- Server source replay: 50/50 files exist, SHA256 matches, decode and AST parse,
  source spans, and 1,689 evidence lines all pass.
- Semantic review: 40 V4-128-compatible rows accepted; 10 audit rows deferred
  only for text truncation. Boundary, description fidelity, and stable125 L3
  alignment failures are all zero.
- V4 loader/weighted-loss/backward: 454/454 rows, 15 batches, finite loss and
  gradient, no checkpoint and no training run.

## Authority

- Dataset: `qgis_train_only_v4_128_454_v1.jsonl`
- Dataset SHA256:
  `9d037845578bf5f49e605de42ab57fd443b9594a5a8c749d7e2922cc0460fe2e`
- Admission: `admission_v1.json`
- Audit evidence:
  `../qgis_train_only_aggregate_507_audit_v1/source_replay_v1.jsonl` and
  `../qgis_train_only_aggregate_507_audit_v1/semantic_review_v1.jsonl`

The earlier 507-row aggregate remains the complete deduplicated provenance
package, but it is not the current V4-128 training entrypoint because 53 rows
would be silently truncated by the production text contract.
