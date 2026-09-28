# GEE Project Context

Last updated: 2026-09-02

This file is the durable technical handoff for the GEE data-processing workstream.
Routine sessions start with `docs/GEE_CURRENT_STATE.md`.

## Corpus Authority Decision

The former 11,397-row grafted subset is not the production mother pool. It is a
historical calibration subset derived from earlier filters. Production now starts
from the surviving raw GEE main batches and uses content identity before any workflow
or training decision.

The authority builder is implemented in:

- `src/gis_recommend/data/gee_corpus_authority.py`
- `scripts/build_gee_corpus_authority_manifest.py`
- `tests/test_gee_corpus_authority.py`

Its contract is fail-closed and deterministic:

- explicit allowlist for 31 batches from `data10000` through `data400000`;
- direct `dataNNNNN/script_<id>.txt` paths only;
- byte SHA256 grouping and deterministic canonical selection;
- exact facts join by expected batch plus `File Name`;
- basename-only matches are diagnostics, never authority;
- facts range validation and enumerated failure ledgers;
- directory-level atomic publication with backup preservation on failure.

The facts-coverage unit is
`source_content_sha256_with_exact_instance_join`. Same-content duplicates may inherit
facts support at SHA level, but `join_ledger.jsonl` records only the exact source
instance that joined.

## Verified Full-Corpus Replay

Read-only inputs:

- `/home/yll/GEE/Data`
- `/home/yll/GEE/描述性知识抽取汇总`

Server outputs:

- `/home/qy/system_redesign/diagnostics/gee_corpus_authority_20260729_run1`
- `/home/qy/system_redesign/diagnostics/gee_corpus_authority_20260729_run2`

Verified counts are recorded in `docs/GEE_CURRENT_STATE.md`. All seven artifacts are
byte-identical across the two runs. Key SHA256 values:

- `canonical_sources.jsonl`: `7e6547e66a39c1c07fb05f950718ba15bd3ec3a7ac9ae03519d1e50afddd6752`
- `facts_ledger.jsonl`: `4e6e338421ce1cde92de04331d078c010425201ed6116b7c98c43d58e10617aa`
- `join_ledger.jsonl`: `4c4fd20b9f794804efebcf2bba4d9bc5be25b3670b2b40f4088badcdb89f8f2d`
- `source_instances.jsonl`: `7c7be8e6d55c976ec02c159937ae15cb455669bb3a28c2266de1e65e7f05f7af`
- `summary.json`: `2a09c243117c72240cfc0015e135c47e9e8d51d9025c78e8d5b9600950c646c0`

Focused tests passed locally and on the server: 16/16. The builder, CLI, and tests
also compile successfully. Compact evidence is stored in:

- `docs/reports/gee_corpus_authority_2026-07-29.md`
- `docs/reports/gee_corpus_authority_2026-07-29.summary.json`
- `docs/reports/gee_corpus_authority_2026-07-29.hash_ledger.json`

## Admission Boundary Before DAG Calibration

The 219,914-row canonical source-content manifest is an inventory, not a training
manifest. No training, validation, test, or production admission follows from corpus
membership or facts coverage.

The next gate is complete output-relevant dependency-DAG recovery over a fixed,
source-disjoint calibration sample selected from the canonical manifest. Selection
must require an observable output sink and enough source structure to evaluate full
backward slicing. The calibration must report full-workflow recovery and fail-closed
reasons; it must not promote a locally correct fragment as a complete training row.

Do not repeat the previous failure mode: prolonged row-by-row review of one local
pattern cannot establish a scalable conversion pipeline.

## Complete Output-DAG Calibration

The complete-DAG gate is implemented in
`src/gis_recommend/data/gee_workflow_dag_gate.py` and exercised by
`scripts/build_gee_workflow_dag_calibration.py`. It admits only explicit top-level
Export sinks, follows their backward dependency closure, preserves source order for
core calls, and fails closed on missing computation, unresolved calls, and control
flow in the closure. Presentation sinks such as `Map.addLayer` do not count.

A fixed, source-disjoint 50-source sample was replayed three times with the same
selection SHA256
`43d2d6fcfcbf14906aa07c2b2ec2ba8d3a0c2b1709aea0ae5d083645d4582576`:

- run 1: 11 passed, 39 fail-closed, 73 unresolved dependency occurrences;
- run 2: 18 passed, one partial, 31 fail-closed, 63 unresolved occurrences;
- run 3: 20 passed, 30 fail-closed, 61 unresolved occurrences.

Runs 2 and 3 recognize only source-proven external spatial inputs. Direct
`clip`/`filterBounds` arguments and nested `region` expressions such as
`geometry.geometry().bounds()` become explicit sidecars. Arbitrary unresolved
datasets, images, derived variables, and calls remain fail-closed. Local and server
focused suites pass 16/16.

Run 3 has 114 output DAGs: 41 passed and 73 fail-closed. Source-level pass rates are
15/30 linear, 4/10 helper, and 1/10 control-flow. Four selected sources contain Export
only inside loops or helpers and correctly remain closed because execution order and
cardinality are not proven.

The DAG gate is necessary but not sufficient for training admission. Inspection found
duplicate exports, spatial accessor calls still present in raw core chains, and a
statically suspicious band selection after a different rename. The next gate must be
deterministic and scalable: deduplicate equivalent output DAGs, preserve spatial
sidecars in the input contract, normalize auxiliary calls out of the core chain, and
reject source inconsistencies that can be proven without guessing. No LLM task text or
training row is allowed before that gate.

Detailed evidence:
`docs/reports/gee_workflow_dag_spatial_sidecar_calibration_2026-07-29.md`.

## Deterministic Fidelity Gate And 500-Source Pilot

The post-DAG gate is implemented in
`src/gis_recommend/data/gee_workflow_fidelity_gate.py` and published by
`scripts/build_gee_workflow_fidelity_calibration.py`. It keeps DAG recovery separate
from semantic fidelity and training admission. Its current contract is:

- normalize `.geometry`/`.bounds` only when the receiver root is a proven external
  spatial input;
- reject a band mismatch only when the source statically proves a literal one-band
  select, a map-return rename without return-path `addBands`, and a later different
  literal select from the mapped collection;
- deduplicate only exact same-source output DAG fingerprints;
- preserve source/workflow identity, normalized chain, dependency edges, external
  inputs, removed auxiliary calls, and fail-closed evidence;
- keep every passed row at
  `not_granted_taxonomy_and_task_text_pending`.

The final fixed-50 replays are
`/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_fixed50_20260729_c`
and `_d`. Their seven artifacts are byte-identical. The 114 workflow decisions are
35 passed, 5 exact duplicates, and 74 fail-closed; 19 unique sources support accepted
candidates. All 73 upstream fail-closed DAGs remain rejected. The same-source NDVI
double export is deduplicated, and the known `rename('lst') -> select('scale')` case
is rejected as `static_single_band_map_output_mismatch`.

The source-disjoint pilot authority is
`/home/qy/system_redesign/diagnostics/gee_workflow_dag_pilot500_20260729_run3`.
It contains 500 unique source SHA values, excludes all 50 calibration SHA values, and
meets exact linear/helper/control-flow quotas of 400/75/25. All selection rows passed
schema, size, and byte-SHA replay against `/home/yll/GEE/Data`; AST success/failure is
500/0. Source statuses are 234 passed, 16 partial, and 250 fail-closed.

