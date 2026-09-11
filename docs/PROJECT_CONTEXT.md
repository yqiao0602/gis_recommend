# Project Context Handoff

Last updated: 2026-07-31

This document is the durable project memory for `system_redesign`. New Codex sessions should read this file before continuing work. Update it after each completed phase with concise changes to `Completed`, `Open Work`, `Known Pitfalls`, and `Verification`.

## Current Objective

Phase 1 (2026-05-27 to 2026-06-04): Complete DPO preference training for L3 model quality, build QGIS landing layer with retrieval + evaluation, and conduct systematic ablation to identify the optimal L3→QGIS bridge strategy.

Key accomplishments this phase:
- DPO v2 model trained (beam top-1 usable 59.9% → 99.1% on 3000 GEE test)
- QGIS Chain Retriever + Evaluator built (200-probe: 100% combined bridge, 0.995 avg quality)
- QGIS chain dataset built from GitHub crawled scripts (D1: 54k scripts, 3,021 multi-step chains)
- 18 reviewed QGIS→L3 crosswalk mappings merged (L3 bridge coverage 12.3% → 24.8%)
- QGIS retrieval index fix: facts_summary text merged into chain records (recall 0.5% → 100%)
- GRPO headroom diagnosis completed: not viable for current L3 model (beam diversity too low)
- Open-user QGIS landing manual audit completed: 80 tasks, modality match 100%, strict grades A=2 / B=23 / C=55
- End-to-end pipeline validated: L3 planning + QGIS landing achieves 100% QGIS chain validity on 3000 test

Current focus: maintain DPO v2 L3 model as the GEE / remote-sensing / raster planning base, and use the newly built QGIS-derived canonical vector planning dataset as the main data source for filling the traditional vector planning gap. The main KPI is whether the system can plan correct vector steps/intents; QGIS landing metrics remain secondary evidence that those plans can map to executable QGIS chains.

Latest training-stage review on 2026-06-24: a read-only audit of the current V4.6 vector/QGIS SFT training stage found that the conservative Step8 quality-gate + QGIS-vector packages are structurally cleaner than the later `vector_v2` / API-trace line. Main risks to preserve are: from-scratch `--num-epochs` can remain teacher-forcing-only when shorter than the fixed 10-epoch TF phase; `--length-stats` defaults to the old quality-gate stats unless explicitly overridden; `train_v4_6_vector_unified.py` documentation/paths/checkpoint names are stale and can confuse experiment tracking; `vector_v2` places generated QGIS/LLM samples into val/test; `API_trace_to_L3_TRAINING_FINAL.jsonl` contains weak placeholder prompts, low-confidence LLM labels, and same-prompt multi-label conflicts; and `_upsample_splits.py` generates duplicate split indices that the current split validator rejects. Next action is to freeze a single authoritative training entry/package, pass package-specific vocab/stats paths explicitly, keep generated vector rows train-only, filter/weight low-confidence LLM/API-trace samples, and evaluate on held-out hand-written vector prompts rather than train-source absorption alone.

Follow-up fix on 2026-06-24: the high-priority training-entry issues above were patched and locally verified. `train_v4_6_quality_gate.py` now blocks from-scratch TF-only short runs by default and only allows them with explicit `--allow-tf-only-smoke`; `--length-stats` now defaults to `None` so implicit defaults can be detected and warned; `_push_and_train.py` and `_upsample_splits.py` now exit by default unless `--force-deprecated` is explicitly provided; `train_v4_6_vector_unified.py` now refuses to run without a package-specific unified length-stats file or explicit `--length-stats`. Verification: py_compile passed for all four scripts; TF-only dry-run is blocked; explicit TF-only smoke passes; the oversampled warmstart dry-run passes with 81,137 workflows, 65,748/7,694/7,695 split, 48 task types, and `tf_phase_epochs=0`.

Data-gate follow-up on 2026-06-24: API-trace weak-supervision cleaning was implemented and verified. New `scripts/clean_api_trace_l3_training_data.py` splits the raw `outputs_v2/API_trace_to_L3_TRAINING_FINAL.jsonl` into clean / weak / rejected / conflicts with `_training_quality` metadata. The LLM generation prompts and gates in `server_batch_api_to_l3.py`, `server_batch_source_to_l3.py`, and `llm_generate_l3_from_api_traces.py` now reject low-confidence guessing rather than forcing a chain. Latest local cleaning result: 6,031 raw rows -> 1,112 clean, 1,384 weak, 3,535 rejected, 1,367 conflict rows from 513 conflict prompts. Main rejection reasons are same-prompt multi-label conflicts (1,109), task/L3 modality mismatch (915), task/code mismatch (874), placeholder prompts (279), low confidence (174), and missing confidence (165). Remaining boundary: weak rows are not ready for equal-weight SFT, rejected rows must not be trained on, and clean API-trace rows still need a train-only Step8-compatible package before they are safe training input.

Training-mechanism follow-up on 2026-06-24: the V4.6 training path now directly targets vector-planning learning rather than only retrieval/landing. Completed: `TaskConditionedL3DatasetV4` returns `_training_quality.sample_weight`; teacher-forcing and AR scheduled-sampling losses use per-sample weighted CE; training prompt text is structured as task type/name/goal and defaults to `--max-text-length 256`; the sampler can combine task-type, vector-family, source-quality, confidence, and sample-weight signals; non-default training packages must use local or explicit length stats; positive `qgis_unmappable_penalty` is rejected because its old direction was unsafe; AR scheduled-sampling horizon is now configurable via `--ar-max-steps`; evaluation inferencers expose `legacy|structured` prompt styles while old DPO/SFT checkpoints stay legacy by default; and QG parent inference explicitly preserves legacy 128-token prompts. Not completed: no new full GPU training has been run, so do not claim vector-planning capability improved yet. Current blocker: server/GPU warmstart SFT plus held-out vector-family evaluation is still required. Next action: run the oversampled warmstart package with explicit vocab/stats, `--enable-family-sampler`, `--max-text-length 256`, and preferably `--ar-max-steps 32`; evaluate new structured-prompt checkpoints with `--sft-prompt-style structured` while keeping old DPO baselines legacy. Verification: relevant unittest suites, py_compile, and oversampled dry-run all pass locally; dry-run with default AR horizon reports 65,748 train rows, no prompt truncation over 256, no sequence truncation at 100, `tf_phase_epochs=0`, and family-sampler coverage for intersection/union/difference/geometry_repair/CRS families; dry-run with `--ar-max-steps 32` reduces train sequences beyond AR horizon from 3,219 to 545.

Eval-source guard follow-up on 2026-06-24: `train_v4_6_quality_gate.py` now fails fast when generated/LLM/API-trace sources appear in val/test splits (`qgis_vector_augment`, `llm_source_code_to_l3`, `llm_api_trace_to_l3`, `api_trace_to_l3`, `api_trace`). This directly guards the earlier `vector_v2` contamination risk. Legacy diagnostic runs can opt in with `--allow-generated-eval-sources`, and the dry-run summary records `eval_source_guard`. Latest oversampled warmstart dry-run reports `eval_source_guard.status=clean` and `generated_eval_rows=0`. This is a data/metric integrity fix; actual vector-planning improvement still requires server training and held-out family evaluation.

## Repository Areas

| Area | Purpose | Current Status |
| --- | --- | --- |
| `src/gis_recommend/` | Runtime code: config, inference, mapping, evaluation, KG helpers | Default paths now mostly point to `outputs_v2` |
| `outputs/` | Legacy 350-L3 outputs | Kept for compatibility and env override only |
| `outputs_v2/` | Repaired 94-L3 outputs and v2 pipeline artifacts | Current default data root |
| `../L1`, `../L2`, `../L3`, `../L3_classification` | Original taxonomy and platform mapping sources | Reference/legacy source material |
| `scripts/` | Pipeline, audit, KG build, mapping repair utilities | Mixed v2 and legacy scripts remain |

## Current Data Truth

| Artifact | Current Truth |
| --- | --- |
| L3 vocabulary | `outputs_v2/classification_hierarchy_v2.csv`, 94 L3 |
| ID mappings | `outputs_v2/id_mappings_v2.json`, 94 L3 |
| GEE mappings | 551 active mappings, 67 skip entries after repair |
| QGIS mappings | 447 QGIS entries in v2 metadata, 75 L3 covered with no threshold filtering |
| Canonical vector planning dataset | `outputs_v2/canonical_vector_planning_dataset.jsonl` exists with 2,319 QGIS-derived planning records. Local verification: 1,598 vector / 456 raster / 265 mixed; 1,046 records have full L3 mapping overall, including 733 pure-vector full-L3 records; all 2,319 rows have non-empty `task_text`. Top required vector step families are `crs_transform` 596, `buffer_analysis` 519, `spatial_overlay` 423, `attribute_filter` 412, `geometry_repair` 401, and `spatial_clip` 391. |
| Clean vector SFT seed | `outputs_v2/canonical_vector_clean_sft_seed.jsonl` exists with 685 structurally clean vector SFT rows. Latest local verification: all rows are vector, full-L3, no blank L3, no `other` steps, no invalid current-vocab L3, chain length 2-15, unique task text and QGIS chains. Overlay/centroid remap is fixed locally: no `L3_02_05_04`; intersection/difference/union/symdiff no longer collapse to Clip. |
| Step8 QGIS vector SFT package | `outputs_v2/pipeline/step8_qgis_vector_sft/` exists as a Step8-compatible package derived from the 685 clean vector rows. Files are `labeled_workflows_l3_v4_qgis_vector.json`, `dataset_splits_qgis_vector.json`, `task_type_vocabulary_qgis_vector.json`, and `manifest.json`. Latest local verification: 685 workflows, train/val/test 548/68/69, exact split coverage 0-684, token ids all in 0-93, no missing task metadata, source `qgis_vector_canonical`, single local task type `"Vector Analysis": 0`, and L3 sequence length min/avg/max 2/4.657/15. V4.2 and V4.6 quality-gate launchers can dry-run this package, and the V4 training-entry smoke can run a CPU forward pass. |
| Step8 quality-gate + QGIS vector merged package | `outputs_v2/pipeline/step8_quality_gate_qgis_vector/` exists as the conservative merged training package: 76,884 quality-gate GEE workflows plus 685 QGIS vector workflows. Latest local verification: 77,569 workflows, train/val/test 62,180/7,694/7,695, split covers exactly 0-77,568, 48 task types with `"Vector Analysis": 47`, QGIS rows are contiguous tail indices 76,884-77,568 and train-only, no normal token ids outside 0-93, original GEE rows keep `-3`/`-4` specials, cross-split content L3 sequence overlap is 0, and QGIS actual-sample CPU forward passes with task type id 47. Server smoke training on 2026-06-07 confirms both from-scratch and expanded-warmstart routes execute on CUDA. The warmstart route is currently stronger: expanded DPO v2 47->48 checkpoint plus 5 AR-SS epochs reached best validation composite 0.5922 at epoch 1 and test AR SetF1 0.523, versus from-scratch 5 TF-only epochs best validation composite 0.4916 and test AR SetF1 0.445. Server vector-impact smoke shows strong QGIS seed absorption with limited GEE contamination: GEE strict-vector rate DPO 0.4% -> SFT 2.0% (+1.6pp), QGIS seed DPO 1.7% -> SFT 53.7% (+52.0pp). |
| Step8 quality-gate + QGIS vector oversampled package | `outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/` exists as the higher-ratio vector SFT package. Local verification on 2026-06-07: 81,137 workflows, train/val/test 65,748/7,694/7,695 with exact split coverage 0-81,136, 48 task types with `"Vector Analysis": 47`, 4,253 QGIS vector rows at tail indices 76,884-81,136 and train-only, no normal token ids outside 0-93, and generated `task_type_length_stats.json` covering all 48 task types. Vector Analysis length stats are count 4,253, mean 5.6, median 5, p90 10. QGIS target-token row coverage from `l3_sequence`: intersection 1,038, union 359, difference 638, symdiff 50, clip 1,440, dissolve 1,541, field_calculate 781, centroid 1,322, geometry_cleanup/repair 1,580. Server warmstart training completed after rebuilding `outputs_v2/transition_allowed_next.json` from this package: 60 transition states, best validation composite 0.5895 at epoch 1, test AR SetF1 0.540 / LCS 0.397 / earlyEOS 11.3%. Held-out generalization improved vector-regime behavior but not fine-grained overlay semantics: vector measurable recall 3.8% -> 27.8%, vector token rate 1.5% -> 57.6%, raster controls stayed 0.0% vector-token contamination, but intersection/union/difference recall remained 0 on the current prompt set. |
| Step8 v2 audit | 1,091,910 L3 tokens matched current mapping, missing 0, mismatch 0, skip leak 0 |
| Step6/7/8 provenance | Code now writes and reports mapping provenance warnings. Existing checked-in/generated `outputs_v2` Step6-8 artifacts predate it and audit as `missing_provenance`, but provenance warnings are report-only under Phase 15C |
| Step8 source counts | `manual_override`: 920,726 tokens; `auto_remap`: 113,841; `audit_override`: 57,055; `manual_25_override`: 288 |
| Dataset splits | `outputs_v2/dataset_splits_v4.json` now covers exactly 107,399 Step8 workflows: train 85,919 / val 10,739 / test 10,741, out-of-range 0, missing 0 |
| Step8 + V4.6 mainline run contract | `gis-evaluate` now records an explicit `MainlineRunContract` in reports. Token profile is `v2_94_l3`: Step8 negative specials (`-1..-4`) and V4.6 internal specials (`94..97`) are stripped for mainline metrics, while legacy `350..353` are only stripped under the explicit `legacy_350_l3` profile. Data authority defaults to Step8 v2 workflow/split/task-vocab/id-mapping/checkpoint paths and `outputs_v2/qgis_operator_io_types.json`; if that I/O metadata file is absent, diagnostics degrade to missing metadata rather than silently reading legacy `outputs/`. `QGISCandidateGenerator`, `CandidateVerifier`, posthoc QGIS evaluation, executable diagnostics, and report decision traces now all consume/report this same authority where applicable. |
| Training data quality audit | `outputs_v2/pipeline/audit/training_data_quality_audit.*` exists; schema is clean, but model-facing warnings remain: 60/94 active L3, Top10 L3 share 70.20%, 67 task types have <10 samples, val/test contain task types absent from train, 5,934 cross-split duplicate L3 sequences, and 50,036 low-confidence tokens |
| API-trace L3 training data gate | `scripts/clean_api_trace_l3_training_data.py` now writes conservative splits under `outputs_v2/diagnostics/api_trace_l3_cleaning/`: `API_trace_to_L3_TRAINING_CLEAN.jsonl` (1,112), `API_trace_to_L3_TRAINING_WEAK.jsonl` (1,384), `API_trace_to_L3_TRAINING_REJECTED.jsonl` (3,535), `API_trace_to_L3_TRAINING_CONFLICTS.jsonl` (1,367), plus JSON/Markdown reports. The clean split excludes placeholder `QGIS script: script_xxx` prompts, explicit self-rejection phrases, same-prompt multi-label conflicts, task/code mismatch reasoning, task/L3 modality mismatch, missing/invalid/low confidence, and explicit "description-only" inference patterns. Treat this as a data gate, not as final training package construction. |
| GEE official-name alignment | Current Step8 uses 306 unique lowercase GEE operators. All 306 match `id_mappings_v2.mapping_metadata.gee_to_l3` case-insensitively, so Step8 GEE->L3 labeling is not losing tokens from case mismatch. Only 45 are exact metadata-key matches, 295 match crawled official operator names case-insensitively, and 11 mapped/high-frequency operators are not direct `name` hits in `../operators-json/gee_operators.json`; downstream official API grounding still needs a canonical alias audit/table. |
| Quality-gated V4 candidate | `outputs_v2/pipeline/step8_quality_gate/` exists and does not overwrite Step8. Candidate has 76,884 workflows, 657,314 L3 tokens, grouped split 61,495 / 7,694 / 7,695 with full coverage and 0 cross-split duplicate L3-sequence hashes. It quarantines 30,515 workflows carrying low-confidence `auto_remap` tokens and merges 116 sparse-task workflows; remaining audit warnings are inactive L3, skewed L3 distribution, and 222 low-confidence non-auto-remap/manual-25 tokens. Quality-gate length stats now exist at `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`: content-token global median 7, mean 8.5, p90 16, 47 task types. |
| Quality-gate transition matrix | `outputs_v2/transition_allowed_next.json` is the global transition matrix read by current V4.6 train/eval paths. Baseline quality-gate training used the quality-gated train split only: 61,495 workflows, 48 states, 587,479 transitions, invalid transitions 0. The QGIS-vector oversampled server run rebuilt the same global file from `step8_quality_gate_qgis_vector_oversampled`: 65,748 workflows, 60 states, 607,006 transitions, invalid transitions 0. Do not copy/use `outputs/transition_allowed_next.json`; that file contains old 350-L3 token ids such as 352 and is incompatible with the v2 98-token training vocabulary. Because this file is global, rebuilding it affects both SFT and DPO evaluation in later runs; within-run SFT-vs-DPO comparisons are still aligned, but cross-run comparisons against older 48-state reports are not perfectly controlled. |
| Quality-gate training entry points | Historical `scripts/train_v4_quality_gate.py` trains the V4.2 Transformer on the quality-gated candidate into `outputs_v2/transformer_checkpoints_v4_2_quality_gate`. `scripts/train_v4_6_quality_gate.py` writes to `outputs_v2/transformer_checkpoints_v4_6_quality_gate`, and the matching Set Predictor path is `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6`. These are quality-gate candidate/research paths, not the current Step8 + V4.6 `gis-evaluate` mainline. They require the v2 transition matrix for strict non-dry-run training. |
| Empirical evaluation artifact | `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json/.md` now exists with schema `gis_recommend.empirical_evaluation.v1`. It is baseline-only/model-optional, covers 20 smoke samples, and persists per-sample baseline predictions, beam candidates, decode traces, token-probability proxies, END timing, repetition stats, candidate/retrieval/reranker diagnostics, split/checkpoint metadata, dataset structure audit, canonicalization audit, decode-policy summaries, and bottleneck attribution. Best smoke baseline by LCS is `lexical_retrieval` at 0.453342. It is not a controlled v2 model prediction report. |
| V5 hybrid planner prototype | `outputs_v2/v5_final_reports/v5_hybrid_planner_prototype/` contains the retrieval-centered checkpoint-only hybrid planner report. It preserves retrieved workflow structure, uses V5_final only for complete-candidate plausibility/reranking, and does not retrain or autoregressively replace retrieval. On the current 50-sample artifact: hybrid LCS 0.46504845 / SetF1 0.59205726 / token accuracy 0.33411111 / IO validity 1.0; retrieval-only LCS 0.44371511 / SetF1 0.56734786 / token accuracy 0.31911111. The selected hybrid candidates are all identity candidates from the retrieval pool, so the measured gain is retrieval-pool selection, not local edit improvement. |
| V5 multistage hybrid planner | `outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/` contains the next retrieval-centered evaluation artifact. Retrieval sources are lexical, embedding, intent, workflow-structure, and graph-aware L2/L3-code features, fused with lexical-primary weights. Safe rerank prevents low-retrieval-confidence candidates from replacing retrieval anchors. On the 50-sample artifact: hybrid/retrieval-only LCS 0.45586827, SetF1 0.57529907, token accuracy 0.33928243, IO validity 1.0. Rerank contribution and repair contribution are both 0.0 under the safe policy; all selected candidates are identity workflows. |
| Retrieval planning stages | `scripts/evaluate_retrieval_planning_stages.py` evaluates Set Predictor-compatible retrieval filtering, execution-aware rerank, and local repair without training or architecture changes. It writes `outputs_v2/v5_final_reports/retrieval_filtering/`, `execution_aware_rerank/`, `local_repair/`, and combined trace/summary artifacts. Current 50-sample artifact uses the local train-frequency set-prior fallback because the trained Set Predictor checkpoint is absent: retrieval-only LCS 0.46677086 / SetF1 0.60017391 / token acc 0.33272688; soft filtering LCS 0.46415182 / SetF1 0.60287787 / token acc 0.32606021; execution-aware rerank LCS 0.45731716 / SetF1 0.61339037 / token acc 0.26513428; local repair selected identity for all samples, so repair contribution is 0.0. These are retrieval/filter/rerank/repair measurements, not generation gains. |
| Historical planning retrieval audit | Current runtime evidence shows history-based planning retrieval is partially implemented only as research/evaluation paths. The "history" source is train-split workflow JSON (`outputs_v2/pipeline/step8_quality_gate/*` or the Step8 split), not a durable user-history/case/feedback database. `LexicalRetrieval` and `empirical.py` retrieval build in-memory indexes/candidate pools from train workflows; V4-QG planner and V5 research scripts can use those candidates for rerank/filter/repair, but the Step8 + V4.6 `gis-evaluate` mainline still selects from V4.6 beam outputs and does not call the historical retrieval path. No persisted FAISS/sqlite/vector-store/retrieval-index or automatic feedback updater was found in the current code/output tree. |
| Repair oracle phase | `outputs_v2/v5_final_reports/repair_oracle_phase/` contains the evaluation-only local repair oracle report. Candidate pools use explicit local edits only: substitution, bridge insertion, deletion, and local swap. On 50 samples with the local set-prior fallback: mean oracle repair gain is LCS +0.12149891 / SetF1 +0.1027359 / token accuracy +0.13011901; repair win rate is 0.88, repair corruption rate is 0.02, and repair selection failure rate is 0.88. Retrieval-pool oracle gain is larger at LCS +0.24863413. Failure taxonomy is `rerank_failure:44`, `repair_quality_failure:3`, `retrieval_saturation:3`, meaning useful local repairs often exist but current scoring/reranking does not recognize them. |
| Repair selection diagnostics | `outputs_v2/v5_final_reports/repair_selection_diagnostics/` diagnoses why useful repairs are not selected, using only existing repair oracle traces. On the same 50 samples: identity selection frequency is 1.0, modified selection frequency is 0.0, modified near-miss rate at margin 0.05 is 0.02, and oracle-vs-selected mean score delta is -0.19874815 despite oracle LCS gain +0.12149891. All 4,939 modified candidates have `edit_penalty` as the strongest suppressor. Failure breakdown is `edit_oversuppression:44`, `retrieval_saturation:6`. Conservative/balanced threshold sweeps adopt 0 repairs; aggressive margin -0.10 adopts 18% with only mean LCS +0.00266667. Random modified selection is negative (mean LCS -0.05363936), so useful repair selection is a calibration/scoring problem, not permission for random repair acceptance. |
| Repair scorer ablations | `outputs_v2/v5_final_reports/repair_scorer_ablations/` re-scores the existing repair oracle candidate pools without model/checkpoint access. Removing edit penalty entirely adopts 100% repairs but is harmful: mean LCS -0.0132707, corruption 0.32. The tested piecewise operation penalties are also harmful: mean LCS -0.01555742, corruption 0.26. Execution/set-heavy weighting is harmful: mean LCS -0.0178352, corruption 0.28. A conservative uniform edit penalty reduction from 0.20 to 0.12 is the best low-corruption candidate on this 50-sample trace: adoption 0.08, corruption 0.02, mean LCS +0.00333333, SetF1 +0.00488889, token accuracy +0.00952381. This is a small evaluation-only recommendation, not a production scoring change yet. |
| Repair calibration sweep | `outputs_v2/v5_final_reports/repair_calibration_sweep/` tests uniform edit penalties 0.0/0.08/0.10/0.12/0.14/0.16/0.20 on a larger 200-sample repair oracle trace. The 200-sample trace still has oracle repair gain (LCS +0.12405501, SetF1 +0.10355055, token accuracy +0.17590497), but selected repair policies are not stable. `uniform_edit_0_12` adopts 13% repairs with corruption 5%, conditional breakage 38.46%, mean LCS -0.00111538, and bootstrap LCS CI [-0.00838557, +0.00748109]. No tested penalty qualifies as a low-corruption positive stable policy; 0.0 collapses, 0.08 over-adopts, and all regions are marked unstable. This supersedes the 50-sample `0.12` hint as insufficient for production scoring. |
| Repair opportunity analysis | `outputs_v2/v5_final_reports/repair_opportunity_analysis/` contains the evaluation-only conditional repair attribution study over the 200-sample held-out repair trace. Oracle repair gain remains present (mean LCS +0.12405501 / SetF1 +0.10355055 / token accuracy +0.17590497), but most candidate opportunity signals are weak or unstable: 17 signals have absolute correlation below 0.10 and 21 bootstrap intervals cross zero. Directional follow-up signals include retrieved-set reference deficit, length-ratio error, lower identity repetition/redundancy, and best-repair LCS retention; IO-transition signals are uninformative in this trace because identity and modified invalid-transition rates are both 0. Broad indicators trigger nearly everything and must not become runtime gates. |
| Repair confidence regimes | `outputs_v2/v5_final_reports/repair_confidence_regimes/` contains the evaluation-only high-confidence repair regime search over the 200-sample held-out repair trace. It evaluated 19,919 candidates, including 19,719 modified candidates, with subtype/context breakdowns, precision-first regime search, bootstrap validation, and random controls. No score-selected regime satisfies the low-corruption high-confidence contract (`score_selected_high_confidence_regime_count=0`), while 12 oracle-only subspaces pass; this means repair opportunity still exists, but no stable deployable runtime repair policy has been demonstrated. Random modified selection is harmful (median LCS delta -0.0542, median corruption 0.455), and random narrow gating is also negative (median LCS delta -0.0054). |
| Unified workflow benchmark | `outputs_v2/v5_final_reports/unified_benchmark/unified_workflow_benchmark.json/.md` now records the current multi-task benchmark families in one artifact without metric mixing: V4 quality-gate teacher-forced token prediction, V4 quality-gate AR rollout, V5_final rollout, retrieval-centered planning, hybrid planning, and Set Predictor set prediction. V4 and Set Predictor values are currently sourced from the user's server-reported results because the raw history/checkpoint directories are not synced locally. |
| System consolidation protocol | `docs/v5_system_consolidation_protocol.md` is the project-level synthesis for final system identity, architecture semantics, demonstrated vs unsupported capabilities, governance boundaries, production interpretation, and research roadmap. It formalizes the system as retrieval-centered, execution-aware, rerank-driven, and constrained-planning-oriented; it explicitly rejects autonomous generation and deployable repair claims under current evidence. |
| L2 semantic recovery protocol | `docs/v5_l2_semantic_recovery_protocol.md` restores the long-term L1->L2->L3 architecture boundary after runtime consolidation. It defines current L3/operator-token retrieval as an empirical simplification, preserves L2 as the platform-independent semantic intent layer, and forbids treating retrieval success as evidence that semantic abstraction is unnecessary or already validated. |
| Semantic retrieval stress evaluation | `outputs_v2/v5_final_reports/semantic_retrieval_stress/` contains the evaluation-only lexical/operator-level retrieval perturbation test. On 50 held-out samples and 371 deterministic perturbations, wording reorder is stable, platform wording and light synonym/operator alias shifts are mostly stable, while abstraction and semantic paraphrase perturbations are brittle: aggregate top1 change rate 0.5202, original top1 retention 0.5391, mean topK overlap 0.4542, mean LCS delta -0.0814, SetF1 delta -0.0833, token accuracy delta -0.0793, retrieval saturation failure 0.4070. This diagnoses lexical sensitivity only; it does not validate L2, semantic retrieval, or semantic planning. |
| Semantic indexing simulation | `outputs_v2/v5_final_reports/semantic_indexing_simulation/` contains the evaluation-only manual semantic-grouping simulation. It uses 10 predefined alias/intent buckets and no models, checkpoints, embeddings, LLM rewriting, or runtime replacement. On the same 50 samples / 371 perturbations, this coarse grouping is net negative: mean top1 retention delta -0.0620, topK overlap delta -0.1067, LCS preservation delta -0.0151, SetF1 delta -0.0227, token accuracy delta -0.0025, retrieval saturation reduction -0.0728. Risk is substantial: semantic drift risk 0.3854 and false equivalence 0.3585, with execution-invalid grouping 0.0. This estimates risk/upside only; it does not implement semantic retrieval or validate L2. |
| Controlled equivalence stress evaluation | `outputs_v2/v5_final_reports/controlled_equivalence_stress/` contains the evaluation-only equivalence safety stress report. On 50 samples / 223 variants, exact alias equivalence is stable (`n=12`, corruption 0, false equivalence 0), exact unambiguous GEE<->QGIS mappings are platform-transfer-safe (`n=12`), but ambiguous/composite cross-platform mappings are unsafe as equivalence claims (`n=49`, false equivalence 1.0). Same-L2 operator-family substitution is execution-breaking/unsafe (`n=50`, execution-invalid 0.46, corruption 0.68). Workflow reorder and bridge expansion are unsafe under current evidence (`n=50` each; reorder corruption 0.58, bridge corruption 0.96). This identifies narrow safe classes only; it does not implement semantic retrieval or prove global execution-preserving equivalence. |
| Bounded ontology inventory | `outputs_v2/v5_final_reports/bounded_ontology_inventory/` contains the first offline bounded semantic ontology inventory. It classifies 3,800 operator-pair rows from current GEE/QGIS mappings plus unsupported GDAL/ArcGIS pairs: exact 13, execution-sensitive 98, partial 691, ambiguous 2,989, composite 4, unsupported 5. Exact rows are deliberately narrow GEE<->QGIS candidates, mainly Buffer and Mosaic. GDAL/ArcGIS are explicitly `unsupported` because no current mapping assets exist. This is inventory/governance only; it does not implement semantic retrieval, L2 runtime authority, ontology inference, or platform translation. |
| Canonicalized workflow evaluation | `outputs_v2/v5_final_reports/canonicalized_evaluation/` contains the strict evaluation-only raw-vs-canonicalized metric report. It reuses only train-split empirical commutative pairs and `empirical.py::_canonicalize_sequence()`. Across 369 persisted prediction records from empirical smoke, Stage1 V5 generation, and hybrid planner artifacts: raw EM 0.0 -> canonicalized EM 0.00542005, LCS +0.0173991, token accuracy +0.06013034, SetF1 +0.01039799. Bootstrap intervals are mostly positive for LCS/token accuracy/SetF1, but exact recovery is only 2 records and TopK canonical recovery is 6 records. This is evidence that raw sequence metrics understate quality in some reordered cases; it is not a runtime, retrieval, training, semantic grouping, or architecture change. |
| Workflow usability evaluation (v1, prediction-record) | `outputs_v2/v5_final_reports/workflow_usability_evaluation/` (v1) read 369 persisted prediction records: Top1 usable 0.035, Top3 0.062, Top5 0.068; `v5_final` generation had 0.0 usable rate. This legacy artifact is superseded by v2 below. |
| Workflow usability evaluation (v2, self-contained) | `scripts/evaluate_workflow_usability.py` (rewritten 2026-05-13) is a self-contained evaluation-only pipeline requiring NO model, checkpoint, training, semantic retrieval, LLM judging, or execution simulation. It evaluates the lexical retrieval baseline directly on 200 quality-gated test samples with 7 strict rule-based usability metrics using L1/L2 classification hierarchy categories and QGIS mappings. Key results: **Top-1 usable rate 0.5600** (56% of test tasks have a usable Top-1 retrieval candidate), **Top-3 any usable 1.0000**, **Top-5 any usable 1.0000** (every task finds >=1 usable workflow in Top-5). Mean usability score 0.7663 [95% CI: 0.7552, 0.7780] exceeds reference usability 0.7207. Mean QGIS mapping rate 0.6365, mean logic consistency 0.9368, mean step coverage 0.6197. Top failure: FP04 consecutive_duplicate (84), FP02 export_before_processing (83), low_qgis_mapping (60). 533 commutative pairs discovered. 76/94 L3 codes have QGIS mappings. This is a PRACTICAL USABILITY estimate, not sequence similarity — it shows retrieval already produces usable chains even where LCS/SetF1 are low. |
| V4-QG planner Phase 1 candidate rerank | `scripts/run_v4_qg_planner.py` is the current practical V4-QG planner entrypoint for candidate-pool plus constraint-aware rerank. It defaults to the V4.6 quality-gate checkpoint path and matching V4.6 Set Predictor checkpoint path. It is evaluation/rerank only: no training, no checkpoint mutation, no architecture change, no semantic grouping, no LLM judging. With local checkpoints absent it uses quality-gate lexical retrieval candidates plus a train-split task-type operator-frequency set prior. On 1,000 quality-gated held-out samples, retrieval Top1 usable is 0.6330 while reranked selected Top1 usable is 1.0000 because every sample has at least one rule-usable candidate in Top5 and rerank now prioritizes rule-usable candidates. Mean selected usability score is 0.8449, mean QGIS mapping rate 0.8082, logic consistency 0.9974, forbidden-pattern scan pass. This is practical rule-based usability, not proof of semantic correctness, parameter validity, or real QGIS execution. |
| Multi-reference workflow evaluation | `outputs_v2/v5_final_reports/multi_reference_evaluation/` contains the strict evaluation-only single-reference vs multi-reference report. Multiple references are limited to exact normalized task text/name matches in existing labeled workflows plus the original reference; no semantic embeddings, LLM judging, runtime changes, retrieval redesign, or execution simulation are used. On the same 369 persisted prediction records, the conservative reference pool has mean reference count 1.0 and multi-reference record rate 0.0, so best-of-multi-reference raw deltas are all 0.0. Canonicalized multi-reference reproduces the earlier canonicalization uplift: EM +0.00542005, LCS +0.0173991, token accuracy +0.06013034, SetF1 +0.01039799, with 2 canonical exact recoveries and 139 LCS-improved records. Current artifacts therefore show metric underestimation from order/canonicalization, but not from explicit multi-reference labels because such labels are effectively absent for the evaluated samples. |
| Multi-reference validation experiment | `scripts/evaluate_multiref_validation.py` is the evaluation-only MRV runner for testing whether current quality-gate GEE workflow data can support reliable multi-reference supervision. It generates adjacent-swap variants from train-split commutative pairs, applies workflow-semantic gates (sensitive-step, semantic usability, non-degradation, length preservation), and records QGIS landing only as an auxiliary downstream transferability signal. The current 50-workflow/100-variant smoke artifact under `outputs_v2/v4_qg_multiref_validation/` produced 19 `verified_equivalent_candidate`, 81 `invalid_variant`, 19 auto-verified registry candidates, a 15-row stratified human-review sample, and a 19-row `equivalence_review_packet.csv` with readable L3 names. Manual review on 2026-05-15 initially labeled 14 `equivalent`, 4 `uncertain`, and 1 `not_equivalent`; source inspection of the 4 uncertain rows then downgraded `wf46_pos2_swap53_28` to `not_equivalent` due to an ImageCollection->Image object-chain break. Current labels are 14 `equivalent`, 3 `uncertain`, and 2 `not_equivalent`. `verified_multi_reference_registry.json` still contains 7 reviewed task groups sourced only from the 14 accepted equivalent variants. QGIS landing remains poor (`qgis_mapping_valid_rate=0.0`), but that no longer blocks GEE workflow-level MRV labels. |
| MRV expansion and equivalence taxonomy | `outputs_v2/v4_qg_multiref_validation_expansion_500/` contains the 500-variant MRV expansion. It generated 500 adjacent-swap variants from 200 workflows and 53 discovered commutative pairs: 46 auto `verified_equivalent_candidate`, 454 `invalid_variant`, semantic auto pass rate 0.092, semantic usable rate 0.116, and guard pass rate 0.9. `configs/equivalence_taxonomy.yaml` now formalizes family/risk/rejection categories, and `scripts/analyze_mrv_expansion.py` writes family/risk/rejection summaries. Family counts: `filter_filter=203` (auto pass 0.1281), `select_filter=63` (0.1746), `select_clip=17` (0.0588), `reducer_or_aggregation=96` (0.0208), `mask_threshold_or_logic=26` (0.0769), `high_risk_sensitive=6` (0.0), `other=89` (0.0449). Risk counts: low 203, medium 80, high 128, unknown 89. QGIS `landing_only_failure=500` is auxiliary and does not invalidate GEE workflow equivalence candidates. These 46 auto candidates are not training labels until manual review promotes them. |
| MRV expansion AI-assisted review draft | `outputs_v2/v4_qg_multiref_validation_expansion_500/equivalence_review_packet_ai_review.csv` and `equivalence_review_ai_summary.*` contain the first pass review over all 46 auto candidates. Draft labels are now 36 `equivalent`, 8 `uncertain`, and 2 `not_equivalent`, following the user-reviewed family boundary: `metadata_mosaic` is uncertain, `select_zonal`/`select_temporal`/`select_logical` are uncertain, and `mask_logical` is not equivalent. Equivalent drafts are dominated by filter/filter, select/filter/date-select, clip/select, clip/arithmetic, and one source-inspected independent select/arithmetic branch. Explicit rejects are the known `wf46_pos2_swap53_28` ImageCollection/Image object-chain conflict and `wf63_pos4_swap29_35` mask/logical failure. `verified_multi_reference_registry_ai_draft.json` groups the 36 draft-equivalent variants into 19 task groups, but it is **not training-eligible** until the user confirms labels and promotes them into the manual registry. The 46 expansion candidates include the first 19 candidates, so global totals must deduplicate by `variant_id` rather than adding 19+46. |
| Verified MRV registry v2 / equivalence KB | `scripts/build_mrv_registry_v2.py` consolidates the initial manual review plus the user-confirmed 46-candidate expansion review without overwriting the original manual registry. Outputs under `outputs_v2/v4_qg_multiref_validation/`: `verified_multi_reference_registry_v2.json`, `verified_equivalence_kb_v2.json/.csv`, and `verified_multi_reference_registry_v2_summary.md`. Deduplicated counts: 65 input review rows -> 55 unique reviewed variants; 42 `equivalent` variants are training-eligible for controlled ablation only; 23 task groups; 13 excluded variants (`uncertain=10`, `not_equivalent=3`) remain outside training labels. Family counts: `filter_filter=30`, `select_filter=8`, `select_clip=3`, `other=1`. Risk counts are normalized and clean: `low=31`, `medium=10`, `unknown=1`; `review_flags` no longer pollute `risk_level`. |
| Controlled MR training ablation artifacts | `scripts/build_mrv_training_ablation.py` builds isolated quality-gate derivatives from MRV registry v2 / equivalence KB v2 only. Current outputs under `outputs_v2/v4_qg_mr_ablation/` are `mr_5`, `mr_10`, and `mr_all_42` plus `mrv_training_ablation_manifest.json`. Base quality-gate data has 76,884 workflows with train/val/test 61,495 / 7,694 / 7,695. `mr_5` outputs 76,889 workflows with train 61,500; `mr_10` outputs 76,894 with train 61,505; `mr_all_42` outputs 76,926 with train 61,537. Val/test are unchanged in all versions, injected rows carry `metadata.mrv_ablation` and `quality_gate.mrv_ablation`, and the manifest records `no_training_started=true`. These are derived ablation inputs only, not a mainline data replacement or training result. |
| MR ablation comparison scaffold | `scripts/compare_mrv_training_ablation.py` is a read-only report comparator for future baseline vs `mr_*` training/evaluation outputs. It normalizes known report keys from planner/usability/canonicalized-style JSON, computes metric deltas and relative deltas, uses paired per-sample bootstrap CIs when reports contain compatible `per_sample` rows, writes JSON/Markdown summaries, and records governance flags for no training, no inference, no checkpoint loading, and no source-data mutation. It does not create model metrics by itself; it only compares already-produced reports. |
| MR all-42 V4.6 training result | `结果/transformer训练结果/train_v4_6_quality_gate-mr-0517.md` records a full from-scratch V4.6 run on `outputs_v2/v4_qg_mr_ablation/mr_all_42/` into `outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42`. Final test: Loss 2.9974 / PPL 20.0 / Top1 31.3% / Top5 60.0% / TF-SeqEM 0.6% / AR-SeqEM 0.0% / AR-TokenAcc 18.8%. This is not a clean MR-vs-baseline conclusion yet: after epoch 11, AR scheduled sampling reports `Train: Loss=inf` repeatedly, while validation remains finite; latest-snapshot evaluation loads epoch 50, although validation quality peaked earlier around Top1 36.9% / Top5 65.0%. The local trainer now fixes the identified AR-SS early-END masking bug by separating CE logits from decode-only sampling logits, but the run still needs to be repeated before any MR effect claim. |

Important distinction: Step1-8 training sample construction is GEE -> L3. The `qgis_to_l3` section in `id_mappings_v2.json` does not affect that GEE training chain directly. QGIS mappings affect later L3 -> QGIS grounding and evaluation.

## Key Decisions

| Decision | Rationale |
| --- | --- |
| `outputs_v2` is the default runtime data root | The repaired 94-L3 system reduces noise from the old 350-L3 taxonomy |
| Keep `outputs/` compatibility through env overrides | Legacy experiments and old checkpoints may still need the 350-L3 setup |
| Do not edit large `outputs/outputs_v2` data files during code migration | Current task is path/mapping consumption; data regeneration is a separate controlled step |
| Do not rerun training in this phase | Training should only happen after mapping provenance and default paths are stable |
| KG build should prefer `outputs_v2/classification_hierarchy_v2.csv` | KG was previously at risk of using old 350-L3 hierarchy |
| Neo4j KG import must be explicit and v2-only by default | Server imports should consume `outputs_v2` / 94-L3 assets, require an explicit Neo4j password, never clear the database unless `--clear` is passed, and only use legacy `outputs/` through `--allow-legacy-inputs` |
| Phase0/Phase1 mainline changes are report-only | Candidate pool traces, evidence bundles, shadow decision core output, and retrieval shadow sources may be recorded, but they must not mutate `pred_tokens`, V4 beam output, decoder behavior, training, legacy metrics, or default selection |
| v2 QGIS metadata top-level `primary_l3` is authoritative for manual decisions | Some `all_candidates` entries contain stale automatic candidates after manual override |
| `manual_reviewed` and `manual_override` QGIS mappings bypass numeric `min_confidence` filtering | Manual review is a human decision; low legacy confidence scores should not drop reviewed keeps |
| Step8 cleaning records Step6 provenance warnings before writing final training data | Prevents silent provenance drift in reports without letting provenance metadata gate execution |
| Existing dataset splits must be validated against the current Step8 workflow count before reuse | Step8 cleaning can remove rows; stale split indices previously caused training/evaluation `IndexError` |
| Quality-gated V4 candidate is a derived artifact, not the source of truth | Keep original Step8 intact for auditability; use the quality-gate directory explicitly when doing smoke training or experiments |

## Completed Work

| Date | Completed |
| --- | --- |
| 2026-06-24 | Re-read the root tracking files (`task_plan.md`, `progress.md`, `findings.md`) and Claude memory files under `C:\Users\qiaoyun\.claude\projects\...\memory`, then checked the corresponding local code/artifacts. Current Phase 9 data truth: `outputs_v2/API_trace_to_L3_TRAINING_FINAL.jsonl` has 6,031 deduplicated API-trace L3 samples, `outputs_v2/vector_training_samples_UNIFIED.jsonl` has 10,768 Route 1+2 unified samples, and `_final_merge.py` explains the reported "~16,800" as 6,031 + 10,768 = 16,799 training candidates before any later package-level filtering. `QGISChainRetriever` now indexes facts text fields plus semantic tags/op-match/native bridge, so QGIS workflow data is actively used both as a landing retrieval library and as vector-planning supervision, not "unused". Security cleanup: removed a hardcoded `DEEPSEEK_API_KEY` from `run_process.bat` and replaced the full key recorded in `progress.md` with an environment-variable note. |
| 2026-04-29 | Migrated default config to `outputs_v2`, 94 vocab, v2 hierarchy, v2 id mappings, and v2 L3 embeddings |
| 2026-04-29 | Updated KG build defaults to prefer v2 hierarchy and v2 id mappings metadata |
| 2026-04-29 | Updated QGIS candidate generation and L3-to-platform mapper to load `mapping_metadata.qgis_to_l3` from `id_mappings_v2.json` |
| 2026-04-29 | Updated inference/evaluation/data helpers to consume config-layer v2 defaults |
| 2026-04-29 | Added default-path tests for v2 config and KG path resolution |
| 2026-04-29 | Found and fixed QGIS manual-review filtering bug: `Write Vector Tiles_mbtiles` and `Write Vector Tiles_xyz` were dropped by default confidence threshold |
| 2026-04-29 | Found and fixed stale-candidate bug: `Remove Duplicate Points` and `Mirror Raster` should use top-level manual `primary_l3`, not stale `all_candidates[0]` |
| 2026-04-29 | Added repository-level context maintenance protocol in `AGENTS.md` and a Chinese human-facing context mirror |
| 2026-05-07 | Added Step6/Step8 provenance gate: Step6 writes mapping/skip-list fingerprints, Step7 preserves them, Step8 validates them, and pipeline audit can fail on provenance warnings |
| 2026-05-07 | Fixed split alignment for v2 Step8 data: invalid existing splits are rebuilt deterministically, real `outputs_v2/dataset_splits_v4.json` now matches 107,399 workflows |
| 2026-05-07 | Added a model-facing Step8 training data quality audit and generated reports under `outputs_v2/pipeline/audit/` |
| 2026-05-07 | Built a quality-gated V4 candidate under `outputs_v2/pipeline/step8_quality_gate/`: low-confidence `auto_remap` quarantine, sparse task merge, grouped split by exact L3 sequence, candidate audit, and GEE alias audit |
| 2026-05-07 | Added and ran a V4 quality-gate training-entry smoke test: explicit candidate data/split/task vocab paths, local-only BERT load by default, v2 L3 embeddings, and one-batch forward without checkpoints |
| 2026-05-07 | Added a safe V4.2 quality-gate training launcher with explicit data/split/task-vocab/checkpoint paths and dry-run validation |
| 2026-05-07 | Added a safe Set Predictor V3 quality-gate training launcher with explicit candidate data/split/task-vocab/active-token/checkpoint paths and dry-run validation |
| 2026-05-07 | Added and generated a v2 quality-gate transition matrix from the candidate train split; updated the V4 quality-gate launcher to require it for strict training |
| 2026-05-21 | Verified the `gis-evaluate` Step8 + V4.6 mainline boundary without training: entrypoint is `gis_recommend.evaluation.runner:main`, data is original Step8 `outputs_v2/pipeline/step8/labeled_workflows_l3_v4_cleaned.json`, split is `outputs_v2/dataset_splits_v4.json`, default checkpoint is `outputs_v2/transformer_checkpoints_v4_6/best_model.pth`, reranker/repair/QGIS diagnostics are optional, and several contract issues remain report-time risks |
| 2026-05-21 | Implemented Phase1/2 mainline contract hardening for Step8 + V4.6: added `MainlineRunContract`, moved semantic metrics off the legacy 350-L3 special-token assumption, made `gis-evaluate` reports include token profile/data authority/repair capability/selection policy/L2 role, made `CandidateVerifier` default to v2 I/O metadata with missing-metadata degradation instead of silent legacy fallback, and marked V4-QG/V5/retrieval-stage experiment reports as non-mainline research artifacts. |
| 2026-05-21 | Closed the post-audit gaps for the Step8 + V4.6 contract: `QGISCandidateGenerator` now consumes the same run-contract I/O metadata authority as verifier/report, selected QGIS candidates expose `qgis_score_components` in per-sample decision traces, posthoc QGIS evaluation can receive the same contract, and `scripts/evaluate_v4_quality_gate.py` plus config comments no longer describe V4-QG as final/mainline. |
| 2026-05-21 | Hardened Neo4j KG import entrypoints for the current `outputs_v2` / 94-L3 mainline: `scripts/build_ontology_kg.py` now requires explicit Neo4j credentials, defaults to v2 hierarchy/id-mapping/embedding assets, handles the v2 hierarchy CSV schema, refuses legacy fallback unless `--allow-legacy-inputs` is set, and skips database clearing unless `--clear` is explicitly passed. `scripts/import_l3_mappings.py` now defaults to `outputs_v2/id_mappings_v2.json` with the same explicit server arguments and guarded legacy fallback. `scripts/README_KG_BUILD.md` now documents the safe server workflow. |
| 2026-05-21 | Implemented Phase0/Phase1 report-only shadow instrumentation for the Step8 + V4.6 Constraint Decoder: run contracts now record `candidate_pool_enabled`, `decision_core_mode`, `retrieval_mode`, and `l2_authority`; reports now include per-sample `candidate_pool_trace`, `evidence_bundle`, and `decision_trace.shadow_decision_core`; optional `--retrieval-shadow-k` builds lexical train-split retrieval shadow candidates without reading test references or replacing legacy output. No decoder, beam, training, metric, `pred_tokens`, or default selection behavior was changed. |
| 2026-05-08 | Completed Phase 1A through Phase 15C.1 read-only V5 semantic-boundary audit: runtime authority is limited to active dataset/sampler callables, TF/AR train-step callables, train-step return dict ABI, checkpoint selector condition, eval/inference decode callables plus direct inputs, and transition/legality data actually read by those callables |
| 2026-05-08 | Completed Phase 15C.3 runtime-boundary enforcement audit: no implemented V5 governance objects exist yet; pre-fix reverse-edge risks were legacy provenance hard-gating in Step8, audit warning process exits, validation/repair mutating selected QGIS chains, and reranker scoring that uses validation classifications |
| 2026-05-09 | Completed Phase 15C.2 code-level convergence pass: removed remaining `weights_only=False` loads in active scripts, converted legacy `train_v3`/`train_v4_3_rl`/`train_graph_embeddings` checkpoint selection to latest-snapshot behavior, and fixed the failing report-only repair test assertion |
| 2026-05-09 | Completed Phase 15C.2 structural alignment pass: removed raw/partial checkpoint load fallbacks from active inference and warm-start paths, made provenance validation report-only, kept repair suggestions non-mutating, and downgraded `gis_recommend.evidence` to snapshot/report-only stubs |
| 2026-05-09 | Completed empirical bottleneck audit in `docs/empirical_bottleneck_audit.md`: measured the real quality-gate dataset, transition graph, ambiguity, retrieval/Markov baselines, and concluded the current bottleneck is supervision/data ambiguity plus ontology/distribution issues, not proven model capacity |
| 2026-05-09 | Built the post-convergence empirical evaluation infrastructure: baseline-only artifact builder, error taxonomy, retrieval baselines, canonicalization audit, decode-policy summaries, engineering bottleneck attribution, console entry point, tests, and a 20-sample v2 smoke artifact under `outputs_v2/evaluation_reports/` |
| 2026-05-09 | Implemented the isolated V5_final runtime path as a memory-augmented AR planner with PVM retrieval attention, fixed temporal decay, training-only alpha noise, IO-constrained greedy/beam decode, diagnostic alpha/graph outputs, strict V5 checkpoint schema, empirical prediction attachment, minimal train/inference entrypoints, configs, docs, and tests |
| 2026-05-09 | Added the V5_final full training/evaluation engine: deterministic subsets, train/validation loop, optional AMP, gradient clipping, early stopping, best/latest checkpoint lifecycle, IO-mask bias annealing, report-only stability/collapse monitoring, evaluation JSON/Markdown, empirical prediction attachment, ablation flags, CLI dry-run, and tests |
| 2026-05-09 | Executed controlled V5_final empirical validation: Stage0 1k/5 completed stable, Stage1 10k/30 completed on CPU with batch size 512, both wrote checkpoints/reports/baseline comparisons under `outputs_v2/v5_final_reports/`; neither stage showed collapse alerts, but Stage1 did not exceed lexical/Markov retrieval baselines on the 50-sample report |
| 2026-05-10 | Completed V5_final controlled empirical attribution tasks: A1 strict no-PVM ablation artifacts synced under `outputs_v2/v5_final_reports/a1_no_pvm/`, Stage1 beam-search re-evaluation for beams 1/3/5/10 under `outputs_v2/v5_final_reports/beam_search_eval/`, and minimal lexical top-3 retrieval-assisted prototype under `outputs_v2/v5_final_reports/retrieval_assisted/` |
| 2026-05-10 | Implemented and evaluated `V5_hybrid_planner_prototype` as a retrieval-centered workflow planner: top-K lexical retrieval remains the structural anchor, candidate expansion allows only local <=1-edit variants under IO filtering, V5_final only scores/reranks complete candidates from the Stage1 checkpoint, and reports/attribution/traces are written under `outputs_v2/v5_final_reports/v5_hybrid_planner_prototype/` |
| 2026-05-10 | Evolved the hybrid planner with multistage retrieval fusion and safe reranking: added lexical/embedding/intent/workflow-structure/graph-aware retrieval sources, source attribution, contribution attribution, repair outcome metrics, failure decomposition, retrieval-confidence floor selection, and a 50-sample artifact under `outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/` |
| 2026-05-10 | Added the unified workflow benchmark runner and artifact: V4 teacher-forced metrics, V4 AR rollout metrics, V5 pure generation, retrieval-only planning, hybrid planning, and Set Predictor are now stored as separate task/mode/scope rows with explicit comparison groups and guardrails against TF-vs-rollout or set-vs-sequence metric mixing |
| 2026-05-10 | Implemented retrieval-centered planning stage evaluation: Set Predictor-compatible retrieval filtering with soft/hard modes, execution-aware rerank features, strictly local repair candidate generation, attribution/failure reports, forbidden-pattern scan artifact, tests, and 50-sample outputs under `outputs_v2/v5_final_reports/retrieval_filtering/`, `execution_aware_rerank/`, and `local_repair/` |
| 2026-05-10 | Implemented the evaluation-only repair oracle phase: explicit local edit pools, repair oracle vs identity retrieval, retrieval-pool oracle comparison, per-candidate repair attribution, rerank-selection failure detection, failure taxonomy, tests, forbidden-pattern scan, and artifacts under `outputs_v2/v5_final_reports/repair_oracle_phase/` |
| 2026-05-10 | Implemented the evaluation-only repair selection diagnostics phase: scorer term decomposition, identity-bias analysis, oracle-gap attribution, conservative/balanced/aggressive threshold sweeps, deterministic random modified-candidate control, forbidden-pattern scan, tests, and artifacts under `outputs_v2/v5_final_reports/repair_selection_diagnostics/` |
| 2026-05-10 | Implemented evaluation-only repair scorer ablations: no-edit-penalty, piecewise operation penalties, uniform edit-penalty sweep, execution/set-heavy weighting, retrieval-preservation-heavy weighting, scorer recommendation artifact, forbidden-pattern scan, tests, and outputs under `outputs_v2/v5_final_reports/repair_scorer_ablations/` |
| 2026-05-10 | Implemented evaluation-only repair edit-penalty calibration sweep: generated a 200-sample held-out repair oracle trace, swept uniform penalties 0.0 through 0.20 with bootstrap intervals, task/subset stability analysis, CSV curves, forbidden-pattern scan, tests, and outputs under `outputs_v2/v5_final_reports/repair_calibration_sweep/` |
| 2026-05-10 | Implemented the evaluation-only repair opportunity attribution study: consumed the existing 200-sample repair candidate traces, measured retrieval ambiguity, IO inconsistency, set mismatch, structural anomaly, repair locality, heuristic opportunity indicators, refined failure taxonomy, bootstrap correlation cautions, forbidden-pattern scan, tests, and artifacts under `outputs_v2/v5_final_reports/repair_opportunity_analysis/` |
| 2026-05-10 | Implemented the evaluation-only repair confidence regime discovery phase: consumed the existing 200-sample repair candidate traces, broke down repair subtypes/context conditions, searched precision-first low-corruption regimes, validated bootstrap intervals, compared random modified/narrow/edit-type controls, wrote forbidden-pattern scan, tests, and artifacts under `outputs_v2/v5_final_reports/repair_confidence_regimes/` |
| 2026-05-10 | Added the V5 system consolidation protocol and integrated its summary into the durable context docs: final system identity is retrieval-centered / execution-aware / rerank-driven / constrained-planning-oriented; generation remains unvalidated as the primary capability; repair remains oracle-supported but not deployable; future claims must separate deployed, experimental, and oracle-only evidence. |
| 2026-05-10 | Completed project-level scientific synthesis: integrated current empirical findings, benchmark governance, retrieval-centered planner results, repair diagnostics, scorer calibration findings, attribution boundaries, evaluation hierarchy, and task-family separation into a "Current Scientific Consensus" section in both PROJECT_CONTEXT.md and PROJECT_CONTEXT.zh-CN.md. This section is now the canonical inherited project state for future sessions. |
| 2026-05-10 | Added `docs/v5_l2_semantic_recovery_protocol.md` to formally separate the current retrieval-centered L3 runtime from the preserved long-term L1->L2->L3 architecture target. The protocol restores L2 as a future semantic-intent layer while keeping all claims evidence-bounded and non-runtime-authoritative. |
| 2026-05-10 | Built the bounded ontology inventory phase: generated conservative GEE<->QGIS mapping classifications, explicit unsupported GDAL/ArcGIS rows, execution-constraint inventory, unsafe mapping registry, narrow workflow-equivalence registry, forbidden-pattern scan, tests, and `docs/v5_bounded_ontology_inventory_protocol.md`. |
| 2026-05-12 | Implemented strict evaluation-only canonicalized workflow metrics: raw vs canonicalized Exact Match/LCS/token accuracy/SetF1, train-split commutative-pair discovery through the existing empirical canonicalization logic, TopK recovery, per-task/per-pair recovery, bootstrap intervals, examples, forbidden-pattern scan, tests, and artifacts under `outputs_v2/v5_final_reports/canonicalized_evaluation/`. |
| 2026-05-12 | Implemented strict evaluation-only workflow usability metrics v1: Top1/Top3/Top5 usable-rate proxies reading 369 persisted prediction records, required-step coverage, harmful/missing step rates, QGIS mapping coverage, ordering/length/redundancy checks, per-task breakdown, failure taxonomy, examples, bootstrap intervals, forbidden-pattern scan, tests, and artifacts under `outputs_v2/v5_final_reports/workflow_usability_evaluation/`. |
| 2026-05-13 | Rewrote `scripts/evaluate_workflow_usability.py` as a self-contained evaluation pipeline (v2): no model, no checkpoint, no training, no semantic retrieval, no LLM judging. Directly evaluates lexical retrieval on 200 quality-gated test samples with 7 rule-based usability metrics using L1/L2 hierarchy categories and QGIS mappings. Generated all 7 report artifacts. Key finding: Top-1 usable 56%, Top-3/Top-5 100%, mean usability 0.7663 exceeds reference 0.7207 — retrieval already produces practically usable chains. |
| 2026-05-13 | Implemented V4-QG planner Phase 1 candidate-pool/rerank entrypoint in `scripts/run_v4_qg_planner.py`: quality-gate defaults, retrieval TopK candidate pool, optional V4 AR candidate hook, train-frequency Set Predictor fallback when checkpoint is absent, soft transition prior as a rerank feature, rule-usability-first selection, JSON/CSV/Markdown artifacts, forbidden-pattern scan, tests, and 200/1,000-sample reports under `outputs_v2/v4_qg_planner_reports/`. |
| 2026-05-12 | Implemented strict evaluation-only multi-reference workflow evaluation: exact-task/text reference pooling from existing labeled workflows, raw single-reference vs best-of-multi-reference vs canonicalized-multi-reference metrics, TopK usability deltas, workflow-family breakdowns, ambiguity taxonomy, recovered examples, forbidden-pattern scan, tests, and artifacts under `outputs_v2/v5_final_reports/multi_reference_evaluation/`. |
| 2026-05-14 | Fixed V4-QG planner Set Predictor checkpoint default alignment: V4.6 quality-gate Set Predictor artifacts now default to `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth`, matching the final practical V4.6 line and avoiding accidental loading of stale old-schema checkpoints. |
| 2026-05-14 | Implemented the MRV Stage 1-2 experiment plus human-review export: adjacent-swap variants from quality-gate train commutative pairs, conservative automatic gates, registry eligibility output, stratified review CSV, design/plan docs, tests, and smoke artifacts under `outputs_v2/v4_qg_multiref_validation/`. |
| 2026-05-14 | Corrected MRV validation-target drift by separating GEE/workflow-level semantic validation from downstream QGIS landing. QGIS mapping/chain failures are now auxiliary transferability signals and no longer block `verified_equivalent_candidate` labels. |
| 2026-05-15 | Completed first manual MRV equivalence review over the 19 auto-verified workflow-semantic candidates: 14 labeled `equivalent`, 4 `uncertain`, 1 `not_equivalent`. The manual-only multi-reference registry now contains 7 task groups sourced from the 14 accepted swaps; uncertain/rejected rows remain excluded from training labels. |
| 2026-05-15 | Completed source-level deep review for the 4 MRV `uncertain` candidates. Three are now recorded as conditional-equivalent but not registry-eligible, and `wf46_pos2_swap53_28` was downgraded to `not_equivalent` because `filterMetadata` occurs on the ImageCollection chain before an image-level `select`, making the swapped variant an object-chain conflict. |
| 2026-05-15 | Ran the 500-variant MRV expansion and added a reusable equivalence taxonomy analysis layer. The expansion produced 46 auto candidates and 454 invalid variants; new family/risk/rejection artifacts identify filter/filter and select/filter swaps as the best manual-review priority while keeping QGIS landing failures auxiliary. |
| 2026-05-15 | Completed and revised an AI-assisted review draft for all 46 MRV expansion auto candidates: 36 equivalent, 8 uncertain, 2 not equivalent. Wrote review CSV/JSON/Markdown plus a non-training registry draft with 19 groups / 36 variant sources. |
| 2026-05-15 | Promoted the user-confirmed MRV review into a formal registry v2 / equivalence KB v2. The builder deduplicates by `variant_id`, keeps only `equivalent` rows as training-eligible, preserves 13 excluded variants, and normalizes family/risk summaries so `review_flags` remain separate evidence fields. Final v2 counts: 55 unique reviewed variants, 42 equivalent variants, 23 task groups. |
| 2026-05-15 | Implemented controlled MR training ablation data construction and generated isolated `mr_5`, `mr_10`, and `mr_all_42` quality-gate derivatives under `outputs_v2/v4_qg_mr_ablation/`. The builder reads only verified MRV registry v2 / KB v2, appends variants to train only, preserves val/test, writes provenance and a no-training manifest, and does not overwrite mainline quality-gate data or checkpoints. |
| 2026-05-15 | Implemented the read-only MR ablation comparison scaffold. It consumes existing baseline and `mr_*` report JSON files, extracts aligned usability/canonicalized/diversity/invalid-harmful metrics where present, computes deltas plus paired bootstrap CIs when per-sample rows are available, and writes comparison JSON/Markdown without training, inference, checkpoint loading, or data mutation. |
| 2026-05-17 | Ingested the server-reported `mr_all_42` V4.6 quality-gate training log. The run completed 50 epochs from scratch, but AR-SS training loss became `inf` from epoch 11 onward and the final latest checkpoint underperformed historical quality-gate V4.2 TF metrics. Treat this as a training-stability/checkpoint-selection diagnostic before making MR effect claims. |
| 2026-05-17 | Fixed the V4.6 AR scheduled-sampling non-finite-loss bug: dynamic minimum-length early-END masking is now decode-only, while CE loss and early-END penalty inspect unmasked logits. Added a regression test that reproduces the old `END_INDEX` target + masked-logit `inf` loss path. Full server training rerun is still pending. |
| 2026-05-19 | Reviewed `结果/周报/周报-2026-05-24.md` and fixed two V4-QG planner blockers discovered during smoke verification: `fallback_set_prior` no longer references `set_prior` before assignment, V4 AR candidate generation now calls `set_complexity_profile()` so task-adaptive EOS suppression is actually applied, and small-sample Markdown CI formatting handles `None` bootstrap bounds. |
| 2026-05-19 | Aligned length/complexity artifacts to the V4 quality-gate mainline: `scripts/compute_task_type_length_stats.py` now defaults to quality-gate data/output, generated `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`, and planner/inferencer length-stat lookup now prefers quality-gate stats before `outputs_v2` root and legacy `outputs/`. |
| 2026-05-19 | Upgraded the V4-QG retrieval/evaluation reporting path: `LexicalRetrieval` now performs query-aware Jaccard ranking over task name/description text while keeping same-task candidates primary and global candidates as low-weight backoff; `run_v4_qg_planner.py` passes task text into retrieval; `evaluate_v4_quality_gate.py` now writes a five-tier metric view and Markdown summary that demotes sequence EM/token accuracy to diagnostics and makes workflow usability/QGIS landing the primary KPI family. This is lexical text matching, not embedding or semantic retrieval, and still needs server-scale ablation. |
| 2026-05-16 | Checked the local minimum MR training loop preconditions. No local V4.6 quality-gate baseline checkpoint or `mr_all_42` checkpoint exists, the workspace is CPU-only (`torch.cuda.is_available=False`), `l3_embeddings_v2.pt` and local BERT cache are present, and quality-gate plus `mr_all_42` dry-runs pass. Full training is deferred to the user's server; do not infer model impact locally. |
| 2026-05-23 | Started the correction sprint away from further observation-only Phase5.x expansion and toward direct ranking remediation. Added an offline evidence-aware ranking experiment that reads existing report/candidate artifacts, compares legacy selection vs evidence-aware selection vs oracle best-in-pool, and writes diagnostics under `outputs_v2/diagnostics/evidence_aware_ranking/` without changing mainline `pred_tokens`, metrics, beam, reranker, or selection. Smoke result on 120 empirical records: evidence-aware LCS 0.4412 vs legacy 0.3957 and SetF1 0.6361 vs 0.5666, but TokenAcc drops 0.1941 -> 0.1696 and oracle match is slightly lower 0.3500 vs 0.3583, so this is a useful ranking signal but not yet production-ready. |
| 2026-05-27 | Built ExecutionAwareSelector as multi-source candidate scoring module (`src/gis_recommend/planning/`). Selector combines retrieval + beam + MR candidates, scores on 9 execution-aware features (QGIS mapping, I/O, transition validity, length fit, repetition, etc.), produces ranked output with explainable selection trace. 200-probe: 100% combined bridge, 0.995 avg quality. |
| 2026-05-28 | Trained DPO v2 model: preference data from 5000 train + 1000 val beam pairs (6019/1214 pairs), 2 epochs. Beam top-1 usable jumped from 59.9% → 98.8% on 3000 test. Verified with manual 50-sample semantic audit: 66% clean, 34% duplicates only, 0% semantic concerns. |
| 2026-05-29 | Built QGIS chain dataset from GitHub crawled scripts (D1 merged dedup: 54k scripts, 3021 multi-step chains). Built QGISChainRetriever + Evaluator. 200-probe: 100% combined bridge, 87.5% L3 bridge, 20% native bridge. Crosswalk expanded: 18 accepted mappings merged, L3 bridge coverage 12.3% → 24.8%. |
| 2026-05-30 | DPO v2 validated on 50-showcase probe: 100% QGIS valid, 100% combined bridge. 50 GEE probe manual audit: A-level 15/50, A/B 17/50, B 15/50, B/C 2/50, C 1/50. Model generates structurally correct L3 sequences for GEE/remote sensing tasks but exhibits template behavior for vector tasks. |
| 2026-05-31 | Built 200-query stratified ablation for QGIS landing. Fixed modality metric for mixed chains (47% → 100%). Added native bridge for reprojectlayer. Combined bridge: 100% modality agreement, 94.5% L3 bridge hit, 0.995 avg quality. Integrated QGIS landing into main eval pipeline (--use-qgis-landing flag). |
| 2026-06-01 | Crawled and analyzed new QGIS facts_summary1000.csv: 2260 task_name/description records, 97.5% match with v2 chains. Filed as critical gap: retriever not indexing facts text, causing 0.5% recall@20. |
| 2026-06-02 | Built QGIS reranker baseline (LogisticRegression, 12 features, AUC 0.67). Upgraded to v2 with 22 task-aware features (XGBoost). Built retrieval reranker with hard negatives from retriever. Early results: AUC 0.61 (limited by synthetic negatives). |
| 2026-06-03 | Pivoted approach: retriever index fix identified as top priority. Merged facts_summary text into chain records (qgis_chain_dataset_v2_enriched_v3.jsonl). Retrieval recall jumped from 0.5% → 100% (self-retrieval), 99.6% R@1 even with operator keywords masked. Verified end-to-end: modality match improved from 0/30 → 30/30, unique chains 1 → 10. |
| 2026-06-04 | GRPO headroom diagnosis completed: 100 vector tasks, beam top-5 scored. Headroom >0.05: 47%, strong >0.10: 8%, worth training: 0%. Conclusion: GRPO not viable for current DPO model; beam diversity too low for vector tasks. Phase conclusion: freeze L3 model, push QGIS landing layer as primary improvement path. |
| 2026-06-04 | Completed QGIS retrieval/reranker correction audit. Earlier 0.5% natural retrieval recall was traced to missing facts text in the QGIS chain index, not to a fundamental retriever failure. After indexing `Task Name` / `Task Description`, self-retrieval results are Full facts R@1/R@20 100%, short Task Name R@1 99.4% / R@20 100%, and operator-masked R@1 99.6% / R@20 100%. QGIS reranker remains useful only after the correct/gold chain is in the candidate pool; it is not the main bottleneck. Current deployable direction is fixed QGIS retrieval + bridge/native-bridge expansion, not more L3 RL training. |
| 2026-06-04 | Completed strict manual audit for `outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv`: 80 open-style QGIS landing tasks, modality match 100%, unique chains improved 1→16 after index repair, but strict semantic grades are A=2 / B=23 / C=55. Main failure mode is template collapse: 30 tasks use `native:reprojectlayer -> native:buffer -> native:clip`, 16 use `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer`, and 10 mixed tasks use `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject`. Next work is fine-grained QGIS operator bridge/native bridge expansion, not more modality fixes. |
| 2026-06-04 | User-reported open landing ablation after op-match and semantic-tag expansion: unique chains improved 1 → 16 → 33, top-3 concentration improved 100% → 31%, and the `native:reprojectlayer -> native:buffer -> native:clip` template dropped from 30 to 7 uses. New tags such as `voronoi`, `density_heatmap`, `nearest_neighbor`, `raster_sampling`, and `zonal_statistics` are moving retrieval toward task-specific chains. Current `+sem tags` modality is 84%, below the >90% target, but this is attributed to rebuilding the enriched dataset without facts text and mixing the old index; treat this as an integration issue, not evidence that semantic tags hurt modality. |
| 2026-06-06 | Completed a read-only QGIS data utility audit for vector-processing improvement. Current QGIS assets are useful in three distinct ways: `qgis_chain_dataset*.jsonl` as executable-chain retrieval pools, `qgis_vector_chain_described.jsonl` plus `qgis_vector_preference_pairs_clean.jsonl` as weak vector preference/ranking supervision, and `open_landing_results.csv` as human evaluation evidence. No single current QGIS dataset has all three required signals at once: facts text, semantic tags, and L3 bridge. The best next data engineering step is to merge facts-text indexing, semantic tags, modality, and bridge/native-bridge fields into one canonical vector landing dataset before further reranker or preference training. |
| 2026-06-06 | Rechecked the current local `outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv`. The file now parses as 80 rows with grades A=18 / B=33 / C=29, not the earlier A=2 / B=23 / C=55 handoff statistic. Current top templates are still concentrated but improved: `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer` appears 14 times, `native:reprojectlayer -> native:buffer -> native:clip` appears 7 times, and `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject` appears 5 times. Treat older grade/template counts as historical pre-expansion evidence unless the older CSV is explicitly restored. |
| 2026-06-06 | Built and verified `outputs_v2/canonical_vector_planning_dataset.jsonl` as the QGIS-derived vector planning supervision dataset. It contains 2,319 records with `task_text`, `modality`, `qgis_ops`, abstract `planning_steps`, `l3_steps`, `has_full_l3`, and `required_step_families`. Verified counts: 1,598 vector records, 1,046 full-L3 records overall, 733 pure-vector full-L3 records, and 20 non-empty required-step families. This artifact changes the QGIS role from mostly landing/retrieval evidence to a direct source for vector-planning SFT/preference preparation. |
| 2026-06-06 | Completed a training-quality audit of `outputs_v2/canonical_vector_planning_dataset.jsonl`. Schema is structurally sound: required fields are present, `qgis_ops` / `planning_steps` / `l3_steps` lengths match for all 2,319 rows, QGIS chains are unique, and `has_full_l3` is internally consistent with blank/nonblank L3 slots. However, full-dataset quality is mixed: 59 rows have very short task text, 463 rows have empty `required_step_families`, 20.4% of operator steps are `other`/blank-L3, and 140 rows contain invalid current-vocab L3 code `L3_02_05_04`. The cleanest immediate SFT seed is not 733 but 610 rows after filtering pure-vector full-L3 records to valid 94-L3 codes, task text length >=80, non-empty required families, chain length <=15, and core providers only. |
| 2026-06-06 | Verified user-generated `outputs_v2/canonical_vector_clean_sft_seed.jsonl` after the centroid/L3 cleanup. Structural checks pass: 685 rows, all `modality=vector`, required fields present, `has_full_l3=true`, no length mismatches, no blank L3, no `other` planning steps, no invalid current-vocab L3, chain length 2-15, task text length 299-300, unique task text and QGIS chains. This is structurally usable as an SFT seed. Semantic caveat: the builder still uses coarse planning-step-to-L3 mappings, e.g. `geometry_repair`/`fixgeometries` -> `L3_02_07_01` even though that L3 is "Multipart to Singlepart", `raster_sampling`/`rasterize`/`polygonize` -> `L3_03_01_01` ("Clip Raster by Geometry"), `grid_generation` -> `L3_02_05_12` ("Minimum Bounding Geometry"), and all overlay subtypes -> `L3_02_02_06` ("Clip"). Treat the 685 rows as structurally clean but not yet semantically audited enough for high-confidence SFT without either accepting coarse L3 family labels or refining mappings. |
| 2026-06-06 | Re-verified `outputs_v2/canonical_vector_clean_sft_seed.jsonl` after coarse overlay remapping. The target coarse failures are fixed: `L3_02_05_04` count is 0; overlay subtypes map to their own current-vocab L3 codes (`Intersect` 110, `Union` 37, `Erase/Difference` 73, `Symmetrical Difference` 5, `Clip` 219). The earlier `Clip` collapse is gone for vector overlay. Remaining caveat is taxonomy granularity rather than structural quality: geometry repair/validation/simplify/delete-holes still share `L3_02_07_01`, and raster sampling/rasterize/polygonize still share `L3_03_01_01`; use as semantic-level clean only if those family-level labels are accepted by the current training/evaluation contract. |
| 2026-06-06 | Verified `outputs_v2/pipeline/step8_qgis_vector_sft/` as a Step8-compatible QGIS vector SFT package. It contains 685 workflows with deterministic 548/68/69 splits, legal 94-L3 token ids, complete task metadata, and a local single-type vocabulary `"Vector Analysis": 0`. V4.2 and V4.6 training launchers both dry-run on the package, and the V4 training-entry smoke completes a CPU forward pass. It is ready as a QGIS-only SFT input and as a component for mixed GEE+QGIS training; current launchers do not yet implement the proposed 5:1 mixed-batch schedule. |
| 2026-06-06 | Audited `outputs_v2/pipeline/step8_quality_gate_qgis_vector/`, the merged quality-gate + QGIS vector package. Structure and loader checks pass: 77,569 workflows, exact 62,180/7,694/7,695 split coverage, QGIS 685 rows appended train-only with combined task type `"Vector Analysis": 47`, no new invalid normal L3 ids, and no cross-split content-sequence overlap. V4.6 dry-run and actual QGIS-sample CPU forward pass succeed. Main blockers are command/loader compatibility: `scripts/train_v4_6_quality_gate.py` has no `--lr` argument, and strict `--warmstart` from current 47-task DPO/quality-gate checkpoints fails when loading the 48-task model. |
| 2026-06-07 | Server-ran the merged quality-gate + QGIS vector training smoke on CUDA. From-scratch 5 epochs completed, but because `--num-epochs 5` with no warmstart keeps `tf_phase_epochs=10`, it was TF-only; best validation composite was 0.4916 at epoch 4 and test AR SetF1 was 0.445. Expanded-warmstart route succeeded after `scripts/expand_checkpoint_task_types.py` converted DPO v2 task-type weights from 47 to 48; 5 warmstart epochs ran AR-SS immediately, reached best validation composite 0.5922 at epoch 1, and tested at AR SetF1 0.523 / LCS 0.386 / earlyEOS 12.9%. Treat warmstart as the better continuation candidate; archive the from-scratch smoke if needed because the second run reused the same checkpoint directory. |
| 2026-06-07 | Server-ran `scripts/evaluate_sft_vector_impact.py` against the warmstart SFT checkpoint and DPO v2 baseline. Strict vector token rates: GEE test DPO 0.4% vs SFT 2.0% (delta +1.6pp), QGIS clean seed DPO 1.7% vs SFT 53.7% (delta +52.0pp). Interpretation: the 685 QGIS vector SFT rows were strongly absorbed by the model while GEE raster preservation remains mostly intact at this smoke level. Boundary: QGIS seed tasks are train-source/absorption evidence, not held-out semantic vector-planning generalization. The script now passes the merged 48-task length stats to the SFT inferencer so `"Vector Analysis"` does not silently fall back to the default 47-task stats path. |
| 2026-06-07 | Reviewed and hardened the held-out vector generalization benchmark before server execution. `configs/unseen_vector_prompts.jsonl` is hand-written and has no exact/substring overlap with `canonical_vector_clean_sft_seed.jsonl`, but its actual modality split is 61 vector / 6 mixed / 3 raster, not the earlier stated 55 / 8 / 7. `scripts/evaluate_vector_generalization.py` now fail-fasts on missing model/vocab/length-stat assets, passes explicit 48-task SFT and 47-task DPO length stats, applies task-type complexity profiles before decoding, keeps raster clip distinct from vector clip, reports measurable vs strict/all expected-family recall, reports unsupported expected families under the current 94-L3 taxonomy, and writes path/count/aggregate metadata to `outputs_v2/diagnostics/vector_generalization.json`. |
| 2026-06-07 | Server-ran `scripts/evaluate_vector_generalization.py` on the 70 hand-written unseen prompts. Vector prompts improved sharply from DPO to SFT in modality behavior: measurable expected-family recall 2.1% -> 25.7%, strict/all recall 1.6% -> 20.2%, raster-ish token rate 94.8% -> 35.6%, vector token rate 1.4% -> 53.3%. Raster controls show no vector contamination: vector token rate stayed 0.0%, raster-ish rate rose 77.8% -> 88.6%. Interpretation: QGIS-vector SFT taught the model to enter a vector planning regime and avoid raster-template collapse on vector prompts, but fine-grained vector semantics remain weak. SFT mainly predicts `spatial_filter`, `spatial_join/table_join`, `buffer`, and `merge`; it still misses dissolve, geometry repair/cleanup, clip, intersection, difference, attribute filter, CRS transform, field calculation, export, grid/centroid, and most unsupported fine QGIS families. Overlay subtype generalization is poor except the single union case. |
| 2026-06-07 | Locally audited the oversampled QGIS-vector package before server training. `outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/` has 81,137 workflows, split 65,748/7,694/7,695, 4,253 train-only QGIS vector rows, no normal token id >=94, and `"Vector Analysis": 47`. Generated `task_type_length_stats.json` for this package; the V4.6 training command must pass it with `--length-stats`. `scripts/evaluate_vector_generalization.py` now accepts CLI overrides for SFT checkpoint/vocab/length-stats/report path, so oversampled runs can be evaluated without editing hardcoded v1 paths. |
| 2026-06-07 | Server-ran the oversampled QGIS-vector warmstart path. First rebuilt `outputs_v2/transition_allowed_next.json` from `step8_quality_gate_qgis_vector_oversampled` (65,748 train workflows, 60 states, 607,006 transitions), then expanded DPO v2 from 47 to 48 task types and trained 5 AR-SS epochs into `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/`. Best checkpoint was epoch 1 with validation composite 0.5895; test metrics were AR SetF1 0.540, LCS 0.397, earlyEOS 11.3%, PPL 17.7. Held-out vector generalization against `outputs_v2/diagnostics/vector_generalization_oversampled.json`: vector prompts measurable recall 3.8% -> 27.8%, strict/all 3.0% -> 21.9%, vector token rate 1.5% -> 57.6%, raster-ish token rate 92.8% -> 34.7%, raster controls kept vector token rate 0.0%. Interpretation: oversampling improved vector-regime strength slightly over v1 but still did not solve fine-grained vector semantics; overlay subtype recall was still 0 for intersection, union, and difference on the current prompt set. |
| 2026-06-07 | Patched `scripts/evaluate_sft_vector_impact.py` to accept CLI overrides for SFT checkpoint/vocab/length-stats/report path, matching `evaluate_vector_generalization.py`. Important: the user's post-oversampling `python scripts/evaluate_sft_vector_impact.py` run still loaded the conservative v1 SFT checkpoint by default (`outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector/best_model.pth`), so its QGIS seed 63.7% result is not oversampled-v2 absorption evidence. Rerun with explicit oversampled paths and write to `outputs_v2/diagnostics/sft_vector_impact_oversampled.json` before comparing v2 seed absorption/preservation. |
| 2026-06-07 | Server-reran `scripts/evaluate_sft_vector_impact.py` with explicit oversampled SFT checkpoint/vocab/length-stats. The run correctly loaded `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/best_model.pth`, the oversampled 48-task vocab/stats, and the 60-state transition matrix. Result: GEE strict-vector rate DPO 0.4% vs SFT 2.4% (+2.0pp), QGIS seed DPO 1.7% vs SFT 57.2% (+55.5pp), with SFT avg length 6.8 on both sets. Interpretation: v2 oversampled seed absorption is confirmed and GEE contamination remains small in this smoke, but it is not materially stronger than v1 on held-out fine-grained vector semantics. Report path: `outputs_v2/diagnostics/sft_vector_impact_oversampled.json`. |

## Modified Files And Why

| File | Why It Changed |
| --- | --- |
| `outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv` | Filled strict manual `grade` and `notes` for 80 open QGIS landing tasks |
| `outputs_v2/canonical_vector_planning_dataset.jsonl` | New canonical QGIS-derived planning dataset for vector-planning supervision: task text, modality, QGIS ops, abstract planning steps, L3 steps, full-L3 flag, and required step families |
| `outputs_v2/pipeline/step8_qgis_vector_sft/*` | Step8-compatible package for the 685 clean QGIS vector SFT rows: labeled workflows, deterministic 548/68/69 splits, local task vocabulary, and manifest |
| `outputs_v2/pipeline/step8_quality_gate_qgis_vector/*` | User-generated conservative merged quality-gate + QGIS vector package: 77,569 workflows, combined 48-type task vocabulary, merged length stats, train-only QGIS injection, and manifest |
| `outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/*` | Higher-ratio QGIS vector SFT package: 81,137 workflows, 65,748/7,694/7,695 split, 4,253 train-only QGIS rows, combined 48-type vocabulary, and generated package-specific `task_type_length_stats.json`. |
| `scripts/evaluate_sft_vector_impact.py` | Compares warmstart SFT vs DPO v2 on GEE preservation and QGIS vector seed absorption; now passes per-model length stats paths so SFT uses the 48-task mixed length stats and DPO uses the original 47-task quality-gate stats, and supports CLI overrides for oversampled SFT checkpoint/vocab/length-stats/report paths. |
| `configs/unseen_vector_prompts.jsonl` | Hand-written held-out prompt benchmark for vector generalization. Current actual split is 70 rows: 61 vector, 6 mixed, 3 raster; it is not sampled from the clean SFT seed file. |
| `scripts/evaluate_vector_generalization.py` | Compares DPO v2 vs QGIS-vector SFT on held-out prompts using expected-family recall, raster/vector token rates, chain length, overlay subtype recall, and sample predictions. The script now uses explicit per-model vocab/length stats, task-type complexity profiles, modality-aware scoring, unsupported-family reporting, metadata-rich JSON output, and CLI overrides for oversampled SFT checkpoint/vocab/length-stats/report paths. |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | Added optional `length_stats_path` to V4 inferencer so evaluation/inference can align task vocabulary and length-bucket priors for mixed 48-task checkpoints without changing default behavior. |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | Recorded QGIS landing manual-audit results, pitfalls, and next bridge/native-bridge priorities |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | Recorded the 2026-06-06 read-only QGIS data utility audit, current local open-landing grade counts, and the data-version pitfall around mixing facts text, semantic tags, and L3 bridge signals |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | Updated the project focus after `canonical_vector_planning_dataset.jsonl`: QGIS workflow data is now a direct vector planning supervision source, not just landing evidence |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | Recorded Step8 QGIS vector SFT package readiness, dry-run/smoke evidence, and mixed-training caveats |
| `docs/PROJECT_CONTEXT.md` / `docs/PROJECT_CONTEXT.zh-CN.md` | Recorded the merged `step8_quality_gate_qgis_vector` package audit, including split/token checks, QGIS train-only injection, from-scratch trainability, and the 47->48 task-type warmstart blocker |
| `AGENTS.md` | Repository-level instruction for future sessions to read and update durable context documents automatically |
| `docs/PROJECT_CONTEXT.md` | Records the V4.6 AR-SS stability fix, verification evidence, remaining rerun requirement, and the pitfall that old `loss=inf` logs are pre-fix training-stability evidence rather than MR-label evidence |
| `docs/PROJECT_CONTEXT.zh-CN.md` | Chinese mirror of the V4.6 AR-SS stability fix, verification evidence, remaining rerun requirement, MR interpretation boundary, and the 2026-05-19 weekly-report/planner smoke review |
| `scripts/run_v4_qg_planner.py` | New V4-QG Phase 1 practical planner entrypoint: merges retrieval and optional V4 AR candidates, applies train-frequency or checkpoint Set Predictor priors, scores soft transition/set coverage/QGIS mapping/rule usability, writes candidate traces and rerank reports, performs forbidden-pattern scanning without training or checkpoint mutation, and now defaults its Set Predictor prior to the V4.6 quality-gate checkpoint directory. |
| `scripts/run_v4_qg_planner.py` | 2026-05-19 planner smoke and length-path fix: construct `set_prior` before deriving trained-prior fallback, call `set_complexity_profile()` for AR candidates instead of only `set_expected_length()`, safely render `None` bootstrap CI bounds for tiny smoke runs, and default/report `--length-stats` under `step8_quality_gate`. |
| `scripts/run_v4_qg_planner.py` | Passes task name/description text into the retrieval candidate source so query-aware lexical/Jaccard scoring affects real planner candidate order, not only standalone tests. |
| `scripts/evaluate_workflow_usability.py` | `LexicalRetrieval` now ranks same-task workflows by query Jaccard over task text, then supplements with low-weight global backoff when needed; restored lightweight test helper APIs for usability records/QGIS mapped-token extraction/forbidden scans. No sklearn/embedding dependency was added. |
| `scripts/evaluate_v4_quality_gate.py` | Adds `five_tier_metrics` to `evaluation_report.json` plus `evaluation_summary.md`; Tier 2/3 workflow usability and QGIS landing are presented first, while sequence EM/token accuracy/LCS/SetF1 are explicitly diagnostic historical-reproduction metrics. |
| `tests/test_workflow_usability.py` | Covers query-aware retrieval ordering and restored lightweight workflow-usability helper APIs. |
| `tests/test_v4_qg_evaluation_report.py` | Covers five-tier V4-QG evaluation report construction and Markdown summary output without loading checkpoints or running inference. |
| `tests/test_v4_qg_planner.py` | Covers quality-gate default paths including the V4.6 Set Predictor checkpoint directory, soft transition scoring, set coverage features, candidate-pool deduplication/source attribution, rule-usability-first reranking, and forbidden-pattern scan behavior |
| `scripts/compute_task_type_length_stats.py` | Computes content-token length stats with explicit CLI paths; defaults to quality-gate data and writes `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`, while `--legacy-step8` preserves the old Step8 output path. |
| `scripts/analyze_length_bucket_distribution.py` | Reads the shared default length-stats resolver so bucket analysis follows the quality-gate stats artifact by default. |
| `src/gis_recommend/data/length_bucket_predictor.py` | Adds `default_length_stats_path()` with priority `outputs_v2/pipeline/step8_quality_gate` -> `outputs_v2` root -> legacy `outputs`, so task-adaptive EOS buckets no longer silently prefer legacy stats. |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | Uses the shared length-stats resolver for expected-length and task-adaptive EOS lookup. |
| `src/gis_recommend/inference/infer_l3_candidates_v4_qg.py` | Uses the shared length-stats resolver for the quality-gate inferencer. |
| `tests/test_task_type_length_stats.py` | Covers content-token length-stat computation, requested output writes, and default length-stats path priority. |
| `scripts/evaluate_evidence_aware_ranking.py` | Offline-only correction-sprint experiment for the six core issues, focused on Ranking/Evaluation/Semantic-Constraint remediation. It extracts candidate pools from existing reports, applies an observable evidence-aware policy, computes oracle best-in-pool headroom when references exist, and writes JSON/Markdown diagnostics without wiring into runtime selection. |
| `tests/test_evidence_aware_ranking.py` | Covers the new offline ranking contract: observable-support tie break, synthetic-candidate exclusion, missing score stays `None`, oracle metrics require references, and input records are not mutated. |
| `outputs_v2/diagnostics/evidence_aware_ranking/evidence_aware_ranking.json` | Generated smoke artifact comparing legacy, evidence-aware, and oracle candidate selections on the existing empirical report records. |
| `outputs_v2/diagnostics/evidence_aware_ranking/evidence_aware_ranking.md` | Human-readable summary of the offline evidence-aware ranking smoke result and contract boundaries. |
| `src/gis_recommend/config/transformer_config.py` | Default runtime paths now point to `outputs_v2`; vocab default is 94; env overrides remain for legacy 350-L3 runs; V4.6 quality-gate Set Predictor checkpoints use `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6` |
| `scripts/build_ontology_kg.py` | KG build now prefers `outputs_v2/classification_hierarchy_v2.csv` and reads v2 `id_mappings_v2.json` metadata |
| `scripts/build_ontology_kg.py` | Tightened embedding checkpoint loading to `torch.load(..., weights_only=True)` so KG enrichment reads tensor/snapshot payloads only |
| `scripts/build_ontology_kg.py` | Neo4j KG build now exposes server CLI/env arguments, requires a password, defaults to `outputs_v2` / 94-L3 inputs, supports v2 hierarchy CSV rows without legacy description columns, does not clear Neo4j unless `--clear`, and only allows legacy input fallback through `--allow-legacy-inputs`. |
| `scripts/import_l3_mappings.py` | Standalone L3 mapping import now defaults to `outputs_v2/id_mappings_v2.json`, uses the same v2 mapping loader as KG build, accepts explicit Neo4j CLI/env arguments, and guards legacy fallback behind `--allow-legacy-inputs`. |
| `scripts/README_KG_BUILD.md` | Documents the current v2/94-L3 Neo4j KG import workflow, safe `--clear` behavior, optional embedding import, and the remaining instance-layer caveat. |
| `src/gis_recommend/operators/qgis_candidate_generator.py` | Defaults to v2 id mappings; respects manual QGIS mapping decisions; keeps manual-reviewed mappings under default threshold |
| `src/gis_recommend/operators/l3_to_platform_mapper.py` | Defaults to v2 hierarchy/id mappings; parses v2 QGIS metadata; respects manual top-level `primary_l3` |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | Uses config-level hierarchy and id mappings paths |
| `src/gis_recommend/inference/infer_l3_candidates.py` | Tightened legacy V3 checkpoint loading to `torch.load(..., weights_only=True)` and kept runtime config derivation from snapshot fields only |
| `src/gis_recommend/inference/infer_l3_candidates.py` | Phase 15C: inference checkpoints must be wrapped payloads with supported schema and `model_state_dict`; `allow_partial_load` is now a no-op compatibility parameter and strict loading is mandatory |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | Phase 15C: removed raw state-dict and `strict=False` fallback; V4 inference loads only supported wrapped checkpoint payloads |
| `src/gis_recommend/inference/infer_task_conditioned_v3.py` | Phase 15C: retained `--allow_partial_load` as deprecated CLI compatibility only; it no longer changes loader behavior |
| `src/gis_recommend/evaluation/runner.py` | Uses config-level v2 paths for evaluation and reranker flows |
| `src/gis_recommend/evaluation/semantic_metrics.py` | Tightened L3 embedding loading to `torch.load(..., weights_only=True)` |
| `src/gis_recommend/evaluation/evaluate_generation_detailed_v3.py` | Tightened legacy detailed-eval checkpoint/embedding loads to `weights_only=True` |
| `src/gis_recommend/evaluation/evaluate_generation_detailed_v3.py` | Phase 15C: detailed evaluation now requires wrapped checkpoint payloads and strict model loading after any explicit evaluation-only embedding replacement |
| `src/gis_recommend/data/__init__.py` | Shared data helpers now default to `outputs_v2` and prefer `id_mappings_v2.json` |
| `src/gis_recommend/data/pipeline_provenance.py` | Shared provenance helpers for `id_mappings`/skip-list SHA-256, version, L3 vocab, GEE mapping counts, and report-only warning generation |
| `src/gis_recommend/data/step6_label_with_l3.py` | Step6 output now embeds provenance for the mapping and skip list used to label workflows |
| `src/gis_recommend/data/step7_prepare_v4_data.py` | Step7 preserves Step6 provenance while grafting task metadata |
| `src/gis_recommend/data/step8_clean_v4_data.py` | Step8 validates provenance against current mapping inputs before writing cleaned V4 data and records `provenance_validated` |
| `src/gis_recommend/data/pipeline_runner.py` | Passes selected `id_mappings` and `skip_list` through to Step8 so custom-output runs validate the intended inputs |
| `src/gis_recommend/training/splits.py` | Shared split validation/rebuild helpers for training and evaluation |
| `src/gis_recommend/training/train_v4_2.py` | Reuses existing split only when it exactly covers the current Step8 dataset; otherwise rebuilds deterministically |
| `src/gis_recommend/training/train_v4_6.py` | Inherits V4.2 split validation through shared `load_or_create_splits` |
| `src/gis_recommend/training/train_v4_6.py` | Fixes AR scheduled-sampling stability by keeping CE/early-END-penalty logits unmasked and applying dynamic minimum-length END blocking only to sampling logits |
| `src/gis_recommend/training/train_set_predictor_v3.py` | Uses the same split validation/rebuild logic as V4 transformer training |
| `src/gis_recommend/evaluation/sampling.py` | Validates `test_indices` before sampling so stale split files fail clearly instead of raising raw `IndexError` |
| `src/gis_recommend/data/training_data_quality.py` | Shared Step8 training-data quality audit for schema, L3 imbalance, task sparsity, split coverage, duplicates, confidence, and mapping-source risk |
| `src/gis_recommend/data/quality_gate.py` | Builds derived V4 quality-gate candidates, quarantines low-confidence `auto_remap` workflows, merges/filters sparse task types, creates grouped splits, writes reports, and audits GEE official-name aliases |
| `src/gis_recommend/models/transformer_model_v4.py` | V4 model now accepts `bert_model_name` and `bert_local_files_only` so smoke tests can verify local cached BERT loading without changing existing training defaults |
| `src/gis_recommend/models/transformer_model_v4.py` | Tightened pretrained embedding load path to `torch.load(..., weights_only=True)` |
| `src/gis_recommend/models/set_predictor_v3.py` | Set Predictor model now accepts `bert_model_name` and `bert_local_files_only`, preserving old defaults while allowing quality-gate training to use local cached BERT files by default |
| `src/gis_recommend/models/set_predictor_v3.py` | Phase 15C: Set Predictor checkpoint loading now requires supported wrapped payloads and reconstructs architecture only from `model_state_dict`, not snapshot `config` |
| `scripts/audit_training_data_quality.py` | CLI that writes `training_data_quality_audit.json/.md` without changing training data or running training |
| `scripts/build_v4_quality_gate_candidate.py` | CLI for generating `outputs_v2/pipeline/step8_quality_gate/` without overwriting Step8; also writes GEE alias audit from crawled official operators |
| `scripts/smoke_v4_quality_gate_training_entry.py` | Training-entry smoke CLI for quality-gated V4 data; loads candidate data/split/task vocab, initializes V4 with v2 vocab/embeddings, runs one forward pass, and intentionally does not create checkpoints |
| `scripts/train_v4_quality_gate.py` | Safe full-training launcher for quality-gated V4.2 runs; avoids original Step8 defaults by requiring/using explicit candidate data, candidate split, candidate task vocab, v2 embeddings, and a separate checkpoint directory |
| `scripts/build_quality_gate_transition_matrix.py` | Builds `outputs_v2/transition_allowed_next.json` from the quality-gated train split with v2 special-token ids and out-of-range token reporting |
| `scripts/train_set_predictor_quality_gate.py` | Safe full-training launcher for quality-gated Set Predictor V3 runs; avoids original Step8 defaults by requiring/using explicit candidate data, candidate split, candidate task vocab, active-token output, and a separate checkpoint directory |
| `scripts/project_l3_embeddings_v2.py` | Tightened legacy embedding payload read to `torch.load(..., weights_only=True)` |
| `scripts/audit_pipeline_outputs.py` | Audit reports provenance warnings; `--fail-on-warning` is retained as a compatibility flag but no longer exits non-zero |
| `tests/test_pipeline_provenance.py` | Covers Step6 provenance, Step7 pass-through, Step8 missing/stale provenance report-only warnings, audit warnings, and runner Step8 argument propagation |
| `tests/test_dataset_splits.py` | Covers invalid split rebuild and valid split reuse |
| `tests/test_evaluate_system_sampling.py` | Covers evaluation sampling split validation and partial test-split support |
| `tests/test_training_data_quality.py` | Covers case-insensitive operator metadata lookup and split/task/duplicate quality warnings |
| `tests/test_training_data_quality_gate.py` | Covers low-confidence `auto_remap` quarantine, sparse task merging, grouped split leakage prevention, separate output filenames, CLI behavior, and GEE alias audit |
| `tests/test_v4_training_entry_smoke.py` | Covers quality-gate smoke defaults, no-checkpoint one-batch forward behavior with test doubles, and local-only HuggingFace BERT loader propagation |
| `tests/test_v4_quality_gate_training_launcher.py` | Covers quality-gate launcher defaults, explicit split loading without rebuild, dry-run behavior that does not create checkpoint directories, and strict transition-matrix requirement for non-dry-run training |
| `tests/test_v4_6_training_stability.py` | Regression coverage for the AR-SS logits split: CE stays finite when the target is `END_INDEX` before dynamic min length, while sampling logits still block early END |
| `tests/test_quality_gate_transition_matrix.py` | Covers v2 transition-matrix generation from train split only, special-token conversion, out-of-range token exclusion, and default output path |
| `tests/test_set_predictor_quality_gate_training_launcher.py` | Covers Set Predictor quality-gate launcher defaults, explicit split loading, train-only active-token discovery, dry-run no-write behavior, and local-only HuggingFace BERT loader propagation |
| `tests/test_v2_defaults.py` | Covers v2 defaults, QGIS v2 loading, manual-reviewed retention, and stale-candidate avoidance |
| `tests/test_build_ontology_kg_paths.py` | Covers KG v2 hierarchy preference and workspace-local test temp directories |
| `src/gis_recommend/training/train_v3.py` | Removed metric-gated best-checkpoint/early-stop behavior in the legacy trainer; now saves latest snapshot each epoch and reloads latest with `weights_only=True` |
| `src/gis_recommend/training/train_v3.py` | Phase 15C: legacy warm-start/final reload requires supported wrapped checkpoint payloads; raw state dict fallback is removed |
| `src/gis_recommend/training/train_v4_3.py` | Phase 15C: warm-start requires an existing supported wrapped checkpoint payload; only `model_state_dict`/`task_classifier_state_dict` affect runtime |
| `src/gis_recommend/training/train_v4_4.py` | Phase 15C: warm-start requires an existing supported wrapped checkpoint payload and treats metric fields as display-only |
| `src/gis_recommend/training/train_v4_3_rl.py` | Removed reward-gated best-checkpoint/early-stop behavior; now saves latest snapshot each epoch |
| `src/gis_recommend/training/train_v4_3_rl.py` | Phase 15C: V4.3-RL warm-start now fails on missing, raw, or unsupported-schema checkpoints instead of falling back |
| `src/gis_recommend/knowledge_graph/train_graph_embeddings.py` | Removed val-loss-gated best-checkpoint/early-stop behavior; now saves `latest` snapshot each epoch and keeps periodic epoch snapshots |
| `src/gis_recommend/evidence/__init__.py` | Phase 15C: removed runtime-enforcement exports from the evidence package; it is snapshot/report-only and must stay out of runtime imports |
| `src/gis_recommend/evidence/_provenance.py` | Phase 15C: removed the advertised checkpoint loader gate; provenance helpers are observational only |
| `src/gis_recommend/evidence/_metric_bundle.py` | Phase 15C: removed metric-bundle validation authority; metric bundles are checkpoint/report snapshots only |
| `src/gis_recommend/evidence/_boundary.py` | Phase 15C: boundary metadata is report-only and `verify_import_boundary` no longer blocks execution |
| `src/gis_recommend/evidence/_schemas.py` | Fixed import ordering so snapshot schema stubs compile cleanly |
| `tests/test_reranker_evaluate_system.py` | Fixed broken `test_interactive_system_repair_is_report_only` assertion (removed undefined `summary` usage) |
| `tests/test_phase15c_runtime_contract.py` | Added regression coverage for wrapped checkpoint/schema-only loading and Set Predictor snapshot-config non-authority |
| `tests/test_chain_repair.py` | Updated report-only repair assertions so candidate mutation is rejected and suggestions stay in diagnostics |
| `docs/empirical_bottleneck_audit.md` | New empirical audit report quantifying quality-gate dataset structure, label entropy, ambiguity, transition-mask coverage, simple baselines, error-taxonomy evidence gaps, and experiment priorities |
| `src/gis_recommend/evaluation/empirical.py` | New empirical artifact builder for post-convergence bottleneck validation: dataset structure audit, retrieval/Markov baselines, per-sample prediction diagnostics, error taxonomy, canonicalization audit, decode-policy summaries, upper-bound proxy, and engineering bottleneck attribution |
| `src/gis_recommend/evaluation/empirical.py` | Added `attach_model_predictions_to_artifact` so V5_final prediction records can be stored in the existing empirical artifact shape without changing baseline predictions or gating runtime |
| `src/gis_recommend/models/v5_final/` | New isolated V5_final runtime package: config, PVM attention, IO mask, AR model, loss, strict checkpoint save/load, diagnostics, empirical record builder, and deterministic smoke task embeddings |
| `src/gis_recommend/training/train_v5.py` | Full V5_final training/evaluation engine with deterministic seeding/subsets, train/validation loops, gradient clipping, optional CUDA AMP, early stopping, best/latest checkpoints, IO-mask bias annealing, report-only stability/collapse diagnostics, evaluation reports, empirical model-prediction records, and ablation flags |
| `scripts/train_v5.py` | Thin CLI wrapper around `gis_recommend.training.train_v5`; supports real quality-gate dry-run validation, bounded smoke subsets, ablation flags, and controlled training options without introducing runtime governance objects; `--disable-pvm` is now an alias for the existing strict `--no-pvm` runtime flag |
| `scripts/evaluate_v5_beam_search.py` | Evaluation-only Stage1 checkpoint beam-search runner for beams 1/3/5/10, optional length-normalized candidate selection, beam oracle metrics, diversity statistics, and decode-trace artifacts; it loads strict V5 checkpoints and does not retrain or mutate checkpoints |
| `scripts/evaluate_v5_retrieval_assisted.py` | Minimal retrieval-assisted evaluation prototype: lexical top-3 retrieval from the train split, eval-time deterministic task-embedding text augmentation, generation-only/retrieval-only/retrieval-assisted metrics, and copied/novel operator attribution without new trainable modules |
| `scripts/evaluate_v5_hybrid_planner.py` | Retrieval-centered hybrid planner prototype: top-K lexical retrieval is the workflow-structure anchor, local expansion is limited to identity/substitution/insertion/removal <=1 edit with IO filtering, V5_final scores complete candidates only, and output artifacts include hybrid metrics, attribution, candidate traces, preservation metrics, and modification-rate statistics |
| `scripts/evaluate_v5_hybrid_planner.py` | Added multistage retrieval fusion: lexical, embedding, intent, workflow-structure, and graph-aware L2/L3-code sources; configurable source weights; safe retrieval-confidence rerank selection; contribution attribution; repair outcome aggregation; oracle comparison; and failure decomposition without model training or architecture changes |
| `scripts/evaluate_retrieval_planning_stages.py` | New retrieval-centered stage evaluator. It optionally strict-loads a Set Predictor checkpoint when available, otherwise records a train-split task-type set-prior fallback; filters retrieval candidates by operator-set overlap, reranks with execution-aware features, generates only local repair candidates, uses V5_final only as a complete-candidate scorer, and writes auditable JSON/Markdown reports without training or architecture changes |
| `scripts/evaluate_repair_oracle_phase.py` | New evaluation-only local repair oracle runner. It builds explicit repair candidate pools from retrieved identity workflows using only substitution, bridge insertion, deletion, and local swap; compares best repair, selected repair, identity retrieval, and retrieval-pool oracle; records per-candidate attribution and failure taxonomy; and keeps V5_final frozen as a candidate scorer only |
| `scripts/evaluate_repair_selection_diagnostics.py` | New evaluation-only diagnostic runner over existing repair oracle traces. It decomposes retrieval/execution/set/edit/V5/final score terms, measures identity bias, attributes oracle repair gaps, runs threshold sweeps and random modified-candidate controls, writes required reports, and performs forbidden-pattern scanning without model loading or training |
| `scripts/evaluate_repair_scorer_ablations.py` | New evaluation-only ablation runner over existing repair oracle traces. It re-scores candidate pools under alternate edit/retrieval/execution/set/V5 weights, compares adoption/corruption/metric gains, emits a quantitative scorer recommendation, and writes compact JSON/Markdown reports without checkpoint/model access |
| `scripts/evaluate_repair_calibration_sweep.py` | New evaluation-only calibration runner for uniform edit penalties. It consumes existing repair candidate traces, re-scores candidates without loading checkpoints, reports adoption/corruption/precision/breakage/identity preservation, bootstrap intervals, task/subset stability, CSV curves, Markdown summary, and forbidden-pattern scan |
| `scripts/evaluate_repair_opportunity_analysis.py` | New evaluation-only attribution runner over persisted repair traces. It measures retrieval ambiguity, IO inconsistency, set mismatch, structural anomaly, repair locality, heuristic opportunity indicators, failure taxonomy v2, bootstrap correlation intervals, and forbidden-pattern scan without loading checkpoints, training, or generating new candidates |
| `scripts/evaluate_repair_confidence_regimes.py` | New evaluation-only high-confidence regime runner over persisted repair traces. It flattens candidates, reports subtype/context statistics, searches runtime-safe precision-first repair subspaces, bootstraps candidate regimes, compares random controls, writes Markdown/JSON artifacts, and performs forbidden-pattern scanning without loading checkpoints, training, generating candidates, or changing production scoring |
| `scripts/build_unified_workflow_benchmark.py` | New artifact unifier for multi-task workflow planning benchmarks. It reads existing V5/hybrid reports, records user-reported V4 quality-gate and Set Predictor metrics when local histories are absent, writes JSON/Markdown, and separates task/prediction-mode/metric-scope/vocabulary rows so metrics are not cross-compared incorrectly |
| `scripts/train_v5_final_minimal.py` | Minimal V5_final training entrypoint with dry-run validation and one-step smoke training support; uses quality-gate defaults and writes strict V5 checkpoints only when not dry-run |
| `scripts/infer_v5_final_minimal.py` | Minimal V5_final inference entrypoint that loads strict V5 checkpoints and writes auditable prediction artifacts with decode/alpha traces and diagnostic graph |
| `configs/v5_final_train_minimal.json` | Minimal runnable V5_final training configuration documenting quality-gate paths, model constants, special-token ids, and runtime-boundary expectations |
| `configs/v5_final_inference_minimal.json` | Minimal runnable V5_final inference configuration documenting checkpoint path, transition matrix, beam/decode settings, and output artifact fields |
| `docs/v5_final_implementation_notes.md` | Implementation notes for the minimal V5_final runtime and execution-purity constraints |
| `docs/v5_final_migration_notes.md` | Migration notes for V4-to-V5 boundaries, strict checkpoint compatibility, empirical attachment, and v2 special-token mapping |
| `docs/v5_final_implementation_report.md` | Implementation report summarizing patch list, runtime contract, empirical outputs, verification, and remaining limits |
| `docs/v5_system_consolidation_protocol.md` | New project-level synthesis and consolidation protocol. It defines final system identity, final architecture semantics, capability hierarchy, failure synthesis, claim governance, production interpretation, and evidence requirements for reopening generation-centric or repair-deployment claims |
| `docs/v5_l2_semantic_recovery_protocol.md` | New semantic recovery protocol. It separates the current L3/operator-token runtime from the preserved L1->L2->L3 architecture target, defines why retrieval-centered planning still needs L2, and sets allowed/forbidden boundaries for future L2 recovery work |
| `scripts/evaluate_semantic_retrieval_stress.py` | New evaluation-only semantic perturbation stress runner. It creates deterministic paraphrase/synonym/alias/platform-wording/abstraction/word-order perturbations, reuses the existing lexical retrieval path, measures retrieval stability, overlap degradation, rerank/top1 robustness, candidate preservation, execution validity preservation, LCS/SetF1/token-accuracy degradation, lexical sensitivity, and writes JSON/Markdown/CSV artifacts without training, checkpoint access, semantic embeddings, or retrieval redesign |
| `tests/test_semantic_retrieval_stress.py` | Regression tests for perturbation-family construction, candidate-shift/degradation metrics, boundary-preserving summary aggregation, and script entrypoint execution |
| `scripts/evaluate_semantic_indexing_simulation.py` | New evaluation-only semantic indexing simulation. It applies predefined manual alias/intent buckets locally to retrieval scoring, compares lexical vs simulated grouped retrieval under the same perturbation families, and reports recall deltas separately from semantic drift, false equivalence, and execution-invalid grouping risk without training, checkpoint access, embedding models, LLM rewriting, or production semantic retrieval |
| `tests/test_semantic_indexing_simulation.py` | Regression tests for manual grouping terms, grouped-vs-lexical synthetic retrieval behavior, recall-vs-collapse attribution, summary claim boundaries, and script entrypoint execution |
| `scripts/evaluate_controlled_equivalence_stress.py` | New evaluation-only controlled equivalence stress runner. It builds alias, operator-family, workflow-variant, and GEE<->QGIS mapping stress classes from existing mappings/retrieval anchors, then reports retrieval preservation, false equivalence, execution-invalid equivalence, workflow corruption, topK retention, LCS/SetF1/token preservation, retrieval saturation change, taxonomy, safe/unsafe tables, and corruption traces without training, checkpoint mutation, vector search, or runtime changes |
| `tests/test_controlled_equivalence_stress.py` | Regression tests for exact cross-platform alias taxonomy, unsafe same-family substitution, outcome classification, summary metrics, and script entrypoint execution |
| `scripts/build_bounded_ontology_inventory.py` | New inventory/governance builder. It reads current v2 mappings, L3 hierarchy, QGIS IO metadata, and controlled equivalence findings; emits conservative mapping classifications, execution constraints, unsupported GDAL/ArcGIS rows, unsafe mapping registry, workflow-equivalence registry, Markdown summary, and forbidden-pattern scan without training, embeddings, semantic retrieval, ontology inference, or runtime changes |
| `tests/test_bounded_ontology_inventory.py` | Regression tests for exact mapping strictness, same-L2 non-equivalence, execution-sensitive classification, unsupported platform assets, unsafe registry preservation, narrow workflow equivalence registry, and script entrypoint execution |
| `docs/v5_bounded_ontology_inventory_protocol.md` | New protocol defining the bounded ontology inventory semantics, classification labels, execution constraints, unsupported-platform policy, unsafe mapping registry, workflow-equivalence boundary, and claim limits |
| `scripts/evaluate_canonicalized_metrics.py` | New strict evaluation-only canonicalized metric runner. It reads existing prediction artifacts, discovers commutative pairs from the quality-gate train split using the same logic as `compute_canonicalization_audit`, reuses `_canonicalize_sequence()`, compares raw vs canonicalized metrics, reports TopK/per-task/per-pair recovery and bootstrap intervals, and writes forbidden-pattern scan output without training, checkpoint access, retrieval redesign, semantic grouping, or architecture changes. |
| `tests/test_canonicalized_metrics.py` | Regression tests for commutative-pair exact recovery, empirical/hybrid artifact parsing, TopK canonical recovery, and clean forbidden-pattern scan behavior. |
| `scripts/evaluate_workflow_usability.py` | v1 reads persisted prediction artifacts for rule-based checking; v2 (rewritten 2026-05-13) is a self-contained evaluation pipeline that directly evaluates lexical retrieval baseline on quality-gate test data using L1/L2 hierarchy categories and QGIS mappings, requiring no model, no checkpoint, no training, no semantic retrieval, no LLM judging, and no execution simulation. |
| `tests/test_workflow_usability.py` | Regression tests for candidate usability rules, missing/harmful/unmapped failure taxonomy, TopK usable recovery accounting, QGIS mapping index construction from `primary_l3` and `all_candidates`, and clean forbidden-pattern scan behavior. |
| `scripts/evaluate_multi_reference_workflows.py` | New strict evaluation-only multi-reference workflow evaluator. It derives conservative alternate references only from exact normalized task text/name matches in existing labeled workflows, compares raw single-reference, best-of-multi-reference, and canonicalized multi-reference metrics, reports TopK usability deltas, workflow-family summaries, ambiguity taxonomy, recovered examples, and forbidden-pattern scan output without training, checkpoint mutation, semantic embeddings, LLM judging, retrieval redesign, or runtime changes. |
| `tests/test_multi_reference_workflows.py` | Regression tests for best-of-multi-reference recovery, canonicalized commutative recovery, exact task-text reference pooling, retrieval-vs-generation family deltas, ambiguity labels, and clean forbidden-pattern scan behavior. |
| `scripts/evaluate_multiref_validation.py` | Evaluation-only MRV runner. It generates local adjacent-swap variants from train-split commutative pairs, applies workflow-semantic gates (sensitive-step / semantic usability / non-degradation / length preservation), keeps QGIS mapping and QGIS-chain checks as auxiliary landing signals, writes auto-verified candidates, exports a readable `equivalence_review_packet.csv`, and creates a manual-only `verified_multi_reference_registry.json`; no training or checkpoint mutation. |
| `tests/test_multiref_validation_experiment.py` | Regression tests for adjacent-swap generation, sensitive guard behavior, semantic-usability gates, QGIS-landing decoupling, auto-label classification, registry eligibility, review-packet export, manual-only multi-reference registry construction, and stratified human-review sample construction. |
| `docs/superpowers/specs/2026-05-14-multiref-validation-design.md` | Design record for the MRV experiment and its boundary: validate data support for reliable multi-reference supervision before any training ablation. |
| `docs/superpowers/plans/2026-05-14-multiref-validation.md` | Implementation plan for the MRV runner, tests, smoke run, and context updates. |
| `outputs_v2/v4_qg_multiref_validation/equivalence_review_packet.csv` | Filled manual review fields for all 19 auto-verified MRV candidates, including `human_label`, execution-semantics notes, hidden drift notes, and review flags for CRS/mask/nodata/threshold/aggregation/temporal risks. |
| `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry.json` | Rebuilt as manual-only training-eligible registry: 7 task groups, 14 accepted equivalent variant sources, 4 uncertain variants excluded, and 1 not-equivalent variant excluded. |
| `outputs_v2/v4_qg_multiref_validation/multiref_validation_report.json` and `outputs_v2/v4_qg_multiref_validation/multiref_validation_summary.md` | Synced MRV report/summary counts with the completed manual review so future sessions do not inherit the old zero-reviewed-groups state. |
| `outputs_v2/v4_qg_multiref_validation/uncertain_deep_review.csv`, `.json`, `.md` | Source-inspection artifact for the 4 previously uncertain MRV candidates. Adds equivalence family, conditional constraints, hidden dependency, semantic risk, source operator window, and reviewer notes; no training labels or registry entries were added. |
| `outputs_v2/v4_qg_multiref_validation/equivalence_review_packet.csv` | Added deep-review fields (`source_script_id`, `source_operator_window`, `equivalence_family`, `deep_review_status`, `conditional_constraints`, `hidden_dependency`, `semantic_risk`, `reviewer_notes`) and downgraded `wf46_pos2_swap53_28` to `not_equivalent` after source inspection. |
| `configs/equivalence_taxonomy.yaml` | New MRV equivalence taxonomy config: token classes, family/risk definitions, conditional constraints, hidden dependencies, risk drivers, and rejection-type mapping. QGIS landing failures are explicitly auxiliary. |
| `scripts/analyze_mrv_expansion.py` | New read-only MRV expansion analyzer. It classifies generated variants into equivalence family/risk buckets, maps validator rejection reasons into a research rejection taxonomy, and writes CSV/JSON/Markdown analysis artifacts without changing labels, registry entries, checkpoints, or training data. |
| `tests/test_mrv_expansion_analysis.py` | Regression tests for taxonomy loading, pair classification, QGIS landing auxiliary mapping, and family/risk total conservation. |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/*analysis*`, `equivalence_family_summary.csv`, `risk_level_summary.csv`, `family_by_label_summary.csv`, `rejection_taxonomy_summary.csv`, `qgis_auxiliary_rejection_summary.csv` | 500-variant MRV expansion distribution artifacts for manual-review prioritization and equivalence-boundary analysis. These are auto-analysis outputs only, not training labels. |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/equivalence_review_packet_ai_review.csv` | AI-assisted review draft over the 46 auto candidates. Adds source script id, source operator window, review label, registry recommendation, drift flags, and reviewer notes without overwriting the original review packet. |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/equivalence_review_ai_summary.json/.md` | Summary of the AI-assisted 46-candidate review: 36 equivalent, 8 uncertain, 2 not equivalent, with per-candidate rationale and the deduplication warning for the original 19 vs expansion 46. |
| `outputs_v2/v4_qg_multiref_validation_expansion_500/verified_multi_reference_registry_ai_draft.json` | Non-training registry draft for user-confirmed promotion only: 19 groups / 36 equivalent draft variants. Do not use directly for training. |
| `scripts/build_mrv_registry_v2.py` | New consolidation builder for user-confirmed MRV review rows. It merges initial manual review and expansion review, deduplicates by `variant_id`, promotes only `equivalent` rows, preserves excluded variants, writes registry v2 plus equivalence KB v2, and keeps `review_flags` separate from normalized `risk_level`. |
| `tests/test_mrv_registry_builder.py` | Regression tests for token parsing, variant-id deduplication, excluded-row handling, manual review family/risk inference, and prevention of `review_flags` pollution in registry risk summaries. |
| `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json` | Formal user-confirmed MRV registry v2: 42 equivalent variants across 23 task groups; 13 uncertain/not-equivalent variants excluded. This is the controlled ablation input, not a command to retrain the main model. |
| `outputs_v2/v4_qg_multiref_validation/verified_equivalence_kb_v2.json/.csv` | Row-level equivalence KB v2 with one row per accepted variant, including source, family, risk, swapped pair, token sequences, constraints, hidden dependencies, review flags, and reviewer notes. |
| `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2_summary.md` | Human-readable summary of registry v2 counts, clean family/risk distributions, and all excluded variants. |
| `scripts/build_mrv_training_ablation.py` | New controlled MR ablation data builder. It reads quality-gate workflows/splits/task vocab plus verified MRV registry v2 / KB v2, selects deterministic verified-MR subsets without oversampling, appends them to train only, copies task vocab, writes reports/summaries/manifest, and records per-row MRV provenance without starting training. |
| `tests/test_mrv_training_ablation.py` | Regression tests for train-only injection, provenance fields, excluded-row rejection, subset-size oversampling guard, isolated CLI output, input preservation, and list-form `id_to_code` vocabulary support. |
| `outputs_v2/v4_qg_mr_ablation/` | Isolated derived ablation data root with `mr_5`, `mr_10`, `mr_all_42`, per-version reports/summaries, copied task vocab, and `mrv_training_ablation_manifest.json`. Main quality-gate data and checkpoint paths are untouched. |
| `scripts/compare_mrv_training_ablation.py` | New read-only comparator for future MR ablation reports. It accepts a baseline report plus repeated `NAME=PATH` variant reports, optionally reads the ablation manifest for counts/no-training status, extracts known metric keys from heterogeneous report schemas, computes deltas/relative deltas and paired bootstrap CIs when possible, and writes JSON/Markdown summaries. |
| `tests/test_mrv_ablation_comparator.py` | Regression tests for metric extraction/delta computation, missing-metric warnings, paired bootstrap CI generation, manifest count attachment, and CLI artifact writing. |
| `tests/test_v5_training_system.py` | Regression tests for IO-mask annealing, soft training masks, deterministic subset selection, report-only collapse detection, ablation flags, warning-clean smoke training, full training checkpoint/report output, and full-engine CLI dry-run |
| `tests/test_v5_final_runtime.py` | Contract tests for V5_final shape invariants, alpha behavior, IO legality, decode, checkpoint strictness, loss purity, diagnostics, and empirical attachment |
| `tests/test_v5_final_entrypoints.py` | Entry-point tests for V5_final dry-run training validation and inference artifact writing |
| `tests/test_v5_empirical_experiment_scripts.py` | Regression tests for beam oracle/diversity metrics, optional length-normalized selection, retrieval-assisted copied/novel attribution, retrieval-conditioning text, hybrid candidate expansion/scoring/preservation/top-k helpers, and direct script entrypoint execution |
| `tests/test_retrieval_planning_stages.py` | Regression tests for operator-set retrieval filtering, filtering pool metrics, strictly local repair candidates, repair outcome summaries, execution-aware rerank feature priority, contribution-channel separation, and direct script entrypoint execution |
| `tests/test_repair_oracle_phase.py` | Regression tests for controlled local edit candidate generation, repair attribution deltas, oracle repair win/selection-failure separation, failure taxonomy classification, candidate win/corruption aggregation, and direct script entrypoint execution |
| `tests/test_repair_selection_diagnostics.py` | Regression tests for score decomposition, modified-candidate suppressor identification, identity-bias metrics, oracle-gap classification, threshold sweeps, random modified-candidate control, and direct script entrypoint execution |
| `tests/test_repair_scorer_ablations.py` | Regression tests for no-edit promotion behavior, piecewise operation penalties, ablation gain/corruption/oracle-ceiling summaries, low-corruption policy recommendation, and direct script entrypoint execution |
| `tests/test_repair_calibration_sweep.py` | Regression tests for calibration metrics, bootstrap interval presence, region classification, artifact writing, and direct script entrypoint execution |
| `tests/test_repair_opportunity_analysis.py` | Regression tests for repair opportunity signal extraction, precision/recall/corruption indicator summaries, weak/unstable signal cautions, artifact writing, and direct script entrypoint execution |
| `tests/test_repair_confidence_regimes.py` | Regression tests for repair subtype/context extraction, subtype gain/corruption separation, precision-first regime reporting, random controls, artifact writing, and direct script entrypoint execution |
| `tests/test_unified_workflow_benchmark.py` | Regression tests for unified benchmark row typing, comparison-group separation, required benchmark-family coverage, and direct script entrypoint execution |
| `scripts/build_empirical_evaluation_artifact.py` | Thin CLI wrapper for generating `gis_recommend.empirical_evaluation.v1` artifacts without training or model execution |
| `tests/test_empirical_evaluation.py` | Regression coverage for error taxonomy, canonicalization audit, required artifact diagnostics, engineering attribution fields, and deterministic retrieval tie ordering |
| `pyproject.toml` | Added `gis-empirical-evaluate` console script pointing to the empirical artifact builder |
| `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json` | Generated 20-sample baseline-only empirical smoke artifact for the quality-gate split |
| `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.md` | Generated compact engineering report summarizing baseline metrics, top error categories, bottleneck attribution, and next benchmark suite |
| `docs/PROJECT_CONTEXT.md` | Durable handoff/context document for future sessions; added "Current Scientific Consensus" synthesis section (2026-05-10) consolidating all empirical findings, benchmark governance, attribution boundaries, and future continuation instructions |
| `docs/PROJECT_CONTEXT.zh-CN.md` | Chinese human-facing mirror of the durable handoff/context document; added "当前科学共识" synthesis section (2026-05-10) |
| `src/gis_recommend/evaluation/run_contract.py` | New Step8 + V4.6 mainline run contract: token profile, data authority manifest, repair capability level, selection policy, and L2 role for report-time interpretation. |
| `src/gis_recommend/evaluation/semantic_metrics.py` | Mainline sequence metrics now strip Step8 negative specials and V4.6 internal specials through the active token profile instead of assuming legacy 350-L3 control ids. |
| `src/gis_recommend/evaluation/report.py` | `build_report_json()` can embed run-contract metadata and per-sample decision traces separating decision features, diagnostics, hard constraints, and posthoc metrics. |
| `src/gis_recommend/evaluation/runner.py` | `gis-evaluate` now builds the mainline run contract, passes the token profile to semantic metrics, passes v2 I/O metadata authority to the verifier/executable diagnostics, and exposes explicit `--io-types` / `--allow-legacy-io-types` flags. |
| `src/gis_recommend/reranking/reranker_verifier.py` | `CandidateVerifier` now defaults to the mainline data authority; missing `outputs_v2/qgis_operator_io_types.json` yields neutral/missing I/O diagnostics instead of silently loading legacy `outputs/`. |
| `src/gis_recommend/operators/qgis_candidate_generator.py` | `QGISCandidateGenerator` now accepts `run_contract` / explicit `io_types_path`, resolves I/O metadata through the same data authority as mainline verifier/report, and records `score_components` so `qgis_score` is not an opaque decision signal. |
| `src/gis_recommend/evaluation/reranker_pipeline.py` | Posthoc QGIS evaluation now passes the active run contract into `QGISCandidateGenerator`, keeping QGIS landing diagnostics on the same metadata authority as the mainline run. |
| `src/gis_recommend/evaluation/report.py` | Per-sample reports and decision traces now include `qgis_score_components` when a reranker-selected QGIS candidate provides them. |
| `scripts/evaluate_v4_quality_gate.py` | V4-QG evaluation report and five-tier metrics now set `system_lineage=research`, `mainline_eligible=False`, and `v4_6_quality_gate_candidate` model profile; CLI/docstrings say candidate/research instead of mainline. |
| `src/gis_recommend/config/transformer_config.py` | Quality-gate config comments now call V4-QG a candidate/research profile and explicitly state it does not replace Step8 + V4.6 `gis-evaluate` mainline. |
| `scripts/run_v4_qg_planner.py` | Report governance now marks V4-QG planner artifacts as research/non-mainline, avoiding confusion with Step8 + V4.6 `gis-evaluate` reports. |
| `scripts/evaluate_v5_hybrid_planner.py` | V5 hybrid reports now include lineage/mainline eligibility metadata marking them as research artifacts. |
| `scripts/evaluate_retrieval_planning_stages.py` | Retrieval-stage reports now include lineage/mainline eligibility metadata marking them as research diagnostics. |
| `tests/test_mainline_run_contract.py` | Regression coverage for v2 token stripping, legacy token profile compatibility, report contract metadata, and verifier I/O metadata default behavior. |
| `tests/test_qgis_candidate_generator_logging.py` | Regression coverage that generated QGIS candidates expose score components for decision traces. |
| `tests/test_v4_qg_evaluation_report.py` | Regression coverage that V4-QG five-tier reports are machine-readable research/non-mainline artifacts. |
| `src/gis_recommend/evaluation/run_contract.py` | Adds Phase0/Phase1 status fields (`candidate_pool_enabled`, `decision_core_mode`, `retrieval_mode`, `l2_authority`) to the report contract only. |
| `src/gis_recommend/evaluation/shadow_phase.py` | New report-only helpers for candidate pool traces, evidence bundles, shadow decision summaries, and lexical train-split retrieval shadow pools. These helpers do not mutate legacy selection. |
| `src/gis_recommend/evaluation/report.py` | Emits `candidate_pool_trace`, `evidence_bundle`, and `decision_trace.shadow_decision_core` per sample while preserving existing legacy metrics and selected tokens. |
| `src/gis_recommend/evaluation/runner.py` | Adds optional `--retrieval-shadow-k` to attach train-split lexical retrieval shadow candidates for reporting; default is off and it does not alter inference/reranker selection. |
| `tests/test_mainline_shadow_phase.py` | Covers contract status fields, candidate pool trace inclusion of legacy selection, evidence missing/degraded semantics, shadow decision output, and train-only retrieval shadow behavior. |

## Known Pitfalls

| Pitfall | Do Not Repeat |
| --- | --- |
| Confusing raw route outputs, deduplicated candidates, and train-package rows | Phase 9 has multiple valid counts. `vector_training_samples_llm_FULL.jsonl` is a raw description-to-L3 output (19,738 local lines), `API_trace_to_L3_TRAINING_FINAL.jsonl` is a deduplicated API-trace merge (6,031 lines), and `_final_merge.py` reports about 16,800 by adding 6,031 API-trace samples to 10,768 unified Route 1+2 samples. Do not report "16,800" without saying this is the merged candidate-data count, not necessarily the final training package row count. |
| Letting temporary LLM/API keys enter project files | Project convention is env-only (`DEEPSEEK_API_KEY` / `LLM_API_KEY`) and no key material in scripts, progress logs, or helper `.bat` files. `run_process.bat` and `progress.md` were sanitized on 2026-06-24. Local generated caches such as `.codegraph/codegraph.db` may still contain indexed historical/crawled strings; do not share them as project artifacts without regenerating or excluding them. |
| Treating QGIS facts self-retrieval as open-ended user accuracy | The 100%/99% recall numbers are source-file-level self-retrieval after `facts_summary` text was indexed. They prove the index is repaired and task text is informative, not that arbitrary user prompts will retrieve the correct QGIS chain with 100% semantic accuracy. |
| Confusing QGIS landing improvement with vector planning ability | Better QGIS retrieval diversity, semantic tags, or modality match do not by themselves prove the small model has learned vector processing planning. Use QGIS workflow data to define/evaluate vector intents and bridge to executable chains, but keep the primary claim on vector step planning quality. |
| Mixing QGIS dataset versions as if they contain the same fields | `qgis_chain_dataset.jsonl` has many L3 bridge rows and semantic tags but noisy task text; `qgis_chain_dataset_v2_enriched_v3.jsonl` has facts text and semantic tags but no L3 bridge; `qgis_vector_chain_candidates.jsonl` has clean vector modality and some bridge rows but no task text; `qgis_vector_chain_described.jsonl` adds weak generated descriptions. Choose the version by task or build a canonical merged dataset first. |
| Miscounting full-L3 rows in the canonical vector planning dataset | `outputs_v2/canonical_vector_planning_dataset.jsonl` has 1,046 full-L3 records across all modalities, not 1,046 pure-vector full-L3 records. The pure-vector full-L3 subset is 733; the pure-vector total is 1,598. Keep these scopes separate when building SFT/preference splits or reporting training volume. |
| Treating `has_full_l3=true` as vocabulary-clean | `has_full_l3` currently means no blank L3 slots, not "all L3 codes exist in `classification_hierarchy_v2.csv`". 140 rows contain `L3_02_05_04`, including 45 pure-vector full-L3 rows; the current 94-L3 vocabulary has `L3_02_05_11` for Feature to Point / centroid-like conversion but no `L3_02_05_04`. Fix or filter this before SFT. |
| Training the full canonical vector dataset without quality filters | The full 2,319 rows are useful for weak supervision, coverage mining, and bridge repair, but not clean SFT as-is. Immediate SFT should use the strict pure-vector valid subset (currently 610 rows under the audited filters) or a corrected/remapped variant that is revalidated. |
| Treating the 685 clean SFT seed as universally fine-grained semantic truth | The overlay/centroid coarse bug is fixed in `outputs_v2/canonical_vector_clean_sft_seed.jsonl`: intersection/difference/union/symdiff/clip now use distinct current-vocab L3 codes and `L3_02_05_04` is gone. Remaining labels still rely on current taxonomy granularity: geometry repair/validation/simplify/delete-holes share `L3_02_07_01`, and raster sampling/rasterize/polygonize share `L3_03_01_01`. This is acceptable for coarse-family SFT under the current 94-L3 contract, but not proof of fully fine-grained operator semantics. |
| Assuming the QGIS Step8 package automatically gives 5:1 mixed training | `outputs_v2/pipeline/step8_qgis_vector_sft/` is Step8-compatible and can be read by existing single-dataset launchers, but current launchers do not implement "every 5 GEE batches insert 1 QGIS batch". Mixed training still needs either a merged weighted dataset, a custom two-loader/batch mixer, or an explicit sampler strategy. |
| Treating the merged package's 1.1% QGIS train share as the proposed 5:1 schedule | `outputs_v2/pipeline/step8_quality_gate_qgis_vector/` injects all 685 QGIS samples into the 62,180-row train split, so QGIS is only 1.1% of train. That is a conservative domain hint, not the earlier GEE:QGIS=5:1 batch ratio. |
| Mixing the QGIS-only task vocabulary directly with GEE data | The QGIS SFT package uses a local task vocabulary with only `"Vector Analysis": 0`. A real mixed GEE+QGIS run needs a combined task vocabulary and stable id assignment, otherwise task-type ids will collide or silently change semantics. |
| Warm-starting the 48-task merged package from current 47-task checkpoints without adaptation | Existing quality-gate and DPO v2 checkpoints have `task_type_embedding.weight` shape `[47, 256]` and task classifier shape `[47, ...]`. Current `load_warmstart_checkpoint()` uses strict `model.load_state_dict(...)`, so `--warmstart` into the merged 48-task model fails unless task-type-specific weights are skipped or expanded and the new `"Vector Analysis"` row is initialized deliberately. |
| Comparing the 5-epoch from-scratch and 5-epoch warmstart runs as equal training regimes | They are not equivalent. With explicit `--num-epochs`, the launcher sets `tf_phase_epochs=10` for from-scratch, so a 5-epoch from-scratch run is TF-only. Warmstart sets `tf_phase_epochs=0`, so a 5-epoch warmstart run is AR scheduled-sampling from epoch 1. Use the from-scratch 5-epoch result only as infrastructure smoke, not as a fair capability baseline. |
| Reusing the same checkpoint directory for different route experiments | The server smoke used `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector` for both from-scratch and warmstart. The second run overwrites `best_model.pth`, `latest_model.pth`, history, and selection manifests. Use separate directories such as `_scratch5` and `_warmstart5` for future comparisons. |
| Treating `evaluate_sft_vector_impact.py` as a held-out vector capability benchmark | The script is a signal-absorption smoke. It compares 50 GEE test tasks against 50 sampled rows from `canonical_vector_clean_sft_seed.jsonl`, which are train-source QGIS seed records. A high QGIS strict-vector rate proves the SFT signal was absorbed; it does not prove open-set vector-planning semantic correctness. Also, the DPO QGIS baseline uses the 47-task vocab without `"Vector Analysis"`, so QGIS delta includes the new task-type embedding effect. |
| Treating `configs/unseen_vector_prompts.jsonl` as the stated 55/8/7 split | The current file has 70 rows but actually splits as 61 vector / 6 mixed / 3 raster. This is still useful as a held-out prompt benchmark, but any report must print/use the actual counts unless the prompt file is relabeled or expanded. |
| Reading unseen expected-family recall as fully fine-grained QGIS semantic accuracy | Many prompt families are outside the current 94-L3 measurable taxonomy, e.g. nearest/tessellation/density/random sampling/concave hull/triangulation/rasterize/polygonize/raster sampling/contour/gap fill. Use the script's measurable recall for current-vocab evaluation and strict/all recall as a lower-bound pressure signal; do not treat unsupported families as model failures without first extending the L3/QGIS mapping. |
| Treating high SFT vector-token rate as solved vector planning | The unseen benchmark shows a real modality shift but not solved semantics. SFT produces many vector tokens on vector prompts, yet recall is concentrated in `spatial_filter`, `spatial_join/table_join`, `buffer`, and `merge`; many core families remain 0-hit. Report this as vector-regime acquisition plus partial family recall, not as complete QGIS vector planning capability. |
| Passing `--lr` to `scripts/train_v4_6_quality_gate.py` | The V4.6 quality-gate launcher has no `--lr` CLI argument; it uses internal `V4_6_BERT_LR` / `V4_6_OTHER_LR` constants. The proposed command with `--lr 1e-5` fails argument parsing unless the launcher is extended. |
| Ignoring QGIS/mixed length stats in V4.6 | Training should pass `outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_length_stats.json` for the merged package. V4 inference now also accepts an explicit `length_stats_path`; use it for mixed 48-task checkpoints so `"Vector Analysis"` does not fall back to the default 47-task quality-gate stats. |
| Training the oversampled package without its own length stats | `outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/` now has its own `task_type_length_stats.json`. If this is omitted, `scripts/train_v4_6_quality_gate.py` falls back to the original quality-gate 47-task stats, so the new `"Vector Analysis"` length prior is not aligned with the 4,253-row QGIS mix. |
| Evaluating an oversampled SFT checkpoint with hardcoded v1 paths | `scripts/evaluate_vector_generalization.py` and `scripts/evaluate_sft_vector_impact.py` default to the conservative v1 SFT checkpoint/package for backward compatibility. For v2 oversampled evaluation, pass `--sft-checkpoint`, `--sft-task-vocab`, `--sft-length-stats`, and preferably a separate `--report-path`; otherwise the script will evaluate the old model and may overwrite the old report. |
| Reusing stale open-landing audit counts | The current local `open_landing_results.csv` parses as A=18 / B=33 / C=29 with improved template concentration. Earlier A=2 / B=23 / C=55 counts are historical evidence from a previous audit state unless that exact file snapshot is restored. |
| Treating GRPO as the next training step after vector weakness | GRPO headroom on 100 vector prompts found 0% worth-training cases and mean gap 0.031 because current DPO beam candidates are too similar. Do not start GRPO unless a later headroom run shows strong diverse candidates with reliable reward separation. |
| Treating QGIS reranker as solving retrieval coverage | The reranker can rank correctly when the gold/similar chain is already in the pool, but it cannot recover chains missing from retrieval. Use it after retrieval recall is healthy; do not use high pool-internal Top-1 as end-to-end accuracy. |
| Trusting old logs | `outputs_v2/_step6_final.log` is stale and reports 556 GEE mappings / 62 skip; current truth is 551 / 67 |
| Assuming `all_candidates[0]` is always authoritative | v2 manual overrides may update top-level `primary_l3` while leaving old candidate lists |
| Filtering manual-reviewed QGIS mappings by numeric confidence | Some reviewed keeps have low old confidence, e.g. `Write Vector Tiles_mbtiles` at 0.1944 |
| Treating QGIS mappings as Step1-8 training input | Step1-8 training chain uses GEE -> L3; QGIS is for L3 -> QGIS landing/evaluation |
| Assuming all scripts now use v2 | Some non-primary scripts still hardcode `classification_hierarchy.csv` or `outputs/l3_embeddings.pt` |
| Treating old V4.6 AR-SS `loss=inf` logs as MR label evidence | The identified root cause was trainer-side dynamic-min-length END masking polluting CE logits. Old `mr_all_42` logs are pre-fix stability evidence; rerun baseline and MR arms before comparing MR impact. |
| Treating pre-2026-05-21 Step8 + V4.6 sequence reports as token-contract clean | The metric bug is now fixed in code, but old reports may have counted Step8 negative specials or V4.6 internal specials inconsistently. Recompute or annotate historical LCS/token accuracy/SetF1/SeqEM before using them for checkpoint or ablation conclusions. |
| Treating V4.6 `repair` as applied runtime repair | In `gis-evaluate --use-repair --use-reranker`, repair writes `repair_candidate_chain` and diagnostics but leaves `repair_applied=False`, `changed_chain=False`, and `repair_stats.applied=0`. Describe it as report-only repair suggestion, not a mutating repair loop. |
| Treating execution-aware diagnostics as stable selection authority | `StructuredReranker` and `TwoStageReranker` currently score/prune on direct candidate/model/set/length/unknown features; validation and I/O compatibility are extracted/reportable but are not hard decision authorities in the Step8 + V4.6 mainline. |
| Treating `qgis_score_components` as a hard constraint trace | `qgis_score_components` explains the aggregate `qgis_score` inputs from QGIS candidate generation, including mapping scores and I/O factors. It is decision evidence only when the reranker actually selects from QGIS candidates; posthoc QGIS/executable diagnostics remain labeled diagnostics. |
| Assuming missing v2 QGIS I/O metadata means legacy metadata was used | `CandidateVerifier` now defaults to `outputs_v2/qgis_operator_io_types.json` and reports `fallback_status=missing` when absent. Legacy `outputs/qgis_operator_io_types.json` is only allowed through an explicit compatibility profile and makes the run non-mainline-eligible. |
| Reading `mainline_eligible=True` as data completeness | It only means the run did not enter a disallowed legacy profile. It does not mean optional assets such as `outputs_v2/qgis_operator_io_types.json` exist; check `io_metadata_profile.fallback_status` before interpreting I/O/executable diagnostics. |
| Running old Neo4j KG import commands | The old KG scripts could clear Neo4j by default and silently mix legacy 350-L3 paths. Use the current `scripts/build_ontology_kg.py` CLI with explicit credentials and `outputs_v2` defaults; add `--clear` only for intentional clean rebuilds. |
| Treating shadow decision or retrieval shadow as runtime selection | Phase0/Phase1 shadow output is report-only. `decision_trace.shadow_decision_core.shadow_selection` and `retrieval_shadow_pool` must not be used to replace `l3_res["pred_tokens"]`, reranker top-1, beam order, or legacy metrics without a Phase2+ contract change. |
| Relying on Git diff in `system_redesign` | This directory is not currently a Git repository root in this environment |
| Using `rg` in this environment | `rg` was not available; use PowerShell `Get-ChildItem` and `Select-String` |
| Treating current `outputs_v2` Step6-8 artifacts as provenance-clean | They were generated before the 2026-05-07 provenance gate and now audit as `missing_provenance`; regenerate Step6-8 or intentionally accept old artifacts for read-only analysis |
| Reusing `dataset_splits_v4.json` only because it exists | Existing split files may target a pre-cleaning workflow count; validate range/coverage before training |
| Treating a structurally clean Step8 file as model-quality clean | Current Step8 has no schema/mapping/skip leaks, but still has strong L3/task imbalance, low-confidence auto-remap pockets, and split design issues that can explain poor model results |
| Treating `task_type` as harmless metadata | V4 uses task-type embeddings and task-classification auxiliary loss, so 1-sample task types and val/test-only task types directly affect training and evaluation |
| Treating lowercase GEE operators as official API names | Step4 lowercases operators and Step6 matches case-insensitively. This is fine for GEE->L3 labels, but official API/code generation needs canonical aliases from the crawled `gee_operators.json` `name`/`code_examples`, especially for nested APIs like `ee.Algorithms.Landsat.simpleComposite` or `ee.Algorithms.Image.Segmentation.SNIC` |
| Assuming the quality-gated candidate fixes all model risk | It fixes split leakage, sparse task gaps, and the largest low-confidence `auto_remap` noise, but active L3 drops to 47/94 and Top20 token share rises to 94.77%; training still needs imbalance handling or reviewed quarantine reintegration |
| Confusing old `task_conditioned_checkpoints_v3*` with the current full-system path | The current quality-gate flow uses V4 Transformer checkpoints plus optional Set Predictor checkpoints. Old `task_conditioned_checkpoints_v3*` are legacy/reference artifacts, while `train_set_predictor_v3.py` still defaults to original Step8 unless the new quality-gate launcher is used |
| Copying old transition matrix into v2 | `outputs/transition_allowed_next.json` is from the legacy 350-L3 setup and contains ids outside v2 `TOTAL_VOCAB_SIZE=98`; copying it to `outputs_v2` can crash transition loss or encode invalid transitions. Rebuild via `scripts/build_quality_gate_transition_matrix.py` |
| Expanding V5 governance objects into runtime controllers | The only valid authority test is whether deleting the object changes runtime-observable behavior. Runtime execution may emit snapshots for validation/tooling, but snapshots, manifests, metric ontology, compatibility results, dataset lineage, and reports must not mutate trainer, inferencer, loader, optimizer, sampler, checkpoint selection, or decode semantics |
| Treating provenance, audit warnings, validation, or metric bundles as execution gates | In the strict execution-only contract, these are interpretive outputs. They may be recorded or reported, but they must not decide data loading, checkpoint loading, decode behavior, chain repair, reranker selection, or process success/failure for runtime execution |
| Reintroducing partial checkpoint loading | `strict=False`, raw state-dict fallback, and `allow_partial_load`-driven behavior are forbidden for active runtime paths. Only supported wrapped checkpoints may load, and only `model_state_dict` plus direct runtime config can affect execution. |
| Treating old `outputs/evaluation_reports` as current v2 evidence | Those reports point to legacy `outputs/` 350-L3 checkpoints such as `outputs/transformer_checkpoints_v4_6/best_model.pth`. They can be historical warnings only; current v2/quality-gate conclusions need `outputs_v2` evaluation artifacts. |
| Treating the empirical smoke artifact as a model result | `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.*` is baseline-only and records `model_predictions_run=False`. Use it as the artifact schema and baseline evidence, not as V4/V5 model performance. |
| Assuming the transition matrix is a strong oracle | The quality-gate train transition mask covers 99.9575% of test transitions but has weighted average outdegree 40.91 over 48 states, so it is highly permissive and cannot explain global workflow correctness. |
| Reading zero exact-match baselines as pure model failure | Grouped quality-gate splits intentionally remove cross-split exact sequence leakage; exact-match-heavy evaluation is brittle because broad task types have very high sequence entropy and many valid sequence variants. |
| Treating the V5_final implementation as a trained model result | The new V5_final path is runtime/instrumentation only. No controlled V5_final checkpoint has been trained, and smoke task embeddings exist only to exercise entrypoints without network downloads. |
| Loading V4 checkpoints through the V5_final loader | V5_final loader rejects raw, V4, or missing-PVM payloads. Any V4 warm-start must be an explicit future utility, not loader fallback. |
| Letting stability or collapse reports steer execution | V5_final collapse indicators are deliberately report-only. They must not change optimizer behavior, checkpoint selection, decode ranking, dataset selection, or loader fallback. |
| Treating semantic perturbation brittleness as L2 validation | The semantic retrieval stress artifact shows lexical/operator-level retrieval can degrade under abstraction/paraphrase. This supports studying semantic indexing, but it does not prove L2 works, does not implement semantic retrieval, and must not be used to relabel operator-level failures as correct. |
| Treating coarse semantic grouping as safe semantic indexing | The semantic indexing simulation found net-negative recall/preservation deltas and high false-equivalence/drift risk for broad manual buckets. This does not disprove L2, but it blocks any claim that coarse alias/intent grouping is deployment-ready. Future semantic indexing needs narrower pre-defined equivalence classes and must prove recall gain without unsafe collapse. |
| Treating same-family or workflow-shape variants as safe equivalence | Controlled equivalence stress shows only exact aliases and exact unambiguous GEE<->QGIS mappings are currently stable/safe in this diagnostic. Same-L2 substitutions, adjacent reorder, bridge expansion, and ambiguous/composite mappings must remain unsafe or ambiguous unless future evidence proves execution-preserving equivalence independently. |
| Treating the bounded ontology inventory as deployed semantic retrieval | The bounded inventory is offline governance only. Its 13 exact rows are conservative candidates, not active runtime rules; partial/execution-sensitive/ambiguous/composite rows must not be used as equivalence, and GDAL/ArcGIS rows are unsupported because no current mapping assets exist. |
| Treating the retrieval-stage set prior fallback as the trained Set Predictor | `outputs_v2/set_predictor_checkpoints_v3_quality_gate/best_model.pth` is absent locally. `evaluate_retrieval_planning_stages.py` can strict-load it when supplied, but current reports use a train-split task-type operator-frequency prior and mark that source explicitly. |
| Assuming the current V4 evaluation CLI is quality-gate aligned by default | `scripts/train_v4_quality_gate.py` and `scripts/train_set_predictor_quality_gate.py` are aligned to `step8_quality_gate`, but `src/gis_recommend/evaluation/runner.py`, `src/gis_recommend/evaluation/sampling.py`, `src/gis_recommend/evaluation/reranker_pipeline.py`, and `src/gis_recommend/inference/infer_l3_candidates_v4.py` still default to legacy Step8 / `dataset_splits_v4.json` / V4.6 checkpoint paths unless explicit paths or a reconciliation wrapper are used. |
| Confusing `mr_5` / `mr_10` with percentage injection | The current ablation artifacts inject 5 or 10 verified variants as deterministic subset counts, not 5% or 10% of the train split. Actual train injection rates are tiny (5/61,495 and 10/61,495); if a true percentage-based augmentation is desired, it must be explicitly designed without oversampling or leakage. |
| Assuming MR ablation artifacts imply training has happened | `outputs_v2/v4_qg_mr_ablation/` contains derived input datasets only. The manifest records `no_training_started=true`; do not claim model impact until separate checkpoints are trained and compared against the quality-gate baseline. |
| Treating the MR ablation comparator as an evaluator | `scripts/compare_mrv_training_ablation.py` only compares existing reports. It does not run model inference, generate predictions, compute usability from raw candidates, or train checkpoints. If a metric is absent from input reports, it is reported as missing rather than silently zeroed. |
| Treating the `mr_all_42` training log as evidence that MR labels hurt | The run is confounded by V4.6 AR scheduled-sampling instability (`Train: Loss=inf` from epoch 11 onward), latest-snapshot test evaluation at epoch 50, and absence of a same-trainer same-policy V4.6 quality-gate baseline control. It currently diagnoses training/evaluation protocol issues more strongly than MR label quality. |
| Starting local full MR training without checking hardware | The current local workspace is CPU-only and has no baseline/MR checkpoints. Training should run on the user's server/GPU; local work should resume only after server checkpoints/reports are copied back. |
| Reading local repair `modified_selection_rate=0` as proof repairs are useless | The repair oracle phase shows non-identity repairs often improve the retrieved identity under oracle selection. The current blocker is primarily scorer/reranker recognition of useful repairs, not necessarily absence of useful local edits. |
| Treating oracle repair gain as permission for broad repair acceptance | Repair selection diagnostics show random modified-candidate selection is harmful and even aggressive score-margin acceptance has tiny net LCS gain. Useful repairs exist, but acceptance needs calibrated scorer changes and attribution, not random or unconditional local edits. |
| Removing edit penalty entirely | Repair scorer ablations show no-edit-penalty adopts every modified repair but degrades mean LCS and has 32% corruption. Edit penalty is over-strong at 0.20, but it is still necessary as a safety term; test bounded reductions instead of deleting it. |
| Promoting the 50-sample `uniform_edit_0_12` result | The larger 200-sample calibration sweep did not confirm the 50-sample positive signal. `uniform_edit_0_12` has mean LCS -0.00111538 and a bootstrap interval crossing zero, while lower penalties over-adopt and no-penalty collapses. Do not productionize uniform penalty changes from the 50-sample result. |
| Turning broad repair opportunity indicators into runtime gates | The 200-sample opportunity analysis shows broad indicators such as high retrieval ambiguity and set-deficit/length anomaly trigger 100% of samples and are not discriminative. IO-validity/transition signals are also flat in this trace. Use these only as report-only diagnostics until narrower, stable confidence features are validated. |
| Treating oracle-only confidence regimes as deployable repair policy | The confidence-regime phase found 12 oracle-only subspaces but 0 score-selected high-confidence regimes. Oracle-only subspaces prove candidate existence, not selection quality; they must not become runtime gates or scorer changes without a score-selected policy that passes corruption and bootstrap criteria. |
| Treating the consolidation protocol as a new architecture | `docs/v5_system_consolidation_protocol.md` is a synthesis and claim-boundary reference only. It does not authorize new runtime modules, new losses, graph learning, autonomous generation claims, or repair deployment. |
| Treating workflow usability proxies as QGIS execution proof | The v2 script (`scripts/evaluate_workflow_usability.py`) uses strict rule-based token checks only: task-critical coverage, harmful/missing tokens, QGIS mapping coverage, basic order/length/redundancy sanity. Even at Top-1 usable rate 56% / Top-3 100%, it does not run QGIS, infer semantic equivalence, validate parameters, or prove the workflow will produce a correct map. Usable != correct. |
| Treating Phase 1 V4-QG rule-rerank as solved workflow accuracy | `scripts/run_v4_qg_planner.py` can select a rule-usable candidate whenever one exists in the retrieval pool, reaching 1.0000 selected Top1 rule-usability on the 1,000-sample run. This is a selector/usability result, not exact-match accuracy, not multi-reference correctness, not parameter grounding, and not real QGIS execution. It should be reported as "candidate-pool/rerank can surface a usable chain under current rules", not as autonomous workflow generation solved. |
| Comparing old and new length metrics without noting the token definition | The quality-gate length stats count content L3 tokens only, excluding `<START>/<END>` ids. The generated quality-gate artifact has global median 7 / mean 8.5, whereas the old legacy `outputs/task_type_length_stats.json` reported larger values. Do not compare early-EOS or length-ratio diagnostics across old/new reports without noting this definition and data-scope change. |
| Treating absent explicit multi-reference labels as proof that workflows are single-solution | The multi-reference evaluator found no alternate exact-task references for the 369 persisted prediction records, but this is a labeling/coverage fact, not evidence that GIS tasks have only one valid workflow. It means current artifacts cannot quantify broad semantic multi-solution recovery without curated multi-reference labels or governed equivalence classes. |
| Treating MRV auto-verified candidates as training labels | `scripts/evaluate_multiref_validation.py` is a candidate-validation and human-review export tool only. The 100-variant smoke run now has 19 workflow-semantic registry candidates after QGIS landing was decoupled, but these are still not training labels until manual review confirms low false-equivalence risk and enough reviewed `verified_equivalent` entries exist. |
| Interpreting QGIS-chain gate failures as semantic invalidity | The MRV pipeline now separates workflow-semantic validation from downstream QGIS landing. `qgis_chain_unusable` and low QGIS mapping are auxiliary transferability failures, not direct evidence that a GEE workflow variant is semantically invalid. |
| Treating raw 500-variant expansion auto candidates as registry labels | Auto `verified_equivalent_candidate` rows are still not training labels by themselves. Use the promoted v2 registry/KB only: `outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json` and `verified_equivalence_kb_v2.*`. |
| Treating the AI-assisted expansion review CSV itself as the training set | The review CSV is provenance and audit evidence. Training ablation must read the deduplicated v2 registry/KB, where only user-confirmed `equivalent` rows are included and `uncertain`/`not_equivalent` rows are explicitly excluded. |

## Verification Evidence

Run from `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign`.

| Command | Latest Result |
| --- | --- |
| Root/context audit and Claude memory read (2026-06-24) | Re-read `task_plan.md`, `progress.md`, `findings.md`, and the external Claude memory files under `C:\Users\qiaoyun\.claude\projects\...\memory`. Current durable source of truth is the root tracking files plus `docs/PROJECT_CONTEXT*`; older `MEMORY.md` architecture sections are historical where superseded by the 2026-06-09 git/cleanup note and later QGIS/vector-planning updates. |
| `Measure-Object -Line` on key Phase 9 / QGIS vector artifacts (2026-06-24) | Verified line counts: `qgis_chain_dataset_v2_enriched_v3.jsonl` 2,319; `canonical_vector_planning_dataset.jsonl` 2,319; `canonical_vector_clean_sft_seed.jsonl` 685; `vector_training_samples_UNIFIED.jsonl` 10,768; `API_trace_to_L3_TRAINING_FINAL.jsonl` 6,031. `_final_merge.py` explains the ~16,800 merged-candidate number as 6,031 + 10,768 = 16,799. |
| `Import-Csv outputs_v2\diagnostics\open_landing_eval\open_landing_results.csv \| Group-Object grade` and `Group-Object modality,grade` (2026-06-24) | Current local open landing CSV still parses as 80 graded tasks: A=18, B=33, C=29. By modality: vector A=13/B=17/C=10, raster A=2/B=10/C=13, mixed A=3/B=6/C=6. |
| Narrow secret scan over root tracking docs, `run_process.bat`, `scripts/*.py`, and `src/gis_recommend/**/*.py` after sanitization (2026-06-24) | No true `sk-...` key material remains in those core files. Remaining matches in `src` are false positives from ordinary text such as `Task-...`. A broad earlier scan found local `.codegraph/codegraph.db` contains indexed historical/crawled strings and should remain excluded from shared artifacts. |
| User-reported open landing comparison: baseline vs `+op_match` vs `+sem tags` | Unique chains 1 → 16 → 33; top-3 concentration 100% → 31%; modality 0% → 100% → 84%. `+sem tags` passes diversity target (>20 unique chains), nearly reaches concentration target (<25%), and needs facts-text index merge to recover modality >90%. |
| `Import-Csv outputs_v2\diagnostics\open_landing_eval\open_landing_results.csv \| Group-Object grade` and Python CSV read (2026-06-06) | Current local open QGIS landing audit file parses as 80 tasks: A=18, B=33, C=29. By modality: vector A=13/B=17/C=10, raster A=2/B=10/C=13, mixed A=3/B=6/C=6. |
| `Import-Csv outputs_v2\diagnostics\open_landing_eval\open_landing_results.csv \| Group-Object top1_ops` and Python CSV read (2026-06-06) | Current local template concentration: 14 tasks use `gdal:warpreproject -> native:reprojectlayer -> gdal:cliprasterbymasklayer`, 7 use `native:reprojectlayer -> native:buffer -> native:clip`, and 5 use `native:reprojectlayer -> native:buffer -> gdal:cliprasterbymasklayer -> gdal:warpreproject`. |
| Read-only QGIS data audit over `outputs_v2/qgis_chain_dataset*.jsonl`, `qgis_vector_chain*.jsonl`, preference pairs, reranker reports, and open landing CSV (2026-06-06) | `qgis_chain_dataset.jsonl`: 3,053 rows / 972 unique chains / 55.3% rows with L3 bridge / 73.6% with semantic tags. `qgis_chain_dataset_v2_enriched_v3.jsonl`: 2,319 unique chains / 97.3% rows with facts text / 78.6% with semantic tags / no L3 bridge. `qgis_vector_chain_candidates.jsonl`: 957 vector or mixed chains / 19.0% rows with L3 bridge / 91.1% with semantic tags. `qgis_vector_preference_pairs_clean.jsonl`: 591 preference pairs, mostly `generic_template`, `modality_mismatch`, and `missing_step` negatives. |
| PowerShell JSONL verification of `outputs_v2\canonical_vector_planning_dataset.jsonl` (2026-06-06) | File exists and sample rows contain `task_text`, `modality`, `qgis_ops`, `planning_steps`, `l3_steps`, `has_full_l3`, `required_step_families`, `source`, `source_file`, and `confidence`. Counts: total 2,319; task_text 2,319; modality vector 1,598 / raster 456 / mixed 265; full-L3 total 1,046; full-L3 by modality vector 733 / raster 198 / mixed 115. Required-step families: 20 unique, led by `crs_transform` 596, `buffer_analysis` 519, `spatial_overlay` 423, `attribute_filter` 412, `geometry_repair` 401, `spatial_clip` 391. |
| Training-quality audit of `outputs_v2\canonical_vector_planning_dataset.jsonl` with PowerShell JSONL checks (2026-06-06) | Required fields missing 0; `qgis_ops`/`planning_steps`/`l3_steps` length mismatches 0; unique QGIS chains 2,319; task text <80 chars 59; empty `required_step_families` 463; total operator steps 21,290 with `other`/blank-L3 4,349 (20.4%). Nonblank L3 steps 16,941; invalid current-vocab L3 steps 163, all `L3_02_05_04`, spanning 140 rows. Pure-vector full-L3 rows are 733; after filtering invalid L3, short text, empty required families, chain length >15, and non-core providers, immediate clean SFT seed is 610 rows with 19 required-step families. |
| Verification of `outputs_v2\canonical_vector_clean_sft_seed.jsonl` after overlay remap (2026-06-06) | Structural checks pass: 685 rows, all vector, `has_full_l3=false` count 0, field missing/empty 0 except `required_step_families` empty for 36 rows, length mismatches 0, operator steps 3,190, `other` steps 0, blank L3 0, invalid current-vocab L3 0, `L3_02_05_04` rows 0, chain length min/median/p90/max 2/4/9/15, task text length min/median/max 299/300/300, duplicate task text groups 0, unique QGIS chains 685, unique L3 chains 619. Local L3 counts: `L3_02_02_06` 219, `L3_02_02_01` 110, `L3_02_02_02` 37, `L3_02_02_04` 73, `L3_02_02_05` 5. Overlay/centroid remap check failures 0 after excluding raster clip operators, which correctly map to raster L3. |
| JSONL audit of `configs\unseen_vector_prompts.jsonl` (2026-06-07) | 70 rows, modality counts vector=61 / mixed=6 / raster=3, duplicate ids 0, empty task 0, empty expected-family list 0, 44 unique expected families. Exact and substring overlap with `outputs_v2\canonical_vector_clean_sft_seed.jsonl` task text is 0. |
| `python -m py_compile scripts\evaluate_vector_generalization.py` (2026-06-07) | OK. Static syntax check only; full model evaluation intentionally left for the server command `python scripts/evaluate_vector_generalization.py` because it loads DPO/SFT checkpoints and decodes 70 prompts. |
| Server: `python scripts/evaluate_vector_generalization.py` (2026-06-07) | Wrote `outputs_v2/diagnostics/vector_generalization.json`. Vector prompts (61, measurable=48): DPO measurable recall 2.1% vs SFT 25.7%, strict/all 1.6% vs 20.2%, raster-ish token rate 94.8% vs 35.6%, vector token rate 1.4% vs 53.3%, mean length 5.0 vs 4.1. Mixed prompts (6): recall unchanged at 20.0% measurable, SFT vector token rate +15.3pp. Raster controls (3): vector token rate stayed 0.0%, raster-ish token rate improved to 88.6%. Overlay recall: intersection 0/4, union 1/1, difference 0/3. |
| Server: oversampled QGIS-vector warmstart training and generalization evaluation (2026-06-07) | Rebuilt `outputs_v2/transition_allowed_next.json` from `step8_quality_gate_qgis_vector_oversampled`: 65,748 train workflows, 60 states, 607,006 transitions, invalid 0. Expanded DPO v2 47->48 task types and trained `outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/` for 5 AR-SS epochs. Best checkpoint was epoch 1 with validation composite 0.5895; test AR SetF1 0.540, LCS 0.397, earlyEOS 11.3%, PPL 17.7. `outputs_v2/diagnostics/vector_generalization_oversampled.json`: vector measurable recall DPO 3.8% vs SFT 27.8%, strict/all 3.0% vs 21.9%, vector token rate 1.5% vs 57.6%, raster-ish token rate 92.8% vs 34.7%; raster controls kept vector token rate 0.0%; overlay intersection/union/difference remained 0. |
| Server: `python scripts/evaluate_sft_vector_impact.py --sft-checkpoint ..._oversampled_warmstart/best_model.pth ... --report-path outputs_v2/diagnostics/sft_vector_impact_oversampled.json` (2026-06-07) | Loaded the oversampled SFT checkpoint with 48-task oversampled vocab/stats and DPO v2 with 47-task quality-gate vocab/stats; both inferencers read the 60-state transition matrix. GEE test: DPO 0.4% strict-vector rate / avg len 5.9, SFT 2.4% / avg len 6.8. QGIS seed: DPO 1.7% / avg len 4.8, SFT 57.2% / avg len 6.8. Delta: GEE +2.0pp, QGIS +55.5pp. |
| `python -m py_compile scripts\evaluate_sft_vector_impact.py scripts\evaluate_vector_generalization.py` (2026-06-07) | OK after adding CLI override support to `evaluate_sft_vector_impact.py`; both vector evaluation scripts can now target the oversampled SFT checkpoint/vocab/length-stats without editing source. |
| Python JSON validation of `outputs_v2\pipeline\step8_qgis_vector_sft\*` (2026-06-06) | Package files present. Manifest reports 685 samples, train/val/test 548/68/69, token vocab `v2_94_l3`, format `step8_compatible`. Labeled workflows total 685; split indices are unique, exact coverage 0-684; bad token ids outside 0-93 are 0; missing task metadata 0; source is `qgis_vector_canonical`; task vocabulary is `"Vector Analysis": 0`; L3 sequence length min/avg/max is 2/4.657/15. |
| Python JSON validation of `outputs_v2\pipeline\step8_quality_gate_qgis_vector\*` (2026-06-06) | Merged package files present. Manifest and data agree on 77,569 workflows; split counts are train/val/test 62,180/7,694/7,695 with exact unique coverage 0-77,568; `task_type_to_id["Vector Analysis"] = 47`; `task_type_length_stats.json` has 48 task types and Vector Analysis median/p10/p90 length 4/2/9. QGIS rows are exactly 685 contiguous tail rows at indices 76,884-77,568, all in train. No ordinary token ids are outside 0-93; `-3`/`-4` negative specials are inherited from the original 76,884 GEE quality-gate rows. Cross-split content L3 sequence overlap is 0. QGIS L3 sequences: 619 unique, 45 duplicate groups / 111 rows, inherited from the 685 seed. |
| `python scripts\train_v4_quality_gate.py --data outputs_v2\pipeline\step8_qgis_vector_sft\labeled_workflows_l3_v4_qgis_vector.json --splits outputs_v2\pipeline\step8_qgis_vector_sft\dataset_splits_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_qgis_vector_sft\task_type_vocabulary_qgis_vector.json --checkpoint-dir outputs_v2\transformer_checkpoints_qgis_vector_sft_smoke --dry-run` | V4.2 launcher dry-run passed: workflows_total 685, train/val/test 548/68/69, num_task_types 1, vocab_size 98, device cpu, no training started. |
| `python scripts\train_v4_6_quality_gate.py --data outputs_v2\pipeline\step8_qgis_vector_sft\labeled_workflows_l3_v4_qgis_vector.json --splits outputs_v2\pipeline\step8_qgis_vector_sft\dataset_splits_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_qgis_vector_sft\task_type_vocabulary_qgis_vector.json --checkpoint-dir outputs_v2\transformer_checkpoints_qgis_vector_sft_v4_6_smoke --dry-run` | V4.6 launcher dry-run passed: workflows_total 685, train/val/test 548/68/69, num_task_types 1, vocab_size 98, device cpu, no training started. Caveat: length_bucket_training still used the default quality-gate length stats path, so QGIS/mixed length stats remain a pre-training task. |
| `python scripts\smoke_v4_quality_gate_training_entry.py --data outputs_v2\pipeline\step8_qgis_vector_sft\labeled_workflows_l3_v4_qgis_vector.json --splits outputs_v2\pipeline\step8_qgis_vector_sft\dataset_splits_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_qgis_vector_sft\task_type_vocabulary_qgis_vector.json --batch-size 2 --max-samples 2 --split train` | V4 training-entry smoke passed on CPU: loaded 94 L3 embeddings, selected 2 train samples, logits shape `[2, 100, 98]`, length prediction shape `[2, 1]`, contrastive representation shape `[2, 128]`, local BERT only, no checkpoints written. |
| `python scripts\train_v4_6_quality_gate.py --data outputs_v2\pipeline\step8_quality_gate_qgis_vector\labeled_workflows_l3_v4_quality_gate_qgis_vector.json --splits outputs_v2\pipeline\step8_quality_gate_qgis_vector\dataset_splits_v4_quality_gate_qgis_vector.json --task-vocab outputs_v2\pipeline\step8_quality_gate_qgis_vector\task_type_vocabulary_v4_quality_gate_qgis_vector.json --length-stats outputs_v2\pipeline\step8_quality_gate_qgis_vector\task_type_length_stats.json --checkpoint-dir outputs_v2\transformer_checkpoints_v4_6_quality_gate_qgis_vector_smoke --dry-run` | V4.6 merged-package dry-run passed: workflows_total 77,569, train/val/test 62,180/7,694/7,695, num_task_types 48, vocab_size 98, device cpu, no training started. |
| Server: `python scripts/evaluate_sft_vector_impact.py` (2026-06-07, after explicit length-stats path fix) | Loaded warmstart SFT with 48-task mixed length stats from `outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_length_stats.json` and DPO v2 with 47-task quality-gate stats from `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json`. Strict vector tokens 14 because `L3_02_05_04` is absent from the 94-L3 vocab. GEE test: DPO 0.4% strict-vector rate / avg len 5.9, SFT 2.0% / avg len 6.3. QGIS seed: DPO 1.7% / avg len 5.0, SFT 53.7% / avg len 6.6. Delta: GEE +1.6pp, QGIS +52.0pp. Report path: `outputs_v2/diagnostics/sft_vector_impact.json`. |
| QGIS-only forward probe on two actual merged-package QGIS rows (2026-06-06) | Built a 48-task V4 model from local BERT/L3 embeddings and fed two rows where `source == qgis_vector_canonical`; batch task type ids were `[47, 47]`, logits shape `[2, 100, 98]`, length prediction shape `[2, 1]`, and contrastive representation shape `[2, 128]`. |
| Warmstart compatibility probe for `outputs_v2\transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed\best_preference_model.pth` into a 48-task model (2026-06-06) | Failed as expected with `size mismatch for task_type_embedding.weight`: checkpoint shape `[47, 256]`, current model shape `[48, 256]`. Existing quality-gate and DPO v2 checkpoints both have 47-task task embedding/classifier shapes. |
| `python scripts\train_v4_6_quality_gate.py ... --dry-run --lr 1e-5` on the merged package (2026-06-06) | Fails argument parsing with `unrecognized arguments: --lr 1e-5`; the launcher currently exposes no learning-rate override CLI. |
| `python scripts\compute_task_type_length_stats.py` | Generated `outputs_v2\pipeline\step8_quality_gate\task_type_length_stats.json` from 76,884 quality-gated workflows. Content-token global stats: median 7, mean 8.5, p90 16; 47 task types. |
| `python -m unittest tests.test_v4_qg_planner tests.test_task_type_length_stats -v` | 10 tests OK; covers V4-QG planner path defaults, explicit length stats load, candidate rerank basics, content-token length stat generation, and length-stats path priority. |
| Step8 + V4.6 mainline read-only audit (2026-05-21) | Confirmed `gis-evaluate = gis_recommend.evaluation.runner:main`; runner reads `V4_LABELED_WORKFLOWS_PATH`, `build_test_set()`, `run_l3_inference()`, optional `--use-reranker`, optional `--use-repair`, optional QGIS/executable diagnostics. Real Step8 count is 107,399 workflows with split 85,919 / 10,739 / 10,741. |
| `SemanticMetricsCalculator._strip_special([-3,1,2,-4,94,95,96,97,350,351,352,353])` | After the 2026-05-21 contract fix, returns `[1,2,350,351,352,353]` under mainline `v2_94_l3`. `legacy_350_l3_token_profile()` strips only `350..353`. A toy perfect prediction against `[-3,54,50,40,-4]` now reports LCS 1.0 / token accuracy 1.0 / SeqEM true. |
| `python -m unittest tests.test_mainline_run_contract -v` | 4 tests OK; covers v2 token stripping, legacy profile compatibility, run-contract report metadata, and `CandidateVerifier` v2 I/O metadata default behavior. |
| `python -m unittest tests.test_mainline_run_contract tests.test_reranker_evaluate_system tests.test_two_stage_reranker tests.test_executable_ratio -v` | 50 tests OK; covers mainline contract, report-only repair behavior, reranker decision/diagnostic separation, and executable diagnostics. |
| `python -m unittest tests.test_v4_qg_planner tests.test_v5_empirical_experiment_scripts tests.test_retrieval_planning_stages -v` | 33 tests OK after adding non-mainline lineage metadata to V4-QG/V5/retrieval-stage reports. |
| `python -m compileall src\gis_recommend\evaluation\run_contract.py src\gis_recommend\evaluation\semantic_metrics.py src\gis_recommend\evaluation\report.py src\gis_recommend\evaluation\runner.py src\gis_recommend\reranking\reranker_verifier.py scripts\run_v4_qg_planner.py scripts\evaluate_v5_hybrid_planner.py scripts\evaluate_retrieval_planning_stages.py tests\test_mainline_run_contract.py` | OK. |
| `python -m unittest tests.test_mainline_run_contract tests.test_qgis_candidate_generator_logging tests.test_v4_qg_evaluation_report -v` | 11 tests OK after the post-audit contract closure. Covers generator run-contract I/O authority, `qgis_score_components` propagation into decision traces, and V4-QG research/non-mainline report lineage. |
| `python -m unittest tests.test_v2_defaults tests.test_mainline_run_contract tests.test_build_ontology_kg_paths tests.test_import_l3_mappings -v` | 21 tests OK after Neo4j KG import hardening. Covers v2 defaults, mainline contract, safe KG build CLI behavior, no implicit `--clear`, v2 hierarchy schema compatibility, v2-only mapping defaults, and standalone L3 mapping import arguments. |
| `python -m compileall scripts\build_ontology_kg.py scripts\import_l3_mappings.py tests\test_build_ontology_kg_paths.py tests\test_import_l3_mappings.py` | OK. |
| `python -m unittest tests.test_v2_defaults tests.test_mainline_run_contract tests.test_mainline_shadow_phase tests.test_reranker_evaluate_system tests.test_executable_ratio tests.test_v4_qg_evaluation_report -v` | 49 tests OK after Phase0/Phase1 shadow instrumentation. Covers v2 defaults, contract/report fields, candidate pool trace, evidence bundle missing semantics, train-only retrieval shadow, report-only repair, reranker/executable diagnostics, and V4-QG non-mainline reporting. |
| `python -m compileall src\gis_recommend\evaluation\run_contract.py src\gis_recommend\evaluation\report.py src\gis_recommend\evaluation\runner.py src\gis_recommend\evaluation\shadow_phase.py tests\test_mainline_shadow_phase.py` | OK. |
| `python -m unittest tests.test_mainline_run_contract tests.test_reranker_evaluate_system tests.test_two_stage_reranker tests.test_executable_ratio tests.test_v4_qg_planner tests.test_v4_qg_evaluation_report tests.test_qgis_candidate_generator_logging tests.test_v2_defaults -v` | 69 tests OK; verifies adjacent reranker/executable/QGIS generator/default-path behavior after wiring generator/report/QGIS evaluation to the run contract. |
| `python -m compileall src\gis_recommend\operators\qgis_candidate_generator.py src\gis_recommend\evaluation\runner.py src\gis_recommend\evaluation\reranker_pipeline.py src\gis_recommend\evaluation\report.py scripts\evaluate_v4_quality_gate.py src\gis_recommend\config\transformer_config.py tests\test_mainline_run_contract.py tests\test_qgis_candidate_generator_logging.py tests\test_v4_qg_evaluation_report.py` | OK after post-audit contract closure. |
| `python -m unittest tests.test_evidence_aware_ranking tests.test_mainline_shadow_phase -v` | 207 tests OK after the evidence-aware ranking correction-sprint script. Confirms new offline ranker tests plus existing shadow/report runtime-contract regressions. |
| `python scripts\evaluate_evidence_aware_ranking.py --report outputs_v2\evaluation_reports\empirical_v2_smoke_artifact.json --output-dir outputs_v2\diagnostics\evidence_aware_ranking` | Wrote `evidence_aware_ranking.json/.md`. On 120 empirical records: candidate absence 0.0, selection diff 0.7333, legacy mean LCS/TokenAcc/SetF1 = 0.3957/0.1941/0.5666, evidence-aware = 0.4412/0.1696/0.6361, oracle best-in-pool = 0.5862/0.3154/0.7654. Contract records offline-only and no mainline output/metric mutation. |
| `python -m unittest tests.test_reranker_evaluate_system -v` | 13 tests OK; includes report-only repair behavior and explicit tests that reranker scoring/pruning ignores validation and compatibility outputs. |
| `python scripts\analyze_length_bucket_distribution.py` | Reads the quality-gate stats artifact by default. Bucket summary: short 5 task types / 562 samples, medium 35 / 47,848, long 7 / 28,474, very_long 0. |
| `python scripts\run_v4_qg_planner.py --eval-samples 1 --output-dir outputs_v2\tmp_planner_smoke_check` | Passes after the 2026-05-19 smoke fixes. Set Predictor checkpoint is absent locally, so train-frequency set prior fallback is used. Selected Top1 usable 1.0000; retrieval Top1 usable 1.0000; Pool Top5 any usable 1.0000; forbidden-pattern scan pass. |
| `python -m unittest tests.test_v4_qg_planner tests.test_mrv_registry_builder -v` | 12 tests OK after the weekly-report/planner smoke review. |
| `python -B -c "import ast, pathlib; p=pathlib.Path('scripts/run_v4_qg_planner.py'); ast.parse(p.read_text(encoding='utf-8')); print('syntax ok')"` | Syntax OK without writing `__pycache__`. |
| `python -m unittest tests.test_v4_6_training_stability -v` | 2 tests OK; covers CE/sampling logits separation for dynamic-min-length END blocking |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_v4_training_entry_smoke tests.test_v4_6_training_stability -v` | 9 tests OK |
| `python -m compileall src\gis_recommend\training\train_v4_6.py tests\test_v4_6_training_stability.py` | OK |
| `python -m unittest tests.test_v4_qg_planner -v` | 7 tests OK; covers V4-QG planner defaults, soft transition prior, set coverage, candidate-pool dedupe, usability-first rerank, and forbidden-pattern scan |
| `python -m compileall scripts\run_v4_qg_planner.py tests\test_v4_qg_planner.py` | OK |
| `python -m unittest tests.test_v4_qg_planner.V4QGPlannerTests.test_default_paths_are_quality_gate_scoped -v` | Initially failed while planner default still pointed to `set_predictor_checkpoints_v3_quality_gate`; passes after V4.6 Set Predictor default path alignment |
| `python -m compileall scripts\run_v4_qg_planner.py src\gis_recommend\config\transformer_config.py tests\test_v4_qg_planner.py` | OK after V4.6 Set Predictor path alignment |
| `python scripts\run_v4_qg_planner.py --eval-samples 200 --output-dir outputs_v2\v4_qg_planner_reports\phase1_candidate_rerank` | Evaluation/rerank only. Set Predictor checkpoint absent locally, so train-frequency set prior fallback used. Selected Top1 rule-usable 1.0000 vs retrieval Top1 0.6350; Pool Top5 any usable 1.0000; forbidden-pattern scan pass. |
| `python scripts\run_v4_qg_planner.py --eval-samples 1000 --output-dir outputs_v2\v4_qg_planner_reports\phase1_candidate_rerank_1000` | Stability check. Set Predictor checkpoint absent locally, so train-frequency set prior fallback used. Selected Top1 rule-usable 1.0000 vs retrieval Top1 0.6330; Pool Top5 any usable 1.0000; mean selected usability 0.8449; mean QGIS mapping 0.8082; forbidden-pattern scan pass. |
| `python -m compileall scripts\evaluate_multiref_validation.py tests\test_multiref_validation_experiment.py` | OK |
| `python -m unittest tests.test_multiref_validation_experiment -v` | 10 tests OK; covers MRV variant generation, sensitive guards, semantic usability gates, QGIS landing decoupling, auto-labeling, registry eligibility, review-packet export, manual-only registry construction, and human-review stratification. |
| `python scripts\evaluate_multiref_validation.py --max-workflows 50 --max-variants 100 --review-auto-verified 10 --review-plausible 5 --review-rejected 5` | Wrote `outputs_v2/v4_qg_multiref_validation/` artifacts. Smoke result after semantic-vs-landing decoupling: 100 variants, 21 commutative pairs, 19 `verified_equivalent_candidate`, 81 `invalid_variant`, 19 auto-verified registry candidates, 15-row stratified review sample, 19-row `equivalence_review_packet.csv`, and 0 reviewed equivalence groups in `verified_multi_reference_registry.json`. QGIS landing is auxiliary and still weak: `qgis_mapping_valid_rate=0.0`, `qgis_io_valid_rate=0.74`, `strict_qgis_landing_usable_rate=0.16`. |
| `Import-Csv outputs_v2\v4_qg_multiref_validation\equivalence_review_packet.csv \| Group-Object human_label` | Manual MRV review labels verified: `equivalent=14`, `uncertain=4`, `not_equivalent=1`. |
| `Get-Content outputs_v2\v4_qg_multiref_validation\verified_multi_reference_registry.json \| ConvertFrom-Json` registry sanity check | Manual registry verified: 7 task groups, 14 accepted source variant ids, label counts 14/4/1, and all 5 uncertain/rejected variant ids absent from registry sources. |
| `Get-Content outputs_v2\v4_qg_multiref_validation\multiref_validation_report.json` plus summary line check | MRV report and Markdown summary both record `reviewed_equivalence_group_count=7` and `reviewed_equivalent_variant_count=14`. |
| Source-inspection extraction over `step1/raw_workflows.json`, `step4/standardized_workflows.json`, and quality-gate Step8 for scripts 1559/2699/3986/3871 | Confirmed the four uncertain rows' concrete operator windows. Key boundary finding: `wf46_pos2_swap53_28` crosses from `imgC.filterDate.filterBounds.filterMetadata` to `img.select`, so swapping select before `filterMetadata` breaks the ImageCollection/Image object chain. |
| `Import-Csv outputs_v2\v4_qg_multiref_validation\uncertain_deep_review.csv` plus registry/report sanity checks | Deep-review artifact verified: 4 inspected rows, 3 `conditional_equivalent_not_registry_eligible`, 1 `not_equivalent_source_inspected`; current review packet label counts are `equivalent=14`, `uncertain=3`, `not_equivalent=2`; registry remains 7 groups / 14 variants with excluded ids absent. |
| `python scripts\evaluate_multiref_validation.py --max-workflows 200 --max-variants 500 --review-auto-verified 100 --review-plausible 30 --review-rejected 30 --output-dir outputs_v2\v4_qg_multiref_validation_expansion_500` | Wrote the 500-variant MRV expansion: 500 variants, 53 commutative pairs, 46 auto `verified_equivalent_candidate`, 454 `invalid_variant`, semantic auto pass 0.092, semantic usable 0.116, guard pass 0.9. QGIS landing remained auxiliary and weak: strict QGIS landing usable 0.074. |
| `python scripts\analyze_mrv_expansion.py --input-jsonl outputs_v2\v4_qg_multiref_validation_expansion_500\generated_variants.jsonl --output-dir outputs_v2\v4_qg_multiref_validation_expansion_500 --taxonomy-path configs\equivalence_taxonomy.yaml` | Wrote MRV expansion analysis artifacts. Family totals/risk totals both sum to 500; highest auto-pass families are `select_filter` 0.1746 and `filter_filter` 0.1281; `landing_only_failure=500` is recorded only as auxiliary transferability failure. |
| MRV expansion artifact sanity check | Verified 500 generated variants, 46 review-packet rows, family summary total 500, risk summary total 500, and report counts aligned with `multiref_validation_report.json`. |
| AI-assisted review sanity check for `outputs_v2\v4_qg_multiref_validation_expansion_500\equivalence_review_packet_ai_review.csv` | Verified 46 review rows, label counts `equivalent=36`, `uncertain=8`, `not_equivalent=2`, and registry draft counts 19 groups / 36 variant sources. |
| `python scripts\build_mrv_registry_v2.py --manual-review outputs_v2\v4_qg_multiref_validation\equivalence_review_packet.csv --expansion-review outputs_v2\v4_qg_multiref_validation_expansion_500\equivalence_review_packet_ai_review.csv --output-dir outputs_v2\v4_qg_multiref_validation` | Wrote registry v2 / KB v2. Final counts: 55 unique reviewed variants, 42 equivalent variants, 23 task groups, 13 excluded variants. |
| Registry v2 JSON/CSV sanity check | Verified 42 entry source variant ids, 42 KB rows, 0 overlap between excluded ids and registry entry ids, and clean risk keys `low`, `medium`, `unknown`. |
| `python -m unittest tests.test_multiref_validation_experiment tests.test_mrv_expansion_analysis tests.test_mrv_registry_builder -v` | 20 tests OK. |
| `python -m compileall scripts\evaluate_multiref_validation.py scripts\analyze_mrv_expansion.py scripts\build_mrv_registry_v2.py tests\test_multiref_validation_experiment.py tests\test_mrv_expansion_analysis.py tests\test_mrv_registry_builder.py` | OK. |
| `python scripts\build_mrv_training_ablation.py --subset-sizes 5,10,all` | Wrote isolated MR ablation datasets under `outputs_v2\v4_qg_mr_ablation\`: `mr_5`, `mr_10`, `mr_all_42`, and `mrv_training_ablation_manifest.json`. Base workflows 76,884; output workflows 76,889 / 76,894 / 76,926; val/test unchanged; manifest records `no_training_started=true`. |
| `python -m unittest tests.test_mrv_training_ablation -v` | 4 tests OK. |
| `python -m unittest tests.test_multiref_validation_experiment tests.test_mrv_expansion_analysis tests.test_mrv_registry_builder tests.test_mrv_training_ablation -v` | 24 tests OK. |
| `python -m compileall scripts\evaluate_multiref_validation.py scripts\analyze_mrv_expansion.py scripts\build_mrv_registry_v2.py scripts\build_mrv_training_ablation.py tests\test_multiref_validation_experiment.py tests\test_mrv_expansion_analysis.py tests\test_mrv_registry_builder.py tests\test_mrv_training_ablation.py` | OK. |
| V4.6 quality-gate dry-run checks for `mr_5`, `mr_10`, and `mr_all_42` | `scripts/train_v4_6_quality_gate.py --data outputs_v2\v4_qg_mr_ablation\<version>\labeled_workflows_l3_v4_quality_gate.json --splits outputs_v2\v4_qg_mr_ablation\<version>\dataset_splits_v4_quality_gate.json --task-vocab outputs_v2\v4_qg_mr_ablation\<version>\task_type_vocabulary_v4_quality_gate.json --dry-run` passed for all three versions; no training or checkpoint directory creation. |
| MR ablation artifact sanity check | Verified injected-row provenance is present, selected variant ids are unique per version, excluded variants do not overlap injected entries, val/test splits are unchanged, and risk keys remain `low` / `medium` / `unknown`. |
| `python -m unittest tests.test_mrv_ablation_comparator -v` | 3 tests OK after TDD red-green; covers report metric extraction, delta computation, missing-metric warnings, paired bootstrap, manifest count attachment, and CLI output. |
| `python -m unittest tests.test_multiref_validation_experiment tests.test_mrv_expansion_analysis tests.test_mrv_registry_builder tests.test_mrv_training_ablation tests.test_mrv_ablation_comparator -v` | 27 tests OK. |
| `python -m compileall scripts\evaluate_multiref_validation.py scripts\analyze_mrv_expansion.py scripts\build_mrv_registry_v2.py scripts\build_mrv_training_ablation.py scripts\compare_mrv_training_ablation.py tests\test_multiref_validation_experiment.py tests\test_mrv_expansion_analysis.py tests\test_mrv_registry_builder.py tests\test_mrv_training_ablation.py tests\test_mrv_ablation_comparator.py` | OK. |
| MR comparator real-report smoke | Ran `scripts\compare_mrv_training_ablation.py` against `outputs_v2\v4_qg_planner_reports\phase1_candidate_rerank_1000\planner_report.json` as both baseline and `baseline_self`, with manifest attached and output in a temp directory. It extracted 6 metric deltas and all deltas were 0.0, confirming the comparator reads the current planner report schema without training or checkpoint access. |
| Read `结果\transformer训练结果\train_v4_6_quality_gate-mr-0517.md` | Server run command used `mr_all_42` data/split/task-vocab and checkpoint dir `outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42`; final test metrics were Top1 31.3%, Top5 60.0%, TF-SeqEM 0.6%, AR-SeqEM 0.0%, AR-TokenAcc 18.8%. Training loss became `inf` after AR-SS started at epoch 11. |
| `python scripts\build_bounded_ontology_inventory.py --output-dir outputs_v2\v5_final_reports\bounded_ontology_inventory` | Wrote bounded ontology artifacts: 3,800 operator-pair rows; exact 13, execution-sensitive 98, partial 691, ambiguous 2,989, composite 4, unsupported 5; no semantic retrieval/runtime change |
| `python -m unittest tests.test_bounded_ontology_inventory -v` | 7 tests OK |
| `python -m compileall -q scripts\build_bounded_ontology_inventory.py tests\test_bounded_ontology_inventory.py` | OK |
| Bounded ontology artifact sanity check | Required JSON/CSV/Markdown artifacts exist; runtime contract reports `semantic_retrieval_implemented=False` and `training_run=False`; forbidden-pattern scan result `pass` with 0 matches |
| `python -m unittest tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 18 tests OK |
| `python -m compileall src/gis_recommend/data/pipeline_provenance.py src/gis_recommend/data/pipeline_runner.py src/gis_recommend/data/step6_label_with_l3.py src/gis_recommend/data/step7_prepare_v4_data.py src/gis_recommend/data/step8_clean_v4_data.py scripts/audit_pipeline_outputs.py tests/test_pipeline_provenance.py` | OK |
| `python -m unittest tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 29 tests OK |
| `python -m compileall src/gis_recommend/training/splits.py src/gis_recommend/training/train_v4_2.py src/gis_recommend/training/train_v4_6.py src/gis_recommend/training/train_set_predictor_v3.py src/gis_recommend/evaluation/sampling.py tests/test_dataset_splits.py tests/test_evaluate_system_sampling.py` | OK |
| `python scripts/audit_training_data_quality.py --data outputs_v2\pipeline\step8\labeled_workflows_l3_v4_cleaned.json --splits outputs_v2\dataset_splits_v4.json --id-mappings outputs_v2\id_mappings_v2.json --hierarchy outputs_v2\classification_hierarchy_v2.csv --out-dir outputs_v2\pipeline\audit` | Wrote training data quality audit; warnings: inactive L3, skewed L3 distribution, sparse task types, val/test-only task types, cross-split sequence duplicates, low-confidence mapping tokens |
| `python -m unittest tests.test_training_data_quality tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 31 tests OK |
| `python -m compileall src/gis_recommend/data/training_data_quality.py scripts/audit_training_data_quality.py tests/test_training_data_quality.py` | OK |
| Current Step8 vs v2 mapping/official GEE operator smoke | 306 unique Step8 operators; 306/306 match v2 GEE metadata case-insensitively; 295/306 match crawled official `gee_operators.json` names case-insensitively; 11 mapped operators are not direct official-name hits and require alias/canonical review |
| `python scripts/build_v4_quality_gate_candidate.py --data outputs_v2\pipeline\step8\labeled_workflows_l3_v4_cleaned.json --id-mappings outputs_v2\id_mappings_v2.json --out-dir outputs_v2\pipeline\step8_quality_gate --min-task-count 10` | Wrote candidate, quarantine, grouped split, task vocab, quality report, and GEE alias audit; summary: input 107,399, candidate 76,884, quarantine 30,515, sparse merged 116, cross-split duplicate sequence hashes 0 |
| `python scripts/audit_training_data_quality.py --data outputs_v2\pipeline\step8_quality_gate\labeled_workflows_l3_v4_quality_gate.json --splits outputs_v2\pipeline\step8_quality_gate\dataset_splits_v4_quality_gate.json --id-mappings outputs_v2\id_mappings_v2.json --hierarchy outputs_v2\classification_hierarchy_v2.csv --out-dir outputs_v2\pipeline\step8_quality_gate\audit` | Candidate audit warnings only: inactive L3, skewed L3 distribution, low-confidence mapping tokens; task types <10 = 0, val/test-only task = 0, cross-split duplicate L3 sequences = 0 |
| Quality-gate split validation smoke | Candidate split covers 76,884/76,884 workflows, unique indices 76,884, out-of-range 0, duplicates 0 |
| Quality-gate GEE alias audit | Candidate has 150 unique operators; 150/150 match v2 GEE metadata case-insensitively; 140/150 match crawled official names case-insensitively; 10 unresolved official-name hits account for 20,593 tokens (3.13%) |
| `python -m unittest tests.test_training_data_quality_gate tests.test_training_data_quality tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 36 tests OK |
| `python -m compileall src\gis_recommend\data\quality_gate.py scripts\build_v4_quality_gate_candidate.py tests\test_training_data_quality_gate.py` | OK |
| `python -m unittest tests.test_v4_training_entry_smoke -v` | 3 tests OK after red-green cycle; verifies quality-gate default paths, no-checkpoint smoke behavior, and local-only BERT loader args |
| `python -m unittest tests.test_v4_training_entry_smoke tests.test_training_data_quality_gate tests.test_training_data_quality tests.test_dataset_splits tests.test_evaluate_system_sampling tests.test_pipeline_provenance tests.test_v2_defaults tests.test_build_ontology_kg_paths tests.test_qgis_candidate_generator_logging -v` | 39 tests OK |
| `python -m compileall src\gis_recommend\models\transformer_model_v4.py scripts\smoke_v4_quality_gate_training_entry.py tests\test_v4_training_entry_smoke.py` | OK |
| `python scripts\smoke_v4_quality_gate_training_entry.py --batch-size 2 --max-samples 2 --split train` | Real quality-gate training-entry smoke passed on CPU with local cached BERT: 76,884 workflows loaded, 47 task types, v2 embeddings loaded for 94 tokens, logits shape `[2, 100, 98]`, no checkpoint writing |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_v4_training_entry_smoke -v` | 6 tests OK |
| `python -m compileall scripts\train_v4_quality_gate.py tests\test_v4_quality_gate_training_launcher.py` | OK |
| `python scripts\train_v4_quality_gate.py --dry-run` | Quality-gate training launcher validates real candidate paths: 76,884 workflows, split 61,495 / 7,694 / 7,695, 47 task types, vocab 98, checkpoint dir `outputs_v2\transformer_checkpoints_v4_2_quality_gate`; no checkpoint directory created |
| `python -m unittest tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_quality_gate_training_launcher tests.test_v4_training_entry_smoke -v` | 10 tests OK |
| `python -m compileall scripts\train_set_predictor_quality_gate.py tests\test_set_predictor_quality_gate_training_launcher.py src\gis_recommend\models\set_predictor_v3.py` | OK |
| `python scripts\train_set_predictor_quality_gate.py --dry-run` | Set Predictor quality-gate launcher validates real candidate paths: 76,884 workflows, split 61,495 / 7,694 / 7,695, 47 task types, 47 train-active tokens, checkpoint dir `outputs_v2\set_predictor_checkpoints_v3_quality_gate`, active tokens `outputs_v2\set_predictor_active_tokens_quality_gate.json`; no checkpoint or active-token file created |
| `python scripts\build_quality_gate_transition_matrix.py` | Generated `outputs_v2\transition_allowed_next.json`: 61,495 train workflows, 48 states, 587,479 transitions, invalid transitions skipped 0 |
| `python -m unittest tests.test_quality_gate_transition_matrix tests.test_v4_quality_gate_training_launcher tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_training_entry_smoke -v` | 14 tests OK |
| `python -m compileall scripts\build_quality_gate_transition_matrix.py scripts\train_v4_quality_gate.py tests\test_quality_gate_transition_matrix.py tests\test_v4_quality_gate_training_launcher.py` | OK |
| Real split validation for `outputs_v2/dataset_splits_v4.json` | 107,399 total indices, 107,399 unique, out-of-range 0, missing 0 |
| Training split smoke with `train_v4_2.load_or_create_splits` | Loads aligned split and builds train/val/test lists: 85,919 / 10,739 / 10,741 |
| Evaluation sampling smoke | `build_test_set(..., max_samples=10)` loads 10 samples from aligned test split without `IndexError` |
| `python scripts/audit_pipeline_outputs.py --outputs-dir outputs_v2` | Wrote audit report; warnings: `step3:large_drop_from_previous`, `step8:missing_provenance` before strict run; after strict run report records Step6/7/8 missing provenance |
| `python scripts/audit_pipeline_outputs.py --outputs-dir outputs_v2 --require-provenance --fail-on-warning` | Legacy gate command now remains report-only under Phase 15C; existing old artifacts still report `step3:large_drop_from_previous` and `step6/7/8:missing_provenance` |
| `python -m unittest tests.test_v2_defaults tests.test_build_ontology_kg_paths -v` | 10 tests OK |
| `python -m unittest tests.test_qgis_candidate_generator_logging -v` | 2 tests OK |
| `python -m compileall src/gis_recommend/operators/qgis_candidate_generator.py src/gis_recommend/operators/l3_to_platform_mapper.py tests/test_v2_defaults.py scripts/build_ontology_kg.py src/gis_recommend/config/transformer_config.py src/gis_recommend/data/__init__.py src/gis_recommend/inference/infer_l3_candidates_v4.py src/gis_recommend/evaluation/runner.py` | OK |
| QGIS default smoke | `QGISCandidateGenerator`: 75 L3 / 438 mappings; `Write Vector Tiles_mbtiles` kept; `Remove Duplicate Points` on corrected L3 |
| Platform mapper default smoke | `L3ToPlatformMapper`: 75 L3 / 438 mappings; `Write Vector Tiles_mbtiles` kept; `Remove Duplicate Points` on corrected L3 |
| Legacy override smoke | `GIS_OUTPUTS_DIR=outputs`, `GIS_VOCAB_SIZE=350` gives `OUTPUT_DIR=outputs`, `VOCAB_SIZE=350`, `TOTAL_VOCAB_SIZE=354`, old id mappings/embeddings |
| Phase 15C.1 V5 semantic-boundary audit | Read-only analysis. Key code anchors verified by source inspection: `train_v4_2.train_epoch` dispatches to `_train_step_autoregressive`, not `_train_step_ar`; v4.4 `_train_step_ar` is pre-A dead path; v4.5 balanced sampler is runtime-active through `_build_train_loader`; v4.6 overrides `_train_step_autoregressive` and selects best checkpoint by `ar_token_acc`; inference constraints live in `L3SequenceInferencerV4._apply_constraints`; executable legality diagnostics are reporting/evaluation-only |
| Phase 15C.3 runtime-boundary enforcement audit | Read-only analysis. Searched for V5 governance object names and reverse-edge terms. Found no implemented `RuntimeProfile`/`CheckpointManifest`/`DatasetLineage`/`GradientProfile`/`MetricRecord`/`CompatibilityResult`/`DecodePolicy` objects. Pre-fix reverse-edge candidates were found in `step8_clean_v4_data.validate_pipeline_provenance`, `audit_pipeline_outputs --fail-on-warning`, reranker validation scoring, and optional chain repair |
| `python -m compileall src\gis_recommend\models\transformer_model_v4.py src\gis_recommend\inference\infer_l3_candidates.py src\gis_recommend\evaluation\semantic_metrics.py src\gis_recommend\evaluation\evaluate_generation_detailed_v3.py src\gis_recommend\training\train_v3.py src\gis_recommend\training\train_v4_3_rl.py src\gis_recommend\knowledge_graph\train_graph_embeddings.py scripts\build_ontology_kg.py scripts\project_l3_embeddings_v2.py tests\test_reranker_evaluate_system.py tests\test_chain_repair.py` | OK |
| `python -m unittest tests.test_pipeline_provenance tests.test_reranker_evaluate_system tests.test_phase15c_runtime_contract tests.test_training_data_quality -v` | 26 tests OK |
| `python -m unittest tests.test_v4_training_entry_smoke tests.test_build_ontology_kg_paths tests.test_chain_repair -v` | 10 tests OK |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_set_predictor_quality_gate_training_launcher tests.test_quality_gate_transition_matrix -v` | 11 tests OK |
| `python -m unittest tests.test_phase15c_runtime_contract tests.test_chain_repair tests.test_reranker_evaluate_system tests.test_pipeline_provenance -v` | 31 tests OK |
| `python -m unittest tests.test_two_stage_reranker -v` | 13 tests OK |
| `python -m unittest tests.test_v4_quality_gate_training_launcher tests.test_set_predictor_quality_gate_training_launcher tests.test_quality_gate_transition_matrix -v` | 11 tests OK |
| `python -m compileall src\gis_recommend\inference\infer_l3_candidates.py src\gis_recommend\inference\infer_task_conditioned_v3.py src\gis_recommend\inference\infer_l3_candidates_v4.py src\gis_recommend\models\set_predictor_v3.py src\gis_recommend\evaluation\evaluate_generation_detailed_v3.py src\gis_recommend\training\train_v3.py src\gis_recommend\training\train_v4_3.py src\gis_recommend\training\train_v4_4.py src\gis_recommend\training\train_v4_3_rl.py src\gis_recommend\data\pipeline_provenance.py src\gis_recommend\evidence tests\test_phase15c_runtime_contract.py tests\test_chain_repair.py` | OK |
| Read-only empirical audit script via `python -` over `outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json` and split JSON | Measured 76,884 workflows, 47 active L3, Top10 token share 74.94%, explicit join proxy 0.39%, median 118 unique sequences per task type, 99.9575% transition-mask test coverage, Markov-2 next-token accuracy 33.51%, weak lexical NN LCS recall 0.607, and at that time no active `outputs_v2` prediction report was available |
| Pre-infrastructure `Get-ChildItem outputs_v2\evaluation_reports` and legacy `outputs\evaluation_reports` inspection | Confirmed legacy reports under `outputs/evaluation_reports` are old 350-L3 artifacts and should not be used as current v2 performance evidence; current v2 evidence now starts with the baseline-only empirical smoke artifact |
| `python -m unittest tests.test_empirical_evaluation tests.test_evaluate_system_sampling tests.test_reranker_evaluate_system -v` | 25 tests OK; includes empirical artifact schema/diagnostics, deterministic retrieval ordering, sampling split checks, and report-only reranker/repair behavior |
| `python -m compileall src\gis_recommend\evaluation\empirical.py scripts\build_empirical_evaluation_artifact.py tests\test_empirical_evaluation.py` | OK |
| `python scripts\build_empirical_evaluation_artifact.py --samples 20 --retrieval-top-k 5 --canonicalization-limit 2000 --out outputs_v2\evaluation_reports\empirical_v2_smoke_artifact.json` | Wrote baseline-only empirical artifact and Markdown report; schema `gis_recommend.empirical_evaluation.v1`, 20 samples, best baseline by LCS `lexical_retrieval` = 0.453342 |
| Empirical smoke artifact field inspection via `python -` | Confirmed artifact includes `dataset_structure_audit`, `upper_bound_analysis`, `engineering_report.bottleneck_attribution`, per-sample predictions for lexical/embedding/nearest/retrieval-rerank/retrieval-constrained/Markov2, beam candidates, decode traces, token probabilities, END timing, repetition stats, candidate pool diagnostics, retrieval diagnostics, and reranker outputs |
| `python -m unittest tests.test_v5_final_entrypoints tests.test_v5_final_runtime tests.test_empirical_evaluation -v` | 16 tests OK; covers V5_final runtime contracts, entrypoints, and empirical artifact regression |
| `python scripts\train_v5_final_minimal.py --dry-run` | Validated real quality-gate defaults without writing checkpoints: 76,884 workflows, split 61,495 / 7,694 / 7,695, vocab 98 |
| `python -m compileall src\gis_recommend\models\v5_final src\gis_recommend\evaluation\empirical.py scripts\train_v5_final_minimal.py scripts\infer_v5_final_minimal.py tests\test_v5_final_runtime.py tests\test_v5_final_entrypoints.py` | OK |
| `python -m unittest tests.test_phase15c_runtime_contract -v` | 8 tests OK after V5_final changes |
| V5_final forbidden-edge source scan | `rg` over new V5 files found no `strict=False`, `weights_only=False`, `gis_recommend.evidence` import, runtime governance objects, or diagnostic terms in the loss beyond explanatory comments |
| `python -m unittest tests.test_v5_training_system tests.test_v5_final_runtime tests.test_v5_final_entrypoints tests.test_empirical_evaluation tests.test_phase15c_runtime_contract -v` | 31 tests OK; covers V5 training system, runtime contracts, entrypoints, empirical artifact regression, and Phase 15C checkpoint/runtime boundaries |
| `python -m compileall src\gis_recommend\training\train_v5.py src\gis_recommend\models\v5_final scripts\train_v5.py scripts\train_v5_final_minimal.py scripts\infer_v5_final_minimal.py tests\test_v5_training_system.py tests\test_v5_final_runtime.py tests\test_v5_final_entrypoints.py` | OK |
| `python scripts\train_v5.py --dry-run --no-amp` | Full V5_final training engine validated real quality-gate paths without writing checkpoints: 76,884 workflows, split 61,495 / 7,694 / 7,695 |
| `python scripts\train_v5.py --dry-run --no-amp --subset-preset 1k` | Deterministic subset dry-run validated real quality-gate paths with `train_count=1000`; no `outputs_v2\v5_final_checkpoints` directory was created |
| `python scripts\train_v5.py --subset-preset 1k --epochs 5 --checkpoint-dir outputs_v2\v5_final_reports\stage0\checkpoints --evaluation-report outputs_v2\v5_final_reports\stage0\evaluation_report.json --no-amp --seed 42 --beam-width 5` | Stage0 completed 5 epochs, wrote best/latest checkpoints, history, evaluation JSON/Markdown, and no stderr; no collapse alerts |
| `python scripts\train_v5.py --subset-preset 10k --epochs 30 --patience 30 --batch-size 512 --checkpoint-dir outputs_v2\v5_final_reports\stage1\checkpoints --evaluation-report outputs_v2\v5_final_reports\stage1\evaluation_report.json --no-amp --seed 42 --beam-width 5` | Stage1 completed 30 epochs on CPU, wrote best/latest checkpoints, history, evaluation JSON/Markdown, and no stderr; no collapse alerts; best val loss 2.82443161 |
| `python scripts\build_empirical_evaluation_artifact.py --samples 50 --retrieval-top-k 5 --canonicalization-limit 2000 --out outputs_v2\v5_final_reports\stage1\baseline_empirical_50.json` | Wrote Stage1 50-sample lexical/Markov baseline artifact; lexical LCS 0.443715, Markov2 LCS 0.37923 |
| `python scripts\train_v5.py --disable-pvm --subset-preset 10k --epochs 30 --patience 30 --batch-size 512 --checkpoint-dir outputs_v2\v5_final_reports\a1_no_pvm\checkpoints --evaluation-report outputs_v2\v5_final_reports\a1_no_pvm\evaluation_report.json --no-amp --seed 42 --beam-width 5` | A1 no-PVM run completed on server and was synced locally; 30 epochs, stderr 0, best val loss 3.07014528, comparison artifacts written to `outputs_v2\v5_final_reports\a1_no_pvm\comparison_vs_stage1.*` |
| `python scripts\evaluate_v5_beam_search.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\beam_search_eval --beam-widths 1 3 5 10 --eval-samples 50 --device cpu` | Stage1 checkpoint re-evaluated without retraining; raw-logprob beam summary and decode traces written under `outputs_v2\v5_final_reports\beam_search_eval\` |
| `python scripts\evaluate_v5_beam_search.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\beam_search_eval\length_norm_alpha_1 --beam-widths 1 3 5 10 --eval-samples 50 --device cpu --length-norm-alpha 1.0` | Optional length-normalized beam selection report written; no checkpoint mutation or retraining |
| `python scripts\evaluate_v5_retrieval_assisted.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\retrieval_assisted --eval-samples 50 --beam-width 5 --retrieval-top-k 3 --device cpu` | Minimal lexical retrieval-assisted prototype evaluated; stderr 0; generated `retrieval_assisted_report.json`, Markdown summary, decode traces, and copied/novel operator attribution |
| `python scripts\evaluate_v5_hybrid_planner.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\v5_hybrid_planner_prototype --eval-samples 50 --retrieval-top-k 5 --device cpu` | Retrieval-centered hybrid planner evaluated with the existing Stage1 checkpoint only; wrote `hybrid_planner_report.json`, `hybrid_planner_summary.md`, `attribution_report.json`, `candidate_trace_analysis.json`, stdout/stderr logs. Hybrid LCS 0.46504845 vs retrieval-only 0.44371511; selected candidates were 50/50 identity from retrieval pool. |
| `python scripts\evaluate_v5_hybrid_planner.py --dry-run --eval-samples 3 --output-dir outputs_v2\v5_final_reports\v5_hybrid_planner_prototype_dryrun_check` | Dry-run validated paths/counts without model execution or artifact mutation beyond `dry_run_summary.json`: 76,884 workflows, 61,495 train, 7,695 test, 3 selected eval samples |
| Hybrid artifact schema inspection via `python -c` | Confirmed `hybrid_planner_report.json` schema `gis_recommend.v5_final.hybrid_planner_prototype.v1`, attribution schema `gis_recommend.v5_final.hybrid_attribution.v1`, candidate-trace schema `gis_recommend.v5_final.hybrid_candidate_trace.v1`, and runtime contract flags `v5_full_generation_used_for_hybrid=false`, `retrained_model=false`, `checkpoint_mutated=false` |
| `python scripts\evaluate_v5_hybrid_planner.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --output-dir outputs_v2\v5_final_reports\v5_hybrid_planner_multistage --eval-samples 50 --retrieval-top-k 5 --device cpu` | Multistage retrieval-centered planner evaluated with the existing Stage1 checkpoint only; wrote `hybrid_planner_report.json`, `hybrid_planner_summary.md`, `attribution_report.json`, `candidate_trace_analysis.json`, and logs. Metrics: LCS 0.45586827, SetF1 0.57529907, token accuracy 0.33928243, IO validity 1.0. Rerank/repair contribution 0.0; selected candidates 50/50 identity. |
| `python scripts\build_unified_workflow_benchmark.py --out outputs_v2\v5_final_reports\unified_benchmark\unified_workflow_benchmark.json` | Wrote unified JSON/Markdown benchmark artifact. Rows include `v4_quality_gate_teacher_forced`, `v4_quality_gate_autoregressive`, `set_predictor_quality_gate`, `v5_final_pure_generation`, `retrieval_centered_planner_retrieval_only`, and `retrieval_centered_planner_hybrid`. Protocol flags set `cross_task_metric_mixing_allowed=false` and `teacher_forced_vs_rollout_direct_comparison_allowed=false`. |
| `python scripts\evaluate_retrieval_planning_stages.py --eval-samples 50 --retrieval-top-k 20 --filtered-top-k 10 --repair-max-edits 1 --repair-top-n-sources 1 --repair-max-candidates 80 --output-root outputs_v2\v5_final_reports` | Wrote retrieval filtering, execution-aware rerank, local repair, trace, and summary artifacts. Set Predictor checkpoint is absent locally, so source is recorded as `task_type_operator_frequency_prior`; local repair selected identity for all 50 samples and repair contribution is 0.0. |
| `python scripts\evaluate_repair_oracle_phase.py --eval-samples 50 --retrieval-top-k 20 --max-repair-candidates 100 --substitution-top-k 10 --bridge-top-k 10 --output-dir outputs_v2\v5_final_reports\repair_oracle_phase --device cpu` | Wrote `repair_oracle_report.json`, `repair_failure_taxonomy.json`, `repair_candidate_traces.json`, and `repair_phase_summary.md`. Mean oracle repair gain: LCS +0.12149891 / SetF1 +0.1027359 / token accuracy +0.13011901; repair win rate 0.88; repair selection failure rate 0.88; failure taxonomy dominated by rerank failure. |
| `python -m unittest tests.test_unified_workflow_benchmark tests.test_v5_empirical_experiment_scripts tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 47 tests OK; covers unified benchmark grouping, hybrid multistage retrieval/fusion helpers, safe rerank selection, repair/contribution attribution, empirical experiment scripts, V5 training system, runtime contracts, and Phase 15C checkpoint/runtime boundaries |
| `python -m unittest tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 55 tests OK; covers retrieval filtering, explicit missing Set Predictor checkpoint failure, local repair, execution-aware rerank, unified benchmark, hybrid helpers, V5 training/runtime, and Phase 15C runtime contracts |
| `python -m unittest tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 62 tests OK; covers repair oracle phase, retrieval filtering, explicit missing Set Predictor checkpoint failure, local repair, execution-aware rerank, unified benchmark, hybrid helpers, V5 training/runtime, and Phase 15C runtime contracts |
| `python -m compileall scripts\evaluate_retrieval_planning_stages.py tests\test_retrieval_planning_stages.py` | OK |
| Retrieval planning forbidden-pattern scan | `outputs_v2/v5_final_reports/forbidden_pattern_scan_retrieval_planning.json` reports 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write, graph loss, entropy regularization, alpha anneal, backward, or optimizer-step patterns |
| `python -m compileall scripts\evaluate_repair_oracle_phase.py tests\test_repair_oracle_phase.py scripts\evaluate_retrieval_planning_stages.py tests\test_retrieval_planning_stages.py` | OK |
| Repair oracle forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_oracle_phase/forbidden_pattern_scan_repair_oracle.json` reports 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write/gating, graph loss, entropy regularization, alpha anneal, backward, or optimizer-step patterns |
| `python scripts\evaluate_repair_selection_diagnostics.py --oracle-report outputs_v2\v5_final_reports\repair_oracle_phase\repair_oracle_report.json --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase\repair_candidate_traces.json --output-dir outputs_v2\v5_final_reports\repair_selection_diagnostics --seed 42` | Wrote required diagnostics artifacts. Key results: identity selection 1.0, modified selection 0.0, mean oracle score delta -0.19874815 despite LCS gain +0.12149891, strongest suppressor `edit_penalty`, failure breakdown `edit_oversuppression:44` / `retrieval_saturation:6`, random modified control mean LCS -0.05363936 |
| `python -m unittest tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 69 tests OK |
| `python -m compileall scripts\evaluate_repair_selection_diagnostics.py tests\test_repair_selection_diagnostics.py scripts\evaluate_repair_oracle_phase.py tests\test_repair_oracle_phase.py` | OK |
| Repair selection forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_selection_diagnostics/forbidden_pattern_scan_repair_selection_diagnostics.json` reports `pass` with 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write/gating, graph loss, entropy regularization, alpha anneal, backward, or optimizer-step patterns |
| `python scripts\evaluate_repair_scorer_ablations.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase\repair_candidate_traces.json --oracle-report outputs_v2\v5_final_reports\repair_oracle_phase\repair_oracle_report.json --output-dir outputs_v2\v5_final_reports\repair_scorer_ablations --seed 42` | Wrote scorer ablation artifacts. Best low-corruption policy is `uniform_edit_0_12`: adoption 0.08, corruption 0.02, mean LCS +0.00333333, SetF1 +0.00488889, token accuracy +0.00952381. No-edit penalty and tested piecewise penalties were net negative. |
| `python -m unittest tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 74 tests OK |
| `python -m compileall scripts\evaluate_repair_scorer_ablations.py tests\test_repair_scorer_ablations.py scripts\evaluate_repair_selection_diagnostics.py tests\test_repair_selection_diagnostics.py` | OK |
| Repair scorer ablation forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_scorer_ablations/forbidden_pattern_scan_repair_scorer_ablations.json` reports `pass` with 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write/gating, graph loss, entropy regularization, alpha anneal, backward, or optimizer-step patterns |
| `python scripts\evaluate_repair_oracle_phase.py --checkpoint outputs_v2\v5_final_reports\stage1\checkpoints\best_model.pt --eval-samples 200 --retrieval-top-k 20 --max-repair-candidates 100 --substitution-top-k 10 --bridge-top-k 10 --output-dir outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200 --device cpu` | Generated a larger evaluation-only repair oracle trace. Oracle repair gain remains present: LCS +0.12405501 / SetF1 +0.10355055 / token accuracy +0.17590497; repair selection failure rate 0.85; no training or checkpoint mutation |
| `python scripts\evaluate_repair_calibration_sweep.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200\repair_candidate_traces.json --output-dir outputs_v2\v5_final_reports\repair_calibration_sweep --edit-penalties 0.0 0.08 0.10 0.12 0.14 0.16 0.20 --bootstrap-iterations 500 --subset-sizes 50 100 200 --seed 42` | Wrote `calibration_sweep_report.json`, `calibration_stability_analysis.json`, `calibration_summary.md`, `calibration_curves.csv`, and `forbidden_pattern_scan_calibration.json`. No tested penalty is stable-positive; 0.0 collapses, 0.08 over-adopts, `0.12` is not confirmed beyond the 50-sample trace |
| `python -m unittest tests.test_repair_calibration_sweep tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 78 tests OK |
| `python -m compileall -q scripts\evaluate_repair_calibration_sweep.py tests\test_repair_calibration_sweep.py scripts\evaluate_repair_scorer_ablations.py tests\test_repair_scorer_ablations.py` | OK |
| Repair calibration forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_calibration_sweep/forbidden_pattern_scan_calibration.json` reports `pass` with 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write/gating, graph loss, entropy regularization, alpha anneal, backward, optimizer step, or `torch.optim` patterns |
| `python scripts\evaluate_repair_opportunity_analysis.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200\repair_candidate_traces.json --transition-matrix outputs_v2\transition_allowed_next.json --output-dir outputs_v2\v5_final_reports\repair_opportunity_analysis --bootstrap-iterations 300 --seed 42` | Wrote `repair_opportunity_analysis.json`, `repair_success_correlations.json`, `repair_failure_taxonomy_v2.json`, `repair_locality_analysis.json`, `opportunity_prediction_summary.md`, `opportunity_signal_table.csv`, and `forbidden_pattern_scan_repair_opportunity.json`. Sample count 200; repair success rate 0.85; harmful rate 0.005; failure taxonomy dominated by scorer ranking failure 0.85. |
| `python -m unittest tests.test_repair_opportunity_analysis tests.test_repair_calibration_sweep tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 83 tests OK |
| `python -m compileall -q scripts\evaluate_repair_opportunity_analysis.py tests\test_repair_opportunity_analysis.py` | OK |
| Repair opportunity forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_opportunity_analysis/forbidden_pattern_scan_repair_opportunity.json` reports `pass` with 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write/gating, graph loss, entropy regularization, alpha anneal, backward, optimizer step, or `torch.optim` patterns |
| `python scripts\evaluate_repair_confidence_regimes.py --candidate-traces outputs_v2\v5_final_reports\repair_oracle_phase_heldout_200\repair_candidate_traces.json --output-dir outputs_v2\v5_final_reports\repair_confidence_regimes --bootstrap-iterations 500 --random-iterations 200 --min-sample-count 10 --seed 42` | Wrote `repair_confidence_regime_report.json`, `repair_subtype_statistics.json`, `repair_context_analysis.json`, `precision_first_regimes.json`, `bootstrap_regime_validation.json`, `random_control_comparison.json`, `summary.md`, and `forbidden_pattern_scan_confidence_regimes.json`. Sample count 200; candidate count 19,919; modified candidates 19,719; score-selected high-confidence regimes 0; oracle-only high-confidence subspaces 12. |
| `python -m unittest tests.test_repair_confidence_regimes tests.test_repair_opportunity_analysis tests.test_repair_calibration_sweep tests.test_repair_scorer_ablations tests.test_repair_selection_diagnostics tests.test_repair_oracle_phase tests.test_retrieval_planning_stages tests.test_v5_empirical_experiment_scripts tests.test_unified_workflow_benchmark tests.test_v5_training_system tests.test_v5_final_runtime tests.test_phase15c_runtime_contract -v` | 88 tests OK |
| `python -m compileall -q scripts\evaluate_repair_confidence_regimes.py tests\test_repair_confidence_regimes.py` | OK |
| Repair confidence forbidden-pattern scan | `outputs_v2/v5_final_reports/repair_confidence_regimes/forbidden_pattern_scan_confidence_regimes.json` reports `pass` with 0 matches for `strict=False`, `weights_only=False`, learned gamma, gated write/gating, graph loss, entropy regularization, alpha anneal, backward, optimizer step, or `torch.optim` patterns |
| Consolidation document content verification | Python verifier checked `docs/v5_system_consolidation_protocol.md`, `docs/PROJECT_CONTEXT.md`, and `docs/PROJECT_CONTEXT.zh-CN.md` for required final identity, architecture semantics, empirical hierarchy, failure synthesis, governance consolidation, production interpretation, research roadmap, and deployed/experimental/oracle-only boundaries; result: `content verification passed` |
| `python -m unittest tests.test_workflow_usability` | 5 tests OK |
| `python scripts\evaluate_workflow_usability.py --eval-samples 200` (v2, 2026-05-13) | 200 samples evaluated. Top-1 usable rate 0.5600, Top-3 any usable 1.0000, Top-5 any usable 1.0000, mean usability score 0.7663 (bootstrap 95% CI [0.7552, 0.7780]), mean QGIS mapping 0.6365, mean logic consistency 0.9368, mean step coverage 0.6197, reference usability 0.7207. 533 commutative pairs, 76/94 L3 codes have QGIS mappings. All 7 artifacts generated. |
| Workflow usability artifact sanity check (v2) | 7 artifacts exist: `workflow_usability_report.json`, `topk_usable_statistics.json`, `workflow_failure_taxonomy.json`, `usable_workflow_examples.json`, `unusable_workflow_examples.json`, `per_task_usability_breakdown.csv`, `workflow_usability_summary.md`. |
| `python -m unittest tests.test_multi_reference_workflows` | 6 tests OK |
| `python -m compileall -q scripts\evaluate_multi_reference_workflows.py tests\test_multi_reference_workflows.py` | OK |
| `python scripts\evaluate_multi_reference_workflows.py --output-dir outputs_v2\v5_final_reports\multi_reference_evaluation --bootstrap-iterations 500 --seed 42` | Wrote multi-reference artifacts for 369 records. Conservative exact-task reference pools have mean reference count 1.0 and multi-reference record rate 0.0, so raw multi-reference deltas are 0.0; canonicalized multi-reference recovers EM +0.00542005, LCS +0.0173991, token accuracy +0.06013034, SetF1 +0.01039799. |
| Multi-reference artifact sanity check | Required JSON/CSV/Markdown artifacts exist; `forbidden_pattern_scan_multi_reference.json` reports `pass` with 0 matches. |
| `python -m compileall scripts\build_unified_workflow_benchmark.py tests\test_unified_workflow_benchmark.py scripts\evaluate_v5_hybrid_planner.py tests\test_v5_empirical_experiment_scripts.py` | OK |
| Unified benchmark forbidden-pattern scan | `rg` over `scripts/build_unified_workflow_benchmark.py` and `tests/test_unified_workflow_benchmark.py` found no `strict=False`, `weights_only=False`, learned gamma, gated write, graph loss, entropy regularization, alpha annealing, training/backward/optimizer calls, runtime governance objects, or `gis_recommend.evidence` imports |
| V5 hybrid script forbidden-pattern scan | `rg` over `scripts/evaluate_v5_hybrid_planner.py` and `tests/test_v5_empirical_experiment_scripts.py` found no `strict=False`, `weights_only=False`, learned gamma, gated write, graph loss, entropy regularization, alpha annealing, training/backward/optimizer calls, runtime governance objects, or `gis_recommend.evidence` imports |
| `python scripts\train_v4_quality_gate.py --dry-run` | Quality-gate Transformer launcher still validates cleanly on local `outputs_v2`: 76,884 workflows, split 61,495 / 7,694 / 7,695, 47 task types, vocab 98, checkpoint dir `outputs_v2\transformer_checkpoints_v4_2_quality_gate`. |
| `python scripts\train_set_predictor_quality_gate.py --dry-run` | Previous local dry-run validated quality-gate inputs cleanly: 76,884 workflows, split 61,495 / 7,694 / 7,695, 47 task types, 47 active tokens. After 2026-05-14 path alignment, the launcher default checkpoint dir is `outputs_v2\set_predictor_checkpoints_v3_quality_gate_v4_6`; rerun dry-run before the next local full training. |
| `python scripts\smoke_v4_quality_gate_training_entry.py --batch-size 2 --max-samples 2 --split train` | V4 quality-gate training-entry smoke still passes locally on CPU. Loaded v2 embeddings for 94 tokens and produced logits shape `[2, 100, 98]` with no checkpoint writes. |
| 2026-05-13 V4 full-flow path audit | Confirmed current practical V4 line is `quality_gate` training plus v2 QGIS grounding, with V4.6 as the intended final practical checkpoint family. Generic V4 inference/evaluation CLIs are not yet quality-gate-safe by default. Local blockers for a full end-to-end rerun remain missing server artifacts: `outputs_v2/transformer_checkpoints_v4_6_quality_gate/`, `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/`, plus optional `outputs_v2/qgis_operator_io_types.json`. The quality-gate `task_type_length_stats.json` artifact now exists under `outputs_v2/pipeline/step8_quality_gate/`. |

## Open Work

| Priority | Task | Notes |
| --- | --- | --- |
| High | Run the oversampled QGIS-vector warmstart SFT on the server | `outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/` is structurally trainable and raises QGIS train share to 4,253/65,748 = 6.5%. Use the expanded DPO v2 47->48 warmstart, pass the oversampled `task_type_length_stats.json`, and write checkpoints to a separate `_oversampled_warmstart` directory. After training, evaluate with `scripts/evaluate_vector_generalization.py` using explicit oversampled SFT checkpoint/vocab/length-stats overrides. |
| High | Use broader QGIS vector records for weak supervision and coverage mining | Keep the broader 1,598 pure-vector records for preference construction, missing-L3 bridge prioritization, and coverage mining. Do not train the full canonical vector dataset as clean SFT without revalidation. |
| High | Improve fine-grained vector-family learning beyond vector-token regime shift | The unseen benchmark proves SFT shifts vector prompts away from raster-template collapse, but family recall remains low and concentrated. Next data/training work should oversample or add preference/SFT rows for zero-hit families: dissolve, geometry repair/cleanup, clip, intersection, difference, attribute filter, CRS transform, field calculation, export, grid/centroid, table join, and overlay subtypes. |
| High | Merge semantic-tag enrichment with facts-text indexing and rebuild open landing v3 | Current `+sem tags` run improved diversity but dropped modality to 84% because enrichment rebuilt a dataset without facts text. Update the retrieval/eval build path so semantic tags and `Task Name` / `Task Description` coexist, then regenerate v3 and rerun the 80-task open landing evaluation. |
| High | Expand fine-grained QGIS bridge/native bridge for failed open landing tasks | Prioritize missing operator intents from the manual audit: mergevectorlayers, difference/erase, spatial/attribute joins, extractbyexpression, extractbylocation, fixgeometries, simplifygeometries, creategrid, voronoi/thiessen, heatmap, nearest, polygonstolines, centroids, split/snap, deleteholes, delete duplicates, field calculator, saveselectedfeatures/export. |
| High | Expand raster/mixed QGIS bridge coverage beyond clip/warp templates | Prioritize zonalstatistics, polygonize, rasterize alignment, rastersampling, fillnodata/interpolation, reclassify/threshold/rastercalculator, contour, hillshade, buildvirtualraster/merge, cost distance, random points in polygons, raster-to-points, table export, and area/statistics summaries. |
| High | Re-run the 80-task open landing audit after bridge expansion | Success criterion should be strict manual grade improvement, not modality. Target first pass: reduce C rate below 40% and reduce top template concentration below 25%. |
| High | Regenerate or provenance-stamp Step6-8 v2 artifacts before training/evaluation | Current `outputs_v2` artifacts predate provenance reporting and still emit `missing_provenance`; do not rerun full training |
| High | Review quality-gate quarantine hotlist and decide reintegration policy | 30,515 workflows were quarantined due to low-confidence `auto_remap`; reviewing high-impact operators may recover useful L3/task coverage without reintroducing label noise |
| High | Sync raw V4 quality-gate and Set Predictor result artifacts from the server | The unified benchmark currently records V4 TF/AR and Set Predictor metrics as user-reported external values. For the final practical line, sync `outputs_v2/transformer_checkpoints_v4_6_quality_gate/` and `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/`; keep older V4.2 artifacts only as historical comparison material. |
| High | Ingest controlled current-v2 model predictions into the empirical artifact schema | Baseline-only `outputs_v2` empirical artifact infrastructure now exists, and V5_final training/evaluation can emit storage-only model records. Once a matching v2/V5 checkpoint exists, populate the same per-sample schema with real model predictions, beam candidates, decode metadata, candidate pools, and oracle candidate metrics. |
| High | Continue conditional repair diagnostics without production scoring changes | Stage0/Stage1, A1 no-PVM, beam-search re-eval, retrieval-assisted generation, hybrid/multistage planner, repair oracle, repair-selection diagnostics, scorer ablations, 200-sample calibration sweep, repair opportunity analysis, and repair confidence-regime search now exist. Stage2 full training remains blocked. No tested uniform penalty is stable-positive, broad opportunity indicators are not discriminative, and no score-selected high-confidence repair regime has been found; future work should focus evaluation-only on scorer discrimination/calibration metrics before any production scoring change. |
| High | Treat `docs/v5_system_consolidation_protocol.md` as the long-term claim-boundary reference | Future reports should use its deployed/experimental/oracle-only distinction and capability hierarchy before making claims about generation, repair, rerank, retrieval, set prediction, or execution awareness. |
| High | Curate bounded ontology rows before any semantic-indexing integration | The new inventory is deliberately offline. Before future semantic retrieval/rerank work, manually review the 13 exact GEE<->QGIS candidates and keep partial/execution-sensitive/ambiguous/composite rows out of runtime equivalence. GDAL/ArcGIS remain unsupported until real mapping assets are built. |
| High | Run controlled quality-gate training when ready | Use `scripts/train_v4_6_quality_gate.py` for the final practical Transformer line and a matching V4.6 quality-gate Set Predictor artifact. The Transformer launcher expects `outputs_v2/transition_allowed_next.json`; rebuild it first if the candidate split changes. Do not use the original default `train_v4_2.py` or `train_set_predictor_v3.py` for the quality-gate experiment. |
| High | Resolve GEE alias gaps before downstream code generation | Candidate alias audit still has 10 unresolved official-name operators, including `ee.imagecollection.filtermetadata`, `ee.imagecollection.clip`, `ee.classifier.randomforest`, and `ee.algorithms.snic` |
| High | Review remaining old hardcoded paths in non-primary scripts | Known examples include old evaluation/inference/training utilities with `classification_hierarchy.csv`, `outputs/l3_embeddings.pt`, or 350 vocab assumptions |
| High | Remeasure or annotate affected historical Step8 + V4.6 reports | The token contract is fixed in code, but old reports may have biased sequence metrics. Recompute important V4.6 reports under `v2_94_l3` before using them for checkpoint selection, MR ablation, or paper claims. |
| High | Generate or explicitly profile v2 QGIS I/O metadata | `gis-evaluate` no longer silently reads legacy I/O metadata. If Level-1 executable/I/O diagnostics are needed for mainline reports, create `outputs_v2/qgis_operator_io_types.json`; otherwise reports should state `fallback_status=missing`. Use `--allow-legacy-io-types` only for explicit compatibility runs, not mainline claims. |
| Medium | Keep V4-QG artifacts isolated as research/candidate unless the mainline decision changes | `evaluate_v4_quality_gate.py`, V4-QG planner, and config comments are now non-mainline/research-labeled. If V4-QG is ever promoted, create a new explicit profile and update lineage/contracts instead of reusing current Step8 + V4.6 report semantics. |
| High | Connect real V4-QG and Set Predictor checkpoints into the Phase 1 planner | `scripts/run_v4_qg_planner.py` now defaults to the V4.6 Set Predictor path `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth`. Local artifacts are still absent in this workspace; sync the server-trained Transformer/Set Predictor checkpoints or pass explicit paths before claiming real V4 AR/Set Predictor candidate contribution. |
| High | Run controlled MR training ablation only on explicit request | Isolated inputs now exist under `outputs_v2/v4_qg_mr_ablation/` (`mr_5`, `mr_10`, `mr_all_42`). Do not start training by default and do not overwrite quality-gate baseline/checkpoints. If training is requested, train into separate output dirs and compare against the quality-gate baseline with TopK usable, diversity, invalid/harmful rate, canonicalized LCS/SetF1/token metrics, and exact match only as secondary. |
| High | Rerun V4.6 baseline/MR controls after the AR-SS fix | The 2026-05-17 `mr_all_42` run used pre-fix AR-SS logic where dynamic-min-length END masking could make CE loss infinite. Before training `mr_5`/`mr_10`, rerun at least a short same-policy V4.6 quality-gate baseline through epoch 11+ and decide whether ablation comparison should use latest epoch, best validation epoch, or a fixed epoch. |
| High | Use the MR comparator after real ablation reports exist | The read-only comparator now exists, but no `mr_*` model training/evaluation reports exist yet. After explicit training/evaluation, run `scripts/compare_mrv_training_ablation.py --baseline-report <baseline_report> --variant-report mr_5=<report> ... --manifest outputs_v2\v4_qg_mr_ablation\mrv_training_ablation_manifest.json` and interpret only metrics actually present in those input reports. |
| High | Calibrate evidence-aware ranking before any runtime selector change | The 2026-05-23 offline smoke shows promising LCS/SetF1 gains but lower TokenAcc and slightly worse oracle match than legacy. Next work should evaluate the policy on larger reports, split by task type/source/metric family, and tune or reject policy terms before any gated runtime selection. Do not continue adding observation-only Phase5.x fields as a substitute for ranking remediation. |
| High | Await server-side baseline and `mr_all_42` training artifacts | The user will train on the server. Required return artifacts are baseline checkpoint/report, `mr_all_42` checkpoint/report, exact commands or config, eval split/sample count/parameters, and any training logs/errors. Keep `mr_5` and `mr_10` blocked until `mr_all_42` comparison shows no negative signal. |
| High | Keep V5 implementation inside the minimal runtime semantic kernel | Do not add governance authority. The only plausible new runtime-authoritative object is a thin frozen `role -> callable` dispatch registry. `RuntimeProfile`, `CheckpointManifest`, `DatasetLineage`, `GradientProfile`, `MetricRecord`, `CompatibilityResult`, and `DecodePolicy` outside an activated eval/inference call must remain DTOs, snapshots, pure validation returns, or archaeology/reporting artifacts |
| High | Keep execution purity guarded during future edits | Main runtime paths are now report-only for provenance/audit/repair and strict for checkpoint loading. Remaining risk is regression: do not import `gis_recommend.evidence` into training/inference/models/pipelines, do not restore raw/partial checkpoint fallback, and do not use test-only `test_mvcs_closure_harness.py` counterexamples as implementation patterns |
| Medium | Decide whether default QGIS mapping count should be 438 or full 447 | Current default keeps reviewed/manual overrides but still filters ordinary low-confidence auto mappings; `min_confidence=0.0` loads 447 |
| Medium | Add KG build provenance | KG outputs should record hierarchy path/count and id mappings path/hash to avoid silent 350-L3 rebuilds |
| Medium | Harden optional KG instance-layer import if it becomes mainline-relevant | `scripts/import_gee_workflows_v2.py` still has hardcoded paths/connection assumptions for optional workflow-instance import. Current Step8 + V4.6 mainline KG use is ontology/mapping-centric, so do not run that instance importer on the server until its paths and credentials are explicitly reviewed. |
| Medium | Promote empirical artifact generation into routine evaluation | The standalone empirical builder now records retrieval-only, Markov, sequence entropy, task ambiguity, canonicalization, and decode-policy summaries. Next step is to call or mirror it from the normal evaluation pipeline without allowing diagnostics to gate runtime. |
| Low | Clean old temp/cache artifacts if desired | `.pytest_cache`, `codex_tmp`, and generated test temp dirs exist; cleanup should be explicit and non-destructive |

## Next Recommended Actions

1. If the quality-gate candidate or split changes, rebuild `outputs_v2/transition_allowed_next.json` with `scripts/build_quality_gate_transition_matrix.py`.
2. Start controlled Transformer training through `scripts/train_v4_6_quality_gate.py`, not the original `train_v4_2.py` default `main()`, so the run uses quality-gate candidate paths, the v2 transition matrix, and the separate `outputs_v2/transformer_checkpoints_v4_6_quality_gate` checkpoint directory.
3. For full-system evaluation with set prior enabled, train or sync the matching Set Predictor for the V4.6 quality-gate line so the planner reads `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6`.
4. After a matching quality-gate checkpoint exists, ingest controlled model predictions into `gis_recommend.empirical_evaluation.v1`; keep the current baseline-only smoke artifact as the reference schema and baseline floor.
5. For retrieval-centered planning, do not productionize the `uniform_edit_0_12` result, broad repair-opportunity indicators, or oracle-only confidence regimes. The 200-sample calibration sweep made the uniform penalty unstable/negative, the opportunity analysis shows broad indicators are not selective, and the confidence-regime search found 0 score-selected deployable regimes. Next scorer work should stay evaluation-only and measure scorer discrimination/calibration while keeping retrieval/rerank/repair/generation contributions separate.
6. Use `docs/v5_system_consolidation_protocol.md` as the project-level claim-boundary reference in future reports. Keep retrieval/rerank/repair/generation/set/execution contributions separated as deployed, experimental, or oracle-only evidence.
7. Treat `outputs_v2/v5_final_reports/bounded_ontology_inventory/` as an offline ontology inventory only. If semantic indexing is revisited, start from manual review of the 13 exact GEE<->QGIS candidates and do not infer GDAL/ArcGIS mappings without new assets.
8. Review the quarantine hotlist in `outputs_v2/pipeline/step8_quality_gate/quality_gate_report.md`; decide which high-impact `auto_remap` operators should be manually corrected and restored versus kept quarantined.
9. Resolve the 10 unresolved official-name aliases in `outputs_v2/pipeline/step8_quality_gate/gee_operator_alias_audit.md` before L3->GEE code generation.
10. Regenerate Step6-8 under `outputs_v2` with the new provenance gate, or create an explicit controlled provenance-stamping path if regeneration is not desired.
11. Re-run `python scripts/audit_pipeline_outputs.py --outputs-dir outputs_v2 --require-provenance --fail-on-warning` for a report-only provenance check, then resolve/accept the remaining Step3 drop warning.

## Current Scientific Consensus (2026-05-10)

This section is the canonical inherited project state for future sessions. It synthesizes all empirical findings, governance protocols, and scientific boundaries established through May 2026. `docs/v5_system_consolidation_protocol.md` is the project-level synthesis for final system identity, production interpretation, and claim boundaries. Read both before interpreting any artifact or making claims about the system.

### A. Current Runtime Understanding

**IMPORTANT: This section describes the CURRENT EMPIRICALLY VALIDATED RUNTIME, which operates primarily at the operator-token level (L3 of the target architecture).** This is a simplification for empirical tractability. See Section A.0 for the preserved long-term architecture target (L1→L2→L3→platform). The task families below describe the current runtime's operational modes, not the final architecture.

The current runtime consists of **three empirically distinct task families**, each with different learning difficulty:

**Task Family A — Operator-Set Prediction.** Predict WHICH operators appear in a workflow, ignoring order. Implemented as a multi-label classifier (Set Predictor V3) over 47 active operator tokens. This is the most learnable formulation: SetF1 = 0.711 from task text alone. The remaining ~29% is irreducible set-level ambiguity.

**Task Family B — Retrieval-Centered Workflow Planning.** Retrieve, rerank, and optionally repair training exemplars. This is the **current strongest overall strategy**. The system retrieves similar training workflows by lexical/embedding similarity, reranks candidates via a scoring function, and may apply constrained local edits. V5_final serves as a **complete-candidate scorer** in this paradigm, not as a generator. Key components: retrieval (C_ret), reranking (C_rank), repair (C_rep), IO constraint enforcement (C_io).

**Task Family C — Autoregressive Workflow Generation.** Generate operator sequences from scratch via AR decoding. Implemented as V5_final: a memory-augmented AR planner with PVM retrieval attention, fixed temporal decay, training-only alpha noise, and IO-constrained beam decode. This is empirically the **weakest formulation**.

**Set Predictor** is a separate model (multi-label classifier) that provides operator-set-level evidence. It is NOT a workflow generator. Its SetF1 = 0.711 is the operator-set prediction ceiling from task text.

**V5_final** is an AR sequence model that predicts operators directly (~150-class vocabulary), bypassing the L3 intermediate representation used by V4. In the retrieval-centered paradigm, it functions as a candidate scorer, not a generator.

**Final current runtime identity:** the validated system is retrieval-centered, execution-aware, rerank-driven, and constrained-planning-oriented. Retrieval preservation dominates current performance. Generation is not the primary validated capability, and repair is not production-deployable under current evidence. This describes the current L3-level runtime; the long-term architecture target (L1→L2→L3) is preserved separately (see A.0).

**Critical vocabulary distinction:** V4 predicts L3 primitives (98-class); V5 predicts operators directly (~150-class). Direct token-level comparison between V4 and V5 is INVALID. Only operator-sequence metrics (LCS, SetF1, EM) enable cross-version comparison.

**Current runtime implementation is FROZEN.** The V5_final neural architecture, training objectives, loss functions, and module designs must not be modified unless: (a) retrieval-centered planning reaches LCS ceiling, (b) scorer calibration is exhausted, (c) repair contribution is maximized, AND (d) a controlled ablation proves the neural architecture is the binding constraint. None of these conditions currently hold.

**The long-term architecture target is PRESERVED and DISTINCT from the current runtime.** See A.0 below.

#### A.0 CRITICAL: Current Runtime vs. Long-Term Architecture Target

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  SEMANTIC-DRIFT WARNING:                                         │
│                                                                 │
│  Recent consolidation documents describe the CURRENT             │
│  EMPIRICALLY VALIDATED RUNTIME. They do NOT describe the         │
│  LONG-TERM ARCHITECTURE TARGET.                                  │
│                                                                 │
│  Conflating the two causes ARCHITECTURE COLLAPSE: the            │
│  flattening of a layered semantic architecture into a            │
│  single-level operator-token retrieval system.                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**The Original Architecture (Preserved):**

```
Natural-language Task Description
        │
        ▼
┌──────────────────────────────────────────┐
│  L1 — ALGORITHM CATEGORY                  │
│  e.g., "Spatial Analysis", "Hydrology",   │
│  "Image Processing"                        │
│  Coarse-grained task classification.       │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│  L2 — PLATFORM-INDEPENDENT SEMANTIC       │
│       INTENT (CORE ARCHITECTURAL LAYER)    │
│  e.g., "Buffer region around features",    │
│  "Compute slope from elevation",           │
│  "Intersect two polygon layers"            │
│                                             │
│  Describes WHAT the workflow must          │
│  accomplish WITHOUT committing to HOW      │
│  any specific platform implements it.       │
│                                             │
│  This is NOT an optional convenience       │
│  layer. It is the architectural foundation  │
│  for cross-platform workflow reasoning.     │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│  L3 — PLATFORM-SPECIFIC OPERATORS         │
│  e.g., QGIS "Buffer vectors",             │
│  ArcGIS "Buffer_analysis",                │
│  GEE "ee.Image.zeroCrossing"              │
│                                             │
│  Maps each L2 semantic intent to the      │
│  concrete operators available on a        │
│  specific platform. Different platforms    │
│  have different operator names, parameter  │
│  conventions, and capability subsets.      │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│  EXECUTABLE WORKFLOW                      │
│  Platform-specific operator chain with    │
│  valid I/O connections, parameters, and   │
│  execution semantics.                     │
└──────────────────────────────────────────┘
```

**What the Current Runtime Actually Does:**

The current empirically validated system operates PRIMARILY at the L3 operator-token level:

- V5_final predicts operator tokens directly (~150-class vocabulary of platform-specific operator names).
- Retrieval retrieves operator sequences from training data (platform-specific).
- Reranking scores candidate operator sequences (platform-specific).
- Repair modifies operator tokens locally (platform-specific).

This is a DELIBERATE SIMPLIFICATION for empirical tractability. It is NOT a permanent architectural commitment to operator-level-only reasoning. The current system flattens L1→L2→L3 into a single prediction task because:

1. The quality-gate training data provides operator sequences with L3 labels but without explicit L2 semantic intent annotations.
2. Building the L2 semantic ontology is a separate, substantial data-engineering task.
3. Demonstrating that retrieval at the operator level outperforms AR generation at the operator level is a necessary empirical milestone, not a statement that semantic layers are unnecessary.

**Why the Empirical Findings STRENGTHEN the Case for L2 Semantic Abstraction:**

| Current Problem | Root Cause | How L2 Abstraction Helps |
|-----------------|------------|--------------------------|
| V5 pure generation LCS = 0.25 | Task-text→operator gap is too large for direct AR | L2 provides intermediate semantic targets, reducing the prediction gap |
| Retrieval corpus depends on platform-specific exemplars | No cross-platform training data | L2 enables platform-independent retrieval, expanding the effective corpus |
| Operator vocabulary is ~150 and platform-entangled | Platform-specific operator names | L2 vocabulary (~50-80 semantic intents) is smaller, more stable, and platform-agnostic |
| Repair candidates are operator-substitution-only | No semantic equivalence mapping | L2 operators have defined equivalence classes across platforms |
| Set Predictor learns "which operators" from task text | Learns platform-specific co-occurrence, not semantic membership | L2 set prediction would learn WHY operators co-occur, enabling transfer |
| Raw exact match = 0.0 under strict sequence scoring | Operator sequences differ even for reordered or near-equivalent workflows; canonicalized evaluation recovers only a small subset | L2 sequences or governed canonical forms could normalize some variants, but current evidence only supports narrow evaluation-layer correction |

**Critical Anti-Collapse Rule:**

```
"The fact that operator-level retrieval currently outperforms
 operator-level AR generation does NOT imply that semantic
 intermediate layers are unnecessary.

 It implies that:
 (a) the operator-level prediction problem is hard,
 (b) retrieval is a stronger strategy than generation at that level,
 (c) the semantic gap between task text and operator tokens is large,
 (d) bridging that gap through intermediate semantic abstraction
     is a promising direction that the current runtime has not
     yet implemented, not a direction that has been disproven."
```

**What IS FROZEN vs. What is PRESERVED:**

| Aspect | Status | Meaning |
|--------|--------|---------|
| V5_final neural architecture (PVM, AR decoder, memory slots) | **FROZEN** | Do not modify modules, losses, or training objectives |
| Current operator-token retrieval runtime | **FROZEN** | Retrieval-centered planning is the validated paradigm |
| L1→L2→L3 semantic hierarchy | **PRESERVED** | This is the target architecture; current runtime is an L3-level simplification |
| L2 semantic intent layer | **PRESERVED** | Core architectural component; implementation deferred, not abandoned |
| Cross-platform abstraction | **PRESERVED** | The project goal remains QGIS + ArcGIS + GEE, not QGIS-only |
| New neural architectures for L2→L3 mapping | **FROZEN** | Cannot be proposed without meeting reopening criteria |
| L2 ontology construction (non-neural, data engineering) | **ALLOWED** | Building the L2 taxonomy is data work, not architecture redesign |
| Retrieval at L2 semantic level (non-neural) | **ALLOWED** | Retrieving L2 intents instead of L3 operators is a data-level change, not architectural |

### B. Unified Benchmark Interpretation

All results reference the **quality-gate dataset** (76,884 workflows, 47 task types, train/val/test = 61,495/7,694/7,695). This dataset was filtered from the broader 107,399-workflow set to remove low-confidence auto-remap noise and cross-split sequence leakage.

**Benchmark rows by task family (operator-sequence outputs, ~150-class vocabulary):**

| System | Task Family | LCS | TokenAcc | SetF1 | EM | IO Validity |
|--------|-------------|-----|----------|-------|-----|-------------|
| Set Predictor (quality-gate) | A (set) | N/A | N/A | **0.711** | N/A | N/A |
| Lexical retrieval (top-1) | B (retrieval) | 0.444 | 0.237 | 0.567 | 0.0 | 1.0 |
| Retrieval-centered planner (multistage) | B (hybrid) | **0.456** | **0.339** | 0.575 | 0.0 | 1.0 |
| V5_final pure generation (greedy) | C (generation) | 0.247 | 0.091 | 0.360 | 0.0 | 1.0 |
| Markov2 | baseline | 0.379 | N/A | N/A | 0.0 | N/A |

**V4 reference rows (L3 tokens, 98-class — DIFFERENT TASK, context only):**

| System | Task | Top1 | Top5 | AR-TokAcc | TF-SeqEM | AR-SeqEM |
|--------|------|------|------|-----------|----------|----------|
| V4.2 TF (quality-gate, 61K, 60ep) | L3 token (TF) | 48.3% | 71.3% | N/A | 2.3% | N/A |
| V4.2 AR (quality-gate, 61K, 60ep) | L3 token (AR) | N/A | N/A | 21.1% | N/A | 0.0% |

**Invariant facts:**
- Raw exact match (EM) is 0.0 for the reported benchmark rows. This is largely an evaluation property (76,884 unique test sequences, high combinatorial space), not a standalone model-failure proof. A later evaluation-only canonicalized pass over 369 persisted prediction records recovered 2 exact matches and improved LCS/token accuracy/SetF1, showing metric underestimation from valid local reorderings, but canonicalized EM remains very low.
- IO validity = 1.0 for all IO-constrained systems.
- Retrieval-centered planning LCS (0.46) >> pure generation LCS (0.25).
- Set Predictor F1 (0.711) is the set-level ceiling; V5 SetF1 (0.360) is ~50% of ceiling.

**Forbidden comparisons:**
1. V4 teacher-forced metrics (Top1, TF-SeqEM) vs V5 rollout metrics (TokenAcc, LCS) — different prediction modes.
2. V4 token-level metrics vs V5 token-level metrics — different prediction tasks (L3 vs operators).
3. Retrieval-centered planning metrics framed as pure generation capability.
4. Set Predictor SetF1 framed as sequence planning accuracy.
5. Any cross-family comparison without explicit task/mode/scope/vocabulary alignment.

### C. What Has Been Empirically Demonstrated

1. **Retrieval-centered planning substantially outperforms pure AR generation.** Retrieval LCS ≈ 0.46 vs generation LCS ≈ 0.25. This gap is large and stable across all evaluation configurations.

2. **Repair opportunities exist in the oracle.** Oracle repair gain: LCS +0.12, repair win rate 0.88, corruption rate 0.02. When an oracle selects among local edit candidates (substitution, bridge insertion, deletion, swap), useful repairs are frequently available with low corruption risk.

3. **The scorer oversuppresses edits.** The edit_penalty term is the strongest suppressor across all 4,939 modified candidates. Identity selection frequency = 1.0; modified selection frequency = 0.0. The deployed scorer never selects a non-identity repair candidate.

4. **Removing edit penalty entirely is harmful.** No-edit-penalty adopts 100% of repairs but degrades mean LCS (-0.013) with 32% corruption. Edit penalty is necessary as a safety term but is over-strong at 0.20.

5. **No stable global repair calibration has been found.** The 200-sample calibration sweep tested uniform edit penalties 0.0-0.20. No tested penalty is stable-positive on bootstrap intervals. 0.0 collapses (corruption 0.32), 0.08 over-adopts (corruption 0.18), and 0.12 has mean LCS -0.001 with CI crossing zero. The 50-sample hint at penalty 0.12 was NOT confirmed at larger scale.

6. **High-confidence repair regimes have not been found under current score selection.** The 200-sample confidence-regime search found 0 score-selected low-corruption regimes. It did find 12 oracle-only subspaces, which is candidate-existence evidence only and not a deployable repair policy.

7. **Set Predictor contains meaningful signal.** SetF1 = 0.711 from task text alone proves operator set membership is substantially predictable. This is an upper bound: sequence models must additionally predict order, making their task strictly harder.

8. **V5_final trains stably without collapse.** Stage 1 (10K subset, 30 epochs) completed with no collapse on any of six stability criteria. The model learns (Top5 token accuracy = 62.1%) but its argmax (TokenAcc = 9.1%) is poor.

9. **PVM retrieval attention is functional.** Alpha entropy = 0.822, slot utilization = 0.367. Memory retrieval is active (not collapsed to uniform), though slot utilization suggests underuse of available capacity.

10. **IO-constrained decoding works.** IO validity = 1.0 across all IO-constrained systems.

11. **Random modified-candidate selection is harmful.** Mean LCS -0.054. Repair acceptance without calibrated scoring destroys retrieval value.

### D. What Has Failed

1. **Naive full AR planning.** V5_final pure generation LCS = 0.25, TokenAcc = 0.09, substantially below retrieval baselines (LCS 0.46, TokenAcc 0.34) and Markov2 (LCS 0.38). Pure autoregressive generation from task text alone is not currently viable.

2. **Unrestricted repair adoption.** No-edit-penalty and piecewise-penalty configurations all produce net-negative mean LCS with corruption rates > 0.25. Accepting repairs without calibrated scoring is destructive.

3. **Global uniform edit calibration.** No single edit penalty value works stably across the 200-sample evaluation set. The relationship between edit penalty and repair quality is non-uniform across task types and candidate pools.

4. **Precision-first confidence gating under current score selection.** The high-confidence regime search found no score-selected regime with low corruption, positive mean LCS/token accuracy, and bootstrap support. Oracle-only regimes must not be treated as runtime gates.

5. **Retrieval-assisted generation for improvement.** When V5_final is allowed to modify retrieved candidates through generation (rather than constrained local edits), it does not improve over the unmodified retrieval. Rerank contribution = 0.0, repair contribution = 0.0 under safe policies.

6. **Exact-match evaluation.** Raw EM is 0.0 for the main benchmark rows, and even canonicalized EM only recovers a small number of cases (2/369 in the current evaluation-only report). Strict EM therefore provides poor discrimination and should not be the primary workflow-planning metric.

7. **Architecture-as-bottleneck hypothesis.** Architecture is ranked #8 of 8 identified bottlenecks. The dominant bottlenecks are supervision ambiguity, scorer calibration, data imbalance, and ontology gaps.

### E. Current Bottleneck Hierarchy

Ranked by evidence strength (strongest evidence first):

1. **Supervision ambiguity** — dominant. Multiple valid workflows exist for the same task; the training data provides one reference but many sequences are plausible. Four independent lines of evidence converge. The quality-gate dataset has high sequence entropy and broad task types with many valid variants.

2. **Scorer calibration** — the repair selection failure. Repair oracle shows useful candidates exist (win rate 0.88, corruption 0.02), but the deployed scorer fails to select them ~88% of the time. The primary failure mode is edit_oversuppression: the edit_penalty term dominates all other score components. The confidence-regime search found 0 score-selected deployable regimes, so this remains an evaluation-only diagnostic problem rather than a production scorer change.

3. **Data imbalance** — Top10 L3 tokens account for ~75% of all tokens; 47 active L3 from 94 total; long-tail operators have very few training examples.

4. **Ontology gaps** — 10 unresolved GEE official-name aliases; a first bounded offline operator-mapping inventory now exists, but it only exposes 13 conservative exact GEE<->QGIS candidates and no GDAL/ArcGIS coverage; deployable semantic repair/equivalence mapping and segment boundary detection are still not built.

5. **Retrieval corpus coverage** — retrieval saturation affects some task types; retrieval-pool oracle gain (+0.25 LCS) substantially exceeds local repair oracle gain (+0.12 LCS), indicating the retrieval corpus itself could be improved.

6. **Task-type sparsity** — some task types have very few training examples, making retrieval and generation both unreliable for those types.

7. **Sequence-level evaluation sensitivity** — LCS is coarse; small but meaningful edits may not register. Need complementary execution-aware and constraint-satisfaction metrics.

8. **Architecture** — NOT the primary bottleneck. V5_final trains stably and learns discrimination (Top5=62%). The gap between discrimination and generation quality is primarily a decoding/scoring problem, not a model capacity problem.

### F. Current Research Direction

The evidence-supported mainline is:

**Retrieval-centered workflow planning** with **constrained repair** and **selective intervention**, using **execution-aware reranking**.

Specifically:
- Retrieval is the structural anchor (lexical + embedding + graph-aware fusion).
- V5_final serves as a complete-candidate scorer, not a generator.
- Local edits (substitution, bridge insertion, deletion, swap) are the repair mechanism.
- Repair adoption requires calibrated confidence — currently the critical unsolved problem.
- Execution-awareness (I/O compatibility, operator feasibility) constrains all stages.

This is NOT:
- Unrestricted autoregressive generation from task text.
- Retrieval-augmented generation where the model freely modifies candidates.
- Blind repair acceptance.
- Graph-structure learning or DAG recovery.

Production interpretation: the deployable system is retrieval plus conservative rerank plus execution reporting. Research exploration may analyze scorer calibration, repair candidates, retrieval coverage, canonicalization, and set priors. Oracle evidence may estimate headroom only; it is not runtime capability.

**Current priority:** Scorer calibration diagnostics. Before any production scoring change, must measure: AUROC (discrimination), ECE (calibration error), RCA (repair-confidence alignment), SIR (selection inversion rate). The goal is to find a score-selected configuration where repair adoption produces net-positive mean LCS with acceptable corruption, verified on bootstrap intervals; oracle-only regimes are not sufficient.

**Secondary priorities:** Oracle metrics computation (Oracle_ret, Oracle_rank, Oracle_repair), preservation bias measurement, adoption-precision curve analysis, and manual review/extension of the bounded ontology inventory before any semantic repair work.

### G. Current Scientific Boundaries

**Forbidden claims (any violation invalidates the claim):**
1. "The system generates workflows" — generation (Task C) is the weakest formulation. Only retrieval-centered planning (Task B) has empirical support.
2. "The system understands GIS workflows" — no understanding metric exists. The system retrieves and modifies training exemplars.
3. "The model learns workflow structure/graph topology" — no graph supervision, no DAG learning, no topological annotation.
4. "V5 outperforms V4" — they predict different things over different vocabularies. Cross-version claims require operator-sequence-level metrics.
5. "Repair works" — C_rep ≈ 0 in deployed configuration. Oracle shows headroom, but deployed repair contribution is negligible.
6. "The scorer is calibrated" — no stable calibration has been found. ECE, RCA not yet measured.

**Forbidden metric mixing:**
1. TF metrics (Top1, PPL, TF-SeqEM) vs AR rollout metrics (TokenAcc, LCS, AR-SeqEM).
2. Token-level comparison across V4 (L3, 98-class) and V5 (operators, ~150-class).
3. Set-level metrics (SetF1) framed as sequence-level evidence.
4. Oracle metrics reported as deployed metrics.
5. Retrieval-centered planning metrics reported as generation capability.
6. 50-sample results promoted without 200-sample+ bootstrap confirmation.

**Forbidden attribution laundering:**
1. C_ret + C_gen reported as C_gen (inflates generation by including retrieval).
2. Oracle ceiling reported as deployed capability.
3. Candidate existence framed as selection quality.
4. C_set improvements claimed as C_gen improvements (cross-family laundering).
5. Preservation bias (never selecting edits) framed as "safe conservatism."
6. Repair corruption rate omitted when reporting repair adoption.

### H. Future Continuation Instructions

**For future Claude/Codex sessions:**

1. **Read this section first** before interpreting any artifact or making claims. The governance protocols (`v5_master_governance_protocol.md`, `v5_planner_phase_governance_protocol.md`, `v5_repair_centered_planning_protocol.md`, `v5_repair_selection_governance_protocol.md`) provide detailed attribution frameworks but this synthesis is the authoritative summary.

2. **Architecture is frozen.** Do not propose new model architectures, losses, neural modules, or training redesigns unless the explicit reopening criteria are met.

3. **Evidence standards are binding:**
   - All claims require ablation measurement (component vs baseline).
   - All metrics require bootstrap confidence intervals on held-out data.
   - 50-sample results are hints, not evidence. 200+ samples minimum for claims.
   - Oracle metrics must be labeled "oracle" and never conflated with deployed.
   - TF and AR metrics must be reported in separate rows/tables.

4. **Currently justified experiments (evaluation-only, no training):**
   - Scorer quality diagnosis (AUROC, ECE, RCA, SIR measurement).
   - Preservation bias quantification.
   - Adoption-Precision Curve analysis.
   - Repair candidate feature analysis (what distinguishes good vs bad repairs).
   - Retrieval corpus coverage analysis.
   - Oracle metric computation from existing traces.

5. **Currently justified experiments (may involve training):**
   - Quality-gate Transformer training via `scripts/train_v4_quality_gate.py`.
   - Quality-gate Set Predictor training via `scripts/train_set_predictor_quality_gate.py`.
   - Larger-scale V5_final training (Stage2) with controlled ablation flags.
   - Beam search and decode strategy evaluation.

6. **Currently unsupported directions (require new evidence to justify):**
   - New model architectures or training objectives.
   - Graph neural networks, DAG structure learning, topological losses.
   - Reinforcement learning for workflow generation.
   - End-to-end differentiable retrieval.
   - Learned repair policies (beyond scoring calibration).
   - Multi-task learning across task families without controlled comparison.

7. **Key artifact locations:**
   - Governance: `docs/v5_master_governance_protocol.md` (authoritative).
   - Consolidation: `docs/v5_system_consolidation_protocol.md`.
   - Benchmarks: `outputs_v2/v5_final_reports/unified_benchmark/`.
   - Repair oracle: `outputs_v2/v5_final_reports/repair_oracle_phase/`.
   - Repair diagnostics: `outputs_v2/v5_final_reports/repair_selection_diagnostics/`.
   - Calibration sweep: `outputs_v2/v5_final_reports/repair_calibration_sweep/`.
   - Scorer ablations: `outputs_v2/v5_final_reports/repair_scorer_ablations/`.
   - Hybrid planner: `outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/`.

8. **When updating this document**, keep the synthesis section current: update benchmark numbers if rerun, add demonstrated findings when confirmed, remove failed approaches if disproven, update bottleneck ranking if evidence shifts. Do not remove the scientific boundaries unless the underlying evidence changes.

## Maintenance Protocol

After each phase, update this file with:

| Section | Required Update |
| --- | --- |
| `Completed Work` | One concise dated row per completed phase |
| `Modified Files And Why` | Add only meaningful source/test/doc changes |
| `Known Pitfalls` | Add any failed attempt or misleading evidence that should not be repeated |
| `Verification Evidence` | Replace stale test results with latest commands and outcomes |
| `Open Work` | Move finished items out; add blockers and next actions |

Also update `docs/PROJECT_CONTEXT.zh-CN.md` so the English and Chinese context documents remain substantively aligned.

## Recent Work Log

### 2026-05-23 — Verified MRV Training Dataset Selection

Completed work:
- Added a shared `resolve_mrv_training_dataset()` helper that lets training launchers explicitly select an isolated MRV-augmented quality-gate dataset version from `outputs_v2/v4_qg_mr_ablation`.
- Wired `--mrv-ablation-version` into both `scripts/train_v4_6_quality_gate.py` and `scripts/train_set_predictor_quality_gate.py`, so Transformer and Set Predictor training can consume verified equivalent / safe commutative variants directly.
- The resolver only trusts `mrv_training_ablation_manifest.json` plus each version's report, and it rejects versions that fail the train-only, no-oversampling, or val/test-unchanged guards.
- Verified the real `mr_all_42` path: both launchers switch to 76,926 workflows with 61,537 train / 7,694 val / 7,695 test and report 42 injected verified variants.

Modified files and why:
- `src/gis_recommend/data/mrv_training_data.py`: shared guard-checked MRV dataset resolver.
- `scripts/train_v4_6_quality_gate.py`: optional MRV-augmented dataset selection for Transformer training.
- `scripts/train_set_predictor_quality_gate.py`: optional MRV-augmented dataset selection for Set Predictor training.
- `tests/test_v4_6_training_readiness.py` and `tests/test_set_predictor_quality_gate_training_launcher.py`: regression tests proving the launchers switch to verified augmented data and preserve dry-run behavior.

Verification evidence:
- `python scripts/train_v4_6_quality_gate.py --dry-run --num-epochs 1 --mrv-ablation-version mr_all_42 --length-bucket-loss-weight 0.1` -> OK; reports 42 injected variants and length bucket summary over 61,537 train samples.
- `python scripts/train_set_predictor_quality_gate.py --dry-run --num-epochs 1 --mrv-ablation-version mr_all_42` -> OK; reports 42 injected variants and 47 active tokens.
- `python -m unittest tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_6_training_readiness tests.test_mrv_training_ablation tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 41 tests OK.

Known pitfalls:
- `mr_all_42` is still small relative to 61,495 base train samples. It is a correct verified injection path, not a sufficient solution to supervision ambiguity by itself.
- Do not train directly from `outputs_v2/v4_qg_multiref_validation_expansion_500` unless its variants are reviewed and rebuilt into the guarded MRV ablation manifest. Auto-only plausible variants are not training labels.

Open work:
- For the next server training run, use `--mrv-ablation-version mr_all_42` if the goal is to include all currently verified equivalent variants.
- To materially increase impact, the next data task is expanding the reviewed MRV registry beyond 42 variants, then rebuilding `outputs_v2/v4_qg_mr_ablation`.

### 2026-05-23 — V4.6 Task-Type Length Bucket Auxiliary Target

Completed work:
- Wired `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json` into the V4.6 quality-gate launcher as an optional task-type length bucket summary and auxiliary loss source.
- Added a new training summary section that reports bucket counts by split and the expected length per bucket, so dry-run output now shows how short/medium/long tasks are distributed before training starts.
- Added a V4.6 trainer-side task-type bucket auxiliary loss that maps `task_type_id -> task_type -> expected length bucket` and adds a small MSE term on top of the existing exact-length and AR length losses.
- Kept the new auxiliary target isolated to training only; no inference, selection, beam, reranker, or runtime metric path was changed.

Modified files and why:
- `scripts/train_v4_6_quality_gate.py`: added `--length-stats` and `--length-bucket-loss-weight`, length-bucket dry-run summary, and trainer wiring for the bucket predictor.
- `src/gis_recommend/training/train_v4_6.py`: added optional task-type bucket target/loss helpers and mixed the weighted bucket term into the existing V4.6 length loss.
- `tests/test_v4_6_training_readiness.py`: added regression coverage for dry-run length bucket summaries, explicit missing-file failure, and optional helper behavior.

Verification evidence:
- `python -m unittest tests.test_v4_6_training_readiness tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 27 tests OK.
- `python -m compileall scripts/train_v4_6_quality_gate.py src/gis_recommend/training/train_v4_6.py tests/test_v4_6_training_readiness.py` -> OK.
- `python scripts/train_v4_6_quality_gate.py --dry-run --num-epochs 1 --length-bucket-loss-weight 0.1` -> OK; dry-run reports task-type length bucket coverage for train/val/test and bucket expected lengths short=3, medium=5, long=8, very_long=13.

Known pitfalls:
- The bucket auxiliary target is intentionally coarse. It is a task-type complexity prior, not a replacement for exact length loss or rollout evaluation.
- The launcher only enables the bucket summary/loss when a positive `--length-bucket-loss-weight` is provided. The direct Python API still defaults to the old behavior unless the caller passes a predictor and positive weight.

Open work:
- Decide whether the next training run should use the default `0.1` bucket weight or a smaller calibrated value.
- If full training is launched, verify whether the bucket auxiliary term reduces short/long confusion without hurting the primary multi-solution metrics.

### 2026-05-23 — P0 Evidence-aware Ranking Calibration Repair

Completed work:
- Repaired `scripts/evaluate_evidence_aware_ranking.py` so the offline calibration verdict is based on primary multi-solution metrics rather than "candidate differs from legacy" alone.
- Added/restored script-level helpers used by tests: `build_evidence_aware_selection`, `compute_candidate_metrics`, `evaluate_records`, and `render_markdown`.
- Preserved the metric contract: primary = SetF1, usable, executable, QGIS mapping; supporting = LCS; diagnostic only = TokenAcc and Sequence EM.
- Fixed `None` markdown formatting and rounded delta means to avoid floating point tail artifacts.

Modified files and why:
- `scripts/evaluate_evidence_aware_ranking.py`: offline-only calibration script. It does not alter `pred_tokens`, decoder, beam, reranker, metrics, or runtime selection.

Verification evidence:
- `python -m unittest tests.test_evidence_aware_ranking -v` -> 6 tests OK.
- `python -m unittest tests.test_mainline_shadow_phase.P0CalibrationScriptTests -v` -> 3 tests OK.

Known pitfalls:
- `outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json` uses the empirical baseline schema and has no top-level `per_sample`; it is not a valid direct input for `scripts/evaluate_evidence_aware_ranking.py`.
- Do not reintroduce "EA differs from legacy" as a PASS condition. Evidence-aware ranking must show improvement on primary metrics, while TokenAcc remains diagnostic only for this multi-solution GIS task.

Open work:
- Run the repaired calibration script on a real planner/evaluation report with top-level `per_sample` and `decision_trace.evidence_aware_ranking.comparison_metrics`.
- Next implementation step should target a real quality lift: semantic constraint hard filtering or calibrated ranking on the candidate pool, with offline A/B validation before any runtime selection change.

### 2026-05-23 — V4.2/V4.6 Training Readiness Hardening

Completed work:
- Hardened `scripts/train_v4_6_quality_gate.py` so MR registry usage is explicit and non-silent: missing explicit registry now fails, explicit `mr_ratio<=0` now fails, and dry-run summaries show MR coverage instead of silently disabling it.
- Added a training-contract summary to the V4.6 launcher so the six-problem constraints and post-training validation requirements are visible before training starts.
- Added a metric-contract summary that keeps `SetF1 / usable / executable / QGIS mapping` primary and `TokenAcc / Sequence EM` diagnostic only.
- Kept the historical latest-snapshot filename `best_model.pth`, but also added separate observation-only checkpoint snapshots for best generation SetF1 and best generation LCS so post-training comparison does not depend only on the latest epoch.
- Added the same training/metric/checkpoint contract summaries to the V4.2 quality-gate launcher, so both transformer training entrypoints expose the multi-solution metric policy during dry-run.
- Redirected direct `python -m gis_recommend.training.train_v4_6` execution to `scripts.train_v4_6_quality_gate.main(argv)` so V4.6 training cannot accidentally bypass the quality-gate paths, MR registry controls, or metric contract.

Modified files and why:
- `scripts/train_v4_6_quality_gate.py`: explicit MR registry gate, training-contract summary, metric-contract summary, checkpoint policy summary.
- `scripts/train_v4_quality_gate.py`: added matching dry-run training/metric/checkpoint contract summaries for the V4.2 quality-gate entrypoint.
- `src/gis_recommend/training/train_v4_6.py`: saved extra observation-only metric-best snapshots while preserving latest-snapshot behavior; direct module main now delegates to the quality-gate launcher.
- `tests/test_v4_6_training_readiness.py`: new contract tests for MR validation, checkpoint policy separation, and direct-main delegation.
- `tests/test_v4_quality_gate_training_launcher.py`: V4.2 launcher dry-run now asserts the primary/diagnostic metric policy.

Verification evidence:
- `python -m unittest tests.test_v4_6_training_readiness tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 24 tests OK.
- `python -m compileall scripts/train_v4_quality_gate.py scripts/train_v4_6_quality_gate.py src/gis_recommend/training/train_v4_6.py tests/test_v4_quality_gate_training_launcher.py tests/test_v4_6_training_readiness.py` -> OK.
- `python scripts/train_v4_6_quality_gate.py --dry-run --num-epochs 1 --mr-registry outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json --mr-ratio 0.5` -> OK; dry-run reports 76,884 workflows, 61,495 train / 7,694 val / 7,695 test, MR registry enabled with 23 task groups and 7 matched train samples, plus the training/checkpoint contracts.

Known pitfalls:
- Do not treat the extra `best_gen_*` snapshots as replacing the historical latest snapshot. `best_model.pth` remains the latest-epoch compatibility file.
- The launcher now fails fast if the caller explicitly provides an MR registry path with `mr_ratio<=0` or a missing file; this is intentional.
- The MR registry currently matches only 7 quality-gate train samples in the default data, so `--mr-ratio` affects a small slice unless the registry/data are expanded.
- Do not run the old direct V4.6 module as an independent training path. It now delegates to the quality-gate launcher; use `scripts/train_v4_6_quality_gate.py` explicitly for server training commands.

Open work:
- Before starting full training, decide whether the next actual training run should use `--mr-registry`/`--mr-ratio` or remain single-reference only.
- If training is launched, validate the resulting checkpoint policy with the post-training evaluation path instead of trusting loss alone.

### 2026-05-23 — Set Predictor Training Readiness Hardening

Completed work:
- Added optional MR registry support to Set Predictor quality-gate training. For matched training tasks, binary/count targets now use the union of verified equivalent references, so equivalent operators are no longer treated as absent in the coverage-prior target.
- Active token discovery can include MR variant tokens. On the current default quality-gate data, MR registry adds no new active tokens because all variant tokens already exist in the 47 active-token set.
- BCE `pos_weight` now uses the same MR-union positive semantics as the dataset targets when MR is enabled.
- Set Predictor training now keeps `best_model.pth` as the latest-epoch compatibility snapshot while also saving `best_set_f1_model.pth` and `best_topk_recall5_model.pth`; the manifest recommends `best_topk_recall5_model.pth` because coverage recall is closer to the coverage-prior role.
- Set Predictor dry-run now reports its role contract: coverage-prior only, not candidate ranking, sequence generation, or semantic validation.
- Direct `python -m gis_recommend.training.train_set_predictor_v3` execution now delegates to `scripts.train_set_predictor_quality_gate.main(argv)` so it cannot accidentally train on stale/default non-quality-gate paths.

Modified files and why:
- `src/gis_recommend/training/train_set_predictor_v3.py`: MR-aware active-token discovery, MR-union dataset targets, MR-aware `compute_pos_weight`, and direct-main delegation.
- `scripts/train_set_predictor_quality_gate.py`: optional `--mr-registry`, MR summary, training/metric/checkpoint contracts, MR registry propagation into train dataset and pos-weight calculation, plus metric-best checkpoint snapshots.
- `tests/test_set_predictor_quality_gate_training_launcher.py`: regression tests for MR target union, missing registry fail-fast, dry-run metric contract, direct-main delegation, and metric-best checkpoint separation.

Verification evidence:
- `python -m unittest tests.test_set_predictor_quality_gate_training_launcher tests.test_v4_6_training_readiness tests.test_v4_quality_gate_training_launcher tests.test_v4_6_training_stability tests.test_v4_6_training_metrics tests.test_v4_training_entry_smoke -v` -> 32 tests OK.
- `python -m compileall scripts/train_set_predictor_quality_gate.py src/gis_recommend/training/train_set_predictor_v3.py tests/test_set_predictor_quality_gate_training_launcher.py` -> OK.
- `python scripts/train_set_predictor_quality_gate.py --dry-run --num-epochs 1 --mr-registry outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json` -> OK; dry-run reports 76,884 workflows, 61,495 train / 7,694 val / 7,695 test, 47 active tokens, MR enabled with 23 groups, 7 matched train samples, and no variant active tokens added.

Known pitfalls:
- This does not make Set Predictor a ranker or semantic validator. It remains a coverage prior; Planner-level usable/QGIS metrics are still the real post-training validation.
- Current MR coverage is very small: only 7 train samples match the registry. The code path is now correct, but current data coverage limits expected impact.

### 2026-05-23 — Automatic Multi-Solution Candidate Mining And Review Loop

Completed work:
- Replaced the old one-off multi-solution candidate path with an offline train-split-only candidate miner in `scripts/build_multisolution_candidates.py`.
- The miner groups only by same `task_type`, then scores candidate pairs with multiset SetF1, LCS ratio, length delta, and task-text Jaccard. Same `task_type` is a recall condition only, not an equivalence label.
- Added review buckets: `high_precision_review_candidate`, `boundary_review_candidate`, and `auto_rejected_control`.
- Human review sheets now support capped, task-balanced sampling plus optional rejected controls for estimating false-positive/false-negative risk.
- Added `scripts/build_multisolution_registry_from_review.py` to convert a completed review sheet into registry/KB v3. It promotes only `human_label in {"equivalent", "verified_equivalent"}` and excludes blank/uncertain/rejected rows.

Real-data artifacts:
- Conservative run: `outputs_v2/v4_qg_multisolution_candidates/`
  - Train samples scanned: 61,495
  - Total candidate pairs: 20,227
  - Review candidates: 279
  - Review sheet rows: 291 = 237 boundary + 4 high precision + 50 rejected controls
  - Registry dry-run from unfilled review sheet correctly produced 0 equivalent variants and 291 excluded variants.
- Relaxed probe: `outputs_v2/v4_qg_multisolution_candidates_relaxed_probe/`
  - Total candidate pairs: 37,534
  - Review candidates: 1,510
  - High precision candidates: 80
  - Review packet: 700 rows

Modified files and why:
- `scripts/build_multisolution_candidates.py`: automatic candidate generation, review bucket assignment, rejected-control sampling, report/summary outputs.
- `scripts/build_multisolution_registry_from_review.py`: safe post-review registry/KB v3 builder for human-confirmed equivalents only.
- `tests/test_multisolution_candidate_generation.py`: covers train-only generation, threshold rejection, balanced review sampling, rejected controls, and review buckets.
- `tests/test_multisolution_registry_from_review.py`: covers human-label-only promotion and blank-label exclusion.

Verification evidence:
- `python -m unittest tests.test_multisolution_candidate_generation tests.test_multisolution_registry_from_review tests.test_mrv_training_ablation -v` -> 12 tests OK.
- `python -m compileall scripts/build_multisolution_candidates.py scripts/build_multisolution_registry_from_review.py tests/test_multisolution_candidate_generation.py tests/test_multisolution_registry_from_review.py` -> OK.
- Real conservative/probe candidate-generation runs completed on the quality-gate train split.

Known pitfalls:
- Do not treat generated candidate rows as training labels. Only the v3 registry builder output after human labels are filled can feed MRV ablation construction.
- Same task type plus high token overlap can still mix non-equivalent tasks, e.g. same atmospheric/ocean task family with different target variables. Human review remains required.
- Conservative thresholds are precise but low-yield; relaxed thresholds are useful for scaling but require stronger sampling discipline.

Open work:
- Human-review the conservative `candidate_review_sheet.csv` first. If acceptance rate is high, review the relaxed probe high-precision rows next.
- After review, run `scripts/build_multisolution_registry_from_review.py`, then point `scripts/build_mrv_training_ablation.py` at the generated v3 registry/KB to create a larger MR training ablation set.

### 2026-05-23 — Multi-Solution Review Promoted To MR Training Ablation

Completed work:
- Verified the reviewed file `outputs_v2/v4_qg_multisolution_candidates/candidate_review_sheet_ai_reviewed.csv`.
- Label counts are: 178 `equivalent`, 63 `not_equivalent`, and 50 blank rejected-control rows.
- Equivalent rows cover 39 task types; total reviewed non-control rows are 241 with a 73.86% equivalent acceptance rate.
- Built v3 registry/KB from reviewed rows under `outputs_v2/v4_qg_multisolution_candidates/verified_registry_v3/`.
- Merged the historical v2 MRV registry (42 equivalent variants) with the new v3 registry (178 equivalent variants) into v4 under `outputs_v2/v4_qg_multisolution_candidates/merged_registry_v4/`.
- Generated the isolated MR training derivative `outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/`.

Key counts:
- v3 registry from auto-mined review: 178 equivalent variants, 156 task groups, 113 excluded variants.
- merged v4 registry/KB: 220 equivalent variants, 179 registry groups, 220 KB rows.
- `mr_all_220` ablation dataset: base workflows 76,884 -> output workflows 77,104; train 61,495 -> 61,715; val 7,694 unchanged; test 7,695 unchanged; injection rate vs base train 0.00357753.

Modified files and why:
- `scripts/merge_multisolution_registries.py`: merges verified v2 and v3 registries plus their KB rows so token-level variant data is preserved for `build_mrv_training_ablation.py`.
- `tests/test_multisolution_registry_merge.py`: covers merged equivalent counts and preservation of KB `variant_tokens`.

Verification evidence:
- `python scripts/build_multisolution_registry_from_review.py --review-csv outputs_v2/v4_qg_multisolution_candidates/candidate_review_sheet_ai_reviewed.csv --output-dir outputs_v2/v4_qg_multisolution_candidates/verified_registry_v3` -> 178 equivalent variants.
- `python scripts/merge_multisolution_registries.py ... --output-dir outputs_v2/v4_qg_multisolution_candidates/merged_registry_v4` -> 220 equivalent variants.
- `python scripts/build_mrv_training_ablation.py --registry outputs_v2/v4_qg_multisolution_candidates/merged_registry_v4/verified_multi_reference_registry_v4.json --kb outputs_v2/v4_qg_multisolution_candidates/merged_registry_v4/verified_equivalence_kb_v4.json --out-dir outputs_v2/v4_qg_mr_ablation_from_multisolution --subset-sizes all` -> `mr_all_220: injected=220 train=61715 val=7694 test=7695`.
- `python -m unittest tests.test_multisolution_candidate_generation tests.test_multisolution_registry_from_review tests.test_multisolution_registry_merge tests.test_mrv_training_ablation -v` -> 14 tests OK.
- `python -m compileall scripts/build_multisolution_candidates.py scripts/build_multisolution_registry_from_review.py scripts/merge_multisolution_registries.py tests/test_multisolution_candidate_generation.py tests/test_multisolution_registry_from_review.py tests/test_multisolution_registry_merge.py` -> OK.

Known pitfalls:
- `mr_all_220` is still a small injection relative to 61,495 train rows, but it is materially larger than `mr_all_42` and covers many more task types.
- The new registry is suitable for controlled training ablation, not a proof that all future auto-mined candidates are safe. Continue requiring human labels before registry promotion.

Open work:
- Use `outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/` for the next Transformer and Set Predictor training dry-runs/full server training.
- Compare against baseline and `mr_all_42` using primary metrics: SetF1, usable, executable, QGIS mapping; keep TokenAcc/SeqEM diagnostic only.

### 2026-05-24 — Unified Multi-Solution Registry And mr_all_1257

Completed work:
- Built a unified verified multi-solution registry from four approved sources:
  - `manual_mrv_v2`: 42
  - `structural_equivalence_conservative`: 178
  - `structural_equivalence_relaxed`: 406
  - `local_filter_swap_sampled`: 631
- Note: the current file facts are `combined_equivalents.csv = 584 = 178 conservative + 406 relaxed-only`, not `66 + 518`; total remains 1,257 when combined with MRV v2 and filter swaps.
- Generated unified registry/KB under `outputs_v2/v4_qg_multisolution_unified_registry_v1/`.
- Generated isolated training ablation dataset `outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/`.

Key counts:
- Unified registry: 1,257 equivalent variants, 660 registry groups.
- `mr_all_1257`: base workflows 76,884 -> output workflows 78,141; train 61,495 -> 62,752; val 7,694 unchanged; test 7,695 unchanged.
- Train injection rate vs base train: 0.02044069.

Modified files and why:
- `scripts/build_unified_multisolution_registry.py`: consolidates MRV v2, structural equivalence CSV, and sampled filter swaps into one source-family-preserving registry/KB.
- `tests/test_unified_multisolution_registry.py`: covers source-family counts, nested CSV token parsing, and KB token preservation.

Verification evidence:
- `python scripts/build_unified_multisolution_registry.py --mrv-registry outputs_v2/v4_qg_multiref_validation/verified_multi_reference_registry_v2.json --mrv-kb outputs_v2/v4_qg_multiref_validation/verified_equivalence_kb_v2.json --conservative-csv outputs_v2/v4_qg_multisolution_candidates/candidate_review_sheet_ai_reviewed.csv --structural-csv outputs_v2/v4_qg_multisolution_candidates_relaxed_probe/combined_equivalents.csv --filter-swap-csv outputs_v2/safe_swap_candidates_v1/sampled_filter_swaps_1000.csv --output-dir outputs_v2/v4_qg_multisolution_unified_registry_v1` -> 1,257 variants.
- `python scripts/build_mrv_training_ablation.py --registry outputs_v2/v4_qg_multisolution_unified_registry_v1/verified_multi_reference_registry_unified.json --kb outputs_v2/v4_qg_multisolution_unified_registry_v1/verified_equivalence_kb_unified.json --out-dir outputs_v2/v4_qg_mr_ablation_from_multisolution_unified --subset-sizes all` -> `mr_all_1257: injected=1257 train=62752 val=7694 test=7695`.
- `python -m unittest tests.test_unified_multisolution_registry tests.test_mrv_training_ablation tests.test_mrv_training_data -v` -> 7 tests OK.
- `python -m compileall scripts/build_unified_multisolution_registry.py tests/test_unified_multisolution_registry.py` -> OK.

Known pitfalls:
- `build_mrv_training_ablation.py` report still labels the source generically as `verified_mrv_registry_v2_and_equivalence_kb_v2`; for `mr_all_1257`, trust the upstream unified registry `source_family_counts` for provenance.
- `local_filter_swap_sampled` teaches local order invariance only; keep it separated from structural equivalence when interpreting ablation results.

Open work:
- Train/evaluate `mr_all_1257` alongside baseline, `mr_all_42`, `mr_all_220`, and optionally `mr_all_738` if generated separately.
- Evaluation must report by scale and source mix; do not collapse structural-equivalence gains and filter-swap gains into one causal claim.

### 2026-05-24 — Unified Multi-Solution Registry v2 And mr_all_1841

Completed work:
- Validated the final high-confidence multi-solution mix:
  - `manual_mrv_v2`: 42
  - `structural_equivalence`: 584
  - `local_filter_swap_sampled`: 1,215
- Confirmed `outputs_v2/unified_multisolution_registry/unified_equivalents_v1.csv` contains 1,799 rows and does not include the 42 MRV v2 rows; 1,799 + 42 = 1,841.
- Confirmed the 93 `needs_review` select/filter/clip rows are not included in `unified_equivalents_v1.csv`; included local swaps are all `tier=auto_verified` and `swap_type=filter<>filter`.
- Generated registry/KB under `outputs_v2/v4_qg_multisolution_unified_registry_v2/`.
- Generated isolated training ablation dataset `outputs_v2/v4_qg_mr_ablation_from_multisolution_unified_v2/mr_all_1841/`.

Key counts:
- Registry v2: 1,841 equivalent variants, 660 registry groups.
- `mr_all_1841`: base workflows 76,884 -> output workflows 78,725; train 61,495 -> 63,336; val 7,694 unchanged; test 7,695 unchanged.
- Train injection rate vs base train: 0.02993739.

Modified files and why:
- `scripts/build_unified_multisolution_registry.py`: added a `--unified-equivalents-csv` path that consumes the pre-merged reviewed-equivalents CSV, preserves source-family provenance, and filters out non-`auto_verified` / non-`filter<>filter` local swap rows.
- `tests/test_unified_multisolution_registry.py`: covers the unified CSV ingestion path and verifies `needs_review` select/filter candidates are excluded.

Verification evidence:
- `python scripts/build_unified_multisolution_registry.py --unified-equivalents-csv outputs_v2/unified_multisolution_registry/unified_equivalents_v1.csv --output-dir outputs_v2/v4_qg_multisolution_unified_registry_v2` -> 1,841 variants.
- `python scripts/build_mrv_training_ablation.py --registry outputs_v2/v4_qg_multisolution_unified_registry_v2/verified_multi_reference_registry_unified.json --kb outputs_v2/v4_qg_multisolution_unified_registry_v2/verified_equivalence_kb_unified.json --out-dir outputs_v2/v4_qg_mr_ablation_from_multisolution_unified_v2 --subset-sizes all` -> `mr_all_1841: injected=1841 train=63336 val=7694 test=7695`.
- `python -m unittest tests.test_unified_multisolution_registry tests.test_mrv_training_ablation tests.test_mrv_training_data -v` -> 8 tests OK.
- `python -m compileall scripts/build_unified_multisolution_registry.py tests/test_unified_multisolution_registry.py` -> OK.

Known pitfalls:
- Do not use the raw round-2 expansion total as verified training data. The 93 `needs_review` select/filter/clip rows remain quarantined.
- `unified_equivalents_v1.csv` is 1,799 rows by design because MRV v2 remains in its source registry/KB; the correct final training count is 1,841 after registry merge.

Open work:
- Use `outputs_v2/v4_qg_mr_ablation_from_multisolution_unified_v2/mr_all_1841/` only as the next high-confidence scale-up after smaller ablations show positive direction.
- Training comparisons should remain split by scale/source mix: baseline, `mr_all_42`, `mr_all_220`, `mr_all_1257`, `mr_all_1841`.

### 2026-05-24 — Training-Stage Optimization Roadmap After Multi-Solution Data

Current state:
- Server-side Transformer/Set Predictor ablations are running or planned for baseline, `mr_all_42`, `mr_all_220`, and `mr_all_1257`.
- Do not blindly expand more multi-solution data while these runs are unresolved. First close the evaluation loop and confirm whether data scale helps.

Decision:
- Next optimization work should stay centered on the original six problems, but shift from data expansion to training/evaluation alignment:
  1. Multi-solution: keep source-family-separated ablations; use `mr_all_1841` only after smaller scales show positive direction.
  2. Workflow Complexity: connect `outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json` to training summaries and an auxiliary short/medium/long or task-type length-bucket target. Track early END and overlength by task type/bucket.
  3. Generation Instability: align training validation with inference by adding constrained AR rollout validation and invalid-transition diagnostics. Training loss alone is insufficient.
  4. Evaluation Misalignment: make best-checkpoint selection prefer workflow-level validation metrics: SetF1, usable, executable, QGIS mapping, with LCS supporting. TokenAcc and SeqEM remain diagnostic only.
  5. Ranking Problem: after ablation results are available, build supervised candidate reranker data from candidate pools using multi-reference/usable/oracle-best candidates as positives and invalid/low-utility candidates as negatives.
  6. Semantic Constraint: add lightweight training-time auxiliary signals for QGIS mapping availability and transition/IO compatibility before attempting heavier ontology/KG authority.

Immediate priority:
- Monitor active runs for `nan`/`inf`, AR collapse, high early-EOS, invalid transitions, and checkpoint behavior.
- Prepare one unified post-training evaluation script/report that compares baseline, `mr_all_42`, `mr_all_220`, and `mr_all_1257` with the same primary metric hierarchy.
- Then implement P1/P2 changes: workflow-metric checkpoint selection and length/complexity auxiliary training signals.

Known pitfalls:
- Do not decide training success from CE loss, TokenAcc, or SeqEM alone. This project is multi-solution; exact token matching can move opposite to workflow usability.
- Do not mix source-family effects. Structural equivalence teaches alternate solutions; local filter swaps mostly teach order invariance.

### 2026-05-26 — Workflow Complexity Evaluation Closure

Completed work:
- Added complexity-bucket rollout diagnostics to `scripts/evaluate_v4_quality_gate.py`.
- Reports now stratify quality-gate evaluation by `short`, `medium`, `long`, and `very_long` buckets from `task_type_length_stats.json`.
- Per bucket, reports include sample count, mean reference length, mean prediction length, length ratio, early-EOS rate, overlength rate, SetF1, LCS, and TokenAcc.
- `scripts/evaluate_checkpoint_epochs.py` now carries long/very-long length ratio and early-EOS diagnostics into checkpoint ranking JSON/Markdown, so checkpoint choice can detect whether length-bucket training actually helps long-chain tasks.

Decision:
- Complexity training is not considered closed by adding length-bucket loss alone. It must be validated by bucket-level rollout diagnostics, especially `long_early_eos_rate`, `very_long_early_eos_rate`, and length ratio.
- TokenAcc remains diagnostic only; use SetF1/LCS plus workflow usability/QGIS/executable metrics for model comparison.

Verification evidence:
- `python -m unittest tests.test_v4_qg_evaluation_report -v` -> 5 tests OK.
- `python -m unittest tests.test_v4_6_training_stability -v` -> 4 tests OK.
- `python -m compileall scripts\evaluate_v4_quality_gate.py scripts\evaluate_checkpoint_epochs.py tests\test_v4_qg_evaluation_report.py` -> OK.

### 2026-05-26 — Server Ablation Results Initial Read

Observed artifacts:
- Transformer logs: `结果/transformer训练结果/0526/{baseline,mr_all_42,mr_all_220,mr_all_1257}.md`.
- Set Predictor logs: `结果/train_set_predictor结果/0526/{baseline,mr_all_42,mr_all_220,mr_all_1257}.md`.

Initial facts:
- All four Transformer runs completed 50 epochs with no observed `nan`/`inf` loss collapse.
- Transformer latest-checkpoint test metrics do not show a positive multi-solution scale trend: baseline AR-LCS/SetF1 = 0.433/0.565; `mr_all_42` = 0.423/0.544; `mr_all_220` = 0.424/0.548; `mr_all_1257` = 0.421/0.557.
- `mr_all_1257` lowers TF loss slightly but worsens rollout length/noise diagnostics versus baseline: pred length 10.5 vs 9.4, len error 5.0 vs 4.0, earlyEOS 7.8% vs 4.7%, bad transitions 44.6% vs 30.9%.
- Set Predictor is roughly flat across ablations. `mr_all_220` is the best small positive signal by best F1@0.70 = 0.715 and best Top5 recall = 0.675, versus baseline 0.713 / 0.673.

Interpretation:
- Do not scale to `mr_all_1841` yet. Current evidence does not show that larger MR injection improves Transformer AR rollout.
- The next required step is checkpoint-level and workflow-level evaluation of saved best snapshots (`best_gen_set_f1_model.pth`, `best_gen_lcs_model.pth`, Set Predictor `best_topk_recall5_model.pth`), not more data expansion.

### 2026-05-26 — Training Evaluation Contract Fixes

Completed work:
- `scripts/evaluate_checkpoint_epochs.py` now evaluates named selection snapshots in addition to epoch checkpoints: `best_model.pth`, `best_gen_set_f1_model.pth`, `best_gen_lcs_model.pth`, and `best_gen_composite_model.pth`.
- `scripts/evaluate_v4_quality_gate.py` now records the actual checkpoint and Set Predictor paths passed to inference in `eval_config`, rather than always reporting default `best_model.pth`.
- `src/gis_recommend/training/train_v4_6.py` now uses at least 16 batches for final test generation evaluation instead of hard-coded 4 batches.
- `src/gis_recommend/training/train_v4_2.py` adds `count_invalid_transitions()` and counts unknown transition source states as invalid diagnostics instead of silently excluding them.

Verification evidence:
- `python -m unittest tests.test_v4_6_training_stability -v` -> 5 tests OK.
- `python -m unittest tests.test_v4_qg_evaluation_report -v` -> 6 tests OK.
- `python -m compileall src\gis_recommend\training\train_v4_2.py src\gis_recommend\training\train_v4_6.py scripts\evaluate_v4_quality_gate.py scripts\evaluate_checkpoint_epochs.py tests\test_v4_qg_evaluation_report.py tests\test_v4_6_training_stability.py` -> OK.

Open requirement:
- The 2026-05-26 server ablation logs must be reinterpreted as noisy/latest-checkpoint diagnostics. Re-evaluate uploaded server checkpoints with the updated checkpoint/workflow evaluation scripts before making MR-vs-baseline claims.

### 2026-05-27 — Offline ExecutionAwareSelector Review

Completed work:
- Reviewed and corrected the new offline `ExecutionAwareSelector` path before any runtime integration.
- `src/gis_recommend/planning/execution_aware_selector.py` now counts unknown transition source states as invalid, matching `count_invalid_transitions()`, avoids mutating caller-provided candidate lists in `select_from_pool()`, and simplifies repetition counting.
- `scripts/evaluate_execution_aware_selector.py` now uses the existing `UsabilityEvaluator` from `evaluate_workflow_usability.py` for primary usability labels instead of a divergent simplified rule set.
- Oracle pool usability is now computed over the full candidate pool, not the selector's truncated top-k ranked candidates.
- Added `tests/test_execution_aware_selector.py` to lock no-mutation behavior, unknown-transition diagnostics, and full-pool oracle accounting.

Key result:
- The earlier 20-sample numbers `retrieval 45% / selector 40% / oracle 80%` were not reliable because the new script had a different usability definition from the project v2 evaluator and truncated oracle accounting.
- Re-run with aligned evaluator:
  - 20 samples: retrieval top-1 usable 85.0%, selector top-1 usable 80.0%, oracle pool usable 100.0%.
  - 200 samples: retrieval top-1 usable 66.5%, selector top-1 usable 81.0%, oracle pool usable 99.0%.
- Current interpretation: rule-based selector is useful offline and improves retrieval top-1 on 200 samples, but there remains large headroom from selector 81% to oracle 99%. Learned/calibrated reranking remains the next path; do not wire runtime until this is validated with beam and larger traces.

Artifacts:
- `outputs_v2/diagnostics/execution_aware_selector_reviewed/`
- `outputs_v2/diagnostics/execution_aware_selector_reviewed_200/`

Verification evidence:
- `python -m unittest tests.test_execution_aware_selector tests.test_v4_6_training_stability tests.test_v4_qg_evaluation_report -v` -> 15 tests OK.
- `python -m compileall src\gis_recommend\planning\execution_aware_selector.py scripts\evaluate_execution_aware_selector.py tests\test_execution_aware_selector.py` -> OK.

### 2026-05-27 — Learned Reranker 1k Offline Probe

Completed work:
- Regenerated the 1,000-sample selector report with full `pool_candidates` traces at `outputs_v2/diagnostics/execution_aware_selector/1k_samples/`.
- Trained the current pairwise logistic-regression reranker with `scripts/train_learned_reranker.py`, writing `outputs_v2/reranker_learned_weights_v1.json`.

Observed facts:
- Selector report: 1,000 query groups, 10,000 candidates, 0 missing candidate pools.
- Candidate pseudo-labels from `UsabilityEvaluator`: 6,427 usable / 3,573 unusable.
- Query groups: 991 with at least one usable candidate, 95 all-usable groups, 896 mixed usable/unusable groups.
- Rule selector on the 1k report: retrieval top-1 usable 65.8%, selector top-1 usable 81.2%, oracle pool usable 99.1%.
- Learned LR held-out split: 800 train queries / 200 test queries; 27,560 pairwise train examples.
- Held-out result: learned Top-1 usable 84.8% vs rule baseline about 83.3% on the same evaluated subset, MRR 0.9118 vs 0.8964, delta +1.5pp Top-1 / +0.0154 MRR.
- Evaluating the saved weights on all 1,000 groups gives Top-1 usable 84.0%, MRR 0.9064.

Interpretation:
- Learned reranking is directionally positive but not yet a major breakthrough. The reliable 1k gain is small, unlike the noisy 50-sample +10pp result.
- Learned weights still show calibration risk: `early_eos_risk` is positive and large, `transition_validity`, `set_predictor_coverage`, and `candidate_source` are effectively zero. Do not wire these weights into runtime as-is.
- Next useful step is feature/label calibration and cross-seed validation, not another Transformer training tweak.

### 2026-05-27 — Learned Reranker v2 Length Calibration

Completed work:
- Updated `early_eos_risk` in `ExecutionAwareSelector` to trigger only below the task-type P10 length: `max(0, (p10 - n) / p10)`.
- Kept `length_bucket_fit` as the P10/P90 in-range reward.
- Updated `scripts/train_learned_reranker.py` to run C-sweep `[0.03, 0.1, 0.3, 1.0]` across seeds `[42, 123, 456]`, save `selected_C`, and label all-groups metrics as in-sample diagnostics after final refit.
- Added a regression test proving reasonable short chains within P10/P90 do not get `early_eos_risk`.

Observed facts:
- Rebuilt report at `outputs_v2/diagnostics/execution_aware_selector/1k_v2/`: retrieval top-1 usable 65.8%, rule selector 82.4%, oracle pool 99.1%.
- The early-EOS calibration itself improved the rule selector from 81.2% to 82.4% on the same 1k setup.
- `early_eos_risk` is now sparse: 156/10,000 candidates nonzero, mean 0.00396.
- Learned v2 C-sweep: C=0.03 mean top-1 83.7% (std 3.7%), C=0.1 83.7% (std 3.3%), C=0.3 84.1% (std 3.6%), C=1.0 84.1% (std 3.6%). Selected C is 0.3.
- Final refit weights: qgis_mapping +5.2606, io_compat +5.6982, length_bucket_fit +1.1699, repetition -1.1213, early_eos +0.2872, model_logprob -0.1459; transition/set/source remain zero due no variance in this retrieval-only setup.
- Final all-groups diagnostic after refit: learned 83.6% Top-1 / 0.9037 MRR vs rule baseline +0.4pp / +0.0020. Treat this as in-sample diagnostic, not held-out generalization.

Interpretation:
- The useful win came from fixing the rule feature, not from LR. The calibrated rule selector is now the stronger practical candidate.
- Current learned reranker does not justify runtime integration. Next evidence-producing step should add new variance sources (Set Predictor coverage and/or beam candidates) before more LR tuning.

Verification evidence:
- `python -m unittest tests.test_execution_aware_selector -v` -> 5 tests OK.
- `python -m compileall src\gis_recommend\planning\execution_aware_selector.py scripts\train_learned_reranker.py tests\test_execution_aware_selector.py` -> OK.

### 2026-05-27 — Beam + Set Predictor Selector Smoke

Completed work:
- Corrected `scripts/evaluate_execution_aware_selector.py` so `--use-beam` defaults to the V4.6 quality-gate Transformer directory, not the non-QG `outputs_v2/transformer_checkpoints_v4_6` directory.
- Corrected the Set Predictor default to `outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth`; the previous code looked at stale `outputs_v2/set_predictor_checkpoints_v3` and silently ran without set-prior constraints.
- Added `--set-predictor-checkpoint` for explicit offline override.
- Stopped swallowing per-sample beam inference failures silently; failures are now printed and recorded as `beam_error`.
- `L3SequenceInferencerV4` now exposes the latest soft token prior through `last_token_prior`, and the selector eval passes it into `ExecutionAwareSelector`, so `set_predictor_coverage` has real variance instead of staying neutral at 0.5.

Observed facts:
- Default `--use-beam` now loads `best_gen_set_f1_model.pth` epoch 43 with the quality-gate 47-type task vocabulary under strict state-dict loading.
- The V4.6 QG Set Predictor loads successfully with 47 active tokens.
- 20-sample beam+SP smoke with real selector prior: retrieval top-1 usable 85.0%, beam top-1 usable 70.0%, selector top-1 usable 90.0%, oracle pool usable 100.0%.
- This is only a smoke result; it proves integration and feature variance, not production-level quality. Larger runs should be done on the server because local CPU beam decoding is about 19-20 seconds per sample.

Artifacts:
- `outputs_v2/diagnostics/execution_aware_selector/beam_sp_prior_smoke_2/`
- `outputs_v2/diagnostics/execution_aware_selector/beam_sp_prior_smoke_20/`

Verification evidence:
- `python -m compileall scripts\evaluate_execution_aware_selector.py src\gis_recommend\inference\infer_l3_candidates_v4.py` -> OK.
- `python -m unittest tests.test_execution_aware_selector tests.test_v4_6_training_stability tests.test_v4_qg_evaluation_report -v` -> 16 tests OK.
- `python scripts\evaluate_execution_aware_selector.py --num-samples 2 --use-beam --output-dir outputs_v2\diagnostics\execution_aware_selector\beam_sp_prior_smoke_2` -> strict checkpoint load OK, Set Predictor load OK.
- `python scripts\evaluate_execution_aware_selector.py --num-samples 20 --use-beam --output-dir outputs_v2\diagnostics\execution_aware_selector\beam_sp_prior_smoke_20` -> selector smoke completed.

### 2026-05-28 — V4.6 Preference Fine-Tuning Scaffold

Completed work:
- Added `--split train|val|test` to `scripts/evaluate_execution_aware_selector.py`, preserving test as default. Reports now include `split`, `sample_index`, and full `task_metadata` so traces can become training data without leaking test into training.
- Added `scripts/build_generation_preferences.py`. It reads `selector_report.json`, filters candidates by source (default `beam`), chooses usable/high-reward positives and lower-reward negatives within the same task, and writes JSONL preference pairs.
- Added `scripts/train_v4_6_preference.py`, an isolated DPO-style post-training entrypoint. It restores a V4.6 checkpoint strictly, keeps a frozen reference model, trains a policy model with `-logsigmoid(beta * ((logP_pos-logP_neg)_policy - (logP_pos-logP_neg)_ref))`, and adds a small CE anchor on positive candidates.
- Added `tests/test_generation_preference_pipeline.py` for split selection, beam-only pair construction, JSONL output, candidate sequence preparation, masked mean log-probability, and DPO loss direction.

Observed facts:
- Existing test 1k selector trace can produce 1,174 beam preference pairs, but this is diagnostic only; real training must generate train/val traces with `--split train` and `--split val`.
- A 1-pair CPU smoke run completed forward/backward/checkpoint writing under `outputs_v2/transformer_checkpoints_v4_6_preference_dpo_smoke/`.

Verification evidence:
- `python -m unittest tests.test_generation_preference_pipeline tests.test_execution_aware_selector tests.test_v4_6_training_stability tests.test_v4_qg_evaluation_report -v` -> 22 tests OK.
- `python -m compileall scripts\evaluate_execution_aware_selector.py scripts\build_generation_preferences.py scripts\train_v4_6_preference.py tests\test_generation_preference_pipeline.py` -> OK.
- `python scripts\evaluate_execution_aware_selector.py --split val --num-samples 1 --output-dir outputs_v2\diagnostics\execution_aware_selector\split_val_smoke_1` -> writes split/sample metadata.
- `python scripts\build_generation_preferences.py --report outputs_v2\diagnostics\execution_aware_selector\beam_sp_prior_1k\selector_report.json --output outputs_v2\preference_data\smoke_beam_pairs.jsonl --source beam --min-reward-margin 0.15 --max-negatives-per-positive 2` -> 1,174 diagnostic pairs.
- `python scripts\train_v4_6_preference.py --checkpoint outputs_v2\transformer_checkpoints_v4_6_quality_gate\best_gen_set_f1_model.pth --train-pairs outputs_v2\preference_data\smoke_beam_pairs.jsonl --output-dir outputs_v2\transformer_checkpoints_v4_6_preference_dpo_smoke --epochs 1 --max-pairs 1 --batch-size 1 --device cpu --lr 1e-6` -> checkpoint smoke completed.

Open requirement:
- Generate preference data from train/val splits on the server. Do not train from `beam_sp_prior_1k` because it is a test-split diagnostic report.

### 2026-05-29 — DPO Final-Policy Quality Reporting Hardening

Completed work:
- Reviewed the DPO `beam_first_usable` / `beam_usable_quality` offline evaluation path after the server-reported 3k result: final usable 99.8%, true final failures 6/3000.
- Hardened `scripts/evaluate_execution_aware_selector.py` reporting so final failures and final warnings are separated. Top-level reports now include `final_warning_taxonomy` in addition to `final_failure_taxonomy`.
- Added a conservative `_quality_adjusted_score()` for `beam_usable_quality`: usability remains the gate, while duplicate tokens, consecutive duplicates, and non-blocking warning markers penalize usable beam candidates during tie-breaking/reranking.
- After the first server `beam_usable_quality` 3k rerun improved duplicate rate but not redundant loops, extended the quality score with hierarchy-derived `token_names` and a direct Train/Apply triplet penalty so loop-like usable beam candidates are penalized during selection, not only diagnosed after the fact.
- Added tests for quality-score penalties and final warning/failure taxonomy separation.

Observed facts:
- `scripts/analyze_final_workflow_quality.py` runs on the existing local `dpo_beam_first_test_3k` report and reports: final usable 2994/3000 (99.8%), true failures 6, duplicate-token rate 25.6%, consecutive-duplicate adjacent-pair rate 0.15%, redundant loop count 437, mean length 5.96, retrieval fallback 30/3000 with 25 usable.
- Treat `beam_usable_quality` as an execution-aware rule-gated offline/runtime-candidate policy, not pure model-only quality. It uses the same rule evaluator as the usability metric to gate beam candidates, so claims must say "execution-aware rule usability", not strict semantic accuracy.

Verification evidence:
- `python -m unittest tests.test_execution_aware_selector -v` -> 7 tests OK.
- After loop-penalty extension: `python -m unittest tests.test_execution_aware_selector -v` -> 8 tests OK.
- `python scripts\evaluate_execution_aware_selector.py --split test --num-samples 5 --selection-policy beam_usable_quality --output-dir outputs_v2\diagnostics\execution_aware_selector\quality_policy_no_beam_smoke_5` -> smoke completed.
- `python scripts\analyze_final_workflow_quality.py --report outputs_v2\diagnostics\execution_aware_selector\dpo_beam_first_test_3k\selector_report.json --output outputs_v2\diagnostics\execution_aware_selector\dpo_beam_first_test_3k\quality_review_smoke_v2` -> quality report smoke completed.

Follow-up:
- Added `--reward-mode quality` to `scripts/build_generation_preferences.py` for DPO v2 pair construction. The default `base` mode preserves v1 behavior; quality mode subtracts duplicate/consecutive-duplicate/warning penalties and allows clean-usable > redundant-usable pairs instead of filtering them out.
- Extended quality-mode pair construction with `--id-mappings` / `--hierarchy` token-name loading so Train/Apply loop penalties used by `beam_usable_quality` can also be distilled into DPO v2 preference pairs.
- `python -m unittest tests.test_generation_preference_pipeline tests.test_execution_aware_selector -v` -> 16 tests OK.
- `python -m compileall scripts\build_generation_preferences.py tests\test_generation_preference_pipeline.py` -> OK.

Server result:
- Quality pairs built from existing train/val selector traces: train 8,265 pairs, val 1,711 pairs using `--reward-mode quality --min-reward-margin 0.10`.
- DPO v2 trained for 1 epoch from `outputs_v2/transformer_checkpoints_v4_6_preference_dpo/best_preference_model.pth` with lr 5e-6, beta 0.05, CE anchor 0.10. Val preference accuracy was 0.7686.
- DPO v2 test 3k with `beam_usable_quality`: retrieval top-1 usable 65.5%, beam top-1 usable 99.2%, selector 89.4%, final 99.9% (2998/3000), oracle 100.0%, final source beam 2999 / retrieval 1.
- Initial quality audit reported redundant loops 302, but review showed the detector incorrectly counted normal `Region-based Sample Extraction -> Train Random Forest Classifier -> Apply Classifier` classification workflows as loops. The detector and training quality penalty were corrected to count only true `Train -> Apply -> Train` or `Apply -> Train -> Apply` cycles.
- Corrected quality audit for DPO v2: true failures 2, duplicate-token rate 1.4%, consecutive duplicate 0.01%, true Train/Apply cycles 0, mean length 5.87. Compared with DPO v1 + loop penalty, DPO v2 trades one additional final failure for much cleaner outputs (duplicates 7.8% -> 1.4%, beam top-1 usable 98.8% -> 99.2%); the prior loop counts are not comparable because they included normal classifier workflows.
- Current recommendation: freeze DPO v2 + `beam_usable_quality` as the best candidate pending 30-50 sample manual semantic audit. Do not run further DPO epochs unless the audit exposes systematic semantic degradation.
- Cycle-fixed DPO v2 follow-up: after correcting the Train/Apply loop detector so normal `Sample -> Train -> Apply` workflows are not penalized, rebuilt quality pairs with 8,288 train pairs and 1,710 val pairs. One-epoch training from the DPO v1 checkpoint completed into `outputs_v2/transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed`; val preference accuracy improved to 0.7865 (previous broad-loop DPO v2 was 0.7686). The next required evidence is test 3k eval + quality audit for this cycle-fixed checkpoint.
- Cycle-fixed DPO v2 test 3k result: beam top-1 usable 99.1%, final usable 2999/3000, true failures 1, duplicate-token rate 2.5%, consecutive duplicate 0.02%, true Train/Apply cycles 0, fallback 2/3000 and both usable. Manual review of 50 usable chains found no empty/fake/reward-hacked chains, but did find expected remote-sensing template reuse (`Filter/Select/Reducer/Clip/Math`) and many non-blocking `missing_critical_steps` warnings.
- Added diversity/template diagnostics to `scripts/analyze_final_workflow_quality.py`: global unique chains, per-task unique/top3 concentration, top repeated chains, Select Bands presence, repeated Select Bands, and non-consecutive repeated Select Bands. On the cycle-fixed 3k report: 1,320/2,999 global unique chains (44.0%), Land use unique 477/932 (51.2%) with top3 9.1%, Vegetation unique 303/573 (52.9%) with top3 11.7%, Select Bands presence 2,556/2,999 (85.2%), repeated Select Bands 22/2,999 (0.7%). Interpretation: cross-task templates exist but no collapse; Select Bands is high-frequency but not usually repeated.

### 2026-05-30 — QGIS GitHub Corpus Intake Audit

Completed work:
- Added `scripts/audit_qgis_workflow_corpus.py`, an offline-only audit that reads the downloaded `爬取GithubQGIS` corpus, builds a QGIS processing algorithm catalog from `QGIS_Input.csv`, aligns QGIS algorithm ids to existing L3 mappings through QGIS display names, audits workflow coverage, and writes high-confidence QGIS->L3 workflow candidates without modifying training data.
- Local audit output written to `outputs_v2/diagnostics/qgis_corpus_audit/`.

Observed facts:
- Corpus structure is mixed. `QGIS_standard_multi_operator_workflows_v2` is the cleanest standard processing subset with 1,045 rows. `github_qgis_workflow_A类` has 10,827 rows, `github_qgis_workflow` has 8,779 rows, `Github_QGIS_RS_Workflows_201509` has 9,933 rows, and `Github_QGIS_RS_QGISPlatform_Related_201509` has 42,550 rows, but the larger sets mix PyQGIS objects/methods, plugins, and QGIS-related code that is not always a processing workflow.
- `QGIS_Input.csv` is an algorithm catalog, not workflow data. It contains 1,292 QGIS processing algorithm ids and display names.
- Existing `id_mappings_v2.mapping_metadata.qgis_to_l3` uses display names, not algorithm ids. The first automatic crosswalk maps 454/1,292 alg ids (35.1%).
- Workflow mention mapping coverage is currently modest: standard 2,180/4,741 mentions (46.0%), A-class 7,739/20,989 (36.9%), general workflow 3,616/9,949 (36.4%). Under strict filters (2-15 tools, input/output signals, >=80% mapped), only 111 unique high-confidence L3 sequences are produced.
- Top unmapped tools are important traditional GIS/QGIS operations: `native:reprojectlayer`, `native:fixgeometries`, `native:mergevectorlayers`, `gdal:warpreproject`, `native:extractbyexpression`, `gdal:polygonize`, `gdal:rasterize`, `native:joinattributesbylocation`, `qgis:fieldcalculator`, etc. Many are not absent from GIS concept space; they are absent from the current QGIS display-name-to-L3 mapping.

Interpretation:
- Do not directly mix the downloaded QGIS corpus into Transformer training yet. The raw corpus has useful traditional GIS/vector workflow signal, but direct training would inject unmapped algorithm ids, PyQGIS method noise, plugin-specific tools, and weak task text.
- The next productive step is to expand and validate `qgis_alg_id -> L3` crosswalk coverage, then build a filtered QGIS-L3 dataset. Use it first for QGIS transition/I-O/rerank evaluation, and only later for DPO or domain-adapted training.

Verification evidence:
- `python scripts\audit_qgis_workflow_corpus.py --output-dir outputs_v2\diagnostics\qgis_corpus_audit` -> completed, wrote catalog/crosswalk/coverage/high-confidence JSONL/Markdown.
- `python -m compileall scripts\audit_qgis_workflow_corpus.py` -> OK.

### 2026-05-31 — QGIS Chain Dataset Verification

Completed work:
- Verified the user-built QGIS chain dataset artifacts at `outputs_v2/qgis_chain_dataset.jsonl` and `outputs_v2/qgis_chain_dataset_summary.json`.
- Confirmed the dataset is suitable as a QGIS-native chain library for retrieval/reranking and transition/grammar learning, but not yet as clean supervised natural-language-to-QGIS-chain generation data.

Observed facts:
- Dataset size is 3,059 records with 973 unique QGIS algorithm chains.
- All included records pass catalog coverage after `--require-catalog`.
- Training target split is 2,683 `qgis_head` only records and 376 `qgis_head+l3_head` bridge records.
- Source split is `standard_v2`: 867, `workflow`: 1,021, `workflow_A`: 1,171.
- Chain length distribution is concentrated at short-to-medium workflows: length 2 = 838, 3 = 583, 4 = 375, 5 = 341, 6 = 253, 7 = 170, 8 = 110.
- Modality split from the summary: pure vector 1,634, pure raster 418, mixed vector/raster 931.
- `task_text` remains noisy: 691 records contain comment-banner artifacts, 440 are only repo/generic text, and 788 have fewer than four useful alphabetic words after basic filtering.

Interpretation:
- Do not directly mix the full QGIS chain dataset into the existing L3 Transformer as L3 training data. Only 376/3,059 records have full L3 mappings, and the unmapped portion contains important native QGIS/GDAL operators that would be lost through the L3 bottleneck.
- Short-term architecture should treat the current DPO v2 L3 model as the semantic planner and this QGIS dataset as the platform landing layer: L3 plan / task text -> QGIS chain retrieval -> QGIS reranker/evaluator -> executable algorithm sequence.
- A direct QGIS generation head remains possible later, but it should wait until task text cleaning, operator vocabulary governance, and a QGIS chain evaluator are in place.

Recommended next implementation:
- Add a QGIS chain retrieval baseline over `outputs_v2/qgis_chain_dataset.jsonl`.
- Scoring should combine weak task-text similarity, optional L3 bridge overlap for the 376 mapped chains, modality compatibility, chain length fit, and transition frequency; it must not rely on task text alone.
- Add a QGIS chain evaluator for catalog coverage, vector/raster consistency, repeated operators, and transition rarity before considering new model training.

Verification evidence:
- `Get-Content outputs_v2\qgis_chain_dataset_summary.json` -> summary matches 3,059 records / 973 unique chains / 376 L3 bridge records.
- PowerShell JSONL inspection -> rows 3,059, unique chains 973, target split 2,683 QGIS-only and 376 QGIS+L3, source split 867/1,021/1,171, and task-text quality caveats above.

Follow-up artifact:
- `scripts/generate_qgis_chain_descriptions.py` generated `outputs_v2/qgis_chain_dataset_described.jsonl` with one row per unique QGIS chain. It uses deterministic templates rather than external LLM/API calls (`llm_generated=false`), so descriptions are operator-intent rewrites, not verified original task semantics.
- Verified described dataset counts: 973 rows / 973 unique chains; modality split pure vector 587, pure raster 140, mixed 246; L3 bridge rows 121; ambiguous chains 352; strict `confidence > 0.8` rows 443; length range 2-15.
- This artifact is suitable for Phase 2 retrieval/rerank experiments and weak query augmentation. It should not be treated as high-confidence semantic truth for supervised generation training without manual/LLM audit.
- Phase 2 user-reported ablation found described data underperformed original data on 20 retrieval probes: avg quality 0.9625 vs 0.9825, L3 bridge hits 12/20 vs 15/20, and B better than A 0/20. Root cause is that current retrieval depends more on L3 bridge coverage than template text. Original has 376 bridge records, while unique-chain described data has only 121 bridge chains.
- Fixed one real compatibility bug: `QGISChainRetriever` now reads top-level `modality` from described rows in addition to `quality.is_pure_vector/is_pure_raster`, so described rows can receive vector/raster type bonuses. Regenerating described data still has 121 L3 bridge rows, confirming this is unique-chain bridge coverage rather than accidental dedup loss.

2026-05-31 QGIS bridge expansion follow-up:
- Built `outputs_v2/qgis_l3_crosswalk_candidates.csv/.json` with 124 high-frequency unmapped QGIS/GDAL/SAGA algorithm candidates for manual review.
- Manual review accepted 18 mappings, rejected 7 clear semantic mismatches, and left 17 uncertain for later. Accepted mappings were merged into `outputs_v2/id_mappings_v2.json`; backup exists at `outputs_v2/id_mappings_v2.backup.20260531T020712.json`; review summary is `outputs_v2/qgis_l3_crosswalk_review_summary.json`.
- Accepted examples include `native:mergevectorlayers -> L3_01_03_04`, `native:extractbyexpression/native:extractbyattribute -> L3_02_06_02`, `native:extractbylocation/native:selectbylocation -> L3_02_06_03`, `native:joinattributesbylocation/qgis:joinbylocationsummary -> L3_02_04_01`, `gdal:warpreproject -> L3_03_05_02`, `gdal:translate -> L3_07_04_05`, and `gdal/native:fillnodata -> L3_03_03_A`.
- Rejected examples include `native:createspatialindex`, `gdal:rasterize`, `gdal:polygonize`, `native:pixelstopolygons`, `gdal:rasterize_over`, `native:joinattributestable`, and `native:creategrid`; these must remain blocked unless the L3 taxonomy grows suitable concepts.
- User-reported 20-probe ablation: baseline avg top-1 score 0.5757 / quality 0.9825 / L3 bridge hits 15/20 / modality 19/20 / bridge coverage 376 (12.3%); after 18 crosswalk mappings: score 0.6651 / quality 0.9950 / hits 19/20 / modality 20/20 / bridge coverage 760 (24.8%); after QGIS semantic tags: score 0.6982 / quality 0.9950 / hits 18/20 / modality 19/20 / bridge coverage unchanged.
- `scripts/build_qgis_chain_dataset.py` now emits `qgis_semantic_tags` for QGIS-native concepts without L3 mappings, including the high-frequency `native:reprojectlayer` as `vector_crs_transform`. `QGISChainRetriever` indexes these tags and applies a small tag bonus.
- Caveat: current semantic-tag bonus is unconditional for chains with tags; it raises top-1 score but did not improve L3 bridge hits on the 20-probe report. Treat it as experimental. A better version should match query/L3 intent to tags instead of rewarding all tagged chains.
- Subsequent fix made semantic-tag scoring query/L3-aware and added a landing-only native bridge for `native:reprojectlayer` as `qgis_native:vector_crs_transform`. This stays out of `id_mappings_v2.json` and does not create an L3 mapping.
- Local rerun after tightening native-bridge and modality-match accounting: `python scripts\evaluate_qgis_retrieval_ablation.py` -> avg score 0.7846, avg quality 0.9950, L3 bridge 175/200 (87.5%), native bridge 40/200 (20.0%), combined bridge 200/200 (100.0%), modality 200/200 (100.0%), accepted boost 138/200 (69.0%), rejected leakage 1/200 (`native:creategrid`, uncertain category, not bridge-mapped). Category L3 rates: vec_analysis/filter/raster_proc/vec_rast_mix all 100%, crs_geom 75%, uncertain 0%.
- Important interpretation: combined bridge is now the right landing metric because some QGIS-native operations deliberately remain outside L3. L3 bridge alone drops because native bridges are separated rather than forced into L3.
- Integrated QGIS landing into `scripts/evaluate_execution_aware_selector.py` as shadow diagnostics via `--use-qgis-landing`. It runs after final L3 selection, converts selected token ids to L3 codes, retrieves QGIS chains with `QGISChainRetriever`, evaluates the top candidates, and writes per-sample `qgis_landing` plus aggregate report metrics. It does not change L3 selection or final usability.
- New CLI args: `--use-qgis-landing`, `--qgis-chain-dataset`, `--qgis-catalog`, and `--qgis-landing-k`.
- Smoke verification: `python scripts\evaluate_execution_aware_selector.py --num-samples 2 --use-qgis-landing --output-dir outputs_v2\diagnostics\execution_aware_selector\qgis_landing_smoke_2` completed. JSON summary showed QGIS top1 valid 1.0, avg quality 1.0, L3 bridge 0.5, native bridge 0.5, combined bridge 1.0 on the 2-sample smoke.
- Test verification: `python -m unittest tests.test_execution_aware_selector -v` -> 10 tests OK.
- Server 3k shadow report at `outputs_v2/diagnostics/execution_aware_selector/dpo_qgis_landing_test_3k/`: final L3 usable 0.9997, QGIS landing top1 valid 1.0, avg quality 1.0, combined bridge 1.0. However, per-sample analysis shows L3 bridge only 1021/3000 (34.0%) and native bridge 1979/3000 (66.0%), driven by `native:reprojectlayer` appearing in 1,979 top-1 chains.
- QGIS landing top-1 diversity is limited in the 3k report: only 47 unique top-1 QGIS chains and top-10 chains cover 83.1% of samples. Several task types have high concentration (e.g., Surface thermal properties top chain 56.6%, Water quality 52.6%, Land use/land cover 32.6%).
- Interpretation boundary: the 3k run proves the shadow landing machinery can always find a rule-valid combined bridge for current GEE-derived final L3 outputs, but it does not prove strict semantic QGIS-chain correctness. The current landing policy overuses native CRS/reproject chains and needs semantic/diversity auditing before production claims.
- End-to-end 50-task showcase report at `outputs_v2/diagnostics/end_to_end_probe_50/`: natural-language task -> DPO v2 L3 sequence -> QGIS landing now runs as a complete prototype. Automatic metrics were L3 rule-usable 49/50, QGIS top-1 valid 50/50, combined bridge 50/50, L3 bridge 40/50, native bridge 10/50, mean QGIS quality 1.0. Manual review found strong remote-sensing/raster L3 planning, but weak traditional vector/QGIS-native intent modeling; QGIS landing often recovers useful chains but remains template-like.
- Random GEE 50-sample L3-only manual audit at `outputs_v2/diagnostics/gee_l3_probe_50/`: final usable 50/50, mean LCS/ref length 0.4608, mean Set-F1 0.5692. Manual grades were A=15, A/B=17, B=15, B/C=2, C=1; therefore A-or-A/B = 32/50 and B-or-above = 47/50. Interpretation: on the original GEE/remote-sensing distribution, the L3 planner can produce usable planning skeletons; many sequence-metric gaps are long-script compression rather than hard semantic failure. The remaining bottleneck is QGIS/vector-native generalization, special algorithms, and parameter/execution-level grounding.
- Added `docs/llm_graphrag_qgis_workflow_summary_zh.md` to capture the system-level positioning discussed on 2026-05-31: LLM is suitable for entry task structuring and final explanation, the trained small model remains the core L3 planner, QGIS landing + Neo4j/GraphRAG provide candidate chains and evidence, and LLM-based correction must be evidence-constrained rather than an unverified final judge. The recommended next data step is high-quality QGIS/vector preference data, not raw QGIS corpus mixing.
- Current main remaining issues are now framed as two buckets: (1) weak traditional vector/QGIS-native workflow handling, which needs higher-quality QGIS/vector preference data; and (2) incomplete fine-grained planning in complex tasks, where the model often produces a correct skeleton but still misses key steps. The next step should address both through stronger task structuring, evidence-constrained repair, and better preference supervision.

- Added docs/qgis_vector_resolution_and_benchmark_plan_zh.md as the short-term TODO for resolving vector/QGIS-native workflow weakness and planning a horizontal benchmark against LLM-only, LLM+RAG, current system, and improved system on the same task set.

## 2026-07-13 Vocabulary-Activation Data Audit

- Read-only server audit found that the 107-vocabulary package has 113,466 rows: 76,884 base quality-gate rows, 18,111 `vocab_expansion_mining` rows, 11,277 `py_script_vector_mining` rows, 4,253 repeated canonical rows, plus smaller targeted sources. The five-code activation package repeats 15,410 target rows five times, producing 77,050 activation rows and 172,405 total rows.
- The 18,111 expansion rows are not natural-language supervision. They contain only 179 unique L3-code-chain prompts; the five activated codes cover 150 overlapping chain prompts. The mining script converts unordered `set`-based QGIS algorithm matches into labels, retains only new-code matches, drops old workflow steps, and uses broad patterns such as `grid`/`warp`. These rows cannot be repaired merely by adding descriptions; ordered source chains must be re-extracted and relabeled.
- The older vector data is not one homogeneous 20K set. `vector_unified` has 4,091 QGIS augmentation rows and 3,037 LLM source-code rows with natural-language text, but known placeholder/conflict/weak-label risks. The 11,277 PY-mined rows also use code-chain prompts. Phase 11's cleaner 81,137-row package instead uses 685 unique canonical natural-language tasks repeated to 4,253 rows.
- Existing natural-language candidates are substantial: `qgis_complete_ALL.jsonl` has 2,754 rows and 1,152 rows whose QGIS chains contain at least one of Reproject/FixGeom/Grid/Simplify/Snap (732/466/135/74/76 respectively; overlaps allowed). However, basename-only `script_xxx` joins can collide across source directories; observed same-ID task changes mean provenance/path-level joins and description-chain consistency checks are mandatory before training.
- The 685-row clean canonical seed contains 299 unique tasks whose actual `qgis_ops` include at least one activation target: Reproject 178, FixGeom 120, Grid 40, Simplify 20, and Snap 19 (counts overlap). All 685 texts are nonblank and unique, but the packaged Phase 11 copies omit explicit START/END and the 299 target-bearing rows use old 94-vocabulary mappings. Rebuild their labels and sequence framing under the experimental 107 profile before mining weaker sources.
- Activation evaluation is also invalid until it uses a 107-specific transition matrix, 107 hierarchy metadata, Set Predictor off or retrained, and held-out natural-language prompts containing the new targets. The old matrix is 94-vocabulary and val/test contain zero target tokens.
- Raw-source inventory of `/home/yll/GEE/工作流抽取结果/QGIS` shows this directory is primarily extracted workflow artifacts, not the full 398,483-PY corpus: 262,901 files / 30.1 GB, including 52,422 AST JSON files, 52,422 steps CSV files, and only 721 `.py` files. Across merged process tables there are 52,329 path-qualified script records, 49,997 unique basenames, and 8,080 records with explicit `processing.run`.
- Strict operation matching in that directory finds 5,907 path-qualified / 4,684 basename-unique candidates containing at least one activation target. Path-level counts are Reproject 4,956, FixGeom 1,107, Grid 356, Simplify 188, and Snap 181; counts overlap and include a duplicated L1 output directory.
- AST text is abundant but noisy: 28,906 ASTs have a module docstring and 27,507 contain at least five English words, but many are license headers, Plugin Builder banners, or generic exported-model text. High-density first-pass sources should be the deduplicated L1, strict-multistep, processing-chained, model/tutorial, and RouteB directories. Their target candidates total 1,771 path records, 822 with a module docstring, but only about 162 pass a deliberately strict task-like-text heuristic before cross-directory deduplication.
- The extraction directory does not preserve authoritative original source paths in each AST/steps artifact; `source_script` is usually only a basename. The next data build must recover upstream path provenance, use ordered `statement_index`/scope rather than sets, hash-deduplicate scripts/chains, reject raster/vector pattern collisions, and join facts/docstrings/README text only through a path-aware key.
- `outputs_v2/_yll_update/facts_summary1000.csv` is a strong full-107 reconstruction input: 20,428 rows, all with nonblank task name/description, 20,394 unique descriptions, and 20,413/20,428 matching both AST and steps artifacts. Text length is 111 words median, 154 p90, 198 p99, and 307 max. It is code-grounded natural-language summary data, not proof of human-authored ground truth.
- Facts linkage still needs controls: 1,887 matched basenames appear in multiple extraction directories and raw task types contain 3,073 distinct strings. Heuristic text flags find 798 test-related, 2,047 UI-related, and 2,841 rendering/style-related rows with overlaps; rendering mentions are not automatic rejects if the AST also contains substantive processing.
- The existing exact-chain funnel reaches only 2,934 rows in `qgis_complete_v4.jsonl` (1,520 vector, 1,013 mixed, 333 raster, 68 unknown), despite nearly complete facts-to-AST linkage. It has 2,149 unique chains and severe long-chain outliers up to 607 steps. To exploit the estimated ~15,700 high-quality descriptions, rebuild ordered full-107 labels from both `processing.run` algorithms and grounded direct QGIS/GDAL APIs, rather than training on text alone or forcing a label when code evidence is weak.
- Consensus planning completed for the first real-data pilot. Approved plan: `.omx/plans/full-107-qgis-pilot.md`. It keeps 94/GEE stable, treats 107 as an experimental starting taxonomy, builds path/hash provenance and T0-T4 evidence tiers, proposes approximately 300 records split into non-mergeable estimation-reference and coverage-diagnostic subsets, and stops for explicit user approval of subset sizes/reviewer policy before batch conversion. No training, taxonomy mutation, scaling, or production switch is authorized by this plan.
- Local synchronization is now a binding phase-close requirement: critical server scripts/configs/prompts/schemas/tests must be copied back into the local repository; taxonomy, authority, quality-gate, review, training-admission, and migration decisions must update `task_plan.md`, `progress.md`, and both context documents. Large data stays on the server, while manifests, hashes, statistics, reproducible builders, and bounded review fixtures are synchronized locally. Secrets are never synchronized.
- Phase 0 execution started on 2026-07-14 in isolated branch `feature/qgis-evidence-pilot`. A sidecar authority report now proves three divergent stable-94 surfaces: vec11277 `vocab_profile`, Step8/V4.6 `run_contract`, and quality-gate V4.6 entry points. The run-contract Transformer and Set Predictor defaults are missing on the server, while vec11277 and quality-gate assets exist. Execution is stopped at the required authority decision gate before large checkpoint hashing/copy, restore smoke, or Phase 1. Reports are mirrored at `docs/reports/qgis_pilot/phase0/` and `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase0/`; 20 local related tests and 6 synchronized server pilot tests passed.
- The corrected authority report also separates `phase11_vector_sft_94`: oversampled workflows/splits/task vocabulary/length stats, the quality-gate transition matrix, the epoch-4 best-composite checkpoint, and Phase 11 logs. The generic quality-gate checkpoint directory had been reused by Phase 11, so pairing that checkpoint with base quality-gate data is not reproducible. The existing quality-gate evaluation JSON is a 500-row all-zero smoke with conflicting configured/effective checkpoint paths and is not accepted as the stable GEE metric authority.
- The user deferred stable-94 backup work and made QGIS data reconstruction the mainline. Phase 1 read-only inventory matched 20,413/20,428 facts rows, found 18,526 unique extraction-group joins and 1,887 multi-group basename collisions, and indexed 262,110 artifacts. Additional text evidence includes 2,009 plugin metadata files, 2,054 READMEs, 851 model/tutorial metadata files, and two fine-evaluation CSVs; 48,011 source scripts are code/docstring candidates, not automatically valid descriptions. Source-root metadata remained unchanged and all writes are ledgered under `/home/qy`. The experimental 107 ID mapping has 107 IDs but zero of its 464 QGIS mappings target the 13 added codes, so Stage 2 requires a reviewed 107-specific crosswalk built from ordered evidence.
- Taxonomy audit scanned 15,942,213 merged-process rows and found that the current 13 additions reuse legacy 350-taxonomy codes with incompatible meanings. The current 107 draft must not be frozen. Real-script evidence supports most intended capabilities but requires separate Define CRS, Geometry Validation, Rasterize, Polygonize, Table Join, and Feature-to-Polygon decisions. The working recommendation is 112-114 classes, default draft 113, pending explicit decisions on Spatial Index, Concave Hull, and direction-specific raster/vector conversion.

### 2026-07-14 - Experimental 114-Class Taxonomy Freeze

- The reviewed QGIS sidecar is now `qgis_l3_v1_114_experimental`. It preserves all stable-94 token IDs `0..93` and assigns 20 reviewed additions to `94..113`. Production remains on 94.
- User decisions are frozen: keep Add Spatial Index, keep Concave Hull independent, and model Rasterize Vector versus Polygonize Raster as separate directional classes.
- The invalid `v3_107_experimental` profile is marked `invalid_code_reuse`. Its 13 added tokens require source-profile-aware semantic migration; code-string replacement is forbidden because several strings had legacy meanings.
- Generated artifacts live in `configs/taxonomy/`: `qgis_l3_v1_114.json`, migration JSON, and added-class CSV. The builder is `scripts/build_qgis_taxonomy_v1.py`; coverage is in `tests/test_qgis_taxonomy_v1.py`.
- Validation proves exactly 114 unique IDs `0..113`, unchanged stable-94 IDs, no collision with the 350-class registry, 49 unique normalized aliases, closed migration targets, complete parent metadata, and deterministic UTF-8/LF JSON.
- Legacy `L3_06_01_02` Delaunay reactivates parents `L1_06/L2_06_01`, which are absent from the stable-94 vocab. The sidecar records this explicitly and supplies `L1_06 = 3D and TIN Analysis`; production L1/L2 vocab is unchanged.
- Local and server artifacts are byte-identical. SHA256: taxonomy `c23b91566e672fa9b2701bb411cad7acfbd636c1219b93d454d07f644eccc739`; migration `5d285d2573198598d9d89cbed96491156fe0dd43dac814f59d291fab2adf278c`; CSV `70baf9c251a6d93176c407fabda34eebb5efe751f84248512956a26c2fcf5970`.
- Server warning: `/home/qy/system_redesign/outputs_v2/id_mappings_v2.json` claims 94 in metadata but contains 107 IDs. It was not modified. Server validation uses the frozen 94 input under `/home/qy/system_redesign/configs/taxonomy/inputs/`.
- Verification: 16 local QGIS pilot/taxonomy tests and 6 server taxonomy tests passed. No training, DeepSeek call, production switch, or `/home/yll` write occurred.
- Next: rebuild ordered, path/hash-qualified QGIS evidence against the 114 alias index, preserve unresolved/degraded evidence, then produce the approximately 300-record disjoint review-sampling proposal before any conversion or training.

### 2026-07-14 - First Full 114-Aware Ordered-Evidence Scan

- The stable-94 expanded crosswalk and 49 reviewed addition aliases were merged into 325 audited entries and 228 exact L3 aliases. Ten known old semantic misassignments are explicit allowlisted reassignments; every other conflicting L3 target still fails closed.
- The server streamed 15,942,213 process rows and retained 1,683,292 relevant QGIS/direct/custom API rows across 21,085 path-qualified records. AST/steps hashes and extraction-group identity are preserved; unresolved collisions remain T0.
- Provenance: 16,936 resolved and 4,149 unresolved-collision records. Ordering: 2,578 deterministic and 18,507 degraded. Mapping: 24 complete-exact, 2,450 partial-exact, and 18,611 unmapped records.
- All 20 added classes have real exact-alias evidence (12-599 records per class), so no added class is currently evidence-empty. This does not make the records training-ready.
- Most unmapped volume is low-level infrastructure such as `QgsProcessingAlgorithm.addParameter`, `QgsProject.instance`, `QgsField`, and `QgsVectorLayer`; treating each call as an L3 operation would recreate the prior over-fragmentation error.
- The 1.6 GB ordered JSONL remains server-side diagnostic data only. Local bounded reports are under `docs/reports/qgis_pilot/phase2_ordered_114/`.
- Next gate: bounded direct-API compaction, semantic aggregation, and statement-index repair before proposing the approximately 300-record human-review subsets. No sampling, DeepSeek conversion, or training is authorized yet.

### 2026-07-14: Direct-API Aggregation Coverage Pilot

- Low-level QGIS calls are compacted into processing operators, semantic anchors, data access, infrastructure, and unknown evidence. Duplicate runs are encoded and missing statement indices remain fallback ordered.
- The final server build reduced 21,085 records to 5,107 eligible records and selected 300 unique coverage-diagnostic rows. It excluded 4,149 T0/collision rows and 11,829 rows with no processing or semantic anchor.
- Sampling covers extraction group, evidence source mode, deterministic modality hint, trace length, semantic family, and ordering quality. The final pilot has 174 direct-API-only, 83 processing-only, 38 processing+custom, and 5 custom-only rows; modality hints are 108 vector, 44 raster, 124 mixed, and 24 unknown.
- `scripts/run_qgis_api_aggregation_pilot.py` enforces a fail-closed `gpt-5.6-luna` contract: bounded 114-crosswalk operators only, record evidence citations, exact L3 mapping, confidence >=0.70, no raw response or hidden reasoning persistence, and fingerprint-based resume.
- Offline preflight found 228 taxonomy-mapped operators and bounded candidates for 292/300 rows. Eight custom or pending operators are rejected before any provider call.
- OpenAI SDK 2.45.0 is installed on the server, but `GGUUAI_API_KEY` is not set in the process environment. No live request was attempted. Do not recover keys from chat or fall back to another provider; run one `--max-records 1` smoke only after external environment setup.
- Reports are under `docs/reports/qgis_pilot/phase3_api_aggregation/`. The 56.2MB pool, 3.07MB full pilot JSONL, and 2.15MB preflight JSONL remain server-side. The pilot is not training data until provider proposals and human adjudication are complete.

### 2026-07-15: Pilot-Guided Compaction Revision

- Three bounded audits of the 300-record pilot identified deterministic UI/framework noise and missed semantic direct APIs. Regression-tested rules now classify feedback, parameters, renderers, registries, and project UI as infrastructure; metadata/geometry/OGR reads as data access; and spatial predicates, rasterize/polygonize, GDAL warp/translate, raster merge, and centroid as semantic anchors.
- Eligible records increased from 4,506 to 5,107. Unknown calls in the selected pilot fell from 3,477 to 1,328 (61.81% reduction). Remaining unknown calls are preserved for human review rather than force-mapped.
- Newly explicit pilot families include centroid 14, data export 20, polygonize 16, raster merge 14, rasterize 10, and spatial predicate 11.
- The reproducible offline provider preflight yields 292 ready rows and 8 zero-candidate rows, with median 4 candidates and median prompt length 5,293.5 characters. It writes a review workbook, summary, ledger, and a separate zero-candidate queue without reading an API key or making live calls.

### 2026-07-15: Code-Constrained Description Admission Policy

- The user approved generating a natural-language task description for a real, path/hash-qualified script when its ordered QGIS operator chain and 114-L3 chain are evidence-bound and human-reviewed but no reliable original task text exists.
- These records are explicitly `silver`, never original gold. The generated text may only verbalize verified evidence: it must not add, remove, or reorder operations and must preserve visible modality, input roles, parameters, CRS, overlay direction, and output type. Insufficient evidence requires rejection.
- Every silver row must retain source path/hash, evidence IDs, operator and L3 chains, generator version, review status, and parent record ID. It is train-only and must be split as a source-script group so no derivative reaches validation or test.
- `facts_summary1000.csv` remains code-grounded/silver candidate material unless human-authored provenance is demonstrated. Controlled paraphrase counts, training weights, and a 20K row quota are not yet approved; decide them only after measuring stratified pilot acceptance and error rates.
- The first live smoke attempted one record and returned HTTP 403 because the value injected into the tmux environment was only two whitespace characters and failed the expected key shape. The invalid value was removed. The gate admitted zero proposals, wrote an empty proposal JSONL, and persisted no raw provider response or reasoning. Re-inject a complete key interactively, validate only shape/length without printing it, and rerun one `--max-records 1 --max-attempts 1` smoke before any canary.

### 2026-07-15: GGUUAI Compatibility and Live Smoke

- GGUUAI documentation explicitly lists `https://gguuai.com/v1` and `https://api.minimax.love/v1` as OpenAI-compatible endpoints and names the OpenAI SDK as supported. The API and `gpt-5.6-luna` are usable; the failure was compatibility behavior, not lack of chat/API support.
- Differential tests proved the gateway returns 403 only when the SDK default `User-Agent: OpenAI/Python 2.41.0/2.45.0` is present. The Stainless headers are accepted. The provider client now uses `GGUU-QGIS-Pilot/1.0`, preserving the SDK and strict response parsing.
- The prompt now includes an exact `allowed_rejected_infrastructure` list and directs data-access/unknown evidence to `unsupported_evidence_ids`. This resolves a real provider-contract mismatch without relaxing validation.
- The server route can return `reasoning_content` by default. `reasoning_effort=none` was ignored, while `extra_body={"thinking":{"type":"disabled"}}` suppressed reasoning and produced validator-compatible JSON.
- Final server smoke: one attempted record, one validated proposal, no raw response or reasoning persisted. The four bounded candidates are `gdal:polygonize`, `qgis:buffer`, `gdal:rasterize`, and `qgis:rastercalculator`; the row remains `pending_human_review` and forbidden for training. Local and server aggregation test suites each pass 24 tests.
- Next gate: a stratified 20-30 record canary followed by human semantic audit. Do not run all 292 ready rows yet.

### 2026-07-15: Stratified 24-Record Canary Stopped Scaling

- A deterministic canary selector excluded the completed smoke and chose 24 unique records/source scripts. Source modes are exactly 8 direct API, 8 processing-only, and 8 processing+custom; the set covers all four modalities, three trace lengths, both ordering qualities, four extraction groups, and 24 distinct primary families.
- Results: 24 attempted, 15 validator-approved proposals, contract pass rate 62.5%. Failures are 8 `provider_returned_reasoning` and 1 `unknown_operator`. The <70% pass-rate threshold and >30% repeated-failure threshold both fired, so scaling is blocked and the remaining 268 ready records were not called.
- Reasoning was detected in memory and rejected; no raw response or reasoning was persisted. The server route does not honor `thinking.type=disabled` consistently across records/channels.
- AI-assisted preliminary semantic review of the 15 contract-valid proposals produced A=8, B=4, C=3. This is not human adjudication. C-level examples expose missing direct-API semantic compaction (dissolve/buffer/simplify), an unmapped custom `identify dangles` operator, and severe compression of a complex fragmentation workflow.
- Artifacts are synchronized under `docs/reports/qgis_pilot/phase3_api_aggregation/canary_24/`. The review workbook remains pending and every row remains forbidden for training.
- Next work is diagnostic, not scaling: stabilize no-reasoning provider behavior, close reviewed custom/direct-API semantic gaps, then run a new bounded canary.

### 2026-07-15: Evidence-Route and Class-Signature Audit

- The canary contains 8 direct-API-only, 8 processing-only, and 8 processing+custom records. Provider reasoning failures are unrelated to source completeness; the unknown custom operator is a crosswalk gap, while missing direct-API steps are extraction/semantic-compaction gaps.
- Ordered evidence retains `scope` but not `_steps.csv.args`; compaction then drops `scope`. Class names and parameter labels therefore do not reach the current provider mapping at all.
- In the current 5,107 eligible pool, 260 records have scope, 224 have class scope, and none have an exact class/catalog match. Across all 21,085 Phase 2 records, only 14 records and 9 unique classes match exactly. This facts-linked corpus is not primarily official algorithm implementation traces.
- The separate QGIS Core Processing source has 110 `_steps.csv` files: 106 contain class scopes, 97 retain parameter args, 61 files have an exact normalized catalog match, and 13 classes are provider-ambiguous. Class and parameter signatures are valuable here but do not approach 20K workflows.
- Use this source to build a fully reviewed operator-signature anchor library. Preserve provider/path, class, parameter and output schemas; disambiguate GDAL/native/QGIS collisions before mapping. Then evaluate the anchors on separate ordinary direct-API workflows.

### 2026-07-15: Core Processing Signature Review Package

- `scripts/build_qgis_core_signature_review.py` now builds a review-only package from all 110 Core Processing traces and the 1,292-record catalog using structured CSV parsing. It retains source/AST hashes, imports, class bases, ordered structured arguments, parameter/output schemas, and provider evidence.
- Matching is fail-closed. Only a unique provider-consistent exact class match becomes `auto_proposed_pending_review`; ambiguous, conflicting, non-exact, and no-class rows remain unresolved. There is no top-1 fallback and no LLM call.
- Server result: 110 source files, 117 class signatures, 121 review rows, 61 pending exact proposals, and 60 unresolved rows. The unresolved split is 54 no exact match, 1 provider-evidence ambiguity (`RasterCalculator`), 1 provider conflict (GDAL `Buffer`), and 4 no-class rows. Accepted anchors=0 and training rows=0.
- The 13-provider-ambiguity figure from the earlier scan was pre-evidence. AST imports, class bases, and trace provider calls reduce the final ambiguity queue to one while preserving a separate conflict row. Provider detection now uses token boundaries so `setProgress` and `Histogram` do not create false OGR/GDAL evidence.
- The full 15MB record stays on the server at `outputs_v2/qgis_pilot/pilot_v1/phase3_core_signature_review_110_v1/`; bounded review artifacts are synchronized under `docs/reports/qgis_pilot/phase3_core_signature_review_110_v1/`. Full JSONL SHA256 is `011973f7a835a9bf7d99d782900ec991e6588ec93a690ab8ca2e5766e8111698`.
- Next gate: human-adjudicate all 121 rows, export only accepted anchors, then measure transfer on a separate 50-record ordinary direct-API workflow sample. Do not train or count operator definitions as workflows.

### 2026-07-15: Signature Adjudication Batch 01

- The user explicitly accepted the first 10 exact GDAL signatures after joint review. Decisions cover AssignProjection, raster/vector extent clipping, ColorRelief, GDAL Dissolve/ExecuteSql, and four GDAL gridding variants.
- The immutable proposal workbook remains unchanged. Decisions are stored in `adjudication_decisions.jsonl` and validated against record/class keys, trace hashes, bounded candidate IDs, and the source review SHA256 by `scripts/validate_qgis_core_signature_adjudications.py`.
- Current cumulative status: 10 accepted anchor candidates, 111 review rows remaining, zero training rows. Anchor export remains blocked until all review rows are adjudicated.
- Batch 02 added 10 more user-confirmed GDAL anchors, bringing the cumulative count to 20 accepted and 101 remaining. `contour` and `contour_polygon` share a source file but remain separate operator anchors, not a generated workflow chain.
- Before Batch 03, review v1 was found to misclassify scalar controls `merge.NODATA_OUTPUT` and `Heatmap.OUTPUT_VALUE` as outputs. The builder now derives direction from the QGIS parameter class and emits `qgis_core_signature_review_v2`. A full 121-row comparison found no key, trace, candidate, proposal, or status changes; only those two parameter schemas changed. The 20 confirmed decisions were migrated with provenance. Review v2 SHA256 is `d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4` and is now authoritative.
- Batch 03 added 10 user-confirmed exact GDAL anchors. Cumulative status is 30 accepted and 91 remaining. `gdalinfo` and `ogrinfo` are accepted as Processing operator signatures only; taxonomy and training admission remain separate decisions.
- Batch 04 added 10 user-confirmed exact GDAL anchors. Cumulative status is 40 accepted and 81 remaining. GDAL provider evidence and parameter schemas disambiguate `rasterize` and `translate` from native namesakes. Training rows remain zero and anchor export remains blocked.
- Batch 05 added 10 user-confirmed exact GDAL/QGIS provider anchors. Cumulative status is 50 accepted and 71 remaining. Plot and other Processing signatures remain anchors only and gain no automatic taxonomy or training admission; training rows remain zero.
- Batch 06 added 10 user-confirmed exact QGIS anchors. Cumulative status is 60 accepted and 61 remaining. Histogram, scatterplot, and other reporting signatures remain anchor-only; training rows remain zero and export stays blocked.
- Batch 07 recorded a mixed user-confirmed decision: five provider/schema aliases accepted and four GDAL framework/UI classes rejected as non-anchors. Cumulative status is 69 decisions, 65 accepted, 4 rejected, and 52 remaining. Source inspection confirms `createcog` and `dataset_identify` are real algorithms, but review v2 lacks correct bounded candidates, so both remain pending rather than being misclassified.
- Batch 08 recorded seven source-name/provider/schema-backed GDAL aliases and rejected two utility/data classes. Cumulative status is 78 decisions, 72 accepted, 6 rejected, and 43 remaining. `ogrinfojson` is a distinct real algorithm but remains pending because review v2 lacks its bounded operator candidate; it must not be merged into `gdal:ogrinfo`.
- Batch 09 accepted eight GDAL/QGIS parameter-backed aliases and rejected an empty-class trace plus `ParameterExecuteSql` as non-anchors. The empty class was recorded under its original `(script_56361, "")` key. Cumulative status is 88 decisions, 80 accepted, 8 rejected, and 33 remaining.
- Batch 10 accepted seven QGIS aliases and rejected three QGIS framework/provider classes. `PointsFromLines` and `RasterCalculator` contain GDAL calls but inherit `QgisAlgorithm` and expose QGIS operator IDs through `name()`, resolving provider ambiguity without relaxing candidate bounds. Cumulative status is 98 decisions, 87 accepted, 11 rejected, and 23 remaining.
- Batch 11 accepted only three actual Processing operators and rejected seven parameter, graph-helper, framework, or configuration classes. Cumulative status is 108 decisions, 90 accepted, 18 rejected, and 13 remaining. The remaining set consists of three known catalog-candidate gaps and ten final review rows.
- Batch 12 rejected the final ten ordinary rows, covering script actions, providers, editors, examples, and no-class traces. Cumulative status is 118 decisions, 90 accepted, 28 rejected, and 3 remaining. Ordinary v2 adjudication is complete; only the source-confirmed real algorithms `gdal:createcog`, `gdal:dataset_identify`, and `gdal:ogrinfojson` remain, and they require a controlled candidate-authority migration before acceptance.
- Controlled review v3 is now generated by a new TDD-covered migrator and audited three-row manifest. Target review SHA256 is `af39d5cbc43f92e35ca8ecd28605f015f64a68d8236234fa66e2e8857a942f98`. A structured 121-row diff proves only the three target rows changed and only in five candidate/proposal fields; 118 existing decisions migrated with immediate-source provenance. Status remains 90 accepted, 28 rejected, 3 pending, zero training rows. Migration did not accept the new candidates; explicit human adjudication remains required.
- Batch 13 explicitly accepted the final v3 candidates `gdal:createcog`, `gdal:dataset_identify`, and `gdal:ogrinfojson`. The 121-row review is complete: 93 accepted anchors, 28 rejected non-anchors, zero remaining, zero training rows, and `anchor_export_admission=ready`. The next gate is deterministic export of only the 93 accepted anchors followed by transfer evaluation on 50 independent ordinary direct-API workflows. Taxonomy and training admission remain separate.

### 2026-07-15: Signature Anchor Export and Independent Transfer Diagnostic

- Exported 93 unique human-accepted signature anchors (GDAL 59, QGIS 34) with taxonomy/training admission explicitly not granted. The synchronized anchor JSONL SHA256 is `0a3e1ebf1113bf8aa6da5b0823e3daf282083d0b934f8a9cbad43e7e6bdf40e2`.
- Added a deterministic exact-operation dual-IDF evaluator. It excludes all prior 300-pilot and 24-canary records, uses 4,673 unique-source `direct_api_only` workflows, and performs zero LLM calls.
- Reproduced the exploratory baseline exactly: 3,388 candidate-bearing workflows (72.50%) and 1,285 abstentions. This is candidate coverage, not accuracy.
- Generated a 50-record review package with 30 candidates and 20 abstentions, unique record/source IDs, and balanced modality/family/length/ordering fields. Human precision and abstention accuracy remain null pending review; no training rows were emitted.
- Preliminary inspection found systematic implementation-call false positives. `gdal.open` appears in 439 workflows (9.39%), narrowly passes the 10% threshold, and causes `gdal:extractprojection` to dominate 12/30 candidate rows. A semantic-anchor-only diagnostic reduced coverage to 1,127 but still produced shared-call errors. Exact signature transfer is therefore evaluation-only and must not auto-label workflows.
- Local stable-94 QGIS regression passed 88/88. Server transfer/export tests passed 7/7; two pre-existing taxonomy tests fail because the server data mirror now exposes 107 IDs while those tests require exactly 94. No server configuration was overwritten.
- Active artifacts: `docs/reports/qgis_pilot/phase3_signature_anchor_library_v1/` and `docs/reports/qgis_pilot/phase3_signature_transfer_evaluation_50_v2/`. Next action is joint human review of all 50 rows before any family/text reranker design.

### 2026-07-16: Signature Transfer Human Review Batch 01

- The user confirmed rows 1-5: rows 1, 2, 3, and 5 are incorrect top-1 transfers; row 4 correctly maps raster boolean overlay to `qgis:rastercalculator`.
- Added a TDD-covered append-only adjudication validator. Decisions bind the immutable review SHA256, review order, record ID, candidate status, and top-1 operator; incorrect rows do not invent replacement operators.
- Current partial result is 5/50 reviewed, 1 correct and 4 incorrect candidate predictions, candidate top-1 precision 20%, 45 remaining. No abstentions have been reviewed, so abstention accuracy remains null. Taxonomy and training admission remain not granted.

### 2026-07-16: Signature Transfer Human Review Batch 02

- The user accepted rows 6-10 as incorrect top-1 transfers. Read-only AST/catalog verification identified `qgis:hypsometriccurves` for row 6 and `qgis:convertgeometrytype` for row 9.
- Row 7 is a multi-step raster workflow using warp/reprojection, raster calculation, GRASS neighborhood smoothing, and translate/export. Row 8 is the custom EnMAP-Box `ImportEnmapL1CAlgorithm`; row 10 is the custom `HZAUSoilTextureDialog` workflow. Custom classes remain unbounded instead of receiving invented catalog IDs.
- Cumulative partial result: 10/50 reviewed, 1 correct and 9 incorrect candidates, top-1 precision 10%, 40 remaining. Abstention accuracy is still null and no taxonomy/training admission is granted.

### 2026-07-16: Transfer Review Batch 03 and Source-Grounded Replacement

- The user confirmed rows 11-14 as incorrect and row 15 `qgis:rastercalculator` as correct. Cumulative partial precision is 2/15 = 13.33%, with 35 rows remaining.
- Ground truth again separates multi-step `RasterProcessor` DSM construction, custom `UrbanSummaryWorker` and FLO-2D infiltration workflows, and the standard `native:simplifygeometries` equivalent for direct `QgsGeometry.simplify()`.
- Documented a replacement source-grounded extractor with four evidence tiers: explicit Processing IDs, self-describing algorithm classes, ordered/data-dependent direct-API semantic chains, and custom/unbounded workflows. Exact signature overlap remains evaluation-only. Complete the 50-row regression set before a roughly 300-row stratified extractor pilot; no training admission is granted.
- Added editable `docs/reports/qgis_pilot/qgis_training_data_mainline.drawio` to show the end-to-end path from source evidence through extractor/regression/pilot gates to train-only data and held-out model evaluation. XML validation passed; no local draw.io CLI was available for bitmap export.

### 2026-07-16: Source-Grounded QGIS Extractor v1 Frozen

- Implemented the deterministic, fail-closed extractor in `src/gis_recommend/data/qgis_source_grounded_extractor.py` with CLI `scripts/run_qgis_source_grounded_extractor.py`. It makes no LLM/API calls and emits no training rows.
- Evidence tiers are now executable: E0 explicit Processing IDs, bounded legacy wrappers and `gdal_calc.py` data flow; E1 self-describing algorithm classes; E2 reviewed direct-API rules with exact catalog constraints; E3 custom/unbounded preservation.
- Generic GDAL opens, metadata reads, UI and infrastructure calls cannot become operators. Repeated real operations are retained, macro/micro duplicates merge only with a shared semantic step identity, and cross-source order is not invented when AST/steps coordinates are incomparable.
- The authoritative development regression is `docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/regression_15_run6_exact/`. Strict exact-ID recovery is 12/14 (85.714%); the two exact misses are `qgis:rastercalculator` and `qgis:simplifygeometries`. Old correct top-1 recovery is 2/2, old incorrect top-1 avoidance is 13/13, and custom recovery is 4/4.
- Provider-suffix grouping was rejected because it inflated recovery. Alternative provider IDs remain exact misses unless human adjudication defines an explicit accepted-alternative set.
- Frozen-code blind predictions for review orders 16-50 are in `docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/holdout_35_v1/`: 35 records, `mode=blind`, `labels_read=false`, taxonomy/training admission `not_granted`, training rows 0. They were later adjudicated without modifying this directory; decisions live in the sibling `holdout_35_adjudication_v1/` artifact.
- Local ledger verification confirms all synchronized Run6 and holdout output hashes and the extractor/CLI code hashes. Verification baseline: 36 focused extractor tests and 127 stable-94 `test_qgis*.py` tests pass locally; the focused server suite passes with one Windows-only path test skipped.
- A scoped `.gitattributes` rule pins Phase 4 report artifacts to LF so Windows `core.autocrlf` cannot invalidate the recorded SHA256 values after checkout.
- The blind gate is complete and blocks scaling. Extractor v2 must address source filtering, E3 role classification, constructor suppression, bounded identity resolution, custom-function preservation, identity gaps, and same-step duplicate merging before re-running the locked regression set.

### 2026-07-16: Blind Holdout Review Completed

- Joint user/Codex review adjudicated all 35 frozen records in seven batches. The original blind artifact was not edited; append-only decisions, summary, report, and hash ledger are under `docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/holdout_35_adjudication_v1/`.
- Item precision is E0 4/5 (80.0%), E1 unmeasured (0 predictions), E2 46/60 (76.7%), E3 12/39 (30.8%), and overall 62/104 (59.6%).
- Only 9/35 workflows (25.7%) are complete and free of emitted-item errors. Grades are 9 correct, 13 partial, 4 incomplete abstentions, and 9 incorrect.
- The main failures are six unfiltered test sources, five unit-test-class false positives, four missing custom functions, four incomplete empty predictions, and three coordinate-transform constructor false positives.
- Confirmed identity gaps include `gdal:proximity`, `gdal:merge`, `qgis:rastersampling`, `qgis:eliminateselectedpolygons`, extract/save operators, and Shapely line polygonization requiring `native:polygonize` rather than `gdal:polygonize`.
- Decision: `pilot_admission=blocked_pending_extractor_v2`. Taxonomy and training admission remain `not_granted`; no roughly 300-row pilot or training package may be generated from v1.
- All 35 orders, record IDs, source-workbook binding, summary metrics, and output hashes were verified. Adjudication SHA256 is `bcc3eb4a357980abb262487959606df641d020295c72ee5f78976289a2e0aac9`.

### 2026-07-16: Extractor v2 Design Approved

- The user approved a deterministic two-stage design: v2.1 addresses precision first, then v2.2 addresses workflow completeness. No LLM, taxonomy change, training data, or model training is allowed.
- v1 remains the default profile. v2 is explicit and cannot become default until it passes the locked regression and a new blind holdout.
- v2.1 adds source-quality gating, E3 role classification, constructor suppression, bounded-identity precedence, confirmed identity gaps, and semantic-step deduplication.
- v2.2 adds module-level custom-function call graphs and dependency-aware chain recovery.
- Hard gates: v2.1 overall precision >=80%, E2 >=85%, E3 >=70%, zero test/constructor false positives; v2.2 complete workflows >=60% with no tier precision drop greater than 5pp.
- Approved specification: `docs/superpowers/specs/2026-07-16-qgis-source-grounded-extractor-v2-design.md`. Implementation has not started.

### 2026-07-16: Extractor v2.1 Implementation Plan Completed

- The executable TDD plan and test specification is `docs/superpowers/plans/2026-07-16-qgis-source-grounded-extractor-v2-1.md`.
- v2.1 will keep the v1 compiler frozen and apply an explicit-profile deterministic precision pass in focused modules for source quality, class roles, identity/suppression/deduplication, and locked-gate evaluation.
- The locked evaluator uses operator/custom multisets. A class retained as E3 only because bounded identity was previously missed, such as legacy Eliminate, is upgraded to bounded E1 and is not also required as an E3 fallback.
- v2.2 remains blocked until every v2.1 hard gate passes. No implementation, taxonomy admission, training data generation, or model training has started from this plan.

### 2026-07-31: QGIS Planner Benchmark v0.1 Freeze

- This workstream owns only the QGIS planner benchmark; it does not alter GEE data, QGIS training data, taxonomy admission, or model training.
- Version `0.1.0` is frozen at `benchmarks/qgis_planner_v1/releases/v0.1-freeze/` with status `internal_sealed_freeze`. Its manifest binds 24 artifacts across development 40, final core 120, refusal diagnostic 12, stable101/QGIS authorities, and the unified scorer; the top-level ledger verifies 27 paths.
- `scripts/score_qgis_planner_benchmark_v01.py` scores graph and refusal splits with separate denominators, records both prediction SHA-256 values, and hashes/parses predictions before verifying or reading sealed freeze artifacts.
- Graph exact match uses operator-labeled directed graph isomorphism, while supporting operator and edge metrics remain multiset-based. Refusal scoring treats any emitted process or link as unsafe planning.
- Verification: 15 focused scorer/freeze tests passed, including full perfect-prediction smoke over final 120 plus refusal 12. No real model predictions were run. The legacy exclusion-ledger test remains environment-blocked because this worktree lacks the external Step8 quality-gate fixture; no old gate code was changed.
- Any gold change after this freeze requires a new benchmark version. The next allowed work is prediction locking and evaluation handoff.

