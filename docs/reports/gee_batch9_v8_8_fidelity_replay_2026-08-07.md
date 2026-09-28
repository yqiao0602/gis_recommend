# GEE Batch9 v8.8 Fidelity A/B Replay

## Decision

Batch9 completed the deterministic post-DAG fidelity gate under the unchanged v8.8
snapshot. The two runs are byte-identical for every business artifact. This remains
a recovery-stage authority: no typed mapping, facts, task text, training rows, or
model-training artifacts were emitted.

## Frozen Rule Authority

The live fidelity-gate module was not used because its SHA256 differs from the
frozen v8.8 snapshot. Both runs used
`code_snapshot_v8_8_band_alias_rulefix_authority`:

- `gee_workflow_fidelity_gate.py`:
  `c47a570511f28016ebb1ed9f4018879bc2e5843b8eb8512ccbd87224f463f2a6`
- `build_gee_workflow_fidelity_calibration.py`:
  `389f84500de36f2fcbd1c1e4bb18cc5ad8414176fa0eb309017a4799ad0b9388`

The A/B DAG input is identical, with `workflow_dags.jsonl` SHA256
`73479cdd3b079f441fef7ea76e40a32d92fe06cee15ee98623afbe25ddcd7340`.

## Results

- Sources: 4,997 AST-success sources.
- Workflow decisions: 11,117.
- Fidelity passed: 644 candidates from 306 unique sources.
- Exact duplicates: 6.
- Fail-closed: 10,467.
- Training rows emitted: 0.

The deterministic fail-closed counts include 10,398 upstream-DAG-not-passed rows,
and additional structural rejection for 54 parallel collection branches, 9 mutable
container dependencies, 3 parallel image fan-ins, 2 empty image-select roots, and
one static band-lineage mismatch. These are preserved as rejections, not relaxed
admission rules.

## A/B Evidence

The A/B artifacts are byte-identical:

- `fidelity_decisions.jsonl`:
  `209a5e16d0bae21f8283bf8609fcdc4027aecc3c7c3fceed9ff7cbf1d130b27b`
- `accepted_candidates.jsonl`:
  `aef0a935d177aa5e2a19f24a5441e415fdfdb15d82fdb41c8e8acf942be34ac4`
- `rejected_ledger.jsonl`:
  `4c4e722d4947a8f85fff83c7ee0051bc91ad9d20755b8c5df8401e87e837c370`
- `duplicate_ledger.jsonl`:
  `c9a9ede3817e1557887ced24a2835e5d68432bd0d60a1139db369f32aeaa0cfa`
- `summary.json`:
  `343240d6aff96dea165e7bcd2a66094241b18095755020508d5cd8fa3a431b77`

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`.
The authoritative directories are `fidelity_v8_8_authority_a` and
`fidelity_v8_8_authority_b`.

## Next Gate

Run the unchanged v8.8 typed canonicalization/mapping A/B replay using only the
644 fidelity-passed candidates. Continue fail-closed for unmapped or ambiguous
operators; no task-text or train-only admission is granted at this stage.