Fidelity replays `_a` and `_b` under
`/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260729_*`
are byte-identical across all seven artifacts. Results are 1,105 decisions: 546
passed, 10 duplicates, and 549 fail-closed. The accepted set has 250 unique source
authorities. External spatial inputs occur in 352 workflows; removed auxiliary calls
are zero. No new static semantic mismatch appeared, and all rejections retain
upstream DAG evidence. Twenty-two source-level fail-closed rows have no workflow
decision because their DAG workflow list is empty; they remain in the 500-source
denominator.

The ledger partition is exact and disjoint: 546 accepted + 549 rejected + 10
duplicates = 1,105 unique `(source_sha256, workflow_id)` keys. All rows emit zero
training rows. Core authority hashes and per-stratum rates are recorded in
`docs/reports/gee_workflow_fidelity_500_pilot_2026-07-29.md`.

## Current Production Gate

The next phase must turn the frozen 546 candidates into real train-only rows before
expanding the diagnostic sample. Bind candidate/AST/DAG hashes, canonicalize verified
core calls, map only exact supported operations to the current L3 taxonomy, and keep
unresolved operations fail-closed. Build task text from source-backed dataset,
temporal, spatial-input, transformation, and output facts; the original whole-script
description is not authority, and an LLM cannot edit the chain. Task-text fidelity,
normalized text plus L3-chain deduplication, schema validation, and a bounded
risk-stratified calibration must pass before replaying over all 546 candidates.

Validation/test admission, production merge, and model training remain separate and
are not granted by this phase.

## Ordinal-Aligned Typed Operator/L3 Census

The fidelity contract now preserves `normalized_core_call_ordinals` together with
`normalized_core_chain`. Replays on fixed-50 and pilot500 are byte-identical within
each pair, retain the prior 35/5/74 and 546/10/549 dispositions, and have identical
old/new workflow-status projections. Every passed or duplicate row has one-to-one
ordinal/chain alignment.

Stable canonicalization primitives live in
`src/gis_recommend/data/gee_operator_canonicalization.py`. The typed domain gate in
`src/gis_recommend/data/gee_typed_canonicalization.py` reconnects each ordinal to
SHA-keyed AST evidence, requires a `core` classification and exact raw-callee match,
and uses only proven EE receiver types. Production typed modules no longer depend on
the historical P4 CLI script.

Two server census runs under
`/home/qy/system_redesign/diagnostics/gee_typed_l3_mapping_pilot500_20260730_*`
produced six byte-identical artifacts. Across 546 unique workflows and 7,773 retained
calls, 6,871 calls mapped. Results are 266 mapping-complete workflows from 131 unique
sources and 280 fail-closed workflows: 232 retained-core/support-role conflicts, 42
catalog-without-L3 workflows, and 6 raw-call-gap workflows. No evidence mismatch
occurred. Mapping-complete coverage is 158 canonical operators and 56 L3 codes.

All rows remain `not_granted_task_text_and_final_dedup_pending` and emit zero training
rows. The active production gate is source-backed task-fact and faithful-text
construction over only the 266 mapping-complete workflows. The three fail-closed
classes remain separate recovery queues and must not block first production.

Detailed evidence:
`docs/reports/gee_typed_l3_mapping_500_pilot_2026-07-30.md`.

## Source-Backed Workflow Facts And Task Text

The production fact/text gate is implemented by
`src/gis_recommend/data/gee_workflow_task_facts.py` and
`scripts/build_gee_workflow_task_facts.py`. It accepts only an exact composite join
between mapping-complete typed rows and fidelity-passed rows, verifies source SHA and
AST identity, requires every frozen call span and Export sink, and then produces five
fact families from the exact dependency closure: dataset, temporal, spatial input,
transformation, and output.

The initial 266-workflow replay was corrected through deterministic regression tests:
`updateMask` is not a temporal operator; `ee.Date(...)`, `ee.Date.fromYMD(...)`, and
static string date expressions are recoverable; Export region is spatial evidence;
image geometry is not falsely promoted to a bound spatial resource; and positional
Export signatures are parsed separately for image, table, and video exports.

Final server replays `_i` and `_j` under
`/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_*`
are byte-identical across eight artifacts. They produce 266 fact bundles, zero
fact failures, 208 canonical task-text candidates, 58 duplicates, and a 50-row
source-disjoint risk-review packet. Text clauses retain fact IDs, keep frozen
operator/L3 order, redact private assets, and omit dynamic date/spatial claims.
All training admission remains closed. Full evidence is in
`docs/reports/gee_workflow_task_facts_500_pilot_2026-07-30.md`.

## Risk Review Rule Repair And Frozen-AST Replay

The first 50-row risk review exposed reusable deterministic faults: helper actuals
stopped before local aliases, repeated helper spans inflated chains, callback calls
were linearized without structural `map`, partial static objects were discarded,
legacy Export config was not expanded, numeric `ee.Image` constants were rendered as
asset IDs, reviewed public projects were redacted, and stale raw namespaces overrode
proven receiver return types.

Regression-first repairs were applied to the DAG gate, task-fact builder, and operator
canonicalizer. Fixed-selection `--ast-replay-dir` verifies source size/SHA and frozen
Program AST identity without Node reparsing. DAG A/B core data are byte-identical with
500/500 AST success: 149 source passed, 12 partial, 339 fail-closed. Fidelity is 340
passed, 10 duplicate, 755 fail-closed. Typed replay yields 209 mapping-complete
workflows from 102 sources and 131 independent gaps. Fact/text replay yields 209
bundles, zero failures, 176 canonical candidates, 33 duplicates, and 100 sources.

The stable 50-workflow packet was reviewed against exact source SHA across all six
fidelity dimensions. Final adjudication is 47 pass, 3 `defer_source_ambiguity`, and 0
remaining rule fixes. One pass has 155 operators and requires a length sidecar for
the current V4 loader. The zero-row calibration state at this point is superseded by
the complete-workflow delivery below. Current source authority:
`/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_rulefix2_a`.

## Complete-Workflow Train-Only V1 Delivery

The complete-workflow admission boundary is now implemented by
`src/gis_recommend/data/gee_workflow_train_schema.py`,
`scripts/export_gee_complete_workflow_training_package.py`, and
`scripts/smoke_gee_complete_workflow_training_package.py`. The new schema is
`gis_recommend.gee_workflow_train_row.v1` with
`training_scope=complete_output_workflow`; it does not reuse the historical local
`core_subworkflow` contract.

The immutable production profile binds the risk packet, fact bundles, task-text
candidates, closed review report, adjudication ledger, and stable-94 mapping by
SHA256. It also freezes the three deferred identities and all eight package counts.
Expansion produces 50 explicit row decisions and rejects missing, additional,
duplicated, or non-exception defer identities. For every pass, the exporter verifies
source lineage, schema/status, workflow key, calibration stratum, omissions, risk
flags, clause lineage, exact DAG and output facts, clause-to-fact references,
operator/L3 alignment, stable-94 resolution, normalized training-pair deduplication,
and V4 length without truncation.

Final server builds `_g` and `_h` under
`/home/qy/system_redesign/diagnostics/gee_complete_workflow_train_v1_20260731_*`
are byte-identical including the loader/loss smoke artifact. Each contains 47
schema-valid semantic rows from 47 unique source
and DAG authorities, 46 current V4-100 train-only rows, one 155-step length-sidecar
row, three source-ambiguity fail-closed rows, and zero duplicates. The real V4
loader/weighted-loss/backward path covers 46/46 rows with finite loss and gradients,
94 content tokens, 98 total tokens, max token 92, max model sequence length 92, and no
checkpoint or training run.

