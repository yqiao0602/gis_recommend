# QGIS API Vector File Export Train-only v1

- Admitted boundary: one source-verified local `QgsVectorFileWriter.writeAsVectorFormat*` macro that writes an already prepared vector layer; whole-function semantics are not admitted.
- Source-disjoint calibration/holdout: 60 rows, 24 complete local writer macros and 36 fail-closed deferred rows; complete false positives, chain truncations, and silent fallbacks are all zero.
- Full strict replay: 211/211 source SHA verified; 83 complete local writer macros and 128 deferred rows (91 control-flow writers, 23 ambiguous writer calls, 12 reprojections, one control-flow options row, and one unresolved options row).
- Deterministic source-fact descriptions passed for 83/83 complete macros without an LLM. Four-layer dedup retained 18 canonical training pairs and suppressed 65 exact task-text/L3 duplicates.
- Cross-pool comparison against 293 Processing rows, six exact API rows, five random-point API rows, and 28 Create Feature Class rows suppressed zero additional rows.
- Existing stable125 mapping is reused: `L3_07_04_01 Save vector features to file`, token 67. No taxonomy class or token was added.
- Train-only JSONL: 18 rows, 18 source authorities, source regions, call graphs, and task texts; 16 normalized DAGs.
- V4 loader/weighted-loss/backward: 18/18 rows, five batches, finite loss and gradients, no checkpoint.
- LLM called: false. Training run: false. Validation/test: false. Production merge: not granted.

Train JSONL SHA256: `09f3d62ee14159f903a1f3b23d4be5e029e50d9d20401b9228bedbf93e19fa14`.
