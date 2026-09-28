# QGIS Processing mapping-gap stable106 draft v1

Report-only draft. No taxonomy, production mapping, or training admission is granted.

| Rank | Operator | Decision | Candidate L3 | Single-gap rows | Unique chains |
|---:|---|---|---|---:|---:|
| 1 | `gdal:importvectorintopostgisdatabaseavailableconnections` | database_sql_excluded | `` | 126 | 1 |
| 2 | `native:creategrid` | core_taxonomy_candidate | `L3_02_03_06` | 50 | 19 |
| 3 | `native:saveselectedfeatures` | support_export_boundary | `` | 44 | 22 |
| 4 | `native:joinattributestable` | core_taxonomy_candidate | `L3_01_03_05` | 43 | 16 |
| 5 | `native:postgisexecutesql` | database_sql_excluded | `` | 27 | 2 |
| 6 | `native:createspatialindex` | support_export_boundary | `` | 24 | 4 |
| 7 | `native:deleteduplicategeometries` | core_taxonomy_candidate | `L3_01_05_04` | 20 | 6 |
| 8 | `native:polygonstolines` | core_taxonomy_candidate | `L3_02_07_03` | 13 | 8 |
| 9 | `native:importintopostgis` | database_sql_excluded | `` | 13 | 4 |
| 10 | `native:filedownloader` | support_export_boundary | `` | 12 | 1 |
| 11 | `native:pointstopath` | unresolved | `` | 10 | 4 |
| 12 | `grass7:r.neighbors` | unresolved | `` | 10 | 2 |
| 13 | `native:simplifygeometries` | core_taxonomy_candidate | `L3_02_05_01` | 9 | 6 |
| 14 | `native:joinbynearest` | existing_stable101_alias | `L3_02_04_01` | 9 | 3 |
| 15 | `native:rasterize` | unresolved | `` | 9 | 2 |
