# GEE Batch9 v8.9.3 Replay and Audit Freeze

## Scope

This replay applies the narrowly scoped v8.9 loop-lineage fail-closed repair to
the frozen 5,000-source Batch9 population. It uses read-only source evidence in
`/home/yll/GEE/Data`, the frozen stable-94 mapping, and no LLM-generated chain.
The publisher snapshot is
`code_snapshot_v8_9_3_loop_lineage_facts_ledger_determinism_authority`.

The facts publisher was additionally repaired to record logical ledger identities
(`source/<corpus path>` and `ast/<source SHA>.json`) instead of its physical replay
directories. This affects only publication determinism, not candidate selection or
semantic facts.

## A/B Results

Every artifact in each A/B pair is byte-identical, including `hash_ledger.json`.

| Gate | Result |
| --- | --- |
| AST/DAG | 4,997 AST success; source `passed=152`, `partial=133`, `fail_closed=4,712`; 410 unresolved output control-flow lineage failures |
| Fidelity | 563 accepted workflow decisions, 6 exact duplicates, 10,548 fail-closed; 273 unique accepted sources |
| Typed mapping | 326 mapping-complete, 237 fail-closed; 142 sources, 122 canonical GEE operators, 47 L3 codes |
| Facts/text | 315 source/AST-backed fact bundles, 11 fail-closed; 224 canonical task-text candidates from 123 sources, 91 duplicates |
| Proposal | 183 proposal-eligible rows from 107 sources; 41 existing/batch duplicates, 0 length defers, 0 semantic failures, 0 reviewed-source overlaps |

The facts A/B ledger SHA256 is
`ada3520aefa74124bbb2ec548bf9c1f17e685328ce90a2c61e9458c10b15f55c`.
The proposal A/B ledger SHA256 is
`def82c618a0ac2225bf82d641ece4e0257e0e4419bfbbb5824ea8b3589c7a718`.

## Frozen Audit Packet

The new 50-source full-source semantic audit is frozen at:

- `expansion_v8_9_3_loop_lineage_authority_a/audit_sample_50.jsonl`
- `expansion_v8_9_3_loop_lineage_authority_a/audit_sample_50.csv`
- `expansion_v8_9_3_loop_lineage_authority_a/audit_source_manifest.jsonl`

It uses the explicit profile
`configs/expansion_profile_v8_9_3_batch9.json` (SHA256
`17aaaf0d69083b05a7314d8afdee1c98952365fdecd9839c72c024c7be907596`).
The 50-row quota is `external_dynamic=6`, `long_or_repeated=18`,
`multi_dataset_private=16`, `no_temporal_operation=2`, `other=1`, and
`spatial_omission=7`. All rows remain `pending_sampling_audit`.

## Admission

This stage emits zero training rows. Train-only admission, validation/test
eligibility, and production merge remain closed. The next gate is the full-source
semantic audit of the frozen 50 rows. Only a systematic, reusable defect may change
a rule; individual records must not be patched or admitted manually.