Fresh verification after the trust-root hardening is 27 focused tests passed and one
local torch-dependent test skipped; server `py_compile` passed. The real server smoke
used `/home/qy/miniconda3/envs/transformer` with PyTorch 2.2.2. The server base Python
does not provide pytest, so no server pytest result is claimed.

The first export failed closed because the server's unrelated `outputs_v2` mapping
contained 107 entries. The final package uses the frozen repository stable-94
mapping with SHA256
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558` and does not
modify either mapping. Detailed evidence is in
`docs/reports/gee_complete_workflow_train_v1_2026-07-31.md`.

This was the boundary before the expansion phase: the remaining 126 candidates could
not be admitted without the same gates and source-disjoint stratified sampling. That
phase is now completed by the census and audit selection below. The independent 131
mapping gaps remain fail-closed and do not block mapping-complete expansion.

## Complete-Workflow Expansion Census And Sampling Gate

The complete-workflow validator was extracted as a reusable fact/text authority
gate, and `scripts/build_gee_complete_workflow_expansion_batch.py` now applies it to
all 126 canonical candidates outside the reviewed 50 identities. The hash-bound
production census routes every remaining identity to exactly one terminal status.
Results are 43 reviewed-source overlaps and 83 source-disjoint proposals, with zero
semantic failures, stable-94 mapping gaps, training-pair duplicates, or V4 length
defers. Proposal status is `pending_sampling_audit`; no train schema is emitted.

The 83 proposals represent 50 unique source authorities. Deterministic risk
classification yields source-representative support of 22 external/dynamic, 5
long/repeated, 9 multi-dataset/private, 7 no-temporal, 1 other, and 6 spatial-omission
sources. A largest-remainder sample of 30 freezes quotas `13/3/5/4/1/4`. Each sampled
source is SHA-replayed below read-only `/home/yll/GEE/Data`, and snippets are bounded
to fact-backed source locations. Human verdict fields remain empty.

Server packages `_a` and `_b` under
`/home/qy/system_redesign/diagnostics/gee_complete_workflow_expansion_v1_20260731_*`
are byte-identical. The original audit JSONL SHA256 is
`c629543fe56fe1d3462466cebb0fbd90a8d25174df9cb33e8cdbb1704bf8ee8d`; the source
manifest SHA256 is `e21f07c6cf3880c993b50e26c49d6b2367f532f39efe87a8def3a96b8d5c42f3`.
The evaluator binds the original selection and permits only
`passed_for_larger_source_disjoint_replay` or `failed_rule_repair_required`. Passing
requires all 30 reviews, point precision >=0.95, Wilson 95% lower >=0.85, and zero
critical chain/L3/fact hallucination failures. It emits no training rows, and an
incomplete production packet was verified to fail closed.

Local audit package: `docs/reports/gee_complete_workflow_expansion_v1/`. Detailed
report: `docs/reports/gee_complete_workflow_expansion_v1_2026-07-31.md`.

## Sampling-Authorized Batch Admission And First Expanded Training Set

The type-gated replay reduced the frozen proposal authority to 78 rows from 45
source authorities. The 30-source stratified review then passed 30/30 with point
precision 1.0, Wilson 95% lower 0.8864866, and zero critical chain/L3/fact failures.
The previous policy treated that result only as permission for another replay. This
was replaced by the production-oriented policy requested for staged yield:
deterministic full-population gates plus a source-disjoint stratified sample authorize
the same frozen rule population. Per-row review is not required after the sample
passes its fixed thresholds.

`scripts/export_gee_expansion_training_batch.py` reruns the hash-bound audit evaluator,
validates proposal permissions and stable-94 mapping, rejects source overlap with the
existing training authority, performs normalized task/L3 deduplication, and writes
both incremental and combined train-only packages. All 78 proposal rows were
admitted with zero duplicates and zero length defers. Combined output is 125 semantic
rows, 124 current V4-100 rows, and the existing one-row 155-step length sidecar.

Server exports `_a` and `_b` under
`/home/qy/system_redesign/diagnostics/gee_expansion_training_batch_v1_20260731_*`
are byte-identical. A real loader/weighted-loss/backward smoke covered 124/124 rows
in one `[124, 100]` batch with finite loss and gradients, max token 92, max model
sequence length 92, and no checkpoint or training epoch. Local package:
`docs/reports/gee_expansion_training_batch_v1/`; report:
`docs/reports/gee_expansion_training_batch_v1_2026-07-31.md`.

The active scaling contract is now yield-oriented: freeze this converter, extend to
200-300 cumulative V4 rows using new source-disjoint batches, audit only 30-50 rows
per batch, and repair a reusable rule only for systematic sampled failures. After
that gate, expand to 500-1000 rows before considering the full corpus.

## Source-Disjoint Batch 2 And The 200-300 Yield Gate

The second expansion applied the same deterministic complete-workflow converter to
the next 500-source authority. The repaired facts replay produced 193 mapping-complete
inputs, 185 fact bundles, 8 fail-closed rows, 157 canonical task-text candidates,
28 duplicates, and 102 candidate sources. Facts A/B outputs are byte-identical.

The independent audit exposed two output-contract defects. An `ImageCollection` was
incorrectly accepted by `Export.table.toDrive`, and a valid
`Export.map.toCloudStorage` workflow was rendered as video. Regression-first repairs
now require provable `ee.featurecollection` input for `Export.table*`, provable
`ee.image` input for `Export.image*` and `Export.map*`, render map output as
`map tiles`, and reject unknown `Export.*` families. The repaired facts/text
authorities differ from the prior run only on the map workflow row. Their SHA256
values are respectively
`34db42c625b18acd6c051c63882f8c4209c9b4991a010d90e2dbd0162e55cbe9` and
`334ae48905d2983d3e065496c948b0b56cf865464d00a578af977dabcbc24bc3`.

Expansion v6 contains 154 proposals from 100 source authorities. Its 30-source audit
excludes the union of 32 previously reviewed sources, keeps the same source manifest
as v5, and changes only the repaired map authority. Twenty-nine exact-authority
reviews were carried forward and `data140000/script_137440.txt` was rechecked against
its full source. The final evaluation is 30/30 pass, point precision 1.0, Wilson 95%
lower 0.8864866068260312, and zero critical failures. The decision
`passed_for_larger_source_disjoint_replay` authorizes the whole same-rule 154-row
population.

The deterministic exporter added all 154 rows with no duplicate or length defer.
Combined output is 279 semantic rows, 278 V4-100 rows, and the existing one-row
155-step length sidecar. Server export A/B directories are byte-identical. A real
V4 loader/weighted-loss/backward smoke covered 278/278 rows in one `[278, 100]`
batch, with finite loss and gradients, max token 92, max model sequence length 92,
and no checkpoint or training run. Validation/test and production merge remain
closed.

The 200-300-row gate is therefore complete. The active gate is now a fresh
source-disjoint expansion to 500-1000 cumulative V4 rows with the v6 converter
frozen, full deterministic population gates, and only a 30-50-source stratified
audit. Detailed evidence is in
`docs/reports/gee_expansion_training_batch2_exportmap_v6_2026-08-01.md`.

## Source-Disjoint Batch 3 And The 500-Row Lower Gate

The next 1,000-source replay used the same output-relevant DAG, typed mapping, facts,
task-text, expansion, sampling, and export boundaries. The first full-source audit
found one critical malformed dataset literal, `LANDSAT/LO08/C01/T1_RT`. Facts had
previously accepted every static dataset string. A TDD repair now rejects an unknown
Landsat platform token when the second path segment has the canonical `L[A-Z][0-9]{2}`
shape. It preserves valid `LC08` and historical `LANDSAT/LC8_L1T_TOA` forms and is
explicitly narrower than full catalog validation.

Facts v5 A/B are byte-identical and partition 368 mapping-complete inputs into 354
fact bundles and 14 fail-closed rows. They produce 296 canonical task texts and 58
duplicates. The new failure is exactly the audited `LO08` workflow. Expansion v5 A/B
are also byte-identical: 288 proposals, 180 eligible sources, six existing or batch
duplicates, and two unadmitted over-length candidates.

After the repair, 28 of 30 audit identities were unchanged. The two replacements, a
35-step ASTER multi-index logical workflow and a JRC wet/dry sibling-export workflow,
were reviewed against full source and passed all six fidelity dimensions. The final
audit is 30/30 pass, point precision 1.0, Wilson 95% lower 0.8864866068260312, and
zero critical failures. It authorizes all 288 same-rule proposals.

The combined delivery contains 567 semantic rows, 566 V4-100 rows, and the existing
155-step length sidecar. Export A/B are byte-identical. Real loader, weighted loss,
and backward smokes on both packages covered 566/566 rows in `[512,100]` and
`[54,100]` batches, with finite loss and gradients and no checkpoint or training run.
The frozen stable-94 mapping came from `configs/taxonomy/inputs/id_mappings_v2.json`;
the mutable `outputs_v2` copy had drifted and was not used.

The next gate is 800-1000 cumulative V4 rows. In parallel, an official GEE STAC
snapshot should be frozen and 57 unique legacy or unverified public dataset IDs should
receive rule-level authority. Fuzzy matching and automatic successor replacement are
not admission evidence. Detailed evidence is in
`docs/reports/gee_expansion_training_batch3_rulefix_v5_2026-08-02.md`.

## Source-Disjoint Batch 4 And The 800-Row Gate

The fourth 1,000-source replay reused the frozen source selection while correcting
three systematic findings from its 30-source audit. Property-level backward slicing
now follows only the referenced key of a statically provable object literal;
`ee.imagecollection.sort` is no longer suppressed when it is output-relevant; and
`ee.Date(Date.now())` is represented as a runtime-current-date argument while
remaining `static_status=partial`. Dynamic keys and unprovable arguments still fail
closed.

The repaired A/B population is deterministic. It contains 285 canonical task
candidates and 275 source-disjoint proposals after ten existing/batch duplicates,
with zero semantic failures and zero length defers. The repaired 30-source audit
passed 30/30 with point precision 1.0, Wilson 95% lower 0.8864866068260312, and zero
critical failures. Only three sampled semantic projections changed; the other 27
retained their operator, L3, DAG, evidence, and task-text projections.

The hash-bound batch exporter admitted all 275 same-rule proposals. Combined output
is 842 complete semantic rows, 841 current V4-100 rows, and the existing one-row
155-step length sidecar. Export A/B directories are identical across all ten files;
the combined semantic and V4 SHA256 values are respectively
`1d58d0f9a07e6c102bd31e4c626dc633f09dbb50420243216091574789cc3c47`
and `fde1964dd7305ecc0f23779b440cd79cbbe02a9b5ac6a15ad32bb187f8516fad`.

Real loader, weighted-loss, and backward smokes on both packages covered 841/841 rows
in `[512,100]` and `[329,100]` batches. Loss and gradients were finite, max token was
92, max model sequence length was 92, and no checkpoint or training epoch ran. The
active gate is now a new source-disjoint replay with v6 frozen to exceed 1,000
cumulative V4 rows. Detailed evidence is in
`docs/reports/gee_batch4_rulefix_v6_training_2026-08-03.md`.

## Source-Disjoint Batch 5 And The 1,000-Row Gate

Batch5 selected 1,000 fresh sources with zero overlap against 3,244 prior source
authorities. Frozen AST replay succeeded for 998 sources and kept two parser failures
closed. The first 30-source audit found a critical false-complete workflow in
`data40000/script_36676.txt`: callback results were collected through `map`, a loop,
and `Array.push`, while the output DAG retained only `Image.cat -> rename`. A TDD
repair now rejects output-relevant bindings mutated through native collection
mutators when their producer closure is not proved. Five workflows receive
`unresolved_mutated_collection_dependency`; four leave the accepted population.

The first replacement source exposed the only reversed literal date interval in the
candidate population, `[2020-01-01, 2019-12-30)`. A second TDD rule rejects static ISO
`filterDate` and `ee.Filter.date` intervals whose start is not before the end, while
leaving wrapping calendar/day-of-year windows unchanged. The invalid row is retained
in `fact_fail_closed.jsonl` and emits no task text.

The final v8 A/B population is deterministic: 552 fidelity-passed workflows, 363
mapping-complete rows, 353 fact bundles, 10 fact failures, 256 canonical task texts,
97 text duplicates, 35 existing/batch duplicates, two length defers, and 219
source-disjoint proposals. The final audit carries 29 unchanged authorities and adds
one full-source-reviewed replacement. It passes 30/30 with point precision 1.0,
Wilson 95% lower 0.8864866068260312, and zero critical failures.

The exporter admits all 219 same-rule proposals. Combined delivery is 1,061 complete
semantic rows, 1,060 V4-100 rows, and the existing one-row 155-step length sidecar,
with zero new export duplicates or length defers. Training A/B directories are
identical. Real loader, weighted-loss, and backward smokes cover 1,060/1,060 rows in
`[512,100]`, `[512,100]`, and `[36,100]` batches with finite loss and gradients; no
checkpoint or training epoch ran.

The cumulative 1,000-row gate is complete. Freeze v8 and expand to 5,000 new
source-disjoint sources, audit 50 stratified source representatives, and target at
least 2,000 cumulative V4 rows. Detailed evidence is in
`docs/reports/gee_batch5_rulefix_v8_training_2026-08-03.md`.

## Source-Disjoint Batch 6, v8.4 Correction, And The 2,000-Row Gate

Batch6 replayed 5,000 fresh source-disjoint sources. Independent full-source review
then revoked the provisional v8.3 50/50 result. One sampled workflow had lost two
variable-bound `ee.Filter.calendarRange` constraints, while another used unsupported
legacy callable `Export.image(...)`. v8.4 restores the typed variable-bound filters
and rejects only callable `Export.image`; supported `Export.image.toDrive`,
`toAsset`, and `toCloudStorage` are unchanged. The full replay routes 17 affected
workflows to fail-closed.

Facts A/B are byte-identical and partition 2,070 mapping-complete inputs into 1,974
fact bundles and 96 failures. They produce 1,321 canonical task candidates and 653
text duplicates. Expansion A/B are also byte-identical: 1,206 proposals from 742
eligible sources, 109 existing/batch duplicates, and six length defers.

Audit inheritance is now keyed by `(source_sha256, workflow_id)` rather than mutable
audit indices. It verifies old/new packet hashes and the full semantic projection.
Forty-seven unchanged identities were carried; corrected/replacement indices 22, 26,
and 50 were reviewed against full source. The final audit is 50/50 pass, point
precision 1.0, Wilson 95% lower 0.9286524008666414, and zero critical failures.

The exporter admits all 1,206 same-rule proposals. Combined delivery is 2,267
complete semantic rows, 2,266 V4-100 rows, and the existing one-row 155-step length
sidecar, with zero new export duplicates or length defers. Training A/B directories
are byte-identical. Real loader, weighted-loss, and backward smokes cover 2,266/2,266
rows in four `[512,100]` batches and one `[218,100]` batch, with finite loss and
gradients and no checkpoint or training epoch.

The 2,000-row gate is complete. v8.4 is the frozen production rule set for the next
larger source-disjoint replay. Production remains batch-level with a 50-row
stratified full-source audit; only systematic sampled failures may trigger a reusable
rule repair and whole-batch replay. Detailed evidence is in
`docs/reports/gee_batch6_5000_v8_4_rulefix_training_2026-08-04.md`.

## Source-Disjoint Batch 7, v8.6 Native-Operator Gate, And The 4,000-Row Gate

Batch7 replayed 10,000 fresh source-disjoint sources. AST succeeded for 9,993
sources. A full-source native-expression review exposed an unsupported
`ee.Image - ee.Image` payload and three EE Image `&&` payloads. v8.6 rejects native
JavaScript operations over EE objects in an output dependency closure, treats
`getInfo()` output as a client value, and limits each declarator's type ownership to
its own initializer. A targeted eight-pattern replay is 4 valid passes / 4 correct
fail-closed decisions. Relative to v8.5, exactly four sources move from passed to
fail-closed and no admitted workflow changes.

The deterministic A/B population contains 3,029 DAG-passed and 311 partial sources.
Downstream replay yields 6,280 fidelity-passed workflows from 3,127 unique sources,
3,809 mapping-complete workflows from 1,882 sources, 3,605 fact bundles, 204 fact
failures, 2,490 canonical task candidates, 1,115 text duplicates, and 2,235 proposals
from 1,321 eligible sources. Seven over-length candidates remain deferred. DAG,
fidelity, typed, facts, and expansion A/B business artifacts are byte-identical.

The v8.6 audit shares 49 identities with v8.5, with zero semantic authority
projection changes. Those 49 full-source PASS decisions are carried by workflow
identity. The removed identity is the confirmed native-operator critical failure;
the replacement `data160000/script_150169.txt` / `output-workflow-3` was explicitly
reviewed against full source and passed. The final evaluation is 50/50 pass, point
precision 1.0, Wilson 95% lower 0.9286524008666414, and zero critical failures.

The exporter admits all 2,235 same-rule proposals with zero duplicate or new length
defer. Combined delivery is 4,502 complete semantic rows, 4,501 V4-100 rows, and the
existing 155-step sidecar. Training A/B directories are byte-identical. Real loader,
weighted-loss, and backward smokes cover 4,501/4,501 rows in eight `[512,100]`
batches and one `[405,100]` batch; loss and gradients are finite, max token is 93,
max model sequence length is 99, and no checkpoint or training epoch ran. Smoke A/B
outputs are byte-identical.

The cumulative 4,000-row gate is complete. v8.6 is frozen for the next fresh
source-disjoint population. Continue deterministic population gates and one 50-row
stratified full-source audit per batch; only systematic sampled failures may trigger
a reusable rule repair and whole-batch replay. Detailed evidence is in
`docs/reports/gee_batch7_10000_v8_6_authority_training_2026-08-05.md`.

## Training-Row Interface Audit And Real Example

A field-level walkthrough verified
`gee_workflow_51e86cacc69bac9c_output_workflow_1` against both the latest Batch7
combined authority and the read-only source
`/home/yll/GEE/Data/data250000/script_246471.txt`. The exported MODIS branch is
correctly isolated from an unrelated Sentinel branch and UI calls. Its source-backed
chain is `filterDate -> median -> clip -> select`, mapped to stable-94 tokens
`50 -> 90 -> 25 -> 28`; the serialized model sequence is
`[-3, 50, 90, 25, 28, -4]`.

This audit clarifies the data contract. The semantic row stores task text, the
auditable GEE operator chain, L3 labels, source/workflow identity, immutable evidence
hashes, admission state, omissions, and sample weight. The current V4 loader consumes
the task prompt and autoregressively supervises the L3 token sequence. It does not
directly supervise GEE operators, QGIS operators, executable parameters, or DAG
edges.

It also exposes a previously unmeasured task-interface problem: the current task name
states the chain length and the description enumerates ordered GEE operations. These
rows are therefore valid source/DAG/L3 authorities and mechanically trainable, but
the current text view leaks the answer for the paper's natural-language planning
objective. Freeze the authorities and derive two views: retain `operator_explicit`
for alignment pretraining/ablation, and create `goal_only` without operator names or
step count for mainline planning. Audit 50 paired rows before training or further
large expansion; do not restart DAG/L3 extraction. Full details and the complete real
JSON row are in
`docs/reports/gee_training_data_contents_and_example_2026-08-05.md`.

Subsequent execution-order decision: data recovery/quality governance and the final
training interface are separate phases. Continue source-disjoint recovery, DAG/L3/fact
gating, deduplication, and sampled rule audits until the target data population is
processed. Only then derive and audit `operator_explicit` and `goal_only` from the
same frozen semantic authorities. The leakage finding remains valid, but it is not a
blocker for further authority production; it becomes a hard gate before model
training and final dataset release.

## 2026-08-06: Batch8 v8.8 band-alias rulefix replay

The fidelity gate now resolves source-order, top-level literal-array aliases used by
`select(bands)`; dynamic, regex, or rebound selectors remain fail-closed. Server
tests pass 33/33. Fresh A/B replay is byte-identical: 17,585 selected sources
(17,567 AST success, 18 failure); fidelity has 39,110 workflows (11,342 passed,
320 exact duplicates, 27,448 fail-closed). The known `script_22112.txt` defect is
closed by `static_band_lineage_select_mismatch`. Typed/facts produced 7,124
mapping-complete workflows, 6,801 fact bundles, and 4,245 task candidates.
Expansion produced 3,469 source-disjoint proposals from 2,035 sources and 26
length sidecars. A fresh 50-row source audit is 50/50 pass with zero critical
failures.

## 2026-08-06: Batch8 v8.8 hash-bound export and V4 smoke

The frozen audit authorized all 3,469 proposals. The hash-bound exporter added 3,469
semantic rows with zero duplicates and zero new length defers. The current combined
authority is 7,971 semantic train-only rows, 7,970 V4-100 rows, and the existing
155-step sidecar. A/B package hashes are identical.

Real `TaskConditionedL3DatasetV4`, weighted-loss, and backward smoke covered all
7,970 V4-100 rows in fifteen `[512,100]` batches and one `[290,100]` batch; losses
and gradients are finite, max token is 93, max model length is 99, and no checkpoint
or training epoch ran. The smoke first fail-closed because remote
`outputs_v2/id_mappings_v2.json` had a mutable SHA different from stable-94. It
passed with `configs/taxonomy/inputs/id_mappings_v2.json` at SHA256
`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.
`scripts/smoke_gee_complete_workflow_training_package.py` now defaults to that
frozen mapping path. Full evidence is
`docs/reports/gee_batch8_v8_8_authority_training_2026-08-06.md`.

