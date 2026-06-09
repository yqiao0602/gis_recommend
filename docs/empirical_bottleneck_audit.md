# Empirical Bottleneck Audit

Date: 2026-05-09

Scope: active `outputs_v2` 94-L3 pipeline, with the quality-gated V4 candidate as the primary empirical object.

Primary artifacts inspected:

- `outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json`
- `outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json`
- `outputs_v2/pipeline/step8_quality_gate/audit/training_data_quality_audit.json`
- `outputs_v2/pipeline/step8_quality_gate/quality_gate_report.json`
- `outputs_v2/pipeline/step8_quality_gate/gee_operator_alias_audit.json`
- `outputs_v2/transition_allowed_next.json`
- `src/gis_recommend/training/train_v4_2.py`
- `src/gis_recommend/inference/infer_l3_candidates_v4.py`
- `src/gis_recommend/evaluation/runner.py`
- `src/gis_recommend/evaluation/semantic_metrics.py`
- `src/gis_recommend/evaluation/diagnostics.py`

Post-convergence infrastructure now exists for reproducible empirical artifacts:

- `src/gis_recommend/evaluation/empirical.py`
- `scripts/build_empirical_evaluation_artifact.py`
- `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json`
- `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.md`

The smoke artifact is baseline-only and model-optional. It is the current empirical artifact schema, but it is not a controlled v2 model prediction report.

This audit does not rerun training. It uses read-only dataset and pipeline measurements.

## Executive Conclusion

The current bottleneck is not proven model capacity. The strongest empirical bottleneck is supervision/data ambiguity: task descriptions and task types map to many valid or near-valid operator chains, while the dataset provides only one linearized sequence label and no graph/edge labels.

The quality-gated data is cleaner than original Step8, but it is narrower: 76,884 workflows, 47 active L3 tokens out of 94, and Top20 L3 tokens cover 94.77% of token mass. True explicit joins are extremely rare by operator keyword proxy: 301 workflows, 0.39%.

The local transition matrix is not a strong decoder bottleneck. It covers 99.96% of test transitions, but the train-time weighted average next-state branching factor is 40.91 over 48 states. It mostly says "almost anything seen can follow almost anything common."

The highest-value work is data/system work: quarantine review, operator canonicalization, sequence canonicalization, split/evaluation discipline, retrieval diagnostics, and controlled v2 evaluation. More V5-style structural complexity is unlikely to recover graph structure under the current supervision regime.

## Dataset Structure Audit

### Data Shape

| Item | Value |
| --- | ---: |
| Candidate workflows | 76,884 |
| Train / val / test | 61,495 / 7,694 / 7,695 |
| L3 tokens | 657,314 |
| Active L3 tokens | 47 / 94 |
| Task types | 47 |
| Unique L3 sequences | 42,325 |
| Unique sequence ratio | 55.05% |
| Cross-split duplicate L3-sequence hashes | 0 |

The active candidate is not a graph dataset. Each item contains `l3_sequence`, `l3_codes`, `operator_sequence`, confidence flags, metadata, and task metadata. There is no explicit DAG, edge target, fork/join annotation, or graph label.

### Sequence Length And Repetition

| Statistic | Value |
| --- | ---: |
| Average content length | 8.55 |
| Length min / p25 / median / p75 / p95 / max | 3 / 4 / 7 / 11 / 21 / 64 |
| Workflows with repeated L3 | 52,118 / 76,884 = 67.79% |
| Long repeat gap >= 5 | 17,907 = 23.29% |
| Long repeat gap >= 10 | 5,538 = 7.20% |
| Median unique-token ratio per sequence | 0.80 |
| Median max run length | 1 |
| p95 max run length | 2 |

Interpretation: repetition is common, but usually not consecutive loops. There is real long-range recurrence in some chains, but the data still presents it as a single linear sequence, not as recoverable structural memory.

### Fork/Join And Structural Proxies

Keyword proxies are imperfect, but they are the only available signal without edge labels.

| Proxy | Workflows | Share |
| --- | ---: | ---: |
| Join keyword workflows | 301 | 0.39% |
| Fusion keyword workflows | 30,420 | 39.57% |
| Join or fusion keyword workflows | 30,565 | 39.75% |
| Join and fusion keyword workflows | 156 | 0.20% |
| Reducer keyword workflows | 18,456 | 24.01% |
| Geometry set-operation keyword workflows | 44,075 | 57.33% |

Top join/fusion operators include:

