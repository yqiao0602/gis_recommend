# GEE Current State

Last updated: 2026-10-09

## Ownership And Goal

This workstream owns **GEE data processing only**. Its fixed goal is to convert the
existing GEE corpus into a scalable, high-quality complete-workflow training set. It
does not modify QGIS data, benchmarks, or model training.

Training rows represent complete output-relevant workflow DAGs. Historical
`mean -> clip`, 11,397-row, and local-fragment packages are calibration evidence, not
current production yield.

## Latest Verified State (2026-10-12, WS1/WS2 adjudication closure + B2-P1 repetition audit)

- **WS1 93/93 + WS2 181/181 semantic adjudications CLOSED** (final item k=370
  ruled by model delegation, owner-confirmed: structure decodes to 38 years x
  3 sensors x 19 stages + 1 = 723, exactly matching the task text — the
  "structural anomaly" hypothesis is withdrawn; stays suspicious due to
  invariant-fold defect, year x sensor loops absent from repetition_groups,
  and unverifiable source authenticity). k=370/994 are same-task twins; at
  most one may enter the trusted subset. Freeze:
  `planner_design/WS1_WS2_ADJUDICATION_FREEZE_V1.json` (six-file SHAs).
- **B2-P1 repetition-group audit v2 (dev 1,852 rows, read-only)**:
  rg.repeat vs stage.repeat agree 2,645/2,645 — zero internal inconsistency;
  the defect axis is fold semantics: condition_count_suspect 1,411 (filter
  condition counts, not execution counts — owner A-ruling class) /
  unverifiable 986 / task_loop_supported 243 / invariant_fold_suspect 5 /
  long periodic unrolls without rg coverage 99 rows. 885 rows (47.8%)
  affected. Report: `REP_GROUP_CONSISTENCY_AUDIT_DEV_V2.json`.
- **Repetition-semantics generation chain fully traced (2026-10-12)**:
  `blueprint_v2_preflight_v1.py` = mechanical RLE over adjacent identical
  semantic-chain tokens -> stage.repeat; rg = runs with count>1;
  iteration_hint = task-text keywords (shared per row, no per-stage
  evidence). No execution semantics, no interleaved-pattern detection, no
  loop-invariant handling anywhere. Mechanism verdicts: M1 counts are
  faithful (k=370 upstream chain sid=60463 literally ends with 38x
  VECTOR_LOAD) but invariant attribution belongs to upstream chain
  generation; M2 condition-count confusion originates at chain token
  granularity (1,411 stratified sample material ready:
  `COND_COUNT_ADJUDICATION_SAMPLE_V1.json`, 28 samples x 15 strata with
  chain context); M3 interleaved loops uncovered because the generator has
  no such detection (99 rows). Repeat structure: 19,379 x repeat=1 + 2,645 x
  repeat>1 (sum 8,625) = 28,004 expanded ops. Repair = representation-policy
  adjudication at the blueprint layer over an upstream strategy question,
  not field fixing.
- **Owner five-step directive**: (1) adjudication freeze done -> (2) B2-P1
  repair (keep source-authenticity and representation-completeness checks
  separate) -> (3) before/after diff report -> (4) trusted dev subset freeze
  + recompute BAND_SELECT P/R/F1 -> (5) only then discuss training. Not
  authorized: full retrain, P1 format overhaul, RL, auto-compressing
  unverified loops.
  **Ruling update (2026-10-13, OWNER_RULINGS_20261013_V1.md ruling C)**:
  steps (2) and (4) approved to run IN PARALLEL. This authorizes the
  audits/repairs only — no new training, no frozen-data modification, no
  formal generation against unverified gold.
- Boundary: closure does NOT mean the 90 suspected binding-error groups are
  all proven, nor that the trusted dev subset is frozen; suspicious items do
  not auto-upgrade.

## Prior State (2026-10-10, Route-2 GEE semantic planner pilot)

