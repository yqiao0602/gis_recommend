# GEE Batch7 10,000-source v8.4 sampling audit

Date: 2026-08-04

## Scope and authority

- Batch root: `/home/qy/system_redesign/diagnostics/gee_batch7_10000_v8_4_20260804`
- Frozen audit packet: `expansion_v8_4_a/audit_sample_50.jsonl`
- Full-source root: `/home/yll/GEE/Data` (read-only)
- Reviewed indices: 1 through 50
- Source SHA256 replay: 50/50 matched
- Stable-94 authority SHA256:
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`

This is a pre-fix audit. It does not grant train, validation, test, or production
admission.

## Result

- PASS: 44
- FAIL: 6
- DEFER: 0
- Critical failures: 6
- Point precision: 0.88

The frozen v8.4 rules therefore fail the Batch7 sampling gate. No Batch7 row
may be merged into the existing 2,267-row train-only authority from this run.

## Failed rows

| Index | Source / workflow | Failure | Required deterministic action |
| --- | --- | --- | --- |
| 4 | `data130000/script_122493.txt`, `output-workflow-1` | Exact operator-to-L3 errors: zero-argument `ee.image.mask()` was labelled Update Mask, and cross-band `ee.image.reduce(...)` was labelled Global Statistics. | Add argument-aware mask semantics and map cross-band image reduce to Cell Statistics. |
| 12 | `data230000/script_227482.txt`, `output-workflow-1` | `ee.image.resample(...)` was labelled Reproject. | Map resample to the existing Resample L3 while retaining `reproject` as Reproject. |
| 16 | `data280000/script_277671.txt`, `output-workflow-1` | `ee.image.unmask(...)` was labelled Update Mask and image-to-image `ee.image.max(...)` was labelled Select Bands. | Map unmask to Unmask / Fill Masked and local image max to Cell Statistics. |
| 23 | `data90000/script_88012.txt`, `output-workflow-1` | `collection.iterate(appendBands, first)` drives repeated band accumulation, but the retained chain contains only `first -> select -> addBands`. The omitted `iterate` changes workflow semantics. | Fail closed for output-relevant iterate/callback aggregation until the structural operator and callback repetition are representable. |
| 46 | `data90000/script_83223.txt`, `output-workflow-10` | The selected GRIDMET export occurs after unconditional top-level `throw` statements and is statically unreachable. | Reject export sinks dominated by an unconditional terminating statement. |
| 47 | `data400000/script_400391.txt`, `output-workflow-1` | Cross-helper and `getInfo().forEach` callback mutation builds the output accumulator, but the chain was truncated to three final `merge` calls. Dataset, spatial and main transformation provenance were lost. | Fail closed when an output depends on callback mutation or helper closure that the backward slice does not close. |

## Mapping verification for indices 18-34

The middle 17-row review slice was additionally checked against all three
mapping layers:

- 17/17 audit rows uniquely matched their typed decisions.
- 41 distinct canonical operators were present in the frozen operator catalog.
- Every canonical operator had an exact `mapping_metadata.gee_to_l3` entry.
- 22 distinct L3 codes were present in the stable-94 mapping.
- Operator, L3 and mapped-call sequences aligned with zero errors.
- Stable token IDs were unique and exactly covered `0..93`.

The only failure in this slice is therefore workflow completeness at index 23,
not a canonical operator or token lookup error.

## Replay gate

1. Add regression fixtures for all six failed identities or minimal equivalent
   ASTs before changing rules.
2. Fix general rules only; do not special-case source hashes or audit indices.
3. Rebuild Batch7 from the DAG stage or earlier when source evidence changes,
   and from the typed stage or earlier when mapping semantics change.
4. Recreate A/B outputs and require byte-identical business artifacts.
5. Re-run a frozen source-disjoint 50-row full-source audit. Previously failed
   identities may be targeted as regression evidence but do not replace the new
   source-disjoint sample.
6. Export training rows only after the new audit has zero critical failures and
   passes the configured precision/Wilson gate, followed by real loader, loss
   and backward smoke.

