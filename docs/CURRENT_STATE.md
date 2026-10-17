# Current Project State

Last updated: 2026-10-15

## (00) QGIS specialized-training route FROZEN as project direction (2026-10-15, owner ruling)

- Owner ratified the QGIS specialized-training route: A operator knowledge
  base (full ~1,200-operator catalog -> normalized schema -> provenance ->
  hybrid RAG -> basic relational/structural checks; full GraphRAG NOT a
  prerequisite) -> B training-data construction (GEE planning supervision +
  QGIS operator semantics + workflow composition + high-quality DAG
  supervision; runs in PARALLEL with A) -> C two-stage SFT (Stage 1 general
  GIS planning / Stage 2 QGIS grounding + params + DAG; keep planning
  supervision against forgetting) -> D full inference chain (planning ->
  evidence ledger -> operator retrieval -> processes+links DAG -> structural
  +semantic checks -> bounded repair) -> E first-version delivery + targeted
  optimization.
- Three owner corrections: (1) ONE continuous recipe on Qwen3.5-9B mixing
  all supervision by role — NOT a separate GEE-planner training followed by
  a fresh QGIS training; (2) complex-task completeness by division of labor
  (model proposes / external evidence ledger tracks / structural validator
  checks / independent semantic review + human sampling; structural legality
  != semantic correctness); (3) knowledge organization and data construction
  proceed in parallel so knowledge engineering cannot become a long project.
- Standing principles: final workflow quality = the only primary goal; the
  operator catalog = authority knowledge source (model params not the sole
  carrier); planning steps are NOT an operator abstraction layer (no unified
  taxonomy; output = real QGIS operators, processes+links); full system
  first, then targeted optimization; self-evaluation never substitutes for
  external validation. GRPO and full GraphRAG deferred until first-version
  bottlenecks are measured. First-version acceptance = 6-item checklist
  (operator knowledge / grounding / plan completeness / DAG correctness /
  repair / evaluation credibility).
- Evaluation discipline unchanged: dev-120 selects, test-111 judges once;
  route2_C0 dev opF1 0.5611 = baseline under the unified protocol;
  system-level vs model-level gains recorded separately from day one.
- Inventory DONE (2026-10-15, four parallel read-only audits): spec V1 skeleton at
  `docs/plans/QGIS_SPECIALIZED_TRAINING_IMPLEMENTATION_SPEC_V1.md`. Headlines: catalog =
  1,291 operators, three consistent sources (qgis_catalog / capability profile v0_4 /
  operators-json); **309 = gold-exercised subset of the 1,565 grounded rows** (148 =
  test111, 38 = benchmark v0.1-120); profile v0_4 covers ALL 1,291 incl. parameter
  schema with defaults for 1,127 (registry dumps) = knowledge-base backbone; 4 validators
  reusable as-is (benchmark structural gate incl. cycle detection / io_factor edge
  compatibility / rl_reward r-battery / r5 coverage); top data gaps = zero parameter
  supervision + grounded volume (1,565 rows; D5 render pipeline = expansion path);
  `stage1_train_v2_2A` missing locally with a row-count discrepancy (ledger 35,246 vs
  docs 23,030) — frozen as do-not-cite; blueprint_v2_gold_v3 local mirror FOUND
  (04_DIAG_WORK, SHA-verified — supersedes the old no-mirror record).
- **Quick-look EXECUTED and CLOSED (same day, owner directive)**: 108 held-out GEE tasks x
  P0/Base, 216 generations; 31 samples hand-judged (22 L1 + 9 stratified): P0 CM 31/31=Y
  cross-band, Base 3/31. Fault localization (raw Blueprint = 2-5 generic stages, 88-137
  tokens; conversion exonerated by construction) + same-interface probe (P0 + NL prompt +
  rep-pen -> 8/8 immediate-EOS) closed the attribution: interface fragility + content
  poverty + schema ceiling; "SFT destroyed ability" REFUTED (Base advantage = pretrained
  prior never in the training target).
- **FINAL RULING (owner, 2026-10-15)**: (1) P0 fmt removed from Stage-1 candidates — no
  patching, no catch-up training; (2) new training starts from Qwen3.5-9B-Base; (3)
  Blueprint v2 demoted — data retained as auxiliary supervision only, NOT the output
  target; (4) unified training with output space = complete QGIS workflow (processes+links
  incl. operators/params/IO/DAG). Three binding principles: freeze the workflow contract
  BEFORE expanding data; new training compared against Base on the SAME test set / prompt
  / evaluator (format correctness != workflow quality); unified != indiscriminate mixing
  (GEE = auxiliary general-planning supervision only, cross-platform label mismatch
  forbidden; supervision sources may differ, generation interface and acceptance target
  unique). Execution order: D1 Unified Workflow Contract -> D2 render pipeline -> D3
  recipe -> D4 eval gates -> GPU only after CPU review (no recipe approved, no training
  launch now). RL line indefinitely suspended (its prereg output space was Blueprint/P0).
  Archive: `pca2_v1/QUICKLOOK_FINDINGS_V1.md`. **DIAG-50 CLOSED (2026-10-15)**:
  50 tasks stratified from the 100 (12/18/12/8, seed 20261013); A arm 50/50 ready
  (reused quicklook Base NL rows); B arm (Base + operator cards -> processes+links
  JSON) failed pre-batch smoke 5/5 rounds — two instrument bugs fixed along the way
  (TRUNC 1024 cutting the trailing instruction block; greedy instead of the frozen
  rep-pen 1.15 instrument), the rest content-level (unclosed think / literal loops /
  card-cycling enumeration / schema echo), parsed_ok 0/4 under every instrument combo.
  **Owner ruling: "bare Base zero-shot JSON-graph contract unusable" accepted as the
  formal diagnostic conclusion** (signature archive parsed_ok 0/20; same tasks pass on
  A-arm NL steps -> Base capability is format-conditional; SFT-priority evidence points
  to format + grounding supervision). Artifacts: `diag50_v1/DIAG50_SMOKE_ROUNDS_V1.md`,
  `DIAG50_BARM_FAILURE_SIGNATURES_V1.json`, `DIAG50_WORKBOOK_A_V1.md`. That review path
  evolved into the **DX five-stage diagnostic line (`dx_v1`, owner-reviewed)**: frozen
  instrument (S0 plan → S1 frozen MiniLM top-10 → S2 per-step selection with full
  operator cards → S3 composition → S4 static validation) + commit-marker recorder
  (raw+gen+commit, no-replace publish; 15/15 tests, 8/8 ext4 probe on mdzhang).
  **DX smoke6 (6 tasks, 2026-10-16) COMPLETE: 45/45 records COMMITTED**; headline:
  first capability wall = **S2 selection** (7 positive / 16 explicit rejections /
  10 no-decision incl. 9 generation-side empty raws — storage corruption excluded by
  recorder evidence); S0 parses 6/6; S3 starved by S2 (composition unjudgeable);
  GAP_COMPLETE≠success and S4-zero≠good demonstrated (T-086, T-062). Reports:
  `diag50_v1/dx_v1/dx50_v1/smoke6_v1/DX50_SMOKE_FINDINGS_SMOKE6_V1.md` +
  `DX50_SMOKE_REVIEW_SMOKE6_V1.md`. **Owner-audit erratum (same day, resolved)**: the
  sheet's UNCOMMITTED flags were real but local-only — the old-pipeline `save_record`
  rewrote published raws LF→CRLF during parsing (36 records); server originals 45/45
  COMMITTED (re-audited with the same recorder), zero content loss (CR-strip sha ==
  marker for all 45, quarantined + manifested), mirror restored from server originals,
  parse tooling fixed parse-only with a regression test (16/16), sheet regenerated
  (45-record integrity now heads the mechanical summary). Findings doc is V1.1 with
  the erratum section. **FULL DX-50 BATCH COMPLETE (owner-authorized 2026-10-16, tag dx50_full_v1):
  392/392 records COMMITTED** (S0 50/16.9min, S2 293/137.9min, S3 49/39.4min; raw
  VERIFIED 316 / EMPTY 76; 3 ledgers complete=True; T-050 explicitly excluded).
  Headline at n=50: S2 selection is the confirmed first wall — positive selection
  48/293=16.4%, rejection 74.2% of parseable, no-decision 37.9% (72% of those =
  2048 cap truncation); S3 termination control collapses (83.7% CAP_TRUNC); 1 out-of-candidate
  selection. Reports: `dx50_v1/dx50_full_v1/DX50_BATCH50_FINDINGS_V1.md` +
  `DX50_BATCH_REVIEW_DX50_FULL_V1.md`. **Owner review closed (2026-10-17): S0
  50/50 final-confirmed; S2 63-row abstention sample fully adjudicated —
  over-rejection (clear) = 0; leading root cause = impoverished operator cards,
  then retrieval misses.** Rulings frozen: methodology
  (`dx_v1/DX_RESEARCH_ROUTE_RULING_OWNER_V1.md` — proven-vs-unverified split,
  A-track 4-criteria acceptance, parser v2, order ①card base → ②instrument →
  ③S2 baseline rebuild → ④training decisions) and experiment design
  (`dx_v1/DX_EXPERIMENT_DESIGN_RULING_OWNER_V1.md` — **A1 card completion /
  A2 retrieval-corpus upgrade / B planning control, single-variable separated,
  combined arm only after A1 and A2; three states recorded separately:
  in-library / recalled-into-Top-10 / card-proves-applicable**). Corrected
  baselines under parser v2: no-decision 130 (44.4%), explicit abstention 119,
  positive selection 48 (16.4%). **EXECUTION QUEUE: A-track P0 card completion
  BUILT (2026-10-17): profile v0_5 created as a NEW file (SHA dfc03628…;
  builder `dx_a_track_build_v05_v1.py` + per-field provenance manifest) — 109/
  109 OTB cards filled from upstream 8.1.2 via macro extractor v2 (1,011
  params + 134 outputs + 116 choice-tree params; 19 input_types_norm fixes;
  base-class headers + CompositeApplication + ShareParameter resolution;
  framework auto-params ram/elev/rand excluded, not guessed); top-level
  description keys 0/1291 (S1 guard), non-OTB entries byte-equal to v0_4
  (SHA 95ae97bc… unchanged), 6 operators marked `provenance_unverified`
  (owner ruling: source & target-env availability unverified — follow-up task
  registered, not treated as confirmed ghosts). full_card() spot-check PASS:
  trainimagesclassifier card now shows classifier(Choice)+io.out — the T-009
  card blindness is lifted. NEXT in queue: A1 pack (v0_5 cards x frozen
  Top-10) → server S2 rerun → four-metric comparison; then A2 controlled
  retrieval comparison (no silent retrieval change) → B independent. Instrument finding: S1 retrieval is operator-ID
  lexical similarity (0/1291 profiles have a description key; layer_c_intent
  unread) — S1 fix is a separate controlled change; card completion must NOT
  write the top-level `description` key.** B-track (GEE planning): owner
  hypothesis ruling + joint audit **Q1-Q4 ALL COMPLETE** (`diag50_v1/
  B_TRACK_GEE_PLANNING_RULING_OWNER_V1.md`, `B_TRACK_Q2Q4_RULING_OWNER_V1.md`,
  `B_TRACK_GEE_POOL_JOINT_AUDIT_V1.md` [V1.1], artifacts `b_track_audit_v1/`):
  full-chain duplication NOT severe but local concentration high (Q1);
  task-condition→structure coupling exists and is monotone, Q2 40-pair human
  adjudication COMPLETE (see below); exact-duplicate multi-template
  negligible, differences are local variants (Q3); planner exact-rate rises
  monotonically with training-pool support (absent 14.1% / singleton 0% /
  low 0% / mid 12.3% / high 25.6%) and predictions skew +19% toward high-freq
  templates — low-support errors = data support gap, high-freq skew =
  training-introduced (clean attribution needs the Base-vs-trained B arm);
  813 AGGREGATION templates mix temporal-composite vs zonal contexts =
  label-flattening evidence anchoring direction ②. Per owner ruling the
  no-intervention gate has now cleared — Q2 human adjudication is done; the
  next step is the V2-P0 source-program walkthrough (below) → reviewed
  reference-sample construction → small-scale controlled training comparison.
  **Q2 40-pair human adjudication REGISTERED (2026-10-17, owner four-batch
  review → `b_track_audit_v1/Q2_OWNER_ADJUDICATION_V1.md/.json`)**: SAME group
  C-class (confirmed structure-mislabel) = **0**, A-class (same-structure well
  justified) 8/20, B-class (needs source verification) 12/20 with SAME-15
  (classification-vs-regression flattening) and SAME-19 (multi-granularity
  temporal aggregation under one label) as priority checks; DIFF group:
  suspicious 12/20, likely-reasonable 2 (DIFF-3/18), weak variant 1; the
  owner's three-field schema (requires-structure-change / label-
  expressiveness / chain-diff-evidence) frozen as the B-track review standard.
  **Mechanical correction: DIFF-20's two chains are NOT identical — they
  differ by exactly one repeated seasonal quad (7 vs 6, invisible in the MD
  rendering); the sampling grouping (template-set equality) is mechanically
  valid, the pair is registered as a weak variant, and the "grouping quality
  check" item is CLOSED (no bug).** Packet pre-observation: all 4 V3 SAME
  pairs (15/19/11/9) share byte-identical canonical API sequences across
  sides (same code, two descriptions; literal-level differences require
  reading the scripts), while all 14 DIFF pairs differ canonically (the
  programs genuinely differ). **Next: V3 label-expressiveness verification COMPLETE 4/4 at source level
(2026-10-17, `b_track_audit_v1/Q2_V3_WALKTHROUGH_FINDINGS_V1.md`): same-
structure held in all 4; SAME-15 instruction A mis-describes the target
variable (three in-code self-proofs say biomass — a description-fidelity
defect, NOT a structure/label-granularity issue); time range / index naming /
loop parameters all live in the literal layer = direct evidence for the
two-layer representation split; instrument lesson: canonical-identical does
NOT imply literal-identical. V2-P0 six-pair source walkthrough (DIFF-6→4→5→
1→12→19) is now UNBLOCKED — the raw GEE script corpus was located locally
(`.tmp_gee_batch13_sources/Data/dataNNNNN/script_XXXXX.txt`, 36/36 packet
scripts covered, path map `Q2_PACKET_SCRIPT_PATHS_V1.json`; the batch8 tree
is a subset, unused); three-way alignment packet =
`Q2_PRIORITY_VERIFICATION_PACKET_V1.md/.json` (run-count RLE rendering +
automatic chain diff + script pointers + 18-pair summary table; sha1-compare
both sides first to exclude same-code variants). Then: size the
"extraction/annotation-difference" share → reviewed reference-sample
construction → small-scale controlled training comparison. Discipline:
verify source programs first — no loss changes or resampling from sample
judgments (owner wording); diagnostic tasks stay out of the B-track training
set; interventions still require owner release.**
  D1 contract ADR sign-off still pending. Live plan: task_plan.md.

## (0a) Planning Capability Audit (PCA): protocol v1 FROZEN, Phase 1 underway (2026-10-13)

- **Owner ruling after E2E A+B double-branch trigger**: freeze the models and
  run an independent planning-capability audit first — **no retraining, no
  21-family changes, no Stage 2**. Purpose is to establish what the evidence
  can support, not to prove Stage 1 right or wrong.
- **Design**: 60 tasks (A GEE held-out / B QGIS operator-free / C complex,
  x20) x 3 arms (base / stage1 / stage1+tool) + B′ standing diagnostic
  (6 tasks; mechanical expansion if B-arm content_assessable_rate < 0.70).
  Format health (format_valid/content_assessable/hit_cap/termination_status)
  reported separately from plan quality; transfer readout = paired-task delta
  + task_type stratification + in/out-domain decomposition (raw A-vs-B/C mean
  gap is NOT a transfer effect); C-arm conclusions limited to "tool
  information effect on plan quality"; human-review stats preregistered
  (quadratic weighted κ, seed 20261013).
- **Authority**: `plan_pipeline_v1/planning_capability_audit_v1/
  PCA_PROTOCOL_V1_FROZEN.md` (owner 5 revisions + 7 OQ rulings; v0 retained
  as history) + `PCA_PHASE1_WORKNOTES_v1.md`. Commit d3623e6c.
- **State**: B-group screening DONE (20 primary + 10 reserve; frozen rules,
  seed 20261013, zero reference to any prediction file). A-group isolation
  can reach `source_record_verified` (b1_gee_stage source_row_id + the
  actually-consumed planner_v2_train text pool on mdzhang; note
  blueprint_v2_gold_v3 has NO local mirror and the F-drive migration package
  is absent — fallback = text_dedup_only disclosure per §2.3). Next: B gold
  back-projection -> A construction -> C drafting -> pairing -> dedup
  ledger -> owner per-task review. **No formal 180-generation until the
  owner approves the gold.**

## (0b) RL line opened (Route-2 Stage-3 slot): four-phase route adopted, prereg v0 DRAFT (2026-10-13)

- **Owner rulings (this session)**: adopt the four-phase RL route (Phase 1 GRPO engineering
  smoke -> Phase 2 RAFT/DPO baselines -> Phase 3 affinity sampling + gated GRPO -> Phase 4
  process-reward / estimation-enhancement ablation); output space pinned to **Blueprint v2
  (P0 planner)** — QGIS-graph RL stays in the frozen Stage-2 slot; Phase-1 venue = mdzhang
  shared (co-tenancy protocol). This amends the 2026-10-12 "RL not authorized" standing
  order to "authorized under the preregistration protocol below".
