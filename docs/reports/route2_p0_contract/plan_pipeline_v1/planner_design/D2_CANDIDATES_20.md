# D2 粒度等价候选（20 对）——归一化后语义结构是否一致

每对判定：unrolled 与 compact 归一化后是否保留相同操作语义+依赖+重复条件？裁定：equivalent / not_equivalent（指出丢失的语义约束）/ needs_full_dag

| # | unrolled（阶段/组/最大连发） | compact（阶段/组） | famJ | U 标题 | C 标题 | 裁定 | 丢失约束 |
|---|---|---|---|---|---|---|---|
| 1 | 20/0/1 | 4/0 | 1.0 | Analyze vegetation dynamics over time | Analyze vegetation trends | ______ | ______ |
| 2 | 29/0/1 | 5/0 | 1.0 | Compare land cover change | Map land cover with Landsat | ______ | ______ |
| 3 | 12/0/1 | 6/0 | 1.0 | Classify land cover and detect cocoa change | Classify land cover types | ______ | ______ |
| 4 | 12/0/1 | 6/0 | 1.0 | Classify cocoa and land cover change | Classify land cover types | ______ | ______ |
| 5 | 12/0/1 | 6/0 | 1.0 | Classify cocoa and forest areas | Classify land cover types | ______ | ______ |
| 6 | 12/0/1 | 4/1 | 1.0 | Analyze NDVI temporal change | Analyze NDWI seasonal patterns | ______ | ______ |
| 7 | 12/0/1 | 7/1 | 1.0 | Analyze NDVI change over time | Analyze NDVI and LST trends | ______ | ______ |
| 8 | 31/0/1 | 6/1 | 1.0 | Classify land cover types | Classify land cover types | ______ | ______ |
| 9 | 31/0/1 | 6/1 | 1.0 | Classify land cover types | Cluster land cover types | ______ | ______ |
| 10 | 19/0/1 | 4/0 | 1.0 | Analyze NDVI time series for forest types | Analyze NDVI time series | ______ | ______ |
| 11 | 81/0/1 | 4/0 | 1.0 | Analyze NDVI trends over time | Analyze NDVI time series | ______ | ______ |
| 12 | 15/0/1 | 3/1 | 1.0 | Analyze surface water extent using MSI | Identify surface water using NDWI | ______ | ______ |
| 13 | 10/0/1 | 5/0 | 1.0 | Compare NDVI from TOA and SR | Compute NDVI from Sentinel-2 | ______ | ______ |
| 14 | 12/0/1 | 4/1 | 1.0 | Analyze vegetation change over time | Analyze NDVI vegetation index | ______ | ______ |
| 15 | 12/0/1 | 4/1 | 1.0 | Analyze NDVI change over time | Analyze NDVI vegetation index | ______ | ______ |
| 16 | 42/0/1 | 5/0 | 1.0 | Classify land cover in Harare | Cluster land cover types | ______ | ______ |
| 17 | 12/0/1 | 5/0 | 1.0 | Analyze air temperature variation | Analyze sea surface temperature anomaly | ______ | ______ |
| 18 | 15/0/1 | 3/1 | 1.0 | Analyze NDVI temporal changes | Analyze monthly NDVI patterns | ______ | ______ |
| 19 | 13/0/1 | 12/4 | 1.0 | Analyze NDVI change over time | Analyze NDVI and EVI trends | ______ | ______ |
| 20 | 15/0/1 | 3/0 | 1.0 | Analyze NDVI temporal changes | Analyze NDVI time series | ______ | ______ |