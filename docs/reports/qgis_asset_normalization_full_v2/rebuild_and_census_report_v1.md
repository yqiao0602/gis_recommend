# QGIS Asset Miner / Normalization v2 rebuild + census sanity check

This is a **v2 rebuild**, not a v1 restore. The v1 normalized ledger
(`45a1c12d…`) existed only on the compute server and was lost when
`/home/qy/system_redesign/diagnostics/` was deleted; only a 1 KB summary had been
mirrored. v2 re-derives the whole asset ledger from local manifests plus the
intact read-only `/home/yll` sources, and both merged ledgers are now hash-bound
with a second copy. No v1 directory was overwritten. Training rows: 0. Authority,
evaluation splits, and checkpoints: unchanged.

## Result — v2 measured, not reproduced

Normalized asset pools (47,852 rows in, 47,852 out):

| Asset type | v1 | **v2** | Δ |
|---|---:|---:|---:|
| `unresolved` | 23,945 | **23,650** | −295 |
| `api_implementation_evidence` | 12,407 | **12,410** | +3 |
| `api_pattern` | 4,880 | **4,880** | 0 |
| `api_semantic_unit` | 3,209 | **3,209** | 0 |
| `processing_workflow` | 1,236 | **1,337** | +101 |
| `processing_implementation` | 1,088 | **1,266** | +178 |
| `processing_operator` | 591 | **595** | +4 |
| `processing_dynamic_candidate` | 496 | **505** | +9 |

`api_semantic_unit` and `api_pattern` land on exactly 3,209 / 4,880 again. That
was not enforced — no expected-output check was run against the v1 numbers — and
it is explained below: the delta is confined to sources that v1 could not read at
all, and those sources contain Processing calls, so they cannot reclassify into
the API pools.

## The entire delta is the 310 rows v1 reported as `source_unresolved`

v1 recorded `parsed=47,542` and `source_unresolved=310`. Two source roots had been
renamed on disk after the manifests were frozen:

| root | manifest path | actual path on disk | rows |
|---|---|---|---:|
| `model_tutorial` | `…/QGIS_Model_Tutorial_Workflows/downloaded_scripts` | `…/downloaded_scripts(QGIS_Model_Tutorial_Workflows)` | 301 |
| `pwc_qgis` | `…/爬取PWCQGIS/downloaded_scripts` | `…/爬取PWCQGIS/downloaded_scripts-PWC` | 9 |

301 + 9 = **310**, matching v1's unresolved count exactly. Both substitutions were
SHA-verified against the manifest before use — `model_tutorial` by an 8-file spot
check (8/8 match) and `pwc_qgis` exhaustively (9/9 match, 0 differ, 0 missing) —
so these are the same bytes the manifest froze, reached by a corrected path, not
different files.

v2 parses **47,852/47,852** with `source_unresolved=0`. The 310 recovered rows
classify as: 178 `processing_implementation`, 101 `processing_workflow`, 9
`processing_dynamic_candidate`, 4 `processing_operator`, 3
`api_plumbing_evidence`, 15 `unresolved` (parsed but no known signature). Summing
the positive deltas: 178+101+9+4+3 = 295, which is exactly the `unresolved` drop.
Every pool delta is accounted for; nothing was reclassified between pools.

## Census sanity check

- Total rows 47,852; `parsed` 47,852; `source_verified_rows` 47,852.
- Unique `source_sha256` 47,852; unique `record_id` 47,852; **duplicate SHA rows 0**.
- `unique_operator_sequences` 1,411 and `unique_semantic_sequences` 1,729 — both
  unchanged from v1.
- Dispositions: candidate 23,697, deferred 24,155.

### `api_semantic_unit` definition — confirmed

Checked against the miner evidence, not the label. All 3,209 rows have **exactly
one** API semantic call (`{1: 3209}`) and **zero** Processing calls. All 4,880
`api_pattern` rows have **two or more** semantic calls (2 → 102, mode 2 at 1,846).

Important nuance: the normalizer reclassifies by semantic-call count, so it does
**not** inherit the miner's own split. Of the 3,209 semantic units, 2,242 came
from miner rows labelled `api_pattern_candidate` and 967 from
`api_semantic_unit_candidate`; conversely 907 miner `api_semantic_unit_candidate`
rows became `api_pattern`. The miner's label keys off "semantic AND plumbing"
versus "semantic only", which is a different question. The authoritative
definition for this lane is the normalizer's: **`api_semantic_unit` = exactly one
API semantic call**. It is not a boundary-unit and not a composite macro.

### Operator pool: 595 rows, still 207 unique operator IDs

The 4 new operator rows all come from `model_tutorial` and carry
`omm:clip_network`, `omm:match_trajectory`, `omm:reduce_trajectory_density` — all
three are third-party non-catalog providers already present in the sealed
qualification as `FAIL_CLOSED`. So the unique-operator count is unchanged at
**207** and the sealed 56/44/107 verdict is unaffected: the new rows add support
to already-fail-closed operators only. The sealed operator qualification stays
bound to its own frozen 591-row v7 sidecar input and is not retro-fitted.

## Preservation gate (new, mandatory going forward)

`preservation_ledger_v1.json` records, in one file: input manifest hashes and row
counts, all five script hashes plus the runner hash, the git commit at build time,
every output hash with size and second-copy location, server paths, and the nine
source roots including both corrections.

Second copies now in-repo and hash-verified after transfer:
`qgis_asset_normalized_v1.jsonl` (83 MB, `a13ce1a2…`), its summary, the miner
sharded summary, the miner hash ledger, and `run_v2.sh`. The 66 MB merged miner
ledger and the 479-shard tree remain server-side only; both are deterministically
regenerable from the shards and manifests, and the shard tree carries a
`DONE.json` per shard.

## Scope boundary — historical API lineage stays separate

The pre-existing API artifacts are **reference lineage only** and are not merged
into this pool: `qgis_api_boundary_v6_post_filter_v1` (2,707 L3 intake units),
`qgis_api_l3_mapping_census_v1` (2,632 rows, of which 2,605 are
`mutation_export_only`), and `qgis_api_composite_macro_census_v1` (10,800
discovery units). That mutation/export line was formally closed in 2026-08 with
no support≥30 family; nothing here reopens it. Asset Miner v2 is the current
canonical API asset source.

## Next step

Do not start qualification on the 3,209 semantic units yet — the census gate above
is the prerequisite and has now passed, so the API semantic lane can open with a
confirmed definition. Recommended order: semantic recovery → L3 grounding →
three-state qualification, reusing the operator lane's proof discipline (span-exact
source evidence, per-row proof before any mapping, `QUALIFIED`/`DEFERRED`/
`FAIL_CLOSED` only).
