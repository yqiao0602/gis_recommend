# QGIS API Create Feature Class Train-only v1

- Whole-function single-L3 mapping was rejected: calibration accepted 5/20 and holdout accepted 6/20, so it would truncate split, import, calculation, sampling, and export tasks.
- The admitted boundary is a local source-verified macro only: `QgsVectorLayer(..., "memory") -> schema -> optional prepared features -> writer` for the same layer alias.
- Full strict replay: 67 source-verified rows; 52 complete local macros, 11 without a memory-layer constructor, 3 incomplete chains, and 1 ambiguous chain.
- Deterministic source-fact descriptions passed for 52/52 local macros. Four-layer dedup retained 28 canonical rows and suppressed 24 exact training-pair duplicates.
- Cross-pool comparison against 293 Processing rows, 6 exact API rows, and 5 random-point rows suppressed 0 additional rows.
- Stable125 adds only legacy `L3_01_01_01 Create Feature Class` as token 124; tokens 0-123 are unchanged.
- Train-only JSONL: 28 rows, 28 source authorities, source regions, call graphs, normalized macro DAGs, and task texts.
- V4 loader/weighted-loss/backward: 28/28 rows, 7 batches, finite loss and gradients, no checkpoint.
- LLM called: false. Training run: false. Validation/test: false. Production merge: not granted.

Train JSONL SHA256: `17cb1de9fbf469ca7cd8e4d9decdcedfd0070088160712533721e12b2d13809e`.
