# QGIS Multi-step Processing Pilot Report (2026-07-22)

## Scope

This report records the read-only, deterministic pilot over the 3,938
`explicit_processing_multistep_catalog_exact` records. It does not generate
task descriptions, grant taxonomy/training admission, or write under
`/home/yll`.

The final authority is the server directory:

`/home/qy/system_redesign/outputs_v2/qgis_multistep_processing/pilot_v3`

`pilot_v1` is the initial discovery run. `pilot_v2` only changed review
sampling to retain the highest-evidence records. `pilot_v3` is the final run
after recovering dependencies from the common `processing.run(...)["OUTPUT"]`
assignment form. Earlier directories remain immutable evidence of those
findings and are not training authorities.

## Frozen Inputs

| Authority | SHA256 |
|---|---|
| `layered_unique_content.jsonl` | `1cb101a01895379d79da436bef2fb8450232e6099a941763f04e06eb9b0c88d8` |
| `/home/yll/GEE/爬取GithubQGIS/QGIS_Input.csv` | `a57e9fda75be0a0623deb619d614de5a58d73e15c109ca36a8b1931b960f9594` |
| `id_mappings_v2_94_frozen.json` | `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558` |
| `qgis_alg_id_crosswalk_v1_114.json` | `82d07467fcc29a2770ff2183b3f74e364eb76e5eaf3eda68efadce4777ba9844` |

The stable-94 authority uses the frozen file's top-level `l3` mapping. The
extractor accepts this production shape and the derived `code_to_token_id`
test shape, while still requiring exactly token IDs `0..93`.

## v3 Counts

| Measure | Count |
|---|---:|
| Selected source contents | 3,938 |
| Processing callsites | 27,721 |
| Workflow regions | 4,264 |
| Straight-line candidate regions | 234 |
| Deferred regions | 4,030 |
| Excluded regions | 0 |
| Review rows | 50 |

Candidate region breakdown:

- stable-94 `complete_exact`: 108
- stable-94 `partial`: 17
- stable-94 `unsupported`: 103
- stable-94 `unresolved`: 6
- dependency `connected`: 61
- dependency `independent`: 148
- dependency `partial`: 25
- exact + connected: 42 rows across 26 unique source contents

The 50-row review pack contains all 42 exact + connected straight-line rows,
plus 8 risk/deferred comparison rows. It covers 34 unique source paths. Its
review fields and decision fields remain blank.

## Review Sampling

`summary.json` records:

```json
{
  "high_evidence_available": 42,
  "high_evidence_selected": 42,
  "high_evidence_shortfall": 0,
  "priority_source_available": 3,
  "priority_source_selected": 3,
  "selected_sample_size": 50
}
```

The high-evidence intersection is explicitly sampled before source and risk
strata. This prevents the only strongest chain from being omitted by a broad
round-robin fill.

## Source Checks

Manual source checks confirmed:

- `github_merge/script_51553.py`: `native:buffer` feeds
  `native:countpointsinpolygon` through `buffered["OUTPUT"]`.
- `github_merge/script_703.py`: `extractbyexpression -> buffer ->
  extractbylocation` is a real connected chain; the `OUTPUT`-subscript
  dependency fix recovers both edges.
- `zenodo_qgis/script_0060567.py`: a real three-step
  `extractbyattribute -> refactorfields -> setlayerstyle` chain, but inside
  `processAlgorithm`, so it remains implementation-review.
- `zenodo_qgis/script_0060601.py`: a five-step chain with a branch guard;
  it remains deferred until control-flow semantics are reviewed.
- `github_merge/script_4203.py`: repeated `native:clip` calls over separate
  layers; it is correctly routed to long/independent review rather than
  collapsed into one workflow.

## Remaining Data Risk

Byte-level source deduplication does not remove all semantic mirrors. Among
the 42 exact + connected rows, there are only 18 `(owner, operator-chain)`
signatures; 35 rows fall into 11 repeated signature clusters. For example,
the same `extract_skipped_streets` and related building-processing chains
occur across textbook, official-plugin, GitLab, and GitHub sources.

