# L3 Inference Optimization Design

## Problem

The Transformer V4.2 model generates L3 sequences that are too long and contain redundant codes:
- Training data averages ~14.69 steps (config comment), but `max_length=50` (constructor default in `infer_l3_candidates_v4.py`) allows generation up to 50 steps
- Consecutive identical L3 codes appear (e.g., L3_09_03_01 → L3_09_03_01) despite being cleaned from training data
- Length score weight (20%) is too low to compete with log_prob (40%)
- `expected_length=12` is hardcoded in inferencer constructor, ignoring task-type-specific distributions
- No early stopping mechanism beyond waiting for all beams to emit END

Test results show chains of 11-14 steps where 3-5 would suffice, with LLM correctly scoring them 2-4/10.

## Goals

1. Reduce generated L3 sequence lengths to match training data distribution
2. Eliminate consecutive duplicate L3 codes
3. Add early stopping to beam search so sequences naturally terminate at appropriate lengths
4. Dynamically adjust expected length based on task type
5. Post-process sequences to remove remaining redundancy

## Architecture Constraints

- **No retraining**: Only modify inference code and configuration
- **No model changes**: The trained Transformer V4.2 checkpoint stays untouched
- **API backward compatible**: The V4 inferencer's existing `infer()` and `infer_from_model_input()` APIs remain unchanged; `set_expected_length()` is optional (defaults to global fallback)
- **Files touched**: `transformer_config.py`, `infer_l3_candidates_v4.py`, `interactive_system.py` (one-line call), one new stats script

## Changes

### 1. Parameter Adjustments

**Score weights — File:** `src/gis_recommend/config/transformer_config.py`

| Parameter | Before | After | Rationale |
|-----------|--------|-------|-----------|
| `V4_SCORE_LOG_PROB_WEIGHT` | 0.4 | 0.25 | Reduce pure probability dominance |
| `V4_SCORE_LENGTH_WEIGHT` | 0.2 | 0.35 | Make length penalty competitive |
| `V4_SCORE_TRANSITION_WEIGHT` | 0.3 | 0.30 | Unchanged |
| `V4_SCORE_DIVERSITY_WEIGHT` | 0.1 | 0.10 | Unchanged |

**max_length — File:** `src/gis_recommend/inference/infer_l3_candidates_v4.py` (constructor default)

| Parameter | Before | After | Rationale |
|-----------|--------|-------|-----------|
| `max_length` | 50 | 25 | Training data p90 ≈ 20; 25 gives headroom |

Note: `max_length` is a constructor default in `L3SequenceInferencerV4.__init__()`, not a config constant. Change the default value directly.

**Tuning guidance:** If sequences become too short after all changes, reduce `V4_SCORE_LENGTH_WEIGHT` back toward 0.25 or increase the `1.8` multiplier in per-beam cutoff to `2.0`.

### 2. Consecutive Deduplication in `_apply_constraints()`

**File:** `src/gis_recommend/inference/infer_l3_candidates_v4.py`

Add **after** existing repetition penalty, no-repeat-ngram, and transition constraint logic. The placement after transition constraints is intentional: transition constraints use additive masking (`logits[b] += mask`), while consecutive dedup uses absolute assignment (`logits[b, token] = -inf`), so the dedup properly overrides even if A→A is a valid transition in the matrix.

```python
# Block consecutive identical tokens (aligned with training data cleaning)
# This intentionally overrides transition constraints that might allow A→A
if gen and len(gen) > 0:
    last_token = gen[-1]
    if last_token < logits.size(1):
        logits[b, last_token] = float('-inf')
```

This matches training data preprocessing which removes consecutive duplicates (`MAX_CONSECUTIVE=2` in cleaner means 2+ consecutive are removed).

### 3. Beam Search Early Stopping

**File:** `src/gis_recommend/inference/infer_l3_candidates_v4.py`

Three mechanisms:

#### 3a. Per-beam length cutoff

In `diverse_beam_search()`, before expanding a beam:

```python
if len(tokens) - 1 > self.expected_length * 1.8:
    group_cands.append((tokens, lp, True))  # Force finish
    continue
```

