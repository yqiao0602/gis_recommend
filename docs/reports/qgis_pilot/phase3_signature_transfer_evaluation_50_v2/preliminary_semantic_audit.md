# QGIS Signature Transfer Preliminary Semantic Audit

Date: 2026-07-15

## Scope

- Authority: 93 human-accepted operator signature anchors.
- Evaluation pool: 4,673 independent `direct_api_only` workflows after excluding the prior 300-record pilot and 24-record canary.
- Baseline: exact operation overlap with anchor document frequency <= 5 and workflow document ratio <= 10%, scored with dual IDF.
- Diagnostic sample: 30 candidate-bearing records and 20 abstentions, with unique record IDs and source scripts.
- This artifact is evaluation-only. It grants neither taxonomy nor training admission.

## Reproduced Result

- Candidate-bearing workflows: 3,388 / 4,673 (72.50%).
- Abstentions: 1,285 / 4,673 (27.50%).
- Eligible exact-match operations: 79.
- LLM calls: 0.
- Human top-1 precision and abstention accuracy: pending.

Candidate coverage is not accuracy. The earlier 98.8% naive overlap and the current 72.50% filtered coverage must not be reported as transfer correctness.

## Preliminary Findings

The first deterministic sample exposes systematic false positives from shared implementation calls:

- `gdal.open` occurs in 439 / 4,673 workflows (9.39%), just below the 10% cutoff. It makes `gdal:extractprojection` the top-1 result for 12 of the 30 candidate records, including spectral unmixing, land-cover smoothing, EnMAP import, DSM generation, and urban summary tasks.
- Geometry primitives such as `qgsgeometry.area`, `qgsgeometry.length`, `qgsgeometry.fromrect`, and WKB-type inspection calls transfer implementation similarity rather than operator identity.
- The known false-positive pattern is reproduced: `Convert geometry type` ranks `qgis:linestopolygons` from polygon/WKB helper calls.

An unpersisted threshold diagnostic restricted workflow evidence to `semantic_anchor` calls. Candidate coverage fell to 1,127 / 4,673 with only eight eligible operations. It removed the `gdal.open` failure but did not solve the architectural problem: shared calls such as `transformBoundingBox` still mapped unrelated download workflows to `qgis:rastercalculator`.

## Gate Decision

The signature library is useful as reviewed operator implementation evidence, but exact call transfer is not yet a reliable automatic workflow labeler. Keep all 50 rows `pending` and complete human review before considering family-aware/text-aware reranking. Do not emit QGIS operator chains, L3 labels, taxonomy changes, or training rows from this baseline.

The server directory `phase3_signature_transfer_evaluation_50_v1` is an intermediate stricter-filter diagnostic (3,194 candidates) and is not the authority. The synchronized `phase3_signature_transfer_evaluation_50_v2` artifact reproduces the predeclared 3,388 baseline and is the active human-review package.

## Human Review Progress

- Batch 01 (2026-07-16): review rows 1-5 jointly adjudicated.
- Correct top-1: 1 (`qgis:rastercalculator` for raster boolean overlay sum).
- Incorrect top-1: 4 (shared geometry primitives, generic `gdal.open`, and layer metadata calls).
- Partial candidate top-1 precision: 1 / 5 = 20%.
- Remaining: 45 rows; abstention accuracy is still unavailable.

Decisions are stored separately in `human_adjudications.jsonl` and bound to immutable review SHA256 `6e7f92606a1e43562c98285fcaa3b6ff149c62aca051d67ce8c5136f74daa314`.