Therefore the 42 rows are review records, not 42 independent training
examples. Region-level AST/semantic deduplication has now measured this risk;
the remaining gate is human review of a deduplicated sample. No LLM
description generation, training-row emission, taxonomy admission, 200-row
expansion, or model training is authorized by this pilot.

## Region-Level Deduplication v1

The review-only authority is:

`/home/qy/system_redesign/outputs_v2/qgis_multistep_processing/pilot_v3_region_dedup_v1`

It consumes all 234 straight-line candidates. The 4,030 deferred regions are
outside its scope. Every canonical source was rehashed before parsing; all 234
matched their frozen source SHA256 and all regions were recovered.

| Measure | Count |
|---|---:|
| Fingerprint rows | 234 |
| Recovery errors | 0 |
| Strict AST groups | 59 |
| Strict AST grouped members | 150 |
| Nonrepresentative strict AST duplicates | 91 |
| Distinct strict AST fingerprints | 143 |
| Semantic review clusters | 59 |
| Semantic clustered members | 165 |
| Distinct semantic signatures | 128 |
| Blank review CSV rows | 234 |
| Training rows | 0 |

The strict AST hash ignores formatting, comments, and source positions while
preserving the complete owner definition, identifiers, literals, arguments,
statement order, and control structure. Equal hashes are deterministic region
duplicate evidence.

The semantic signature normalizes owner/local names but preserves ordered and
repeated operators, parameter-key shape, Processing call form, input/output
subscript keys, normalized dependency edges, owner kind, and control context.
Equal semantic signatures are only review clusters. They do not authorize
deletion, canonical admission, or training admission.

Within the 42 stable-94-exact and dependency-connected rows:

- 20 strict AST fingerprints remain;
- 18 semantic signatures remain;
- 22 rows are nonrepresentative strict AST copies;
- 35 rows belong to semantic review clusters;
- 18 rows are the deterministic semantic review representatives.

The earlier 18 `(owner, operator-chain)` signatures and the new 18 semantic
signatures have the same count, but they are not the same test. The semantic
signature additionally checks parameter structure and dataflow. Across all 234
candidates, the largest observed semantic cluster contains seven
`native:fixgeometries -> native:retainfields` regions from five source roots.

## Dedup-Aware Human Review Pack v2

The current human-review authority is:

`/home/qy/system_redesign/outputs_v2/qgis_multistep_processing/pilot_v3_review_50_v2`

The local mirror is:

`docs/reports/qgis_multistep_processing/pilot_v3_review_50_v2/`

It deterministically selects 50 unique records from the 234 region fingerprints:

| Stratum | Count | Purpose |
|---|---:|---|
| High-evidence semantic representatives | 18 | Cover all 42 stable-94-exact and dependency-connected records without counting mirrors as independent samples |
| Within-cluster controls | 12 | Compare equal semantic signatures whose strict owner AST differs, directly testing semantic over-merging |
| Diversity representatives | 20 | Add nonoverlapping signatures while broadening source, chain length, dependency state, mapping state, repetition, provider, source role, and risk evidence |

The pack contains 49 semantic signatures and 46 unique canonical source files.
Twenty-four rows include a deterministic comparison record and both source
snippets. All 12 control rows are semantic-equal but strict-AST-different from
their comparison representative. The CSV embeds line-numbered source snippets,
cluster members, mapping/dataflow evidence, and 11 blank human review fields.
Taxonomy/training admission remains `not_granted`; training rows remain zero.

Real-data QA rejected the preliminary v1 package as the review authority because
11 of its 12 controls were strict AST mirrors. The v2 selector searches all 59
review-only semantic clusters for different-AST controls and prevents the
20-row diversity stratum from repeating a control's semantic signature.

Two independent v2 server builds were byte-identical. The second temporary
directory was removed after comparison. Key v2 hashes are:

