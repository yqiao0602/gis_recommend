# QGIS Mapped Recovery/Split Family Census v1

This is an overlapping mechanism census, not training admission.

- Input rows: 272
- Verified rows: 272
- Independent source authorities: 254
- Multi-step local units: 138
- Currently eligible units: 19
- Training rows emitted: 0

## Recovery Mechanisms

| Family | Rows | Authorities | Rows with multi-step | Current eligible units | Calibration status |
|---|---:|---:|---:|---:|---|
| parameter_dictionary | 169 | 161 | 57 | 8 | pending_source_disjoint_precision_calibration |
| result_dictionary | 115 | 110 | 46 | 0 | pending_source_disjoint_precision_calibration |
| output_alias | 78 | 74 | 34 | 0 | pending_source_disjoint_precision_calibration |
| immediate_output_extract | 73 | 71 | 47 | 13 | pending_source_disjoint_precision_calibration |
| backward_slice_alias | 54 | 53 | 48 | 4 | pending_source_disjoint_precision_calibration |
| helper_function_call | 37 | 35 | 20 | 5 | pending_source_disjoint_precision_calibration |
| cross_function_dataflow | 5 | 5 | 5 | 0 | frozen_support_below_30 |
| parameter_dictionary_mutation | 1 | 1 | 0 | 0 | frozen_support_below_30 |

## Structural Blockers

| Blocker | Rows | Authorities |
|---|---:|---:|
| control_flow:for | 44 | 44 |
| downstream_data_transform | 45 | 43 |
| missing_data_edges | 23 | 23 |
| intermediate_data_transform | 22 | 22 |
| control_flow:if | 23 | 21 |
| conditional_early_exit | 17 | 16 |
| control_flow:try | 12 | 10 |
| downstream_low_level_data_transform:addFeature | 10 | 8 |
| downstream_low_level_data_transform:setGeometry | 9 | 7 |
| downstream_low_level_data_transform:commitChanges | 6 | 5 |
| downstream_low_level_data_transform:startEditing | 6 | 5 |
| downstream_low_level_data_transform:updateFeature | 6 | 4 |
| downstream_low_level_data_transform:materialize | 3 | 3 |
| downstream_processing_consumer:gdal:cliprasterbymasklayer | 3 | 3 |
| downstream_processing_consumer:native:clip | 3 | 3 |
| downstream_low_level_data_transform:changeAttributeValue | 1 | 1 |
| unused_temporary_terminal | 1 | 1 |