In `temperature_sample()`, equivalent cutoff in the per-step loop:

```python
if step > self.expected_length * 1.8:
    break
```

#### 3b. END token progressive boost

In `_apply_constraints()` (applies to both beam search and temperature sampling):

```python
if step > self.expected_length:
    overshoot = step - self.expected_length
    bonus = 0.5 * overshoot
    logits[:, END_INDEX] += bonus
```

Each step past expected length adds +0.5 to END logit. At 5 steps over, END gets +2.5 bonus — substantial but not forced.

#### 3c. Completion bonus in ranking

In `_score_and_rank()`, after computing `final_score`:

```python
if not c.is_complete:
    c.final_score *= 0.8  # 20% penalty for incomplete sequences
```

### 4. Post-processing

**File:** `src/gis_recommend/inference/infer_l3_candidates_v4.py`

New method `_postprocess_sequence(tokens: List[int]) -> List[int]`.

**Call site:** Inside `infer()` and `infer_from_model_input()`, after candidates are collected from beam search + temperature sampling, but **before** `_score_and_rank()`. After post-processing, update both `c.tokens` and `c.length`:

```python
for c in candidates:
    c.tokens = self._postprocess_sequence(c.tokens)
    c.length = len(c.tokens)
```

**Logic:**
1. **Remove consecutive duplicates**: `[A, A, B]` → `[A, B]`
2. **Truncate tail loops**: If 3+ consecutive tokens at the end are all previously-seen codes, truncate to remove the repeated tail

### 5. Dynamic expected_length

**New script:** `scripts/compute_task_type_length_stats.py`
**Output:** `outputs/task_type_length_stats.json`

Pre-compute per-task-type sequence length statistics (mean, median, p90) from training data.

**API:** `set_expected_length(task_type: str)` — accepts the task type name string (e.g., "Topography"), uses internal `task_vocab_builder.task_type_to_id` to convert to int, then looks up stats. Fallback to global `expected_length = 12` if task type is unknown.

**Caller change:** `InteractiveQGISSystem._generate_l3_sequences()` calls `self.l3_inferencer.set_expected_length(task_type)` before calling `infer()` or `infer_from_model_input()`. This is a one-line addition.

## Data Flow

```
InteractiveQGISSystem._generate_l3_sequences()
  │
  ├─ set_expected_length(task_type)         ← NEW: dynamic length (optional, fallback=12)
  │
  ├─ diverse_beam_search()
  │    ├─ _apply_constraints()
  │    │    ├─ existing: repetition penalty, no-repeat-ngram, transition
  │    │    ├─ NEW: consecutive dedup (block same as last token, after transition)
  │    │    └─ NEW: END boost (after expected_length)
  │    ├─ NEW: per-beam cutoff (force finish if > expected × 1.8)
  │    └─ max_length=25 (was 50)
  │
  ├─ temperature_sample()
  │    ├─ same _apply_constraints() (consecutive dedup + END boost)
  │    └─ NEW: per-step cutoff (break if step > expected × 1.8)
  │
  ├─ _postprocess_sequence()               ← NEW: clean each candidate
  │    ├─ remove consecutive duplicates
  │    ├─ truncate tail loops
  │    └─ update c.tokens and c.length
  │
  └─ _score_and_rank()
       ├─ weights: log_prob=0.25, transition=0.30, length=0.35, diversity=0.10
       └─ NEW: incomplete penalty (×0.8)
```

## Verification

### Baseline capture

**Before making any changes**, run the 5 test cases and save the output (L3 sequences, lengths, QGIS chains, LLM scores) for comparison.

### Test cases

1. DEM slope analysis
2. Buffer + intersect
3. NDVI vegetation
4. Merge + dissolve
5. Reproject + clip

### Success criteria
- Average L3 sequence length ≤ 10 (was 4-14, many at 11+)
- No consecutive duplicate L3 codes
- Key L3 primitives still present (e.g., slope-related L3 for DEM task)
- LLM scores improve (> 4/10 average, was 2-4/10)
