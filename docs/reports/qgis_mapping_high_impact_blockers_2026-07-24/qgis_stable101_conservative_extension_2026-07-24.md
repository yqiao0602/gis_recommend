# QGIS stable-N保守扩展正式草案（2026-07-24）

本草案只纳入服务器源码片段复核通过的4个保守映射，不修改`outputs_v2` authority，不生成训练集，不训练模型。

## 版本口径

- 基线：`stable98`，98个L3。
- 草案：`stable101`，101个L3。
- 旧token ID保持不变，新L3只追加到末尾。
- `native:createspatialindex`和`native:saveselectedfeatures`不在本草案内。

## 新增L3

| L3 | token | 名称 | 说明 |
|---|---:|---|---|
| `L3_01_05_02` | 98 | Repair Geometry | Repairs invalid feature geometries automatically. |
| `L3_01_09_03` | 99 | Raster-Vector Conversion | Converts between raster and vector formats: raster to polygon/point/line or vector to raster. |
| `L3_01_10_01` | 100 | Project/Reproject | Transforms spatial data from one coordinate reference system (CRS) to another including projection and datum transformation. |

## QGIS算子映射

| QGIS operator | L3 | 证据 |
|---|---|---|
| `gdal:polygonize` | `L3_01_09_03` Raster-Vector Conversion | 3条源码片段，源码层唯一命中512 |
| `gdal:rasterize` | `L3_01_09_03` Raster-Vector Conversion | 3条源码片段，源码层唯一命中576 |
| `native:fixgeometries` | `L3_01_05_02` Repair Geometry | 3条源码片段，源码层唯一命中924 |
| `native:reprojectlayer` | `L3_01_10_01` Project/Reproject | 3条源码片段，源码层唯一命中1292 |

## 覆盖影响

| 场景 | 完整记录 | 唯一链 |
|---|---:|---:|
| stable-98草案 | 802 | 270 |
| stable-N保守草案 | 1442 | 449 |
| 增量 | 640 | 179 |

## 明确排除

- `native:createspatialindex`：support/export boundary confirmed by source review; excluded from the conservative stable-N training-target draft。
- `native:saveselectedfeatures`：support/export boundary confirmed by source review; excluded from the conservative stable-N training-target draft。

## 准入状态

- `taxonomy_admission=not_granted`。
- `training_admission=not_granted`。
- 下一步只能进入taxonomy authority人工确认；确认前不得写入生产映射或训练集。
