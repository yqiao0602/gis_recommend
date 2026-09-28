# QGIS `native:lineintersections` mapping correction v1

## Decision

The prior auto-name mapping to `L3_02_05_06 Split Line at Point` is excluded.
The operator creates point features at intersections between two line layers; it
does not split either input line layer. After that exclusion, the operator is
mapped to the existing `L3_02_02_01 Intersect` capability. No L3 class or token
is added.

## Evidence

- QGIS catalog: two vector inputs, intersection-point vector output, optional
  fields retained from both inputs.
- Taxonomy: `Intersect` covers geometric intersection with attributes from both
  inputs; `Split Line at Point` requires points as cutters and returns split
  lines.
- Corpus: 59 rows / 59 unique source SHA values / 31 operator chains contain
  the operator. Forty-four are fully normalized.

## Replay

The stable110 exclusion baseline has 775 mapping-complete rows, 274 unique
mapping-complete chains, and 127 direct rows. Applying the correction restores
16 mapping-complete rows, eight unique chains, and two direct rows, yielding
791 / 282 / 129. The two direct chains now end in `L3_02_02_01`.

Training, validation, test, and production admission remain closed. The two
direct rows next require deterministic description fidelity, source replay, and
four-layer deduplication.
