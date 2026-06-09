# Design: Evaluation System & Targeted Optimization

**Date:** 2026-03-15
**Status:** Draft (Rev 2 — post review)

## Problem Statement

Current evaluation relies solely on **Token Accuracy** (TF: 44.86%, AR: 16.45%), which is fundamentally mismatched with the task:

- **99.5% of task descriptions are unique** — the model must generalize, not memorize
- **75.6% of L3 sequences appear only once** — no dominant "correct answer"
- **Same GIS task can have multiple valid L3 implementations** — Token Accuracy penalizes valid alternatives

We need evaluation metrics that measure **semantic correctness** (does the generated L3 sequence solve the task?) rather than **exact match** (does it match the training label token-by-token?).

## Diagnosis Summary

| Finding | Value | Implication |
|---------|-------|-------------|
| Conditional entropy H(next\|prev) | 3.77 bits (13.6 choices) | High inherent ambiguity per step |
| Bigram ceiling (prev + task_type) | 26.9% | Model at 44.86% already surpasses this |
| Task_type entropy reduction | 0.26 bits only | Task type is weak signal |
| Unique descriptions | 99.5% | Model must generalize from text |
| Singleton L3 sequences | 75.6% | No memorizable patterns |
| Noise diagnostic | 7.5% (= END token only) | Model capacity is appropriate |
| L3 mapping coverage | 212/350 (60.6%) | 39.4% rely on semantic discovery |

## Design

### Part 1: New Evaluation Metrics

#### 1a. Sequence-Level Semantic Similarity (two required metrics)

**Content Similarity (SeqSim)** — order-invariant, measures whether the right L3 operations are present:

```
SeqSim(P, R) = cosine_similarity(
    mean_pool(L3_embeddings[P]),
    mean_pool(L3_embeddings[R])
)
```

**Ordered Similarity (OrderedSim)** — order-aware, measures structural correctness:

```
OrderedSim(P, R) = 1 / (1 + DTW(embed(P), embed(R)))
```

Uses DTW (dynamic time warping) over L3 embedding sequences. Normalization `1/(1+d)` guarantees output in (0, 1] and avoids negative values.

Both metrics are **required** — SeqSim alone would reward a model that picks the right operators in wrong order.

#### 1b. Structural Metrics

- **L2-Category Accuracy**: Map each L3 to its L2 category (78 classes) via `classification_hierarchy.csv`, then compute token accuracy at L2 level. Special tokens (START/END/PAD) are excluded. If an L3 code has no L2 mapping (edge case), treat it as a mismatch.
- **Subsequence Overlap (LCS ratio)**: Longest Common Subsequence / max(len(P), len(R)). Measures structural preservation.
- **Length Ratio**: len(P) / len(R). Does the model produce sequences of appropriate length?
- **Token Accuracy (Top-1)**: Retained as baseline for comparison with prior results.
- **Sequence Exact Match**: Retained from V3 evaluation for continuity.

#### 1c. Functional Equivalence via Chain Validation

For end-to-end evaluation of QGIS chains:
- **Coverage Score**: % of steps with a non-UNKNOWN operator.
- **Validity Score**: % of non-UNKNOWN steps whose operator name is confirmed to exist in Neo4j.
- **I/O Compatibility Score**: % of consecutive step pairs with compatible I/O types.
- **Chain Validity**: Combined score from ChainValidator.

Coverage and Validity are separate — a chain can have high coverage (few UNKNOWNs) but low validity (operator names not found in knowledge graph).

### Part 2: Automated Evaluation Pipeline

#### 2a. Test Set Construction

**Dataset**: `labeled_workflows_l3_v4_cleaned.json` (54,835 workflows, V4).

**Split strategy**: Create a new persistent V4 split. The V3 split (`dataset_splits_v3.json`) indexes into a different dataset and is incompatible. The new split file `outputs/evaluation_split_v4.json` stores train/val/test indices for reproducibility.

**Stratified sampling** (adaptive to task type size):
- Task types with >= 10 samples: 5 test samples
- Task types with 5-9 samples: 2 test samples
- Task types with < 5 samples: excluded from stratified test (noted as coverage gap)
- Expected test set size: ~300 samples

