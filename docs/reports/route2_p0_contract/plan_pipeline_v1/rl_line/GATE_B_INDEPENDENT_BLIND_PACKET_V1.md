# Gate B 独立集盲评包 v1（10 任务 × 8 候选 = 80 候选）

> 规则 v0.5.1；**盲评：不显示 r5 的 missing/covered 判定**。
> 判定单位 = 候选 × r5-required 槽位；另对候选整体标注非必需步骤。

## 槽位级判定口径（owner 十二轮）

| 标签 | 含义 |
|---|---|
| `omission` | 任务明确要求该能力，候选无可语义替代的可见实现（真实遗漏） |
| `covered` | 候选已有语义上足以实现该能力的阶段或可核验等价 |
| `requirement_uncertain` | 任务文本不足以确定该能力是否必需 |
| `representation_boundary` | 任务需要该能力但阶段词表无法表达（记词表缺口，不算模型遗漏） |
| `non_required` | 任务根本不要求该能力 |

## 候选级附加字段

- `unnecessary_stages`：候选中任务无依据的冗余阶段（列名；无则空）

---
## 组 2235

**任务全文：**

Task: Identify least cloudy pixels
Compute a cloud score for each Landsat 8 image based on spectral and thermal thresholds, then creates a mosaic of the least cloudy pixels using the 'cloudscore' band to prioritize clear observations.

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. AGGREGATION x1
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x2
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. COLLECTION_MGMT x1
5. ITERATIVE_APPLY x3
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. BAND_SELECT x3
2. RASTER_LOAD x1
3. ITERATIVE_APPLY x1
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x1
3. AGGREGATION x1
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x2
2. BAND_ARITHMETIC x1
3. BAND_SELECT x1
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. COLLECTION_MGMT x1
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
```

| MASK | ______ | ______ |
**unnecessary_stages：** ______

## 组 3084

**任务全文：**

Task: Compare MODIS NDVI from Terra and Aqua
Compare the minimum NDVI values derived from two MODIS surface reflectance products (MYD09Q1 and MOD09Q1) over a specific region during a 16-day period in July 2019. It calculates NDVI using band ratios from red and near-infrared bands, applies cloud and land/water masking using QA bits, clips the results to a vector boundary, computes the difference between the two sensors' NDVI composites, and visualizes the results with custom color palettes. Outputs include three map layers: NDVI from Aqua, NDVI from Terra, and their difference, along with the study area boundary.

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['CHART_PLOT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x2
3. RASTER_LOAD x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x2
4. SPATIAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. BAND_SELECT x1
5. ITERATIVE_APPLY x1
6. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. BAND_SELECT x1
5. AGGREGATION x4
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x4
2. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x1
5. AGGREGATION x1
6. RASTER_LOAD x1
7. SPATIAL_FILTER x1
8. TEMPORAL_FILTER x1
9. ATTRIBUTE_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. ATTRIBUTE_FILTER x4
2. RASTER_LOAD x2
3. None x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
**unnecessary_stages：** ______

## 组 10540

**任务全文：**

Task: Calculate annual precipitation mean
Calculate the mean annual precipitation from the PERSIANN-CDR dataset for the year 2003, clips it to a user-defined geometry (table), and exports the resulting image to Google Drive. It also computes and prints the mean precipitation value over the region.

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. AGGREGATION x3
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. AGGREGATION x4
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. AGGREGATION x3
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. BAND_SELECT x3
3. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. TEMPORAL_FILTER x2
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. AGGREGATION x3
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x1
2. TEMORAL_FILTER x1
3. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| SPATIAL | ______ | ______ |
| STATS | ______ | ______ |
**unnecessary_stages：** ______

## 组 10893

**任务全文：**

Task: Analyze nighttime LST trends
Compute 3-monthly composite nighttime land surface temperature (LST) from VIIRS and MODIS data over a user-defined AOI between December 2019 and March 2023, generates a time series chart of median LST values, visualizes the mean composite, and exports each 3-month composite to Google Drive.

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['CHART_PLOT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x2
4. BAND_SELECT x1
5. ITERATIVE_APPLY x2
6. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. BAND_SELECT x1
3. TEMPORAL_FILTER x2
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. RASTER_LOAD x4
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. BAND_SELECT x1
5. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x1
4. BAND_SELECT x1
5. SPATIAL_FILTER x1
6. ITERATIVE_APPLY x1
7. RASTER_LOAD x1
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x4
2. TEMPORAL_FILTER x4
3. BAND_SELECT x1
4. AGGREGATION x1
5. ATTRIBUTE_FILTER x1
6. EXPORT_OUTPUT x1
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x1
3. BAND_SELECT x1
4. ITERATIVE_APPLY x1
5. TEMPORAL_FILTER x2
6. AGGREGATION x1
7. VECTOR_LOAD x1
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. RASTER_LOAD x1
2. ITERATIVE_APPLY x1
3. TEMPORAL_FILTER x1
4. BAND_SELECT x1
5. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x5
4. ATTRIBUTE_FILTER x4
```

| TEMPORAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

## 组 24025

**任务全文：**

Task: Analyze seasonal surface reflectance
Generate mean seasonal surface reflectance composites using Sentinel-2 top-of-atmosphere imagery over California, applying cloud masking and visualizing true-color (B4, B3, B2) images for winter, spring, summer, and fall of 2020–2021.

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['CHART_PLOT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. ATTRIBUTE_FILTER x1
2. VECTOR_LOAD x1
3. VECTOR_GEOMETRY x1
4. VECTOR_CLIP x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x2
2. TEMPORAL_FILTER x6
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x2
3. SPATIAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x2
3. COLLECTION_MGMT x1
4. RASTER_LOAD x1
5. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. ATTRIBUTE_FILTER x1
2. VECTOR_LOAD x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. TEMPORAL_FILTER x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
**unnecessary_stages：** ______

## 组 24515

**任务全文：**

Task: Classify land cover types
Classify land cover into Water body, Vegetation, Bareland, and Grassland using Sentinel-2 imagery from October 2022 over a specified AOI. It computes NDVI, trains a CART classifier on labeled sample points, generates a classified land cover map, calculates area per class in square kilometers, displays the result on the map, and exports the classified image to Google Drive.

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. RASTER_LOAD x3
2. ATTRIBUTE_FILTER x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x1
5. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x2
5. BAND_SELECT x1
6. CLASSIFICATION x1
7. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x1
5. BAND_SELECT x1
6. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. ATTRIBUTE_FILTER x1
3. SPATIAL_FILTER x1
4. TEMPORAL_FILTER x1
5. CLASSIFICATION x1
6. BAND_ARITHMETIC x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x6
5. COLLECTION_MGMT x1
6. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x1
5. CLASSIFICATION x1
6. BAND_ARITHMETIC x1
7. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
None. TEMPORAL_FILTER x1
None. ATTRIBUTE_FILTER x5
5. BAND_ARITHMETIC x1
6. AGGREGATION x8
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ATTRIBUTE_FILTER x2
4. SPATIAL_FILTER x1
5. BAND_ARITHMETIC x1
6. AGGREGATION x2
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| STATS | ______ | ______ |
| CLASSIFY | ______ | ______ |
**unnecessary_stages：** ______

## 组 25159

**任务全文：**

Task: Generate true color composite
Generate a true-color composite image using median-reduced Landsat 8 Surface Reflectance data from 2014 to 2020. It applies cloud and shadow masking via the pixel_qa band, computes a median pixel value across the image collection, and visualizes the result using bands B4, B3, and B2 scaled between 0 and 0.3. The output is a visually enhanced satellite image layer displayed on the map.

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['CHART_PLOT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. RASTER_LOAD x1
2. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x3
2. TEMPORAL_FILTER x1
3. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

## 组 29444

**任务全文：**

Task: Analyze vegetation health with NDVI
Calculate NDVI from median Landsat 8 surface reflectance imagery over Paradise, California, to assess vegetation health in early 2019, post-Camp Fire. It visualizes the median RGB image and corresponding NDVI layer, then exports a GeoTIFF of the median composite with a mask for cloud-free pixels to Google Drive.

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['CHART_PLOT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. VECTOR_LOAD x1
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x3
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x1
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. AGGREGATION x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x3
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x3
3. RASTER_LOAD x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

## 组 31187

**任务全文：**

Task: Calculate NDVI growing season composite
Compute the median NDVI composite across the frost-free growing season (April 30–October 13) for each year from 2016 to 2024 over Toronto, Ontario, using Landsat 8 Surface Reflectance (SR) imagery. It applies a custom NDVI function (using SR_B4 and SR_B5 bands), filters by geometry and date range per year, merges all annual NDVI image collections, reduces to a single median NDVI image (pixel-wise median across all dates/years), clips to the study geometry, visualizes with a blue-white-green palette, and exports the final 20-m resolution GeoTIFF to Google Drive in UTM zone 17N (EPSG:26917).

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['CHART_PLOT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. VECTOR_LOAD x1
2. RASTER_LOAD x1
3. ATTRIBUTE_FILTER x2
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. ATTRIBUTE_FILTER x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. ATTRIBUTE_FILTER x1
2. RASTER_LOAD x1
3. None x1
4. None x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x2
3. SPATIAL_FILTER x1
4. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x2
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x2
4. ATTRIBUTE_FILTER x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. ATTRIBUTE_FILTER x3
2. RASTER_LOAD x1
3. SPATIAL_FILTER x1
4. TEMPORAL_FILTER x1
```

| TEMPORAL | ______ | ______ |
| INDEX | ______ | ______ |
| SPATIAL | ______ | ______ |
| COMPOSITE | ______ | ______ |
**unnecessary_stages：** ______

## 组 31609

**任务全文：**

Task: Analyze NDVI time series by landcover
Analyze Sentinel-2 TOA reflectance and NDVI time series over different landcover types (urban, grassland, water, forest, soil) between 2016 and 2018, generating spectral profiles and temporal NDVI trends for each class using median-composited, cloud-screened imagery.

（解析注：requirement_uncertain 槽位 = 无；词表边界信号 = ['PROFILE_TRANSECT']——此类不强制判定）

**r5-required 槽位（逐候选逐槽位判定）：**

| 槽位 | 判定（omission / covered / requirement_uncertain / representation_boundary / non_required） | 证据附注 |
|---|---|---|
**候选 0**

```
1. ATTRIBUTE_FILTER x4
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. SPATIAL_FILTER x1
5. AGGREGATION x7
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 1**

```
1. RASTER_LOAD x1
2. TEMPORAL_FILTER x1
3. SPATIAL_FILTER x1
4. ATTRIBUTE_FILTER x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 2**

```
1. VECTOR_LOAD x1
2. ATTRIBUTE_FILTER x3
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 3**

```
1. RASTER_LOAD x1
2. SPATIAL_FILTER x1
3. TEMPORAL_FILTER x1
4. ATTRIBUTE_FILTER x2
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 4**

```
1. RASTER_LOAD x1
2. BAND_ARITHMETIC x3
3. AGGREGATION x4
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 5**

```
1. GEOMETRY_DEFINE x1
2. VECTOR_LOAD x1
3. RASTER_LOAD x1
4. SPATIAL_FILTER x1
5. TEMPORAL_FILTER x1
6. ATTRIBUTE_FILTER x1
7. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 6**

```
1. AGGREGATION x1
2. RASTER_LOAD x1
3. TEMPORAL_FILTER x1
4. ITERATIVE_APPLY x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______

**候选 7**

```
1. RASTER_LOAD x1
2. AGGREGATION x3
3. BAND_SELECT x1
```

| TEMPORAL | ______ | ______ |
| MASK | ______ | ______ |
| INDEX | ______ | ______ |
**unnecessary_stages：** ______
