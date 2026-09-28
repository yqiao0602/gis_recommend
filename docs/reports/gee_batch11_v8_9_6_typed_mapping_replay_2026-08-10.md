# GEE Batch11 v8.9.6 Typed Canonicalization/Mapping A/B Replay

## Decision

Batch11 completed frozen typed canonicalization and L3 mapping from its valid
fidelity-passed population. Both runs are byte-identical, including the hash ledger.
Mapping remains fail-closed: only mapping-complete workflows may proceed to the
source/AST-backed facts gate. No task text, proposal, export, merge, or training row
was emitted.

## Frozen Inputs

- Population: 388 fidelity-passed candidates from Batch11 A/B fidelity outputs.
- AST authority: valid Node/Acorn replay with explicit Node 20 and `NODE_PATH`.
- Stable-94 mapping SHA256:
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.
- v8.5 override SHA256:
  `b73ba4fee77a49a71e91263663982ccaade4608fad1b4e652b6534e8cfdd3074`.
- Skip-list SHA256:
  `88062860680b163ae13749f5a5a31891fcd82adff9caa3cb71e6b997679270c7`.

## Results

- Decisions: 388.
- Mapping-complete: 206 workflows from 125 unique sources.
- Fail-closed: 182 workflows.
- Coverage: 107 canonical GEE operators and 42 L3 codes.
- Strata: `helper_export` 127 complete / 120 fail-closed; `control_flow_export`
  79 complete / 62 fail-closed.
- Training rows emitted: 0.

## A/B Evidence

The following business artifacts are byte-identical between
`typed_v8_9_6_a` and `typed_v8_9_6_b` under
`/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/`:

- `typed_mapping_decisions.jsonl`:
  `d69e05399d2a297b591803fe5c4bd34aaf7869ded6a9f6a947618d584d99caad`
- `mapping_complete_candidates.jsonl`:
  `5e7f23e3e68fa5026cd9b61c86d1eafa6d3d015683ae21e9487c670c1a9742d6`
- `mapping_fail_closed.jsonl`:
  `20e06afca24280c1d55382ba9737692bb86829aeffa160c195ca9dfb4f44f7b4`
- `summary.json`:
  `b403d1e845c04fd8f6ee54fa4a3d72fcd0431e60490da9e5fe59c4f1f60e0cdf`
- `report.md`:
  `1e335812a31c7c85080e5f35f2e5c937a34063a44aa029e57ec767e26a5f700b`
- `hash_ledger.json`:
  `5060e5ed1b2e693f57b793d03b4d6907d8a4e2ab2763b0302a670f172b8b0836`

## Next Gate

Run the frozen source/AST-backed facts A/B publisher using only each mapping-complete
output. Facts must prove dataset, temporal, spatial, transformation, and output
claims from the source and AST before canonical task text, proposal generation, or
any train-only admission is considered.