## 2026-08-06: Batch9 v8.8 source-disjoint selection

Batch9 freezes 5,000 new hard-structure sources under unchanged v8.8: 4,000 helper
exports and 1,000 control-flow exports. The source boundary excludes 36,663 prior
processed/excluded source hashes; selection A/B is byte-identical and has zero
overlap. An attempted 20,000-source composition fail-closed because the remaining
strict population does not have 15,000 eligible linear exports. This is recorded as
a capacity constraint, not a gate relaxation. Batch9 is selection-only and next
requires AST A/B replay. See
`docs/reports/gee_batch9_v8_8_source_disjoint_selection_2026-08-06.md`.

## 2026-08-07: Batch9 v8.8 AST/DAG A/B replay

The frozen Batch9 population completed its AST/DAG gate under unchanged v8.8.
Both independent runs have 5,000 selected sources, 4,997 AST successes, and three
parse failures held fail-closed. DAG source status is 187 passed, 140 partial, and
4,670 fail-closed. The selection, workflow DAG, parse-failure, and summary business
artifacts are byte-identical; `workflow_dags.jsonl` SHA256 is
`73479cdd3b079f441fef7ea76e40a32d92fe06cee15ee98623afbe25ddcd7340`.

This result does not grant facts, task-text, or train-only admission. The next gate
is fidelity A/B replay, followed by typed mapping, facts, expansion, and a sampled
full-source audit. Evidence is in
`docs/reports/gee_batch9_v8_8_ast_replay_2026-08-07.md`.

