# QGIS family semantic review and admission v1

The two frozen semantic packets were reviewed with the bounded source-fact
reviewer and then passed together through the existing four-layer dedup
classifier.

| lane | structural passed | source-fact Silver candidates | unique after dedup |
|---|---:|---:|---:|
| dissolve -> multipart-to-singleparts | 73 | 73 | 1 |
| buffer -> clip | 34 | 34 | 1 |
| **combined** | **107** | **107** | **2** |

All reviewed rows satisfied the frozen AST audit facts, proposed L3 sequence,
vector I/O contract, and family-level task vocabulary. The 105 suppressed rows
were duplicates at the normalized-DAG layer (72 in the first family, 33 in the
second), not semantic failures. Gold remains zero because the current task text
is a family-level source-fact candidate and still requires independent intent
adjudication. No training rows, authority, evaluation split, or checkpoint was
modified.

The two dedup survivors are candidate-only Silver outputs, not train-only data.
The full dashboard is in
`docs/reports/qgis_asset_production_dashboard_v1/dashboard_v1.md`.
