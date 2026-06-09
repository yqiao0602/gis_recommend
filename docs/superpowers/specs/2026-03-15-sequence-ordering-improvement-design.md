# Design: Improve L3 Sequence Ordering (V4.3 + RL)

**Date:** 2026-03-15
**Status:** Draft (Rev 2 — post spec review)

## Problem Statement

Evaluation reveals a critical ordering gap in L3 sequence generation:

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Set F1 | 49.14% | Model selects ~right tokens |
| Token Accuracy | 7.65% | But places them in wrong positions |
| LCS Ratio | 0.2151 | Poor subsequence overlap |
| L2 Positional Accuracy | 12.91% | Even coarse categories misaligned |

The model knows WHICH L3 operations to use but cannot arrange them in the correct ORDER during autoregressive inference. This is caused by exposure bias: training uses ground truth context (teacher forcing), but inference uses the model's own predictions.

## Diagnosis: Why Current AR Training Fails

The V4.2 training schedule has three structural issues:

1. **AR starts too late (epoch 10)**: `V4_TF_PHASE_EPOCHS = 10` — the model trains in pure teacher forcing for 10 epochs. By then, it has learned to rely on ground truth context. When AR-SS begins at epoch 10, the model cannot unlearn this dependency.

2. **TF ratio starts at 100% in AR phase**: `V4_SS_TF_START = 1.0` — when the AR-SS phase begins, the within-step TF ratio is 100%, decaying to 10% (`V4_SS_TF_END = 0.1`) via inverse sigmoid. This means the transition from TF to AR is extremely gradual — the model barely sees its own predictions early in Phase B.

3. **AR batch ratio ramps too slowly**: `V4_1_AR_RATIO_START = 0.1`, `V4_1_AR_RATIO_END = 0.7` — at the batch level, only 10% of batches use AR-SS initially, and even at the end, 30% of batches are still pure TF. The model never experiences a fully AR training environment.

Note: `V4_2_AR_MAX_STEPS = 40` caps AR training at 40 steps, but since average sequence length is ~15 and most sequences are < 25, this cap rarely activates. It is not a primary concern.

### Two levels of TF/AR control (clarification)

The V4.2 training uses two independent mechanisms:

- **Batch-level** (`ar_ratio`): What fraction of batches in an epoch use AR-SS vs pure TF. Controls how often the model encounters AR training at all.
- **Within-step** (`tf_ratio`): During an AR-SS batch, at each decoding position, the probability of using the ground truth token vs the model's own prediction. Controls the severity of exposure to its own errors.

Both must be reduced for the model to learn ordering under realistic inference conditions.

## Design

### Phase 1: V4.3 — Fixed AR Training Regime

#### Config Changes

| Parameter | Level | V4.2 (actual) | V4.3 (proposed) | Rationale |
|-----------|-------|----------------|------------------|-----------|
| TF-only phase | schedule | 10 epochs | 3 epochs | Sufficient for basic token/embedding learning |
| tf_ratio start | within-step | 1.0 | 0.5 | Start with 50% own-predictions from AR-SS onset |
| tf_ratio end | within-step | 0.1 | 0.0 | Reach pure AR (0% TF) by end of training |
| ar_ratio start | batch-level | 0.1 | 0.3 | 30% of batches are AR-SS from the start |
| ar_ratio end | batch-level | 0.7 | 1.0 | All batches use AR-SS by end |

#### Warm-Start Strategy

Load V4.2 best checkpoint (`transformer_checkpoints_v4_2/best_model.pth`) as weight initialization. Since the model already has good token prediction from V4.2, skip the TF-only phase and start directly with AR-SS from epoch 0. The 3-epoch TF phase exists only for from-scratch training.