## 2026-08-07: Batch9 v8.8 fidelity A/B replay

Batch9 fidelity ran only from the v8.8 controlled snapshot because the live
`gee_workflow_fidelity_gate.py` SHA differed from the snapshot. The two independent
runs consumed the identical DAG authority and produced byte-identical decisions:
11,117 workflows, 644 passed candidates from 306 sources, six exact duplicates, and
10,467 fail-closed. No training row was generated. The next gate is typed
canonicalization/mapping A/B over the passed candidate population. Full evidence is
`docs/reports/gee_batch9_v8_8_fidelity_replay_2026-08-07.md`.

## 2026-08-07: Batch9 v8.8 typed mapping A/B replay

The frozen typed publisher, canonicalizer, stable-94 mapping, v8.5 overrides, and
v2.7 skip-list produced byte-identical A/B outputs for all 644 fidelity-passed
workflows. It admits 355 mapping-complete workflows from 154 sources and fail-closes
289 workflows. The complete set covers 126 canonical GEE operators and 47 L3 codes;
no training row is emitted. The next gate is source/AST-backed facts A/B for the
mapping-complete output. Evidence is
`docs/reports/gee_batch9_v8_8_typed_mapping_replay_2026-08-07.md`.

## 2026-08-07: Batch9 v8.8 source/AST-backed facts A/B replay