- **A1-A4 detector evaluation & calibration CLOSED (2026-10-10)**: six-script
  pilot -> 25-script validation (ledger SHA 05af094d) -> single-annotator
  exploratory labeling (2517 units) -> unsealed comparison -> A3 fix round
  (59.77%->92.02%, zero regression, v1.1 frozen) -> A2 review closed (146
  adjudications, protocol v1.0 frozen, annotation_results_v2 SHA d3fca732).
  Post-review metrics: A1 candidate-set 100%; A2 status 89.64% / count
  92.16% (70 status divergences in three named families F-A/F-B/F-C, no-fix
  per owner; conclusion report is the future fix spec); A3 strict 92.02%;
  A4 insufficient_sample. Single-annotator exploratory, not dual-blind.
  Authority: `expansion_validation_prep_v1/` (EXECUTION_LOG_V1,
  EVALUATION_PROTOCOL_V1_0_FROZEN, A2_REVIEW_CONCLUSION_V1, a3_v1_1_freeze/,
  a2_review/).
- **Frozen-dataset extraction-defect impact analysis DONE (2026-10-10)**:
  F-A/F-B zero pollution (production extractor has explicit presentation
  prefix classification; 20k-row scan: semantic vocab = exactly 30 classes,
  canonical chain Map./ui./print counts all 0); F-C is a design property, not
  a detector defect (unconsumed-variable share 10.2%, 0-37.5%). Rebuild
  decision framework: (a) no rebuild, run mainline experiments first
  [recommended]; (b) 25-script pilot re-extraction with v1.1-detector
  dead-branch filter; (c) full re-extraction. Report:
  `docs/reports/gee_frozen_data_impact_v1/`. **Awaiting owner ruling.**
- **Back to mainline**: GEE workflow supervision -> workflow-reasoning
  capability validation; QGIS operator grounding -> processes+links graph
  generation. Not authorized: resampling, full-corpus promotion, gold
  designation, training.

- Six-script reconstruction pilot COMPLETE (RECONSTRUCTION_PILOT_METHOD_V1 frozen):
  37/37 audit-unit recovery, 0 implementation-detail fixation, conflicts preserved
  both-sides, 269131 duplicate edges verified (40 raw records -> 38 logical).
- EXPANSION_DESIGN_V1 frozen per owner ruling 2026-10-09 (A1 candidate-only rule,
  A3 unknown-never-analysis + role coexistence, WP-B adds detector-independent
  random stratum, C1/C2 auditable denominators; 5% fixation and 90% agreement are
  candidate thresholds only).
- Work Package A implemented and back-tested on the six pilot scripts ONLY —
  A1-A4 all PASS (`wp_a_backtest_v1/WP_A_BACKTEST_REPORT_v1.md`; detectors
  `scripts/run_wp_a_detector_backtest_v1.py`, tests 13/13). Back-test surfaced
  three ground-truth corrections in the frozen pilot records (36595
  elevation/lulc actually declared in-source, soil/s2 assignment-globals,
  CHIRPS/DEM/modis missed prebindings; 269131 Fire_Sus uses AST-verified 11 not
  12; 302840 first statement truncated, 11 undeclared candidates) — recorded,
  frozen artifacts untouched. Owner ruling: source evidence wins over old
  records; detectors are never forced to match them.
- WP-B sampling design FROZEN (`EXPANSION_WP_B_SAMPLING_V1.md`; script
  `scripts/build_expansion_validation_sample_v1.py`, seed 20261009, design
  manifest SHA 7b0769c7..., tests 10/10) and WP-C metric denominators FROZEN
  (`EXPANSION_WP_C_METRICS_V1.md`). Pre-execution review package delivered:
  `PRE_EXECUTION_REVIEW_PACKAGE_V1.md`.