When warm-starting:
- Learning rate: use V4.2 values (`V4_2_OTHER_LR = 1e-4`, `V4_2_BERT_LR = 1e-5`)
- Warmup: 1 epoch (shorter than from-scratch's 3 epochs since weights are pre-trained)
- LR schedule: cosine annealing from warmup to end

#### Training Script

New file `src/gis_recommend/training/train_v4_3.py`, based on `train_v4_2.py` with:
- Updated AR schedule parameters (table above)
- Warm-start loading from V4.2 checkpoint
- Skip TF-only phase when warm-starting
- Evaluation with SetF1, LCS, Token Accuracy tracked per epoch
- Keep all existing auxiliary losses (length, task_cls, transition) unchanged

TF noise injection (randomly replacing ground truth tokens during TF phase) is **out of scope** for V4.3 — it only applies during the TF-only phase, which warm-start skips. If from-scratch training is ever needed, this can be added later.

#### Expected Outcome

Token Accuracy should improve from 7.65% toward 15-25%. Set F1 should be maintained at >= 45%. The gap between Set F1 and Token Accuracy should narrow, indicating better ordering.

### Phase 2: V4.3-RL — REINFORCE Fine-tuning

Applied only if Phase 1 Token Accuracy < 25%.

#### Method: Self-Critical Sequence Training (SCST)

For each training sample:
1. Sample K=4 sequences **sequentially** using nucleus sampling (temperature=0.8, top_p=0.9). Memory footprint equals single-sequence generation.
2. Greedy decode 1 sequence as baseline (no sampling, argmax at each step).
3. Compute reward for each: `R = 0.5 * SetF1 + 0.3 * LCS_ratio + 0.2 * L2_accuracy`
4. REINFORCE gradient: for each sampled sequence k, `grad += (R_k - R_baseline) * grad_log_P(seq_k)`
5. Update parameters

#### Reward Function Dependencies

Uses `SemanticMetricsCalculator` from `gis_recommend.evaluation.semantic_metrics`. Constructor requires:
- `l3_embeddings_path`: `OUTPUT_DIR / "l3_embeddings.pt"` (350x256 tensor)
- `hierarchy_csv_path`: `PROJECT_ROOT / "classification_hierarchy.csv"` (L3→L2 mapping)
- `id_to_l3_code`: `Dict[int, str]` loaded from `OUTPUT_DIR / "id_mappings.json"` (key `"l3"`, invert to get id→code)

`SetF1` and `lcs_ratio` are static methods (no self needed). `l2_accuracy` requires the instance (uses `l3_to_l2` mapping). All operate on `List[int]` token IDs and are non-differentiable — this is expected for REINFORCE, which uses the reward as a scalar signal, not as a differentiable loss.

Computational cost: `_lcs_length` is O(n*m) DP. For K=4 samples + 1 baseline per instance, batch_size=16 = 80 LCS calls per batch. At typical sequence length ~15, each LCS call is O(225) — negligible. At max length 100, O(10000) per call, still fast on CPU.

#### Training Details

- Load V4.3 best checkpoint
- Freeze BERT entirely (only update decoder)
- Learning rate: 1e-5 (10x lower than CE training)
- Warmup: 100 steps (linear)
- Gradient clipping: 0.5 (tighter than CE's 1.0)
- Epochs: 5-10, early stopping on validation mean reward
- **Mixed objective**: `L = L_REINFORCE + 0.1 * L_CE` — a small CE regularization term prevents catastrophic forgetting of token-level knowledge during RL fine-tuning. The CE loss uses the same teacher forcing setup as V4.2.
- Batch size: 16 (K=4 samples generated sequentially, so memory per instance equals single generation)

#### Training Script

New file `src/gis_recommend/training/train_v4_3_rl.py`.

## File Structure

| File | Action |
|------|--------|
| `src/gis_recommend/training/train_v4_3.py` | **Create** — Phase 1 training with fixed AR regime |
| `src/gis_recommend/training/train_v4_3_rl.py` | **Create** — Phase 2 REINFORCE fine-tuning |
| `src/gis_recommend/config/transformer_config.py` | **Edit** — Add V4.3 config section |

New config constants:
```python
# V4.3 Configuration
V4_3_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_3"
V4_3_TF_PHASE_EPOCHS = 3
V4_3_SS_TF_START = 0.5
V4_3_SS_TF_END = 0.0
V4_3_AR_RATIO_START = 0.3
V4_3_AR_RATIO_END = 1.0
V4_3_WARMSTART_PATH = V4_2_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
V4_3_WARMUP_EPOCHS = 1           # Shorter warmup for warm-start
V4_3_NUM_EPOCHS = 40

# V4.3-RL Configuration
V4_3_RL_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_3_rl"
V4_3_RL_LR = 1e-5
V4_3_RL_GRADIENT_CLIP = 0.5
V4_3_RL_BATCH_SIZE = 16
V4_3_RL_NUM_SAMPLES = 4          # K=4 sampled sequences
V4_3_RL_CE_WEIGHT = 0.1          # CE regularization weight
V4_3_RL_NUM_EPOCHS = 10
```

No changes to model architecture, inference code, or evaluation pipeline.

## Verification

```bash
# Phase 1
python -m gis_recommend.training.train_v4_3

# Evaluate
python scripts/evaluate_system.py --skip-qgis

# Phase 2 (if Token Accuracy < 25%)
python -m gis_recommend.training.train_v4_3_rl

# Re-evaluate
python scripts/evaluate_system.py --skip-qgis
```

## Success Criteria

1. **Phase 1**: Token Accuracy > 15%, Set F1 >= 45%, LCS ratio > 0.30
2. **Phase 2** (if applied): Token Accuracy > 25%, LCS ratio > 0.40
3. No regression in Set F1 (content selection quality)