The frozen facts publisher replayed all 355 mapping-complete workflows against
read-only source and AST evidence. It produced 339 fact bundles and fail-closed 16
rows; deterministic task-text/L3 deduplication retained 242 candidates from 133
sources and put 97 exact duplicates in a sidecar. A 50-row risk-review packet is
published, but no training row is emitted. The next gate is expansion/proposal A/B
over the canonical candidate population. Evidence is
`docs/reports/gee_batch9_v8_8_facts_replay_2026-08-07.md`.

## 2026-08-07: Batch9 v8.8 expansion/proposal A/B replay

The frozen expansion publisher replayed all 242 Batch9 canonical task-text
candidates using the controlled v8.8 snapshot, read-only source evidence, reviewed
identity exclusions, and the existing Batch8 semantic authority. The A/B business
artifacts, including `hash_ledger.json`, are byte-identical. The resulting partition
is 197 proposal-eligible rows from 114 unique sources, 44 existing/batch duplicates,
one length defer, zero reviewed-source overlaps, and zero semantic failures.

The 50-row stratified full-source packet is frozen with its deterministic quotas;
its status is `pending_sampling_audit`. No training row, validation/test eligibility,
or production merge is granted. A rule change remains permitted only for a
systematic, reusable failure found by that audit. Evidence is
`docs/reports/gee_batch9_v8_8_expansion_replay_2026-08-07.md`.

## 2026-08-07: Batch9 frozen expansion audit failed closed

The hash-bound 50-row full-source audit has 43 pass rows and seven critical failures
(point precision 0.86; Wilson 95% lower 0.7381380628941446). The evaluator decision
is `failed_rule_repair_required`, emits zero training rows, and grants neither
validation/test eligibility nor production merge.

Five independent sources establish the reusable defect: an output-relevant EE value
has loop-carried reassignment, collection mutation, dynamic asset enumeration, or
multiple control-flow reaching writes, but the slice retains only its terminal
operation. The next repair is limited to a fail-closed lineage gate for this pattern,
followed by a full Batch9 A/B replay and new sampled audit. Two singleton defects
(unreachable callback code and impossible literal catalog date range) remain recorded
and fail-closed. Evidence is
`docs/reports/gee_batch9_v8_8_expansion_audit_2026-08-07.md`.

## 2026-08-07: Batch9 v8.9.3 loop-lineage replay and audit freeze

The proven control-flow repair is intentionally fail-closed: it rejects an export
whose output dependency closure is reassigned or redeclared inside pre-sink control
flow when full lineage cannot be statically proven. It does not infer loop semantics
or alter unrelated top-level reassignment. The new DAG result is 4,997 AST successes,
152 passed sources, 133 partial sources, and 4,712 fail-closed sources; 410 sources
carry `unresolved_output_control_flow_lineage`.

All downstream A/B publications are byte-identical under
`code_snapshot_v8_9_3_loop_lineage_facts_ledger_determinism_authority`: fidelity
has 563 accepted decisions, typed mapping has 326 complete decisions, and facts has
315 fact bundles plus 224 deduplicated task-text candidates. The facts ledger was
repaired to write logical `source/<corpus path>` and `ast/<source SHA>.json` keys,
so its A/B ledger now also matches.

The explicit v8.9.3 proposal profile freezes the new authority hashes and expected
partition: 183 proposal rows from 107 eligible sources, 41 duplicate sidecar rows,
and zero length, semantic, or reviewed-source-overlap sidecars. Its stratified
50-source audit packet is frozen as `pending_sampling_audit`, with no train-only,
validation/test, or production admission. Evidence is
`docs/reports/gee_batch9_v8_9_3_replay_and_audit_freeze_2026-08-07.md`.

## 2026-08-07: Batch9 v8.9.5 catalog temporal coverage authority

The next 50-source audit found and fully source-verified two date defects: a
pre-coverage Landsat query and pre-coverage Sentinel-2 queries. The minimal repair
adds `catalog_temporal_coverage_empty` only for supported, exact public
`ee.ImageCollection("<literal>")` IDs with literal `filterDate` or
`ee.Filter.date` bounds whose interval has no catalog intersection. It does not
infer dynamic datasets or dates.

Under the controlled
`code_snapshot_v8_9_5_catalog_temporal_filter_authority`, the full Batch9 replay is
A/B byte-identical: fidelity has 545 accepted workflows (six duplicates and 10,566
fail-closed), typed mapping has 323 complete workflows from 140 sources, facts has
312 bundles and 221 canonical candidates, and expansion has 180 proposals from 105
sources plus 41 duplicates. The replacement hash-bound audit is 50/50 pass with no
critical failure and Wilson lower bound 0.9286524008666414, so its evaluator grants
larger source-disjoint replay.

