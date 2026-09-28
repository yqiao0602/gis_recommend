# QGIS stable113 taxonomy proposal v1 (superseded)

This five-class draft is retained for provenance but superseded by
`anti_bloat_audit_v1/stable110_extension_proposal_v1.json`. It is not an active
taxonomy proposal and has no authority.

## Decision boundary

This proposal resolves all seven remaining top-20 taxonomy gaps without
granting taxonomy or mapping authority.

- Five single-capability operators are proposed as appended stable113 classes.
- `native:splitvectorlayer` remains deferred because it creates an unbounded
  number of outputs and the current single-chain schema cannot represent that
  contract faithfully.
- `native:shortestpathpointtopoint` remains deferred because stable108 has no
  Network Analysis L1/L2 branch; adding an isolated leaf would make the
  hierarchy inconsistent.

## Proposed classes

| operator | candidate L3 | capability | single-gap rows |
|---|---|---|---:|
| `native:createpointslayerfromtable` | `L3_01_01_04` | XY Table to Point | 4 |
| `native:explodelines` | `L3_02_05_16` | Explode Lines | 12 |
| `native:splitwithlines` | `L3_02_05_17` | Split Features with Lines | 9 |
| `qgis:eliminateselectedpolygons` | `L3_02_07_10` | Eliminate Sliver Polygons | 4 |
| `gdal:proximity` | `L3_03_06_01` | Raster Proximity | 6 |

Stable108 token IDs 0-107 remain unchanged; proposed tokens are appended at
108-112. Every row has three previously SHA-verified source samples and exact
catalog semantics. This is still `proposal_only`: human taxonomy fields remain
blank, training rows are zero, and production merge is not granted.

## Full-pool dry-run

Replaying all 3,163 catalog-miss rows with the proposal, without granting it,
changes 53 routes:

- 42 fully-normalized rows become mapping-complete; 11 partially normalized
  rows still defer on operator/provider resolution.
- Fully-normalized mapping-complete coverage changes 766 -> 808 and unique
  chains 271 -> 291.
- Direct rows change 127 -> 130, so only 3 rows reach the later description and
  dedup gates.
- Other route changes are recovery +10, split +21, API sidecar +5, alignment
  exclusion +3, and operator-resolution defer +11.

The dry-run emits zero training rows. No direct or structural row may be
exported unless the five taxonomy mappings are explicitly approved.
