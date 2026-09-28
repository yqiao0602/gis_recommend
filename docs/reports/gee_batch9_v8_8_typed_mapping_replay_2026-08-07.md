# GEE Batch9 v8.8 Typed Canonicalization/Mapping A/B Replay

## Decision

Batch9 completed typed canonicalization and L3 mapping under the frozen v8.8
snapshot. The two runs are byte-identical. Mapping remains fail-closed: only
mapping-complete workflows advance to facts; unresolved, support-only, ambiguous,
or taxonomy-gap calls do not receive guessed L3 labels.

## Frozen Inputs

- Fidelity-passed candidates SHA256:
  `aef0a935d177aa5e2a19f24a5441e415fdfdb15d82fdb41c8e8acf942be34ac4`
- Typed publisher SHA256:
  `45d4f33af373b733841c809537a9c374632a20b5589b5d6b730658e41e6b58e6`
- Typed canonicalizer SHA256:
  `11c2e1c1f22644f48bfd0287e2c5332ac865378ba687e7710c3b3492bf4aece2`
- Frozen stable-94 mapping SHA256:
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`
- v8.5 L3 overrides SHA256:
  `b73ba4fee77a49a71e91263663982ccaade4608fad1b4e652b6534e8cfdd3074`
- v2.7 skip-list SHA256:
  `dac7a405655d5a9ab44cf336925b4710e68b81a8df29ec09af2887ffd30a02d8`

## Results

- Input decisions: 644 fidelity-passed workflows from 306 AST-backed sources.
- Mapping complete: 355 workflows from 154 sources.
- Fail-closed: 289 workflows.
- Coverage of passed mappings: 126 canonical GEE operators and 47 L3 codes.
- Training rows emitted: 0.

Fail-closed dispositions are `canonical_l3_gap` 92, `support_classified_retained_call`
123, `unmapped_raw_call` 31, `l3_override_taxonomy_gap` 40,
`l3_override_signature_mismatch` 2, and `empty_canonical_chain` 1. The leading
reasons include retained geometry constructors, `focal_median` without an L3 contract,
and untyped feature/property calls; all remain outside the mapping-complete output.

## A/B Evidence

The A/B business artifacts are byte-identical:

- `typed_mapping_decisions.jsonl`:
  `8509af27f479ab6c6ed530e505e14f07d297b52bf002fdf38db996147d5eb541`
- `mapping_complete_candidates.jsonl`:
  `f8e468e2438388effc32e5c2b62b22c4d460a628ebf25fdfa46d5a089f68ecec`
- `mapping_fail_closed.jsonl`:
  `bc8583724eab472affc60fe313ec33494b37643c3f44db3aee8302c19881c028`
- `summary.json`:
  `59cd551273b37a6deea14204e66d4eef4dbddf9067e61842ba8dddcaa3847215`

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`.
The authoritative directories are `typed_v8_8_authority_a` and
`typed_v8_8_authority_b`.

## Next Gate

Run the frozen facts A/B publisher using only `mapping_complete_candidates.jsonl`.
Facts must remain source/AST-backed; task text, deduplication, train-only admission,
and model training remain closed.
