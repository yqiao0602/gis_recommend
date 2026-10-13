# r5 合成正样本盲评包 v1（第二轮，synthetic）

> **全部候选为合成样本**（规则逻辑测试，不代表真实分布可靠性；owner 七轮）。
> 规则版本冻结 v0.3；标注口径沿用冻结协议（4 主标签 + 两证据字段）。
> 每项给一个主判定；`both_reasonable` 仅用于组内比较类条目。

| 判定 | 含义 |
|---|---|
| `omission` | 缺少任务明确需要的能力（注明缺什么） |
| `unsupported` | 含无依据阶段（注明） |
| `complete_reasonable` | 满足任务全部明确需求（多解容忍：等价/替代路径也算） |
| `unclear` | 无法判定 |

---
## S1（B_clear_omission）

**任务全文：**

Task: [SYNTHETIC] Reservoir surface water mapping
Compute the NDWI from green and near-infrared bands of Sentinel-2 imagery acquired between March and May 2021, apply cloud masking, clip to the reservoir boundary, and export a median NDWI composite for the study period.

### 候选
```
1. RASTER_LOAD
2. MASKING
3. BAND_ARITHMETIC
4. SPATIAL_CLIP
5. AGGREGATION
6. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S2（A_reasonable_complete）

**任务全文：**

Task: [SYNTHETIC] Reservoir surface water mapping
Compute the NDWI from green and near-infrared bands of Sentinel-2 imagery acquired between March and May 2021, apply cloud masking, clip to the reservoir boundary, and export a median NDWI composite for the study period.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. MASKING
4. SPECTRAL_INDEX
5. SPATIAL_FILTER
6. AGGREGATION
7. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S3（A_reasonable_complete）

**任务全文：**

Task: [SYNTHETIC] Reservoir surface water mapping
Compute the NDWI from green and near-infrared bands of Sentinel-2 imagery acquired between March and May 2021, apply cloud masking, clip to the reservoir boundary, and export a median NDWI composite for the study period.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. MASKING
4. BAND_ARITHMETIC
5. SPATIAL_CLIP
6. AGGREGATION
7. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S4（C_vague）

**任务全文：**

Task: [SYNTHETIC] Imagery screening
Perform a suitable analysis of the available imagery for the region of interest.

### 候选
```
1. RASTER_LOAD
2. SPATIAL_FILTER
3. AGGREGATION
```
**判定：** ______（附注：______）

## S5（A_reasonable_complete）

**任务全文：**

Task: [SYNTHETIC] Parcel crop classification
Classify crops using Sentinel-2 imagery from April to October 2022, train a random forest classifier on labeled parcels, and export the classification with per-class area statistics.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. CLASSIFICATION
4. AGGREGATION
5. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S6（B_clear_omission）

**任务全文：**

Task: [SYNTHETIC] Reservoir surface water mapping
Compute the NDWI from green and near-infrared bands of Sentinel-2 imagery acquired between March and May 2021, apply cloud masking, clip to the reservoir boundary, and export a median NDWI composite for the study period.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. MASKING
4. SPATIAL_CLIP
5. AGGREGATION
6. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S7（B_clear_omission）

**任务全文：**

Task: [SYNTHETIC] Reservoir surface water mapping
Compute the NDWI from green and near-infrared bands of Sentinel-2 imagery acquired between March and May 2021, apply cloud masking, clip to the reservoir boundary, and export a median NDWI composite for the study period.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. BAND_ARITHMETIC
4. SPATIAL_CLIP
5. AGGREGATION
6. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S8（C_boundary_untransparent）

**任务全文：**

Task: [SYNTHETIC] Reservoir surface water mapping
Compute the NDWI from green and near-infrared bands of Sentinel-2 imagery acquired between March and May 2021, apply cloud masking, clip to the reservoir boundary, and export a median NDWI composite for the study period.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. MASKING
4. ITERATIVE_APPLY
5. SPATIAL_CLIP
6. AGGREGATION
7. EXPORT_OUTPUT
```
**判定：** ______（附注：______）

## S9（C_unrepresentable）

**任务全文：**

Task: [SYNTHETIC] Urban expansion mapping
Detect urban expansion between 2010 and 2020 using Landsat imagery and produce an expansion map with yearly built-up area statistics.

### 候选
```
1. RASTER_LOAD
2. TEMPORAL_FILTER
3. CLASSIFICATION
4. AGGREGATION
5. EXPORT_OUTPUT
```
**判定：** ______（附注：______）
