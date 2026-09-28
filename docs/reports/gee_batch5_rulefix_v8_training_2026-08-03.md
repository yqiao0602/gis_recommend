# GEE Batch5 Rulefix v8 Train-Only Delivery

Date: 2026-08-03

## Scope

This phase applied the complete output-relevant GEE workflow converter to 1,000 new
source-disjoint sources. `/home/yll/GEE/Data` remained read-only. No QGIS data,
benchmark data, `outputs*`, `train11397_*`, model checkpoint, or training epoch was
modified or run.

## Rule Repairs

The initial 30-source audit had 29 passes and one critical false-complete workflow.
`data40000/script_36676.txt` collected helper/callback return properties through
`map`, a loop, and `Array.push`, but the recovered workflow retained only
`ee.Image.cat -> rename`. A TDD regression now makes output-relevant native collection
mutation fail closed as `unresolved_mutated_collection_dependency`. The 1,000-source
replay found five affected workflows; four previously accepted workflows were removed.

The first replacement audit row used the only reversed literal date interval in the
candidate population: `[2020-01-01, 2019-12-30)`. A second TDD rule now rejects static
ISO `filterDate` and `ee.Filter.date` intervals when start is not before end. It does
not reject wrapping `calendarRange` or day-of-year windows. The row is retained in the
fact fail-closed sidecar and emits no task text.

Local focused regression after both repairs is 169 passed and 1 skipped. The skipped
test requires local PyTorch; the real server smoke below covers that boundary. Server
`py_compile` and both new unit regressions passed.

## Deterministic Population

The v8 A/B replay produced identical data artifacts:

| Stage | Result |
| --- | ---: |
| Selected sources | 1,000 |
| AST success / failure | 998 / 2 |
| Fidelity passed / duplicate / fail-closed | 552 / 19 / 1,616 |
| Mapping complete / fail-closed | 363 / 189 |
| Fact bundles / fact failures | 353 / 10 |
| Canonical task candidates / text duplicates | 256 / 97 |
| Existing or batch duplicates | 35 |
| Length defers | 2 |
| Source-disjoint proposals | 219 |

Key authority hashes:

- workflow DAGs: `1612955f725a8230bc96143447001293c7a91bbcf67531d9b054a2eeb870a7f9`
- fact bundles: `27947dd78c9ee4db6a4a76beba0a847fb5034a4e0c119a8aed4e43da67d59bca`
- task candidates: `62ecacb5e319ca70c3dbd59e3e5d3b7c25039da72fc391ae9abab365a8314467`
- proposals: `7ddc00f9b36e45c24b5bb6989a4f1a50508cbd88ad77269298b469dac0bc5eff`
- stable-94 mapping: `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`

## Audit And Admission

The final audit preserves 29 unchanged prior workflow authorities and adds one
full-source-reviewed replacement, a seven-step Sentinel-2 export chain. All 30 rows
pass dataset, temporal, spatial, transformation, output, and task-text fidelity with
zero critical failures. Point precision is 1.0 and the Wilson 95% lower bound is
0.8864866068260312. Reviewed audit SHA256 is
`b6298e8c0dc3621d74d8afa004260a077988171c239af9b01aa734a2a1a1fac7`.

The evaluator decision is `passed_for_larger_source_disjoint_replay`, authorizing the
same frozen-rule 219-row proposal population. The exporter added all 219 rows with
zero duplicates and zero new length defers.

## Training Package Smoke

The combined package has:

- 1,061 complete semantic train-only rows;
- 1,060 current V4-100 rows;
- one existing 155-step length sidecar;
- validation/test eligibility false and production merge not granted.

Combined semantic SHA256 is
`2577c8278fc136a5050196a99eaee89c61ce06124107b2bdfc4d7035594251ef`;
combined V4 SHA256 is
`ded46b075b27bca02fbd2edbbf3617acdb3f6cf984ed67a4b5e1be29d3413032`.
All ten training artifacts are byte-identical between A and B.

Real `TaskConditionedL3DatasetV4`, weighted sequence loss, and backward smoke covered
1,060/1,060 rows in batches `[512,100]`, `[512,100]`, and `[36,100]`. Loss and
gradients are finite, max token is 92, max model sequence length is 92, and no
checkpoint or training run occurred. Smoke A/B SHA256 is
`56a95728134fe015ca1497d96b6ab20414bd6d5eab2c8cb0813de134ac6641a7`.

Server authority root:

`/home/qy/system_redesign/diagnostics/gee_batch5_rulefix_v8_20260803`

The next gate freezes v8 and expands to 5,000 new source-disjoint sources, with a
50-source stratified audit and a target of at least 2,000 cumulative V4 rows.