- **Authority**: `plan_pipeline_v1/rl_line/RL_LINE_PREREGISTRATION_V1_CANDIDATE.md` (V1
  CANDIDATE; v0 DRAFT retained as history). Review-round OQ rulings ALL landed: OQ-1
  approved (24 tasks x 8 rollouts, seed 20261013); OQ-2 conditional (equal-weight synthesis
  only after the positive/negative pytest battery + S2 failure-co-occurrence check — fix
  definitions, not weights); OQ-3 beta=0.04 initial value only; OQ-4 S4 hard cap <=48
  task-group updates + six pre-registered stop conditions (KL abort separate from beta:
  per-token KL >1.0 nat x5 consecutive or >10 nat single-step); OQ-5 Phase 2 released only
  after the S2 throughput-extrapolation report + separate owner approval. r4 is now a
  schema-grounded executable definition (non-empty / seq continuity / rg<->stages
  bidirectional consistency / hint-label legality, per_feature = illegal) with the
  P1/N1-N7/B1-B3 battery as pytest — all green before the reward implementation freezes;
  absolute repeat magnitude logged, never scored (Contract E4 caliber). S2 acceptance split:
  engineering acceptance + signal diagnosis (effective groups <8/24 -> "limited signal
  coverage", NOT interpretable as scale-up readiness). Schema authority =
  `planner_design/PLANNER_V2_CONTRACT_FREEZE_v1.md`. Standing pins: reward v0 gold-free
  four-component with unverifiable dimensions masked; rollout decode rep-pen 1.15 (frozen
  eval instrument unchanged); RL training tasks ⊂ planner_v2_train only; E0 reuses existing
  P0 dev-1852 predictions; S1 is read-only (SHA / co-tenancy / vocab materialization /
  battery run), stop on any resource conflict. PCA/multisolution line = external input;
  only Phase 3 depends on it.
- **Local implementation delivered (2026-10-13)**: `scripts/rl_reward_v1.py` +
  `tests/test_rl_reward_v1.py` — battery 22/22 green (pytest 7/7). Real-data verification
  found TWO coexisting rg dialects in the local corpus: contract dialect
  (stage_seq/family/repeat/iteration_hint; 755 rows with non-empty rg) scores **755/755 =
  1.0**; anchor dialect (anchor_seq/pattern/repeat_count/order_preserved; 1,078 rows = P1/P2
  experiment lineage, window folds) is OUT of the P0 output space and unsupported by design.
  P0=contract-dialect is an inference (planner_v2_train built post-freeze; E3 consumes
  iteration_hint) -> **S1 now includes a dialect-fingerprint check** (planner_v2_train
  targets + one p0_dev_full_preds sample). total_iterations/stage_count appear in 0/2,985
  local targets -> presence logged, never required. 5+5 non-maximal-run rows are anchor-
  lineage only (out of RL scope, logged). Authority: `rl_line/REWARD_BATTERY_REPORT_V1.json`
  (deviations D1-D4 flagged for owner; empty-stages scores 5/6 under C0 — deferred to S2).
  **Owner round-2 rulings applied (2026-10-13), implementation revised to v1.1** (module SHA
  `5d5b6789f938980a…`): D1 reverted to V1 scoped masking (entry defects mask only affected
  components; cascade reserved for r1a/r1b; uniform rule determinable-fail > masked >
  pass); D2 accepted (no repair); D3 upgraded (missing rg key -> r4 MASKED, never silently
  passed); D4 not accepted unconditionally — contract has NO explicit minItems:1, hole
  quantified by a dedicated test (empty=0.833 / minimal-legal=1.0 / parse-fail=0.0),
  disposition options (a)(b)(c) recorded in `REWARD_BATTERY_REPORT_V1_1.json`, owner decides
  before S2. **Owner round-3 ruling D4=(b) applied, implementation v1.2** (module SHA
  `18c4e5a51d7f916b…`): empty stages = gateway-level degenerate output, FORMAL reward 0
  (`empty_stages_gateway`); gateway default ON = the formal RL reward path, OFF is
  diagnostic-only (pre-v1.2 behavior preserved); `composite` always carries C0 (5/6 for
  empty retained for analysis) and r4 V1_empty_stages diagnostics kept; no other penalties
  expanded. Owner qualification: engineering ruling only — the frozen schema contract is
  NOT amended (no minItems); formalizing non-empty stages would go through contract-change
  process. Battery 23/23 with formal-reward expectations, pytest 12/12 incl. the
  owner-required gateway on/off regression matrix, contract-dialect 755/755 on the formal
  path, D1/D3 regression tests unchanged; `REWARD_BATTERY_REPORT_V1_2.json` (v1.1/v1 kept
  as history). **Status: v1.2 awaiting owner diff/SHA review -> S1 (read-only) -> S2 as a
  separate release point (S2 NOT authorized).** **Pre-S1 verification DONE + S1 EXECUTED
  (2026-10-13, mdzhang read-only)**: scoped diff review = mechanical regression (v1.2
  gateway-off replay vs v1.1 recorded outputs) EXACT on 23 battery rows + 3 D4 scenarios;
  full SHA-256s in report; interface contract = trainer consumes ONLY
  `RewardResult.training_reward` (gateway default ON). **S1 = PASS with 2 open items**:
  (1) train-target dialect = contract 100% CONFIRMED (21,714/21,714 stage_seq; P0 preds
  1,852 full-scanned, parse 84.23%, rg all stage_seq — dialect chain end-to-end proven);
  train SHA matches frozen `443d5d31…` exactly; (2) vocab gap — contract says 30 classes,
  train targets use 23 (`vocab23_server_verified.json`, SHA `8562982d…`; authoritative
  30-name list not locally available; false-accepts impossible, possible false-rejects
  will surface in S2 r2 unknown-token report) — OWNER DECISION; plus evidence: P0 emits
  1 OOV family (CLASSIFICATION_LOAD — the exact defect r2 penalizes) and never emits 5
  train families (X4-type under-emission, S2 diagnostic material). Adapter fingerprinted
  (`82095811…`, 15.7MB). Report: `S1_VERIFICATION_REPORT_V1.json`. **S2 NOT authorized;
  awaits owner review of S1 results.** **Owner round-4: S1 PASSED (open item 1 = option
  (i), vocab23 provisional); S2 diagnostic dry run EXECUTED (no parameter updates)**:
  24 x 8 candidates (seed 20261013, temp 1.0 + rep-pen 1.15, p0b2-identical prompt);
  throughput **74.46 tok/s / 8.2GB peak** (Phase-2 cost gate: ~5 min per GRPO step,
  ~8h per 100 steps); **signal: pipeline PASS but coverage LIMITED** — effective groups
  6/24 = 25% (< the 8/24 clause), formal mean 0.9809 top-saturated, variance all
  "one defective candidate vs perfect rest", NO graded quality signal -> GRPO on
  structural-reward-v0 alone learns only rare-defect avoidance (X5/format), zero signal
  for the X4 main bottleneck; graded signal must come from r5 (Phase 3, gated on the
  multisolution line). r2-masking sensitivity LOW (5/6 groups keep variance) -> vocab23
  provisionally adequate; full OOV log: TEMORAL_FILTER (typo) + VECTOR_CLIP, 1 each,
  OOV rate 1%. Dry run caught+fixed the AUX13 bug (seq-less stage KeyError; regression
  added); post-fix battery 24/24, pytest 13/13, module SHA `2ade2e79…`. Report:
  `s2_dryrun/S2_DRYRUN_REPORT_V1.md` (all labeled provisional_vocab23). **Phase 2 NOT
  released; awaits owner review of the S2 report.** **Owner round-5: S2 engineering
  validation formally PASSED, limited signal coverage REGISTERED, Phase 2 stays PAUSED
  (no GPU rental, no training scheduling); next priority = r5 credibility + offline
  discrimination validation.** Delivered: (1) `R5_DESIGN_V0.md` — requirement-slot
  matching mechanism (10 rule families + equivalence classes + ABSTAIN gating +
  anti-bias audit checklist; validation gates: false-punish rate <=10%, omission
  detection >=80%, honest abstain rate; DRAFT awaiting owner review); (2)
  `R5_VALIDATION_PACKET_V1.md` + `r5_validation_packet_v1.json` — 6 groups x 4
  candidates = 24 BLIND labeling items built from real S2 candidates (band-stratified,
  shuffled, reward-blind; letter->cand mapping only in JSON) + builder script.
  **Awaiting owner: r5 design review + blind labeling -> implement r5 v0 -> blind run
  -> agreement metrics -> offline audit (effective-group coverage delta + three bias
  audits).** **Owner round-6: R5 mechanism PASSED, trigger rules conditionally passed,
  direct-RL NOT passed; four pre-implementation fixes (three requirement states /
  conditional equivalence / certainty-based abstain / task+candidate-level stats);
  labeling protocol frozen (4 main labels + 2 evidence fields, non-exclusive); owner
  completed the 24-item blind labeling = ALL omission (representation-sufficiency
  conservative caliber; packet lacks positive multisolution + unsupported cases, cannot
  declare r5 passed from it).** **r5 v0 IMPLEMENTED + BLIND-RUN + UNBLINDED**:
  `scripts/r5_requirement_parser_v0.py` (rules v0.2: 10 slot families, conditional
  equivalence, F3 certainty abstain, F4 full audit trail, vocab-gap signals for
  unrepresentable requirements). Unblind vs owner labels: candidate-level 22/24 agree
  (2/24 divergence = k=30160 B/C complete_coarse_uncertain vs omission, evidence-level
  consistent via the ACCURACY_ASSESSMENT gap signal); task-level 5/6 + 1 evidence-level
  (k=17970 abstain + PROFILE/CHART gap signals = the F3 design-success case); FALSE-
  PUNISH RATE UNMEASURABLE (0 positives); ABSTAIN 1/6. Validation itself caught and
  fixed 2 rule defects (study-area false STATS; elevation over-broad) + 1 semantic
  correction (coarse != complete). Report: `R5_V0_VALIDATION_REPORT_V1.md`. **Next
  (owner): (1) supplementary synthetic positive-multisolution packet, second blind
  round; (2) offline audit (effective-group coverage delta + three bias audits);
  (3) ruling on next stage — no auto Phase 2/3.** **Owner round-7: R5 v0.2 first-round
  validation PASSED (22/24 positive but limited — omission detection validated,
  multisolution tolerance almost untested); synthetic blind validation + full offline
  audit APPROVED (no parameter updates); RL access NOT approved; scorable three-class
  rule (never pool numerators). DELIVERED both round-7 reports**: (1)
  `R5_SYNTHETIC_BLIND_VALIDATION_REPORT_V1.md` — synthetic packet 9 items (3
  reasonable-complete / 3 clear omissions / 3 boundary; rules frozen v0.3:
  primary_family semantics + CHANGE_DETECTION detector), self-check 9/9 (zero
  self-harm; all three omissions named exactly; C1 gap + C2 abstain correct; A2's
  first draft genuinely lacked AGGREGATION and was rejected by its own self-check —
  the owner's warning materialized), awaiting owner blind labels for the authoritative
  false-punish rate; (2) `R5_S2_OFFLINE_AUDIT_REPORT_V1.md` — scorable classification
  **10/13/1 (vocab expressiveness = the dominant blocker; 13/23 partially_scorable)**;
  r5 splits 5 groups vs formal 6 with overlap only 1 (complementary, NOT additive;
  both low-density); length bias none (coverage rises with length); template bias 0
  violations; family bias = **MASKING coverage ≈1% (1 instance across 11 requiring
  tasks) — X4 cloud-mask under-emission quantified at slot level for the first time**.
  Data: `s2_dryrun/R5_S2_OFFLINE_AUDIT_V1.json`. **Phase 2/3 stay frozen; awaiting
  owner: blind-label the 9 synthetic items -> unblind false-punish rate -> independent
  next-stage ruling.** **Owner round-8 blind labels: FALSE-PUNISH 0/3, omission
  detection 3/3, abstain 2/9 (S8 boundary separate) — the multisolution-tolerance red
  line measured at ZERO for the first time; owner's complete_reasonable on S2/S3 = r5's
  complete_coarse_uncertain (same reserved uncertainty, mechanized). Round-8 ruling:
  R5 v0.3 admitted to the next offline round, Phase 2/3 NOT approved; next = align
  labels/rule-outputs/192 candidates, independently re-verify every counted-missing
  slot. DELIVERED `R5_MISSING_SLOT_RECONCILIATION_REPORT_V1.md`**: 358 missing
  instances fully listed (174/192 candidates); **INDEX 90 + MASK 87 = 49.4%** (X4
  resolved to exact slots); V1 plain 305 / V2 wrapper-ambiguous 53 (kept missing per
  the S8 precedent, reported separately); 3 deep-dives all genuine omissions (incl. 1
  V2 boundary); **three independent methods converge** (capability localization X4
  47.6% / S2 audit MASKING 1% / this reconciliation INDEX+MASK 49.4%); one
  construction-annotation error of mine registered (A4 expected-gap claim wrong —
  T_CROP has no accuracy requirement, r5 correctly fired nothing). **Awaiting owner:
  spot-check the reconciliation (2-3 per slot from V1) -> final V2 wrapper-ambiguity
  caliber -> next-round ruling (reproducible discrimination on real tasks + no
  systematic false-punishment = the RL-reward admission condition).** **Owner
  round-9: (1) V1 evidence-chain sampling approved (not all 358 claimed verified);
  (2) V2 THREE-STATE CALIBER FROZEN — missing_confirmed / covered_confirmed /
  unresolved_wrapper; the 53 V2 instances keep original missing records as audit
  history but are marked unresolved_wrapper in new stats (preventing
  "representational limitation misjudged as model incapacity"); (3) 358 = rule
  output scale, NOT independently human-confirmed errors;   frozen. **Owner rounds 15-16: three rulings landed + trainer v2 implemented**:
  (1) lambda final = S0 default (combinations need replicable increment to win);
  (2) v0.6 PARTIALLY IMPLEMENTED: TERRAIN unscored/representation_boundary
  (parser SHA `1cfd48c9...`), 25159 wrapper deferred with evidence checklist;
  (3) GRPO smoke contract DRAFT submitted for review. **Trainer v2
  (commit 34058b6a)**: P0-P4 blockers all fixed — real training path
  scaffolding, data isolation ENFORCED with assertions, advantage formula
  exact, k=8 enforced, KL reference = INITIAL P0 fmt policy (adapter swap,
  not bare base), abstain candidates excluded from stats (advantage 0, no
  silent 0.0). Fault injection 8/8, mock dry-run 24/24 updates full pass.
  **Owner round-16 contract final review: v2 FINAL CANDIDATE produced
  (GRPO_SMOKE_CONTRACT_V2_FINAL_CANDIDATE.md, commit c4ddbcbb) — §3.5
  four-point red-line text, §3.7 pre-registered rules table (PRIMARY =
  independent-set slot coverage v0.6 caliber; CO-GATE = ordered-F1 <=3pp
  drop; preliminary >=5pp; parse/invalid 5pp safety; discrimination demoted
  to diagnostic; dual reporting mandatory). Three final-approval
  preconditions landed.   frozen. **Owner rounds 19-20: trainer v2 accepted as DEPLOYMENT
  CANDIDATE** (mock pass != real GPU verification — three evidence tiers
  distinguished); E1 acceptance thresholds CONFIRMED (dC>=+5pp, dF>=-3pp,
  parse<=5pp drop, invalid<=5pp rise, no gaming — ALL simultaneous, no
  trade-offs); result framing = controlled experiment meets pre-registered
  criteria, NOT general GRPO effectiveness. **Five-step window execution
  order confirmed**: (1) GPU pre-check >=12GB + zero external-process
  impact; (2) server SHA re-verification (code ce573440, data, model);
  (3) minimal launch check (model load, single k=8 rollout, finite
  loss/grad, KL computation, checkpoint save); (4) <=48 updates per
  contract (hard stop = terminate, no ad-hoc reward/threshold changes);
  (5) E1 one-shot re-eval (no checkpoint cherry-picking). **ALL LOCAL WORK
  COMPLETE — awaiting GPU window. Phase 2/3 frozen. **GRPO smoke contract v3 FINAL SIGNED (commit 0febaf85)** — launch
  authorization pending GPU window (>=12GB margin) + external-process safety
  check; VRAM watch re-armed. Remaining pre-launch work: the GRPO trainer
  script per contract sections 0-3 (P0 fmt + base dual-SHA load, k=8
  rollouts, S0 reward = r5 v0.6 coverage, group-relative advantage, LoRA
  update, KL control, every-8-update checkpoints, six abort conditions, 48
  task-group update unit) — to be implemented with syntax + dry-run
  assertions before window deployment. Phase 2/3 frozen. **Owner round-17 final review + GRPO_SMOKE_CONTRACT_V3_FINAL
  landed**: the three pre-sign conditions are now FROZEN as computable specs
  (`eval_set_frozen_spec_v1.json`) — Cond-1 coverage formula pinned
  (candidate C/(C+M) over v0.6 required slots excluding TERRAIN/
  not_required/uncertain; covered includes covered_coarse; task = mean of 8;
  eval = mean of tasks; 7 no-scorable-slot tasks excluded by frozen ID);
  Cond-2 dC/dF in percentage points with FIVE simultaneous acceptance
  conditions (dC>=+5pp, dF>=-3pp, parse<=5pp drop, invalid<=5pp rise, no
  gaming red line; no trade-offs; task-level distribution mandatory);
  Cond-3 gaming monitors frozen pre-unblind with E0 baselines (empty
  14.06% -> >5pp FAIL; adjacent-duplicate 0% -> >5pp review / >10pp FAIL;
  unlinked-stage 45.21% -> >10pp review; mean stages 3.1 -> >25% review).
  **E0 frozen: C_E0 = 0.4975, F_E0 = 0.3577** (gold chains 24/24 from b1
  semantic_chain_rle — degradation co-gate reference, NOT a
  multisolution-improvement reference). Contract file:
  `GRPO_SMOKE_CONTRACT_V3_FINAL.md` (v2 content unchanged + frozen §8
  appendix). **Awaiting owner final sign-off; after sign-off still requires
  GPU window + >=12GB VRAM pre-check + launch-list SHA re-verification.
  Phase 2/3 frozen; RAFT/DPO/GRPO unrun. **Eval-set generation + scoring + blind packet DONE
  (commit 578c8439)**: 192 never-trained candidates (115.76 tok/s, same
  decode config); scoring-bug fixed (prediction text was mistakenly parsed
  as task text -> 154 false abstains; corrected: 32 abstain / 100
  incomplete / 16 coarse / 17 complete / 27 unparseable); rule-level
  missing marks: MASK 44, TEMPORAL 38, SPATIAL 29, TERRAIN 23 (new task
  mix), INDEX 16, COMPOSITE 14, CLASSIFY 9, STATS 7; 4/24 groups fully
  abstained (F3 correct). **Blind packet
  `eval_procurement/EVAL_SET_BLIND_PACKET_V1.md` frozen (SHAs logged),
  awaiting owner labels** -> unblind -> one-shot S0-S3 comparison ->
  reward-admission review.   frozen. **Eval-set blind labeling + unblind + one-shot S0-S3 comparison
  DONE (commit 98662901)**: 27 empty candidates EXACTLY match the r5
  unparseable list by ID; slot order 0 mismatches; 314 adjudicable slot
  instances: **TP 157 / TN 134 / FP 0 / FN 0** — r5 and the owner agree
  100% on every non-TERRAIN slot; all 23 boundary disagreements are
  TERRAIN (owner caliber: terrain processing unjudgeable at stage
  granularity) -> v0.6 ledger gains: demote TERRAIN from required. One-shot
  S0-S3 on the never-trained set (aligned adjudicable universe, TERRAIN
  excluded both sides): **S0 r5-only discrimination 13/17, tau +1.0, 0
  false-reward, 4 saturated — PASSES all thresholds**; lambda 0.3/0.5
  identical; lambda 0.7 misses discrimination (11/17); **structure-only
  (lambda=1.0) FAILS all** (0/17, tau -0.976, 7/17 false-reward groups,
  15/17 saturated). **The owner's round-13 replication demand is FULFILLED
  on never-trained tasks.** Bounds: n=17 tasks; owner score = stage-family
  C/(C+O); TERRAIN excluded both sides (disclosed).   frozen. **Owner round-15 three rulings LANDED**: (1) lambda final = S0
  (r5-only) as current default baseline — combinations kept only as
  future comparisons, must show replicable incremental benefit without
  extra costs to win; (2) v0.6 PARTIALLY approved & IMPLEMENTED: TERRAIN =
  unscored/representation_boundary (requirement layer preserved, excluded
  from both numerator and denominator, parser SHA `1cfd48c9...`, regression
  clean) — 25159 wrapper caliber DEFERRED with an evidence checklist;
  (3) GRPO smoke contract DRAFT submitted for review
  (`R5_V06_LEDGER_AND_GRPO_CONTRACT_DRAFT_V1.md`: P0 fmt baseline + S0
  reward only; <=48 updates + six abort conditions; E0/E1 one-shot;
  reward metrics reported SEPARATELY from final-target metrics — S0
  improvement != QGIS quality without independent end-to-end assessment;
  L2/L3 operator/param/DAG metrics marked not-yet-measurable; stop/rollback
  thresholds await owner). Statistical-unit discipline registered: tau=+1.0
  (task-group level) and 157/134 (slot-instance level) mutually support but
  are NOT the same metric.   frozen; RAFT/DPO/GRPO unrun. **Owner round-16 contract final review +
  GRPO_SMOKE_CONTRACT_V2_FINAL_CANDIDATE landed**: §3.5 replaced with the
  four-point red-line/conclusion-boundary text (reward-behavior diagnostics
  != capability evidence; joint examination of coverage + ordered-F1 +
  parse + structural validity + gaming checks; L2/L3 proxies flagged;
  limited quality claims need four preconditions; 24 tasks = preliminary
  evidence only); §3.7 pre-registered rules table (PRIMARY = independent-set
  required-slot coverage at v0.6 caliber; CO-GATE = ordered-stage F1 no
  >3pp drop; preliminary benefit target >=5pp coverage gain [engineering
  threshold]; parse/invalid 5pp safety lines; discrimination DEMOTED to
  reward diagnostic; task+candidate dual reporting mandatory). Three final-
  approval preconditions landed: contract revision done; full checkpoint
  identity recorded (adapter/base-config/train-data/eval-tasks/parser/vocab
  full SHA-256s); update unit = 1 task prompt + k=8 responses = 1 update,
  <=48; signal starvation computably defined (10 consecutive task-groups
  with zero within-group formal-reward variance). 25159 wrapper does NOT
  block this smoke: v0.5.1 conservative caliber (wrapper slots count as
  missing) fixed for the whole run as an experimental condition. **Awaiting
  owner final sign-off on GRPO_SMOKE_CONTRACT_V2_FINAL_CANDIDATE.md; after
  sign-off still requires GPU window + >=12GB VRAM pre-check. Phase 2/3
  frozen. Owner
  personally spot-checked 15 slot instances (merged by k): all "requirement
  confirmed; missing pending verification" — the JSON supports requirement
  confirmation, missing-confirmation needs full candidate stages; two evaluation
  risks flagged (candidates not independent — report task/candidate/instance counts
  together; slot presence != function realization — require task-requirement +
  stage-semantics + verified-equivalence). DELIVERED adjudication packet
  `r5_adjudication_packet_5516_6878_9210_9854_v1.jsonl` (32 records: k + cand +
  task + full stages + r5_missing; all 5 owner-named V2 items inside, r5_missing
  lists match the owner's enumeration exactly). **Awaiting owner: three-state
  adjudication per record -> reverse-direction checks (covered instances + negative
  controls) -> real-task revalidation on tasks not used in rule debugging -> reward
  admission review (RAFT/DPO/GRPO stay unrun until then).** **Owner rounds 8-9
  supplementary spot-checks (three batches through k=32751) confirmed all requirements
  while exposing rule-defect candidates — reverse controls EXECUTED (rules frozen
  v0.4.1)**: 5 rule defects confirmed & fixed — (1) unbounded `EVI` matched
  "de**vi**ation" (32751's two INDEX hits were both "standard deviation" — the
  owner's suspected false positive CONFIRMED); (2) SPATIAL scope-words treated as
  operations (32593); (3) COMPOSITE matched "composite indices" (26102); (4) STATS
  merged accuracy with area (30160 — accuracy moved to gap-signal only); (5) `crop`
  noun polysemy (introduced by fix #2, caught immediately by synthetic A4).
  **False-positive quantification: 358 -> 323 (-35, -9.8% all rule FPs/demotions;
  INDEX -15 / MASK -8 / COMPOSITE -6 / SPATIAL -4 / TEMPORAL -2); core finding
  ROBUST: INDEX+MASK = 154/323 = 47.7% still dominant — X4 is not a rule artifact.**
  New fourth state `requirement_uncertain` implemented (first instances: k=32593
  SPATIAL, k=26102 TEMPORAL, k=22822 MASK); V2 = 51. Synthetic-validation validity
  re-verified: 0/9 verdict changes under v0.4.1 (the owner's 0/3 false-punish
  conclusion stands on the frozen version). Report:
  `R5_V04_REVERSE_CONTROL_REPORT_V1.md`. **Phase 2/3 frozen; awaiting owner: spot-
  check this report (the deviation FP evidence chain) -> three-state adjudication of
  the 32-record packet -> reverse checks + undebugged-task revalidation -> reward
  admission review.** **Owner round-12: R5 v0.5.1 NOT admitted as formal
  training reward; SHADOW EVALUATION approved (Gates A-D, no parameter
  updates); three-source evidence judged separately (39/317 and 74/80 must
  NOT be converted into accuracy/omission rates — different statistical
  units); GRPO-entry risks registered (independent-set false-punish
  unverified / within-group discrimination value unclear / over-generation
  inducement). EXECUTED: Gate A DONE — all artifacts committed to Git
  (commit 7ba729a3, 61 files: reward module v1.2 + r5 v0.5.1 + adjudication
  chain + shadow contracts, incl. per-candidate independent-set outputs
  `independent_set_r5_outputs_v051.json`); Gate B blind packet ready
  (`GATE_B_INDEPENDENT_BLIND_PACKET_V1.md`, 10 tasks x 8 candidates, five-
  label slot matrices + candidate-level unnecessary_stages field); Gate C/D
  pre-registration frozen (`GATE_CD_PREREGISTRATION_V1.md`: CF1-CF4
  counterfactuals with CF3 no-reward-increase >=95% as the anti-over-
  generation hard gate; Gate D four metrics pre-registered — within-task
  discrimination >=70%, Kendall tau >=0.6, false-reward <=10%, saturation
  reported; n<10 subsets marked uncertain). **Awaiting owner: Gate B blind
  labeling of 80 candidates -> Gate C construction -> Gate D analysis ->
  shadow verdict (pass -> reward synthesis design; fail -> r5 stays the X4
  offline instrument). Phase 2/3 frozen; RAFT/DPO/GRPO unrun.** **Gate B EXECUTED + UNBLINDED (234 slot instances over 80
  candidates)**: TP 128 / **FP 4 (2.74% << 10% pre-registered line)** / FN **0** /
  TN 88 / unresolved_wrapper 14 (9.6%, separate) / false-requirements 0 — round-12
  risk #1 (unquantified false-punish) now quantified and LOW. All 4 FPs concentrate
  in k=25159 COMPOSITE wrapper-caliber divergence (owner credits wrapper+context as
  visible composite evidence; r5 conservatively requires AGGREGATION) — a single
  fixable cause, NOT random; task-level deltas <=2 everywhere except 25159 (+10,
  fully explained by the same divergence); FN=0. Invalid stages (4) and redundancy
  (empty) recorded separately per owner directive. Shadow gates: A done, B done,
  C/D next; the wrapper-caliber fix enters the v0.6 ledger PENDING owner approval
  (no rule changes during shadow evaluation). Report:
  `R5_GATE_B_UNBLIND_REPORT_V1.md`. **Gates C+D EXECUTED (commit 2018cf08)**: Gate C counterfactual
  6/6 x 4 gates (CF3 redundant-no-increase >=95% hard gate holds); Gate D
  three-scorer ranking on the 10 independent tasks: **structure formal FAILS
  all pre-registered thresholds** (discrimination 0/10, mean tau -0.737
  anti-aligned, 2 false-reward groups, 4 saturated — ranking-level
  corroboration of the S2 dry-run finding); **r5 coverage PASSES all**
  (7/10 discrimination at the 70% line, tau +0.796, 0 false-reward, 1
  saturated); combined lambda=0.3/0.5 PASSES (0 saturated). Shadow verdict
  per the pre-registered rule: r5 and low-lambda combinations carry the
  task-quality signal and advance to reward-synthesis DESIGN; structure
  formal alone does not. Honest bounds: n=10; owner labels are
  stage-family granularity; the negative-tau mechanism awaits owner review.
  Report: `R5_SHADOW_EVALUATION_VERDICT_V1.md`. **Owner round-11: INDEX definition FROZEN = computing a NEW
  index from bands (product-band reading/scaling != INDEX; 9854 = not_required);
  v0.5 ledger L1/L2/L3 approved; re-run + independent revalidation approved;
  reward admission separately reviewed. EXECUTED v0.5 -> v0.5.1 full chain**:
  L1 area statistical-action context (9210 false requirement eliminated, real
  stats preserved); L2 INDEX compute-context determination (9854 -> not_required;
  genuine compute tasks preserved); L3 requirement_determination field live.
  **Reverse controls caught two v0.5 regressions mid-round, both fixed**: 9854
  STATS deleted by the L1 context window (exactly the owner's step-3 warning) ->
  mean-over-region pattern restored it; 6878 "NDVI derived from imagery" missed
  -> derived-from pattern added (matches the owner's round-10 adjudication).
  **Numbers: 323 -> 317 (-6, all caliber fixes); INDEX+MASK = 153/317 = 48.3%
  stable; independent task-set revalidation (10 tasks x 8 candidates that drove
  NO rule change): task-level 10/10, candidate-level 74/80 requirement-coverage
  gaps (rule-level, unadjudicated)**. Process lesson registered: rule-version
  evolution should git-commit BEFORE re-runs (the v0.4.1 instance-level baseline
  was overwritten; slot-level aggregates survive via dual outputs); recommend
  committing rl_line artifacts with the next commit. Report:
  `R5_V05_REVALIDATION_REPORT_V1.md` (includes the reward-admission review
  material list: rules-vs-labels / reward distribution / frozen external evals
  reported side by side, none cross-corroborating). **Phase 2/3 frozen;
  awaiting owner: reward-admission ruling.** **Owner round-10: the 32-record packet FULLY ADJUDICATED
  (dual-track: requirement states separate from coverage states) and FROZEN**
  (`r5_adjudication_5516_6878_9210_9854_frozen_v1.json`): r5's 61 missing marks
  resolved as **missing_confirmed 39 / unresolved_wrapper 5 / requirement_uncertain
  8 / not_required 8 / reclassified covered 1**. **Two rule findings enter the v0.5
  ledger (awaiting owner approval)**: L1 = `\bareas?\b` false requirement (9210's
  "deforested **areas**" class name triggered the area-statistics slot -> 8
  candidates mislabeled; fix = statistical-verb context); L2 = INDEX slot DEFINITION
  boundary (9854: MODIS product-band reading + scaling != computing an index -> 8 x
  requirement_uncertain; **the owner must fix the INDEX definition first**). L3 =
  record format gains a requirement_determination field (required/not_required/
  uncertain), only `required` enters coverage adjudication. **Reporting discipline**:
  39 is NOT a unified omission-rate numerator — 9210 non-required, 9854 definition
  boundary, and AGGREGATION granularity uncertainty are all reported separately.
  Positive: the uniform wrapper rule worked (5/5 unresolved_wrapper); covered_coarse
  semantics held (9854 cand3/4/6 honest annotations match the owner's notes); 39/61
  marks confirmed (64%) with all 16 overturned concentrated in two locatable issues.
  Report: `R5_ADJUDICATION_FREEZE_REPORT_V1.md`. **Awaiting owner: (1) fix the INDEX
  slot definition; (2) approve the v0.5 ledger (L1/L2/L3); (3) then r5 v0.5 re-run +
  reverse checks + revalidation + INDEX/MASK confirmed-omission summary -> reward
  admission review. Phase 2/3 frozen; RAFT/DPO/GRPO unrun.**
- **Two mechanism corrections frozen as design principles** (owner method review): (C1)
  group-relative comparison is NOT de-biasing — normalization cancels only additive
  common-mode offsets; content-correlated scorer bias gets REINFORCED, so de-biasing belongs
  to reward verification + confidence gating. (C2) RAFT cannot create verifier-invisible
  correctness — first RAFT round restricted to verifiable error classes. E7 (Kalman /
  estimation enhancement) launches only after measured GRPO advantage-estimation instability.

## (0) Planner representation-pivot line: P1/P2 closed; P0 = current best (2026-10-13)

- **Current best model on the frozen planner benchmark: P0 fmt checkpoint**
  (`/home/qy/stage1_run_planner_v2_fmt/stage1_adapter`, dev-1852 parse
  .8445 under the batched three-way instrument). Historical bs=1 reference:
  .8423 (a153dfe9 preds).
- **P1 (mixed-format SFT) FAIL, mechanism identified**: same-prompt dual-
  format supervision (208 folded + 1,200 old) gives the model no fold-
  trigger signal -> parse dropped to .789, fold adoption 11/1,545 rows.
- **P2 (uniform-target SFT, owner-approved) trained + evaluated**:
  data gate 1,161/1,200 converted (39 isolated undeclared-window rows, no
  forced folds), G5 100% exact; fold adoption fixed to 100% of parsed rows
  and P2 beats P1 everywhere (+4.5pp parse, -9.5pp hit-cap), but dual
  criteria vs P0 NOT met: parse .8342 (-1.0pp, within noise), fidelity
  -0.7~-1.5pp. **Failure mode precisely localized**: 291/307 P2 failures are
  literal stage-list loops on window-bearing rows -> window-folding
  supervision too thin (only the 208 rebuilt rows teach window folds).
  Authority: `plan_pipeline_v1/planner_design/p2_uniform_gate_v1/`
  (gate report + three-way eval), commits 9195219b / 1f30d625.
- **Rulings landed (owner, 2026-10-12/13)**: P3 FROZEN pending error-analysis
  gate; budget NOT the bottleneck (768->2048 zero change, 0/36 improved);
  error taxonomy on 1,564 parsed dev rows: 15.9% exact -> bottleneck =
  Layer-1 planning. E2E mainline Steps 1-3 complete on dev-120 (QGIS
  domain, commits 608d40f3/da2a2333/0c399113): P0 cross-domain blueprints
  frozen (parse .65, zero perfect, family P .163/R .140), Oracle grounding
  best opF1 .2897, true-E2E opF1 .0332 -> BOTH decision-tree branches fire
  (L1 content errors AND L2 grounding independently deficient).
- **Active mainline (owner, 2026-10-13): Stage-1 capability audit BEFORE
  QGIS-operator learning; training not on the table — authority and live
  state in section (0a) above.** Ruling record + acceptance matrix
  (dependency eval = option (a) three layers; external set = supplementary
  axis, not in PCA v1; three control points: threshold isolation,
  trusted-dev vs acceptance-set division, three-outcome decision tree):
  `planning_capability_audit_v1/STAGE1_GATE_OWNER_RULING_V1.md` /
  `STAGE1_GATE_ACCEPTANCE_MATRIX_V1.md`.
  **RESOLVED 2026-10-13: owner ruled PCA (section 0a above) — the audit
  precedes any further training or grounding work.**
- **Eval instrument note**: dev-1852 evals now use the batched three-arm
  script (bs=8 left-padding, symmetric across arms; aggregate drift vs bs=1
  <=0.3pp; EOS termination absent in ALL arms - p50=384 tokens burned, JSON-
  completeness-before-cap is the effective parse condition).

### Superseded but referenced (2026-10-10 snapshot)

- GEE detector audit (A1-A4) + frozen-data impact analysis: CLOSED, no
  rebuild (owner ruling a). Authority:
  `docs/reports/gee_frozen_data_impact_v1/`,
  `docs/reports/gee_semantic_planner_v1_pilot_round3/`.
- Stage-1 (GEE stage) gate FAILED all five conditions -> owner froze
  Task->Blueprint->Serializer->Grounding pivot (line remains closed).
- Current Best Model Audit protocol v1 frozen (e21b5e47): primary benchmark
  = QGIS dev-120 processes+links, unified inference; test-111 never used
  for selection.

## Active Route-2 v2 handoff

**Compute server mdzhang (10.191.2.38) is ONLINE (repowered ~2026-10-11,
owner coordination)**. Live assets there: P0 fmt adapter
`/home/qy/stage1_run_planner_v2_fmt/stage1_adapter`, P1
`/home/qy/stage1_run_p1_v1/`, P2 `/home/qy/stage1_run_p2_v1/`, paired-set
`/home/qy/pairs_with_task_208.json`, three-way eval outputs
`/home/qy/p*_dev_full_preds*.json` + `/home/qy/p2_three_way_eval.json`.
Co-tenancy protocol: check `nvidia-smi --query-compute-apps` before GPU
launches; yyt (labmate SAM training) and the parallel C0/A1' line share the
GPU — never kill foreign processes; A1 decode-contrast (protocol v1.1) is
the parallel line's experiment, not this line's.

**Base zero-shot dev result (2026-09-27, evaluator v1.3.1, zero OOM/timeout/batch-halving)**: W1/W2/W3(as-is,rewrite)/W4 all 0.0; invalid 2795/3236 (86.4%). Untrained Base sits at the floor -> absolute-floor thresholds are trivially satisfiable; the pre-registered W1-W4 judgment weight falls on the delta (zero-shot + Delta_i) conditions. Formal reading belongs to the owner. Dev artifacts committed by the holder line (0a41a6d) and mirrored in the backup.

**Base zero-shot test half: cancelled mid-run (owner decision), rerun on a rented GPU** under the frozen SHA trio: evaluator v1.3.1 / probes dev c3d95f67... test 866c3762... / inference config 6355bab4.... The mid-run silence (no disk/log writes for hours) was evaluator-by-design - reports are written once at completion (confirmed by the holder line); do not diagnose a hang from log silence again.

Phase R remains **CLOSED-FAIL (infrastructure/evaluator failure), strictly NOT Stage-2 FAIL**: `docs/reports/transfer_phase2/phase_r/phase_r_report.md`.

**Next actions (gated on the rented GPU + owner release)**: (1) rent GPU, restore env, re-download Qwen3.5-9B-Base -> (2) Base zero-shot gate-test rerun (~11h at dev pace, --batch-size 1) -> (3) pre-register W1-W4 absolute floors + Delta_i -> (4) Stage-1 training only on explicit owner release. The Route-2 v2 holder line was notified before shutdown and confirmed; their poweroff watcher was fail-safe and did not interfere.

Stage-1 protocol and B2 construction gates remain frozen。
**租卡机产物回迁规则**（2026-09-30 立，全文见 `route2_p0_contract/RENTED_BOX_ARTIFACT_POLICY_v1.md`）：租用服务器为临时资源，其上一切实验产物（报告/账本/adapter/日志）须先入桌面仓库再于 mdzhang 复电后同步——Stage-1 adapter 与全量训练账本已按此入库（`stage1_run_v1/`）。
; Stage-2 preregistration remains `docs/plans/transfer_phase2_stage2_prereg_v1.md`. See `docs/plans/transfer_phase2_roadmap.md` and `route2_p0_contract/` for live gate state.

This is the routine handoff entrypoint. See `task_plan.md` for live work and
`docs/PROJECT_CONTEXT.md` for detailed historical evidence.

## (7) Stage-1 training protocol frozen (2026-09-24, owner ruling, v1)

Single mixed stream (**token-based**): Task->Plan 60% / Dependency-
Completion 10% / Reconstruction 10% / W4 20% (<=25% cap) / **Chain LM
0%** (A1 attribution cleanliness). Recipe identical to P0 (QLoRA r16
a32 NF4 / 1e-4 cosine / batch 32 / max_len 1024). **Truncation
correction**: Task fully protected, overflow truncates the Plan tail,
all audited. Gate: two-level (dev selects, test judges) + dual-
condition thresholds (absolute floor AND zero-shot + delta,
pre-registered on the frozen base before training) + **hard pre-
condition** (all single-capability thresholds pass before weighted
comparison: W1 .20 / W2 .25 / W3 .40 / W4 .15 — template memorization
cannot average its way through). **W1 correction**: known operation
concepts + new contexts / low-frequency ops / surface variants (never
unseen concepts); compositional generalization burden sits on W3 novel
combinations. 1 epoch first; FAIL -> continue under the same protocol.
**Success criterion = gate pass, not loss.** (1)->(7) fully frozen.
Build-6's three CPU artifacts and the Stage-1 preflight (v2_2 data +
Gate-v3 probes + evaluator) are all complete; training now waits only
on a GPU window and the owner's explicit release. See
`route2_p0_contract/ROUTE2_V2_STAGE1_PROTOCOL_v1.md`.

## (6) B2 data construction v0 (2026-09-24, owner ruling)

**Order (veto-gated)**: 6-0 Operator Capability Profile -> 6-1 Audit-A
(redefined as an Information Discriminability Test — does the interface
objectively contain the discriminators, not "can a model guess";
148 mapping groups -> Grounding Discriminator Matrix; anti-cheat:
gold-back-projected Plans do not pass by default) -> 6-2 chain->Plan ->
6-3 Retention Audit -> 6-4 attach Plans -> 6-5 B2 package. **Plan main
source = Teacher Plans from the frozen Stage-1 model**; the gold
back-projection line is diagnostic/upper-bound only (strict de-grounding
+ Leakage Audit: can the operator ID be recovered from the Plan), the
two lines never mix; gold may never generate/correct/select/rewrite
Teacher Plans. **B2 dual families**: G1 operation grounding (unit=
operation) / G2 workflow grounding (unit=workflow), explicitly labeled
for separable analysis. One interface path across splits (1334/120/111
all planned by the same frozen Stage-1; test adds prediction lock).
**Key ordering constraint: no batch distillation before Stage-1 passes
its capability gate** (poor Teacher Plans are part of the experimental
design). 6's three artifacts + Audit-A PASS gate the step-7 protocol.
See `route2_p0_contract/ROUTE2_V2_B2_DATA_CONSTRUCTION_v1.md`.

## (5) Stage-2 grounding information requirements v0 (2026-09-24, owner ruling)

Stage 2 = Task + Plan + QGIS knowledge (internalized via post-training,
not input text) -> QGIS Graph. **Four grounding classes G1-G4**: I/O
constraints / implementation-discriminating constraints (the true gap
the Oracle exposed: raster vs vector, mask geometry, CRS behavior...) /
parameter semantics (training data must carry parameter-schema <-> task-
constraint correspondence) / graph realization (ports, fan-in-out —
where the Stage-1 linear / Stage-2 DAG division lands). **Three audits
become benchmarks**: Audit-A discriminability (pick the implementation
within oracle mapping groups; **fail = do not train B2**) / Audit-B
information sufficiency (per-field ablation toward the minimal
sufficient interface) / Audit-C realization (operator/link/port/fan
checks). Three freezes: GEE API never enters Stage 2; QGIS knowledge is
not stuffed into the Plan (What-should-happen vs How-QGIS-implements
boundary); QGIS-plan provenance stays an open dependency (sole rule:
satisfy the 4-contract + pass audits). **New asset: QGIS Operator
Capability Profile** (309 operators, from Neo4j QGIS_Operator 1,291
nodes + the processing registry — Stage-2's knowledge base). See
`route2_p0_contract/ROUTE2_V2_STAGE2_GROUNDING_REQUIREMENTS_v1.md`.
Order: (1)-(5) done -> **(6) B2 data (open question: how the 1,334 QGIS
workflows get Plans without circular leakage)** -> (7) protocol.

## (4) Stage-1 interface information contract v0 (2026-09-24, owner ruling)

Only the **information contract** is frozen, not schema: Plan = five
layers (P1 open-vocabulary operation intent, P2 typed I/O [KG 1,425
nodes hasInput/hasOutput as source — the 37-class defect was missing
typed context, not category count], P3 order and P4 dependency as
**separate fields** [adjacency != dependency; unknown when
unextractable, never fabricated], P5 step-relevant constraints [no task
text duplication]). GEE provenance two-tier isolation: API/AST/canonical
chain stay on the training/audit side, **never exposed to Stage 2**
(prevents regression to API translation). Forbidden as sole interface:
37-class IDs, bare token sequences, GEE API chains; positioning = finer
than 37 classes, more platform-neutral than GEE API. **Three formal
anti-bottleneck audits** (defined now, benchmarked in 5): Plan Collision
/ Information Retention / Grounding Discriminability. Not frozen:
schema, serialization, plan language, W1-W4 weights, how QGIS-side plans
are obtained (open dependency). Boundary: 4 = what to retain (done);
**5 = what else is needed (next)**. See
`route2_p0_contract/ROUTE2_V2_STAGE1_INTERFACE_CONTRACT_v1.md`.

## (3) Objective & interface v0 decision (2026-09-24, owner ruling)

**Task -> Workflow Plan is the Stage-1 core objective** (W3 carrier);
auxiliaries derive from the same plan (Dependency/Completion/
Reconstruction; W4 <=25% tokens); raw chain LM is out (3-C, A1
precedent); **Stage-2 interface = Task + Workflow Plan -> QGIS
Grounding** (task-preserving — the Oracle showed task text carries more
operator evidence than gold semantic chains; the Plan's job is to make
the task's implicit structure explicit, not replace the task). Plan
representation: only information constraints frozen (operation-level /
ordered / dataflow / typed I/O / dependencies / subgoal relations) —
**schema NOT frozen, no 37-class ontology, no QGIS API embedding**.
Training organization = planning-centered multi-task (W1/W2 organized
into the main objective, W4 as controlled auxiliary). Formal A1
differentiation: learning pressure shifts from sequence continuation to
task-conditioned workflow construction with explicit structural
constraints. Answer-echo counter-design: accept only rewritten Task A'
-> Workflow A plus novel operation combinations. See
`route2_p0_contract/ROUTE2_V2_STAGE1_OBJECTIVE_INTERFACE_v1.md`.
Order: (3) done (v0) -> **(4) interface concretization (fields /
derivability / anti-bottleneck; next)** -> (5) Stage-2 info needs ->
(6) B2 data -> (7) training protocol.

## Stage-1 capability definition frozen (2026-09-24, owner ruling)

**W1-W4 frozen, W5 delegated**: W1 operation semantics (foundation) /
W2 dataflow composition (foundation) / W3 goal-decomposition planning
(**core**; gate must cross-check W1/W2 sub-scores to rule out template
memorization) / W4 structural discrimination & repair (auxiliary,
**token budget <=25%, default ~20%**). **W5 branching delegated to
Stage 2** — formal boundary: Stage 1 = Sequential/Linear Workflow
Reasoning, Stage 2 = QGIS-specific DAG Grounding (must be stated in the
paper). Terminology frozen: retire "Stage 1 outputs Semantic Workflow";
say "Stage 1 forms and explicitly exposes a Workflow Reasoning
representation/plan" — **capability frozen, representation NOT frozen**.
Inherited constraints: A1 boundary (structure-related learning pressure
required + must answer "why A1 wouldn't"), B1/Oracle boundary (no
information-losing abstraction), non-memorization (held-out vocabulary +
recombination acceptance). See
`route2_p0_contract/ROUTE2_V2_STAGE1_CAPABILITY_v1.md`. Order: (1)
architecture done -> (2) capability definition done -> **(3) Stage-1
output/interface (next)** -> (4) Stage-2 info needs -> (5) B2 data ->
(6) training protocol.

## Route-2 v2 architecture decided: two-stage capability formation (2026-09-23, owner ruling)

**Top mainline decision**: new Route-2 = two-stage capability formation
(Stage 1 GEE Workflow Learning -> independent capability gate -> Stage 2
QGIS Grounding Post-training; Stage 3 RL reserved, not started). Direct
motivation: B1 was formally two-stage but effectively single-stage
(stage 2 trained Task->QGIS directly — no verified capability interface);
evidence base: the Oracle verdict (37-class semantic chains ground to
nothing). Key understanding: **Stage-1 capability != 37-class semantic
workflow** — Stage 1 must form reasoning from the raw GEE workflows
(gee_canonical_chain) themselves. Order: (1) architecture (this entry)
-> (2) Stage-1 output/interface + capability-gate design (**current
frontier**) -> (3) Stage-2 information needs -> (4) B2 data -> (5)
training protocol. See `route2_p0_contract/ROUTE2_V2_ARCHITECTURE_v1.md`.

## Route-2 four-block synthesis: the semantic->operator interface is broken (2026-09-17 -> 09-23)

dev + test + error audit + Oracle grounding, all four blocks:

```
              dev opF1   test opF1   Oracle opF1   Oracle EM
C0 QGIS-only    0.5611     0.5059      0.0771         0.000
B1 sem->QGIS    0.5541     0.4788      0.0963         0.000
A1 DAPT->QGIS   0.5510     0.4584      0.1165         0.000
```

**Oracle verdict (branch B)**: feeding the gold semantic workflow (B1
vocabulary, 148 operators mapped, 21 categories in use) directly to all
three arms puts everyone on the floor (opF1 0.077-0.117, EM exactly 0) -
including B1, whose stage-1 fitted Task->semantic to loss 0.336. **The
37-category semantic abstraction does not determine QGIS operator
choice: task text (0.479) carries more operator evidence than the gold
semantic chain (0.096).** The abstraction loses what grounding needs -
the granularity-gap hypothesis now has direct experimental support.

**Error audit headline**: ops_mixed (partially-correct operator sets)
dominates at 55-58% of rows in every arm; B1's linkF1 edge survives the
parse-ok restriction (0.4917 vs C0 0.4476) but the clean
ops-wrong-links-right cell is 8 rows vs C0's 7 (a distributed effect,
not a subpopulation); all arms under-generate ~2.9 operators/row.

**Final mechanism**: H1 fails at the semantic->operator grounding link -
not at Task->workflow learning (B1 learned it) and not at QGIS grounding
itself (C0 reaches 0.51). A model trained on both directions
(Task->semantic, Task->QGIS) does not compose the third (semantic->QGIS)
zero-shot. B2 branch pre-registered by the owner and now hit: oracle-low
-> dedicated semantic->QGIS training (Semantic Operation->Operator and
Semantic Workflow->Graph), not more plain QGIS SFT. B2 design awaits
owner approval. Artifacts: `test111_final_v1/` (RESULTS_LOCK_v1,
ORACLE_RESULTS_LOCK_v1, error_audit_v1, oracle_semantic_input_v1,
per-arm predictions + SHA). Scripts: `scripts/audit_route2_test111_errors_v1.py`,
`scripts/build_route2_semantic_oracle_v1.py` (29178fd).

Test detail (dev-120 checkpoint selection; one-shot test, SHA-locked):

```
           dev opF1 (best)   test opF1  test EM   test linkF1  test parse-fail
C0 QGIS-only    0.5611 ep20   0.5059     0.1351     0.4355       2.7%
B1 sem->QGIS    0.5541 ep18   0.4788     0.1441     0.4607       6.3%
A1 DAPT->QGIS   0.5510 ep15   0.4584     0.1081     0.3794       9.0%
```

Additional readings: parse-failure monotonicity (C0<B1<A1) reproduces on
dev and test; dev differences phrased as comparable-to-epoch-fluctuation
(no significance test); both GEE stages fitted successfully yet transfer
did not follow. final-100/refusal-12 (frozen benchmark scorer) belongs
to the peer Gate-2 line. Incident history: three server reboots in three
days (exact-state resume proven live on B1); B1's test eval hit a
transient CUBLAS error and passed cleanly on a solo rerun; autoboot
disarmed after use. Ledgers: run_ledger{,_A1,_B1}.json +
RESULTS_LOCK_v1.json (dd64280/d7b3180/8d785df/c77989a). Gate-2 eval
window open.

## M1-R2 evaluation complete: structural collapse fixed, task mapping not (2026-09-16, Phase 2 closed)

The M1 enhancement line (decoder backbone domain pretraining) is fully closed:
DAPT 493.4M byte-tokens (loss 5.56 -> 0.6257) -> migration audit 8/8 -> SFT with
the R1 protocol verbatim (single variable = decoder backbone init, ckpt
22a77f77...) -> frozen-protocol evaluation (R4 discipline: prediction hashes
locked before any gold access; the M3 block re-scores to the locked 0.1605
exactly).

**R1 -> R2 (final-100)**: empty graphs 88% -> 20%; bridge drop 83.8% -> 43.9%;
L3 tokens 154 -> 528; Define-Projection first token 99% -> 0% (new attractors:
Add Spatial Index 70 / Lake Inundation 26 / Simplify 4); chain length 1.5 ->
5.3; **operator F1 0.0047 -> 0.0857 (x18)**. In-distribution is essentially
flat (val Top1 14.87 -> 15.24%, diagnostic F1 0.173 -> 0.187); edge F1 still
0, harmful-extra 0.90 (fixgeometries appears in 88/100 rows — a new
"universal opener" bias). **Conclusion (owner-final, M1 line closed at 5e3f818)**: R2 improves the
structural capability of "what kind of sequence to generate" but not the
conditional mapping of "which specific workflow to generate from the task
semantics" (layer A generator state fixed by DAPT; layer B conditional
mapping untouched — closing the loop with the Phase 0-B attribution).
**Phase 3 ruling: R3/R4 will NOT be opened** — the three-route convergent
signal shows model-side changes do not improve task->L3 mapping; insufficient
task-semantics-to-operator supervision in the training data is the primary
candidate bottleneck worth prioritizing (careful wording: not "proven to be
data"). **Next phase: paper_v2 data side** (intent rewrite of the 257k
description library), with R1/R2/M2/M3 as the preceding baselines. Two evaluation-environment
incidents are archived separately (dev-20 first run invalidated by legacy
id-mapping leakage; val diagnostic crashed on the taxonomy default path — the
three M1 inference env vars must be embedded in the launch entrypoint).
Evidence: `docs/reports/m1_r2_eval_v1/`, `docs/reports/qgis_planner_eval_v1/
SCORES_R2_v1.json` + `predictions_r2/`.

## External data & evaluation landscape survey (2026-09-16 -> 09-18, paper_v2 precursor)

Survey series, three reports (all read-only, no external data consumed): v1
GIS-specific data `docs/reports/external_gis_training_data_survey_v1.md`; v2
general tool-chain literature & methods addendum
`docs/reports/external_gis_training_data_survey_v2.md`; **consolidated report
with the new evaluation-comparison dimension
`docs/reports/qgis_data_eval_landscape_v1.md`**.

Headlines: (1) Data — no ready-made "NL intent -> QGIS operator DAG" training
set exists; the main material remains the internal 257k description library +
44,220 converted GEE rows; the three external sources (GeoAnalystBench
Apache-2.0 / AutoGEEval-plus 2,612 cases, no license / GISAgentBench 349 tasks,
repo not public) total ~1,800 intent-form samples usable only as OOD eval +
seeds + citations; no external GEE<->QGIS crosswalk exists — the in-repo KG is
the only implementation (paper contribution). (2) Evaluation — benchmark
v0.2.1 occupies a unique niche (the only GIS eval scoring structured operator
DAGs rather than code, the only refusal diagnostic + unsafe-planning metric,
prediction-lock + frozen scorer, topology-tiered gold); gaps vs external
standards = execution-level ground truth (GISAgentBench), scale (AutoGEEval++
thousands vs our 100), dynamic/multi-turn (BFCL V4, GeoAgentBench sandbox);
four v0.3 candidates (execution-augmented layer / scale expansion / topology
breakdown / refusal expansion) all NOT approved. (3) Alignment diagnosis — the
benchmark is already intent-form; the mismatch is on the training side (GEE
100% answer-echo): fix the data, not the eval; the eval-side shortcomings are
scale and execution evidence. Rewrite-pipeline method anchors: back-instruct
(TaskBench) / WorkflowLLM three phases / APIGen three-stage verification.
Mainline status: M1 line closed at 5e3f818 (R2 x18 but conditional mapping
unsolved); M2 three-arm loop closed (C0 best at 0.2236); M3 closed at P2-T1;
next phase = paper_v2 data-side four-arm rewrite.

## M1 enhancement-ablation route opened + domain_corpus_v1 spec drafted (2026-09-11)

Benchmark v0.2.1 freeze (6006e49) is merged into main (c515c77/5647636); the M1/M3
inference config is frozen (45f5abb, `docs/reports/qgis_planner_eval_v1/INFERENCE_CONFIG_FREEZE_v1.json`)
and final-100 predictions are complete: M1 has 88 empty graphs with 100/100 chains starting
with L3_01_10_02 Define Projection (OOD collapse; val Top1 13.75%), while M3's outputs
follow the task text (74% of tokens within bridge coverage). M1-R1 is frozen as the
scratch baseline (its true composition is a frozen general-purpose English BERT plus a
from-scratch decoder, not pure random init) — no retraining, no relitigating. On this
basis the M1 enhancement ablation is opened (this round adds only M1-R2 = decoder-only
causal-LM DAPT with the BERT encoder kept at its R1 frozen configuration; R3 = BERT MLM
and R4 = +TAPT are Phase-3 candidates pending R2's result) together with domain_corpus_v1
(rules frozen at v1 in `docs/plans/domain_corpus_v1_spec.md`; owner decisions 2026-09-11:
no external QGIS/GDAL/OGC docs this round; D1–D5 corpus pools; four-layer leakage
isolation including a 6-gram=0 assertion; one manifest with separate M1/M2 recipes; four
D5 audit fields). Execution order locked: Phase 0 pre-checks (task-text language matrix,
task_type oracle-vs-Unknown inference ablation) → Phase 1 corpus build → Phase 2 M1-R2 →
Phase 3 decision on R3/R4/stop. See the "模型实验" section of `task_plan.md`.

**Phase 0-A is complete** (2026-09-11, `docs/reports/m1_phase0_precheck_a_language_v1/`):
all 132 benchmark tasks are English with bert [UNK]=0 — no inference-side language
confounder, so M1's collapse cannot be attributed to input language. However, within
paper train the QGIS subset (616 rows) is 81.7% Chinese/mixed and 69.2% of those rows are
≥50% [UNK] for the M1 encoder, leaving only ~190 readable QGIS supervision rows for M1
versus all 8,817 for M3 — a training-side language asymmetry now on the M1-vs-M3
confounder list, and M1-R2's DAPT can only consume the English pool.

**Phase 0-B is complete** (2026-09-14, `docs/reports/m1_phase0_precheck_b_tasktype_v1/`):
a 2x2 ablation (task_type {oracle, Unknown} x length {per-type, fixed-8}) on the same
SHA-bound checkpoint, same 49 val rows, same process — **task_type OOD is the primary
trigger/amplifier of M1's collapse, but not its only cause**: switching only the
task_type string to Unknown drops P/R from 0.13/0.20 to 0.00/0.00, first-token diversity
26→5, with an attractor emerging (L3_04_05_09 + Define Projection 24.5%); GEE and QGIS
rows both collapse to zero. Yet under Oracle the model is still 0/49 exact with SetF1
0.148 — the base capability is low on its own. The length policy is second-order, and
the empty-prediction rate is 0/49 in every condition (the benchmark's 88/100 empty
graphs are bridge drops, not empty chains; token-level and graph-level emptiness are
reported separately from now on). task_type is a quantified M1-specific handicap
(ΔP −0.13 / ΔR −0.20; M3 consumes no task_type).

**Phase 0 closed** (2026-09-14, owner ruling: no further A/B). Final four-layer
attribution: M1-R1 benchmark collapse = (1) task_type conditioning failure (primary
trigger/amplifier) + (2) benchmark text OOD (amplifier, not a necessary condition) +
(3) insufficient domain/GIS prior (to be tested by R2) + (4) QGIS Chinese-supervision
coverage gap (training-side structural limit). R2 goal: measure the independent
generalization contribution of decoder-backbone domain pretraining (single active
variable = decoder initialization).

**Phase 1 domain_corpus_v1 is complete and frozen (2026-09-14)**: D3 code pool
43,809 docs / 174.7M WP (91.6% of the 47,852 authority sources retained after
cleaning) + D4 English text 6.6M WP + D1 anchors; assertion battery all-pass. Frozen
recipe: D3 60% downsampling + D4 4x epoch-level oversampling + D1 1x, with a
**byte-level training budget of 487.5M byte-tokens** (exposure D3 80.15% / D4 19.85%).
The M1-R2 §10 implementation contract is frozen (decoder backbone domain pretraining:
DAPT with a temporary byte-level vocab, dummy memory, and task_type=Unknown; SFT
reinitializes the 132-token L3 vocab, carries over the body+FiLM, and keeps the R1
protocol exactly unchanged). A leakage-set GPL-boilerplate false-positive was found and
fixed during the build (one paper_v1 test row's task_text is itself a GPL header —
recorded as a data-quality note). Evidence: `docs/reports/domain_corpus_v1/`.
**Next: Phase 2, M1-R2 DAPT implementation and training.**

## Agent Ownership

This agent owns **QGIS data processing only**: deterministic conversion of the
QGIS Processing corpus and low-level PyQGIS API corpus into auditable train-only
candidates. GEE processing and benchmark construction belong to separate
workspaces. This agent must not rewrite their conclusions, counts, gates, or next
actions; updates to this file should change only the QGIS entry and necessary
cross-workstream references.




## M3-P0 and M3-P1 complete: SFT aligns the L3 output space (2026-09-08)

M3-P0 (zero-shot post-trained Qwen3.5-9B, frozen protocol, val 49): 0/49 exact,
code P/R 0/0, length error −4.0 — the model answers GEE tasks in fluent
English steps (semantically right direction, e.g. "filterDate → select → mean")
but never emits L3 codes. Clean Qwen-prior floor. M3-P1 (same model, plain
QLoRA/SFT — NF4, r16 q/k/v/o, weighted CE, 1 epoch × 8,817 paper_v1 train rows,
83 min, 14.35 GB): the frozen-protocol pass read 0/49 exact with recall 0.885
and +3.71 length error, which diagnosed as a truncation artifact: with
EOS-aware decoding the prediction begins with the exact gold chain in **42/49
(85.7%)** and the first block matches exactly in **41/49 (83.7%)**; EOS is
generated 46/49. Failure taxonomy of the 8 misses: 6 wrong-first-operator or
order errors, 2 no-EOS repetition. Known next-round fix (one line, no
retraining): pass eos_token_id/stop strings to generate. Q2 answered for round
one: plain task SFT maps the model's GIS semantic prior onto the L3 output
space; the 0→41/49 delta is attributable to SFT alone (same model, prompt,
decode). Both experiments registered in the append-only experiment ledger
(M3-P0-v1, M3-P1-v1 with checkpoint SHA, data version, params, GPU time).
Evidence: `docs/reports/m3_p1_sft_v1/m3_p1_report_v1.md`.

## Qwen3.5-9B-Base E3 smoke + E4 overfit gate: PASSED (2026-09-08)

The ladder foundation is complete. Isolated `qwen35` env (torch 2.5.1+cu121 /
transformers 5.16.1 with the qwen3_5 class and pure-torch GatedDeltaNet
fallback / peft 0.20.0 / bnb 0.50.2; 2.2.2-era envs untouched). Both Qwen3.5-9B
variants downloaded as original HF safetensors (19.3 GB each, hf-mirror,
completed 04:57); ollama GGUF stays inference-only. **E3 smoke 9/9** on Base:
NF4 load 7.19 GB, forward/backward/accumulation finite, LoRA save/reload
byte-identical (32 lora_A tensors), generation OK, peak 18.13/23 GB. **E4
100-sample overfit gate PASSED**: 100 paper_v1 train rows (60 GEE + 40 QGIS),
40 epochs, first loss 0.788 → 0.0000, exact L3-chain probe 10/10, 28.6 min,
peak 12.74 GB — the stack demonstrably learns the task format. Next: ⑤ M3-P0
zero-shot (post-trained Qwen3.5-9B), ⑥ M3-P1, ⑦ M1 controlled rerun. Evidence:
`docs/reports/qwen35_base_a10_smoke_v1/`.
## Three model-experiment routes fixed (2026-09-07)

User corrected the Qwen3.5-9B assessment: the architecture is fine-tunable — the problem was only that the local ollama GGUF (Q4_K quantized) is not suitable for the Transformers + BitsAndBytes + PEFT/QLoRA pipeline. The correct path is downloading the original HF safetensors weights: `Qwen/Qwen3.5-9B-Base` (verified on HF, 4 safetensors shards, `Qwen3_5ForConditionalGeneration`) for M2/M2-C0 and `Qwen/Qwen3.5-9B` (the post-trained variant, same repo family) for M3/M3-P0, loading NF4 at train time via BitsAndBytes. Route definitions are now fixed in `task_plan.md` under "Model-experiment route definitions": M1 = in-house planning architecture route (keep V4.x, data governance → SFT → AR → optional DPO); M2 = Base-model domain-specialization route (Base → DAPT → task SFT → optional process/preference stages); M3 = mature post-trained model direct task adaptation (Qwen3.5-9B → QLoRA/SFT only, no DAPT). All three share the same output boundary (L3 semantic workflow → common L3→QGIS landing) for fair comparison. M2-C0 is M2's internal no-DAPT control; M3-P0 is M3's zero-shot floor. Open scoping decision pending: which M2 stages (DAPT→SFT→process supervision→preference/tool feedback) belong to the main experiment vs. follow-ups.
## A10 QLoRA smoke 9/9 passed; Qwen3.5-9B unusable as base (2026-09-07)

Stage ③ complete. **Critical finding: the local `qwen3.5:9b` ollama weight is a
hybrid SSM+attention multimodal architecture** (ssm_* state-space layers,
mtp.* multi-token-prediction head, v.blk.* vision tower) — transformers 4.57.5
has no `qwen35` class (verified fail), and supporting it means implementing the
SSM scan/MTP/vision stack from scratch. The experiment matrix's base model must
be replaced; candidates on disk: Qwen2.5-7B (validated), Qwen2.5-14B (needs NF4
memory check), or an HF download of Qwen3-8B.

The stack itself is proven on **Qwen2.5-7B** (`/data/llms/Qwen2.5/7b`): NF4
double-quant load 6.59 GB, forward/backward/grad-accumulation finite, LoRA
(r=16, q/k/v/o) save + reload byte-identical (112 lora_A tensors compared),
generation works. **Peak memory 12.86 / 23 GB.** Environment pinned: torch
2.2.2+cu121, transformers 4.57.5, peft 0.20.0, bitsandbytes 0.45.0 (wheel
transferred from local because the server mirror kept timing out). Evidence:
`docs/reports/qwen_a10_qlora_smoke_v1/` (per-step ledger, report, hash
ledger); script `scripts/qwen_a10_qlora_smoke.py`.

Next: user decides the base model, then ④ 100-sample overfit on paper_v1 rows
(data path and LoRA config already proven).

## paper_v1 supervision manifest v2 — GEE side corrected to the 8,283 authority (2026-09-07)

The user corrected a real error in the first paper_v1 build: the GEE side had
been taken from the superseded 76,884-row legacy baseline (old step1-8
pipeline). The current official GEE train-only authority is the 8,283-row
Batch12-merged cumulative package. That package was **recovered intact** from
the repo-root working file `.tmp_gee_cumulative_authority_v8_9_9_batch12_20260811.json`
— SHA256 exactly matches the recorded cumulative-authority hash
(`30dbfe5c…`), so it is the original file, not a regeneration. It is now
materialized with a recovery hash ledger at
`docs/reports/gee_train_only_authority_v8_9_9_8283/`; the option-B server
rebuild was stopped and cleaned after the discovery.

**paper_v1 v2 = 8,912 rows** (GEE 8,283 + QGIS 629): train 8,817 / val 49 /
test 46; source-disjoint verified independently (8,797 distinct source
identities, 0/0/0 overlap); zero empty task texts; both held-out splits carry
real multi-step supervision on both platforms (GEE val/test 37/35 multi-step,
QGIS val/test 5/4). L3 vocabulary: GEE 57 codes, QGIS 56, shared 25, QGIS-only
31. Weights: GEE 0.5×8,283; QGIS 1.0×172 / 0.8×24 / 0.7×430 / 0.6×3. The
invalid 77,513-row first build is fully superseded. Training rows 0; manifest
only. Evidence: `docs/reports/paper_v1_supervision/` (manifest, summary,
`manifest_report_v1.md`, hash ledger pinning the 8,283 input at `30dbfe5c…`).

## paper_v1 supervision manifest frozen (2026-09-07) — SUPERSEDED by v2 above

The model-experiment phase is open. `paper_v1` unifies GEE + QGIS into one
supervision ledger (108 MB, 77,513 rows: GEE 76,884 + QGIS 629) with a uniform
schema (record id, task text, platform, source identity + SHA, L3 chain,
operator chain or package reference, alignments, split, weight, evidence level)
and **source-disjoint train/val/test** assigned per source identity (77,398
distinct identities; independently re-verified 0/0/0 overlaps). Splits:
train 76,733 / val 391 / test 389; QGIS val 8 (6 multi-step, incl. 9- and
6-step chains) and test 3 (all multi-step, incl. one GOLD). Weights 1.0×77,056 /
0.8×24 / 0.7×430 / 0.6×3. L3 overlap: 18 shared codes between platforms, 38
QGIS-only. 17 GEE train rows have empty task text (inherited; kept in train).
A merge bug that dropped the 3 standalone task texts was caught during
manifest verification and fixed (pool rebuilt, hashes refreshed, tests 5/5).
Evidence: `docs/reports/paper_v1_supervision/` (manifest, summary,
`manifest_report_v1.md`, hash ledger pinning both inputs); script
`scripts/build_paper_v1_supervision_manifest.py` (rng seed 20260907).

Next per the user's roadmap: ③ Qwen3.5-9B A10 training smoke (NF4 QLoRA:
tokenizer/forward/backward/grad-accum/checkpoint save-reload/generation), ④
100-sample overfit, ⑤ M3-P0 zero-shot, ⑥ M3-P1, ⑦ M1 controlled rerun — all
consuming this one manifest; Benchmark Gate-3 supply refill runs in parallel
from QGIS source-backed data outside the 629 pool. No training row has been
emitted; no checkpoint exists.

## Official merged QGIS training pool v1: 629 rows (2026-09-07)

The final merge-level admission over the three audited sources — 506 audited
existing + 120 API-pattern candidates + 3 standalone — with all dedup layers
re-applied jointly (sample identity, source-SHA+span, L3-sequence+task-text).
**Result: 629 admitted, 0 cross-pool rejects** — the prior stages' cross-dedup
held exactly. Structure: single-step 367, **multi-step 262** (workflow
composition supervision, +84.5% over the old 142), 277 unique L3 sequences
(227 of them multi-step: 107 existing + 120 pattern, the pattern lane's entire
contribution sequence-unique), 617 unique task texts, length bands 1:367 /
2–3:138 / 4–7:89 / 8+:35, weights 1.0×172 / 0.8×24 / 0.7×430 / 0.6×3. V4 smoke
over the full pool: real dataset + real tokenizer, 20 batches, max content 55/100,
finite loss/gradients, no checkpoint/epoch. The pool is
`admitted_train_only_candidate_v1` — versioned and hash-bound, not a training
run; every row carries validation/test=false and production_merge=not_granted.
Evidence: `docs/reports/qgis_training_pool_merged_v1/` (`pool_report_v1.md`,
`qgis_training_pool_v1.jsonl`, summary, hash ledgers); script
`scripts/merge_qgis_training_pool_v1.py`.

Per the user's roadmap: next is the GEE-vs-QGIS distribution analysis and the
decision between a first GEE→QGIS adaptation training experiment (QGIS now has
500+ rows of which 260+ are true workflow supervision) and an AI reconstruction
round aimed specifically at the workflow-diversity gap (262 → ~500), not at a
raw row count.

## Existing QGIS training-pool audit: 508 → 52 GOLD / 454 SILVER / 2 REJECT (2026-09-07)

The user-ordered audit of the existing 508-row aggregate ran directly against
the pool ledger with no new mining. Every check is mechanical and complete (not
sampled): server-side source SHA re-verification **508/508** (0 missing/mismatch/
unreadable), span checks 453 verified + 55 no-span rows, L3 validity and
token-ID consistency **508/508** against the 128 taxonomy, task text ≥15 chars
508/508, QGIS platform (no `ee.*`) 508/508, real tokenizer gate **0 rejections**
(max 126), V4 smoke over the 506 non-reject rows (16 batches, max content 14/100,
finite loss/gradients, no checkpoint/epoch). Duplicates: 2 exact (L3 sequence +
task text) twins → REJECT. The 20 multi-step rows without `dependency_edges`
all carry `normalized_dag_key` + `call_graph_key` — dataflow proven at
admission, serialized as sequence (V4 does not consume edges); reclassified
`sequence_serialized_dag_verified`, not a defect.

**The pool is real: 506 structurally clean rows (52 GOLD weight 1.0, 454
SILVER weight 0.7/0.8/0.6).** Caveats: GOLD/SILVER inherit admission-time review
tiers — this audit re-verified structure, not human semantics (those reviews are
frozen in the source packages); 364/506 are single-step rows (operator-level
supervision; multi-step mass is 142); 406 rows share 55 distinct L3 sequences —
task-text diversity carries the supervision. Combined QGIS standing: audited
506 + 120 pattern candidates + 3 standalone + 56 proven operators = potential
629-row supervision ceiling if the 120 are admitted. The 2 REJECT rows are
flagged, not deleted. Evidence: `docs/reports/qgis_508_pool_audit_v1/`
(`audit_report_v1.md`, verdict/structural/source ledgers, hash ledger).

## API pattern 875-funnel FINAL: 120 training candidates (2026-09-07)

The full 875-funnel is closed. Final number: **875 → 120 training candidates**
(13.7% of signatures; 2.5% of the 4,880 instances), all passing the real
`bert-base-uncased` gate (max 119 tokens, mean 49.3, zero rejections) and the
real V4 data path (8 batches, max content length 55/100, finite loss and
gradients, sample weights emitted; no checkpoint, no epoch). Final-stage
attribution over the 142 qualified: task-text reject (no source context) 4;
internal L3-sequence dedup 8; 508-pool hits 10 (source SHA 4 / L3 sequence 6 /
task text 0). Task text provenance — nothing invented: docstrings 90,
task-bearing comments 11, domain-named class.function scope 19 (real plugin
algorithm classes like `JunctionBufferTrimAndExplode`). Distributions: length
mode 3 with a real tail to 55; L3 coverage Intersect 289 / Buffer 161 /
Reproject 150 / Feature to Point 131 / Collect 78 / Erase 49 / Repair 34 / Min
Bounding 7 / Simplify 5 / Smooth 1 / SymDiff 3.

**Reading (user's bands): 120 is in the 50–150 band** — API pattern has real
multi-step structure but insufficient task supervision to be a primary training
source alone; per the pre-agreed interpretation, AI-assisted reconstruction and
other lanes now enter the roadmap formally, while the lane's standing products
are the 120 verified candidates plus the frozen predicate/operator evidence.
The largest known unlock remains the 645 unproven transform steps (238 rows).
The 120 are candidates, not training rows: package consumption is a separate
user decision. Training rows 0; authority/evaluation/checkpoints unchanged.
Evidence: `docs/reports/qgis_api_pattern_production_final/`
(`final_report_v1.md`, `pattern_consumption_v1.jsonl` with stage reasons and
token counts, `qualified_context_v1.json`, hash ledgers); script
`scripts/consume_qgis_api_pattern_training_rows.py`; tests 6/6.

## API pattern L3 qualification: 875 → 142 QUALIFIED (2026-09-07)

Pattern-lane qualification ran over the 875 unique chain signatures using the
frozen `human_binding_review_2026_09_04` binding classes (reused unchanged) and
the user-approved **Predicate/Metric Step Policy v1**: a predicate enters the
sequence only when its result provably controls a later transform call
(`if`/`while` operand whose branch executes a chain call; 61 of the 142
qualified rows have such a control node, encoded with the existing Intersect
token); measurements never take a slot; 1,796 predicate steps are retained as
structural evidence on the rows. No new L3 codes; taxonomy untouched.

Funnel: of 875, L3 mapping complete 434 (unresolved 306 — 645 of 647 unresolved
steps are `transform:unproven_receiver`, the same name-bound receiver wall as
the standalone lane; deferred actions 135 rows / 451 steps). QUALIFIED
**142** = complete mapping + ≥2 transform steps + domain-named owner. DEFERRED
733: owner 292, policy-insufficient transforms 127, unresolved 238, deferred
actions 76. Qualified chains span 11 L3 classes (Intersect 298, Buffer 177,
Reproject 168, Feature to Point 141, Collect 90, Erase 52, Repair 37, Min
Bounding 8, Simplify 5, SymDiff 3, Smooth 1), length 2–55 with no dominant
duplicate L3 sequence — chain diversity survived qualification. Training rows 0;
tokenizer/V4 not yet run; authority unchanged. Note: the census ledger lacked
`source_path`; the qualification input was joined by record_id to the v2
normalized ledger server-side before the run. Evidence:
`docs/reports/qgis_api_pattern_qualification_v1/` (ledger, summary, hash
ledgers, `qualification_report_v1.md`); script
`scripts/qualify_qgis_api_pattern_chains.py`; tests 9/9.

Next: cross-pool dedup of the 142 vs the 508 pool, then task text/tokenizer/V4.
Optional unlocks (user decision): dominating-assignment proof for the 645
unproven transform steps (238 rows), and an owner-policy adjudication for the
292 plain-scope complete chains.

## API pattern multi-step census: 4,880 → 875 (2026-09-04)

First pass over the 4,880 `api_pattern` rows measuring compression structure
only — no L3 mapping, no task text, no admission. Stage table: 0 source
failures; FAIL_CLOSED 45 (foreign receiver/keyword); structure invalid 2,742
(no QGIS-proven receiver 813, no dataflow linkage 731, predicate/measurement-
dominated 1,198); **2,093 structurally valid multi-step chains**, deduped by
chain signature to **875 unique signatures** (2.4:1). All 875 have verified
producer→consumer linkage. Task owners: `domain_named` 322 (all with unique
signatures and real multi-operation shapes like
`makevalid|intersects|buffer|unaryunion|intersection|transform`), `plain_scope`
505, `module_level` 25, `generic_verb` 23. Chain-length mode is 3–8 steps with a
tail to 102 — not two-call fragments; the largest signature is
`transform|transform` (257→1). Predicate contamination is high (531/875 carry
predicates; only 259 are pure transform chains).

Reading: instance count (4,880) was never the supervision number — 875
signatures is, and the task-qualified training ceiling starts near the 322
domain-named rows before predicate filtering, per-source review, 508-pool
cross-dedup, and tokenizer/V4 gates. The move to multi-step structure is
confirmed; the standalone lane stays sealed at its 3 candidates. Training rows
0; authority unchanged. Evidence: `docs/reports/qgis_api_pattern_census_v1/`
(`pattern_census_v1.jsonl` with per-row stage reasons, `census_report_v1.md`,
hash ledgers); script `scripts/census_qgis_api_pattern_chains.py`; tests 9/9.

## API semantic standalone consumption: 137 → 3 (2026-09-04)

The yield pipeline over the 137 adjudicated standalone rows completed with no new
parsing. **Result: 3 training candidates** (Reproject 1, Intersect 1, Simplify 1),
after 1 existing-pool SHA hit, 66 internal payload duplicates (99 of 137 rows
share identical call text; 39 signatures cover all 137), and 67 rows without
independent task context (55 module-level snippets with no task owner, 12
no-observable-semantics helpers). The 3 survivors all passed on
`domain_named_scope` (e.g. `AddMultipleTreesTool.get_line_segment`), passed the
real `bert-base-uncased` gate (max 35 tokens), and passed the real
`TaskConditionedL3DatasetV4` + weighted-CE + backward smoke (loss/gradients
finite, no checkpoint, no epoch). They are candidates only — consumption into a
training package needs an explicit user decision.

**Lane conclusion:** the API semantic *unit* lane contributes operator-semantic
knowledge (998 qualified action bindings; 861 grounding-grade), not workflow
training data. Single geometry calls without task context are not user workflows,
and per the locked principle different sources were not dressed up as different
tasks. The next API-side yield increment must come from multi-step structure:
`api_pattern` (4,880) and the workflow lanes. Evidence:
`docs/reports/qgis_api_semantic_production_v2/consumption/`
(`consumption_report_v1.md`, `standalone_collapse_v1.jsonl`,
`training_candidates_v1.json`, hash ledgers); script
`scripts/collapse_qgis_api_standalone_candidates.py`; tests 10/10.

## QGIS API semantic production v2 — L3 qualification adjudicated (2026-09-04)

The human binding review (`human_binding_review_2026_09_04`) is applied and
materialized as a ledger: **QUALIFIED 998 / DEFERRED 59 / FAIL_CLOSED 1** over the
1,058 proof rows. Approved as classes: `native_operator_slug_equivalence` 387,
`transform_crs_receiver` 558 (+1 promoted geometry transform with an inline
`QgsCoordinateTransform` argument), `taxonomy_class_equivalence` 52 — per-row
evidence retained. `interpolate` 40 / `offsetcurve` 3 / `splitgeometry` 2 stay
DEFERRED (`action_deferred_by_adjudication`); geometry-flavored `transform` split
1 QUALIFIED / 14 DEFERRED (`transform_argument_not_yet_proven`, recoverable later
via dominating-assignment proof on the argument) / 1 FAIL_CLOSED (numeric
`transform(float(x), float(y))`). The ledger resolved the arithmetic caution: the
16 transforms were inside the 61 unresolved, outside the 997 proposals, hence 998.

Consumption routing (QUALIFIED only): **137 standalone rows → workflow-training
candidate pool** (Reproject 65, Feature to Point 25, Buffer 21, Simplify 8,
Intersect 7, Smooth 5, Collect 4, Repair 1, Minimum Bounding 1), still downstream
of normalized-sequence/dedup/context/tokenizer/stable124 gates — training-eligible
≠ training row; **861 intermediate rows → operator-grounding corpus**. Training
rows 0; authority/evaluation/checkpoints unchanged. Evidence:
`docs/reports/qgis_api_semantic_production_v2/phase2_adjudicated/`
(`adjudication_v1.jsonl`, summary, hash ledgers, `adjudication_report_v1.md`);
script `scripts/adjudicate_qgis_api_semantic_l3.py` (adjudication text frozen
inside); tests 6/6.

The lane KPI is now: **how many independent QGIS training rows the 137 standalone
candidates yield** (sequence construction → cross-source dedup → independent
workflow/task context → tokenizer → stable124/V4), not further parsing volume.

## QGIS API semantic production v2 — phase 2 complete (2026-09-04)

Phase 2 (L3 proof over the 1,058 candidates) is done. It binds each semantic
action to an L3 class **with recorded mapping evidence** and splits standalone
operations from implementation steps, but emits **proposals only**: every row is
`DEFERRED / awaiting_independent_binding_review`, because the binding review is
the QUALIFIED gate and is a separate authorized pass. `qualified_rows = 0` by
construction.

Mapping evidence per row — never method-name-only:
`transform_crs_receiver` 558 (`QgsCoordinateTransform.transform` is reprojection
by type contract), `native_operator_slug_equivalence` 387 (PyQGIS engine of the
same-named Processing operator whose L3 is already fixed in
`composed_stable124`), `taxonomy_class_equivalence` 52 (`convexhull` →
L3_02_05_12 as an enumerated hull variant; `combine` → L3_02_03_05 Collect
Features), `unresolved_action` 61 (`interpolate` 40, `offsetcurve` 3,
`splitgeometry` 2, geometry-flavored `transform` 16 — no binding proposed until
each is separately decided).

Result: **997/1,058 carry an L3 proposal across 11 distinct classes** (Reproject
558, Feature to Point 174, Buffer 92, Intersect 57, Minimum Bounding 33,
Simplify 28, Repair Geometry 24, Collect Features 19, Smooth 10, Erase 1,
Symmetrical Difference 1). Standalone split: **137 standalone-operation rows**
(result returned to caller 62 / module-level 75) — the only rows a
workflow-training line could consume, composed of Reproject 65, Feature to
Point 25, Buffer 21, Simplify 8, Intersect 7, Smooth 5, Collect 4, Repair 1,
Minimum Bounding 1 — versus **860 intermediate-implementation rows** whose
result never leaves the enclosing function (operator-semantic knowledge, not
workflow steps). Training rows 0; authority/evaluation/checkpoints unchanged.
Evidence: `docs/reports/qgis_api_semantic_production_v2/phase2/` (`l3_proof_v1.jsonl`,
summary, hash ledgers, `phase2_report_v1.md`); script
`scripts/prove_qgis_api_semantic_l3.py`; tests 9/9.

Next: the independent binding review (one decision per mapping class:
slug-equivalence table, CRS-receiver rule, hull/combine equivalences, plus
verdicts for `interpolate`/`offsetcurve`/`splitgeometry`/geometry-`transform`)
is the QUALIFIED gate; after it, the 137 standalone rows become this lane's
first training-eligible pool pending downstream gates, and the 860 intermediate
rows feed the operator-grounding corpus.

## QGIS API semantic production v2 — phase 1 complete (2026-09-04)

The API semantic lane is open. Phase 1 (source fact extraction + semantic
qualification) ran over the 3,209 confirmed `api_semantic_unit` rows of the v2
normalized ledger (hash-pinned input `a13ce1a2…`), with L3 mapping explicitly
**not attempted** — only `DEFERRED`/`FAIL_CLOSED` are reachable; `QUALIFIED`
requires the phase-2 L3 proof layer. Result:

- **1,058 candidate geometry semantics** (33%): receiver proven QGIS,
  geometry-transform role, result retained. Composition: **558
  `QgsCoordinateTransform.transform` (reproject semantics)**, 484 classic
  geometry transforms (centroid 174, buffer 92, intersection 57, interpolate 40,
  convexhull 33, simplify 28, makevalid 24, combine 19, smooth 10, offsetcurve 3,
  splitgeometry 2, symdifference 1, difference 1), 16 geometry-flavored
  `transform`. 1,058 unique source SHAs; only 26 non-transform candidates have
  all-literal argument values.
- **1,168 ambiguous receivers**: the receiver's QGIS type is not provable from the
  file alone — the measured size of the "semantics hidden in implementation"
  problem and the concrete phase-3 capability decision (inter-procedural type
  recovery), not a rule tweak.
- **889 predicates/measurements/discarded results** (527 scalar-returning, 362
  unused): honest knowledge, not workflow steps.
- **94 foreign libraries fail closed** (osgeo 33, pyproj 23, shapely 18, sklearn 8,
  geopandas 5+4, others 3).

Method-name matching required receiver proof because the same names exist in
shapely/geopandas/pyproj/sklearn; two hardening rules were added from inspecting
the first run and are regression-tested: foreign-only keyword arguments
(`cap_style` etc.) fail closed, and a bare `.geometry` attribute (GeoDataFrame
idiom) is not a QGIS receiver while `.geometry()` calls are. Every row keeps the
full fact record (`call_span`, `call_text`, receiver binding evidence,
`argument_facts`, `return_target`, `enclosing_scope`, `semantic_action` as
role:method, never an L3 code), so later phases never reparse source. Verdicts:
DEFERRED 3,115 / FAIL_CLOSED 94 / QUALIFIED 0. Training rows 0. Evidence:
`docs/reports/qgis_api_semantic_production_v2/` (ledger, summary, hash ledgers,
`phase1_report_v1.md`).

## Asset Miner / normalization v2 rebuild (2026-09-04)

The asset ledger was rebuilt as **v2** (not a v1 restore) after the server-side v1
tree was deleted; no v1 directory was overwritten. Inputs came from local
manifests (8,466 Processing + 39,386 API = 47,852) plus the intact read-only
`/home/yll`. v2 parses **47,852/47,852 with zero unresolved sources**, versus v1's
47,542/310. Two source roots had been renamed on disk after the manifests froze
(`model_tutorial` → `…/downloaded_scripts(QGIS_Model_Tutorial_Workflows)`,
`pwc_qgis` → `…/downloaded_scripts-PWC`), accounting for exactly 301 + 9 = 310
rows; both substitutions were SHA-verified against the manifest before use.

v2 pools: `unresolved` 23,650 (−295), `api_implementation_evidence` 12,410 (+3),
`api_pattern` **4,880** (0), `api_semantic_unit` **3,209** (0),
`processing_workflow` 1,337 (+101), `processing_implementation` 1,266 (+178),
`processing_operator` 595 (+4), `processing_dynamic_candidate` 505 (+9). Every
delta traces to the 310 recovered sources; no row moved between pools, and the
3,209/4,880 match was measured, not enforced.

Census gate passed: 47,852 unique source SHA and record IDs, duplicate SHA rows 0,
`unique_operator_sequences` 1,411 and `unique_semantic_sequences` 1,729 unchanged.
Definition confirmed against evidence: **`api_semantic_unit` = exactly one API
semantic call** (3,209/3,209, zero Processing calls); `api_pattern` = two or more
(2–102). This is the normalizer's definition and deliberately not the miner's
label — 2,242 of the semantic units came from miner `api_pattern_candidate` rows.
It is neither a boundary-unit nor a composite macro.

The operator pool is 595 rows but still **207 unique operator IDs**: the 4 new
rows carry `omm:*` third-party operators already `FAIL_CLOSED`, so the sealed
56/44/107 qualification is unaffected and stays bound to its own frozen 591-row
v7 sidecar input.

Preservation gate now mandatory: `preservation_ledger_v1.json` binds input
manifest hashes and row counts, all script hashes, the git commit, and every
output hash with its second-copy location. The 83 MB normalized ledger is
mirrored in-repo and hash-verified after transfer (`a13ce1a2…`); the 66 MB merged
miner ledger and 479-shard tree remain server-side and are regenerable.

Historical API artifacts stay **reference lineage only** and are not merged:
`qgis_api_boundary_v6_post_filter_v1` (2,707 intake units),
`qgis_api_l3_mapping_census_v1` (2,632 rows, 2,605 `mutation_export_only`),
`qgis_api_composite_macro_census_v1` (10,800 discovery units). The 2026-08
mutation/export closure is not reopened. Asset Miner v2 is the canonical API asset
source. Training rows 0; authority, evaluation, and checkpoints unchanged.
Evidence: `docs/reports/qgis_asset_normalization_full_v2/` and
`docs/reports/qgis_asset_miner_full_v2/`.

## Latest QGIS family collapse audit (2026-09-03)

The read-only `normalized-DAG` collapse audit covered all 107 rows in the
combined family admission ledger. It found two duplicate groups: dissolve /
multipart-to-singleparts (73 rows, 31 source SHAs, 21 semantic parameter
signatures, 34 parent structures) and buffer / clip (34 rows, 24 source SHAs,
10 semantic parameter signatures, 18 parent structures). Task text, L3, vector
I/O, and normalized DAG are identical within each group; source-backed parameter
and parent-structure variation is present in both. This is a potential
over-merge signal for future parameter-aware assets, not sufficient evidence to
change the current task-to-L3 workflow dedup key. Dedup is unchanged, Gold=0,
training rows=0, and the two survivors remain candidate-only Silver.
Evidence: `docs/reports/qgis_normalized_dag_collapse_audit_v1/`.

## QGIS parameter and parent asset pool v1 (2026-09-03)

The collapse evidence is now materialized as a separate candidate-only pool:
31 processing parameter-signature assets, 52 parent-structure assets, and four
operator observations from 107 source-backed rows. Every asset retains source
SHA, family, normalized-DAG provenance, and zero training admission. This pool
does not relax workflow dedup and does not modify L3 authority, evaluation
splits, production profiles, or checkpoints. Evidence:
`docs/reports/qgis_family_parameter_asset_pool_v1/`.

## Processing operator asset lane (2026-09-03)

The server full-pool census is complete using the normalized Asset Miner ledger:
47,852 input rows contain exactly 591 `processing_operator` asset rows, which
aggregate to 207 unique operator IDs backed by 591 unique source SHA values.
All 591 rows have processing-call evidence and the expected-row check is
`matched`. The normalized v1 schema does not carry parameter dictionaries or
provider I/O contracts, so both are reported as
`not_carried_by_normalized_ledger`, not as failed qualification. L3 mapping,
training admission, authority, and checkpoints remain closed. Evidence:
`docs/reports/qgis_processing_operator_assets_full_v3/`.

The independent evidence sidecar is now at v7 after a repaired binding rule. On the
same frozen input it source-verifies all 591 rows and recovers 591 AST calls:
**511** calls have static parameter dictionaries, 438 expose static INPUT/OUTPUT
keys, 504 have I/O evidence including positional `runalg`, 589 have provider-prefix
evidence, and 12 remain deferred. v6 labelled a by-name parameter dictionary
`name_to_static_assignment` using a module-wide `{name: last assignment}` walk, which
proved nothing about scope, order, dominance, or mutation; it attributed another
call's payload to 4 `qgis:joinattributesbylocation` rows and wrongly deferred 6
provable ones. Rule `dominating_same_scope_static_dict_v2` now requires a single
dominating same-scope assignment, no rebinding or dict mutation before the call span,
and a static dict, and records `assignment_lineno`/`assignment_span`/
`dominance_verified`/`mutation_guard` for all 224 accepted bindings (224/224 on every
provenance field). Parameter completeness is reported for the first time:
`static_parameter_complete=50`, `static_parameter_partial=529`,
`parameter_unresolved=12`. The sidecar remains evidence-only; L3 mapping,
qualification, authority, and training are closed. Evidence:
`docs/reports/qgis_processing_operator_evidence_sidecar_full_v7/` (including
`regression_v6_to_v7_v1.md`); v6 is superseded.

Operator-pool L3 qualification is complete with a three-state verdict
(`QUALIFIED` / `DEFERRED` / `FAIL_CLOSED`, no interim states). Of the 207 unique
operator IDs: **56 QUALIFIED** (15 exact `composed_stable124` mappings with 39
support rows + 41 `qgis:<slug>`→`native:<same slug>` operators with 241 rows,
every row independently alias-proven by source reread, SHA re-verification, and
span-exact literal relocation across all three entrypoints; the 198-row
`processing.run` subset agrees 198/198 with the existing precedent verifier),
covering **37 distinct L3 codes**; **44 DEFERRED** (36 catalog providers without
a mapping, including `native:rastercalc` and `qgis:filedownloader`, kept as
minimal-extension observation candidates; 8 no-precedent alias shapes — 7
`gdalogr:`→`gdal:` and 1 `sagang:`→`saga:`); **107 FAIL_CLOSED** third-party
plugin providers (210 rows). 56 is the operator-level ceiling under current
authority, not a promise of 280 training rows; parameter/IO evidence is recorded
as coverage without gating. Training rows 0; L3 grants, authority, evaluation,
and checkpoints unchanged. Evidence:
`docs/reports/qgis_processing_operator_qualification_v1/` (ledger, alias proofs,
precedent cross-check, and `semantic_qualification_report_v1.md`).

Infrastructure note (2026-09-04): the entire server-side
`/home/qy/system_redesign/diagnostics/` tree was deleted outside this session
(~450G freed on `/`, ~590G on `/data`), including the server copies of the
operator-asset census, the frozen normalized ledger input (`45a1c12d…`), and all
GEE batch evidence. `/home/yll` is intact. The operator lane's authoritative
chain now lives in this repository (v7 sidecar ledger + qualification ledger);
the qualification rebuilt the operator aggregation from the local v7 sidecar and
matched the frozen census exactly (207/591/591). The normalized ledger is
regenerable from `/home/yll` via `scripts/mine_qgis_assets.py` +
`scripts/normalize_qgis_assets.py` if ever needed; that regeneration has not
been run.

## Processing family calibration status (2026-09-02, superseded v1)

The first high-support family packet, `native:dissolve ->
native:multiparttosingleparts`, is source-disjoint by SHA (40 sources; 20
calibration and 20 holdout; 86 occurrences total). The first audit passed 70
occurrences and deferred 16 for an explicit cross-variable/list-loop dataflow
rule gap; there were zero semantic or structural failures and zero SHA overlap.
The audit remains candidate-only: no L3, task, I/O, dedup, Gold/Silver,
training, authority, or evaluation admission has been granted. The dependency
auditor now recognizes bounded `append`/`extend`/`insert` result sinks and
`for item in container` propagation, with regression coverage; arbitrary
mutation and runtime aliasing remain deferred. Evidence:
`docs/reports/qgis_family_calibration_audit_dissolve_multipart_v1.md`.

This historical v1 paragraph is superseded by the server v2 rerun below.

## Processing family calibration rerun (2026-09-02)

The frozen 86-occurrence `native:dissolve -> native:multiparttosingleparts`
packet was replayed without regeneration using the bounded container/loop rule:
73 passed, 13 remained deferred, and 0 failed. All 86 source SHAs were
verified; calibration/holdout overlap remained zero. Three dependency-only rows
were recovered (two calibration, one holdout). This remains candidate-only;
L3, task, I/O, dedup, Gold/Silver, training, authority, and evaluation are
closed. Independently qualify the 73 passed rows and explicitly resolve or
bound the remaining 13 before promotion or batch expansion. Evidence:
`docs/reports/qgis_family_calibration_audit_dissolve_multipart_v2.md`.

The 73 passed dissolve/multipart rows completed qualification preflight: 73/73
existing-authority L3 proposals and 73/73 deterministic vector I/O contracts;
task fidelity and cross-pool dedup remain pending. In parallel,
`native:buffer -> native:clip` was calibrated from 54 occurrences / 36 sources /
19 structures: 34 passed, 20 dependency-only deferred, 0 failed, SHA overlap 0.
Both lanes remain candidate-only. Evidence:
`docs/reports/qgis_family_qualification_dissolve_multipart_v1.md` and
`docs/reports/qgis_family_calibration_buffer_clip_v1.md`.

Independent source-fact review packets are now frozen for both lanes: 73
dissolve/multipart rows (31 unique source SHAs) and 34 buffer/clip rows (24
unique source SHAs). Each packet embeds verified source text and an explicit
gold/silver/reject review contract; decisions and training rows remain zero.
Evidence:
`docs/reports/qgis_family_semantic_review_dissolve_multipart_v1.md` and
`docs/reports/qgis_family_semantic_review_buffer_clip_v1.md`.

The deterministic source-fact review and combined four-layer admission pass is
complete: 107/107 rows passed the frozen AST facts, L3, vector I/O, and family
task-vocabulary checks. Dedup retained 2 normalized-DAG-unique Silver
candidates (one per family) and suppressed 105 duplicates. Gold=0 and
training rows=0; the two survivors still need independent intent adjudication.
Dashboard: `docs/reports/qgis_asset_production_dashboard_v1/dashboard_v1.md`.

## Raw-source LLM extraction pilot (2026-08-11)

The prior boundary v3 pilot sent bounded source windows plus pre-extracted AST
steps; it did not test raw-source operator extraction. The isolated raw route is
now prepared: one complete Python source file per request, a catalog shortlist,
and operator candidates with source line evidence only. The local validator now
allows candidates absent from the deterministic extractor and labels them
`locally_confirmed` or `call_site_only`. No L3, training, or authority admission
is granted.

The first server pilot is complete: 10 Processing + 10 API, 20 unique SHAs. API
known AST facts were recovered 6/8 (0.750 recall, 1.0 precision among verified
known facts). All five Processing gold sources had empty/non-JSON responses; a
five-source retry recovered one partial response with an incompatible extra
candidate and remained fail-closed. `call_site_only` (LLM-only) candidates=0,
training rows=0. This proves the raw request/local validation chain runs, but
does not prove recovery beyond the deterministic extractor. Keep isolated and
candidate-only; do not expand or merge. Report:
`docs/reports/qgis_llm_raw_operator_extraction_pilot_v1/report_v1.md`.

## Workflow Gold/Silver Pilot (2026-08-12)

The 455 Processing workflow-tier candidates are not a workflow corpus, but
they have now produced a bounded output pilot. Corrected structural replay
results are 70 candidates, 161 boundary deferrals, 36 extractor-unsupported,
80 mapping deferrals, and 108 operator-resolution deferrals. Deterministic
description fidelity passed for 69/70. Dual-baseline (294 Processing + 508
all-QGIS) four-layer dedup classified 21 rows as **Silver** and 49 as Reject.
The frozen independent full-source semantic review then classified those 21 as
**15 Gold, 4 retained Silver, and 2 revoked**. The two revoked rows are excluded
from the curated package: one has a Boolean raster-expression L3 mismatch and
one has a conflicting vector/raster output contract.

The original isolated package has 21 unique source SHA rows and remains
immutable. A separate curated package has 19 reviewed train-only rows: 15 Gold
(weight 1.0) and 4 retained Silver (weight 0.7). It cannot enter validation/test,
benchmark, production authority, or a checkpoint-producing run. Four overlong
descriptions were deterministically compacted from ordered source-verified
operator chains. A real cached `bert-base-uncased` gate then passed 21/21
without truncation (max 122), and the real `TaskConditionedL3DatasetV4` plus
`weighted_sequence_cross_entropy` covered 21/21 rows with finite loss and
gradients. The stable124 (max token 118) runtime adapter is smoke-only and
does not change the production 94/107 profile. Evidence:
`docs/reports/qgis_workflow_admission_v2_structural_replay_v1/report_v2.md` and
`docs/reports/qgis_workflow_admission_v2_structural_replay_v1/silver_semantic_review_decision_v1/`.

## `runalg` Entry-Point Calibration Freeze (2026-08-16)

The first unsupported Processing family is now frozen as legacy
`processing.runalg`, not yet supported by the production extractor. A
read-only server census over all 8,466 Processing authorities found 201
readable `runalg` sources (927 calls): 775 literal calls, 152 dynamic/blank
calls, and 189 non-authority literal-source rows. Normalized-body dedup left
148 authorities and deterministically froze 30 calibration + 30 holdout rows
with zero source-SHA and body-hash overlap. The 295 absent source files remain
fail-closed; no training rows were produced. `runalg` is predominantly a
positional legacy API (918/927 calls), so it cannot be added as a synonym for
dictionary-based `processing.run`.

The isolated adapter passed calibration (30/30 independent structural audit)
but failed its source-disjoint holdout (26/30): three sources mix literal and
dynamic calls, and one requires a positional static-output-path proof rule.
`runalg` is therefore **not promoted**. The 26 matching holdout rows remain
candidate-only and cannot enter any training path. The family is now **frozen
and deprioritized**: do not open a strict-profile follow-up unless a later
corpus-yield decision explicitly re-prioritizes it. Do not touch the production
extractor, merge authority, run model training, write checkpoints, or lower
operator/boundary/L3 constraints. Evidence:
`docs/reports/qgis_runalg_adapter_calibration_v1/report_v1.md`.

## Workflow-corpus expansion policy (2026-08-16)

The primary QGIS KPI is now the cumulative number of usable, source-grounded
Gold/Silver workflows, not additional gate-pass counts. The reviewed 19-row
Processing package is the seed workflow corpus. Existing PyQGIS local-macro
packages, including the nine `route1` rows, remain a separate operator-semantic
knowledge asset; they must not be relabelled as user workflows merely to raise
the corpus count.

The next bounded production lane is a synthetic-workflow **candidate** design
based on the seed corpus, L3 operator semantics, and explicit I/O/transition
constraints. Every candidate must carry its seed provenance and constraint
profile, be grouped by `parent_source_sha256` in every future split, remain
train-only and evaluation-ineligible, and undergo an
independent semantic review before Gold/Silver admission. It must not be
generated by arbitrary operator concatenation. Cross-platform operator
semantics remain a separate corpus, not a direct workflow-count multiplier.
No model training or checkpoint is authorized by this policy.

The first intake has completed: six multistep seeds yielded 31 source-derived,
catalog-I/O-compatible subworkflow candidates; 13 single-step seeds were
excluded. The review packet restricts decisions to `independent_workflow`,
`implementation_subworkflow`, or `duplicate_or_parent_contained`, and enforces
parent-group split lineage. Report:
`docs/reports/qgis_seed_subworkflow_candidate_intake_v1/semantic_review_packet_v1/`.

The cumulative expansion KPI is updated: 52 in-scope candidate rows, 20 Gold,
eight Silver, and 24 Reject. The curated train-only corpus now has 28 rows;
formal authority and evaluation splits are unchanged. Report:
`docs/reports/qgis_workflow_corpus_kpi_v1/`.

The 31-way semantic review is complete: 11 `independent_workflow`, 17
`implementation_subworkflow`, and three `duplicate_or_parent_contained`. The
11 independent rows received source-fact task-fidelity review: five Gold, four
Silver, and two exact-parent duplicates rejected. The 28-row combined package
passed real V4 data-path smoke (BERT-128 no truncation, correct weights, finite
forward/loss/backward/gradients); no training or checkpoint was written. Report:
`docs/reports/qgis_seed_subworkflow_candidate_intake_v1/semantic_review_packet_v1/task_fidelity_review_v1/`.

## Stable124 augmentation experiment profile (2026-09-02)

The isolated `stable124_experimental` profile is now materialized under
`docs/reports/qgis_stable124_experiment_profile_v1/`. It contains a baseline copy
of the 76,884-row mainline package and a 76,912-row copy with all 28 curated QGIS
rows appended to train only. Validation/test indices are byte-identical between
the two packages; the 124x256 embedding keeps the original 94 rows unchanged and
uses deterministic seed `124256` for the 30 appended rows. The profile activates
with `GIS_VOCAB_PROFILE=stable124_experimental` and reports model vocab size 128.
Both baseline and +28 training-entry dry-runs pass preflight; no model training or
checkpoint has been run. Production `v2_94_stable`, `outputs_v2`, authority,
validation/test, and benchmark remain unchanged.
An exact census of the actual baseline rows shows all 76,884 `operator_sequence`
values are exclusively `ee.*` (GEE-only); QGIS appears only in the appended 28.
The experiment task vocabulary is 49 types (47 baseline + 2 explicit QGIS types).
Composition evidence: `baseline_composition_v1.json`.

## Data-role definition (2026-09-02)

The project objective is QGIS-oriented workflow generation, not a platform-balanced
GEE/QGIS generator. GEE supplies scalable workflow supervision for learning
general GIS composition patterns; QGIS supplies target-platform operator semantics,
vector-processing behavior, I/O transitions, and QGIS-specific composition. L3 is
the shared algorithm-semantic representation between these sources. QGIS corpus
targets are therefore coverage-driven (operator, L3, vector, transition, I/O,
length, and task-semantic coverage), not a numeric parity target with GEE. The
verified 76,884-row baseline is GEE-only; historical figures such as 8,283 must
be labeled as a subset and not used as the baseline total without a source ledger.

## QGIS data-production acceleration (2026-09-02)

The active objective is production yield: rapidly increasing source-traceable,
train-only QGIS rows without weakening structural, I/O, mapping, or semantic hard
constraints. First scan the 23,638 raw `unclassified` sources with deterministic
high-recall signatures for real Processing/API calls, wrappers, and local workflows;
then recover bounded workflows/subworkflows, maintain a separate single-operator
grounding corpus, and only later expand implementation/API families. Existing
verified QGIS assets remain the baseline and dedup reference. Unconstrained LLM
structural extraction is not the production path.

Every batch must emit a manifest-backed census, provenance and parent lineage,
four-layer deduplication, and a Gold/Silver/Reject/Deferred ledger. Track accepted
rows, review cost, unique sources/parents, family concentration, and coverage gain.
The near-term goal is a repeatable batch process with measured yield improvement,
not a fixed 2,000-row claim. Training remains downstream of this loop.

## Asset semantic normalization v1 (2026-09-02)

The next semantic-preparation layer is implemented as
`scripts/normalize_qgis_assets.py`. It consumes the candidate-only Asset Miner
ledger and emits typed, provenance-preserving assets with explicit operation
hints, source/parent lineage, four deduplication keys, and next-gate routing.
Operation hints are lexical semantic labels only, not L3 mappings. The script
emits zero training rows and cannot change authority, validation, test, or
production state. Focused normalizer/miner tests pass 7/7. A server run now
covers the full ledger: 1,236 Processing workflows, 1,088 implementations,
591 operators, 496 dynamic candidates, 3,209 API semantic units, 4,880 API
patterns, 12,407 implementation-evidence rows, and 23,945 unresolved rows;
47,542 rows are SHA-verified. Report:
`docs/reports/qgis_asset_normalization_full_v1.md`.

The first bounded family packet is now generated for
`native:clip|qgis:multiparttosingleparts` (7 Processing workflow candidates):
3 calibration and 4 holdout rows, seven verified source SHAs, and zero
calibration/holdout source overlap. It remains candidate-only with no L3,
training, authority, or evaluation admission. Report:
`docs/reports/qgis_asset_family_review_clip_multipart_v1.md`.

Deterministic semantic calibration is complete: 7/7 rows pass SHA, AST literal
ID/order, parameter, and inter-call alias-dependency checks; 0 failures/deferred,
zero calibration/holdout SHA overlap, and seven distinct normalized templates.
This validates the recovery rule only; task fidelity, provider/I/O, L3,
cross-pool dedup, and Gold/Silver gates remain closed. Report:
`docs/reports/qgis_asset_family_semantic_audit_clip_multipart_v1.md`.

The calibrated rule was applied to the full normalized Processing workflow
population: all 1,236 `processing_workflow` candidates yielded 7 matching
parents and 7 family candidates, with one distinct full parent sequence and no
multiple matched spans. Qualification preflight resolves an existing L3
proposal and deterministic vector I/O contract for 7/7, while task fidelity
and cross-pool dedup remain pending. Reports:
`docs/reports/qgis_family_expansion_clip_multipart_v1.md` and
`docs/reports/qgis_family_qualification_clip_multipart_v1.md`.

The first full Processing family census is complete: 8,330 family records from
all 1,236 workflow candidates (exact=363, 2-step=2,427, 3-step=3,113,
transition=2,427; support >=2). Priority scheduling now recommends
`native:dissolve -> native:multiparttosingleparts` (support 86, 40 sources, 18
parent structures, fully pre-resolvable L3/I/O), followed by
`native:buffer -> native:clip` (support 54, 36 sources, 19 structures). The
previous clip/multipart family remains a calibration baseline (support 7).
Task/template metrics are explicitly unavailable until semantic review. Report:
`docs/reports/qgis_processing_family_census_full_v1.md`.

## Raw-source 13-candidate review (2026-09-02)

The 13 structural candidates were reviewed directly against `/home/yll` raw sources with SHA binding. `d8d9…` (DEMProcessing) is a real raster implementation candidate: `classify` contains the two-step `calc_stats → grass7:r.reclass` dependency chain, while `export_uniques` is independent. `bb18…` (CSV Tools) is plugin implementation/subworkflow evidence only. Three dynamic calls are deferred, four generic wrappers/CLI runners are rejected, one detector false positive is rejected, and three other implementations remain deferred for recovery. Training rows remain 0 and production merge is not granted. See `docs/reports/qgis_raw_unclassified_pilot_v1/review_v2/`.

The `d8d9…` candidate record now materializes source spans, dependency/I-O evidence, provisional L3 mappings, task text, and dedup keys. `bb18…` is materialized separately as implementation evidence and is excluded from complete-workflow counts; both remain gated on independent semantic review and downstream gates.

The `d8d9…` gate review is complete: candidate-level semantics are coherent; strict L3 remains deferred (statistics pending, GRASS provider binding pending); no exact operator-sequence duplicate was observed locally, but full cross-pool four-layer dedup remains deferred; real local `bert-base-uncased` 128-token smoke passed at 40 tokens without truncation. Final status remains `deferred_candidate_only`.

`scripts/mine_qgis_assets.py` (Asset Miner v1) now emits a unified candidate-only inventory for Processing workflow/implementation/operator, dynamic recovery, API semantic-unit/pattern, plumbing, and unresolved assets. A server pilot of 100 rows per pool parsed 194/200 rows; training rows remain 0. Summary: `docs/reports/qgis_asset_miner_pilot_v1.md`.

A direct full-pool run exceeded 10 minutes without incremental output because of per-row path resolution; it was stopped and is not treated as a full-pool result. The next version must shard by source root and checkpoint before deterministic merge.

Added `scripts/run_qgis_asset_miner_sharded.py`: fixed pool shards with `DONE.json` checkpoints and merge-only-completed behavior; tests cover exclusion of incomplete shards.

Server tiny end-to-end validation passed (10 rows per pool, 20 total): two checkpoints completed and merged to 20 rows (parsed=19, source_unresolved=1), with 0 training rows. A 250-row shard exceeded the SSH time limit due to `/home/yll` NFS read latency and is not counted.

Full Asset Miner inventory completed (479/479 shards, 47,852 rows): parsed=47,542 and source_unresolved=310; workflow=1,236, implementation=1,088, operator=591, dynamic=496, API semantic-unit=1,874, pattern=6,215, plumbing=12,407, unresolved/no-known-signature=23,945. This is an asset-discovery baseline, not training admission; L3, authority, and training rows remain unchanged. Report: `docs/reports/qgis_asset_miner_full_v1.md`.

## Silver Scale Validation (2026-08-11)

## Source-Role Census (2026-08-11)

A read-only census over all 47,852 sources found `user_workflow=2,209`,
`processing_implementation=1,012`, `api_semantic_operation=9,028`,
`api_plumbing=11,655`, `unclassified=23,638`, and 310 missing server files.
The Processing pool contains 2,068 workflow and 1,011 implementation rows. A
strict preliminary screen (run>=2, task/input-output signals, downstream
dependency) leaves 169 workflow + 114 implementation candidates; these still
need normal fidelity/L3/dedup/V4 gates. API semantic rows feed the API/L2-L3
knowledge layer, not the main workflow training corpus. Report:
`docs/reports/qgis_source_role_census_v2/report_v1.md`.

## Workflow-value tiers (2026-08-11)

The server scored all 47,852 census rows without rereading source or calling
an LLM: tier1 multi-step workflow=169, tier2 single-operator workflow=325,
tier3 Processing implementation=983, API semantic knowledge=4,737, API
plumbing evidence=11,655, unclassified deferred=29,673, and missing=310.
The next Processing workflow queue is 455 rows (tier1=169, tier2=286 in the
Processing pool); 39 tier2 rows retain API provenance and remain separate. No training rows were
emitted. Report: `docs/reports/qgis_source_role_tiers_v1/report_v1.md`.

The 455-row replay is complete and its superseding 70/69/21 result is recorded
above. The current next action is the semantic review of the 31 source-derived
subworkflow candidates. The broader workflow-tier deferred bucket is 29,673 rows,
of which raw `unclassified` is 23,638; neither bucket goes to unrestricted LLM
extraction.

## Workflow Admission Structural Replay (superseded counts, 2026-08-11)

This earlier `304/3/0` statement came from an adapter-order defect and is
superseded by the 70/69/21 report above. Do not use it for planning or yield
estimates.

The current 508 formal QGIS train-only rows (539 including isolated rows) are
not an extraction ceiling for 47,852 sources. They are the observed result of
the strict Gold gates and four-layer deduplication. The API census contains
13,554 pattern candidates, 10,800 discovery units, and 2,773 priority units in
14 composite families, but those units are not yet normalized or admitted.
Existing family experiments retain between 0.5% and 75% of source authorities,
so no global yield extrapolation is valid. The evidence report is
`docs/reports/qgis_silver_scale_validation_v1/report_v1.md`.

The 2,773 priority units are historical discovery population: their 14
mutation-only families have subsequently been replayed, completed, or closed.
Next action: refresh the API census with those families excluded. Only if at
least five new high-support families remain will a no-LLM, source-disjoint
150-source scale pilot measure replay, mapping, fidelity, and canonical-row
retention. It cannot modify the 508-row authority or relax Gold gates.

## Isolated API LLM Boundary Pilot (2026-08-11)

The first 100-source API boundary pilot is complete: 50 calibration and 50
frozen holdout sources, all SHA-disjoint. `deepseek-v4-flash-0731` returned 79
locally validated boundary proposals, 2 multiple-sink proposals were rejected,
and 19 requests failed with HTTP errors. Validation currently establishes JSON,
source-step, line, and single-sink consistency only; it does not establish
semantic correctness. The pilot remains candidate-only with zero training rows.
Evidence: `docs/reports/qgis_api_llm_boundary_pilot_v1/`.

Latest retry and audit update: the complete request ledger is 80 validated, 3
invalid, and 17 HTTP failures. Retrying those 17 with frozen prompt hashes
recovered 2, rejected 1 for multiple sinks, and left 14 HTTP failures. The
independent audit packet contains 82 proposals (41/41 calibration/holdout),
with 8 baseline-step omissions and 52 edge-set differences; no unsupported or
reverse data-flow edges were found. Independent source-backed semantic review
accepted 75, found five wrong chains and two truncated chains; holdout is 38/41,
so the zero-error promotion gate is not met. No semantic promotion or training
admission is granted. Evidence:
`docs/reports/qgis_api_llm_boundary_pilot_v1/semantic_review_v1/`.

The v3 fail-closed follow-up added two local checks: a selected control-path
step must include its controlling header in the source span, and every visible
QGIS data mutation in that span must be represented by a selected AST step.
It rejects 8 of the former 18 locally valid v2 proposals on replay. A newly
frozen 200-source (100/100), source-disjoint v3 packet supplied a controlled
20-source (10/10) experiment: one validated holdout proposal, 16 empty/invalid
proposals, and three HTTP failures. The
single holdout proposal passed independent semantic review, but this recall and
service reliability are far below a promotion threshold. The route is closed
to expansion and remains candidate-only: no L3, training row, or authority
change. Evidence: `docs/reports/qgis_api_llm_boundary_pilot_v3/`.

Scope correction: this v3 experiment supplied bounded source windows plus
pre-extracted AST steps. It tested LLM boundary selection, not raw-source
operator extraction. It therefore does not establish that an LLM cannot find
operators missing from the deterministic extractor; that raw-source route is
still unvalidated and must be tested separately before being closed.

## Isolated LLM Operator Extraction 100-Source Pilot (2026-08-10)

The SHA/AST-verified mixed staging contains 50 Processing and 50 API sources.
Ten bounded scopes per pool were sent to `deepseek-v4-flash-0731`: all 20
responses were valid JSON, selected only supplied catalog IDs, and cited valid
original lines; request failures and unverified candidates were both zero.
Every sent scope had locally observable facts, so this validates the
scope-to-shortlist-to-LLM-to-line-validation protocol only, not recovery of
dynamic IDs or complex workflows. Eighty-seven supported scopes remain budget
deferred and three oversized scopes were not truncated. The API uses a new,
restricted semantic catalog, not L3 labels. Training rows remain zero and no
authority merge is granted. Evidence:
`docs/reports/qgis_processing_llm_operator_pilot_v1/mixed_100_request_budget_10_v1/`;
plan: `docs/plans/qgis_llm_mixed_operator_pilot_v1.md`. The source-disjoint
dynamic/partial-evidence control is complete and produced no independently
verified dynamic recovery; this isolated LLM lane has no approved expansion.

## Processing Dynamic-Argument Full Census (2026-08-10)

A read-only SHA/AST census of all 8,466 Processing authorities found 8,143
readable verified sources, 295 missing sources, and 28 parse failures. Only
**484 sources / 1,379 calls (5.95% of readable sources)** pass a nonliteral
first argument to a Processing-module call: 1,190 `Name` arguments, 125
expression forms, and 64 calls without an argument. Another 4,841 sources have
no direct Processing-module call. The current `deferred_operator=387` group is
not dynamic-ID work; it already has literal provider/algorithm IDs but lacks
catalog or mapping authority. LLM work is therefore limited to the expression
lane, after static recovery of `Name` bindings; all other unresolved forms stay
deferred. The API lane is frozen for now. Evidence:
`docs/reports/qgis_processing_dynamic_argument_census_v1/`.

The 25/25 source-disjoint dynamic-expression LLM pilot is complete: 50
SHA-verified sources / 74 expression calls, 20 attempted scopes, and 15 valid
responses. Its six returned IDs were all already proven literal calls in the
same scopes; new dynamic-expression candidates were zero, and five responses
were unparseable. Expanded JSON parsing and retries yielded two abstentions and
four more unparseable responses, still with zero yield. **Do not expand the LLM
route to 125 calls**. A deterministic AST pass now resolves only source-proven
Boolean conditions; runtime conditions remain multi-candidate and deferred.
The `mappy.matchAlgo` exception has now been tested under a separately frozen
`mappy v0.3.2` implementation hash. Recovery requires the matching source
header, exact relative import, no visible rebinding, one literal argument, and
catalog proof of the returned ID. The full authority census found only **3
sources / 5 calls**; all three were SHA-replayed locally and none formed a
canonical candidate. Two remain blocked by unmapped custom `mappy:*` IDs, and
one is blocked by the existing downstream-transform gate. This wrapper family
is closed as non-scalable. Evidence:
`docs/reports/qgis_processing_dynamic_operator_contract_v1/`. The next
source-only recovery lane is the 1,190 `Name`-argument calls, not an expanded
LLM run.

That `Name` lane has now been census-replayed: 316 sources / 997 calls contain
a `Name` first argument; 97 dynamic chains resolved, and 83 fully normalized.
The eight route-level auto candidates are all one-operator scopes and violate
the Processing two-to-six boundary. The remaining bounded follow-up is 20
fully normalized two-to-six-operator sources were replayed through the existing
call-graph/local-subworkflow gate; two additional two-operator sources were
already `review_api_sidecar`. The replay produced 63 local units but zero
eligible two-to-six units (31 single-step, 32 deferred). Training rows remain
zero. Evidence:
`docs/reports/qgis_processing_name_binding_split_replay_v1/`.

## QGIS API polygon_geometry_construction family (2026-08-09, complete)
## QGIS API coordinate_transform family (2026-08-09, complete)
## QGIS API rectangle_geometry_construction family (2026-08-09, complete)
## QGIS API semantic_priority layer exhausted + composite-macro discovery (2026-08-10)

unary_union (last remaining semantic family): calibration 50 -> full pool 119
-> **0 complete** (real unaryUnion shapes mismatch: non-literal sinks 68,
non-unique calls 33, with-args 14). **The census_v2 semantic_priority layer
(7 families) is mined out**: six complete (polygon 3 + coordinate_transform 1
+ rectangle 2 = +6 rows) plus unary_union zero.

**v3 composite-macro census** (`build_qgis_api_composite_macro_census.py`)
fixes two census_v2 blind spots: dropped multi-producer units (1,286/5,580)
and dropped mutation-only windows (3,718 windows / 2,232 unique sources;
the add_field mechanisms overlapped only 40/2,232). **14 new priority
families / 2,773 units; largest setattributes->addfeature 575 sources.**

## QGIS API setattributes family closed (2026-08-10, +3 rows)

- Calibration 200: v1 strict-literal rule 1/200 (0.5%); sampling showed 68%
  are attribute-copy shapes (`setAttributes(feature.attributes())` alias or
  direct) -> one evidence-driven relaxation -> **60/200 (30%)**; also fixed
  replay template defects (complete rows missing authority key; split without
  source-SHA fallback).
- Full pool 883 units / 575 sources -> **213 complete / 173 authorities
  (24%, largest ever)**; deferred mainly on non-literal sinks 239, dynamic
  values 197, non-unique calls 121, non-unique aliases 113.
- L3 mapping (vocabulary 130, no extension): buffer->L3_02_01_01(8),
  intersects/intersection->L3_02_06_03(22) Extract by Location,
  simplify->L3_02_05_01(104), difference->L3_02_02_04(11) Erase. **Deferred**:
  PLAIN_COPY 145 units/110 auth (no geometry processing inside the evidence
  window; no attribute-copy L3 class), centroid 9 (no class), construct 12
  (evidence invisible).
- Export 45 fidelity -> four-layer dedup **3 canonical rows** (one per group;
  description-template compression, same shape as polygon 43->3) ->
  cross-pool 0 suppressed -> loader smoke (130 vocab) passes. Output
  `docs/reports/qgis_api_setattributes_train_only_v1/` (buffer 1 + extract 1
  + simplify 1). **Semantic proximity note**: extract_by_location is a new
  API single-chain shape absent from 508 (508's L3_02_06_03 rows are all
  Processing/direct); buffer/simplify share L3 with existing 508 API rows
  (similar task, different description) - retention is the user's call.
- **517 train-only rows overall** (508 + 9 isolated: 15-step 1 + polygon 3
  + coordinate_transform 1 + rectangle 2 + setattributes 3).

## Route-1 pilot (LLM candidates + deterministic verifier, 2026-08-14 closed, +9 rows)

User authorized the boundary shift to "LLM proposes candidates, verifier
hard-filters". Protocol evolution: v1 (LLM locates line numbers itself) 0
verified (reasoning model truncation 98 + endpoint 504 61) -> fix max_tokens
16000 + deep backoff -> v2 **5%** (10/200, 12h) -> **v3 protocol inversion**
(AST pre-extracts the call-fact list; LLM only selects indexes) -> **10.5%**
(21/200) -> export **9 rows** (buffer 3 + centroid 1 + changeattributevalue 1
+ difference 1 + frompointxy 1 + frompolygonxy 1 + fromwkt 1; all L3 reused
from vocabulary 130). cross-pool 0 suppressed; loader smoke passes. Verifier
admitted zero hallucinations. **Scale-up projection**: T2 fresh pool 3,575 x
10.5% ~ 160 exported rows. Artifacts `docs/reports/qgis_api_route1_train_only_v1/`,
`qgis_api_route1_pilot_v3/`. Current total **548 train-only** (539 + 9).

## QGIS API mutation-only pool remaining families mined out (2026-08-10, +21 rows)

- **Batch sinks are not provable**: addattributes+updatefields->addfeatures
  calibration 0/200 (batch addFeatures lists are dynamically accumulated in
  loops) - **all 9 sink=addfeatures families (252/216/157/114/63/53/45/33/32)
  permanently closed**.
- **Singular-sink mining**: 63->4, 117->19, 45->5 (addattributes rule:
  literal QgsField names + updateFields + addFeature);
  setattribute->addfeature (182) -> 5 (new rule setAttribute('field',
  literal/unique-alias value)); addattribute->addfeature (40) -> 0.
- **Combined export 21 rows** (`docs/reports/qgis_api_addattributes_train_only_v1/`):
  addattributes 19 (L3_01_02_01/token 1, field-name descriptions - breaks the
  one-per-group compression, 33 fidelity -> 21 canonical) + setattribute 2
  (L3_01_02_06/token 4). cross-pool 0 suppressed; loader smoke passes.
- **All 14 mutation-only priority families mined; +24 rows total
  (setattributes 3 + addattributes-class 21 + setattribute-class 2)**;
  **539 train-only rows overall** (508 + 31 isolated: 15-step 1 + polygon 3
  + coordinate_transform 1 + rectangle 2 + setattributes 3 + addattributes 19
  + setattribute 2).


Vocabulary 129->**130** (L3_01_01_09/token 129); calibration 100 -> full pool
153 -> **4 complete (2.6%, lowest)** -> four-layer dedup keeps **2 canonical
rows** -> BERT-128 + V4 smoke passes. Export
`docs/reports/qgis_api_rectangle_geometry_train_only_v1/`. Deferred mainly on
non-construction extents (46) and non-literal sinks (72). **2026-08-09 API
families total +6 (polygon 3 + coordinate_transform 1 + rectangle 2); 514
train-only rows overall.**


Calibration 200 -> full pool 370 -> **27 complete (25 authorities, 7.3%)** ->
L3 reuse `L3_01_10_01 Project/Reproject` (token 100; no vocabulary extension) ->
27/27 descriptions pass -> four-layer dedup keeps **1 canonical row** ->
BERT-128 (52 tokens) + V4 smoke passes. Export
`docs/reports/qgis_api_coordinate_transform_train_only_v1/`. Deferred mainly on
non-unique transform calls (136) and non-literal sinks (113).


First family of the post-Processing API local-macro lane is closed:
calibration 200 -> full pool 491 -> **43 complete (37 authorities)** ->
stable129 L3 grant (`L3_01_01_08 Create Polygon Features from Vertices` /
token 128; vocabulary 128->**129**,
`docs/reports/qgis_taxonomy_129_authority_v1/taxonomy_129_v1.json`) ->
43 deterministic descriptions pass -> four-layer dedup keeps **3 canonical
rows** (40 suppressed as exact training pairs) -> zero cross-pool suppression
against the 508 aggregate -> BERT-128 + V4 smoke passes (3/3, 2 batches,
finite). Export `docs/reports/qgis_api_polygon_geometry_train_only_v1/`,
SHA256=`32e6035d...`; L3 authority
`qgis_api_polygon_geometry_stable129_authority_v1/`. Deferred on runtime
vertices (179) and non-literal sinks (207). Yield 3 rows (same magnitude as
point/polyline; four-layer dedup dominates).

## QGIS L3 Vocabulary Authority (fixed 2026-08-08)

**The single authoritative L3 vocabulary is 128 content tokens (0-127)**, fixed
in `docs/reports/qgis_taxonomy_128_authority_v1/taxonomy_128_v1.json`
(SHA256=`45860335...`; all 128 classes have names/descriptions; tokens are
contiguous). Composition: 101 (stable101) + 17 (stable106/108, tokens 101-117)
+ 6 (stable120/121/124, 118-123) + 4 (stable125-128, 124-127). All L3 validity
checks, mapping checks, and token assignments use this file only; the
94/101/107/114 systems (v2_94_stable, stable101_taxonomy, qgis_l3_v1_114,
v3_107_experimental) are superseded historical profiles and must not be used as
judgment baselines (the ruggednessindex/basicstats false positive came from
using the stable101-taxonomy baseline).

## QGIS Processing Driver v2 (executed 2026-08-08)

The Processing conversion mainline completed the v2 pipeline end to end. All
8,466 source authorities pass through the driver; no source-level subtraction
is permitted. **The helper-inline route is formally terminated** (v1/v1.1/v1.2
all hit zero units on the real corpus; the gap between real helper forms and a
statically provable whitelist is unbridgeable without re-entering the
branch-uniqueness region Batch-3 already proved low-yield).

The real blocker was a stale L3 mapping authority: the full-pool replay used
the stable110-era mapping (153 operators). Upgrading to the stable124 composed
mapping (168 operators, strict superset) unlocked the standing candidates. The
upgrade also fixed authority pollution (two mappings in composed pointed to
L3 codes outside the 124-token registry and were removed) and a route
alignment contract bug (`call_sites=None` full extraction was misjudged as
unaligned; now accepts `all_literal_calls`).

Results: full-pool replay (direct 100->147, defer_mapping 7,913->7,255) ->
unlock batch of 520 candidates -> 50-row source-disjoint audit (zero wrong
chains/truncations) -> 12 canonical rows. **The formal Processing authority
stays 294 rows**: the 12 canonical rows were checked and all share identical
operator chains and L3 sequences with existing 294 rows - only the description
differs (new compact template vs old template), i.e. zero new tasks; per user
decision they are not merged and remain an isolated description-variant
package (`train_only_v1/decision_note_v1.json`, usable for MR-style
multi-description training). The full QGIS aggregate is 508 rows. The frozen
dual reference is `docs/reports/qgis_processing_conversion_v2_freeze_v5/`
(508 unique / 294 overlap). All artifacts:
`docs/reports/qgis_processing_stable124_unlock_v1/`.
**Correction (late 2026-08-08)**: the `ruggednessindex`/`basicstatisticsforfields`
mappings were once misjudged as pointing outside the token registry and four
rows were revoked - this was a false positive (L3_04_02_02 = token 110 and
L3_01_08_04 = token 113 are official classes; the 505 package contains a
basicstats row). The mappings (composed back to 170 operators) and the four
rows were restored; 302/306/516/520/freeze_v3/v4 were built on the
false-positive revocation and are superseded by 294/508/freeze_v5 (revocation
sidecar marked `restored_false_positive_revocation`).

## QGIS Authority Correction

The previous 454/455-row and 29/2 geometry-difference statements in this file
were written by an obsolete parallel branch and are superseded. The 495-row
entrypoint has now received a strict stable127 polyline-geometry local-macro
increment of three rows. The authoritative V4-128 train-only entrypoint is
`docs/reports/qgis_train_only_v4_128_505_v1/` (505 rows, SHA256
`13bb886d87ce8b487f7f45e80a155e592b8c937667b61cf835e7f121b952a97a`).
The 495-row entrypoint, the 492-row entrypoint, the old 455-row package, and
geometry-difference v1/v2 artifacts remain superseded provenance only and must
not be used as training authority.

The active API expansion stage has completed a 200-source point-geometry
calibration: 200/200 source SHA verified, 193 normalized-body authorities,
107 complete strict macros (102 complete authorities), and 93 fail-closed
deferrals. Calibration/holdout source-SHA and normalized-body overlap are both
zero. The complete macros split into 57 coordinate-constructor and 50
prebuilt-point payloads. Stable126 has admitted 55 strict coordinate-pair
macros; the 50 prebuilt-point payloads remain outside L3 and training admission.
`L3_01_01_04 Create Points from Table` covers only the former when field
provenance is established, so it cannot be applied to the whole family.
Authorities: `docs/reports/qgis_api_point_geometry_calibration_v1/`,
`qgis_api_point_geometry_replay_v3/`, and
`qgis_api_point_geometry_payload_census_v1/`.
Stable126 minimally adds `L3_01_01_05 Create Point Features from Coordinates`
/ token 125 for the source-verified local macro `point factory -> same-feature
setGeometry -> sink`. Its 55/55 deterministic Chinese descriptions pass
source-fact fidelity without an LLM. Four-layer deduplication suppresses 52
exact training-pair copies, retaining three rows with zero cross-pool overlap
against the 492-row base. All 495 rows pass real tokenizer and V4
loader/loss/backward gates; no training/checkpoint, validation/test, or
production merge is granted. Authorities are `docs/reports/qgis_api_stable126_authority_v1/`,
`docs/reports/qgis_api_point_geometry_train_only_v1/`, and
`docs/reports/qgis_train_only_v4_128_495_v1/`.

The next API family, `polyline_geometry_construction`, has completed its
source-disjoint boundary gate: a 200-source calibration yields 9 complete
calibration and 9 complete holdout macros with zero source-SHA/body-authority
leakage. Full replay verifies 611/611 source rows and retains 54 strict local
macros from 34 normalized-body authorities; 557 rows remain fail-closed.
Stable127 minimally adds `L3_01_01_06 Create Polyline Features from Vertices`
/ token 126 for `fromPolyline/fromPolylineXY -> same-feature setGeometry ->
literal sink`. It does not claim whole-function semantics. Deterministic
source-fact descriptions pass 54/54 without an LLM; four-layer dedup suppresses
51 exact pairs and cross-pool dedup retains three new rows. All 498 rows pass
real tokenizer and V4 loader/loss/backward gates. Authorities are
`docs/reports/qgis_api_polyline_geometry_replay_v2/`,
`qgis_api_polyline_geometry_replay_v3/`,
`qgis_api_stable127_authority_v1/`,
`qgis_api_polyline_geometry_train_only_v2/`, and
`qgis_train_only_v4_128_498_v1/`.

The WKT-geometry family then completed source-disjoint calibration. After
tightening cross-branch geometry-mutation detection, it retained 74 complete
macros / 73 normalized-body authorities with zero calibration/holdout authority
overlap. Full replay verifies 644/644 source rows and retains 270 complete
macros / 156 authorities. Stable128 minimally adds
`L3_01_01_07 Create Features from WKT Geometry` / token 127 only for
`fromWkt -> same-feature setGeometry -> literal sink`; it does not reuse the
raster format-conversion class. All 270 source-fact Chinese descriptions pass;
four-layer dedup suppresses 263 copies and cross-pool dedup retains seven new
rows. That stage's V4-128 entrypoint was `docs/reports/qgis_train_only_v4_128_505_v1/`
(505 rows, SHA256
`13bb886d87ce8b487f7f45e80a155e592b8c937667b61cf835e7f121b952a97a`),
passing the real `bert-base-uncased` 128-token gate and V4 loader/loss/backward
smoke (16 batches; finite loss/gradients). No LLM, training, checkpoint,
validation/test, or production merge was granted. **The current formal full
QGIS train-only aggregate is 508 rows**
(`docs/reports/qgis_train_only_aggregate_508_v1/`, SHA256
`4d9e64af...`)
= 214 API rows + 294 Processing rows; the 507-, 516- and 520-row entrypoints
are superseded provenance.

## Isolated LLM Catalog Extraction (2026-08-10)

The pilot repairs two protocol defects: canonical literals now enter catalog options, and a
module-level `processing.run(name, ...)` carries its unique prior static binding with original line
evidence. Five sent literal scopes returned all 9 locally proved IDs with no empty response. In a
four-source control audit, the static-alias positive returned
`native:joinattributesbylocation@115`; both external-parameter/wrapper negatives abstained.

This validates the scope/binding protocol, not reliable recovery of runtime-dynamic IDs. The gain is
deterministically recoverable static aliases. LLM remains isolated and candidate-only: do not batch
call 8,466 sources or emit L3, descriptions, training rows, or authority merges. Evidence:
`docs/reports/qgis_processing_llm_catalog_extraction_pilot_v2/literal_protocol_fix_5_v1/` and
`docs/reports/qgis_processing_llm_catalog_extraction_pilot_v2/dynamic_binding_audit_4_v2/`.

## Mainline

The QGIS mainline deterministically converts source code into high-quality train-only
data for natural-language task to reliable QGIS workflow operator chains. The formal
aggregate is the 516-row full QGIS package, of which the current formal Processing
aggregate has **294 rows** (`docs/reports/qgis_processing_aggregate_294_v1/`;
the 302/306 packages (built on the false-positive revocation / on 12
description-variant rows with zero new tasks) are superseded); the remainder
are earlier API deliveries. `8,466` is Processing source replay/provenance coverage, not
the number of converted training samples.

The Processing 500-1000 target is judged unreachable with current capabilities
(2026-08-08 review: all remaining pools are closed - 5,714 empty chains dead,
729 single-gap rows below the L3 support>=30 gate, boundary 778 diagnosed with
no mineable stratum, 390 multi-gap dead; 295 rows is the capability ceiling).
**The API family freeze is lifted**; low-level PyQGIS API local-macro families
(historically the most stable source) become the main data-construction lane. Processing Batch-3 selects 200 source-disjoint authorities from
995 unadmitted blocker parents: 40 each for `control_flow_if`, `control_flow_for`,
`helper_alias_missing_edges`, `split_local_subworkflow`, and
`dynamic_or_custom_operator_resolution`, split 100/100 into calibration and holdout.
Normalized-body authorities and source SHA values are both disjoint. The server freshly
reverified all 200 `/home/yll` source SHA values with zero missing or mismatched files.
This is a rule-calibration baseline, not training data. The next loop is reusable-rule
calibration/holdout -> whole-family replay -> source-disjoint random audit ->
description/L3/four-layer-dedup/V4 gates, never per-file production review.

The server-side Batch-3 structural evaluation produced 366 local units from the 200
authorities: 31 structural eligible and 335 fail-closed deferred, with zero source
failures in both partitions. Helper/alias, split, and some control-flow strata have
candidate units; 40 dynamic/custom authorities remain `catalog_provider_resolution_pending`.
No rule promotion, L3 admission, or training admission is granted. Evidence:
`docs/reports/qgis_processing_batch3_calibration_v1/structural_evaluation_summary_v1.json`.

Dual-partition rule grouping permits only three rules to enter full-family replay:
`recovery-connected-local-dag-v1` at 3/5, `recovery-multi-root-fanin-dag-v1` at 4/4,
and `split-local-structure-v9` at 12/3 eligible units (calibration/holdout). The
995-parent replay is complete: 491/491 parser source SHA checks passed, yielding 44
candidates across 33 normalized-body authorities. These are still candidates, not training rows.

`scripts/admit_qgis_processing_batch3_candidates.py` now provides authority folding,
four-layer keys, exact training-pair cross-pool suppression against the existing 293-row
Processing package, and a deterministic source-disjoint audit manifest. The run retains
five canonical candidates pending source-snippet audit; 11 same-authority units, five
within-batch duplicates, and 23 existing-pool duplicates are recorded in sidecars. Audit
calibration/holdout normalized-body overlap is zero, but no train-only row is emitted until
the sampled source review passes. The hash-frozen admission package is
`docs/reports/qgis_processing_batch3_admission_v3/`.

The five canonical source snippets are now audited on `/home/yll`: three are accepted pending
downstream gates and two are deferred (interleaved low-level edits break the local boundary;
one source formula references a misspelled field). Deterministic source-fact compression brings
the three accepted descriptions under the real `bert-base-uncased` 128-token gate (max 80 tokens),
and the isolated V4 loader/weighted-loss/backward smoke covers 3/3 with finite loss/gradients and
no checkpoint. The isolated train-only package is
`docs/reports/qgis_processing_batch3_train_only_v2/`; it is not merged into the formal aggregate,
and validation/test plus production merge remain disabled. Evidence and adjudication are under
`qgis_processing_batch3_source_audit_v1/` and `qgis_processing_batch3_source_adjudication_v2/`.
The legacy BERT-128 gate is now batch-repaired: 33 overlong descriptions pass deterministic
`task name + ordered operator run-length` source-fact compaction, while two ultra-long chains remain
deferred. Together with the three new rows, the 294-row package at
`docs/reports/qgis_processing_aggregate_294_v1/` passes real BERT-128 (maximum 127 tokens) and
V4 loader/weighted-loss/backward smoke (294/294, 19 batches, finite loss/gradients). No training,
checkpoint, validation/test eligibility, or production merge is granted.

A seven-row canonical trial from the historical stable124 candidate package completed server source
audit (7/7 SHA verified): five local boundaries were acceptable and two were deferred. The five
otherwise acceptable rows are already present in the current 294-row pool by both source SHA256 and
normalized DAG, so the corrected cross-pool four-layer dedup suppresses all five and emits zero new
rows. The temporary 299-row aggregate and pre-fix five-row export are explicitly superseded and must
not be used. The exporter now separates stable token authority from operator-to-L3 mapping and makes
source region, call graph, normalized DAG, and training-pair overlap hard gates; source SHA remains
source-verification and source-disjoint evidence rather than a dedup key by itself.

The prior conclusion that no old narrow Processing signature met support>=30 closes only
that narrow search; it does not complete Processing or permit an API switch. Validation/test,
production merge, and model training remain closed.

The next source-backed static-recovery census excludes 1,565 formal or previously scanned source SHA256s and replays
6,820 remaining `deferred_mapping`/`deferred_operator` sources on read-only `/home/yll`. Only AST-provable constant
aliases, fixed dictionary keys, and fixed list/tuple indexes are accepted; runtime indexes, multi-value branches,
registry/wrapper calls, catalog misses, and missing sources remain deferred. It recovers 57 direct static chains,
records helper evidence for 55 and strict output-alias evidence for three, but produces only three complete local
units from two sources. No source-disjoint support family exists, so calibration, L3, descriptions, and training rows
remain zero. The server-only evidence ledger is mirrored locally only by summary/hash at
`docs/reports/qgis_processing_static_recovery_census_v1/`. The next capability must recover real cross-helper
parameter/result propagation or single-path dynamic IDs and prove complete local boundaries before calibration;
structural similarity remains non-admissible as a training label.

The remaining blocker authority outside the first 319-source verified subset has now received
the same exact provider reanchoring and structural census. Of 343 selected sources, 323 passed
server SHA verification (20 missing sources remain fail-closed); 93 exact `qgis:<slug>` to
`native:<same slug>` alias migrations were independently AST-proved. The remaining recovery
and split parents yield six and 94 local units respectively, but only one unit survives the
strict boundary plus description gate, so its normalized-body support is one. The 230 remaining
operator-resolution sources contain 222 normalized bodies and 124 exact canonical operator
sequence clusters; the highest support is only 11 (`native:mergevectorlayers`), followed by
10 (`native:fieldcalculator`). These sequence clusters have no recovered task boundary and are
explicitly not calibration-eligible. No family reaches the support-30 source-disjoint
calibration threshold; no training, L3, description, or export admission is granted. Authority:
`docs/reports/qgis_processing_expansion_remaining_census_server_v1/reanchored_family_census_v2/`.
The reusable census entry is `scripts/census_qgis_processing_reanchored_families.py`.

An independent blocker intake, without revisiting those 343 sources, excluded the formal 294-row authority and the
previously scanned 360/343 source-SHA populations. Requiring exact agreement between `call_sites` and
`operator_sequence` left 297 clusters; 6,408 rows lacked call evidence and 365 database/support-export rows were
fail-closed. No safe cluster reached support 30, so no calibration, L3, description, or training row was emitted. The
preliminary 126-row PostGIS-import selection is superseded provenance. This closes only exact whole-chain signatures;
next recover local-subworkflow boundaries from call-bearing sources, without re-scanning the 343-source pool. Evidence:
`docs/reports/qgis_processing_independent_blocker_intake_v2/`.

The full local-boundary replay for that independent population is complete: 624 of 678 safe source representatives
passed server SHA verification and splitting, with 530 exact `qgis:<slug> -> native:<same slug>` AST reanchors. It
recovered 1,952 local units, 623 multi-step units, 47 structurally eligible units from 33 sources, and 331 boundary
signature clusters. The maximum structural signature support is 13 but mixes distinct operator chains; the maximum
exact canonical local-chain support is 8. Sixteen over-64-call sources cannot lift any family to support 30. No
source-disjoint calibration, L3, description, or training row is granted. This closes the independent call-bearing
boundary-signature route; the next lane needs a different source-backed subpopulation or a new helper/output-alias/
dynamic-ID recovery capability. Authority: `docs/reports/qgis_processing_independent_local_boundary_replay_v1/replay_v6/`.

`task_plan.md` maintains three independent sections: GEE data processing, QGIS
data processing, and benchmark construction. GEE and benchmark work may proceed
in parallel, but neither pauses nor replaces the QGIS mainline.

This agent's scope is QGIS source-to-training-data conversion only. It owns the
8,466-row Processing pool and the 39,386-row low-level PyQGIS API pool through
source replay, task-boundary recovery, L3 mapping, description fidelity,
deduplication, and train-only admission. It does not own GEE data or benchmark
construction.

## Latest Verified State

- **2026-08-08: Processing authority stays 294 rows.** The 12 stable124-unlock canonicals (520 candidates -> 50-row source-disjoint audit with zero wrong chains/truncations -> 12 rows) were checked and all share identical chains/L3 with existing 294 rows - only descriptions differ (new compact template), i.e. zero new tasks; per user decision not merged, kept isolated as description variants (`train_only_v1/decision_note_v1.json`). The 306 package (294+12) is superseded.
- **2026-08-08 (late) false-positive correction**: `ruggednessindex->L3_04_02_02` and `basicstatisticsforfields->L3_01_08_04` were misjudged as pointing outside the token registry (wrong baseline: stable101 taxonomy + added_l3 collection missed the stable106/108 classes in existing_code_to_id, tokens 101-117; L3_04_02_02 = token 110 and L3_01_08_04 = token 113 are official, and the 505 package contains a basicstats row). The four-row revocation and mapping removal were rescinded: composed restored to 170 operators, rows restored, revocation sidecar marked `restored_false_positive_revocation`; 302/516/freeze_v3 superseded.
- **2026-08-08: Full QGIS aggregate is 508 rows** (214 API + 294 Processing), `qgis_train_only_aggregate_508_v1/`, SHA256=`4d9e64af...`; the 507-, 516- and 520-row entrypoints are superseded. Frozen dual reference is `qgis_processing_conversion_v2_freeze_v5/` (508 unique / 294 overlap, SHA256=`13debc60...`).
- **2026-08-08: helper-inline route terminated** (v1/v1.1/v1.2 all zero hits on the real corpus). Empty-chain attribution: 87 of 215 dual-feature rows carry catalog-external third-party provider operators (umep/pff/trendsearth etc.; 16 mix QGIS-native operators but whole chains contain third-party ones) - permanently deferred, not unlockable; 128 are truly empty (no literal processing call; deferred).
- **2026-08-08: mapping authority upgrade.** Replay mapping upgraded from stable110 (153 operators) to stable124 composed (170 operators, strict superset); route alignment contract fixed (`all_literal_calls` accepted). Gap census (after restoration): 472 missing operators, raw support>=30 for only four (deleteholes/stringconcatenation/package/orderbyexpression), all below the normalized-body threshold, so no minimal-extension L3 admission; kept as an observation list (`empty_chain_and_gap_diagnosis_v1.json`, `mapping_gap_prioritization_v1.json`).
- The API mainline has closed its first reusable family. A 102-row field-schema replay narrows to 67 strict rows after macro-contract, higher-level spatial-semantics, and source-scope gates. Frozen 20-row calibration and 20-row holdout splits have zero source-SHA and normalized-body overlap. Full AST alias replay yields 52 complete local macros, 11 missing memory-layer constructors, three incomplete chains, and one ambiguous multi-chain row; all incomplete or ambiguous cases remain fail-closed. Whole-function single-L3 mapping was formally rejected because only 5/20 calibration and 6/20 holdout functions preserve the full task, while the rest would truncate split/import/calculation/sampling/export semantics.
- Stable125 restores only legacy-350 `L3_01_01_01 Create Feature Class` as token 124 and preserves stable124 tokens 0-123. Its authority is restricted to the source-verified local macro `QgsVectorLayer(..., "memory") -> schema -> optional prepared features -> writer`; `whole_function_semantics_admission=not_granted`. Source-fact-only descriptions pass 52/52 without an LLM, and four-layer dedup retains 28 canonical rows while suppressing 24 exact training-pair duplicates. Cross-pool overlap against 304 existing QGIS rows is zero. The formal package is `docs/reports/qgis_api_create_feature_class_train_only_v1/`, JSONL SHA256=`17cb1de9fbf469ca7cd8e4d9decdcedfd0070088160712533721e12b2d13809e`. Real V4 loader/weighted-loss/backward covers 28/28 rows in seven batches with finite loss and gradients; no training, checkpoint, validation/test eligibility, or production merge was granted.
- `Vector File Export` has completed one rule calibration and full-pool replay. The 60-row source-disjoint calibration/holdout packet yields 24 complete and 36 fail-closed rows with zero complete false positives, chain truncations, or silent fallbacks. The identical parser verifies source SHA for all 211 strict candidates and yields 83 complete local writer macros plus 128 deferrals. Source-fact descriptions pass 83/83 with `llm_called=false`; four-layer dedup retains 18 training pairs and suppresses 65 exact duplicates. Existing stable125 `L3_07_04_01`/token 67 is reused. Cross-pool overlap against 332 existing QGIS rows is zero. The formal package is `docs/reports/qgis_api_vector_file_export_train_only_v1/`, JSONL SHA256=`09f3d62ee14159f903a1f3b23d4be5e029e50d9d20401b9228bedbf93e19fa14`. Real V4 loader/weighted-loss/backward covers 18/18 rows in five batches with finite loss and gradients; no training, checkpoint, validation/test eligibility, or production merge was granted.
- `Add Field -> Calculate Field` has completed rule hardening, full replay, and an isolated delivery. Of 3,190 Add Field sidecar rows, 66 enter the family. The v2 rule yields 30 complete macros / 28 normalized-body authorities and fails closed on 22 missing same-feature update chains, five adjacent schema mutations, three cross-layer/spatial boundaries, and six downstream same-field transforms. Source-disjoint 14/14 calibration/holdout covers the complete authority population with zero source/body overlap, observed false positives, or chain truncations. Source-fact descriptions pass 30/30 with `llm_called=false`; four-layer dedup retains 15 training pairs and suppresses 15 exact duplicates, with zero overlap against the existing 350-row pool. The formal package is `docs/reports/qgis_api_add_calculate_field_train_only_v1/`, JSONL SHA256=`23b14847d29470aba97817491adc085911d944298376965c048be9253dafd47a`. Real V4 loader/weighted-loss/backward covers 15/15 rows in four batches with finite loss and gradients. Automatic family promotion remains ungranted because normalized-body support is 28<30; only this fully reviewed bounded population receives train-only admission. No training, checkpoint, validation/test eligibility, or production merge was granted.
- `Raster Calculator` and `Set CRS Metadata` deliver 83 and 35 source-verified API train-only rows. Both source-disjoint reviews use 20/20 calibration/holdout with zero source-SHA/body overlap, false positives, or chain truncations. Real V4 loader/loss/backward covers 83/83 and 35/35 rows. Raster File Export remains deferred because one writer family mixes incompatible output-format contracts.
- The corrected Existing-Layer Add Field bounded batch screens 2,651 authorities and recovers only 30 complete units across 23 normalized-body authorities by grouping every same-layer add call before one `updateFields()` commit. The superseded v1 truncated population is not reused. Source-disjoint 15/15 review covers all 30 candidate unit IDs with zero overlap, false positives, or chain truncations. All descriptions pass from literal field names only; stable125 `L3_01_02_01`/token 1 is reused. Four-layer dedup retains 24 rows, suppresses six exact pairs, and cross-pool comparison against 483 rows suppresses zero more. JSONL SHA256 is `320bce3f65d6e8573c20f32999000ebe43f88c017cc73954ca0803e2c9288c78`; V4 smoke passes 24/24. Rule promotion remains closed at support 23<30.
- The bounded `geometry_difference` batch is explicitly anchored to 31 frozen `resolved_local_call_chain` units, all source-SHA verified on the server. Control-path-correct replay retains 29 complete local macros across 17 authorities and defers two post-difference `convertToMultiType()` units. Calibration/holdout source-SHA/body overlap, observed false positives, and chain truncations are zero. Deterministic descriptions pass 29/29; four-layer dedup suppresses 28 exact training-pair duplicates, and cross-pool comparison against 454 rows suppresses zero, yielding one net-new row. Automatic family promotion remains closed below support 30. Authorities are `docs/reports/qgis_api_geometry_difference_replay_v2/`, `qgis_api_geometry_difference_source_review_v2/`, and `qgis_api_geometry_difference_train_only_v1/`.
- Remaining mutation/export family selection is closed for the current census: the six semantic anchors have authority support 24/18/16/15/13/8, all below 30. Seven apparent support-30-to-40 groups are only generic `x/y`, `geometry/boundingBox/center`, or legacy parameter-access co-occurrences that mix multiple tasks and cannot be mapped as training operators. The next census must cluster the 13,554 pattern candidates by composite producer + mutation + sink terminal macros rather than single calls or call co-occurrence.
- The old 507-row provenance and 455/498-row V4-128 entrypoints remain superseded historical evidence only. The current formal entrypoint is the 505-row stable128 package stated above; it retains the same closed validation/test and production-merge boundary.
- The stratified aggregate audit is complete. Its 25/25 calibration/holdout split has zero source-SHA or authority overlap. Server replay verifies 50/50 files, hashes, decodes, ASTs, source spans, and 1,689 evidence lines. Semantic review yields 40 `accepted_v4_128_audit` and ten `deferred_text_truncation`; boundary, description-fidelity, and stable125 operator/L3 failures are all zero. Authority: `docs/reports/qgis_train_only_aggregate_507_audit_v1/`.
- The authoritative Processing delivery is now 293 train-only rows at `docs/reports/qgis_processing_delivery_293_v1_source_verified/`. Stable124 replay of the 445-row dynamic/empty operator-ID slice yields 53 candidates, ten canonical rows, and 43 exact training-pair duplicates. All ten pass source SHA, call-site, parameter provenance, description fidelity, stable124 L3, and cross-pool four-layer dedup without granting a new rule signature. All 293 sample IDs, source regions, call graphs, and training pairs are unique; the package covers 237 source SHA values, 209 normalized DAGs, 170 operator sequences, and 150 L3 sequences. JSONL SHA256 is `bc82877b644072dc803b63563a8ecbef0deb65374b73ac50f86404d845a9ed58`. Real V4 loader, weighted loss, and backward cover 293/293 rows in 19 batches with finite loss and gradients. Validation/test eligibility is false and production merge is not granted. The 283-row package is superseded provenance.
- The prior narrow Processing family search has deferred-authority counts of 18/22/16/25/23/14 for parameter/result/output/backward/immediate/helper, with five true cross-function authorities and only three safe fixed-small-independent `control_flow:for` bodies. This closes that narrow-signature search only. It does not close Processing: Batch-3 now calibrates reusable rules over 200 source-disjoint authorities across five blocker strata; API new-family work is frozen until a 500-1000-row Processing delivery. Authority: `docs/reports/qgis_processing_batch3_calibration_v1/`.

- Processing boundary-family replay is frozen at splitter v9 over 995 blocker parents and 173 direct rows with zero source failures. Its same-if, downstream/sink, `QgsProcessingUtils`, and output-alias conclusions are closed evidence rather than active work. Authorities: `docs/reports/qgis_processing_boundary_families_v2_condition_evidence/`, `docs/reports/qgis_processing_same_if_calibration_v1/`, and `docs/reports/qgis_processing_downstream_transform_census_v1/`.
- Stable124 adds only the original-350 classes `Define Projection`, `Flip Line`, and `Split by Attribute` as tokens 121-123, preserving tokens 0-120. Their QGIS 3.28 catalog contracts are exact, 83 source files pass SHA verification, and normalized-body support is 11, 12, and 22. This fixed-provider mapping authority remains separate from the support>=30 extraction-signature auto-generalization gate and does not directly grant training admission. The 3,163-row replay raises mapping-complete rows from 984 to 1,012; full replay yields 570 strict candidates, with all 12 mapping-induced candidates suppressed as existing training-pair duplicates. The remaining seven canonical rows enter through explicit candidate IDs and server source/description replay in a canonical calibration batch; no new rule signature is granted. Authorities are under `docs/reports/qgis_processing_stable124_authority_v1/`, `docs/reports/qgis_processing_stable124_full_population_v1/`, and `docs/reports/qgis_processing_stable124_canonical_adjudication_v1/`.
- Stable121 follows the minimum-supplement rule: `qgis:voronoipolygons` adds `L3_02_07_07`/token 120 and `native:removeduplicatesbyattribute` reuses `L3_01_05_04`/token 102. `native:boundary`, `native:convexhull`, and `qgis:linestopolygons` remain deferred because normalized-body support is below 30. The 3,163-row replay yields 1,536 fully normalized, 984 mapping-complete, and 173 direct rows; full-population replay yields 558 strict candidates and 13 canonical rows. Six canonical rows match stable120 v5's admitted exact dual-split signature and are exported, while seven unseen-signature rows remain deferred. No per-row gate relaxation, LLM generation, or training occurred. Authorities are under `docs/reports/qgis_processing_stable121_authority_v1/`, `docs/reports/qgis_processing_stable121_full_population_v1/`, and `docs/reports/qgis_processing_stable121_train_increment_v1/`.
- stable120 follows the minimum-extension rule: `native:createspatialindex` adds `L3_01_07_01`/token 118, `native:snapgeometries` adds `L3_02_07_09`/token 119 after 51 independent normalized source bodies, and `native:saveselectedfeatures` reuses existing `L3_07_04_01`. `native:serviceareafromlayer` and unconditional `grass7:v.clean` break/snap aliases remain deferred. The 3,163-row replay yields 982 mapping-complete and 173 direct rows; authority is `docs/reports/qgis_processing_stable120_authority_v1/`.
- The stable120 v5 full-population replay verifies 952/952 recovery/split/operator-resolution parents plus 173/173 direct rows with zero source failures. `deterministic_operator_dag_zh_v5` recovers only AST-proven function inputs and dominating same-scope derived values while keeping all uncertain cases fail-closed. The result is 530 strict candidates: 61 canonical, 126 duplicate source regions, and 343 exact training-pair duplicates. The seed-20260803 review has 50 calibration and 50 holdout rows with zero source-SHA and normalized-body-authority overlap. Only three support>=30 exact signatures with dual-split evidence are admitted, yielding 55 incremental rows. The merged 270 package passes real `TaskConditionedL3DatasetV4`, weighted loss, and backward for 270/270 rows in 17 batches with finite loss/gradients; no checkpoint, training run, LLM description generation, or production merge occurred. Candidate authority: `docs/reports/qgis_processing_stable120_full_population_v5_policy_v1/`.
- The QGIS Processing-resolution authority contains 8,466 rows. Source SHA verification passes for 8,466/8,466 with zero source failures.
- Full Processing source replay now covers 8,466/8,466 unique source SHA rows with feature extractor v8: 100 direct candidates, 222 recovery rows, 203 API sidecars, 7,913 mapping deferrals, and 28 unparseable exclusions. This is routing-only and emits zero training rows.
- `scripts/run_qgis_processing_batch.py` is now the unified Processing entrypoint. It uses the 8,466-row authority and full replay v2 as its base, overlays the latest 3,163-row stable110/correction replay only by `(record_id, source_sha256)`, and joins deterministic descriptions, four-layer dedup evidence, and the admitted train-only authority. A 200-row stratified calibration includes all 129 latest direct rows and all 38 existing accepted rows; after identity/chain/leakage gates pass, the identical frozen inputs replay across all 8,466 rows. Final outcomes are accepted 38, deferred 8,284, duplicate 70, and excluded 74; detailed blockers are boundary 612, operator 387, mapping 7,261, description fidelity 22, source replay 2, alignment exclusion 50, and unparseable 24. All 35 direct accepted rows exactly match the latest operator/L3 chain and no uncertain row is exported. Authority: `docs/reports/qgis_processing_unified_replay_v1/`. This calibration proves batch-state and admission invariants, not human semantic precision for new rules.
- All 757 blockers have completed read-only replay with 757/757 source hashes verified and zero failures. v10 fixes the missing existing-L3 authority for `native:extractwithindistance` and is now the blocker authority: 166 candidates, 45 canonical rows, 121 duplicates, 130 fully-normalized mapping-complete rows, and 218 partial mapped subsets. This pool contains custom callers only and emits no direct training row. Corrected custom-scope replay covers 8,471 unique sources and 97 variants, raises complete variants/scope parents from 7/7 to 9/9, and yields three scope candidates (two canonical and one duplicate). Quality gates export one new six-step `filterstructures` train-only row. Authority: `docs/reports/qgis_processing_operator_expansion_v1/report_v2.md` and `docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping/report_v1.md`.
- The stable110 existing-L3 alias batch is complete: nine mapping authorities cover 21 single-gap records, and the 3,163-row replay raises direct routing to 150. Of 17 newly routed direct rows, nine pass deterministic description fidelity; three missing-source rows and three exact training-pair duplicates are then suppressed, leaving three canonical rows. All 3/3 pass source SHA, AST, and call-span replay and are exported train-only. A real V4 loader/loss/backward smoke covers 3/3 with finite loss and gradients and no training or production merge. This historical stage reached 168 rows and is superseded by the 210-row authority above. Authority: `docs/reports/qgis_processing_mapping_gap_stable110_alias_replay_v2/report_v2.md`.
- Full-pool workflow-input provenance replay is complete for the 73 description-deferred direct rows. Dynamic parameters are admitted only when AST evidence traces them to `parameters[...]` or a dominating same-scope `parameterAs*()` assignment; bare locals, computed expressions, non-dominating branches, and dictionary mutation remain fail-closed. Description fidelity rises from 77 to 97. Of the 20 recovered rows, one missing source and 13 exact training-pair duplicates are suppressed, leaving six canonical rows. All 6/6 pass source SHA/AST/call-span replay and real V4 loader/loss/backward. The 52-step target has 54 sequence tokens below the 100-token label limit, but its natural-language prompt is 1,955>128 and is now deferred from the V4-128 package. This historical stage reached 174 rows and is superseded by the 210-row authority above. Authority: `docs/reports/qgis_processing_runtime_parameter_replay_v1/report_v1.md`.
- A provenance census of the remaining 53 description-deferred rows led to a TDD-locked rule for dominating same-scope literal aliases and three explicit empty-default parameter keys. Its four-row increment produced the historical 178 count. Later semantic review revoked the incorrectly mapped `native:ruggednessindex` and `qgis:basicstatisticsforfields` rows, while corrected custom-scope replay added one row, yielding 177 at that stage. The 177/178 counts are now superseded by the 210-row stable120 authority. Authorities: `docs/reports/qgis_processing_runtime_parameter_replay_v2_corrected/report_v1.md` and `docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping/report_v1.md`.
- The corrected custom-implementation resolver searched an 8,471-row source index and found 167 matching instances / 97 implementation variants; 8,471 is not a workflow-candidate count. Its 10 expanded-complete variants, 27 unresolved variants across 16 families, four scope candidates -> two canonical/two duplicate rows, and zero net-new result close only that target-family subproblem. They do not close all 4,858 implementation/custom records. Authority: `docs/reports/qgis_processing_custom_implementation_closure_v1/`.
- Recomputing the old 3,163-row replay with the corrected 153-operator stable110 mapping yields 726 fully normalized mapping gaps rather than the stale count of 708. Only 195 are structurally eligible; after excluding 142 database-side-effect rows and 16 support/export rows, 37 semantic-review rows collapse to 33 normalized source bodies and 18 feature signatures. Source SHA is verified for 149/195 rows; all 46 unverified rows are sidecars (44 database side effects and two semantic deferred) and cannot count as normalized-body support. Exact existing-stable110 candidates are zero, training rows are zero, and this lane is closed. Authority: `docs/reports/qgis_processing_mapping_gap_stable110_closure_v1/`.
- The strong-signal low-level API authority is exactly 39,386 unique source SHA rows; the broader layer table contains one extra non-authoritative row and is not used. Full source-backed AST extraction verifies and parses 39,386/39,386 rows, yields 235,795 API steps, 13,554 multi-signal pattern candidates, and 25,832 insufficient-boundary deferrals. L3/description/dedup/training outputs remain zero.
- Final boundary rule `typed-terminal-control-path-dag-v4` has completed full-pool v6 replay: 39,386/39,386 source hashes verify, 37,901 normalized source bodies yield 2,708 candidate units across 1,587 source authorities and 2,327 deferred terminal units. The reviewed post-filter leaves 2,707 L3-intake units; across the old 200 and fresh calibration/holdout 200, all 393 true positives are retained and all seven false positives are suppressed.
- The stable110 API mapping census covers all 2,707 intake units. Of 102 strong-semantic-anchor units, 75 units across 59 source authorities map completely to existing Buffer, Intersect, Simplify, Feature to Point, or Minimum Bounding Geometry L3 contracts. Twenty-seven fail closed: seven for insufficient output contracts, eight for parameter dependence, ten for taxonomy-contract mismatch, one taxonomy gap, and one insufficient task scope. The other 2,605 units contain mutation/export support only; `setGeometry`, `setAttributes`, and `addFeature` are not treated as algorithms.
- Read-only `/home/yll` replay verifies source SHA, AST, API call span, and arguments for all 75 exact-L3 proposals with zero failures. Deterministic description fidelity passes 74 and defers one `buffer(0, 1)` geometry-repair idiom. Four-layer deduplication retains six canonical rows and suppresses 68 exact training-pair duplicates.
- Cross-pool comparison against 118 existing QGIS train-only rows finds no exact overlap. Six isolated `qgis_api_training_sample_v1` rows now cover six source authorities and five L3 sequences. A real V4 loader/weighted-loss/backward smoke covers 6/6 with finite loss and gradients; no checkpoint, training run, production merge, or LLM call occurred.
- The remaining 2,605 `mutation_export_only` units were replayed with `control-path-caller-and-terminal-backward-slice-v4`: 1,429 resolve locally, 382 remain branch-ambiguous, 51 remain external payload, and 743 remain without a locatable `setGeometry`. The 743 terminal payload sidecar has 593 support/custom-only, 109 no local chain, 41 ambiguous, and 0 known geometry-semantic candidates. After excluding 158 reviewed-family units, 2,447 remain; 210 complete signature families exist but none has support>=30. No mapping, description, or training rows are emitted. Authority: `docs/reports/qgis_api_unresolved_recovery_v1/`.
- The 52 nested-centroid candidates have completed the strict source-disjoint pipeline. Normalized bodies collapse 12 declared authorities to nine; 50 units have complete boundaries and two defer because point-in-polygon counting dependencies were omitted. The 25/25 calibration and 25/25 holdout partitions have zero source-authority, source-SHA, alias-group, or unit-ID overlap. All 50 pass stable110 mapping, source replay, and description fidelity; four-layer dedup retains one canonical row, which is already present in the 124-row QGIS train-only authority, so net new training yield is zero.
- The 44-authority geometry-return expansion is also closed. The broad pool contains 85 units/44 declared authorities; after excluding the 52 reviewed baseline units, 33 units/32 authorities remain. Rule v2 fail-closes two `buffer -> WKB -> cascaded_union -> WKT` truncations and one `buffer -> difference` truncation while retaining eight branch-ambiguous sidecars. The remaining 22 units across 18 normalized-body authorities pass boundary review with 11/11 calibration/holdout and zero overlap on all four identities. All 22 pass stable110 mapping, source replay, and description fidelity. Four-layer dedup yields four canonical tasks (convex hull, buffer, centroid, simplify), but all four are suppressed against the existing 124-row pool. Net new training yield is zero and loader/loss is not run for an empty export.
- The next authority-ranked family, `random_point_construction`, is now closed as a composite API pattern rather than a synthetic Processing operator. Its 40 units/32 normalized-body authorities split into disjoint 20/20 calibration and holdout packets (all four identity overlaps are zero). A lexical-scope AST recovery verifies two random draws, bounded point/iteration counters, a point factory, containment and minimum-distance predicates, `setGeometry`, and the declared sink. All 40 pass source replay and map through frozen recovery provenance to existing `L3_02_06_06 Sample Points` (token 97). Scope-faithful deterministic descriptions yield five canonical tasks; none overlaps the 124-row pool, so five isolated `qgis_api_training_sample_v1` train-only rows are granted. Real V4 loader/weighted-loss/backward smoke covers 5/5 with finite loss and gradients, no checkpoint, training run, production merge, or LLM call. The other reviewed anchor, unary union, has only 21 normalized-body authorities after downstream-transform deferrals and remains below the support>=30 gate.
- The remaining mutation/export census is formally closed. The control-path, caller-provenance, and terminal-payload rules produced no new support>=30 family and no train-only row; unary union remains at 21 authorities and deferred. The old v2 census is historical; the current evidence is `docs/reports/qgis_api_remaining_mutation_export_census_v4/` and `docs/reports/qgis_api_unresolved_recovery_v1/`.
- The dispersed 107 unified, nine stable106, one top20, one correction, six exact API, and five random-point rows now form a 129-row cross-pool authority with zero additional suppression. A deterministic diversity selector emits the first 50-row QGIS train-only delivery: six pools, 50 distinct source SHA/regions/call graphs/operator sequences/L3 sequences, and 41 L3 codes. The real V4 loader/weighted-loss/backward path covers 50/50 with finite loss and gradients and no checkpoint or training run. Evidence status remains explicit: 39 `source_reviewed_evidence`, ten `verified_sha256`, and one carried-forward verified row. Authority: `docs/reports/qgis_train_delivery_50_v3/`.
- Stable106 top-15 adjudication freezes five new L3 classes and one stable101 alias. Full-pool mapping-complete coverage rises from 553 to 700, and direct routing from 100 to 125.
- Stable106 direct description fidelity, four-layer deduplication, and source replay yield nine train-only increment rows: nine unique sources and nine unique DAGs. A real V4 loader/loss/backward smoke covers 9/9; validation/test are false and production merge is not granted.
- Read-only replay covers 24 new recovery and 27 new split routes with 51/51 source hashes verified. Structural gates retain only two unadmitted candidates and emit zero training rows.
- Seven existing-L3 mappings have source-reviewed authority. Their replay unlocks two `native:rasterlayerstatistics` direct rows: both pass description fidelity, four-layer deduplication keeps one canonical row, and 1/1 source replay plus real loader/loss/backward passes. Only that isolated train-only row is granted; no training or production merge occurred.
- Stable108 additionally grants Smooth=`L3_02_05_02`/token 106 and Delaunay Triangulation=`L3_06_01_02`/token 107 while preserving stable106 tokens 0-105. Fully normalized mapping-complete coverage rises from 754 to 766, unique chains from 268 to 271, and `defer_mapping` falls from 2,040 to 2,020, with no new direct row.
- Relative to stable106, 87 records leave mapping gaps: 66 are fully normalized and 21 remain partially normalized under `defer_operator_resolution`. The stable108-only 20-record delta is recovery 2, API sidecar 6, alignment exclusion 4, and operator-resolution defer 8; it emits zero training rows.
- Repeated stable108 authority/replay builds are byte-identical. Fifteen focused tests, contiguous unique tokens 0-107, 3,163 unique record IDs, and zero replay training rows all pass.
- Read-only server audit closes the two stable108-only recovery rows: 2/2 source hashes verify and each yields one `gdal:contour -> native:smoothgeometry` local unit, but both fail closed on `control_flow:try` and downstream low-level data transforms. The files differ only by a seven-line harvest header, so canonical authority support is 1<30; structural eligibility and training output are both zero, and the rows remain sidecars.
- Stable113 was frozen and replayed before the newer anti-bloat audit, but training/production never opened and it emitted zero training rows. Option A now marks it `superseded_historical_evidence_only`; tokens 110-112 are unassigned and its direct rows are closed.
- Stable110 freezes only `native:explodelines`=`L3_02_05_16`/108 and `native:splitwithlines`=`L3_02_05_17`/109 after the 235/235 source-verified audit measured normalized source-body support 81 and 70. Five other candidates remain deferred, including `splitvectorlayer` despite support 32 because its multi-output contract is not representable.
- Stable110 now explicitly excludes the incorrect `native:lineintersections -> L3_02_05_06 Split Line at Point` mapping; its fail-closed replay is 775 mapping-complete rows, 274 unique chains, and 127 direct rows. A separate correction authority uses the catalog contract, L3 definitions, and 59 unique source rows to restore the now-unmapped operator to existing `L3_02_02_01 Intersect`. Corrected replay returns to 791/282/129 without adding an L3 or token. The two new direct rows, `9a7cdfe933736366640a4e1c` and `e452e53925dfe7c00eb2a1c4`, now end in Intersect.
- The correction direct loop is complete: both descriptions pass deterministic fidelity; four-layer dedup keeps one canonical and suppresses one exact training-pair duplicate; the canonical row carries forward 1/1 source identity from the frozen 235/235 source-SHA-verified normalized-body authority and verifies 4/4 cached processing call spans. One stable110 train-only JSONL row was exported and passed a real V4 loader/loss/backward smoke in an isolated 110-content-token process. Production vocab, `outputs_v2`, validation/test, and training remain closed; no LLM was called.
- The GEE `mean_clip_core` review is complete at 22 accepted / 13 deferred. The original rule fails (precision 0.6286, Wilson lower 0.4634); the repaired transitive-provenance/type gate matches 35/35 (TP/FP/TN/FN=22/0/13/0, precision 1.0, Wilson lower 0.8513).
- Deterministic task-text replay now covers all 86 repaired-rule mean/clip definitions from 24 source authorities. All 86 pass source SHA, AST, dependency-backlink, and schema gates; normalized text/L3 deduplication retains 27 non-admitted candidates and records 59 duplicates. Of the 27, 26 have one exact public ImageCollection and one uses the generic fallback. A risk-first 20-row audit packet contains the generic row and all eight candidates whose unreviewed temporal facts were omitted. Training/validation/test/production admission remains closed and training rows remain zero.

## Next Actions Across Three Workstreams

- QGIS expansion priority is reset: first build a bounded, auditable high-recall detector for the 23,638 raw `unclassified` sources, then expand provenance-preserving workflows/subworkflows and a separate operator-level semantic package. Candidate yield, admission rate, and coverage gain come before any fixed row target; defer the stable124 training run.
- QGIS data: the formal Processing authority is 294 rows and the full QGIS aggregate is 508 rows. Next: ① the 170-composed full-pool rerun is done: unlock batch 534 candidates -> 15 canonical (13 description variants not merged + the 15-step chain exported isolated + the 52-step chain deferred per precedent); the 87 rows are third-party-provider operators, permanently deferred; ② keep the four gap operators (deleteholes/stringconcatenation/package/orderbyexpression) on the observation list until normalized-body support accumulates - no minimal-extension L3 admission now; ③ the API pool (39,386) is now the main lane: cluster the remaining 13,554 pattern candidates by producer+mutation+sink composite terminal macros and select the next support>=30 family through source-disjoint calibration, full replay, minimal L3, description, dedup, tokenizer, and V4 gates; the Processing residual pools stay closed. Every new row must pass source-disjoint calibration, full-pool replay, exact/minimal L3 contract, deterministic source-fact description, four-layer/cross-pool dedup, real tokenizer gate, and random audit.
- GEE data: jointly review the 20-row repaired-batch audit packet for dataset, temporal, and retained-chain fidelity. Any mismatch returns to deterministic rule repair and full replay; even a clean audit does not grant training admission automatically.
- Benchmark: Gates 1 and 2 are complete. Four hash-bound human decisions pass the state-machine validator: `001/006/007` are approved and admitted to Gate 3, while `008` is `returned_for_revision` because no task intent or output constraint demonstrates semantic closure of the long chain. Gate 3 now contains 149 rows (146 source-backed + 3 expert-authored), 90 source authorities, and 52 distinct DAGs; only two families still meet 8+3 and status remains `failed_insufficient_candidate_supply`. `L3_02_03_05` is a semantic class that intentionally admits dissolve/collect variants, not a one-operator class. Gate 4, development/final/refusal rows, and the family roster remain closed. See `docs/reports/qgis_benchmark_expert_human_approval_v1.md`.

## Hard Boundaries

- The formal mainline does not use an LLM to guess, add, or change chains and does not train.
  The user-approved isolated `qgis_processing_llm_candidate_extraction_pilot_v1` may only
  propose operator IDs with source-line evidence; AST/catalog/single-value verification remains
  authoritative, and the pilot cannot emit L3 labels, training rows, or authority changes. The
  v2 pilot parses each source locally and sends only one bounded Processing-relevant AST scope
  per call with original line numbers; whole-file submission and silent truncation are prohibited.
  Its first five-scope literal baseline returned catalog/span-valid 5/5 (TP=5, FP=0, FN=0), but
  all five scopes came from one source and are protocol evidence only, not recovery capability.
  The source-disjoint literal holdout staged 10 SHA-verified sources read-only from `/home/yll`.
  After one AST-candidate correction and one bounded retry, successful responses cover 8 sources:
  TP=10, FP=0, FN=3 (precision=1.0, recall=0.769); one scope was too large to send and one source
  still returned empty JSON. It is therefore a high-precision but incomplete candidate aid only,
  not an extractor replacement or a gateway to training authority. Contract revalidation found
  the prior ledger dropped returned source lines; v2 now persists `proposed_operator_source_lines`
  and verified lines remain inside their scopes. Empty JSON and oversized scopes stay deferred.
- Do not modify `outputs/`, `outputs_v2/`, `train11397_*`, or `/home/yll`.
- Benchmark planner gold compares only parameter-free QGIS `processes + links`; do not fabricate supply or enter Gate 4 before Gate 3 passes.

QGIS plan: `.omx/plans/2026-07-24-qgis-source-to-training-data.md`. Benchmark
plan: `.omx/plans/2026-07-28-qgis-benchmark-freeze-v1.md`.
## Blocker source-disjoint yield (2026-09-02)

A bounded 60-row audit of the `recover_call_graph` (222 available) and
`review_api_sidecar` (203 available) lanes preserved zero source-SHA overlap between
calibration and holdout. Local SHA/AST replay verified 35 rows; 25 rows lacked a local
source mirror and remain deferred. The fixed rubric measured 6 Gold, 13 Silver, 16 Reject,
and 25 Deferred (19/35 accepted among verified rows). No training rows or authority/eval
changes were made; the 7,567 low-evidence deferred rows were untouched. Results:
`docs/reports/qgis_blocker_source_disjoint_audit_v1/result_v1/`.
