# Seed Subworkflow Semantic Review v1

| decision | rows | disposition |
|---|---:|---|
| `independent_workflow` | 11 | eligible for a separate Gold/Silver task-fidelity review |
| `implementation_subworkflow` | 17 | reject; parent implementation detail |
| `duplicate_or_parent_contained` | 3 | reject; no independent task distinction |

The 11 independent rows are not yet Gold or Silver training rows. Their task
text must be confirmed or rewritten from source-backed facts before admission.
All 31 decisions retain parent source lineage and remain evaluation-ineligible;
training rows emitted in this phase: 0.
