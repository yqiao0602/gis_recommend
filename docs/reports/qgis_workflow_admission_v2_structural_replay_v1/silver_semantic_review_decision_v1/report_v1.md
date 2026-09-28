# QGIS Silver Independent Semantic Review v1

The original 21-row Silver export is immutable. This review produces a separate curated experimental package and never changes the 508-row formal authority, validation/test, benchmark, or checkpoints.

| decision | rows | train-only treatment |
|---|---:|---|
| Gold | 15 | isolated reviewed train-only, weight 1.0 |
| Retained Silver | 4 | isolated reviewed train-only, weight 0.7 |
| Reject | 2 | explicit revocation, excluded from curated package |
| Curated Gold + Silver | 19 | train-only experimental package |

## Rejected Rows

| record_id | reason |
|---|---|
| `3d2310d2bfb7ec50fcd15b19` | The Boolean raster expression uses comparisons and AND, but qgis:rastercalculator is mapped to Arithmetic & Math instead of Logical & Comparison. |
| `632fea18482f1643b8fd2131` | Rasterize writes to parameters['OUTPUT'], the declared vector point destination, while the declared RASTER_OUTPUT is unused; do not repair the source output contract. |

## Constraints

No model training was run. The Gold package is not a formal-authority merge and remains excluded from validation, test, benchmark, and production checkpoint workflows.