Samples within each task type are selected for length diversity (short/medium/long based on that type's p25/median/p75).

**Stage 1 check**: For each test sample, compare the LLM-extracted `task_type` against the ground-truth `task_type` from `task_metadata`. This is a free diagnostic (string comparison) that identifies whether LLM extraction is a bottleneck.

#### 2b. Evaluation Script

Script `scripts/evaluate_system.py`:

1. Generates test set (if not already cached) and saves split
2. Runs L3 inference (beam search, **deterministic mode only** — no temperature sampling, fixed seed=42) for each sample
3. Computes L3-level metrics (SeqSim, OrderedSim, L2 accuracy, LCS, length ratio, token accuracy, sequence EM)
4. Runs L3→QGIS mapping for top-1 L3 candidate (structural scoring only from Stage 4a — no LLM API calls)
5. Computes chain-level metrics (coverage, validity, I/O compatibility)
6. Outputs summary report + per-sample JSON details

**No LLM scoring (Stage 4b) in automated evaluation** — this avoids DashScope API costs and latency. LLM scoring can be added later for a subset of samples if needed.

**Dependencies**: Neo4j must be running at bolt://localhost:7687 for chain validation and QGIS operator lookup.

**Output format**:
```
=== L3 Generation Evaluation (N=300) ===
Token Accuracy (Top-1): 44.8%     <- baseline comparison
Sequence Exact Match:   2.1%      <- baseline comparison
SeqSim (content):       0.82      <- new: semantic content overlap
OrderedSim (structural):0.71      <- new: order-aware similarity
L2-Category Accuracy:   68.3%     <- coarse-grained accuracy
LCS Ratio:              0.71      <- subsequence overlap
Length Ratio (mean):     0.95      <- length calibration

=== Stage 1: LLM Extraction ===
Task Type Accuracy:     85.2%     <- LLM extraction quality

=== QGIS Chain Evaluation ===
Coverage Score:         0.82      <- % non-UNKNOWN steps
Validity Score:         0.76      <- % steps confirmed in Neo4j
I/O Compatibility:      0.68      <- % compatible pairs
Chain Validity:         0.54      <- combined score

=== Breakdown by Task Type ===
Task Type               | N  | SeqSim | OrdSim | L2Acc | Cov   | I/O
Land use/land cover     | 5  | 0.85   | 0.73   | 72%   | 0.80  | 0.70
Topography              | 5  | 0.78   | 0.68   | 65%   | 0.72  | 0.65
...
```

**Estimated runtime**: ~60-90 min on GPU (300 samples x beam search + Neo4j queries). No LLM API calls.

### Part 3: Targeted Optimization (based on evaluation results)

After evaluation reveals the real bottleneck, apply the appropriate optimization. Thresholds below are initial guidelines to be revised after the first evaluation run — the decision should be based on **relative comparison across stages**, not absolute numbers alone.

#### 3a. If L3 Generation is the bottleneck (SeqSim notably low)

- **Semantic loss function**: Add embedding-based loss alongside CE. Penalize semantically distant tokens more, semantically close tokens less.
- **Track SeqSim during training**: Monitor on validation set to catch improvements that Token Accuracy misses.

#### 3b. If L3→QGIS Matching is the bottleneck (Validity notably low)

- **Fill mapping gaps**: Use LLM to propose QGIS mappings for the 138 unmapped L3 primitives, validate with Neo4j.
- **Finer I/O types**: Extend vector→{point, line, polygon, table}, raster→{raster, dem, grid} for more precise compatibility.

#### 3c. If Text Understanding is the bottleneck (large variance across task types)

- **Unfreeze more BERT layers**: Currently 2 layers unfrozen; try 4-6 layers with lower LR.
- **Better text encoding**: Use domain-specific encoder (e.g., SciBERT) instead of generic BERT.

The specific optimization chosen depends on evaluation results — we won't know until we measure.

## File Structure

| File | Action |
|------|--------|
| `scripts/evaluate_system.py` | **Create** — Main evaluation pipeline |
| `src/gis_recommend/evaluation/semantic_metrics.py` | **Create** — SeqSim, OrderedSim, L2Acc, LCS metrics |
| `outputs/evaluation_split_v4.json` | **Generated** — Persistent train/val/test split for V4 data |
| `outputs/evaluation_test_set.json` | **Generated** — Stratified test samples |
| `outputs/evaluation_report.json` | **Generated** — Full evaluation results |

## Verification

```bash
# Generate test set + run evaluation
python scripts/evaluate_system.py

# Expected runtime: ~60-90 min (300 samples x beam search + Neo4j queries, no LLM calls)
```

## Success Criteria

1. Evaluation runs end-to-end without errors
2. Report shows all metrics broken down by task type
3. Clear identification of which pipeline stage is the primary bottleneck
4. Actionable optimization target identified for Part 3
