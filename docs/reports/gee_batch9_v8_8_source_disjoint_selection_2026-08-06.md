# GEE Batch9 v8.8 Source-Disjoint Selection

## Decision

Freeze Batch9 as a 5,000-source hard-structure replay batch under the unchanged
v8.8 rules. It is selection-only: no AST replay, facts, task text, train rows, model
training, validation/test admission, or `goal_only` view was generated.

## Boundary

The selection excludes the union of the Batch8 source-exclusion authority (19,078
sources) and Batch8 selected source manifest (17,585 sources): 36,663 unique source
SHA256 values in total. The selected 5,000 source SHA256 values have zero overlap
with that union.

The canonical content manifest and exact-join ledger remain the input authorities.
Every selected source was checked against read-only `/home/yll/GEE/Data` for path,
size, and SHA256 before selection.

## Capacity Result

An attempted 20,000-source quota of `linear_export=15,000`, `helper_export=4,000`,
and `control_flow_export=1,000` was correctly rejected by the exact-quota gate:
after the exclusion boundary, the strict population did not contain 15,000 eligible
linear exports. No Batch9 output was published from that failed attempt.

The measured strict capacity immediately supports 5,000 new hard-structure sources:

| Stratum | Selected sources |
| --- | ---: |
| `helper_export` | 4,000 |
| `control_flow_export` | 1,000 |
| `linear_export` | 0 |

This is a deliberate evidence-based batch size, not a relaxation of the gate.

## Reproducibility

Remote root:
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`.

- Selection A/B `selection.jsonl` SHA256:
  `bd489a279fd904e6b7eccd37f9d6336e44a6de377156bfb35bf9ee0dce3aed80`
- Exclusion union A/B SHA256:
  `a2ec7306fdcf8181197b80dd7c95eda8abd0f0dad10192e690e78ea4d23730bf`
- Both selection manifests contain 5,000 unique source SHA256 values and are
  byte-identical.

The next step is Batch9 AST A/B replay under frozen v8.8, followed by the existing
DAG, fidelity, typed mapping, facts, expansion, and 50-row source-audit gates. The
current 7,971-row Batch8 semantic authority remains unchanged.