The hash-bound exporter adds all 180 proposals with zero new duplicate or length
defer. The combined authority is 8,151 semantic rows, 8,150 V4-100 rows, and one
existing 155-step sidecar. In the server `transformer` environment (PyTorch
2.2.2+cu121), real `TaskConditionedL3DatasetV4`, weighted loss, and backward smoke
read 8,150/8,150 rows in sixteen batches; loss/gradients are finite and A/B smoke
outputs are byte-identical. No checkpoint or training epoch ran. The frozen
stable-94 mapping SHA is `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`.
Evidence: `docs/reports/gee_batch9_v8_9_5_authority_training_2026-08-07.md`.

Local GEE regression commands must set `PYTHONPATH=src`; otherwise a parent legacy
`gis_recommend` package shadows the workspace implementation and yields false test
failures. The focused v8.9.5 tests pass as 40 passed and one torch-dependent skip
when run against the workspace source.

## 2026-08-08: Batch10 v8.9.6 expression-band lineage repair

Batch10 selected 2,000 new source-disjoint sources. Its v8.9.5 A/B replay reached
37 pending proposals from 30 eligible sources, but full-source review identified a
reusable fidelity defect: `ee.Image.expression()` creates the default `constant`
band unless renamed, while a retained downstream static `select('HV')` was accepted.
The v8.9.6 controlled snapshot records expression output lineage as `constant`,
propagates static checks into expression arguments, and rejects only provable
mismatches. Local pytest and remote unittest both pass 64 focused tests.

The full Batch10 replay is byte-identical A/B: 143 fidelity candidates (82 sources),
57 mapping-complete workflows (43 sources), 55 fact bundles, 48 canonical task-text
candidates, and 36 pending proposals from 29 eligible sources. `exhaustive_29` is a
full-coverage audit of this batch; no row was exported or merged, and the 8,150-row
Batch9 v8.9.5 authority remains unchanged.

The completed `exhaustive_29` audit has 28 pass rows and one fail-closed row,
`data300000/script_304794.txt` / `output-workflow-1`. The output-relevant chain
uses loop-derived `annual_col` imagery, but its dataset facts and task text retain
only the Laos boundary FeatureCollection. A deterministic Batch10 census finds that
this is the only missing ImageCollection dataset fact among 37
ImageCollection-chain bundles, so it is not evidence for a reusable extractor
change. The frozen row remains excluded. The hash-bound evaluator reports point
precision `0.9655172413793104`, Wilson lower `0.8282447812067973`, and
`failed_rule_repair_required`; this policy result denies Batch10-wide admission.
Evidence: `docs/reports/gee_batch10_v8_9_6_full_audit_2026-08-08.md`.

## 2026-08-09: Batch11 v8.9.6 source-disjoint selection

Batch11 expands from the frozen v8.9.6 rule set without revisiting the isolated
Batch10 fact omission. The exclusion authority combines 43,663 prior or touched
source hashes. Selection A/B is byte-identical and freezes 5,000 new sources:
2,500 `helper_export` and 2,500 `control_flow_export`. This is selection-only;
AST/DAG replay, facts, proposals, training admission, and merge remain pending.

The initial Batch11 DAG invocation is superseded, not a corpus result: the detached
environment could not resolve `node` and then Acorn, so it emitted 5,000 parser
environment failures and zero DAGs. A one-source smoke confirms the existing Acorn
runtime emits a location-bearing Program AST when `NODE_PATH` is set to
`/home/qy/system_redesign/.runtime/gee-ast-parser/node_modules`; the valid replay
also explicitly supplies `/home/yll/.local/node-20/bin/node`.

## 2026-08-10: Batch11 v8.9.6 valid replay through typed mapping

With the explicit Node/Acorn runtime, Batch11 AST/DAG A/B is valid and
byte-identical: 4,995 AST successes, five parse failures, 9,069 workflow DAGs, and
source statuses of 143 passed, 98 partial, and 4,754 fail-closed. Its fidelity A/B
replay is also byte-identical: 388 passed candidates from 217 sources, 14 exact
duplicates, and 8,667 fail-closed decisions.

The frozen v8.9.6 typed publisher was run independently over each fidelity output
with the stable-94 mapping, v8.5 overrides, and v2.7 skip list. It yields 206
mapping-complete workflows from 125 sources, 182 fail-closed workflows, 107
canonical GEE operators, and 42 L3 codes. The five business artifacts and hash ledger
are byte-identical; the source-root evidence is
`/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/typed_v8_9_6_{a,b}`.
No facts, task text, proposal, export, or training row is authorized. The immediate
next gate is the source/AST-backed facts A/B replay on `mapping_complete_candidates.jsonl`.
Evidence: `docs/reports/gee_batch11_v8_9_6_typed_mapping_replay_2026-08-10.md`.

## 2026-08-10: Batch11 audit failure and v8.9.7 controlled repair

The Batch11 v8.9.6 50-source full-source audit verifies all source SHA256 values but
fails admission: 47 pass, three critical failures, precision 0.94, and Wilson lower
0.8378290831116182. One source proves an omitted public catalog coverage interval for
`COPERNICUS/S2_SR_HARMONIZED`; two independent sources prove that `sort` is
output-relevant before `first()` or `mosaic()` and cannot be globally skipped. The
v8.9.6 95-proposal population is therefore unadmitted.

v8.9.7 adds only the known S2 SR Harmonized lower bound and derives a versioned skip
authority removing only `ee.imagecollection.sort`; stable-94 already maps it to
`L3_03_09_07`. A controlled replay from the valid Batch11 DAG A/B is byte-identical
at every downstream stage: 387 fidelity-passed, 205 mapping-complete, 199 facts,
134 canonical task-text candidates, and 93 pending proposals from 76 sources. The
fresh 50-source audit packet is frozen; it must be reviewed before hash-bound export.
Evidence: `docs/reports/gee_batch11_v8_9_6_audit_and_v8_9_7_replay_2026-08-10.md`.

## 2026-08-10: Batch11 v8.9.9 EE-image-lineage repair and audit

The fresh v8.9.7 audit found one critical temporal-coverage failure: a
`COPERNICUS/S2_HARMONIZED` request was entirely before its 2017-03-28 catalog start,
but a one-argument `ee.Image(collection...median())` wrapper lost the proven
collection lineage before the temporal gate. v8.9.9 makes that wrapper lineage
transparent and records the S2 Harmonized lower bound. The focused fidelity-gate test
suite passes `40/40`.

From the valid Batch11 DAG A/B, the v8.9.9 fidelity through proposal replay is
byte-identical: 386 fidelity-passed workflows, 204 mapping-complete workflows, 92
pending proposals from 75 eligible sources, 40 duplicates, and one length sidecar.
The frozen audit sample and source manifest SHA256 are
`221fd1e4a9d702b9143e5dd2c017b8ade1ddf37736be377669ba87f68eae3fad` and
`d20ea5c5475cca843ac8ee30e7d3d8f4d7b3b12918009342237d323a45d873b4`.

All 50 sampled source hashes were recomputed from read-only `/home/yll/GEE/Data` and
matched. Full-source review passed dataset, temporal, spatial, output-relevant DAG,
output closure, and task-text fidelity for every row; critical failures are zero. The
hash-bound evaluator result is 50/50 pass, precision 1.0, Wilson 95% lower
0.9286524008666414, and `passed_for_larger_source_disjoint_replay`. Audit artifacts
are under `/home/qy/system_redesign/diagnostics/gee_batch11_5000_v8_9_6_20260808/audit_v8_9_9_full/`.
The subsequent hash-bound exporter produced byte-identical A/B packages and admitted
all 92 rows (zero duplicate and zero new-length defers). The combined authority is
8,243 semantic train-only rows, 8,242 V4-100 rows, and one existing 155-step sidecar.
Real V4 loader/loss/backward smoke covered every 8,242-row A/B package in 17 batches,
with finite loss/gradients, no checkpoint, and no training run. Batch11 is therefore
admitted only to the GEE train-only authority; validation/test and production merge
remain closed.

