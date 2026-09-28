# QGIS taxonomy anti-bloat audit v1

## Gate

New L3 proposals require at least 30 independent normalized source-body
authorities. Passing support alone is insufficient: parameter-dependent,
unbounded multi-output, support/export, or hierarchy-incomplete capabilities
remain deferred.

All 235 matching replay rows were verified against `/home/yll`; source hash
failures are zero. Harvest copies were folded with the existing
`qgis_source_authority` implementation.

## Decisions

| operator | normalized body support | decision |
|---|---:|---|
| `native:explodelines` | 81 | retain stable110 candidate |
| `native:splitwithlines` | 70 | retain stable110 candidate |
| `native:splitvectorlayer` | 32 | defer: unbounded multi-output |
| `qgis:eliminateselectedpolygons` | 19 | defer: support below 30 |
| `native:shortestpathpointtopoint` | 15 | defer: support below 30 and missing network hierarchy |
| `gdal:proximity` | 12 | defer: support below 30 |
| `native:createpointslayerfromtable` | 10 | defer: support below 30 |

The two retained operators should not be merged merely to reduce class count:
one splits every line at existing vertices, while the other uses a second
cutter layer and supports line or polygon inputs. Their task conditions and
input contracts are independently recoverable.

## Existing overlap

`L3_02_05_06 Split Line at Point` cannot absorb these operators. Its current
accepted mapping is only `native:lineintersections`, whose catalog contract
creates intersection points instead of splitting geometry. That mismatch is
recorded as a separate repair sidecar and is not silently changed here.

## Outcome

The five-class stable113 draft was frozen concurrently before this newer audit
completed. The audit recommends superseding that authority with a two-class
lean successor, but the authority transition is pending explicit user
resolution. Stable108 is the safe current base. The stable110 token assignment
must not be consumed while that conflict remains unresolved.

The stable110 full-pool dry-run changes 35 routes. Of these, 25 fully
normalized rows raise mapping-complete coverage 766 -> 791 and unique chains
271 -> 282; 10 partially normalized rows still defer on operator resolution.
Direct rows change 127 -> 129. Training rows remain zero.
