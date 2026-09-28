# API pattern 875-funnel: FINAL — 120 training rows

The complete qualification-to-consumption funnel over the 875 unique API-pattern
chains, run exactly as ordered: frozen bindings only, Predicate/Metric Policy v1,
no new census or mining, no AI-generated text, no GEE. Final answer:

> **875 → 120 training candidates** (13.7% signature-level retention; 2.5% of
> the original 4,880 pattern instances). All 120 pass the real tokenizer and the
> real V4 data path. None is a training row yet — consumption into a training
> package requires the user's explicit decision.

## The complete funnel table

| Stage | Rows |
|---|---:|
| API pattern | 4,880 |
| unique chain signature (census) | **875** |
| L3 mapping complete | 434 |
| L3 unresolved (unproven transform receiver) | 306 |
| QUALIFIED (complete + ≥2 transforms + domain owner) | 142 |
| DEFERRED: task owner not domain-named | 292 |
| DEFERRED: insufficient transforms after predicate policy | 127 |
| DEFERRED: deferred actions in chain | 76 |
| predicate steps kept as sequence control nodes | 61 (of 142) |
| predicate steps kept as evidence only | 1,796 |
| task-text reject (no source context) | 4 |
| internal L3-sequence dedup | 8 |
| hit 508 pool (source SHA 4 / L3 sequence 6 / task text 0) | 10 |
| tokenizer reject | **0** |
| V4 reject | **0** |
| **FINAL TRAINING CANDIDATES** | **120** |

The qualification (steps 1–3) was reported in
`qgis_api_pattern_qualification_v1/`; this report covers the final consumption
stages over the 142.

## Task text provenance (nothing invented)

90 of 120 from **docstrings** (module or function, verbatim), 11 from
**task-bearing comments** near the call site, 19 from **domain-named
class.function scope** (e.g. `SampleRasterAtLineEndpoints.processAlgorithm`,
`JunctionBufferTrimAndExplode`, `SplitPolygonsByGrid.compute` — real QGIS
Processing-plugin algorithm classes). 4 rows rejected outright for having no
source context at all. Mean text length 49.3 tokens, max 119, **zero tokenizer
rejections** at the 128 gate.

## Distributions of the final 120

**Workflow length** (L3 steps): 2:12, 3:23, 4:13, 5:13, 6:17, 7:9, 8:5, 9:5,
10:4, 11:2, 12:1, 13:2, 14:3, 15:3, 16:1, 17:1, 19:2, 39:1, 46:1, 50:1, 55:1 —
mode 3, real multi-step tail, max 55 steps within the V4 100-token sequence
budget.

**L3 class distribution**: Intersect 289, Buffer 161, Reproject 150, Feature to
Point 131, Collect 78, Erase 49, Repair Geometry 34, Min Bounding 7, Simplify 5,
Smooth 1, Sym Difference 3 (step counts across the 120 rows).

**V4 smoke** (real `TaskConditionedL3DatasetV4` + real tokenizer, batch size 16,
8 batches): max content length 55 (limit 100), loss finite (sum 39.68), all
gradients finite, sample weights emitted. No checkpoint written, no training
epoch run.

## Reading against the user's decision bands

> 875 → 120 lands in the **50–150 band**: API pattern carries real multi-step
> structure, but its task supervision is not enough to be a primary training
> source on its own.

Per the pre-agreed interpretation: AI-assisted reconstruction / other lanes
should now formally enter the roadmap, and the API pattern lane's standing
product is (a) these 120 verified candidates, (b) 1,796 predicate facts and
operator-semantic knowledge already frozen in the evidence ledgers. The single
largest remaining unlock stays the 645 unproven transform steps (238 deferred
rows) via the dominating-assignment argument proof.

## Provenance

- Consumption ledger: `pattern_consumption_v1.jsonl` (142 rows with stage
  reasons; 120 kept with task text, source kind, token counts).
- Context ledger extracted on the server (docstrings, comments, class/function
  chains per row) and pinned in `hash_ledger_v1.json`.
- Inputs hash-pinned: context ledger + 508 aggregate.
- Focused tests 6/6; `compileall` clean.
- `training_admission = not_granted_consumption_only`; authority, evaluation
  splits, checkpoints unchanged; the 1208-package production merge is a separate
  user decision.