## 2026-08-10: Batch12 v8.9.9 source-disjoint selection

Batch12 extends only after Batch11 train-only admission. A fresh cumulative exclusion
authority combines the prior 43,663-source union with Batch11's 5,000 selected
sources. Both exclusion builds are byte-identical: 48,663 unique selector-compatible
source SHA256 values, with no duplicate or incompatible source records.

Using that frozen exclusion selection, Batch12 A/B freezes 5,000 canonical sources:
2,500 `helper_export` and 2,500 `control_flow_export`. The selection manifests and
hash ledgers are byte-identical; all 5,000 selected source hashes are unique and have
zero overlap with the 48,663 excluded hashes. This is selection-only and emits no
facts, text, proposals, or training rows. The next gate is AST/DAG A/B replay under
the controlled v8.9.9 code snapshot.

## 2026-08-10: Batch12 v8.9.9 full replay and audit failure

The controlled v8.9.9 replay completed with byte-identical A/B business artifacts.
AST/DAG processed all 5,000 selected sources: 4,994 AST successes, six parse
failures, and source statuses of 227 passed, 119 partial, and 4,648 fail-closed.
Fidelity produced 699 accepted workflows from 313 sources; typed mapping retained
338 complete workflows from 166 sources; facts produced 335 bundles and 228
deduplicated task-text candidates from 130 sources. The expansion profile used the
current 8,243-row semantic authority as cross-batch dedup base and retained 105
pending proposals from 66 eligible sources after 26 duplicate and 47 reviewed-source
overlap exclusions.

The frozen source-disjoint 50-source audit recomputed every source SHA256 against
read-only `/home/yll/GEE/Data` and found 37 pass plus 13 critical failures. The
hash-bound evaluator reported precision `0.74`, Wilson 95% lower `0.6044684273515117`,
and `failed_rule_repair_required`; training rows remain zero. The critical cases all
show the same reusable defect: loop/list/map/helper-created exported objects can lose
output-relevant upstream datasets, filters, and transformations while a terminal call
remains extractable.

Batch12 is fully unadmitted. Do not export its 105 proposals or run training smoke.
The next repair must be minimal and fail-closed for this precise control-flow
upstream-lineage gap, followed by a full replay from the frozen AST/DAG inputs and a
replacement 50-source audit. Evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/`; report:
`docs/reports/gee_batch12_v8_9_9_full_audit_2026-08-10.md`.

## 2026-08-10: Batch12 v8.9.9 snapshot-authority repair and replacement audit

The prior Batch12 replay used the live DAG gate SHA `472607...`; the frozen v8.9.9
snapshot gate SHA is `4cb297...` and contains the existing loop-carried and unresolved
output control-flow lineage predicates. A directed replay of the 13 critical source
hashes made all 13 fail-closed, so no new permissive predicate was introduced.

The complete snapshot-authority A/B replay is byte-identical: 4,994 AST successes,
six parse failures, DAG statuses 135 passed / 105 partial / 4,754 fail-closed, 467
fidelity candidates, 219 mapping-complete workflows, 218 fact bundles, 162 task-text
candidates, and 70 proposal rows from 41 sources. The proposal hash ledger is
`772218209cae88a9a407bd51b9ee6c1e889a210b37bfd59c816445adc7db3223`.

Only 41 independent eligible sources remained after the repair. Reusing rejected
sources to reach 50 would invalidate source independence, so all 41 were audited
exhaustively. The replacement audit passed 41/41 with zero critical failures;
precision is 1.0 and Wilson 95% lower is 0.9143324298155681. The evaluator decision
is `passed_for_larger_source_disjoint_replay`. Batch12 is still not admitted; the
next gates are hash-bound export and real V4 loader/loss/backward smoke. See
`docs/reports/gee_batch12_v8_9_9_snapshot_authority_replay_audit_2026-08-10.md`.

## 2026-08-11: Batch12 export and loader/loss smoke

The 41 exhaustive-audit pass sources passed the hash-bound exporter: semantic=41,
V4-100=41, duplicate=0, fail-closed=0, and length sidecar=0; maximum model
sequence length is 20. Package directory:
`/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/export_snapshot_authority_41/`.
All authority and artifact hashes are recorded in `hash_ledger.json`.

The real `TaskConditionedL3DatasetV4`, weighted loss, and backward smoke covered
41/41 rows in two batches with finite loss and gradients; no checkpoint or
training run occurred. Because the server default Python lacks torch, the smoke
used local PyTorch 2.7.1 CPU against the copied hash-bound package; it must be
rerun on the training host before training. The package may enter an incremental
train-only manifest. Validation, test, production merge, and training remain
closed. See `docs/reports/gee_batch12_v8_9_9_snapshot_export_smoke_2026-08-11.md`.

## 2026-08-16: Replacement Batch13 DAG and fidelity

The old Batch13 directory duplicated Batch12 (selection `2bdadd...`, audit
`983537...`, proposal ledger `772218...`) and is diagnostic-only. The replacement
batch excludes 53,663 prior sources, freezes 5,000 new SHA-disjoint sources
(selection `61f737...`), and has zero overlap with Batch12, invalid Batch13, or its
exclusion set. Snapshot v8.9.9 DAG A/B is identical (4,993 AST success, seven parse
failure; 120 passed / 124 partial / 4,749 fail-closed). Fidelity A/B is also identical:
454 passed candidates from 228 unique sources, 17 duplicates, and 8,939 fail-closed.
No downstream mapping, facts, proposal, export, or training admission is granted.
## 2026-09-02: replacement Batch13 facts/task-text replay

The frozen v8.9.9 facts builder was run against the 266 mapping-complete candidates
from replacement Batch13. The source root was corrected to
`/home/yll/GEE/Data/data20000_AST_failed`; the initial run against its parent safely
failed closed all rows as missing files and was discarded. With the corrected root,
the deterministic builder produced 259 `source_backed_complete` fact bundles, 177
deduplicated task-text candidates, 82 duplicate sidecars, seven fact fail-closed
rows, and a 50-row risk review packet. No LLM was used. A/B snapshot directories
were copied and all seven business artifacts (facts, task text, duplicate sidecar,
failures, risk packet, summary, and hash ledger) were byte-identical. The frozen
50-row mechanical risk review passed 50/50. Two checker regex gaps were repaired
(`Export.table.toDrive` and `Export.image.toAsset`) and covered by regression tests.
Final deterministic deduplication retained 177 unique candidate keys with no overlap
against the 82 duplicate sidecars. Training, proposal, export, validation/test, and
production admission remain closed.

## 2026-09-02: replacement Batch13 proposal census

The 177 reviewed task-text candidates were routed through the frozen expansion
census against the combined Batch11+Batch12 semantic authority. Results: 127
remaining identities, 26 reviewed-source overlaps, 25 existing-authority
duplicates, and 76 proposal-eligible rows; semantic failures and length defers were
zero. A 35-source stratified audit packet was emitted. Snapshot A/B proposal
artifacts and hash ledgers are byte-identical. All 76 remain
`pending_sampling_audit`; no export or training admission is granted.
