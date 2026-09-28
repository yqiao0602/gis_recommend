# QGIS API LLM Boundary Semantic Review v1

Input SHA256: `ced03c843cd7250a487fb6adc7fead37fa0b88d20e6c3ca313b5e74fb5a89eb8`

This is an independent source-window review of proposal semantics. It is candidate-only; no L3, training, or authority admission is granted.

| split | rows | boundary correct | wrong chain | chain truncated |
|---|---:|---:|---:|---:|
| calibration | 41 | 37 | 4 | 0 |
| holdout | 41 | 38 | 1 | 2 |
| total | 82 | 75 | 5 | 2 |

## Non-passing rows

| row | split | record_id | decision | reason |
|---:|---|---|---|---|
| 1 | calibration | `03001319fccc8ff071ca1c12` | wrong_chain | setAttributes calls are mutually exclusive gisOutput branches, but the proposal chains all six into one feature history. |
| 6 | calibration | `1680657088b74d908c207904` | wrong_chain | The two setGeometry calls are the if/else alternatives; both cannot occur in one execution path. |
| 8 | holdout | `17c100457ef95fd983e0f430` | chain_truncated | The proposal starts at intersection() but omits the source-visible intersects() guard that controls whether the operation executes. |
| 15 | holdout | `2709b565ee6ca6fdd6eaec74` | wrong_chain | The three setGeometry calls are alternative row/coordinate representations; chaining all alternatives is not one execution path. |
| 21 | calibration | `3c5061aed8ce28dce32f0dc8` | wrong_chain | The proposal is empty (no selected steps, sink, or boundary), so it is not a semantic boundary. |
| 22 | calibration | `3d480c392abdae33a172e4db` | wrong_chain | The source writes through provider.addFeatures and writer.addFeature; the proposal silently selects one of two sinks and omits the other. |
| 23 | holdout | `4140bc1721ef5a6110b66217` | chain_truncated | The selected addAttribute call is inside a fieldList loop; selecting one iteration followed by export does not represent the complete schema-building boundary. |

## Interpretation

Mechanical edge differences are not automatically errors: source-backed branch selection is accepted when the selected branch is a complete single-sink path. The holdout contains semantic failures, so the LLM boundary rule is not promoted and remains isolated.
