# Source-Grounded Extractor v1 Blind Holdout Review

Review date: 2026-07-16

## Scope

- Frozen predictions: review orders 16-50, 35 records.
- Source workbook SHA256: `ffd3ee18128d17de22c8d606eb3301b9f7611619ab89ad788b63c8fba09a2279`.
- Review method: joint user/Codex source-grounded adjudication in seven batches.
- No extractor changes, LLM labeling, taxonomy admission, training rows, or training runs occurred during review.

## Results

| Metric | Correct | Predicted | Precision |
| --- | ---: | ---: | ---: |
| E0 explicit evidence | 4 | 5 | 80.0% |
| E1 self-describing class | 0 | 0 | Not measurable |
| E2 reviewed direct API | 46 | 60 | 76.7% |
| E3 custom/unbounded | 12 | 39 | 30.8% |
| Overall emitted items | 62 | 104 | 59.6% |

Only 9/35 records (25.7%) were complete and free of emitted-item errors. Record grades were 9 correct, 13 partial, 4 incomplete abstentions, and 9 incorrect.

Item precision and workflow completeness are intentionally separate. A correct operator identity can still belong to a duplicated or severely incomplete chain. Empty predictions do not reduce item precision, but they fail completeness when a real bounded or custom workflow was omitted.

## Main Findings

1. E2 identity rules are useful but not sufficient. Direct API precision is 76.7%, while long workflows frequently retain only buffer, centroid, Translate, or BuildVRT fragments.
2. E3 is the main precision failure. Only 12/39 custom components were real algorithms or domain workflow orchestrators. Test classes, mocks, providers, data containers, helpers, and GUI/Dialog shells account for most false positives.
3. Source quality must be gated before extraction. Six reviewed records were test modules; they caused false E0, E2, and E3 emissions even when the referenced API or Processing ID was real.
4. Module-level custom functions are under-recovered. Harmonic interpolation, network analysis, HDF5 import, spatial query, raster stacking, shoreline extraction, and other real workflows disappeared when no suitable class identity existed.
5. Constructor and setup calls leak into chains. `QgsCoordinateTransform(...)` was incorrectly emitted as `native:reprojectlayer` in three records; only the later `transform`/`transformBoundingBox` calls represented operations.
6. Exact identity gaps remain. Confirmed examples include `gdal:proximity`, `gdal:merge`, `qgis:rastersampling`, `qgis:eliminateselectedpolygons`, extract-by-expression/save-features, and Shapely line polygonization incorrectly mapped to `gdal:polygonize` instead of `native:polygonize`.
7. Duplicate evidence still affects workflow quality. Same-input/same-output BuildVRT calls and parallel AST/steps confirmations must be distinguished from genuinely repeated operations.

## Decision

Extractor v1 is not admitted to the roughly 300-record pilot and must not produce taxonomy or training rows. `pilot_admission=blocked_pending_extractor_v2`.

Extractor v2 should implement, in order:

1. Reject test, mock, example, provider, and UI-only source modules before operator extraction.
2. Classify E3 roles into algorithm/orchestrator versus helper, data container, provider, mock, test, and GUI shell.
3. Suppress constructors and configuration objects; emit only execution calls.
4. Resolve bounded legacy/self-describing identities before exposing internal E2 implementation substeps.
5. Preserve reviewed module-level custom functions and their dependencies.
6. Add the confirmed bounded identity gaps and same-step duplicate merging.
7. Re-run the same locked 35 records as a regression set before selecting a new blind pilot.

Taxonomy admission and training admission remain `not_granted`.