- **Small-scale validation UNSEALED AND COMPARED (2026-10-10)**: owner ruled
  single-annotator final round (no second annotator; dual-blind NOT claimed) ->
  seal opened 17:21:40 (conclusion SHA verified unchanged) -> full comparison
  (`expansion_metrics_v1.json`, 795-entry divergence ledger; report
  `EXPANSION_METRICS_REPORT_V1.md`). Results: A1 candidate-set 100% (45=45);
  A2 status 89.6% (divergences mainly 33 annotator cross-sample drift items);
  A3 59.8% (ALL 721 divergences mechanically attributed: 82% one fixable
  defect — nested call chain path=None — plus ui/console namespace fallback,
  A1-root cascade, and line-ruling granularity; zero genuine boundary errors);
  A4 insufficient_sample; C1 not computable (no duty adjudication); C3=0.
  **S3 reading**: A3 <80% but every divergence attributed — this report IS the
  review material; detector fix round awaits owner ruling. Annotator-1
  submission: 2517/2517 units (SHA 5dbb4308...).
- **A3 v1.1 FROZEN (2026-10-10)**: engineering acceptance passed; primary
  metric 92.02% strict (96.89%/100% are sensitivity analyses only); no third
  fix round; freeze at `a3_v1_1_freeze/` (detector v1.1, 1796 per-item
  predictions, test records, three-tier metrics, 143-residual list).
  Four-step plan: (1) freeze done; (2) A2 review IN PROGRESS — adjudication
  table generated (`a2_review/A2_ADJUDICATION_TABLE_V1.jsonl`, 146 divergent
  units: 54 status / 76 count / 16 both; 4 cause categories; decision column
  open, old labels untouched); (3) unified evaluation protocol drafted
  (`EVALUATION_PROTOCOL_DRAFT_V0.md`, 4 points pending owner); (4) independent
  verification deferred (needed only if detector performance becomes a paper
  claim). Stage verdicts: A1 provisional pass (no missing_definition positive
  examples; zero-miss not generalizable), A2 in review, A3 exploratory pass
  (line-level vs call-level reported separately), A4 insufficient_sample.
  Single-annotator exploratory, not dual-blind.

## Superseded: batch8/batch9 replay line (archived 2026-10-09; historical evidence below)

- Batch8 v8.8 band-alias rulefix was replayed from a controlled snapshot
  `code_snapshot_v8_8_band_alias_rulefix_authority`; the new rule resolves proven
  top-level literal-array aliases used by `select(bands)` and remains fail-closed for
  dynamic or rebound selectors. Server unit tests pass 33/33.
- Full DAG A/B replay is byte-identical for 17,585 selected sources (AST
  17,567 success / 18 failure; source statuses 5,090 passed, 520 partial, 11,957
  fail-closed). Fidelity A/B is byte-identical: 39,110 workflows, 11,342 passed,
  320 exact duplicates, 27,448 fail-closed, and 5,214 unique accepted sources.
- The rule closes the previously audited `data30000/script_22112.txt` defect:
  its `bandas = [B1..B7]` alias followed by `select('ndvi')` is now
  `static_band_lineage_select_mismatch` and cannot reach facts or proposals.
- Downstream typed/facts A/B are byte-identical: 7,124 mapping-complete workflows,
  6,801 fact bundles, 4,245 task candidates, and 323 fact fail-closed rows. The
  new expansion census has 3,469 source-disjoint proposals from 2,035 sources,
  26 length sidecars, and zero semantic sidecar rows.
- The fresh 50-row full-source audit is 50/50 pass, 0 fail/defer, 0 critical
  failures, and all source SHA checks verified. The evaluator decision is
  `passed_for_larger_source_disjoint_replay`; no new rule change is required.
- Hash-bound export admitted all 3,469 proposals with zero duplicates and zero new
  length defers. The current combined authority is **7,971 semantic train-only
  rows, 7,970 V4-100 rows, and one existing 155-step sidecar**. Training artifacts
  A/B are byte-identical.
- The real `TaskConditionedL3DatasetV4`, weighted-loss, and backward smoke covered
  7,970/7,970 rows in fifteen `[512,100]` batches and one `[290,100]` batch. Loss
  and gradients are finite, max token is 93, max model sequence length is 99, and no
  checkpoint or training epoch ran. Smoke A/B is byte-identical.
- The smoke CLI now defaults to the frozen taxonomy mapping authority. Remote
  `outputs_v2/id_mappings_v2.json` has a different SHA and correctly fail-closed;
  Batch8 verification used `configs/taxonomy/inputs/id_mappings_v2.json` at the
  required stable-94 SHA.
