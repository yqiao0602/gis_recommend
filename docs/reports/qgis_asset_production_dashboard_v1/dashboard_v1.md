# QGIS asset production dashboard v1

- Raw sources: 47852
- SHA-verified rows: 47542
- Family candidates reviewed: 107
- Silver candidates before dedup: 107
- Unique Silver candidates after four-layer dedup: 2
- Gold candidates: 0
- Training rows emitted: 0

| Asset pool | Rows | Status | Next |
|---|---:|---|---|
| processing_workflow | 1236 | family_production | calibration -> qualification -> dedup |
| processing_operator | 591 | queued | operator grounding |
| processing_implementation | 1088 | queued | semantic recovery |
| processing_dynamic_candidate | 496 | deferred | bounded dynamic recovery |
| api_semantic_unit | 3209 | queued | API -> GIS semantic -> L3 |
| api_pattern | 4880 | queued | pattern qualification |
| api_implementation_evidence | 12407 | evidence_only | support other pools |
| unresolved | 23945 | deferred | do not process yet |

| Family lane | Structural passed | Semantic Silver | Dedup unique |
|---|---:|---:|---:|
| native:dissolve|native:multiparttosingleparts | 73 | 73 | 1 |
| native:buffer|native:clip | 34 | 34 | 1 |
