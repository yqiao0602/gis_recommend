# Training Optimization Plan for the Six Core Problems

## Goal

Improve the quality of the recommended operator chains by aligning training, validation, and checkpoint selection with the real system objective: usable, executable, and semantically valid multi-solution workflows.

This plan is scoped to the current quality-gate mainline:
- Transformer: `scripts/train_v4_6_quality_gate.py`
- Set Predictor: `scripts/train_set_predictor_quality_gate.py`
- Data root: `outputs_v2/pipeline/step8_quality_gate/`
- Multi-solution ablations: `mr_all_42`, `mr_all_220`, `mr_all_1257`, `mr_all_1841`

## Current State

- Baseline, `mr_all_42`, `mr_all_220`, and `mr_all_1257` are already running or planned on the server.
- `mr_all_1841` is prepared but should only be used after smaller-scale results show a positive direction.
- The current risk is not lack of data alone. The larger risk is training/evaluation mismatch.

## Scope

This plan addresses the six known problems:
1. Multi-solution Problem
2. Workflow Complexity Problem
3. Generation Instability
4. Evaluation Misalignment
5. Ranking Problem
6. Semantic Constraint Problem

## Phase 0: Protect the Experiment

### Objectives
- Keep active runs isolated and comparable.
- Prevent noisy conclusions from loss-only or TokenAcc-only analysis.

### Actions
- Keep the current ablation ladder: baseline, `mr_all_42`, `mr_all_220`, `mr_all_1257`, then `mr_all_1841` only if justified.
- Record run metadata consistently for every experiment:
  - dataset version
  - source mix
  - checkpoint path
  - primary metric set
  - best checkpoint selection rule
- Monitor for:
  - `nan` / `inf`
  - early EOS spikes
  - invalid transition spikes
  - checkpoint drift between latest and best

### Acceptance Criteria
- Every run has a comparable report.
- No run is judged by TokenAcc or SeqEM alone.

## Phase 1: Fix Evaluation Misalignment

### Objective
Make checkpoint selection and validation reflect workflow quality, not token imitation.

### Actions
- Define a single validation hierarchy:
  - Primary: `SetF1`, `usable`, `executable`, `QGIS mapping`
  - Supporting: `LCS`
  - Diagnostic only: `TokenAcc`, `SeqEM`
- Update checkpoint selection to prefer workflow-level validation metrics instead of latest epoch or loss-only rules.
- Add a small validation rollout path that mimics constrained inference.

### Acceptance Criteria
- Best checkpoint is selected by workflow-level metrics.
- A model with better loss but worse usability cannot win by default.

## Phase 2: Address Workflow Complexity

### Objective
Teach the model to distinguish short, medium, and long workflows more explicitly.

### Actions
- Connect `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json` to training summaries.
- Add a lightweight auxiliary target such as:
  - task-type length bucket
  - short / medium / long complexity class
- Track per-task-type and per-bucket:
  - early END rate
  - overlength rate
  - invalid transition rate

### Acceptance Criteria
- Long workflows are less likely to terminate too early.
- Length errors are visible by task bucket, not only globally.

## Phase 3: Reduce Generation Instability

### Objective
Make training closer to inference behavior.

### Actions
- Add validation rollout that uses the same constrained decoding logic as inference.
- Measure invalid transitions during validation.
- Compare teacher-forced and rollout behavior in the same report.
- Keep scheduled sampling, but do not let it hide rollout instability.

### Acceptance Criteria
- Rollout validation exists and is used during model selection.
- Invalid transition rate is tracked and not silently ignored.

## Phase 4: Improve Set Predictor Coverage

### Objective
Make the Set Predictor better at coverage, not just set-level imitation.

### Actions
- Continue using multi-solution data in the Set Predictor target.
- Compare `mr_all_42`, `mr_all_220`, `mr_all_1257`, and `mr_all_1841` by:
  - set recall
  - top-k recall
  - usable downstream effect
- Evaluate whether the model learns more useful coverage when multi-solution examples expand.

### Acceptance Criteria
- Set Predictor improvements are judged by downstream planner utility, not only set F1.

## Phase 5: Build Ranking Supervision

### Objective
Teach the system how to choose among candidates.

### Actions
- After the ablation runs, build supervised candidate-ranking data from existing candidate pools.
- Use positives such as:
  - multi-reference matches
  - usable candidates
  - oracle-best candidates
- Use negatives such as:
  - invalid candidates
  - low-utility candidates
  - poor-mapping candidates
- Delay full ranking model training until the ablation results show which candidate families are most useful.

### Acceptance Criteria
- A future reranker dataset exists and is grounded in existing artifacts.
- Ranking training is separated from generation training.

## Phase 6: Add Lightweight Semantic Constraints

### Objective
Make the model aware of basic semantic compatibility before introducing heavier ontology authority.

### Actions
- Add auxiliary signals for:
  - QGIS mapping availability
  - transition compatibility
  - IO compatibility
- Keep this lightweight first. Do not jump directly to a heavy KG authority or runtime gating.

### Acceptance Criteria
- Semantic constraint signals exist in training summaries or auxiliary objectives.
- Invalid semantic combinations become easier to detect during training.

## Execution Order

1. Finish the current ablation ladder.
2. Close the evaluation gap with workflow-level checkpoint selection.
3. Add length/complexity auxiliary supervision.
4. Add constrained rollout validation.
5. Expand Set Predictor evaluation by source mix.
6. Build ranking supervision data.
7. Add lightweight semantic constraint signals.

## Risks and Mitigations

### Risk: More data does not help
Mitigation: keep source-family-separated ablations and do not assume larger is better.

### Risk: Loss improves while usability worsens
Mitigation: select checkpoints by workflow-level metrics, not loss.

### Risk: Complexity control overfits to length only
Mitigation: track early END, overlength, and invalid transitions by task type.

### Risk: Ranking work becomes a new blind spot
Mitigation: build ranking supervision only from existing verified or oracle-backed artifacts.

### Risk: Semantic constraints become runtime authority too early
Mitigation: keep them as lightweight auxiliary signals first.

## Verification

Each phase should be verified with a small, reproducible report:
- dataset version used
- source-family mix
- best checkpoint rule
- primary metric comparison
- known failure modes

Minimum verification for the next iteration:
- baseline vs `mr_all_42`
- baseline vs `mr_all_220`
- baseline vs `mr_all_1257`
- same report schema for all runs

## Deliverables

- Unified training comparison report
- Updated checkpoint selection rule
- Length/complexity auxiliary target design
- Rollout validation diagnostics
- Set Predictor source-mix comparison
- Candidate reranker data design
- Lightweight semantic constraint proposal