| Operator | Count |
| --- | ---: |
| `ee.image.addbands` | 15,201 |
| `ee.imagecollection.merge` | 13,177 |
| `ee.imagecollection.mosaic` | 8,410 |
| `ee.image.cat` | 2,947 |
| `ee.image.unmask` | 2,873 |
| `ee.image.where` | 2,486 |
| `ee.join.saveall` | 287 |
| `ee.featurecollection.merge` | 133 |

Interpretation: there is substantial "combine/fuse" behavior, but explicit join-like branching is very sparse. This is not enough supervision to claim reliable latent fork/join recovery.

### Branching Factor

The train split transition graph has 48 states.

| Transition statistic | Value |
| --- | ---: |
| Unweighted average outdegree | 30.10 |
| Weighted average outdegree | 40.91 |
| Median outdegree | 36 |
| p75 outdegree | 40.25 |
| p95 outdegree | 43 |
| Max outdegree | 44 |

Interpretation: local transition legality is highly permissive. For common states, the next-token set is almost the whole active vocabulary plus special tokens. A transition mask cannot supply much discriminative structure.

### Entropy And Ambiguity

| Measure | Value |
| --- | ---: |
| Unigram L3 entropy | 4.242 bits |
| Unigram perplexity | 18.93 |
| Unigram entropy normalized by active L3 | 0.764 |
| Sequence entropy | 14.293 bits |
| Sequence perplexity | 20,073 |
| `H(next | previous)` | 3.431 bits |
| `H(next | previous two)` | 3.037 bits |
| `H(next | task_type)` | 4.142 bits |
| `H(next | task_type, previous)` | 3.247 bits |
| Weighted L3 co-occurrence entropy | 4.295 bits |
| Weighted L3 co-occurrence degree | 43.40 |

Task-to-sequence ambiguity is the decisive measurement.

| Task ambiguity statistic | Value |
| --- | ---: |
| Task types | 47 |
| Median unique sequences per task type | 118 |
| p75 unique sequences per task type | 626.5 |
| p95 unique sequences per task type | 5,910.3 |
| Max unique sequences for one task type | 14,887 |
| Median task sequence entropy | 6.790 bits |
| p95 task sequence entropy | 11.726 bits |
| Task types where top sequence share < 50% | 46 / 47 |
| Median top-sequence share per task type | 3.03% |

Most ambiguous task types:

| Task type | Workflows | Unique sequences | Entropy bits | Top sequence share |
| --- | ---: | ---: | ---: | ---: |
| Land use/land cover | 23,742 | 14,887 | 13.167 | 0.68% |
| Vegetation | 15,350 | 9,129 | 12.409 | 0.74% |
| Land surface/agriculture indicators | 11,563 | 6,762 | 11.788 | 1.59% |
| Terrestrial hydrosphere indicators | 5,365 | 3,923 | 11.581 | 0.93% |
| Surface thermal properties | 3,067 | 2,034 | 10.400 | 2.22% |

Exact text duplication is rare:

| Exact text statistic | Value |
| --- | ---: |
| Exact task text keys | 76,860 |
| Duplicate exact text keys | 9 |
| Ambiguous exact text keys | 7 |
| Workflows in ambiguous exact-text groups | 29 |
| Test exact-text coverage from train | 0.117% |

Interpretation: exact duplicate ambiguity is not the main issue. The issue is that semantically similar task descriptions and broad task types admit many sequence variants, while evaluation treats one sequence as ground truth.

### Operator Vocabulary Granularity

| Mapping statistic | Value |
| --- | ---: |
| Unique operators in candidate | 150 |
| Operators mapping to multiple L3 | 0 |
| L3 tokens with multiple operators | 32 / 47 |
| Median operators per active L3 | 2 |
| p75 operators per active L3 | 4 |
| Max operators per active L3 | 14 |

Examples of coarse L3 buckets:

| L3 token | Token events | Operators mapped into bucket |
| --- | ---: | ---: |
| 34 | 48,906 | 14 |
| 35 | 32,166 | 11 |
| 56 | 32,653 | 9 |
| 77 | 19,860 | 8 |
| 32 | 1,881 | 8 |

The v2 GEE alias audit reports 150/150 operators matched the v2 mapping case-insensitively, but only 140/150 matched crawled official names case-insensitively. The 10 unresolved official-name operators account for 20,593 tokens, 3.13% of candidate tokens.

Interpretation: operator-to-L3 mapping is deterministic in this candidate, so one-to-many label noise at the operator side is not the immediate problem. The larger issue is many operators collapsed into coarse L3 categories, which limits what sequence-level metrics can say about executable operator correctness.

### Distribution Imbalance

From the quality-gate audit:

| Distribution statistic | Value |
| --- | ---: |
| Active L3 | 47 / 94 |
| Inactive L3 | 47 / 94 |
| Top10 L3 token share | 74.94% |
| Top20 L3 token share | 94.77% |
| Rare L3 count `<100` | 5 |
| Rare L3 count `<1000` | 15 |

The quality gate quarantined 30,515 of 107,399 original Step8 workflows. High-impact quarantined operators include `ee.featurecollection.filter` 4,954, `ee.terrain.slope` 4,059, `ee.geometry.bounds` 2,589, `ee.algorithms.landsat` 2,544, `ee.image.arrayflatten` 2,075, `ee.clusterer.train` 1,960, and `ee.join.apply` 1,122.

Interpretation: the candidate removed major low-confidence noise, but also narrowed the training distribution. This improves label reliability while reducing structural/operator coverage.

## Upper-Bound Analysis

These are not trained neural model results. They are empirical baselines from the active quality-gate split.

### Next-Token Baselines

| Baseline | Test next-token accuracy |
| --- | ---: |
| Global unigram next token | 11.74% |
| Task-type majority next token | 11.95% |
| Previous-token Markov | 27.24% |
| Previous-two-token Markov | 33.51% |
| Task-type + previous-token Markov | 29.14% |

Interpretation: a shallow recency/transition prior captures a significant fraction of local token prediction. Task type alone adds little because task types are broad and internally high-entropy.

### Sequence Baselines

Grouped splitting removes exact sequence leakage, so exact-match scores are intentionally zero for memorization-style baselines.

| Baseline | Exact match | Avg LCS recall | Median LCS recall | Aligned token accuracy | Avg abs length error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Global majority sequence | 0.00% | 0.232 | 0.200 | 0.0775 | 5.49 |
| Task-type majority sequence | 0.00% | 0.312 | 0.286 | 0.0748 | 5.05 |
| Exact-text majority else task | 0.00% | 0.312 | 0.286 | 0.0748 | 5.05 |
| Greedy Markov-1 | 0.00% | 0.215 | 0.200 | 0.0133 | 71.51 |
| Greedy Markov-2 | 0.00% | 0.394 | 0.333 | 0.0989 | 4.23 |
| Task-prev greedy Markov | 0.00% | 0.270 | 0.250 | 0.0149 | 69.21 |
| Capped lexical nearest-neighbor retrieval | 0.00% | 0.607 | 0.636 | 0.2368 | 3.29 |

The capped lexical nearest-neighbor baseline uses task text token overlap with capped candidate scoring. It is not a tuned retrieval model. Even this weak retrieval reaches average LCS recall 0.607 while exact sequence match stays 0%.

Interpretation: retrieval gets much of the broad workflow shape without learning a neural generator, but exact sequence prediction remains brittle because the target is a single canonical chain among many plausible variants.

### Oracle Transition-Mask Evaluation

The train-derived local transition mask was evaluated against the test split.

| Oracle transition statistic | Value |
| --- | ---: |
| Test transition coverage by train mask | 99.9575% |
| Covered transitions | 72,982 / 73,013 |
| Conflict events | 31 |
| Unseen previous-state events | 0 |
| Train states | 48 |
| Weighted average outdegree | 40.91 |
| Uniform random within mask expected accuracy | 2.48% |

Interpretation: the transition matrix is almost perfectly covering test transitions, but it is too wide to be a useful oracle. It does not encode global executable workflow validity, and it cannot distinguish many wrong but locally seen next tokens.

## Error Taxonomy

An active baseline-only v2 smoke artifact now exists under `outputs_v2/evaluation_reports`. Existing JSON reports under `outputs/evaluation_reports` are legacy `outputs/` 350-L3 reports and should not be treated as current v2 performance evidence.

The new artifact persists per-sample baseline predictions, candidate pools, decode traces, token-probability proxies, END timing, repetition statistics, retrieval diagnostics, reranker features, split metadata, dataset structure audit, canonicalization audit, decode-policy summaries, and bottleneck attribution. It does not yet contain controlled model predictions because no matching v2 quality-gate checkpoint was supplied.

