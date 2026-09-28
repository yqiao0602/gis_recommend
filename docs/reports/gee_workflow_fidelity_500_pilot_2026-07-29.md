# GEE Workflow Fidelity 500-Source Pilot

Date completed: 2026-07-30

## Decision

The fixed-selection replay and deterministic post-DAG fidelity gate are reproducible
and can now feed the next data-construction stage. The 500-source pilot produced 546
complete-DAG, fidelity-passed candidates from 250 unique source authorities. These are
not training rows yet: taxonomy mapping, faithful task text, final deduplication, and
train-only admission remain closed.

This phase did not call an LLM, generate L3 labels, modify a source script, write into
`outputs/` or `outputs_v2/`, or run model training.

## Authority And Reproducibility

The pilot consumed the frozen full-corpus authority and excluded the fixed 50-source
calibration selection by source SHA256.

- DAG authority: `/home/qy/system_redesign/diagnostics/gee_workflow_dag_pilot500_20260729_run3`
- Fidelity replay A: `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260729_a`
- Fidelity replay B: `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_pilot500_20260729_b`
- Selected sources: 500 unique SHA256 values
- Quotas: linear/helper/control-flow = 400/75/25
- Fixed-50 exclusion: 50 unique SHA256 values
- Fixed-50/pilot500 intersection: 0
- Selection rows revalidated against `/home/yll/GEE/Data`: 500/500 schema, size, and byte-SHA checks passed
- AST success/failure: 500/0
- Source statuses: passed 234, partial 16, fail-closed 250
- Training rows emitted: 0

The 500-row `selection.jsonl` and 500-row `workflow_dags.jsonl` account for every
selected source. Twenty-two fail-closed source rows have an empty workflow list, so
they correctly produce no workflow-level fidelity decision: control-flow 10, helper
4, and linear 8. They remain in the source-level denominator and are not silently
dropped.

Core DAG artifact hashes:

| Artifact | SHA256 |
| --- | --- |
| `selection.jsonl` | `f3f1a1c90f24c32aa938b222cdbd0487dec9fc14ae6dafb41bee9d3edc0c48c9` |
| `workflow_dags.jsonl` | `4784421acec33f7fd3a8c38f4e984d8cac7ffdef24ebb86495aa74b6a17eb393` |
| `parse_failures.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `summary.json` | `a2e522417d31622abcdfdb24a8238b129e07c9f8389fe11f55cc8aae196f96bb` |
| `report.md` | `2494085e42815a921eb24cc662604f492579d8cf0d1dbf1f6cc024243bd149f3` |

The DAG hash ledger also binds the canonical manifest, exact facts join ledger,
fixed-50 exclusion manifest, and parser. In particular, the exclusion manifest SHA
is `43d2d6fcfcbf14906aa07c2b2ec2ba8d3a0c2b1709aea0ae5d083645d4582576`.

## Fixed-50 Rule Freeze

The final fixed-50 fidelity replays are:

- `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_fixed50_20260729_c`
- `/home/qy/system_redesign/diagnostics/gee_workflow_fidelity_fixed50_20260729_d`

All seven files are byte-identical across the two runs. Results are 114 workflows:
35 passed, 5 exact duplicates, and 74 fail-closed. The original 73 upstream
fail-closed DAGs remain rejected; none was promoted. Nineteen unique source
authorities support the 35 accepted candidates.

Both controls passed:

- `data300000/script_290909.txt`: the first NDVI export passed and the second
  same-source output was marked `exact_output_duplicate`.
- `data280000/script_289501.txt`: the statically proven `rename('lst')` followed by
  `select('scale')` mismatch was rejected as
  `static_single_band_map_output_mismatch`.

The fixed rule therefore became the authority used by the 500-source fidelity runs.

## Pilot Results

The two 500-source fidelity runs produced the same seven files byte for byte.

- Workflow decisions: 1,105
- Fidelity passed: 546 (49.41%)
- Exact output duplicates: 10 (0.90%)
- Fail-closed: 549 (49.68%)
- Unique accepted sources: 250/500 (50.00%)
- Workflows with external spatial input sidecars: 352/1,105 (31.86%)
- Removed auxiliary accessor calls: 0
- New semantic rejection reasons in this pilot: 0
- Training admission: `not_granted_taxonomy_and_task_text_pending`
- Training rows emitted: 0

Per-stratum accounting uses all selected sources as the source denominator:

| Stratum | Sources | Accepted sources | Source yield | Workflows | Passed | Duplicate | Fail-closed | Workflow pass rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control-flow | 25 | 4 | 16.00% | 27 | 12 | 0 | 15 | 44.44% |
| helper | 75 | 26 | 34.67% | 171 | 72 | 0 | 99 | 42.11% |
| linear | 400 | 220 | 55.00% | 907 | 462 | 10 | 435 | 50.94% |
| total | 500 | 250 | 50.00% | 1,105 | 546 | 10 | 549 | 49.41% |

All 549 rejected workflow decisions retain `upstream_dag_not_passed`. Original
fail-closed evidence occurrences are:

- unresolved dependency: 515;
- unresolved call in dependency closure: 98;
- no core calls: 30;
- control flow in dependency closure: 3.

No statically provable semantic mismatch appeared in this source-disjoint pilot. This
does not weaken the rule: the fixed-50 positive control proves that the mismatch path
is active. It means only that none of these 500 selected sources met the complete
static mismatch predicate.

Fidelity replay A hashes:

| Artifact | SHA256 |
| --- | --- |
| `fidelity_decisions.jsonl` | `2ae8f958f0e382af789e42d1e30aa88d330f651339c4344271fc078cf2cb2bda` |
| `accepted_candidates.jsonl` | `a6175a0de177d97eab5a98f14bcf76ded7674e00e573b0cda6c5bf6d740a29ce` |
| `rejected_ledger.jsonl` | `db214a57fb55d9c702d63471b453d10149aad4f8214b3d58d49dc4b8f1c98979` |
| `duplicate_ledger.jsonl` | `3bae9e4e47ba614c1910c44124c6cc7083188e8c645972c8a098b1a74f33a0d1` |
| `summary.json` | `e49535a08c342440b2f58305d7882083f1ffc857746c79147f9eddcefb67d754` |
| `report.md` | `17152764c7419e5d6c1bb03bfb2c2609837ae1bcfb71f1138280b6a7cb841104` |
| `hash_ledger.json` | `71a207eff693cc50b4f21c9e64e0dd746a6f9dc7d5ec34de5641675795b61237` |

The ledger partition is exact: 546 accepted + 549 rejected + 10 duplicates = 1,105
decisions, with 1,105 unique `(source_sha256, workflow_id)` keys. Accepted, rejected,
and duplicate ledgers have no overlapping keys. All accepted rows are `passed`, all
rejected rows are `fail_closed`, all duplicate rows carry `exact_output_duplicate`,
and every row has `training_rows_emitted=0`.

## Next Production Gate

The next phase must convert the frozen 546 candidates into actual train-only rows,
not enlarge the diagnostic sample first:

1. Freeze the candidate manifest and its AST/DAG hash lineage.
2. Canonicalize the verified core calls and map only exact, supported operations into
   the current L3 taxonomy; unresolved operations remain fail-closed.
3. Generate source-backed dataset, temporal, spatial-input, transformation, and
   output facts from the admitted DAG. Produce task text only from those facts; do not
   use the original whole-script description as authority and do not let an LLM edit
   the chain.
4. Apply task-text fidelity, normalized text plus L3-chain deduplication, schema, and
   train-only admission gates.
5. Review a bounded, risk-stratified calibration sample to repair reusable rules,
   then replay the same deterministic pipeline over all 546 candidates.

Only rows passing every gate can become GEE train-only data. Validation/test admission,
production merge, and model training remain separate decisions.
