# QGIS `processing.runalg` Entrypoint Census v1

Date: 2026-08-16

## Scope

This is an isolated read-only intake and calibration freeze for the legacy
`processing.runalg` entrypoint. It consumes the frozen 8,466-row Processing
source-role census, verifies raw source SHA-256 under `/home/yll`, and inspects
AST call shapes. It does not change the production extractor, L3 mapping,
authority, validation/test/benchmark data, or any training package.

## Census

| Measure | Result |
|---|---:|
| Processing manifest rows | 8,466 |
| Server-missing sources | 295 |
| Readable `runalg` sources | 201 |
| `runalg` calls | 927 |
| Literal operator calls | 775 |
| Dynamic/blank-first-argument calls | 152 |
| Literal-only eligible source rows | 189 |
| Internally duplicate normalized bodies | 41 |
| Canonical normalized-body authorities | 148 |

All 927 calls use the historic positional API in 918 cases; only nine use a
keyword (`progress` or `**kwargs`). Positional argument counts range from one
to 23. Therefore `runalg` cannot be admitted by merely treating it as
`processing.run`: its parameters do not satisfy the dictionary contract that
the production extractor relies on for I/O typing and output-path evidence.

The dominant readable roots are `github_merge` (129 source rows) and
`textbook_strict` (61), with small representation from `official_plugins`,
`route_b`, `pwc_qgis`, and `gitlab_supplement`. The 292 missing `model_tutorial`
sources account for nearly all missing rows and are not silently replaced.

## Frozen Packet

The deterministic, root-round-robin freeze selected 60 literal-call sources:

| Role | Rows |
|---|---:|
| Calibration | 30 |
| Holdout | 30 |

Both source SHA-256 and normalized source-body SHA-256 have zero overlap across
the split. Existing 294 Processing and 508 all-QGIS authority source hashes
were excluded where present; none of the 392 unique authority hashes occurs in
this Processing census, so no body-level authority key could be resolved from
the current manifest. The packet remains calibration-only and has zero training
rows.

## Next Gate

Implement an **isolated** AST-compatible `runalg` adapter and execute only the
30 calibration sources first. It must demonstrate exact literal call-site
alignment, no false operator insertion, and correct source-grounded dependency
recovery. The 30 holdout sources remain unused until that calibration result is
reviewed. A successful holdout does not itself grant Gold/Silver admission;
the normal boundary, L3, description, deduplication and V4 gates remain in
force.

Artifacts and hashes are in this directory. The server source root remained
read-only; all execution artifacts were written under `/home/qy/system_redesign`
before being copied back.
