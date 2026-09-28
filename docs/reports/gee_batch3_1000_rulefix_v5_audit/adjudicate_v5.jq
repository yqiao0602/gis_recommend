(
  .human_dataset_fidelity,
  .human_temporal_fidelity,
  .human_spatial_fidelity,
  .human_transformation_fidelity,
  .human_output_fidelity,
  .human_task_text_fidelity
) = "pass"
| .human_critical_failure = "no"
| .human_decision = "pass"
| .human_notes = (
    if .source_sha256 == "08b6de758c8708cb90a6b6487546d27fff52253823accf72b77e89baa3fcab76" then
      "Full-source audit passed: ASTER dataset/date/spatial facts and the 35-step eight-index logical extraction DAG, L3 sequence, export sink, and task text are complete and faithful."
    elif .source_sha256 == "08e6c869ee2b7276c878758e85be429ee5d67e2f5582cb8da25a795a95a896d7" then
      "Full-source audit passed: JRC wet-season filterDate-select-mosaic-clip chain, private AOI dependency, sibling-export isolation, L3 sequence, output, and task text are complete and faithful."
    else
      "Inherited full-source audit pass: dataset, temporal, spatial, complete transformation DAG, L3 sequence, output, and task text are faithful."
    end
  )