- Batch9 completed its frozen v8.8 AST/DAG A/B replay for 5,000 fresh,
  source-disjoint sources. A/B is byte-identical: AST 4,997 success / 3
  fail-closed parse failures; DAG source status 187 passed / 140 partial / 4,670
  fail-closed. `workflow_dags.jsonl`, `parse_failures.jsonl`, and `summary.json`
  are identical across the two runs. This produces no facts, task text, or training
  rows; detailed evidence is in
  `docs/reports/gee_batch9_v8_8_ast_replay_2026-08-07.md`.
- Batch9 completed frozen v8.8 fidelity A/B over the identical DAG input using the
  controlled code snapshot rather than the drifted live fidelity module. The 11,117
  workflow decisions are byte-identical: 644 passed candidates from 306 sources, 6
  exact duplicates, and 10,467 fail-closed; training rows remain zero. Evidence is
  in `docs/reports/gee_batch9_v8_8_fidelity_replay_2026-08-07.md`.
- Batch9 completed frozen v8.8 typed canonicalization/mapping A/B: 355
  mapping-complete workflows from 154 sources, 289 fail-closed, 126 canonical GEE
  operators, and 47 L3 codes. The typed business artifacts are byte-identical and
  emit zero training rows. Evidence is in
  `docs/reports/gee_batch9_v8_8_typed_mapping_replay_2026-08-07.md`.
- Batch9 completed frozen source/AST-backed facts A/B: 339 fact bundles, 16
  fail-closed rows, and 242 deterministic task-text candidates after 97 exact
  task-text/L3 duplicates were suppressed. A 50-row risk packet was produced;
  training rows remain zero. Evidence is in
  `docs/reports/gee_batch9_v8_8_facts_replay_2026-08-07.md`.
- Batch9 completed frozen expansion/proposal A/B over all 242 canonical task-text
  candidates. Every business artifact, including the hash ledger, is byte-identical:
  197 proposals from 114 eligible sources, 44 duplicate sidecars, one length defer,
  and no semantic or reviewed-source-overlap failures. The frozen 50-row stratified
  full-source audit packet is pending; training rows remain zero. Evidence is in
  `docs/reports/gee_batch9_v8_8_expansion_replay_2026-08-07.md`.
- The frozen Batch9 50-row full-source semantic audit failed closed: 43 pass, seven
  critical failures, precision 0.86, Wilson 95% lower bound 0.7381380628941446, and
  evaluator decision `failed_rule_repair_required`. Five failures establish one
  reusable control-flow loop-lineage defect; no proposal or training admission is
  granted. Evidence is in
  `docs/reports/gee_batch9_v8_8_expansion_audit_2026-08-07.md`.
- The v8.9 loop-lineage repair was replayed from Batch9 DAG through proposal under
  `code_snapshot_v8_9_3_loop_lineage_facts_ledger_determinism_authority`. Every A/B
  artifact is byte-identical: 326 mapping-complete workflows produce 315 facts and
  224 canonical task-text candidates; 183 proposals from 107 sources remain after
  41 duplicates. Facts ledger keys now use logical source/AST identities rather than
  physical A/B directories. A new 50-source stratified audit packet is frozen as
  `pending_sampling_audit`; training rows remain zero. Evidence is
  `docs/reports/gee_batch9_v8_9_3_replay_and_audit_freeze_2026-08-07.md`.
- The v8.9.5 literal catalog temporal-coverage gate was replayed from Batch9
  fidelity through proposal and export. It rejects only proven literal collection/date
  ranges with empty catalog coverage. A/B retained 180 proposals from 105 sources;
  the new 50-source full-source audit passed 50/50 with no critical failure and a
  Wilson lower bound of 0.9286524008666414. The hash-bound export admitted all 180
  rows. The Batch9 v8.9.5 combined authority was **8,151 semantic rows, 8,150 V4-100 rows,
  and one 155-step length sidecar**. Real V4 loader/loss/backward smoke passed
  8,150/8,150 rows in A and B with identical output, finite loss/gradients, and no
  checkpoint or training epoch. Evidence:
  `docs/reports/gee_batch9_v8_9_5_authority_training_2026-08-07.md`.

