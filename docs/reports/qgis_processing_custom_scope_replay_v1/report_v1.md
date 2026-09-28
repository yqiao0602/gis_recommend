# QGIS Processing custom lexical-scope replay v1

Date: 2026-07-31

## Decision

The remaining blocker pool does not produce the missing 35 Processing training
pairs under the frozen stable110 authority. The cross-file implementation
resolver is now batch-capable and was replayed against the complete custom
implementation census. It recovered seven implementation bodies, but only one
scope candidate survived the existing structural and deterministic description
gates. That candidate is not yet a train-only row: it still requires the normal
source-disjoint review/export gate.

No L3 class was added, stable114 was not enabled, no LLM was called, and no
training or production merge was run.

## Inputs and replay

- v7 blocker replay: 757/757 source SHA verified, zero source failures.
- Provider-equivalence replay: 158 fully normalized rows, 133 mapping-complete;
  229 partial rows, 220 mapped subsets. The mapping-gap remainder is therefore
  25 fully normalized plus 9 partial, not 34 fully normalized.
- Custom census: 8,474 source rows, 8,176 SHA-verified, 167 implementation
  instances and 97 normalized implementation variants.
- v7 provider rules changed two variants from unresolved to
  `expanded_complete`; the full custom census contains seven complete variants.

## Scope replay result

Each complete variant was reduced to one SHA-verified
`processAlgorithm + reachable-helper` lexical scope and then sent through the
existing route, splitter, recovery, deterministic description, and four-layer
deduplication code. File-level replay was intentionally not used because it
mixes multiple class definitions and produces false task boundaries.

| result | count |
|---|---:|
| scope parents | 7 |
| `review_api_sidecar` | 1 |
| `recover_call_graph` | 3 |
| `split_subworkflow` | 3 |
| scope candidate units | 1 |
| canonical candidates after cross-pool dedup | 1 |
| train-only rows exported | 0 |

The surviving candidate is the final `native:deletecolumn` local unit in
`summitprocess_2`; it is structurally and textually faithful as a local unit,
but remains pending source-disjoint authority review. The other six bodies are
blocked by API transformations, control flow, missing data edges, or deferred
description fidelity. The 30 unresolved variants are dominated by stable110
taxonomy gaps or specialized providers (`geometrybyexpression`,
`extractwithindistance`, `splitlinesbylength`, `orderbyexpression`,
`interpolatepoint`, `idragratools`, WBT, QuickOSM, and PreCourlis); adding
provider aliases would not be an exact existing-L3 mapping.

## Delivery impact

Processing remains at 165 delivered train-only rows. The custom lexical-scope
lane has an observed upper bound of one pending canonical row, so it cannot
honestly close the 200-row milestone. The next productive QGIS lane is the
already extracted 39,386-row API-pattern pool: apply the same source-disjoint
calibration, task-boundary, stable110 mapping, fidelity, and dedup gates there.
Processing blockers remain sidecars unless a new existing-L3 authority is
source-reviewed; no taxonomy expansion is authorized by this report.

## Reproducibility

Driver: `scripts/build_qgis_custom_implementation_expansion.py`.

Server authority: `/home/qy/system_redesign/diagnostics/qgis_processing_custom_implementation_v1/full_custom_scope_replay_v4/`.

Key artifacts and hashes are recorded in `hash_ledger_v1.json` in that
directory. Local implementation tests: 34 passed; `py_compile` passed.
