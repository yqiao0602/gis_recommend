# GEE replacement Batch13 v8.9.9 facts/task-text replay

Date: 2026-09-02  
Scope: replacement Batch13, mapping-complete candidates only  
Snapshot: `code_snapshot_v8_9_9_ee_image_lineage_authority`  
Source root (read-only): `/home/yll/GEE/Data/data20000_AST_failed`

## Result

The deterministic `build_gee_workflow_task_facts.py` conversion processed all 266
typed mapping-complete candidates. It produced:

| Artifact | Count |
|---|---:|
| Source/AST-backed fact bundles | 259 |
| Fact fail-closed rows | 7 |
| Task-text candidates before deduplication | 259 |
| Deduplicated task-text candidates | 177 |
| Duplicate sidecars | 82 |
| Risk-review rows | 50 |
| Training rows emitted | 0 |

The first attempt used `/home/yll/GEE/Data` as root; every row failed closed as
`source file missing` because the selected files are nested under
`data20000_AST_failed`. That output was discarded. No extraction rule was relaxed.

## Determinism and admission

Snapshot A was copied to snapshot B. SHA256 matched byte for byte between A and B:

* facts `8ef2ad222e845c588c70ac808e5af76746998fb43ea1d42883ba640290c40f04`
* task text `2fe13d7e7c80e17281b75ab9146be4eebd2f4529e67c51a6a016f38949a095ad`
* duplicate sidecar `164c689e2a458f43f519e5ba3882ca6b12811b677c40b1d14837b0e7b3c7b016`
* fact failures `458d84059dc74e0184f1cb1e79e9d73078d09872db14445ab310cad4b796776c`
* risk packet `f81d701cba77bf20d7769b38817eec44e1beab64c58cdf3d17faca1ac0f56029`
* summary `b7d5561f049c69ea7f398367b00eedb902a47ea4059c1e86f03ca9068678f9f8`
* hash ledger `dffc3a5a6ed1c1ed041466db567fcbf8adf71a893980be50bd1255cf0e123d77`

The generated task text cites only source-backed facts and the retained canonical
operator/L3 sequence; dynamic or private values remain risk flags.

Proposal/export/training, validation/test, and production admission remain closed.
The frozen risk review and deterministic final deduplication are now complete; no
LLM was involved.

## Risk review and final deduplication

The 50-row packet passed 50/50 after two mechanical checker corrections: output
recognition now accepts both `Export.table.toDrive(...)` and
`Export.image.toAsset(...)`. Regression tests cover these forms. Source SHA256,
fact joins, AST span bounds, operator/L3 sequences, fact references, task operator
order, and output-class claims all passed for the sampled rows. No systematic
data-extraction defect was found.

The final deterministic key check retained 177 unique candidate keys and found zero
overlap between candidates and the 82 duplicate sidecars. This is an audit result,
not a training approval; proposal/export/training and validation/test admission stay
closed.

The same mechanical review was run on snapshot B; its output matched snapshot A
byte-for-byte (review SHA256
`fbfb969a345a920c8e02734bd6f5fbfdbe52aae9c6a4a74f9064c577427e98c8`).

Output directories:

`/home/qy/system_redesign/diagnostics/gee_batch13_replacement_5000_v8_9_9_20260816/facts_v8_9_9_snapshot_a`

`/home/qy/system_redesign/diagnostics/gee_batch13_replacement_5000_v8_9_9_20260816/facts_v8_9_9_snapshot_b`
