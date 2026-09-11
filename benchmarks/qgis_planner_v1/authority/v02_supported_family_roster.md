# v0.2 Supported Family Roster — Rationale & Freeze Record

Frozen: 2026-09-10 · Machine-readable authority:
`v02_supported_family_roster.json` (same directory)

## What this freezes

The v0.2 benchmark does **not** attempt exhaustive coverage of the 50
stable101 families. A supported family roster is predefined by source
availability, semantic verifiability, and research relevance; only roster
families carry v0.2 quotas. This is the deliberate inversion of the v0.1
failure mode ("pick whatever 40 of 52 are available") into: declare the
target, then report attainment honestly.

## Why 20 / 8 / 22

Measured fact (from `candidate_supply_summary.json`, Gate 3 run): **all
149 candidates and all 52 distinct DAGs are concentrated in exactly 20
families; the other 30 have zero supply.** The roster boundary therefore
requires no discretionary cut among supplied families — every family with
demonstrated supply is rostered; the discretion lives only in how the 30
zero-supply families are triaged:

- **SUPPORTED (20)** — the supply families, tiered A/B/C/D by role:
  - A (6, already quota_4-eligible): the anchor set. L3_01_10_01,
    L3_02_01_01, L3_02_22_06, L3_02_04_01, L3_02_06_02, L3_03_05_02.
  - B (4, topology/length repair carriers): Intersect, Collect Features,
    Merge (merge-topology carrier), Calculate Field (7+ long-chain carrier).
  - C (4, raster/modality repair carriers): Arithmetic & Math (7 raster),
    Slope Gradient, Zonal Statistics, Clip Raster by Extent (raster-only).
  - D (6, long-tail small quota): Minimum Bounding Geometry, Delete Field,
    Feature to Point, Multipart to Singlepart, Raster-Vector Conversion,
    Region-based Sample Extraction.
- **DEFERRED (8)** — classic raster/overlay/terrain families with zero
  supply (Reclassify, Focal Statistics, Hillshade, Aspect, Mosaic, Union,
  Erase, Extract by Location). v0.3 candidates if P0 mining happens to
  produce them; **no v0.2 quota, excluded from coverage-deficit math**
  (rule R6).
- **OUT_OF_SCOPE (22)** — zero supply and distant from the paper's core
  comparison (ML training, temporal, filtering, field admin, geometry
  repair, miscellany).

## Quotas (per family)

Candidate-side admission reuses the existing Gate 3 quota_4 rule (7
source-backed candidates incl. reserve). DAG-side quotas are tiered:
A/B = 4, C = 3, D = 2 → upper bound 64 DAGs, trimmed by the 120-task
budget cap. **A family landing below quota is recorded as
`quota_shortfall` in the v0.2 audit — never silently absorbed, never
substituted** (rule R1).

## Final budget (~120 tasks)

| Dimension | v0.1 actual | v0.2 target |
|---|---|---|
| Structure | 40 DAG × 3 variants | **~60 DAG × 2 variants** |
| task_style | unannotated | variant pair = 1 operator_explicit + 1 planning_oriented where possible → both subsets reportable |
| Modality | raster 14–19/120 | **raster+mixed ≥ 20/60 DAG (≥33%)** |
| 1-step | 1 DAG | **≥ 6 DAG** |
| 2–3 / 4–6 / 7+ | 32 / 12 / 7 (of 52 queue) | ~28 / ~18 / ~8 |
| Topology | linear 30, merge 22, **branch 0** | ~32 / ~20 / **branch ≥ 8** |

Branch note: candidate-pool branch supply is zero — branch DAGs must come
from expert-authored proposals (the `vector_branch` stratum) or newly
authored supply. The 8 existing expert proposals target exactly the P0
strata; 4 pending + 1 returned_for_revision await adjudication as the
fastest supply path.

## Dev budget (~40 tasks)

~35 canonical DAGs × ≤2 variants, DAG-disjoint from final, task_style
labels carried over, gold unsealed as in v0.1.

## Feasibility math (known before mining starts)

- Distinct DAGs required: ~60 final + ~30 dev = **90**; available: 52 →
  **net ~40 new**, concentrated in raster / branch / 1-step / long-chain.
- Candidate quota total: 20 × 7 = 140; available: 149 — sufficient in
  aggregate, mis-distributed per family (Tier B/C/D need 2–5 more each).

## Standing rules

R1 quota_shortfall explicit · R2 roster immutable during repair · R3 v0.1
sealed gold never regenerated · R4 prediction hashes locked before sealed
gold reads · R5 no M1/M3 retraining (benchmark revision must not flow back
into the models) · R6 deferred excluded from deficit math · R7 refusal
gold inherited but re-hash-bound; refusal boundary re-checked against this
roster (clustering is not rostered, so refusal-004
`unsupported_capability` stays consistent).
