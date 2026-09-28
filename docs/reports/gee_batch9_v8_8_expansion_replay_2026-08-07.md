# GEE Batch9 v8.8 Expansion/Proposal A/B Replay

## Scope

This gate replays the frozen complete-workflow expansion publisher over the 242
Batch9 canonical task-text candidates. It uses only the controlled snapshot
`code_snapshot_v8_8_band_alias_rulefix_authority`, read-only source evidence under
`/home/yll/GEE/Data`, the frozen stable-94 mapping, reviewed-identity exclusions,
and the existing Batch8 semantic authority. No extraction rule was changed.

## Result

The independent A and B runs are byte-identical for all business artifacts,
including `hash_ledger.json`. The shared Batch9 profile SHA256 is
`d536ab3909fbb52642e31a6fa42a7ebf6d89fa6deac30b2d713638040a274fb3`.

| Partition | Count |
| --- | ---: |
| Canonical candidates | 242 |
| Existing or batch duplicates | 44 |
| Deferred for length | 1 |
| Reviewed-source overlap | 0 |
| Semantic fail-closed | 0 |
| Proposal eligible | 197 |
| Eligible unique sources | 114 |
| Stratified audit sample | 50 |
| Training rows emitted | 0 |

The 50-row sample is frozen with quotas `external_dynamic=6`,
`long_or_repeated=17`, `multi_dataset_private=17`, `no_temporal_operation=3`, and
`spatial_omission=7`. Its audit status is `pending_sampling_audit`.

## Authority And Verification

Remote outputs are under
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`:

- `expansion_v8_8_authority_a`
- `expansion_v8_8_authority_b`

`cmp -s` verified byte identity for `proposal_candidates.jsonl`,
`remaining_ledger.jsonl`, all four sidecars, `audit_sample_50.jsonl`,
`audit_source_manifest.jsonl`, `summary.json`, `report.md`, and
`hash_ledger.json`.

The A/B artifact SHA256 values include: proposal candidates
`e55e27d23c95f475981438aa9775719d9e881a8ab1a3bdea4c0cbf36969c7326`,
duplicate sidecar `f969e43990c7476b292dc84c06ad9c5c0c75e3317ee6e77833cfe912b5918b66`,
length sidecar `47b5c39d047f1553de5bc6ee1f1d8ff313e489645208876d8eb0ba411957199d`,
and summary `d4d972dc0ef5a9e8bae69f5fb138a325ddb976f20a4bd8cfd173f8b8d31c2d20`.

## Admission Status

This is not a training admission. `training_admission`, production merge, and
validation/test eligibility remain closed. The next and only gate is a full-source
semantic audit of the frozen 50-row stratified packet. A rule change is allowed only
if that audit identifies a systematic, reusable defect; otherwise the 197 proposals
can proceed to the already-defined train-only admission path.