- The production mother pool remains 219,914 unique source contents. Batch7 replayed
  10,000 fresh source-disjoint sources; `/home/yll` remained read-only. AST replay
  succeeded for 9,993 sources.
- v8.6 adds fail-closed detection for native JavaScript operations over EE objects,
  treats `getInfo()` output as a client value, and limits declarator type ownership to
  each initializer. Against v8.5, exactly four previously passed workflows moved to
  fail-closed and no admitted workflow changed.
- The v8.6 authority contains 3,029 DAG-passed and 311 partial sources. Downstream A/B
  replay yields 3,809 mapping-complete workflows, 3,605 fact bundles, 2,490 canonical
  task candidates, and **2,235 source-disjoint proposals from 1,321 eligible sources**.
  Seven over-length candidates remain outside this proposal population.
- The 50-row audit migration carries 49 unchanged full-source PASS identities. The
  removed v8.5 identity is the confirmed native-operator critical failure; the one
  replacement identity was explicitly reviewed against full source and passed. The
  final v8.6 audit is 50/50 pass: point precision 1.0, Wilson 95% lower
  0.9286524008666414, and zero critical failures.
- Batch-level admission adds all 2,235 same-rule proposals with zero export duplicate
  and zero new length defer. The combined train-only package now contains **4,502
  complete semantic rows, 4,501 V4-100 rows, and one existing 155-step length
  sidecar**.
- Real `TaskConditionedL3DatasetV4`, weighted-loss, and backward smoke covered
  4,501/4,501 rows in eight `[512,100]` batches and one `[405,100]` batch. Loss and
  gradients are finite, max token is 93, max model sequence length is 99, and no
  checkpoint or training epoch ran. Training and smoke A/B outputs are byte-identical.

Current authority:

- Server root:
  `/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806`
- Train packages: `training_v8_8_band_alias_authority_a` and
  `training_v8_8_band_alias_authority_b` are retained provenance; current additive
  authority is `training_v8_9_5_catalog_temporal_filter_authority_a` and `_b`
- Smoke: `loader_loss_smoke_v8_9_5.json` in each current A/B train-package directory
- Formal report:
  `docs/reports/gee_batch9_v8_9_5_authority_training_2026-08-07.md`
- Data-content and real-row walkthrough:
  `docs/reports/gee_training_data_contents_and_example_2026-08-05.md`

The walkthrough verified one current Batch7 row against `/home/yll/GEE/Data` and
the latest combined authority. It also identifies a model-interface risk that the
chain/source audits did not measure: current task names expose the step count and
current descriptions enumerate the ordered GEE operators. The 4,502 semantic rows
remain valid source/DAG/operator/L3 authorities, but their current text view is an
operator-explicit GEE-to-L3 translation input, not yet a leakage-controlled
natural-language planning input.

## Active Gate

Batch10 is the active fresh source-disjoint expansion, not part of the current
8,150-row authority. Its v8.9.5 replay produced 37 pending proposals from 30
eligible sources. Full-source review proved one reusable defect: an
`Image.expression()` output without `rename()` was later selected as `HV` even
though its static default band is `constant`. Snapshot v8.9.6 repairs that
fail-closed rule; local pytest and remote unittest each pass 64 focused tests.
The full Batch10 fidelity, typed-mapping, facts, and proposal A/B replays are
byte-identical under v8.9.6: 143 fidelity candidates, 57 mapping-complete
workflows, 55 fact bundles, 48 canonical task-text candidates, and 36 pending
proposals from 29 eligible sources. The frozen `exhaustive_29` audit is now
complete: 28 pass and one isolated fail-closed row
(`data300000/script_304794.txt`). Its loop-derived imagery dependency is absent
from dataset facts and task text. A deterministic census finds no second case
(one missing ImageCollection fact among 37 ImageCollection-chain fact bundles),
so no rule changed or replay is justified. The hash-bound evaluator returns
`failed_rule_repair_required` because its Wilson lower bound is `0.8282448`,
below `0.85`; Batch10 stays entirely unadmitted and excluded from 8,150. See
`docs/reports/gee_batch10_v8_9_6_full_audit_2026-08-08.md`.

