# QGIS Silver Scale Validation v1

Date: 2026-08-11

## Decision

The current ~500-row result is not an extraction ceiling for the 47,852 source
files. It is the observed output of the strict Gold contract: source-backed
chain recovery, exact L3 mapping, deterministic description fidelity, and
four-layer deduplication. The available census proves a larger *candidate*
population, but does not yet prove a larger Gold population.

## Evidence

| Layer / family | Source or unit population | Post-gate result | Compression / interpretation |
|---|---:|---:|---|
| All QGIS corpus | 47,852 sources (8,466 Processing + 39,386 API) | 508 formal QGIS train-only rows; 31 additional isolated rows | Corpus coverage is not row count |
| Processing | 8,466 sources | 294 formal rows; 12 stable124 canonical candidates were all existing chains with alternate descriptions | Dynamic/helper route is closed; no new task semantics |
| API pattern census | 39,386 sources; 13,554 pattern candidates | 10,800 discovery units; 1,023 families | Discovery only; no L3/description/admission yet |
| API composite priority pool | 2,773 units in 14 families | Historical discovery population; its 14 mutation-only families were subsequently replayed, completed, or permanently closed | Not a remaining 2,773-unit opportunity pool |
| `setattributes -> addfeature` | 575 source SHA / 883 units | 213 complete units / 173 authorities; 45 fidelity rows; 3 canonical | Signature support 575 -> canonical 3 (0.5% of source SHA) |
| `addattributes` / `setattribute` | 33 fidelity rows | 21 canonical rows; 20 source authorities | A family can retain more variation when fields are explicit |
| point geometry | 102 complete authorities | 55 fidelity rows; 3 canonical | 2.9% of complete authorities |
| polyline geometry | 34 normalized authorities | 54 fidelity rows; 3 canonical | 8.8% of authorities |
| WKT geometry | 156 normalized authorities | 270 fidelity rows; 7 canonical | 4.5% of authorities |
| raster calculator | 59 complete authorities / 116 units | 114 fidelity rows; 83 canonical | This family has meaningful Gold yield |
| raster file export | 49 authorities / 53 units | 53 fidelity rows; 37 canonical | Mapping/contract specificity preserves variation |

The largest confirmed compression is therefore not source extraction alone:
many source variants collapse to the same normalized DAG, task text, and
operator/L3 pair. Conversely, raster and parameterized families demonstrate
that strict gates can still yield tens of canonical rows from one family.

## What is and is not proven

Proven:

1. A strict Gold-only interpretation naturally lands near the current
   500-row scale because deduplication removes repeated implementations.
2. The corpus contained a materially larger API candidate population: 2,773
   priority units across 14 macro families and 10,800 discovery units overall.
   That population demonstrated source-scale discovery, but its priority
   families have since been processed or closed.
3. Existing family results range from 0.5% to 75% source-authority-to-canonical
   retention, so one global extrapolation is invalid.

Not proven:

1. The remaining population after completed and permanently closed families is
   not quantified by the historical census. Its support must be recomputed
   before projecting any additional yield.
2. LLM extraction has not demonstrated incremental verified operators on this
   population. It remains candidate-only and isolated.
3. A 1,000-row Gold target cannot be claimed until new families pass the same
   replay, mapping, fidelity, dedup, tokenizer, and V4 gates.

## Next bounded experiment

First refresh the API family census after excluding every completed and
permanently closed family. If it contains at least five new high-support
families, run source-disjoint replay on five of them, 30 authorities per family
(150 total). Measure, per family:

`discovery support -> normalized authorities -> complete units -> mapping pass -> fidelity pass -> canonical rows`.

This is a scale-validation experiment, not a production export. It must not
call the LLM, alter the 508-row authority, or relax any Gold gate. A family is
worth full replay only if its 30-source pilot has at least 5 complete
source-disjoint authorities and at least 2 distinct normalized DAG/task pairs.
If the refreshed census has no such family, close the current API macro route
as exhausted rather than creating a Silver pool from weak or duplicate units.

## Status

`training_admission=not_granted`; `production_merge=not_granted`; no training or
checkpoint action performed.
