# L3 Prediction Accuracy Optimization Design

**Date:** 2026-03-25
**Status:** Draft
**Goal:** Improve end-to-end L3 Set F1 from 48% to 65-70%

## 1. Problem Statement

End-to-end evaluation (N=279, 全量数据 114K) shows two independent bottlenecks:

| Problem | Metric | Value | Impact |
|---------|--------|-------|--------|
| Sequences too short | Length Ratio | 0.70 | Caps Set F1 ceiling at 78% |
| Wrong token selection | Token efficiency | 61.4% | Only 61% of predicted tokens correct |

Combined, these limit Set F1 to **48%**. Target: **65-70%**.

### 1.1 Evidence: Sequence Length Problem

- **33% of predictions are only 4 tokens** (the minimum allowed)
- Predicted mean length: 6.4 vs reference mean: 10.7 (deficit: -4.3 tokens)
- Hard cutoff at `expected_length * 1.5` forces early termination
- `_apply_constraints()` blocks the last generated token from repeating (line 358-360), AND applies END boost after `expected_length` — combined effect is overly aggressive stopping

### 1.2 Evidence: Token Selection Problem

- L2 vs L3 confusion gap: 10.2% (correct L2 category but wrong L3 within it)
- Soft Set Sim = 0.999 confirms errors are near-identical semantically
- Set Predictor: F1=59%, P=46%, R=91% — predicts too many false positives
- Right-length samples have Set F1 = 47.9%, same as short ones — length alone won't fix everything

## 2. Architecture: Current Inference Flow

```
Task Input → Set Predictor (token budget) → Transformer (beam search with constraints) → L3 Sequence
                  ↓                                    ↓
           {token: count}                    _apply_constraints():
           P=46%, R=91%                      - Set budget mask (only allow budgeted tokens)
                                             - Block special tokens
                                             - Repetition penalty
                                             - No-repeat ngram
                                             - Transition matrix
                                             - Block consecutive same token
                                             - END boost after expected_length
```

## 3. Optimization Plan

### Phase 1: Fix Sequence Length (target: Length Ratio 0.70 → 0.90)

#### 1a. Relax Hard Cutoff

**File:** `infer_l3_candidates_v4.py`, lines 406 and 511

Current: `expected_length * 1.5` hard cutoff forces beam termination.
With `expected_length=8`, this kills beams at step 12, but reference sequences average 10.7.

**Change:**
```python
# Before
if len(tokens) - 1 > self.expected_length * 1.5:

# After: use 2.0x cutoff, minimum 15
cutoff = max(self.expected_length * 2.0, 15)
if len(tokens) - 1 > cutoff:
```

#### 1b. Soften END Token Boost

**File:** `infer_l3_candidates_v4.py`, lines 362-366

Current: Linear boost `1.0 * overshoot` starts immediately after `expected_length`.
With expected_length=8, at step 12 the boost is already +4.0 — strong enough to force END.

**Change:**
```python
# Before
if step > self.expected_length:
    overshoot = step - self.expected_length
    bonus = 1.0 * overshoot
    logits[:, END_INDEX] += bonus

# After: delayed start, gentler slope
grace = max(self.expected_length * 0.3, 2)  # grace period after expected_length
if step > self.expected_length + grace:
    overshoot = step - self.expected_length - grace
    bonus = 0.5 * overshoot  # gentler slope
    logits[:, END_INDEX] += bonus
```

#### 1c. Remove Consecutive Token Block

**File:** `infer_l3_candidates_v4.py`, lines 357-360

Current: Unconditionally blocks the last generated token from appearing next. This is too aggressive — some GIS workflows legitimately repeat the same L3 primitive (e.g., two consecutive "Raster Calculation" steps).

**Change:** Remove or gate behind a flag. The no-repeat-ngram constraint already prevents long repetitions.

#### 1d. Use Set Predictor Token Count as Length Hint

When Set Predictor predicts a budget like `{A:2, B:1, C:3}`, the total count (6) is a strong length signal. Use this instead of or in addition to `expected_length`:

```python
if predicted_counts:
    set_pred_length = sum(predicted_counts.values())
    self.expected_length = max(set_pred_length, self.expected_length)
```

### Phase 2: Improve Token Selection (target: efficiency 61% → 75%)

#### 2a. Raise Set Predictor Threshold

Current default `confidence_threshold=0.5`. Evaluation data shows:

| Threshold | F1 | Precision | Recall | AvgSize |
|-----------|-----|-----------|--------|---------|
| 0.5 | 0.59 | 46% | 91% | 15.8 |
| 0.7 | **0.65** | **57%** | 83% | 11.5 |

At thr=0.7, the prediction set is smaller and cleaner. The 83% recall means 17% of correct tokens are excluded, but the Transformer can still generate outside the budget when the budget runs out.

**Change:** `SET_PREDICTOR_CONFIDENCE_THRESHOLD` from 0.5 to 0.65 in `transformer_config.py`.

#### 2b. Budget Exhaustion Fallback

Currently when all budget tokens are spent, the constraint mask blocks everything except END. This forces premature stopping.

**File:** `infer_l3_candidates_v4.py`, `_apply_constraints()`

**Change:** When budget is exhausted, fall back to unconstrained mode:
```python
if budget is not None:
    remaining = sum(1 for v in budget.values() if v > 0)
    if remaining == 0:
        budget = None  # lift constraint, let Transformer decide freely
```

#### 2c. L2-Aware Beam Reranking

Since L2 accuracy (58%) > L3 accuracy (48%), add an L2-level scoring bonus during beam candidate selection. This helps the model prefer beams that cover the right L2 categories even if specific L3 choices differ.

**Implementation:** Post-beam reranking with L2 diversity bonus:
```python
# After beam search, rerank candidates by:
# final_score = log_prob / length + alpha * l2_diversity_bonus
```

This is lower priority and can be evaluated after Phase 1 + 2a/2b.

## 4. Implementation Order

| Step | Change | Files | Risk |
|------|--------|-------|------|
| 1a | Relax hard cutoff 1.5x → 2.0x | `infer_l3_candidates_v4.py` | Low |
| 1b | Soften END boost | `infer_l3_candidates_v4.py` | Low |
| 1c | Remove consecutive token block | `infer_l3_candidates_v4.py` | Low |
| 1d | Set Predictor count → length hint | `infer_l3_candidates_v4.py` | Low |
| 2a | Raise threshold 0.5 → 0.65 | `transformer_config.py` | Low |
| 2b | Budget exhaustion fallback | `infer_l3_candidates_v4.py` | Low |
| 2c | L2-aware reranking | `infer_l3_candidates_v4.py` | Medium |

All changes are **inference-only** — no retraining needed.

## 5. Evaluation Plan

After each step, run:
```bash
PYTHONPATH=src python scripts/evaluate_system.py --skip-qgis
```

Key metrics to track:
- **Set F1** (primary): target 65-70%
- **Length Ratio**: target 0.85-0.95
- **LCS Ratio**: should improve with longer sequences
- **Soft Set Sim**: should stay >0.99

Run Phase 1 (1a-1d) together, measure. Then Phase 2 (2a-2b), measure. Finally 2c if needed.

## 6. Non-Goals

- **No retraining** — all changes are inference-time parameter adjustments
- **No model architecture changes** — Transformer and Set Predictor models stay as-is
- **No QGIS layer changes** — Coverage=100%, Validity=100%, I/O=85.8% is already strong
