# QGIS Canary Evidence Source and Class-Signature Analysis

Date: 2026-07-15

## Canary provenance

The 24-record canary deliberately mixed three evidence routes:

| Evidence route | Selected | Contract valid | Reasoning rejected | Other failure |
| --- | ---: | ---: | ---: | ---: |
| Direct API only | 8 | 7 | 1 | 0 |
| Explicit `processing.run` only | 8 | 4 | 4 | 0 |
| `processing.run` plus custom algorithm | 8 | 4 | 3 | 1 unknown operator |

The eight reasoning failures are provider/channel behavior, not missing source data.
The semantic omissions have different causes:

- `Generate low-detail grid boundary` is direct-API-only. Its current ordered evidence has
  six steps, no scope, and no preserved dissolve/buffer/simplify evidence. This is an
  extraction/semantic-compaction gap.
- `Extract river headwater points and lines` contains the custom
  `continuous_network_analysis:identify dangles` call in the trace. The evidence exists,
  but the bounded catalog/crosswalk does not contain that operator.
- `Evaluate spatial fragmentation accuracy` has many low-level geometry/raster calls, but
  the compact semantic chain represents only a small part of the described workflow. This
  is a direct-API aggregation/completeness problem.

## Current pipeline behavior

- `build_ordered_evidence()` reads and retains `scope`.
- The ordered-evidence schema does not retain the `_steps.csv` `args` column.
- `compact_api_trace()` drops `scope`, so neither class name nor parameter labels reach the
  provider prompt.
- Current Phase 3 uses explicit processing IDs and a reviewed 228-operator 114-taxonomy
  crosswalk. It does not use `QGIS_Input.csv` class/parameter signature matching.

Therefore the proposed class-name plus parameter-label route is not currently integrated.

## Measured class-scope coverage

### Current 5,107 eligible pool

- Records with any scope: 260
- Records with a `class_*` scope: 224
- Exact class-name matches to the 1,292-operator catalog: 0

These class names are predominantly custom workflow/plugin classes, not official QGIS
Processing implementation classes.

### Full 21,085 Phase 2 records

- Records with any scope: 2,578
- Records with a `class_*` scope: 1,729
- Records with an exact normalized class/catalog match: 14
- Unique matched class names: 9
- Ambiguous class names: 3

The current facts-linked Phase 2 corpus therefore contains little official class-name
signal. Class matching cannot repair most of the existing 21,085 records by itself.

### `WorkflowoutputQGIS_QGIS_Core_Processing`

This separate source is where the proposed method is effective:

- `_steps.csv` files: 110
- Files containing a class scope: 106
- Files retaining parameter `args`: 97
- Files with an exact normalized class/catalog match: 61
- Unique matched classes: 62
- Ambiguous classes: 13

Verified examples include:

- `VariableDistanceBuffer` -> `qgis:variabledistancebuffer`
- `contour` -> `gdal:contour`
- `contour_polygon` -> `gdal:contour_polygon`

Class-name matching is not automatically near 100% accurate. Provider collisions include:

- `Dissolve` -> `gdal:dissolve` or `native:dissolve`
- `AssignProjection` -> `gdal:assignprojection` or `native:assignprojection`
- `RasterCalculator` -> GDAL, QGIS, or SAGA variants
- `polygonize`, `rasterize`, `slope`, and `hillshade` -> GDAL/native variants

Parameter labels, source provider/path, class inheritance/imports, and output types are
required to disambiguate these cases.

## Recommended routing

1. **Explicit Processing route**: preserve ordered `processing.run` IDs as deterministic
   evidence. No LLM selection is needed for known IDs.
2. **Official/Core class-signature route**: retain class name, provider/source path,
   parameter types and complete labels, output labels/types, and imports. Use exact catalog
   matching only when the candidate is unique and provider-consistent.
3. **Ambiguous class route**: give the LLM only the bounded candidates, parameter schema,
   provider evidence, and output type; require human review.
4. **Direct API workflow route**: aggregate ordered low-level calls into semantic motifs.
   Class matching is only an additional signal when a meaningful scope exists.
5. **Custom algorithm route**: preserve the custom ID and evidence. Do not force it to an
   official catalog operator; map it to a taxonomy family only after review.

## Scale implication

The Core Processing directory can provide roughly one hundred high-quality operator
anchors, not 20,000 independent workflows. Its main value is an audited signature library
that improves later direct-API semantic aggregation. Training-volume growth still depends
on distinct real workflow scripts, code-grounded descriptions, and reviewed segmentation;
class-name matching alone cannot supply the target volume.

## Next validation

Rebuild a bounded 110-record Core Processing workbook retaining `scope`, raw structured
`args`, parameter labels, provider/path evidence, deterministic candidates, and ambiguity
flags. Review all 110 because the set is small. Use the accepted mappings as an anchor
library, then test them on a separate stratified sample of ordinary direct-API workflows.
