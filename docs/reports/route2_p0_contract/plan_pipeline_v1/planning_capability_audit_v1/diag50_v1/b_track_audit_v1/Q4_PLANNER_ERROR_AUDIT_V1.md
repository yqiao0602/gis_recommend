# Q4 规划错误 × 池分布审计 V1

预测源：`planner_v2_fmt_dev_full_preds.json`（fmt 检查点，dev-1852）；task_head 对齐 1852/1852。
解析成功 1560/1852（parse_fail 0.1577）；精确匹配 247（0.1334）。

## 按金标模板的池频（训练支持度）分层的错误率

| 池频桶 | n | exact 率 | parse_fail 率 |
|---|---|---|---|
| absent(0) | 1253 | 0.1413 | 0.1915 |
| high(>100) | 199 | 0.2563 | 0.0101 |
| low(2-10) | 166 | 0.0 | 0.1807 |
| mid(11-100) | 155 | 0.1226 | 0.0387 |
| singleton(1) | 79 | 0.0 | 0.1772 |

## 按金标链长分层的错误率

| 长度桶 | n | exact 率 | parse_fail 率 |
|---|---|---|---|
| 1-5 | 553 | 0.2242 | 0.0416 |
| 11-20 | 390 | 0.1333 | 0.2333 |
| 6-10 | 685 | 0.1007 | 0.1139 |
| >20 | 224 | 0.0089 | 0.4464 |

## 高频偏置证据

- 金标模板平均池频：43.9；预测模板平均池频：52.34
- 预测去重模板数：736；预测 Top-10 集中度：0.1756

## 金标家族缺失直方图（对照 R5 X4 INDEX/MASKING 欠发射）

- BAND_SELECT: 229
- ITERATIVE_APPLY: 215
- SPATIAL_FILTER: 174
- VECTOR_LOAD: 130
- TEMPORAL_FILTER: 126
- AGGREGATION: 117
- ATTRIBUTE_FILTER: 101
- BAND_ARITHMETIC: 96
- GEOMETRY_DEFINE: 53
- COLLECTION_MGMT: 47
- SPATIAL_CLIP: 27
- MASKING: 23
- THRESHOLD_LOGIC: 19
- EXPORT_OUTPUT: 16
- TERRAIN_DERIVED: 9
- RASTER_LOAD: 7
- VECTOR_GEOMETRY: 7
- SPECTRAL_INDEX: 6
- CLASSIFICATION: 6
- REGIONAL_STATS: 6