| Error category | Quantified evidence | Learnability under current data |
| --- | --- | --- |
| Semantically equivalent predictions | Not directly measurable without current v2 predictions and equivalence labels. Evaluation has `SoftSetSim`, `SetF1`, `LCS`, and exact metrics, but no true equivalence oracle. | Partly learnable, but current evaluation can penalize valid alternatives as wrong. |
| Operator aliasing | 10 unresolved official-name operators, 20,593 tokens = 3.13%. 32/47 active L3 buckets map multiple operators. | Mostly data/ontology work, not capacity. |
| Valid alternative workflows | 46/47 task types have top sequence share <50%; median top sequence share is 3.03%; median unique sequences per task type is 118. | Underidentified unless canonicalization or alternative labels are added. |
| Impossible due to missing context | Exact text train coverage for test is 0.117%; broad task types contain thousands of sequences. | Additional task/context fields or retrieval evidence likely matter more than model depth. |
| Retrieval miss | Weak capped lexical NN gets LCS 0.607 but exact 0%; average Jaccard 0.370. | Better retrieval is rational and measurable. |
| Decoding collapse | Smoke artifact reports baseline proxy collapse/length/repetition rates; controlled model collapse remains unavailable until v2 model predictions are ingested. | Decode policy can matter, but must be evaluated on controlled v2 model predictions. |
| Early END | Smoke artifact reports baseline END timing; controlled model early-END rate is still unavailable without generated model sequences. | Needs model prediction ingestion into the empirical artifact schema. |
| IO constraint conflict | Local train transition mask conflicts with only 31 / 73,013 test transitions = 0.0425%, but this is local legality only. | Local IO mask is not the bottleneck; global executable validity remains separate. |
| Rare operator undertraining | Operators with train count `<1000` account for 3.92% of test operator events; L3 tokens with train count `<1000` account for 1.06% of test token events. | Rare operators matter locally but are not the dominant aggregate bottleneck. |
| Ambiguous supervision | Sequence entropy 14.293 bits; task-conditioned sequence entropy median 6.790 bits; exact-match baselines stay 0%. | Dominant bottleneck. More architecture cannot identify unlabeled alternatives. |

Historical legacy reports show sequence exact match 0.0 and token accuracy around 6.37% for old baseline reports, improving only to about 7.44% with reranker reports. Those are useful warnings, but they are not current v2 evidence because they point to `outputs/transformer_checkpoints_v4_6/best_model.pth`.

## Ablation Priority Ranking

The ranking below is restricted to empirical/system experiments, not architecture redesign.

| Rank | Experiment | Expected gain | Cost | Confidence | Rationale |
| ---: | --- | --- | --- | --- | --- |
| 1 | Ingest controlled current-v2 quality-gate model predictions into the empirical artifact schema | High scientific value | Medium | High | Baseline artifact infrastructure now exists, but model-specific failure categories remain unmeasured. |
| 2 | Review and selectively reintegrate quality-gate quarantine hotlist | High | Medium | High | 30,515 workflows were removed; high-impact operators include terrain, join, clustering, feature collection, and array operations. Reintegration may recover structural coverage. |
| 3 | Sequence canonicalization audit | High | Medium | High | Exact-match evaluation is brittle; task types have thousands of sequence variants. Canonicalization can reduce label entropy without new model capacity. |
| 4 | Operator canonical alias table for GEE names | Medium | Low | High | 3.13% of candidate tokens are from unresolved official-name operators; alias cleanup is low-risk and directly measurable. |
| 5 | Better retrieval baseline and retrieval-assisted evaluation | Medium-high | Medium | High | Weak lexical NN already reaches LCS 0.607; retrieval quality likely explains more than latent graph capacity. |
| 6 | Vocabulary merge/split review for coarse L3 buckets | Medium | Medium | Medium-high | Some L3 buckets collapse 8-14 operators; this limits operator-level correctness and may hide errors in L3 metrics. |
| 7 | Curriculum or sampler rebalance on active v2 candidate | Medium | Low-medium | Medium | Top10 L3 share is 74.94%; imbalance is real. But rare token test share is modest after quality gate. |
| 8 | Hard-negative mining for similar task texts | Medium | Medium | Medium | Broad task families dominate; hard negatives can test whether text encoders distinguish similar workflows. |
| 9 | Decode policy sweep: beam width, END penalty, repetition handling, local mask on/off | Medium | Low | Medium | Decode collapse cannot be quantified without current predictions; sweep is cheap after v2 evaluation is available. |
| 10 | Synthetic DAG/branch supervision | High for structure, low for immediate sequence metrics | High | Medium | Necessary only if graph correctness becomes a primary target. It is data design, not architecture expansion. |

Low priority:

- Larger model variants before current v2 evaluation exists.
- More latent graph induction mechanisms without edge supervision.
- More governance/snapshot machinery.
- More local transition-mask tuning, because the mask is already 99.96% covering and very wide.

## True Bottleneck Determination

### Most Likely Primary Bottleneck: Supervision Insufficiency + Sequence Non-Uniqueness

Evidence:

- No graph/edge labels exist in the active dataset.
- The task-to-sequence map is high entropy: median 118 unique sequences per task type, p95 5,910.3, max 14,887.
- 46/47 task types have top sequence share below 50%; median top sequence share is only 3.03%.
- Exact sequence overlap across train/test is intentionally 0 after grouped split, so memorization cannot explain test success.
- Exact-text duplicate ambiguity is rare, so the problem is not duplicate rows; it is broad semantic underspecification.