The cumulative 8,000-row semantic gate is complete. Batch9 v8.9.5 is the current
GEE train-only authority. Its 5,000 hard-structure sources (4,000 helper exports and
1,000 control-flow exports) have zero overlap with the 36,663-source prior exclusion
union. The old v8.8 audit failed closed, the loop-lineage repair was replayed, and
the literal catalog temporal-coverage gate then removed the two proven date defects.
The replacement 50-source audit passed and the 180 same-rule proposals are now
admitted train-only. The next gate is a fresh source-disjoint selection under frozen
v8.9.5, not further review of already admitted rows.

An attempted 20,000-source selection correctly failed exact quotas because the
remaining strict population cannot provide 15,000 linear-export sources. This is a
capacity result, not a rule relaxation. Do not change a rule unless later sampling
identifies a systematic reusable defect.

Each subsequent batch still requires deterministic full-population A/B replay and a
stratified full-source audit. The next GEE action is a new source-disjoint population
selection under frozen v8.9.6, sized to yield at least 50 eligible sources for a
statistically adequate audit. Only a systematic audited failure may change one
reusable extraction rule and trigger one whole-batch replay.

Batch11 freezes that next population under v8.9.6: 5,000 sources
(`helper_export=2,500`, `control_flow_export=2,500`) after excluding 43,663 prior
or touched source hashes. The valid AST/DAG A/B replay uses
`/home/yll/.local/node-20/bin/node` and
`NODE_PATH=/home/qy/system_redesign/.runtime/gee-ast-parser/node_modules`; it is
byte-identical: AST `4,995` success / `5` parse failures, DAG source statuses
`143` passed / `98` partial / `4,754` fail-closed, and `9,069` workflow DAGs.
Fidelity A/B is also byte-identical: `388` passed candidates from `217` sources,
`14` exact duplicates, and `8,667` fail-closed decisions.

The frozen v8.9.6 typed canonicalization/mapping A/B replay processed all 388
fidelity-passed candidates. It is byte-identical, including its hash ledger: `206`
mapping-complete workflows from `125` unique sources, `182` fail-closed workflows,
`107` canonical GEE operators, and `42` L3 codes. These remain non-admitted; no
facts, proposal, or train-only row exists yet. The source/AST-backed facts A/B then
produced `200` fact bundles, `6` fact fail-closed rows, and `135` deduplicated
task-text candidates from `101` sources (`65` duplicate sidecars). Frozen expansion
replay retained `95` pending proposals from `78` eligible sources, excluded `39`
existing/batch duplicates, and placed `1` over-length row in a sidecar. Expansion
A/B artifacts and hash ledgers are byte-identical. The next gate is the frozen
50-source full-source audit; no proposal is train-only admitted until its decision.

That Batch11 v8.9.6 audit is complete: all 50 source SHA256 values match, but only
47 pass. Three critical failures prove two reusable defects: the catalog coverage
table omitted `COPERNICUS/S2_SR_HARMONIZED` and the skip authority removed output-
relevant `ee.imagecollection.sort` before `first()` or `mosaic()`. The hash-bound
evaluator returns `failed_rule_repair_required` (precision `0.94`, Wilson lower
`0.8378290831`, three critical failures), so the 95 proposals are unadmitted.

The minimal v8.9.7 repair adds the public S2 SR Harmonized coverage lower bound and
removes only `ee.imagecollection.sort` from the versioned skip authority; stable-94
already maps it to `L3_03_09_07`. Its full-source audit still found one critical
catalog-coverage defect: `COPERNICUS/S2_HARMONIZED` was requested wholly before its
2017-03-28 availability after an `ee.Image(...)` wrapper hid the collection lineage.
The v8.9.7 93-proposal population remains unadmitted.