| Artifact | SHA256 |
|---|---|
| `manual_review_50.csv` | `d8e8ec8b7fc544e914e8352ffc1799fbab90c1f4d2b0d3828a1df59dafb5a98d` |
| `selection.jsonl` | `ab9a5db3dbc9bccacbf45c76496b7c442060a7373bd4cfe3af64e1a7aa1ebab1` |
| `summary.json` | `945491b2590a9c231d8403f09531727f787c125b68b2e6e64113e5cdc048c873` |
| `hash_ledger.json` | `ec2da8f9e27dcd58001f0dc62d3c4df7d880ec542aa4f45574f95e5ad6c5fe43` |

## Artifact Hashes

The v3 `hash_ledger.json` verifies all nine artifacts. Key hashes:

| Artifact | SHA256 |
|---|---|
| `processing_callsites.jsonl` | `05b0c1579e8f992fa95ef379eb2e032eb18128f284d76e1f5d20048ada04f369` |
| `workflow_regions.jsonl` | `87ac5125fa312ebc4b8819f001a71e2469d4ed26881d76d5c19536c63bf97780` |
| `candidate_chains.jsonl` | `0ffd34bb9931b1699f0a03aa352c0bfb7f1a586391931db0c60e468dfd0b08ce` |
| `deferred_records.jsonl` | `2d473c136150f37a403f21fa3d87d7db2f1d5735b92d6a1ce3d3e30f6089df0b` |
| `manual_review_50.csv` | `37a789ed0ad399d58548f650522752940efeeb538a593b2e548f9b7ad81a2d39` |
| `summary.json` | `ec3652b9402a263a0e7f5832fd4c74c81e62e3b70aeba66a17308fe65c2ba16d` |

The region-dedup v1 ledger records:

| Artifact | SHA256 |
|---|---|
| `input_manifest.json` | `ff9e28635986f3b4bb0acecee5cbc7e9bd2d36b713d6fa3715ef63f6cdea68c8` |
| `region_fingerprints.jsonl` | `b606270122036b5cfa54b14e75588caabef9821595b11f9e5e4c5f163c931f84` |
| `exact_ast_groups.jsonl` | `fe1f6a1ec837f7e486f51ff5c0735f743fb4fde86aa993e6aabf12c7233aa180` |
| `semantic_clusters.jsonl` | `43c3483c688efcb93109ad2f4135ea6b7c079931e8583f45790ff90558375e66` |
| `dedup_review.csv` | `2385ebdbcbeb38e774c6ee5f52706af75049f24d24d5df63f627da47a91aaf04` |
| `summary.json` | `b3ccc1ab7e90c4eda9a2cc4e8fca80d05ee21a9012624eedeef73b96f8ec3c41` |
| `hash_ledger.json` | `2ce9853459d0815da3f144f0994cd93c9a64033d8009b07e904b2ae290792dbe` |

## Verification

- Local focused suite: 33 passed.
- Local combined QGIS regression: 107 passed.
- Local full `test_qgis*.py`: 614 passed.
- Server combined regression: 108 passed, 1 Windows-only test skipped.
- Server v3 output counts and artifact SHA256 ledger verified.
- All nine canonical source roots were read-only; no `/home/yll` writes were
  performed.
- Region dedup local focused suite: 24 passed.
- Region dedup local full `test_qgis*.py`: 638 passed.
- Region dedup server combined suite: 57 passed, 1 Windows-only test skipped.
- Independent server validation rechecked all 234 candidate IDs, all group
  memberships, all output hashes, all blank human fields, and all 234 source
  hashes.
- A second server build was byte-identical across all seven artifacts. Its
  verified temporary directory was removed; the fixed v1 authority remains.
- Six historical invalid-escape `SyntaxWarning` lines were emitted across the
  two server runs. They did not affect parsing or fingerprints.
- Review-pack verification: local focused 10/10 and full QGIS 648/648; server
  combined review-pack/region-dedup/multistep suite 67 passed with one
  Windows-only skip. Local and server hashes for the new library, CLI, and test
  are identical. Two real v2 builds and the local mirror match the frozen ledger.
