.human_dataset_fidelity = "pass"
| .human_temporal_fidelity = "pass"
| .human_spatial_fidelity = "pass"
| .human_transformation_fidelity = "pass"
| .human_output_fidelity = "pass"
| .human_task_text_fidelity = "pass"
| .human_critical_failure = "no"
| .human_decision = "pass"
| .human_notes = (
    if .source_path == "data140000/script_137440.txt"
    then "verified_after_export_map_contract_fix"
    else "carried_forward_from_exact_v5_full_chain_review"
    end
  )
