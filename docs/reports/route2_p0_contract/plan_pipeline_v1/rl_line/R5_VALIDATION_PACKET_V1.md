# r5 人工判定包 v1（盲评）

> 6 组 × 4 候选 = 24 判定项。每个候选给：任务全文 + 解析后的 stage 列表（乱序、无奖励分、无 gold）。
> 对每个候选给**一个**主判定，必要时附注：

| 判定 | 含义 |
|---|---|
| `omission` | 计划**缺少**任务明确需要的能力（注明缺什么，如 "缺 NDWI 计算"/"缺年度聚合"） |
| `unsupported` | 计划含任务**无依据**的处理阶段（注明哪个阶段） |
| `both_reasonable` | 与组内其他候选路径不同但**都满足任务需求**（多解，注明差异性质） |
| `unclear` | 无法判定（宁选此项不猜） |

---
## 组 5227（short_2_4）

**任务全文：**

Task: Map land surface reflectance
Process Landsat 7 Surface Reflectance data from 2014 to 2017 by applying a cloud masking function to remove cloudy and shadowed pixels, then computes the median composite of the cleaned image collection and visualizes it using blue, green, and red bands (B1, B2, B3) with specified scaling, aiming to produce a clear, cloud-reduced representation of surface reflectance for visual interpretation.

### 候选 A
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```
**判定：** ______（附注：______）

### 候选 B
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```
**判定：** ______（附注：______）

### 候选 C
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```
**判定：** ______（附注：______）

### 候选 D
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
```
**判定：** ______（附注：______）

## 组 17970（short_2_4）

**任务全文：**

Task: Extract elevation profile along transect
Extract an elevation profile along a specified longitudinal transect using ALOS World 3D DSM data, sorting elevation values by longitude and visualizing them as a chart with elevation in meters versus longitude.

### 候选 A
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
```
**判定：** ______（附注：______）

### 候选 B
（1 个阶段带重复计数）
```
1. RASTER_LOAD x2
2. BAND_ARITHMETIC x1
3. ATTRIBUTE_FILTER x1
```
**判定：** ______（附注：______）

### 候选 C
（1 个阶段带重复计数）
```
1. RASTER_LOAD x2
2. BAND_SELECT x1
```
**判定：** ______（附注：______）

### 候选 D
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. AGGREGATION x1
```
**判定：** ______（附注：______）

## 组 823（mid_5_8）

**任务全文：**

Task: Cluster vegetation and land cover
Generate an annual median composite of Landsat 5 surface reflectance imagery for 2010, masks clouds and shadows, clips to a watershed boundary (C6C5), and applies K-means clustering (15 clusters) to classify land cover patterns, particularly focusing on vegetation and surface features. The outputs include a true-color image, multiple band composites for vegetation analysis, the final classified cluster map, and both the composite and classification results are exported to Google Drive as GeoTIFFs.

### 候选 A
（1 个阶段带重复计数）
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x40
5. CLASSIFICATION x1
```
**判定：** ______（附注：______）

### 候选 B
```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. ITERATIVE_APPLY x1
5. CLASSIFICATION x1
```
**判定：** ______（附注：______）

### 候选 C
（1 个阶段带重复计数）
```
1. RASTER_LOAD x4
2. TEMPORAL_FILTER x1
3. CLASSIFICATION x1
```
**判定：** ______（附注：______）

### 候选 D
（1 个阶段带重复计数）
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x4
```
**判定：** ______（附注：______）

## 组 29519（mid_5_8）

**任务全文：**

Task: Extract surface water using NDWI
Compute the Normalized Difference Water Index (NDWI) from Landsat 5 TM surface reflectance imagery to identify surface water features over a specific region between July and November 1997. It applies pixel quality masking to remove clouds and cloud shadows, calculates NDWI using green and near-infrared bands, scales the reflectance values, and generates a median composite NDWI image clipped to the study area. The output includes a true-color visualization of the input imagery, a mapped NDWI layer, and an exported GeoTIFF of the median NDWI result for offline use.

### 候选 A
```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. ITERATIVE_APPLY x1
```
**判定：** ______（附注：______）

### 候选 B
（1 个阶段带重复计数）
```
1. RASTER_LOAD x2
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x1
```
**判定：** ______（附注：______）

### 候选 C
（1 个阶段带重复计数）
```
1. RASTER_LOAD x2
2. ITERATIVE_APPLY x1
```
**判定：** ______（附注：______）

### 候选 D
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. SPATIAL_FILTER x1
```
**判定：** ______（附注：______）

## 组 13612（long_9plus）

**任务全文：**

Task: Analyze NDVI in agricultural regions
Calculate and visualizes NDVI values over multiple geographic regions (EC6, EC5, EC12B, EC12C, EC10B) using Sentinel-2 surface reflectance data from January to February 2023. It generates a median NDVI composite, clips it to specified regions, computes regional areas, and creates time-series line and scatter charts of mean NDVI per region to analyze vegetation dynamics.

### 候选 A
（1 个阶段带重复计数）
```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x2
```
**判定：** ______（附注：______）

### 候选 B
（1 个阶段带重复计数）
```
1. VECTOR_LOAD x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x1
5. SPATIAL_FILTER x1
6. AGGREGATION x3
```
**判定：** ______（附注：______）

### 候选 C
（2 个阶段带重复计数）
```
1. VECTOR_LOAD x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
5. ATTRIBUTE_FILTER x2
6. AGGREGATION x2
```
**判定：** ______（附注：______）

### 候选 D
（2 个阶段带重复计数）
```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x2
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. TEMPORAL_FILTER x1
6. BAND_SELECT x1
7. AGGREGATION x2
```
**判定：** ______（附注：______）

## 组 30160（long_9plus）

**任务全文：**

Task: Classify land cover types
Classify land cover into six categories (urban, water, forest, agriculture, grassland, unuseland) using Sentinel-2 surface reflectance data from June to October 2020, applying a Random Forest classifier trained on labeled regions, and exports the resulting classification map with accuracy assessment including kappa, overall accuracy, and area calculation per class.

### 候选 A
（1 个阶段带重复计数）
```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x1
3. BAND_SELECT x1
4. TEMPORAL_FILTER x1
5. SPATIAL_FILTER x1
6. AGGREGATION x2
```
**判定：** ______（附注：______）

### 候选 B
（2 个阶段带重复计数）
```
1. ATTRIBUTE_FILTER x2
2. RASTER_LOAD x2
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
5. CLASSIFICATION x1
6. BAND_ARITHMETIC x1
7. AGGREGATION x1
```
**判定：** ______（附注：______）

### 候选 C
（1 个阶段带重复计数）
```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x3
4. ITERATIVE_APPLY x1
5. AGGREGATION x1
6. CLASSIFICATION x1
```
**判定：** ______（附注：______）

### 候选 D
（2 个阶段带重复计数）
```
1. ATTRIBUTE_FILTER x3
2. BAND_SELECT x1
3. RASTER_LOAD x3
```
**判定：** ______（附注：______）
