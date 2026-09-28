# API pattern multi-step census: 4,880 → 875 (first-pass compression structure)

First pass of the API multi-step lane over all 4,880 `api_pattern` rows of the v2
normalized ledger (input hash-pinned). No L3 mapping, no task text, no admission —
this is exactly the compression-structure measurement requested before any
further processing. Training rows 0; authority unchanged.

## The stage table

| Stage | Rows |
|---|---:|
| `api_pattern` input | **4,880** |
| source unavailable / parse error | 0 (all SHA-verified and parsed) |
| FAIL_CLOSED (foreign receiver/keyword) | 45 |
| structure invalid | 2,742 |
| ├─ `no_receiver_proven_qgis` | 813 |
| ├─ `no_dataflow_linkage_between_calls` | 731 |
| └─ `insufficient_transform_steps` (predicate/measurement-dominated) | 1,198 |
| multi-step structure valid | **2,093** |
| internal chain-signature dedup | 1,218 |
| **unique chain signatures kept** | **875** |

All 875 kept rows have verified dataflow linkage between calls (≥1
producer→consumer name pair); owner split: `domain_named` 322, `plain_scope` 505,
`module_level` 25, `generic_verb` 23.

## The three requested readings

### 1. Chain-length distribution (the homogeneity question)

The census does **not** collapse into two-call fragments: length-2 chains are only
38 of 875; the mode is 3–8 steps with a real tail to 102. The biggest signature is
`transform|transform` (257 rows → 1 kept), followed by
`transform×3` (97) and `centroid|centroid` (74) — the CRS/centroid mass is as
homogeneous as the standalone lane's, but multi-step heterogeneity exists beyond
it: `transform|buffer|transform` (24), `intersects|intersection|combine` (26),
`interpolate|interpolate` (21), plus long mixed chains with predicates.

### 2. Task owner (the signal proven in the standalone lane)

**322 `domain_named` chains, and all 322 have unique signatures** — no two
domain-named rows share a chain signature. Every one of the top examples shows a
genuine multi-operation workflow shape: `makevalid|intersects|buffer|unaryunion|
intersection|transform`, `buffer|buffer|intersects|intersects|splitgeometry`,
`centroid|transform|transform|contains|transform|centroid`. This is structurally
different from the standalone lane, where domain-named survivors were 3 of 137.

### 3. Signature independence (instance count vs supervision count)

2,093 structurally valid chains compress to **875 unique chain signatures**
(2.4 : 1). The compression is real but not catastrophic, and — critically — it
does **not** destroy diversity: 322/875 (37%) come with a domain-named task
owner. Predicate/measurement contamination is high (531 of 875 carry predicates,
246 carry measurements); only 259 are pure transform chains.

## What the numbers say about the lane's ceiling

Reading these as workflow-training supervision — before any L3/task-text work:

- The optimistic **signature-level** pool is 875; the **task-qualified** pool
  starts at ~322 (domain-named) and the honest ceiling after predicate-dominance
  filtering, per-source semantic review, 508-pool cross-dedup, and the tokenizer/
  V4 gates will be lower.
- Even the most conservative reading (pure-transform + domain-named + unique
  signature) leaves a multi-step pool **two orders of magnitude above the
  standalone lane's 3**, with real chain diversity — so the "move to multi-step
  structure" call is confirmed, but so is the user's warning: instance count
  (4,880) was never the supervision number; 875 signatures is, and the
  task-qualified subset of that is the training number.

## Verification

- Focused tests 9/9 (linked-chain census, signature dedup, foreign fail-closed,
  predicate-pair invalid, unlinked invalid, module owner, <2 calls, missing
  source, closed gates); `compileall` clean.
- Server run over `/home/yll`; artifacts mirrored and hash-verified locally;
  pinned input equals the local v2 normalized ledger (`a13ce1a2…`).
- Caveats recorded honestly: receiver proof here follows assignments across the
  whole file (weaker than the sidecar's dominating-scope discipline) and counts
  are census-grade, not admission-grade; `insufficient_transform_steps` reasons
  are batched per (T+P+M) shape in the ledger.
