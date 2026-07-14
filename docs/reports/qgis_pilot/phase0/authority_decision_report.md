# Phase 0 Stable-94 Authority Decision Report

Status: `authority_decision_required`

No default configuration was changed.

## vocab_profile_v2_94_stable

| Role | Exists | Size | Path |
|---|---:|---:|---|
| id_mappings | True | 7844270 | `/home/qy/system_redesign/outputs_v2/id_mappings_v2.json` |
| l3_vocab | True | 4319 | `/home/qy/system_redesign/outputs_v2/l3_vocab_v2.json` |
| length_stats | True | 7672 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_v2_vec11277_augmented/task_type_length_stats.json` |
| set_predictor | True | 445821876 | `/home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_vec11277/best_model.pth` |
| set_predictor_active_tokens | True | 779 | `/home/qy/system_redesign/outputs_v2/set_predictor_active_tokens_vec11277.json` |
| splits | True | 656548 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_v2_vec11277_augmented/dataset_splits_vec_augmented_11277.json` |
| task_vocab | True | 3141 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_v2_vec11277_augmented/task_type_vocabulary_v4_quality_gate_qgis_vector_v2.json` |
| transition_matrix | True | 29276 | `/home/qy/system_redesign/outputs_v2/transition_allowed_next.json` |
| workflow | True | 159827762 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_v2_vec11277_augmented/labeled_workflows_l3_v4_vec_augmented_11277.json` |

## step8_v4_6_run_contract

| Role | Exists | Size | Path |
|---|---:|---:|---|
| id_mappings | True | 7844270 | `/home/qy/system_redesign/outputs_v2/id_mappings_v2.json` |
| l3_vocab | True | 4319 | `/home/qy/system_redesign/outputs_v2/l3_vocab_v2.json` |
| qgis_io_types | True | 178455 | `/home/qy/system_redesign/outputs_v2/qgis_operator_io_types.json` |
| set_predictor | False |  | `/home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3/best_model.pth` |
| splits | True | 748136 | `/home/qy/system_redesign/outputs_v2/dataset_splits_v4.json` |
| task_vocab | True | 3083 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json` |
| transformer_checkpoint | False |  | `/home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6/best_model.pth` |
| transition_matrix | True | 29276 | `/home/qy/system_redesign/outputs_v2/transition_allowed_next.json` |
| workflow | True | 189782234 | `/home/qy/system_redesign/outputs_v2/pipeline/step8/labeled_workflows_l3_v4_cleaned.json` |

## quality_gate_v4_6_entrypoints

| Role | Exists | Size | Path |
|---|---:|---:|---|
| id_mappings | True | 7844270 | `/home/qy/system_redesign/outputs_v2/id_mappings_v2.json` |
| l3_vocab | True | 4319 | `/home/qy/system_redesign/outputs_v2/l3_vocab_v2.json` |
| length_stats | True | 7582 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json` |
| qgis_io_types | True | 178455 | `/home/qy/system_redesign/outputs_v2/qgis_operator_io_types.json` |
| set_predictor | True | 445773364 | `/home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth` |
| set_predictor_active_tokens | True | 416 | `/home/qy/system_redesign/outputs_v2/set_predictor_active_tokens_quality_gate.json` |
| splits | True | 911579 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json` |
| task_vocab | True | 3083 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json` |
| transformer_checkpoint | True | 470003429 | `/home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth` |
| transition_matrix | True | 26272 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/transition_allowed_next.json` |
| workflow | True | 206501387 | `/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json` |

## Required Decision

Select one reviewed stable-94 restore authority before hashing/copying large checkpoints or running the restore smoke.
The report does not infer this choice.
