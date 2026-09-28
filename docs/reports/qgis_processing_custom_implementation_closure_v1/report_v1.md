# QGIS Processing custom-implementation closure v1

Date: 2026-08-01

## Decision

The corrected custom-implementation replay is closed under the frozen
stable110 taxonomy. It produces no additional train-only row beyond the
previously admitted `filterstructures` row already included in the 177-row
Processing authority.

This is a family-level batch conclusion, not a request for more per-file
review. Reopening the lane requires a new mapping or taxonomy authority.

## Verified Funnel

| Gate | Count |
| --- | ---: |
| Unique source rows replayed | 8,471 |
| Implementation variants | 97 |
| Expanded complete variants | 10 |
| Deferred unresolved-operator variants | 27 |
| Unresolved operator families | 16 |
| Scope parents | 10 |
| Scope candidates | 4 |
| Scope canonical | 2 |
| Scope duplicates | 2 |
| New train-only rows | 0 |

`indicea3` contains an eight-step mapping-complete Processing sequence, but the
whole workflow includes control-flow and low-level feature mutations. Its local
three-step units are cut by `try`, `for`, dynamic formulas, and `addFeature`;
the remaining independent unit is single-step. Net new training rows: 0.

## Remaining Families

The 27 unresolved variants collapse to 16 families. Ten variants use standard
or legacy provider IDs (`geometrybyexpression`, `interpolatepoint`,
`orderbyexpression`, `removeduplicatevertices`, `splitlinesbylength`,
`definecurrentprojection`, `sumlinelengths`); 17 use third-party/custom
providers. None has both a complete standard Processing DAG and an exact
stable110 contract.

`definecurrentprojection` only assigns CRS metadata and is not coordinate
reprojection. `sumlinelengths` has no exact stable110 vector-summary class and
its reviewed source also reuses the same output alias for two reprojected
inputs. `orderbyexpression` is not Select by Attribute. Third-party families
cannot be bound to a unique standard DAG from the available source evidence.

The authoritative replay evidence remains in
`docs/reports/qgis_processing_custom_scope_replay_v3_geometry_semantics/`.
No LLM, training run, production merge, or stable110 extension was performed.
