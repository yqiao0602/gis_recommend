# QGIS stable101 train-only manifest v1

## Result

- input rows: 43 (19 ready-now + 24 recovered canonical)
- manifest rows: 43
- source groups: 34 (6 multirow)
- unique operator sequences: 38
- unique L3 sequences: 37
- chain length: 1..14

## Cross-pool audit

- common source SHA256: 0
- common record IDs: 0
- common operator sequences: 2
- task-text near-duplicate pairs: 0
- max task-text similarity: 0.427746
- suppressed rows: 0

Equal operator sequences are retained when source identity and task semantics differ.
All rows remain train-only; production merge and validation/test admission are not granted.
