# QGIS Seed Subworkflow Task-Fidelity Review v1

Reviewed 11 independent subworkflow candidates: 5 Gold, 4 Silver, and 2 Reject.

| disposition | rows | treatment |
|---|---:|---|
| Gold | 5 | train-only, weight 1.0 |
| Silver | 4 | train-only, weight 0.7 |
| Reject | 2 | excluded as an exact parent duplicate |

All accepted rows retain `parent_source_sha256` split grouping and remain excluded from authority, validation, test, benchmark, and checkpoints.
