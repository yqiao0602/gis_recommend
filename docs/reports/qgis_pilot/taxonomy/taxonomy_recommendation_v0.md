# QGIS Taxonomy Recommendation v0

## Decision Status

This is a user-review draft. No vocabulary, ID mapping, training data, or runtime default has been changed.

## Evidence Base

- 20,428 facts rows and 12 merged QGIS process tables.
- 15,942,213 process rows scanned; 9,270,200 rows belong to facts-linked scripts.
- 44,776 QGIS processing calls, 1,095 unique processing operations, and 21,255 direct API names.
- Counts below are unique facts-linked scripts, not duplicated training rows.

## Blocking Defect in the Current 107 Draft

The 13 additions reuse legacy 350-taxonomy codes with different meanings. Examples:

| Current 107 assignment | Legacy meaning | Conflict |
|---|---|---|
| `L3_02_01_02` Reproject | Variable Distance Buffer | incompatible |
| `L3_02_01_03` Fix Geometries | Multiple Ring Buffer | incompatible |
| `L3_02_03_01` Grid | Dissolve | incompatible |
| `L3_02_03_02` Simplify | Aggregate Polygons | incompatible |
| `L3_02_05_01` Delete Duplicate | Simplify | incompatible |
| `L3_02_05_02` Snap | Smooth | incompatible |
| `L3_02_07_02` Polygons to Lines | Feature to Polygon | reversed conversion |
| `L3_02_07_03` Extract Vertices | Polygon to Line | incompatible |

The current 107 IDs must not be frozen or used for formal labels.

## Review of the 13 Intended Capabilities

| Intended capability | Scripts | Boundary scripts | Recommendation |
|---|---:|---:|---|
| Vector CRS transform | 503 | 46 define-CRS cases | KEEP, use legacy `L3_01_10_01`; separate Define Projection |
| Geometry repair | 433 | 20 validation cases | KEEP, use legacy `L3_01_05_02`; separate Check Geometry |
| Vector grid generation | 117 | 0 | KEEP with a new non-conflicting ID; exclude raster grids |
| Simplify | 65 | 47 smooth/generalize cases | KEEP, restore legacy `L3_02_05_01` |
| Voronoi | 52 | 0 | KEEP, restore legacy `L3_02_07_07` |
| Delaunay triangulation | 19 | 0 | KEEP, restore legacy `L3_06_01_02` |
| Delete duplicate geometries | 79 | 12 duplicate-vertex cases | KEEP, use legacy `L3_01_05_04` with geometry/record scope |
| Geometry snap | 75 | 0 | KEEP, restore legacy `L3_02_07_09` |
| Delete holes | 66 | 0 | KEEP with a new non-conflicting ID |
| Smooth | 38 | 78 simplify boundary cases | KEEP, restore legacy `L3_02_05_02` |
| Concave hull | 10 | 0 | REVIEW; semantically distinct but low observed coverage |
| Polygon to line | 108 | 0 | KEEP, restore legacy `L3_02_07_03` |
| Extract vertices | 121 | 169 generic-vertices boundary cases | KEEP with a new non-conflicting ID; do not reuse Polygon to Line |

## Additional Capabilities Required by Real Evidence

| Capability | Minimum scripts | Proposed treatment |
|---|---:|---|
| Define Projection / Assign CRS | 46 | Restore legacy `L3_01_10_02`; never merge with coordinate transformation |
| Check Geometry / Geometry Validation | 20 | Restore legacy `L3_01_05_01`; never merge with repair |
| Rasterize vector | 198 | Add a direction-specific non-conflicting code |
| Polygonize raster | at least 197 | Add a direction-specific non-conflicting code |
| Attribute table join | 180 | Add a non-spatial table-join code; do not map to Spatial Join |
| Add spatial index | 143 | Restore legacy `L3_01_07_01` only if explicit performance/index tasks remain in scope |
| Feature/line to polygon | 22+ | Restore legacy `L3_02_07_02`; distinct from Polygon to Line |

## Proposed Taxonomy Size

- Stable base: 94 classes.
- Restore or correctly add 19 planning capabilities: 13 intended capabilities plus Define CRS, Geometry Validation, Rasterize, Polygonize, Table Join, and Feature to Polygon/Add Spatial Index after scope review.
- Working range: **112-114 classes**, not the current semantically conflicting 107.
- Proposed default: **113 classes**, keeping Add Spatial Index but merging low-evidence Concave Hull into a reviewed hull family until more evidence is found.

## Required User Decisions

1. Keep Add Spatial Index as a planning-level class or treat it as implementation detail.
2. Keep Concave Hull as an independent class or merge it into a hull/bounding-geometry family.
3. Confirm direction-specific Rasterize and Polygonize classes instead of one broad Raster-Vector Conversion class.
4. After these decisions, allocate collision-free IDs against the complete legacy 350 registry and freeze taxonomy v1.
