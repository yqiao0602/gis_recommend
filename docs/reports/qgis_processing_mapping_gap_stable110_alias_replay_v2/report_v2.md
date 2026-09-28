# QGIS Processing Stable110 Existing-L3 Alias Replay v2

Date: 2026-08-01

## Decision

This phase grants three additional **Processing train-only** rows under the
existing stable110 taxonomy. It does not add L3 classes or tokens, merge
production data, run training, or call an LLM.

The cumulative admitted Processing count is now **168**. The next milestone is
200 rows, leaving 32 rows to recover through the same batch gates.

## Batch Funnel

| Gate | Result |
| --- | ---: |
| Existing-L3 aliases granted | 9 |
| Single-gap records covered | 21 |
| Full stable110 replay rows | 3,163 |
| Mapping-complete rows | 828 |
| Direct rows | 150 |
| Direct description fidelity passed | 77 |
| Newly routed direct rows | 17 |
| New direct fidelity passed | 9 |
| Source replay deferred because source is missing | 3 |
| Exact training-pair duplicates | 3 |
| Canonical candidates | 3 |
| Source replay verified | 3/3 |
| Train-only rows exported | 3 |

The 17 newly routed direct rows are not training rows. Eight fail deterministic
description fidelity, three have no verifiable source replay, and three are
exact training-pair duplicates. Only the remaining three canonical rows pass
every admission gate.

## Source And Dedup Evidence

- Canonical selection prioritizes `verified_source_ast` over input order.
- Rows explicitly marked `source_file_missing` are routed to
  `source_replay_deferred` and cannot occupy a canonical key.
- The three canonical rows cover three source authorities, three source SHA256
  values, and three distinct DAGs.
- All three pass source SHA, AST, and Processing call-span verification.
- Cross-pool dedup compares against 176 existing QGIS authorities: 129 rows in
  the unified authority plus 47 rows in the prior Processing second batch.

## Description And Split Replay

Deterministic description replay v4 covers all 150 direct rows. It passes 77
and defers 73; 139 rows have verified source AST evidence and 11 remain missing
source files. The policy uses operator DAG and source-backed literal parameters,
not legacy task text or generated descriptions.

Split replay covers 183 parent rows and 801 units. Only nine multi-step units
pass the structural boundary gate and six of those pass description fidelity.
The newly unlocked split parent produces only independent single-step units, so
it contributes no train-only row.

## Loader And Loss Smoke

The exported JSONL contains three rows under
`qgis_existing_l3_increment_v1`/stable110. A real
`TaskConditionedL3DatasetV4` loader, weighted sequence cross-entropy, and
backward pass cover 3/3 rows in one `[3, 100]` batch. Loss and gradients are
finite. No checkpoint or training run is produced.

Training JSONL SHA256:

```text
afdaec72cf5b7de779c5a271930c856c93fdd63dc5e15d884e3914e8dfea8099
```

## Authority Files

- `exact_l3_authority_v1/`: nine existing-L3 alias decisions.
- `replay_v3/`: 3,163-row stable110 replay.
- `direct_descriptions_v4/`: deterministic fidelity evidence.
- `split_units_v4/`: split summary and hash ledger.
- `direct_increment_audit_v6/`: four-layer and cross-pool dedup ledger.
- `direct_source_replay_v6/`: canonical source replay.
- `train_only_increment_v6/`: three-row JSONL, smoke result, and hashes.

## Next Gate

Continue the Processing ladder with another existing-L3 family batch. Calibrate
operator families once, replay the frozen pool, generate deterministic
descriptions, verify source authority, deduplicate against the now 179-row
cross-pool authority, and export only canonical train-only rows. Do not switch
to the 39,386-row API pool until Processing reaches the 200-300 milestone and
passes its staged audit.