The v8.9.9 repair adds that S2 Harmonized lower bound and transparently preserves
proven lineage through one-argument `ee.Image(value)`. Full A/B replay is
byte-identical: 386 fidelity-passed, 204 mapping-complete, 92 proposals from 75
eligible sources (40 duplicates, one length sidecar). The new frozen 50-source audit
verified every source SHA256 and passed 50/50 rows with zero critical failures
(precision `1.0`, Wilson lower `0.9286524008666414`).

Hash-bound export A/B is byte-identical: it admitted 92 new rows with zero duplicates
and zero new length defers. The current combined authority is **8,243 semantic
train-only rows, 8,242 V4-100 rows, and one existing 155-step sidecar**. Real V4
loader/loss/backward smoke covered 8,242/8,242 rows in A and B (17 batches, final
`[50,100]`), with finite losses and gradients, maximum token 93, maximum model
sequence length 99, no checkpoint, and no training run. Batch11 is granted train-only
admission; validation/test and production merge remain closed.

Batch12 now freezes that next v8.9.9 source-disjoint population: 5,000 sources
(`helper_export=2,500`, `control_flow_export=2,500`) have zero SHA256 overlap with
the cumulative 48,663-source exclusion authority. Selection A/B and hash ledgers are
byte-identical. It is selection-only, emits zero training rows, and its immediate gate
is frozen v8.9.9 AST/DAG A/B replay.

Task-interface conversion is deliberately deferred until the target data population
has been processed. The frozen semantic authority remains the shared source for two
later views: `operator_explicit` for GEE-to-L3 alignment/ablation and `goal_only` for
leakage-controlled natural-language planning. Generate and audit both views together
at the final training-interface stage; do not let that stage block source/DAG/L3/fact
recovery now, and do not discard the recorded leakage risk.

The 57 legacy/unverified public dataset IDs remain a separate rule-authority queue.
Fuzzy matching, embeddings, or automatic dataset-ID replacement cannot grant
admission and must not block the already admitted package.

## Batch12 Snapshot Replay And Audit

The first Batch12 replay used the drifted live DAG gate (SHA `472607...`) rather than
the frozen v8.9.9 gate (SHA `4cb297...`), which omitted the existing control-flow
lineage predicates. Replaying 13 known critical sources with the snapshot made all
13 fail-closed, proving a runtime-authority defect rather than a permissive rule gap.

The full snapshot-authority A/B replay is byte-identical: AST 4,994 success / 6 parse
failures; DAG source statuses `passed=135`, `partial=105`, `fail_closed=4,754`;
fidelity 467 accepted workflows from 218 sources; typed mapping 219 workflows from
112 sources; facts 218 bundles and 162 task-text candidates from 97 sources; and
70 proposals from 41 eligible sources. Proposal hash ledgers are identical
(`772218...`), and no training rows have been emitted.

The post-replay exhaustive 41-source full-source audit (all available sources after
the repaired fail-closed gate; 50 were impossible without reusing rejected sources)
is 41/41 pass with zero critical failures, precision `1.0`, Wilson 95% lower
`0.9143324298155681`, and evaluator decision
`passed_for_larger_source_disjoint_replay`. Batch12 remains unadmitted until the
next hash-bound export and real V4 loader/loss/backward smoke. Evidence:
`docs/reports/gee_batch12_v8_9_9_snapshot_authority_replay_audit_2026-08-10.md`.

### Batch12 export and loader/loss smoke (2026-08-11)

