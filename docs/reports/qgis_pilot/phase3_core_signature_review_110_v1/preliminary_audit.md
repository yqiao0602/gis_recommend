# QGIS Core Signature Review Package: Preliminary Audit

Date: 2026-07-15

## Scope

This package covers all 110 `_steps.csv` files in the read-only
`WorkflowoutputQGIS_QGIS_Core_Processing` source. These files describe QGIS
Processing algorithm implementations. They are operator-signature evidence,
not 110 independent user workflows and not training rows.

The builder uses the CSV parser for both traces and the 1,292-record catalog,
retains source hashes, AST imports, class bases, ordered structured arguments,
parameter and output schemas, and provider evidence. It never calls an LLM.

## Result

| Metric | Count |
| --- | ---: |
| Source files | 110 |
| Files with AST | 110 |
| Class signatures | 117 |
| Human-review rows | 121 |
| Files with parameter schema | 94 |
| Files with provider evidence | 98 |
| Unique provider-consistent exact proposals | 61 |
| Unresolved review rows | 60 |
| Accepted human-reviewed anchors | 0 |
| Training rows emitted | 0 |

All 61 deterministic proposals remain `auto_proposed_pending_review`; none is
accepted automatically. The 60 unresolved rows comprise:

- 54 with no exact class-name match;
- 1 multi-provider evidence ambiguity: `RasterCalculator` imports/uses GDAL
  utilities while inheriting the QGIS algorithm base;
- 1 provider conflict: GDAL `Buffer` versus the exact QGIS/native class name;
- 4 files with no class scope.

The former claim that 13 classes were ambiguous was a pre-package count before
using AST imports, class bases, trace calls, and provider consistency. Those
signals reduce the final ambiguity queue to one row, while preserving one
explicit provider conflict. Provider token detection uses word/path boundaries;
`setProgress` and `Histogram` are not misclassified as OGR evidence.

## Preliminary Triage

This is not human adjudication. It only orders the review workload.

- The 61 exact proposals are operator-like and name/provider consistent. Review
  their parameter and output schemas before acceptance.
- About 30 no-exact rows appear to be real operator aliases or historical names,
  such as `ClipRasterByMask`, `buildvrt`, `gdalcalc`, `pct2rgb`,
  `EliminateSelection`, `FieldsPyculator`, and `RandomPointsAlongLines`.
- About 24 no-exact rows are framework, UI, provider, parameter, or helper
  classes, such as `GdalAlgorithmDialog`, `QgisAlgorithmProvider`,
  `ProcessingConfig`, and `ScriptEditorDialog`. These should normally be marked
  non-anchor after inspection, not forced to a catalog operator.
- The remaining exact ambiguity/provider-conflict/no-class rows require direct
  evidence review and must not default to the top-ranked candidate.

## Review Order

1. Confirm or reject the 61 unique exact proposals using class, provider, input,
   output, and parameter-label evidence.
2. Resolve the operator-like no-exact aliases against the bounded candidates.
3. Mark framework/UI/helper classes as non-anchor where supported by evidence.
4. Resolve `RasterCalculator` and GDAL `Buffer` explicitly.
5. Complete all 121 review rows before exporting any accepted anchor library.

Afterward, evaluate accepted anchors on a separate 50-record sample of ordinary
direct-API workflows. Do not inflate operator definitions into workflow counts.

## Artifacts

- Full server record: `signature_records.jsonl`, SHA256
  `011973f7a835a9bf7d99d782900ec991e6588ec93a690ab8ca2e5766e8111698`.
- Local review workbook: `signature_review.csv`.
- Local unresolved queue: `ambiguities.json` and `ambiguity_report.md`.
- Reproducibility ledger: `hash_ledger.json`.
- Server directory:
  `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase3_core_signature_review_110_v1/`.

Training admission remains `forbidden_until_human_review`.

## Verification

- Local: 41 related `unittest` tests passed.
- Server: the same 41 tests passed.
- The server package was rebuilt twice with identical full-record SHA256
  `011973f7a835a9bf7d99d782900ec991e6588ec93a690ab8ca2e5766e8111698`.
- The ledger covers 221 inputs (catalog plus 110 traces and 110 AST files).
- All five synchronized bounded outputs match their ledger hashes.

## Adjudication Progress

- Batches 01-02 were jointly reviewed and explicitly accepted by the user.
- Accepted: 20 exact GDAL operator signatures.
- Remaining: 101 of 121 review rows.
- Decisions are stored separately in `adjudication_decisions.jsonl`; the
  immutable proposal workbook is unchanged.
- Anchor export remains blocked until the full review is complete. Training rows
  emitted remain zero.
- `contour` and `contour_polygon` are accepted as separate operator anchors from
  one source file; they are not treated as a two-step workflow.
