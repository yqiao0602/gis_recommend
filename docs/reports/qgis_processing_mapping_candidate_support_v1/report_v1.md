# QGIS mapping candidate support audit v1

| operator | candidate L3 | source rows | normalized bodies | gate |
|---|---|---:|---:|---|
| `native:boundary` | `L3_02_07_03` | 26 | 17 | defer |
| `native:convexhull` | `L3_02_05_12` | 27 | 18 | defer |
| `native:removeduplicatesbyattribute` | `L3_01_05_04` | 45 | 30 | pass |
| `qgis:linestopolygons` | `L3_02_07_02` | 34 | 23 | defer |
| `qgis:voronoipolygons` | `L3_02_07_07` | 37 | 30 | pass |

- Combined new mapping-complete rows: 37
- Combined new direct rows: 0
- Mapping/training admission: not granted
