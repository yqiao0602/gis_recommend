# GEE Complete-Workflow Train-Only V1 Report

## Decision

The first reviewed complete-output-workflow GEE package is admitted for isolated
train-only use. It is not admitted to validation, test, production merge, or a model
training run.

## Frozen Authorities

| Authority | SHA256 |
| --- | --- |
| Risk-review packet | `c33b1528f98b4ed4a0a2e9a1d2dd021d6eb0f61295ea2ce38a1c02101b6a023f` |
| Workflow fact bundles | `feb652c2d5ea0988a5812a5e84a88626b41b8e78a9dada555271d45b9e62e8b6` |
| Task-text candidates | `e804b6fbcbe333c5b365006d1e79fd811776c2d2fa099288c6a194cfadedb846` |
| Closed review report | `3755915fb35ea61628ba0c47dec2bac160ea98588370d4d1ca3508def3e7eeef` |
| Adjudication ledger | `68eca1c40820341ceb647521a6dcfc4087f79901a956fd1f1e7612558c91b879` |
| Frozen stable-94 mapping | `005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558` |

The server's current `outputs_v2/id_mappings_v2.json` contains 107 entries and has a
different hash. The exporter failed closed on that mismatch. The package therefore
uses an explicit frozen copy of the repository's stable-94 authority and does not
modify the server mapping.

## Package Result

| Partition | Rows |
| --- | ---: |
| Explicit adjudication manifest | 50 |
| Reviewed pass | 47 |
| Source-ambiguity defer | 3 |
| Schema-valid complete semantic rows | 47 |
| Current V4-100 train-only rows | 46 |
| Long-sequence sidecar | 1 |
| Fail-closed sidecar | 3 |
| Duplicate sidecar | 0 |

The 47 semantic rows have 47 unique source SHA and exact-DAG authorities. The 46
current-loader rows have 46 unique sources, 46 unique exact DAGs, 44 unique operator
sequences, and 44 unique L3 sequences. The long-chain row has 155 content operators
and requires a model sequence length of 157, so it is not truncated or admitted to
V4-100.

Key artifact hashes:

- `semantic_train_rows.jsonl`:
  `5c2677f81d69f7cbeae155556ebd1bc200b1b96b7e182983f55c0d3e08952c81`
- `train_v4_100.json`:
  `cbaa211d0b0e09ab2f20fe14bf0dc0d7a640a81e1c2a9cc2ccc146cad8483b3b`
- `adjudication_manifest.jsonl`:
  `cfbe757dd0358b61250f9b700ae0e6c8f5a176bbde664854ac150747167b62f1`
- `length_sidecar.jsonl`:
  `cf2c94252ebcef0dd89150025f8b81210b44168d20124c2a10d10bbf271b2af0`
- `fail_closed_sidecar.jsonl`:
  `6e86d5504da840c30dd1460cd6f87d723bac570b08ce69b4162f72dadfbdd0f4`
- `loader_loss_smoke.json`:
  `ff23e678a2cd79117bf92ee859ef7df5de81ca6f90eb93e2f68b7b5c5c4445ac`

## Deterministic Gates

`gis_recommend.gee_workflow_train_row.v1` fixes the training scope as
`complete_output_workflow`. The exporter fails closed unless all joined authorities
agree on `(source_sha256, workflow_id)`, source path, workflow key, schema/status,
calibration stratum, omissions, risk flags, clause lineage, ordered operator chain,
ordered L3 chain, exact DAG, output fact, task text, and clause-to-fact references.
The immutable production profile pins all six authority hashes, the three deferred
identities, and every package count. Stable-94 must contain valid L3 keys mapped
bijectively to non-bool integer IDs `0..93`; normalized task-text-plus-L3
deduplication runs before length routing.

The final server builds are byte-identical:

- `/home/qy/system_redesign/diagnostics/gee_complete_workflow_train_v1_20260731_g`
- `/home/qy/system_redesign/diagnostics/gee_complete_workflow_train_v1_20260731_h`

The synchronized local package is `docs/reports/gee_complete_workflow_train_v1/`.

## Loader/Loss Verification

The real `TaskConditionedL3DatasetV4` and `weighted_sequence_cross_entropy` path ran
under `/home/qy/miniconda3/envs/transformer` with PyTorch 2.2.2:

- rows loaded/seen: 46/46;
- batch shape: `[46, 100]`;
- content/total vocabulary: 94/98;
- max content token: 92;
- max model sequence length: 92;
- mean smoke loss: 4.584967136383057;
- finite loss: true;
- finite non-zero gradient: true;
- checkpoint written: false;
- training run: false.

Fresh focused regression after trust-root hardening is 27 passed and 1 skipped. The
skipped local smoke test requires PyTorch, which is absent from the Windows test
interpreter; the equivalent real server smoke passed. Local and server `py_compile`,
local artifact hash verification, and the final server `_g`/`_h` directory comparison
including smoke passed. The server base Python lacks pytest, so server pytest is not
claimed. Ruff was unavailable and is not claimed.

## Next Gate

The remaining 126 canonical candidates are unreviewed and remain non-admitted. The
next phase applies the same deterministic converter to them and then to a larger
source-disjoint batch. Admission quality is measured with source-disjoint stratified
sampling; any failure changes a reusable rule and triggers full replay. The separate
131 mapping-gap queue does not block this path.
