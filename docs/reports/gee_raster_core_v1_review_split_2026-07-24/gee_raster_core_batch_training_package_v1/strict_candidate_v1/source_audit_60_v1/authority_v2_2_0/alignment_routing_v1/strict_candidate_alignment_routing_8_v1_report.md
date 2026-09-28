# GEE Strict Alignment Routing v1

Technical source-review routing only. Human adjudication fields remain unchanged and no training rows are emitted.

## Counts

- accept_rebuilt_pending_export_gate: 1
- expand_dataflow_slice: 4
- reject_current_chain: 1
- rewrite_task_text_then_export_gate: 1
- split_repeated_subworkflows: 1

## Rows

### Rank 3: Extract water vapor at different times

- Route: `expand_dataflow_slice`
- Chain: `incomplete_minimal_window`
- Task text: `describes_repeated_selects_outside_window`
- Notes: Expand the toBands result through all five indexed select branches before text admission.

### Rank 15: Filter high-quality GEDI canopy height data

- Route: `expand_dataflow_slice`
- Chain: `incomplete_minimal_window`
- Task text: `describes_power_beam_filter_outside_window`
- Notes: Follow qa into the only_power callback and summed beam mask; the current window stops after QA masking.

### Rank 16: Detect edges in Sentinel-2 imagery

- Route: `reject_current_chain`
- Chain: `invalid_input_type`
- Task text: `not_executable_as_written`
- Notes: CannyEdgeDetector receives an ImageCollection without a source-proven image aggregation step.

### Rank 19: Identify bright urban areas

- Route: `accept_rebuilt_pending_export_gate`
- Chain: `complete_rebuilt`
- Task text: `faithful`
- Notes: The rebuilt chain restores the source-backed gte(50) threshold before Gaussian convolution.

### Rank 22: Extract median Sentinel-2 imagery

- Route: `rewrite_task_text_then_export_gate`
- Chain: `complete_rebuilt`
- Task text: `needs_dataset_name_rewrite`
- Notes: The chain is complete, but COPERNICUS/S2 must not be described as surface reflectance.

### Rank 49: Compute vegetation and water indices

- Route: `expand_dataflow_slice`
- Chain: `incomplete_minimal_window`
- Task text: `describes_three_index_branches`
- Notes: Recover NDVI, NDWI, NBR and both addBands joins; the current window covers only the first index branch.

### Rank 50: Compute vegetation and water indices

- Route: `expand_dataflow_slice`
- Chain: `incomplete_minimal_window`
- Task text: `describes_three_index_branches`
- Notes: Recover NDVI, NDWI, NBR and both addBands joins, then deduplicate against the normalized sibling workflow.

### Rank 58: Analyze VV and VH backscatter over water, dryland, wetland, and irrigated areas

- Route: `split_repeated_subworkflows`
- Chain: `oversized_parallel_window`
- Task text: `broadly_faithful_but_not_single_chain`
- Notes: Split by land-cover, polarization, and year branches; a 139-operator linearized window is not a usable single workflow label.
