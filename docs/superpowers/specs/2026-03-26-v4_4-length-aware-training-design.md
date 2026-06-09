# V4.4 Training: Length-Aware Warm-Start from V4.2

**Date:** 2026-03-26
**Status:** Draft
**Goal:** Fix short-sequence bias (pred mean=6.4 vs ref mean=10.7), improve Set F1 from 48% to 58-65%

## 1. Root Cause Analysis

V4.2 model generates sequences averaging 6.4 tokens while ground truth averages 10.7. Seven systemic biases identified:

| # | Root Cause | Severity |
|---|-----------|----------|
| 1 | Curriculum Phase 1: 6 epochs training only ≤8 token sequences | Critical |
| 2 | Curriculum Phase 2: 10 more epochs only ≤15 tokens | High |
| 3 | AR training truncated at 40 steps | Moderate |
| 4 | Length loss weight=0.1, applied to START token only | Moderate |
| 5 | Length loss uses ground truth length, not AR-generated length | Moderate |
| 6 | END token has no position-aware penalty | Moderate |
| 7 | Decode min_length=4 (too short) | Low |

## 2. Design: V4.4 Training Script (`train_v4_4.py`)

New training script that inherits from V4.2 trainer and overrides the problematic components.

### 2.1 No Curriculum — Full Data From Epoch 1

```python
# V4.4: No curriculum filtering, use all sequences from the start
curriculum_phases = None  # Disabled
train_indices = list(range(len(train_workflows)))  # All data
```

**Rationale:** Curriculum was designed to stabilize early training, but V4.4 warm-starts from a converged V4.2 model — no need for curriculum stabilization.

### 2.2 Enhanced Length Loss (weight 0.1 → 0.5)

```python
V4_4_LENGTH_LOSS_WEIGHT = 0.5  # Was 0.1

# In AR mode: compute length loss on GENERATED sequence length
def _ar_length_loss(self, length_pred, generated_lengths, target_lengths):
    """Penalize deviation between generated and target lengths."""
    log_gen = torch.log(generated_lengths.float().clamp(min=1))
    log_target = torch.log(target_lengths.float().clamp(min=1))
    # MSE between generated and target in log-space
    return F.mse_loss(log_gen, log_target) + F.mse_loss(length_pred.squeeze(-1), log_target)
```

**Key change:** In AR mode, length loss now has two terms:
1. Model's length predictor output vs target (existing)
2. Actual generated length vs target (NEW — provides gradient signal about early stopping)

### 2.3 Early END Penalty

During AR training, when the model generates END before reaching 70% of the target sequence length, apply an additional loss:

```python
V4_4_EARLY_END_PENALTY = 2.0
V4_4_EARLY_END_THRESHOLD = 0.7  # Penalize END before 70% of target length

# In AR training loop, when model predicts END too early:
if predicted_token == END_INDEX and step < target_length * V4_4_EARLY_END_THRESHOLD:
    # Add penalty: CE loss for this position gets extra weight
    early_penalty = V4_4_EARLY_END_PENALTY * ce_loss_at_this_step
    total_loss += early_penalty
```

**Rationale:** This directly teaches the model "don't generate END early". The penalty is proportional to how early END appears.

### 2.4 Dynamic Minimum Length in AR Training

During AR-SS training, block END token until reaching a dynamic minimum:

```python
# During AR decoding in training:
dynamic_min_len = max(int(target_length * 0.5), 5)  # At least 50% of target, min 5
if step < dynamic_min_len:
    step_logits[:, END_INDEX] = float('-inf')
```

**Rationale:** Forces the model to learn to generate longer content before being allowed to stop. Different from inference-time min_length because this affects gradient flow.

### 2.5 Warm-Start Configuration

```python
V4_4_WARMSTART_PATH = V4_2_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
V4_4_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_4"

# Training schedule — skip TF-only and curriculum, go straight to AR-SS
V4_4_NUM_EPOCHS = 25
V4_4_TF_PHASE_EPOCHS = 0          # No TF-only phase
V4_4_SS_TF_START = 0.3            # Start with 30% TF (model already learned basics)
V4_4_SS_TF_END = 0.0              # End with pure AR
V4_4_AR_RATIO_START = 0.5         # Start with 50% AR batches (aggressive)
V4_4_AR_RATIO_END = 0.9           # End with 90% AR
V4_4_WARMUP_EPOCHS = 2
V4_4_EARLY_STOPPING_PATIENCE = 12

# Learning rates — lower than V4.2 since warm-starting
V4_4_OTHER_LR = 5e-5              # Half of V4.2's 1e-4
V4_4_BERT_LR = 5e-6               # Half of V4.2's 1e-5
```

### 2.6 Loss Composition

```python
total_loss = (
    main_ce_loss                           # weight 1.0 (token prediction)
    + V4_4_LENGTH_LOSS_WEIGHT * length_loss  # weight 0.5 (length matching)
    + early_end_penalty                    # weight 2.0 per occurrence
    + task_cls_weight * task_loss           # weight 0.1 (task classification)
)
```

## 3. Implementation Plan

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `config/transformer_config.py` | Modify | Add V4.4 config section |
| `training/train_v4_4.py` | Create | New training script inheriting from V4.2 |

### `train_v4_4.py` Structure

```python
class ScheduledSamplingTrainerV4_4(ScheduledSamplingTrainerV4_2):
    """V4.4: Length-aware warm-start training.

    Changes from V4.2:
    - No curriculum (all data from epoch 1)
    - Enhanced length loss (weight 0.5, uses AR-generated length)
    - Early END penalty during AR training
    - Dynamic min_length in AR decoding
    - Warm-start from V4.2 checkpoint
    """

    def _train_one_epoch(self, epoch):
        # Override: no curriculum filtering
        # Override: modified AR loop with END penalty + dynamic min_length
        ...

    def _ar_train_step(self, batch, tf_ratio):
        # Override: add early END penalty
        # Override: compute AR-generated length for length loss
        # Override: dynamic min_length blocking
        ...

    def _compute_ar_length_loss(self, generated_lengths, target_lengths, length_pred):
        # NEW: length loss on actual generated lengths
        ...
```

## 4. Training Procedure

```bash
# On server:
PYTHONPATH=src python -m gis_recommend.training.train_v4_4

# Expected: ~25 epochs, ~8-10 hours on A10
# Warm-starts from: outputs/transformer_checkpoints_v4_2/best_model.pth
# Saves to: outputs/transformer_checkpoints_v4_4/best_model.pth
```

## 5. Evaluation

After training:
```bash
# Update evaluate_system.py to use V4_4 checkpoint, or:
PYTHONPATH=src python scripts/evaluate_system.py --skip-qgis
```

**Target metrics:**
- Length Ratio: 0.70 → **0.85-0.95**
- Set F1: 0.48 → **0.58-0.65**
- LCS Ratio: 0.34 → **0.42-0.50**
- Soft Set Sim: stay >0.99

## 6. Risk Mitigation

- **Risk:** Warm-start might overfit or diverge
  - **Mitigation:** Lower LR (half of V4.2), patience=12
- **Risk:** END penalty too aggressive → sequences too long
  - **Mitigation:** Only penalize before 70% of target, penalty=2.0 (tunable)
- **Risk:** Removing curriculum destabilizes training
  - **Mitigation:** Model already converged from V4.2; no curriculum needed

## 7. Rollback Plan

If V4.4 underperforms V4.2, simply switch checkpoint path back to `transformer_checkpoints_v4_2/best_model.pth`. No code changes needed — inference code reads checkpoint path from config.