### Secondary Bottleneck: Data Distribution And Ontology Granularity

Evidence:

- Only 47/94 L3 tokens are active after quality gate.
- Top10 tokens cover 74.94%; Top20 cover 94.77%.
- 32/47 active L3 categories map multiple GEE operators; the largest bucket contains 14 operators.
- 30,515 original workflows were quarantined, including structurally relevant operators such as joins and clustering.

### Important Bottleneck: Retrieval Quality

Evidence:

- Weak capped lexical nearest-neighbor retrieval reaches average LCS recall 0.607 and median 0.636 with no neural generator.
- Exact sequence match remains 0%, which means retrieval can recover rough shape but not canonical sequence identity.
- Exact text train coverage for test is only 0.117%, so retrieval must generalize semantically rather than memorize exact task text.

### Not Primary: Local Decoding Legality

Evidence:

- Train transition mask covers 99.9575% of test transitions.
- Weighted average outdegree is 40.91 over 48 states.
- Uniform random within the mask would only get 2.48% expected next-token accuracy.

The mask is permissive, not discriminative. It can prevent a few impossible local transitions, but it cannot enforce global workflow correctness.

### Not Proven: Model Capacity Limits

Evidence:

- No current v2 model prediction artifact exists; the current smoke artifact is baseline-only.
- Simple previous-two-token Markov reaches 33.51% next-token accuracy, showing local regularity exists.
- Retrieval baselines recover substantial LCS shape without model capacity.
- The hardest observed limits are label ambiguity and missing structural supervision, not failure of a measured current model to fit identifiable signal.

## Evaluation Methodology Findings

The evaluation stack measures useful but incomplete signals:

- `src/gis_recommend/evaluation/semantic_metrics.py` computes exact sequence match, positional token accuracy, LCS ratio, SetF1, L2 metrics, and embedding-based SoftSetSim.
- `src/gis_recommend/evaluation/diagnostics.py` can compute oracle metrics over generated candidate lists.
- `src/gis_recommend/evaluation/runner.py` can run reranker and repair diagnostics, but these depend on generated candidates and optional QGIS/KG validation paths.

Current gap:

- There is an active baseline-only `outputs_v2` empirical artifact, but no controlled v2 model prediction report.
- Existing `outputs/evaluation_reports/*.json` are legacy 350-L3 reports and must not be mixed into v2 conclusions.

Required next empirical artifact:

- A no-training evaluation run against the intended v2 quality-gate checkpoint once it exists, writing model predictions into the same per-sample schema used by `gis_recommend.empirical_evaluation.v1`.

## Final Engineering Verdict

### What Should Definitely Not Be Worked On Anymore

- New latent graph mechanisms without edge supervision.
- More local transition-matrix tuning as a primary strategy.
- Larger model experiments before current v2 error reports exist.
- Attempts to infer fork/join correctness from chain-only labels as if it were identifiable.
- Expanding governance/semantic framework objects instead of measuring data and evaluation behavior.

### Rational Experiments Still Remaining

- Controlled current-v2 quality-gate evaluation with per-sample predictions.
- Quarantine review and selective reintegration of high-impact operators.
- Sequence canonicalization and equivalent-workflow evaluation.
- Operator alias/canonical-name cleanup.
- Retrieval baseline improvement and retrieval-error attribution.
- Decode policy sweeps after real v2 prediction traces exist.
- Synthetic DAG or edge-labeled augmentation only if graph correctness is an explicit target.

### Low-Risk / High-Value Improvements

- Persist every evaluation run with dataset path, split path, checkpoint path, decode mode, candidate pool, and per-sample predictions.
- Add a dataset-level canonicalization report before training.
- Add a retrieval-only baseline to the normal evaluation report.
- Add operator alias coverage to the quality-gate audit.
- Track sequence ambiguity metrics by task type in every candidate build.

### Larger Models

Retraining larger or more complex models is unlikely to resolve the dominant bottleneck. It may improve local next-token accuracy and smooth over common sequence shapes, but it cannot identify unlabeled graph structure or choose among many valid sequence variants without additional supervision, canonicalization, retrieval context, or evaluation changes.

### Pivot Decision

The project should pivot from architecture-first work to data and system design. The empirical evidence says the current performance ceiling is governed by label entropy, sequence non-uniqueness, active-token imbalance, operator ontology granularity, and missing prediction/evaluation artifacts. Architecture complexity now has diminishing expected return until those are addressed.
