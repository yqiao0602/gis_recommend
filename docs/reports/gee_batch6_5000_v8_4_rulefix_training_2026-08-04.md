# GEE Batch6 5,000-Source v8.4 Train-Only Delivery

Date: 2026-08-04

## Scope

This phase applied the complete output-relevant GEE workflow converter to 5,000
fresh source-disjoint sources. `/home/yll/GEE/Data` remained read-only. No QGIS data,
benchmark data, `outputs*`, `train11397_*`, model checkpoint, or training epoch was
modified or run.

## Audit Correction And Rule Repair

Independent full-source review invalidated the earlier v8.3 claim of 50/50 passes.
`data160000/script_155999.txt` used two variable-bound
`ee.Filter.calendarRange` filters, but the old task facts omitted the month and year
constraints. `data240000/script_232718.txt` used legacy callable
`Export.image(image, description, config)`, for which the current pipeline has no
execution authority.

v8.4 uses the existing typed variable-binding recovery to preserve both calendar
filters and adds a narrow fail-closed rule for callable `Export.image(...)`. The rule
does not reject `Export.image.toDrive`, `Export.image.toAsset`, or
`Export.image.toCloudStorage`. Seventeen affected workflows now fail closed.

The rule regression is covered by `tests/test_gee_workflow_task_facts.py`. The
identity-based adjudicator now carries prior decisions only by
`(source_sha256, workflow_id)`, requires old/new audit hashes, verifies the complete
semantic projection, and leaves changed or replacement rows for explicit review.

## Deterministic Population

The v8.4 facts and expansion A/B replays are byte-identical.

| Stage | Result |
| --- | ---: |
| Mapping-complete inputs | 2,070 |
| Fact bundles | 1,974 |
| Fact fail-closed | 96 |
| Canonical task candidates | 1,321 |
| Task-text duplicates | 653 |
| Proposal population | 1,206 |
| Eligible proposal sources | 742 |
| Existing/batch duplicates | 109 |
| Length defers | 6 |
| Stratified audit rows | 50 |

Key hashes:

- fact bundles: `62292b30230284036fe60c7d66792eeccd247fe36cc0bb8697219f0e990f86f7`
- task candidates: `45696264ae6c793d518f31c8cb896440db17cb9d605634b3c36e06945661f9a2`
- proposals: `955c16404e72a7c3c765d99cbe864ca6f0504a3c58449748da5ecc39053828c7`
- stable-94 mapping: `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`

## Audit And Admission

The final manifest carries 47 unchanged prior pass identities. Three rows were
reviewed explicitly against full source:

- index 22 restores month `[2,5]` and year `[2021,2021]` calendar filters;
- index 26 is the independent Landsat-5 `La5` output branch;
- index 50 is the 2020 `rcp85` NASA/NEX-GDDP output branch.

The reviewed packet has SHA256
`5866b11e5692b7e0f113c83ae569a1747b8e63ca1dcadb729f386801eda14663`.
All 50 rows pass dataset, temporal, spatial, transformation, output, and task-text
fidelity. Point precision is 1.0, Wilson 95% lower is 0.9286524008666414, and critical
failures are zero. The evaluator decision is
`passed_for_larger_source_disjoint_replay`.

## Train-Only Package

The exporter admitted all 1,206 same-rule proposals. There are no new export
duplicates and no new over-length rows. The combined package contains:

- 2,267 complete semantic train-only rows;
- 2,266 current V4-100 rows;
- one existing 155-step length sidecar;
- validation/test eligibility false;
- production merge not granted.

Training A/B directories are byte-identical. Combined semantic SHA256 is
`47dfe4bc2ab65dff217ba1f4d3f8f78f8a27ff1f1f3579a36549a3b6b554f7b2`;
combined V4 SHA256 is
`f1e63380e8ec2f42d714a743c9095ab108462756c1bc6ad8adf7651bce959bd1`.

## Loader And Loss Smoke

Real `TaskConditionedL3DatasetV4`, weighted sequence loss, and backward smokes ran
twice under `/home/qy/miniconda3/envs/transformer` with PyTorch 2.2.2. Each run
covered 2,266/2,266 rows in batch shapes `[512,100]` four times and `[218,100]` once.
Loss and gradients are finite, max token is 92, max model sequence length is 92, and
no checkpoint was written. Smoke summaries are byte-identical with SHA256
`63373e9699a3c5ce150fa15aa0fc90f60831690590e9a692654c40767f4f1e84`.

Local focused regression is 87/87 passed. Server base and transformer Python do not
contain pytest; server integration evidence is the real evaluator, two independent
exports, two real PyTorch smokes, and script compilation. The first export command
failed before writing output because the repository uses a `src/` layout; rerunning
with `/home/qy/system_redesign/src` in `PYTHONPATH` succeeded.

Server authority root:

`/home/qy/system_redesign/diagnostics/gee_batch6_5000_authorities_v8_20260803`

The next gate freezes v8.4 and applies it to a larger fresh source-disjoint batch.
Production remains batch-level with a 50-row stratified full-source audit; only a
systematic sampled failure may trigger one reusable rule repair and whole-batch
replay.