The 41 audited independent sources passed the hash-bound exporter: 41 semantic
complete-workflow rows, 41 V4-100 rows, zero duplicates, zero fail-closed rows,
and zero length sidecars (maximum model sequence length 20). The package is at
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/export_snapshot_authority_41/`;
all authority and artifact hashes are recorded in `hash_ledger.json`.

The real `TaskConditionedL3DatasetV4`, weighted sequence cross-entropy, and
backward smoke loaded all 41 rows in two batches (`[32,100]`, `[9,100]`) with
finite loss and gradients; no checkpoint or training run occurred. The server's
default Python has no torch, so the smoke used the local PyTorch 2.7.1 CPU
environment against the copied hash-bound package. This is an environment gap,
not a data failure; it must be rerun on the training host before training.
The package is now eligible for an incremental train-only authority manifest;
validation/test, production merge, and training remain closed. See
`docs/reports/gee_batch12_v8_9_9_snapshot_export_smoke_2026-08-11.md`.

## Batch13 Replacement Selection And DAG Replay (2026-08-16)

The prior `gee_batch13_5000_v8_9_9_20260811` directory is **not a new batch**:
its selection (`2bdadd...`), 41-source audit packet (`983537...`), and proposal
ledger (`772218...`) are byte-identical to Batch12. It is retained only as a
diagnostic artifact and must never be exported or counted again.

A replacement population was frozen at
`/home/qy/system_redesign/diagnostics/gee_batch13_replacement_5000_v8_9_9_20260816`.
It extends the exclusion authority to 53,663 selector-compatible sources and freezes
5,000 new sources (2,500 helper / 2,500 control-flow). Its selection SHA is
`61f737...`; overlap with Batch12, the invalid Batch13, and the exclusion authority
is zero. The frozen v8.9.9 AST/DAG A/B replay is byte-identical: AST success=4,993,
parse failure=7, source status passed=120 / partial=124 / fail-closed=4,749. No facts,
proposal, or training row has been emitted.

Replacement fidelity A/B is byte-identical: 9,410 workflow decisions from 4,993
parsed sources produced 454 passed candidates (228 unique sources), 17 exact
duplicates, and 8,939 fail-closed. No mapping, task text, proposal, export, or
training row has been emitted. Immediate next gate: typed canonicalization/mapping
A/B on the 454 passed candidates only.

Replacement typed canonicalization/mapping A/B is complete and byte-identical:
266 of 454 fidelity candidates are mapping-complete (121 unique sources), while
188 remain fail-closed. The result covers 108 canonical operators and 47 L3 codes.
The fail-closed set includes 43 canonical-L3 gaps, 22 override-taxonomy gaps,
13 override-signature mismatches, 96 support-classified retained calls, and 14
unmapped raw calls. No facts, task text, proposal, export, or training row has been
emitted; the next gate is facts/task-text generation for the 266 complete candidates.

## Batch13 Replacement Facts and Task Text (2026-09-02)

Using the frozen v8.9.9 snapshot and the correct read-only source root
`/home/yll/GEE/Data/data20000_AST_failed`, deterministic facts/task-text generation
processed all 266 mapping-complete candidates. It produced 259 source/AST-backed fact
bundles, 177 deduplicated task-text candidates (82 duplicate sidecars), and 7
fail-closed rows. The 50-row mechanical risk review passed 50/50 after correcting
the checker to recognize `Export.image.toAsset` and `Export.table.toDrive`; the
correction is covered by regression tests. Final deterministic deduplication found
177 unique candidate keys with zero candidate/sidecar overlap. The same 50-row
review on snapshot B is byte-identical to A (SHA256
`fbfb969a345a920c8e02734bd6f5fbfdbe52aae9c6a4a74f9064c577427e98c8`). A/B outputs
and hash ledgers are byte-identical. No proposal, export, or training row is admitted; the
next gate is proposal generation only after this reviewed package is explicitly
advanced.

## Batch13 Replacement Proposal Census (2026-09-02)

The reviewed 177 candidates were passed through the frozen expansion census. It
retained 76 proposal-eligible rows; 26 rows overlapped the reviewed source set and
25 duplicated existing semantic authority. No semantic failures or length defers
occurred. Snapshot A/B proposal artifacts and hash ledgers are byte-identical.
The 76 rows remain `pending_sampling_audit`; no export or training admission is
granted.

## Hard Boundaries

- `/home/yll` is read-only; large artifacts stay under `/home/qy`.
- Do not modify `outputs/`, `outputs_v2/`, or `train11397_*`.
- Do not train and do not let an LLM guess, add, remove, or reorder chains.
- Validation/test admission and production merge remain closed.
- Use the frozen stable-94 mapping at
  `configs/taxonomy/inputs/id_mappings_v2_94_frozen.json`, SHA256
  `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.
