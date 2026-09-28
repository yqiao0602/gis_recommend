# QGIS API LLM Boundary v3 Semantic Review

Candidate-only independent review. No L3 mapping, training row, authority, or production admission is granted.

| split | rows | boundary correct | wrong chain | chain truncated |
|---|---:|---:|---:|---:|
| holdout | 1 | 1 | 0 | 0 |

The accepted holdout proposal is a module-scope, contiguous `setGeometry -> setAttributes -> writer.addFeature` path. It has one sink, valid source span and dataflow edges, no control path, and no source-visible QGIS data call absent from the selected steps.

This is insufficient to promote the route: 16 of the 20 v3 requests abstained/returned empty and 3 failed at HTTP level.
