# GEE Batch11 Audit and v8.9.7 Replay

## v8.9.6 Audit Decision

The frozen 50-source packet was reviewed against full read-only source files. Every
source SHA256 matches the packet. The result is 47 pass, three critical failures,
point precision `0.94`, and Wilson 95% lower bound `0.8378290831116182`.
The hash-bound evaluator returns `failed_rule_repair_required`; no proposal is
exported or merged.

The failures are:

- `data270000/script_268746.txt`: `COPERNICUS/S2_SR_HARMONIZED` queried only
  `[2016-04-01, 2016-04-30)`, before its 2017-03-28 coverage start.
- `data250000/script_246479.txt`: `sort('system:time_end', false)` controls
  `first()` but was absent from the retained chain.
- `data400000/script_411333.txt`: `sort('system:time_start')` controls `mosaic()`
  priority but was absent from the retained chain.

Remote audit authority:
`/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/audit_v8_9_6_full/`.

## v8.9.7 Repair and Replay

The repair adds only the S2 SR Harmonized catalog lower bound and removes only
`ee.imagecollection.sort` from a versioned skip authority. Stable-94 already maps
that operator to `L3_03_09_07`. The new controlled snapshot is
`code_snapshot_v8_9_7_sort_catalog_authority`.

All A/B business artifacts and ledgers match from fidelity through proposal:

- Fidelity: 387 passed, 14 duplicate, 8,668 fail-closed.
- Typed mapping: 205 complete, 182 fail-closed, 108 canonical operators, 43 L3 codes.
- Facts: 199 bundles, six fail-closed, 134 canonical task-text candidates.
- Proposal: 93 pending proposals from 76 sources, 40 duplicate sidecars, one length
  sidecar.

The repaired `sort` chains include the operator, L3 code, and task-text step. The
invalid S2 SR Harmonized row no longer passes fidelity. A fresh stratified 50-source
audit packet is frozen under `proposal_v8_9_7_{a,b}`. Training admission remains
closed until that packet passes.
