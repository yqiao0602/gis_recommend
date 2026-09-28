# M1 sampler pilot: 4 ratios × 3 epochs, protocol verification

Pre-training preflight per the user's fixed protocol (2026-09-08). Purpose is
sampler verification only — no model training, no ratio selection by loss.
The 70:30 main plan is pre-registered; R0/R1/R3 exist to confirm the mechanism
across the range.

## Protocol deviation found and resolved (needs user sign-off)

The new 8,283-row GEE authority carries a **constant** task_type
(`GEE_COMPLETE_OUTPUT_WORKFLOW`, all rows) — the 47 semantic task types belonged
to the old legacy baseline's vocabulary and do not exist in the new authority.
The per-row semantic signal available is the **first L3 code (entry family,
37 strata)**. The pilot stratifies GEE by first-L3 entry family instead of
task-type. QGIS stratification is as specified (chain length 1 / 2-3 / 4-7 / 8+).
**This substitution awaits preflight confirmation.**

## Pilot results (real paper_v1 train rows, 3 epochs each)

| Ratio | GEE share observed (3 ep) | QGIS strata share | GEE entry families | QGIS unique rows/epoch (of 616) |
|---|---|---|---|---|
| R0 93:7 | 0.930 / 0.929 / 0.931 | ~25% ×4 | 37/37 | 325 / 313 / 321 |
| R1 80:20 | 0.794 / 0.800 / 0.803 | ~25% ×4 | 37/37 | 504 / 510 / 500 |
| **R2 70:30** | **0.701 / 0.697 / 0.694** | ~25% ×4 | 37/37 | 553 / 545 / 556 |
| R3 50:50 | 0.503 / 0.507 / 0.496 | ~25% ×4 | 37/37 | 602 / 597 / 600 |

All verification criteria pass: observed platform ratios within ±0.6% of
target; QGIS four length strata uniform within ±3%; all 37 GEE entry families
observed every epoch; epoch = 8,928 samples (ceil(8,817/32)×32 — note the
train set is 8,817 after dropping empty-text rows, so samples/epoch is
8,832 for the real set, not 8,928); QGIS repetition ~4.3×/row/epoch at 70:30
(553 unique of 616 per epoch ≈ 89.8% coverage per epoch); batch contract
untouched (sampler yields indices only).

## Note on epoch size

The user-fixed definition ceil(N/batch)×batch with N = full train set
(8,817 non-empty rows, batch 32) gives **276 batches × 32 = 8,832
samples/epoch** (not 8,928, which assumed N = 8,912 including the 95
empty-text rows that cannot be trained on). The pilot ran with the
dataset-length-based value; the trainer must use 8,832.

## Files

`pilot_results_v1.json` (all four ratios, three epochs each), sampler
`scripts/platform_stratified_sampler.py`, tests 8/8
(`tests/test_platform_stratified_sampler.py`).
