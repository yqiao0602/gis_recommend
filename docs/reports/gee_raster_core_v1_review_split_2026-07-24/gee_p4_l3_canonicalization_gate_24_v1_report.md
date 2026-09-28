# GEE P4 L3 Canonicalization Gate

Deterministic gate for mapping P4 source-extracted GEE calls into canonical GEE operators and L3 codes.
This report emits no training rows and does not reuse old P4 lineage L3 sequences.

## Summary

- Input rows: 24
- L3-ready rows: 18
- Rows needing canonicalization rules: 6
- Training rows emitted: 0
- Training admission: `not_granted_pending_export_gate`

## Top unmapped raw operators

- 1: `table.distinct`
- 1: `ndbi_bangunan.reducetovectors`
- 1: `ee.reducer.minmax`
- 1: `beforehh.focal_median`
- 1: `beforehv.focal_median`
- 1: `afterhh.focal_median`
- 1: `afterhv.focal_median`
- 1: `myregions.reducetoimage`
- 1: `myregions.reducetoimage.rename.aside`
- 1: `myfunctions.makeaeaproj`
- 1: `featurecollection.aggregate_array`
- 1: `meso_regions.geometry.dissolve`

## Rows

### gee_raster_core_review_004

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 78
- Canonical operators: 77
- Skipped raw operators: 1
- Unmapped raw operators: 0

### gee_raster_core_review_005

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 54
- Canonical operators: 47
- Skipped raw operators: 7
- Unmapped raw operators: 0

### gee_raster_core_review_006

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 22
- Canonical operators: 17
- Skipped raw operators: 5
- Unmapped raw operators: 0

### gee_raster_core_review_009

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 59
- Canonical operators: 58
- Skipped raw operators: 1
- Unmapped raw operators: 0

### gee_raster_core_review_010

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 31
- Canonical operators: 31
- Skipped raw operators: 0
- Unmapped raw operators: 0

### gee_raster_core_review_014

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 15
- Canonical operators: 10
- Skipped raw operators: 5
- Unmapped raw operators: 0

### gee_raster_core_review_018

- Source bucket: `p4_accepted`
- Status: `needs_canonicalization_rules`
- Raw operators: 21
- Canonical operators: 17
- Skipped raw operators: 3
- Unmapped raw operators: 1

### gee_raster_core_review_020

- Source bucket: `p4_accepted`
- Status: `needs_canonicalization_rules`
- Raw operators: 33
- Canonical operators: 28
- Skipped raw operators: 4
- Unmapped raw operators: 1

### gee_raster_core_review_021

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 11
- Canonical operators: 11
- Skipped raw operators: 0
- Unmapped raw operators: 0

### gee_raster_core_review_022

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 55
- Canonical operators: 44
- Skipped raw operators: 11
- Unmapped raw operators: 0

### gee_raster_core_review_027

- Source bucket: `p4_rewritten_needs_edit`
- Status: `needs_canonicalization_rules`
- Raw operators: 23
- Canonical operators: 17
- Skipped raw operators: 5
- Unmapped raw operators: 1

### gee_raster_core_review_029

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 24
- Canonical operators: 17
- Skipped raw operators: 7
- Unmapped raw operators: 0

### gee_raster_core_review_030

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 26
- Canonical operators: 26
- Skipped raw operators: 0
- Unmapped raw operators: 0

### gee_raster_core_review_031

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 57
- Canonical operators: 28
- Skipped raw operators: 29
- Unmapped raw operators: 0

### gee_raster_core_review_033

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 51
- Canonical operators: 45
- Skipped raw operators: 6
- Unmapped raw operators: 0

### gee_raster_core_review_034

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 29
- Canonical operators: 26
- Skipped raw operators: 3
- Unmapped raw operators: 0

### gee_raster_core_review_035

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 24
- Canonical operators: 21
- Skipped raw operators: 3
- Unmapped raw operators: 0

### gee_raster_core_review_038

- Source bucket: `p4_accepted`
- Status: `needs_canonicalization_rules`
- Raw operators: 38
- Canonical operators: 33
- Skipped raw operators: 1
- Unmapped raw operators: 4

### gee_raster_core_review_042

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 130
- Canonical operators: 130
- Skipped raw operators: 0
- Unmapped raw operators: 0

### gee_raster_core_review_044

- Source bucket: `p4_rewritten_needs_edit`
- Status: `needs_canonicalization_rules`
- Raw operators: 96
- Canonical operators: 89
- Skipped raw operators: 4
- Unmapped raw operators: 3

### gee_raster_core_review_045

- Source bucket: `p4_accepted`
- Status: `needs_canonicalization_rules`
- Raw operators: 23
- Canonical operators: 18
- Skipped raw operators: 3
- Unmapped raw operators: 2

### gee_raster_core_review_047

- Source bucket: `p4_rewritten_needs_edit`
- Status: `l3_ready`
- Raw operators: 29
- Canonical operators: 29
- Skipped raw operators: 0
- Unmapped raw operators: 0

### gee_raster_core_review_049

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 42
- Canonical operators: 39
- Skipped raw operators: 3
- Unmapped raw operators: 0

### gee_raster_core_review_050

- Source bucket: `p4_accepted`
- Status: `l3_ready`
- Raw operators: 153
- Canonical operators: 140
- Skipped raw operators: 13
- Unmapped raw operators: 0
