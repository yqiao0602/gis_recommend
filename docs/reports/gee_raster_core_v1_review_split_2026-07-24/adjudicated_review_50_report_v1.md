# GEE raster-core review_50 adjudication draft

This draft merges the five 10-row human-adjudication batches. The original `review_50.csv` remains unchanged.

## Summary

- Rows reviewed: 50
- Accepted as train-only candidates: 9 (18.0%)
- Deferred: 41 (82.0%)
- Task-text fidelity: {'yes': 22, 'partial': 27, 'no': 1}
- L3-chain correctness: {'yes': 18, 'partial': 32}
- Chain completeness: {'yes': 9, 'partial': 41}
- Split counts: {'train': 40, 'val': 5, 'test': 5}
- Accept by split: {'train': 7, 'val': 2}

## Decision

- Dataset-level training admission remains `not_granted`.
- Accepted rows are only candidate train-only raster/L3 semantic rows; they must not enter validation/test or QGIS operator-chain gold evaluation.
- Deferred rows are mainly caused by missing helper-expanded feature construction, masking, model evaluation, vector aggregation, UI/export/statistics side effects, or task descriptions that exceed the retained core chain.

## Accepted review IDs

gee_raster_core_review_001, gee_raster_core_review_008, gee_raster_core_review_011, gee_raster_core_review_017, gee_raster_core_review_023, gee_raster_core_review_036, gee_raster_core_review_037, gee_raster_core_review_041, gee_raster_core_review_043

## Deferred review IDs

gee_raster_core_review_002, gee_raster_core_review_003, gee_raster_core_review_004, gee_raster_core_review_005, gee_raster_core_review_006, gee_raster_core_review_007, gee_raster_core_review_009, gee_raster_core_review_010, gee_raster_core_review_012, gee_raster_core_review_013, gee_raster_core_review_014, gee_raster_core_review_015, gee_raster_core_review_016, gee_raster_core_review_018, gee_raster_core_review_019, gee_raster_core_review_020, gee_raster_core_review_021, gee_raster_core_review_022, gee_raster_core_review_024, gee_raster_core_review_025, gee_raster_core_review_026, gee_raster_core_review_027, gee_raster_core_review_028, gee_raster_core_review_029, gee_raster_core_review_030, gee_raster_core_review_031, gee_raster_core_review_032, gee_raster_core_review_033, gee_raster_core_review_034, gee_raster_core_review_035, gee_raster_core_review_038, gee_raster_core_review_039, gee_raster_core_review_040, gee_raster_core_review_042, gee_raster_core_review_044, gee_raster_core_review_045, gee_raster_core_review_046, gee_raster_core_review_047, gee_raster_core_review_048, gee_raster_core_review_049, gee_raster_core_review_050
