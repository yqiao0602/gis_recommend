# QGIS Processing Independent Blocker Intake v2

## Scope

This intake re-examines only sources outside the formal 294-row Processing
aggregate and the two previously scanned blocker selections (360 and 343 source
SHA values). It does not revisit the 343-source low-support census.

## Evidence Gate

An intake row must have a non-empty `call_sites` operator sequence that exactly
matches its recorded `operator_sequence`. The selector excludes database-side
effects and support/export-only operators before measuring family support.

## Result

- Input ledger: 8,466 rows.
- Excluded delivered or previously scanned source SHA: 941.
- Independent call-evidence clusters: 297.
- Rows without recorded call evidence: 6,408.
- Unsafe database/support-export rows: 365.
- Clusters with independent source support >= 30: 0.
- Selected rows: 0; L3, description, and training rows: 0.

The initial `qgis_processing_independent_blocker_intake_v1` run selected a
126-source `native:refactorfields ->
gdal:importvectorintopostgisdatabaseavailableconnections` cluster before the
existing database/support exclusion was applied. It is superseded provenance,
not a calibration packet or a training candidate.

The earlier `qgis_processing_bounded_joinbylocationsummary_intake_v1` is also
superseded: its unresolved label did not appear in either `call_sites` or the
recorded operator sequence. Source-file existence does not prove an operator
call.

## Next Action

Exact whole-chain signatures are now closed for this independent population.
The next Processing expansion lane is to recover evidence-backed local
subworkflows from these call-bearing rows, then cluster their recovered boundary
signatures before selecting a source-disjoint calibration packet. No rule, L3,
description, or training export is granted by this report.
