# GEE P2 Rewrite Human Adjudication

This sidecar records human review decisions for the deterministic P2 rewrites.
It does not grant validation/test admission.

## Summary

- Rows: 8
- Adjudicated rows: 8
- Accepted train-only: 8
- Needs edit: 0
- Rejected: 0
- Training admission: `not_granted_pending_train_only_export_gate`

## Rows

### gee_raster_core_review_002

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: Retained select/mosaic/reduceRegions/limit chain is described; volume, area multiplication, and top-5 ranking stay in known omissions.

### gee_raster_core_review_003

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: NDVI mask, pixel-area multiplication, and region reduction are preserved; display layers and printed summaries remain omitted.

### gee_raster_core_review_015

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: Select/filter/reduce/reduceRegions chain matches the rewritten task; watershed area and export behavior stay omitted.

### gee_raster_core_review_016

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: V2 text grounds the cumulative-cost mask and retained country-code collection filter without claiming peat-forest overlay, alert display, or visual assessment.

### gee_raster_core_review_019

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: V2 text replaces unsupported cloud-criteria wording with source-evidenced date and WRS path/row metadata filtering while preserving the NDVI-temperature mask and area chain.

### gee_raster_core_review_025

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: Random Forest sampling/training/classification and class-area reduction are faithfully described; accuracy metrics remain omitted.

### gee_raster_core_review_032

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: Calibrated precipitation select/filterDate/filterBounds chain is faithful; clipping and downstream analysis remain omitted.

### gee_raster_core_review_048

- Task text faithful: yes
- Known omissions correct: yes
- Should enter train-only: yes_train_only
- Notes: TerraClimate mean/toBands/rename chain is preserved; annual composites, WorldClim comparison, and print output remain omitted.
