# T1 试审 20 条：协议校准包（2026-10-18）

- **目的**：检验裁定协议是否清晰，**不用于估计全量准确率**，不合并、不改 split。
- **范围**：105 条 T1 截断跨 split 边中的 20 条，覆盖 A/C 与五种证据模式。
- **机器台账**：`B_TRACK_T1_PILOT20_V1.json`；对账：`B_TRACK_GATE1_RECONCILIATION_V1.json`。

## 0. 机器级对账

| 检查 | 结果 |
| --- | --- |
| `pending_hi_v3_recomputed` | 4391 |
| `review_pending` | 4391 |
| `pending_sets_equal` | True |
| `deferred_hi_recomputed` | 1387 |
| `review_deferred` | 1387 |
| `deferred_sets_equal` | True |
| `union_review` | 5778 |
| `union_recomputed` | 5778 |
| `overlap_pending_deferred` | 0 |
| `t1_count` | 105 |
| `t1_expected` | 105 |
| `t1_sets_equal` | True |
| `t2_count` | 1399 |
| `t2_expected` | 1399 |
| `t2_sets_equal` | True |
| `review_id_unique` | True |
| `pair_unique_in_review` | True |
| `class_changes_vs_summary` | {'A': 2739, 'B': 109, 'C': 2930} |
| **all_pass** | **True** |

> 对账从 decision log + V3 manifest 独立重算 pending/deferred/T1/T2 集合，按无序端点对比较；不是只核对汇总数字。

## 1. 覆盖

- 20 条 = A 16 / C 4；规则 {'G1_exact_asset_set_group': 14, 'D2_star_group': 6}
- 模式：{'same_assets_diff_title': 4, 'mixed_or_weak': 5, 'same_targets_diff_title': 5, 'same_title_diff_source': 4, 'task_type_diff': 2}
- 资产证据范围：{'project_shared': 9, 'task_specific': 3, 'unclear': 8}
- Agent 初步建议：{'MERGE_provisional': 17, 'UNRESOLVED': 3}
- 端点族大小之和 > 10,000 的：20 条

## 1.1 试审观察（agent）

- project_shared 9 条：8 条仍有文本/链第二轴 → MERGE_provisional；1 条仅资产轴（R00888）→ UNRESOLVED。asset_evidence_scope 起到“阻断资产单证合并”的作用，但不会否决多轴证据。
- 截断 20/20 的端点族大小之和 > 10,000（G1 14 / D2 6）；截断是族上限造成的真实分歧，不是证据缺失。
- same_title_diff_source 4 条（built-up / fire）T=0.667、O=2、无共享资产；暂 MERGE，但需源码级核验定义（BU index vs nighttime lights vs non-forest built-up）。
- task_type_diff 2 条均 UNRESOLVED；协议要求至少一个目标/来源/链之外的独立证据。
- 地区/时间/输入条件不同 5 条（R00150、R01290、R00257、R01340、R00916）；是否同族需 owner 先锁定“条件差异”口径。

## 2. 试审总表

| rank | review_id | class | pattern | rule | split | asset_scope | agent | T | B | O | AS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | R00787 | A | `same_assets_diff_title` | G1 | t-s | project_shared | MERGE_provisional | 0.3333 | 0.3469 | cover,land | 78 |
| 2 | R00888 | A | `same_assets_diff_title` | G1 | t-s | project_shared | UNRESOLVED | 0.3333 | 0.3226 | cover,land | 78 |
| 3 | R00769 | A | `same_assets_diff_title` | G1 | t-s | project_shared | MERGE_provisional | 0.375 | 0.3241 | cover,land | 50 |
| 4 | R00916 | A | `same_assets_diff_title` | G1 | v-t | project_shared | MERGE_provisional | 0.3333 | 0.4362 | cover,land | 21 |
| 5 | R00150 | A | `mixed_or_weak` | G1 | s-t | project_shared | MERGE_provisional | 0.6 | 0.4787 | cover,land | 15 |
| 6 | R00652 | A | `mixed_or_weak` | G1 | t-s | project_shared | MERGE_provisional | 0.6 | 0.463 | cover,land | 11 |
| 7 | R00653 | A | `mixed_or_weak` | G1 | t-s | project_shared | MERGE_provisional | 0.6 | 0.3051 | cover,land | 11 |
| 8 | R00257 | A | `mixed_or_weak` | G1 | t-s | project_shared | MERGE_provisional | 0.6 | 0.4848 | cover,land | 9 |
| 10 | R00356 | A | `mixed_or_weak` | G1 | t-s | project_shared | MERGE_provisional | 0.6 | 0.375 | cover,land | 8 |
| 45 | R01348 | A | `same_targets_diff_title` | G1 | t-s | task_specific | MERGE_provisional | 0.4286 | 0.6304 | cover,land | 2 |
| 47 | R01143 | A | `same_targets_diff_title` | G1 | t-s | unclear | MERGE_provisional | 0.5 | 0.3902 | cover,land | 2 |
| 48 | R01290 | A | `same_targets_diff_title` | G1 | t-s | unclear | MERGE_provisional | 0.5 | 0.3551 | cover,land | 2 |
| 50 | R01340 | A | `same_targets_diff_title` | G1 | v-t | unclear | MERGE_provisional | 0.375 | 0.4643 | cover,land | 2 |
| 51 | R01275 | A | `same_targets_diff_title` | G1 | t-s | unclear | MERGE_provisional | 0.4286 | 0.3421 | cover,land | 2 |
| 88 | R04697 | C | `same_title_diff_source` | D2 | t-v | unclear | MERGE_provisional | 0.6667 | 0.2087 | built,up | 0 |
| 89 | R04691 | C | `same_title_diff_source` | D2 | t-v | unclear | MERGE_provisional | 0.6667 | 0.2035 | built,up | 0 |
| 90 | R01374 | A | `same_title_diff_source` | D2 | t-s | unclear | MERGE_provisional | 0.6667 | 0.1827 | built,up | 0 |
| 92 | R01372 | A | `same_title_diff_source` | D2 | t-s | unclear | MERGE_provisional | 0.6667 | 0.1683 | affected,fire | 0 |
| 99 | R05668 | C | `task_type_diff` | D2 | t-s | task_specific | UNRESOLVED | 0.1538 | 0.1343 | terrain | 1 |
| 100 | R05660 | C | `task_type_diff` | D2 | s-t | task_specific | UNRESOLVED | 0.3333 | 0.1759 |  | 1 |

## 3. 逐条卷宗

### R00787 — A_merge_candidate / `same_assets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F5fb95067f1fbbd5a` (6019 组件)；族大小和 17544 （cap 10000，超限=True）。
- **截断组**：`G6465ebad24c3b001`，组记录 {'n_components': 2, 'signature_group_size': 2, 'anchor': 11706, 'n_merged': 1, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 1/1。
- **端点 A**：component `11706`，family `Fa5ad55d64d83cd29`，split `t`，script `script_66373`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover into four categories (Vetylw, Low, Medium, High) using a Gradient Tree Boosting classifier trained on multi-source remote sensing data including Sentinel-1 SAR, Sentinel-2 optical indices, Landsat 8 derived vegetation indices, terrain attributes, soil, geology, and forest structure. The output includes a classified land cover map, variable import
- **端点 B**：component `86005`，family `F5fb95067f1fbbd5a`，split `s`，script `script_66376`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using multi-source remote sensing data the workflow performs land cover classification using a Random Forest model trained on a wide array of multispectral, terrain, soil, vegetation indices, SAR texture, and seasonal spectral difference features. It generates a classified land cover map and derives a confidence index (SEDCI) based on prediction probabilities from multipl
- **证据**：T=0.3333，B=0.3469，有效目标=['cover', 'land']，共享数据族=['custom', 'landsat', 'other', 'sentinel-1', 'sentinel-2']，共享资产=78，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`project_shared`；依据 {'group_size': 2, 'shared_assets': 78, 'custom_assets': 72, 'asset_families': ['custom', 'landsat', 'other', 'sentinel-1', 'sentinel-2']}。
- **资产样本**：COPERNICUS/S1_GRD, COPERNICUS/S2, COPERNICUS/S2_SR, JAXA/ALOS/PALSAR/YEARLY/SAR, LANDSAT/LC08/C01/T1_SR, LANDSAT/LC08/C01/T1_TOA, projects/chenyangcyhyy/assets/EOSx, projects/chenyangcyhyy/assets/LOSx …
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00888 — A_merge_candidate / `same_assets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F5fb95067f1fbbd5a` (6019 组件)；族大小和 17544 （cap 10000，超限=True）。
- **截断组**：`G91c3c7fdb203640c`，组记录 {'n_components': 4, 'signature_group_size': 4, 'anchor': 40905, 'n_merged': 2, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 2/2。
- **端点 A**：component `40905`，family `Fa5ad55d64d83cd29`，split `t`，script `script_66371`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover into four categories (Vetylw, Low, Medium, High) using a combination of Sentinel-1 SAR, Sentinel-2 optical indices, Landsat 8 surface reflectance, terrain features, soil, vegetation dynamics, and texture metrics. It trains an SVM classifier with labeled samples and produces a classified map exported to Google Drive.
- **端点 B**：component `41240`，family `F5fb95067f1fbbd5a`，split `s`，script `script_66359`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using multi-source remote sensing data the workflow performs land cover classification using a Random Forest model trained on a wide array of environmental variables derived from Sentinel-1, Sentinel-2, Landsat 8, ALOS PALSAR, and numerous terrain, soil, vegetation, and climate indices. It outputs a classified land cover map with four classes (Vetylw, Low, Medium, High), 
- **证据**：T=0.3333，B=0.3226，有效目标=['cover', 'land']，共享数据族=['custom', 'landsat', 'other', 'sentinel-1', 'sentinel-2']，共享资产=78，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=0。
- **资产证据范围**：`project_shared`；依据 {'group_size': 4, 'shared_assets': 78, 'custom_assets': 72, 'asset_families': ['custom', 'landsat', 'other', 'sentinel-1', 'sentinel-2']}。
- **资产样本**：COPERNICUS/S1_GRD, COPERNICUS/S2, COPERNICUS/S2_SR, JAXA/ALOS/PALSAR/YEARLY/SAR, LANDSAT/LC08/C01/T1_SR, LANDSAT/LC08/C01/T1_TOA, users/chenyangcyhyy/AnalyticalHillshading, users/chenyangcyhyy/Aspect …
- **Agent 初步建议**：`UNRESOLVED` — project-shared assets plus fewer than 2 strong text/chain axes。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00769 — A_merge_candidate / `same_assets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F5fb95067f1fbbd5a` (6019 组件)；族大小和 17544 （cap 10000，超限=True）。
- **截断组**：`Ga6e25cbb13b9c695`，组记录 {'n_components': 5, 'signature_group_size': 5, 'anchor': 54640, 'n_merged': 4, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 3/4。
- **端点 A**：component `8291`，family `F5fb95067f1fbbd5a`，split `s`，script `script_66361`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using multisource remote sensing data Classify land cover by training a Random Forest model using a combination of Sentinel-1 SAR texture features, Sentinel-2 spectral indices (summer and winter), and numerous terrain, soil, vegetation, and climate variables derived from DEMs and other environmental layers. The output is a classified land cover map and associated probabil
- **端点 B**：component `54640`，family `Fa5ad55d64d83cd29`，split `t`，script `script_240628`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover (LC) types in the Jiuxian region using a Random Forest classifier in Google Earth Engine. It integrates multi-source data including Sentinel-1 SAR imagery (VV/VH backscatter and GLCM texture features), Sentinel-2 optical indices (NDVI, EVI, SAVI, etc.) from summer and winter seasons, and numerous terrain, soil, geology, and climate variables deri
- **证据**：T=0.375，B=0.3241，有效目标=['cover', 'land']，共享数据族=['custom', 'sentinel-1', 'sentinel-2']，共享资产=50，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=0。
- **资产证据范围**：`project_shared`；依据 {'group_size': 5, 'shared_assets': 50, 'custom_assets': 47, 'asset_families': ['custom', 'sentinel-1', 'sentinel-2']}。
- **资产样本**：COPERNICUS/S1_GRD, COPERNICUS/S2, COPERNICUS/S2_SR, users/chenyangcyhyy/AnalyticalHillshading, users/chenyangcyhyy/Aspect, users/chenyangcyhyy/ChannelNetworkBaseLevel, users/chenyangcyhyy/ChannelNetworkDistance, users/chenyangcyhyy/ClosedDepressions …
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00916 — A_merge_candidate / `same_assets_diff_title` / G1_exact_asset_set_group — split v-t

- **端点半族**：`F3a9f5165e6de27d5` (1 组件) ↔ `Fa5ad55d64d83cd29` (11525 组件)；族大小和 11526 （cap 10000，超限=True）。
- **截断组**：`Gf9df68e374f3aa0f`，组记录 {'n_components': 2, 'signature_group_size': 2, 'anchor': 69985, 'n_merged': 1, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 1/1。
- **端点 A**：component `69985`，family `F3a9f5165e6de27d5`，split `v`，script `script_284114`，task_type `Land use/land cover`。
  - 指令：Task: Identify land cover probability Compute land cover class probabilities (Cropland, Forest, Grassland, Others) for the year 2015 using a Random Forest classifier trained on labeled sample points. It adds SRTM-derived elevation and slope as features to a series of surface reflectance images, trains separate probability models for each class by iteratively redefining positive and negative classe
- **端点 B**：component `106924`，family `Fa5ad55d64d83cd29`，split `t`，script `script_284403`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types using a time series of surface reflectance images from 1998 to 2017, augmented with SRTM-derived elevation and slope data. It trains a Random Forest classifier in probability mode for four classes (Cropland, Forest, Grassland, Others) using labeled sample points from 'table2', generating per-pixel class probabilities. The output is a multi-
- **证据**：T=0.3333，B=0.4362，有效目标=['cover', 'land']，共享数据族=['custom', 'srtm', 'usgs']，共享资产=21，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`project_shared`；依据 {'group_size': 2, 'shared_assets': 21, 'custom_assets': 20, 'asset_families': ['custom', 'usgs']}。
- **资产样本**：USGS/SRTMGL1_003, users/547695554/LP_Data/LP_SRImage/LP_SRImage_1998, users/547695554/LP_Data/LP_SRImage/LP_SRImage_1999, users/547695554/LP_Data/LP_SRImage/LP_SRImage_2000, users/547695554/LP_Data/LP_SRImage/LP_SRImage_2001, users/547695554/LP_Data/LP_SRImage/LP_SRImage_2002, users/547695554/LP_Data/LP_SRImage/LP_SRImage_2003, users/547695554/LP_Data/LP_SRImage/LP_SRImage_2004 …
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00150 — A_merge_candidate / `mixed_or_weak` / G1_exact_asset_set_group — split s-t

- **端点半族**：`Ff10c5e3739bfc1d1` (2 组件) ↔ `Fa5ad55d64d83cd29` (11525 组件)；族大小和 11527 （cap 10000，超限=True）。
- **截断组**：`G601baca445d04231`，组记录 {'n_components': 3, 'signature_group_size': 3, 'anchor': 494, 'n_merged': 2, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 2/2。
- **端点 A**：component `494`，family `Ff10c5e3739bfc1d1`，split `s`，script `script_249519`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover in Bangladesh Classify land use and land cover (LULC) in Bangladesh using multi-source satellite data from 2015 to 2020. It generates a training dataset by combining MODIS, NLCD, CGLS, GAIA, Hansen forest change, and other ancillary datasets, then applies a Random Forest classifier on Sentinel-2, Sentinel-1, and WorldPop-derived features to produce a high-resolution LULC 
- **端点 B**：component `75726`，family `Fa5ad55d64d83cd29`，split `t`，script `script_249520`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types over a user-defined region using multi-source satellite data from 2015 to 2020. It generates a training dataset by combining Sentinel-2, Sentinel-1, MODIS, and auxiliary datasets (e.g., forest change, urban, population), applies a Random Forest classifier, and produces a classified land use/land cover (LULC) map per grid tile. The output in
- **证据**：T=0.6，B=0.4787，有效目标=['cover', 'land']，共享数据族=['jrc', 'landsat', 'modis', 'nasa', 'other', 'sentinel-1', 'sentinel-2', 'usgs']，共享资产=15，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`project_shared`；依据 {'group_size': 3, 'shared_assets': 15, 'custom_assets': 0, 'asset_families': ['jrc', 'landsat', 'modis', 'nasa', 'other', 'sentinel-1', 'sentinel-2', 'usgs']}。
- **资产样本**：COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019, COPERNICUS/S1_GRD, COPERNICUS/S2_SR, JAXA/ALOS/PALSAR/YEARLY/FNF, JRC/GSW1_2/GlobalSurfaceWater, LANDSAT/MANGROVE_FORESTS, MODIS/006/MCD12Q1, NASA/JPL/global_forest_canopy_height_2005 …
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00652 — A_merge_candidate / `mixed_or_weak` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F45aba8c6d9a4dab5` (31 组件)；族大小和 11556 （cap 10000，超限=True）。
- **截断组**：`Gc64b86fc179c607e`，组记录 {'n_components': 6, 'signature_group_size': 6, 'anchor': 58147, 'n_merged': 5, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 3/5。
- **端点 A**：component `58147`，family `Fa5ad55d64d83cd29`，split `t`，script `script_92508`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types using Landsat surface reflectance data from 1994, 2002, and 2007, trained on INEGI land use reference data for a specific Mexican state, applying topographic correction and cloud masking, and outputs a mode-reduced land cover classification map for 1994.
- **端点 B**：component `67135`，family `F45aba8c6d9a4dab5`，split `s`，script `script_92510`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using RF Classify land cover types (e.g., croplands, forest, urban, shrub/grass) for a specific Mexican state using Landsat surface reflectance data from 1994, applying Random Forest classification trained on stratified samples derived from INEGI land use maps across multiple years, with topographic and illumination corrections.
- **证据**：T=0.6，B=0.463，有效目标=['cover', 'land']，共享数据族=['custom', 'landsat', 'other', 'usgs']，共享资产=11，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`project_shared`；依据 {'group_size': 6, 'shared_assets': 11, 'custom_assets': 7, 'asset_families': ['custom', 'landsat', 'other', 'usgs']}。
- **资产样本**：LANDSAT/LE07/C01/T1_SR, LANDSAT/LT05/C01/T1_SR, USGS/SRTMGL1_003, ft:1jgYOOLXCqEOJuAtwDIp7AA-5B9BztyNDjvm-G6cy, users/dwmmclaughlin/01_inegi1_lu, users/dwmmclaughlin/01_inegi2_lu_2019_04_09, users/dwmmclaughlin/01_inegi3_lu_2019_04_09, users/dwmmclaughlin/01_inegi4_lu_2019_04_09 …
- **Agent 初步建议**：`MERGE_provisional` — 3 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00653 — A_merge_candidate / `mixed_or_weak` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F45aba8c6d9a4dab5` (31 组件)；族大小和 11556 （cap 10000，超限=True）。
- **截断组**：`Gc64b86fc179c607e`，组记录 {'n_components': 6, 'signature_group_size': 6, 'anchor': 58147, 'n_merged': 5, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 4/5。
- **端点 A**：component `58147`，family `Fa5ad55d64d83cd29`，split `t`，script `script_92508`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types using Landsat surface reflectance data from 1994, 2002, and 2007, trained on INEGI land use reference data for a specific Mexican state, applying topographic correction and cloud masking, and outputs a mode-reduced land cover classification map for 1994.
- **端点 B**：component `111899`，family `F45aba8c6d9a4dab5`，split `s`，script `script_92573`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using RF Classify land cover types using a Random Forest classifier trained on stratified samples from Landsat surface reflectance data, INEGI land use maps, and terrain variables (slope, aspect, month) for multiple years. The output includes classified land cover images and an error matrix for accuracy assessment.
- **证据**：T=0.6，B=0.3051，有效目标=['cover', 'land']，共享数据族=['custom', 'landsat', 'other', 'usgs']，共享资产=11，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`project_shared`；依据 {'group_size': 6, 'shared_assets': 11, 'custom_assets': 7, 'asset_families': ['custom', 'landsat', 'other', 'usgs']}。
- **资产样本**：LANDSAT/LE07/C01/T1_SR, LANDSAT/LT05/C01/T1_SR, USGS/SRTMGL1_003, ft:1jgYOOLXCqEOJuAtwDIp7AA-5B9BztyNDjvm-G6cy, users/dwmmclaughlin/01_inegi1_lu, users/dwmmclaughlin/01_inegi2_lu_2019_04_09, users/dwmmclaughlin/01_inegi3_lu_2019_04_09, users/dwmmclaughlin/01_inegi4_lu_2019_04_09 …
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00257 — A_merge_candidate / `mixed_or_weak` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `Ff08ce6bb0f09e7bc` (1 组件)；族大小和 11526 （cap 10000，超限=True）。
- **截断组**：`G59b73f3e9b120f31`，组记录 {'n_components': 30, 'signature_group_size': 30, 'anchor': 2533, 'n_merged': 29, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 16/29。
- **端点 A**：component `2533`，family `Fa5ad55d64d83cd29`，split `t`，script `script_177973`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types in the Upper East region of Ghana using Sentinel-2 surface reflectance imagery from April 2021. It computes multiple spectral indices (NDVI, MNDWI, GNDVI, NDMI, BSI, SAVI, EVI) and applies a Random Forest classifier trained on ground control points with 70% for training and 30% for validation. the workflow includes hyperparameter tuning for
- **端点 B**：component `12354`，family `Ff08ce6bb0f09e7bc`，split `s`，script `script_177994`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover in January Classify land use and land cover (LULC) for January 2021 in the Upper East region of Ghana using Sentinel-2 surface reflectance imagery. It applies cloud masking via QA60 and SCL bands, computes a median composite, and derives multiple spectral indices (NDVI, MNDWI, GNDVI, NDMI, BSI, SAVI, EVI). A CART classifier is trained on ground control points with ClassDo
- **证据**：T=0.6，B=0.4848，有效目标=['cover', 'land']，共享数据族=['custom', 'sentinel-2']，共享资产=9，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=0。
- **资产证据范围**：`project_shared`；依据 {'group_size': 30, 'shared_assets': 9, 'custom_assets': 8, 'asset_families': ['custom', 'sentinel-2']}。
- **资产样本**：COPERNICUS/S2_SR, users/kakpoti/Buffer200mS, users/kakpoti/BufferClip1, users/kakpoti/BufferClip2, users/kakpoti/BufferClip3, users/kakpoti/BufferIntersect1km250m, users/kakpoti/ClassDomain, users/kakpoti/NOV2019_20 …
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R00356 — A_merge_candidate / `mixed_or_weak` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F45aba8c6d9a4dab5` (31 组件)；族大小和 11556 （cap 10000，超限=True）。
- **截断组**：`G330afe34384a7e76`，组记录 {'n_components': 10, 'signature_group_size': 10, 'anchor': 7985, 'n_merged': 9, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 8/9。
- **端点 A**：component `7985`，family `Fa5ad55d64d83cd29`，split `t`，script `script_92569`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land use and land cover (LULC) types in a specific Mexican state using Landsat surface reflectance data from 1994, 2002, and 2007. It applies topographic correction (SCSc), masks clouds, trains a Random Forest classifier on stratified training samples derived from INEGI land use maps, and generates a mode-reduced classified land cover image for the year 199
- **端点 B**：component `111271`，family `F45aba8c6d9a4dab5`，split `s`，script `script_92504`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using RF Classify land cover types (e.g., croplands, forest, urban, shrub/grass) using a Random Forest classifier trained on Landsat surface reflectance data, SRTM-derived topography (slope and aspect), and month information. Training and testing points are derived from INEGI land use reference data for specific years (1994, 2002, 2007). The output is a classified land co
- **证据**：T=0.6，B=0.375，有效目标=['cover', 'land']，共享数据族=['custom', 'landsat', 'other', 'usgs']，共享资产=8，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=0。
- **资产证据范围**：`project_shared`；依据 {'group_size': 10, 'shared_assets': 8, 'custom_assets': 4, 'asset_families': ['custom', 'landsat', 'other', 'usgs']}。
- **资产样本**：LANDSAT/LE07/C01/T1_SR, LANDSAT/LT05/C01/T1_SR, USGS/SRTMGL1_003, ft:1jgYOOLXCqEOJuAtwDIp7AA-5B9BztyNDjvm-G6cy, users/dwmmclaughlin/01_inegi1_lu, users/dwmmclaughlin/01_inegi2_lu_2019_04_09, users/dwmmclaughlin/01_inegi3_lu_2019_04_09, users/dwmmclaughlin/01_inegi4_lu_2019_04_09
- **Agent 初步建议**：`MERGE_provisional` — 2 strong axes despite project-shared assets。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01348 — A_merge_candidate / `same_targets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F5fb95067f1fbbd5a` (6019 组件)；族大小和 17544 （cap 10000，超限=True）。
- **截断组**：`Gb67892a809d0413b`，组记录 {'n_components': 2, 'signature_group_size': 2, 'anchor': 103059, 'n_merged': 1, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 1/1。
- **端点 A**：component `103059`，family `Fa5ad55d64d83cd29`，split `t`，script `script_158515`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types the workflow performs Tasseled Cap transformation on a Landsat 8 surface reflectance image to derive brightness, greenness, and wetness components. It then creates a labeled feature collection of training points representing six land cover classes (Urban, Agriculture, Rangeland, Forest, Water, Barren) with spatial buffers around sample points. These points are joine
- **端点 B**：component `115574`，family `F5fb95067f1fbbd5a`，split `s`，script `script_158517`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using Tasseled Cap transformation the workflow performs a Tasseled Cap transformation on a Landsat 8 surface reflectance image to derive brightness, greenness, wetness, and additional orthogonal components. It creates a labeled feature collection of training samples representing six land cover classes (Urban, Agriculture, Rangeland, Forest, Water, Barren) with spatial buf
- **证据**：T=0.4286，B=0.6304，有效目标=['cover', 'land']，共享数据族=['landsat']，共享资产=2，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=2。
- **资产证据范围**：`task_specific`；依据 {'group_size': 2, 'shared_assets': 2, 'custom_assets': 0, 'asset_families': ['landsat']}。
- **资产样本**：LANDSAT/LC08/C02/T1_L2, LANDSAT/LC08/C02/T1_L2/LC08_046032_20150215
- **Agent 初步建议**：`MERGE_provisional` — 4 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01143 — A_merge_candidate / `same_targets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F130efdb2767d24aa` (2 组件)；族大小和 11527 （cap 10000，超限=True）。
- **截断组**：`G9a3de8eb849b432f`，组记录 {'n_components': 21, 'signature_group_size': 21, 'anchor': 2789, 'n_merged': 14, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 12/14。
- **端点 A**：component `2789`，family `Fa5ad55d64d83cd29`，split `t`，script `script_202294`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover in a basin using Landsat 5 surface reflectance data from June to September 2006. It computes spectral indices (NDVI, NDBI, MNDWI, BSI) and integrates ALOS elevation data to form a composite. After normalization, a Random Forest classifier is trained on labeled ground control points to produce a land cover map. Post-classification refinement adjus
- **端点 B**：component `94032`，family `F130efdb2767d24aa`，split `s`，script `script_8072`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover with spectral indices Classify land cover types using Landsat 5 surface reflectance data, spectral indices (NDVI, NDBI, MNDWI, BSI), ALOS elevation data, and a random forest classifier. It further refines the classification by reassigning certain classes based on threshold conditions involving BSI and NDVI, then exports the resulting classified image for 2011.
- **证据**：T=0.5，B=0.3902，有效目标=['cover', 'land']，共享数据族=['landsat', 'other']，共享资产=2，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`unclear`；依据 {'group_size': 21, 'shared_assets': 2, 'custom_assets': 0, 'asset_families': ['landsat', 'other']}。
- **资产样本**：JAXA/ALOS/AW3D30/V2_2, LANDSAT/LT05/C01/T1_SR
- **Agent 初步建议**：`MERGE_provisional` — 3 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01290 — A_merge_candidate / `same_targets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F120b8726311e3eac` (3 组件)；族大小和 11528 （cap 10000，超限=True）。
- **截断组**：`Ge00f065bad59dbd8`，组记录 {'n_components': 3, 'signature_group_size': 3, 'anchor': 20813, 'n_merged': 1, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 1/1。
- **端点 A**：component `20813`，family `Fa5ad55d64d83cd29`，split `t`，script `script_255642`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types in Inner Mongolia using Sentinel-2 imagery from May to June 2020. It uses a Random Forest classifier trained on user-defined samples (water, trees, grass, etc.) and applies it to median-composited Sentinel-2 bands (Blue, Green, Red, NIR, SWIR1, SWIR2). The output is a classified raster map visualized with ESRI-style land cover colors and in
- **端点 B**：component `117825`，family `F120b8726311e3eac`，split `s`，script `script_255641`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover in Inner Mongolia Classify land cover types in Inner Mongolia using a Random Forest classifier applied to median-composited Landsat 4, 5, and 8 surface reflectance imagery from 2021. Training samples are merged from multiple land cover classes (water, trees, flooded vegetation, crops, built area, bare ground, rangeland, others, clouds), and the classification is performed
- **证据**：T=0.5，B=0.3551，有效目标=['cover', 'land']，共享数据族=['custom']，共享资产=2，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`unclear`；依据 {'group_size': 3, 'shared_assets': 2, 'custom_assets': 2, 'asset_families': ['custom']}。
- **资产样本**：projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m, users/zhangby/ChinaAdminProvince
- **Agent 初步建议**：`MERGE_provisional` — 3 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01340 — A_merge_candidate / `same_targets_diff_title` / G1_exact_asset_set_group — split v-t

- **端点半族**：`Faca5fe24b8c7e2e8` (4 组件) ↔ `Fa5ad55d64d83cd29` (11525 组件)；族大小和 11529 （cap 10000，超限=True）。
- **截断组**：`G7df9adb0e0591ab0`，组记录 {'n_components': 2, 'signature_group_size': 2, 'anchor': 83390, 'n_merged': 1, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 1/1。
- **端点 A**：component `83390`，family `Faca5fe24b8c7e2e8`，split `v`，script `script_158440`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using Sentinel-2 and elevation data Classify land cover in a user-defined region using Sentinel-2 surface reflectance imagery from May to September 2020, combined with SRTM elevation and derived terrain metrics (slope), spectral indices (NDVI, EVI, SAVI, NDBI, NDWI), and GLCM texture features from band B8. A Random Forest classifier is trained on labeled sample points fro
- **端点 B**：component `113146`，family `Fa5ad55d64d83cd29`，split `t`，script `script_158437`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types in a specific region using Sentinel-2 surface reflectance data, terrain variables (elevation and slope), and spectral indices (NDVI, EVI, SAVI, NDBI, NDWI) along with GLCM texture features from band B8. It applies a Random Forest classifier trained on field sample points, evaluates accuracy using confusion matrices, and exports the resultin
- **证据**：T=0.375，B=0.4643，有效目标=['cover', 'land']，共享数据族=['custom', 'sentinel-2']，共享资产=2，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`unclear`；依据 {'group_size': 2, 'shared_assets': 2, 'custom_assets': 1, 'asset_families': ['custom', 'sentinel-2']}。
- **资产样本**：COPERNICUS/S2_SR, users/jakubowskifjsd43/1117_5
- **Agent 初步建议**：`MERGE_provisional` — 3 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01275 — A_merge_candidate / `same_targets_diff_title` / G1_exact_asset_set_group — split t-s

- **端点半族**：`Fa5ad55d64d83cd29` (11525 组件) ↔ `F56359038461d499c` (1 组件)；族大小和 11526 （cap 10000，超限=True）。
- **截断组**：`Ga728e691362bbda8`，组记录 {'n_components': 9, 'signature_group_size': 10, 'anchor': 16813, 'n_merged': 8, 'decision': 'merge', 'purpose_class': 'detect'}；该边在组内强度排名 7/8。
- **端点 A**：component `16813`，family `Fa5ad55d64d83cd29`，split `t`，script `script_115881`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover types Classify land cover types using a Random Forest classifier trained on multi-temporal Sentinel-2 optical imagery and ALOS PALSAR SAR data, with NDVI as a spectral index. The output is a classified land cover map masked to a specific area, visualized with a custom color palette.
- **端点 B**：component `122147`，family `F56359038461d499c`，split `s`，script `script_85762`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using SAR and multispectral data Classify land cover types using a combination of ALOS PALSAR SAR data and multiple Sentinel-2 image composites. It computes NDVI from Sentinel-2 bands, creates temporal mosaics based on NDVI quality, stacks them with SAR data, and trains Random Forest and SVM classifiers using labeled training samples (campo) to produce classified land cov
- **证据**：T=0.4286，B=0.3421，有效目标=['cover', 'land']，共享数据族=['other', 'sentinel-2']，共享资产=2，链相同=True，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`unclear`；依据 {'group_size': 10, 'shared_assets': 2, 'custom_assets': 0, 'asset_families': ['other', 'sentinel-2']}。
- **资产样本**：COPERNICUS/S2, JAXA/ALOS/PALSAR/YEARLY/SAR
- **Agent 初步建议**：`MERGE_provisional` — 3 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R04697 — C_undetermined / `same_title_diff_source` / D2_star_group — split t-v

- **端点半族**：`F925c318fd4d0208a` (10312 组件) ↔ `F1e4e357a44cff9c7` (2 组件)；族大小和 10314 （cap 10000，超限=True）。
- **截断组**：`Sfd79630fb61db7ed`，组记录 {'bucket_size': 501, 'anchor': 7772, 'decision': 'merge', 'purpose_class': 'detect', 'bucket': ['built', 'up']}；该边在组内强度排名 193/356。
- **端点 A**：component `7772`，family `F925c318fd4d0208a`，split `t`，script `script_228160`，task_type `Human settlements`。
  - 指令：Task: Identify built-up areas Identify built-up and non-built-up areas in Sri Lanka using Sentinel-2 surface reflectance imagery from January to August 2021. It performs cloud masking by joining S2_CLOUD_PROBABILITY, computes a median composite, and creates a mosaic based on minimum spectral distance to the median. Training samples for built-up (id=1) and non-built-up (id=2) are balanced and split
- **端点 B**：component `112868`，family `F1e4e357a44cff9c7`，split `v`，script `script_272408`，task_type `Land use/land cover`。
  - 指令：Task: Identify built-up areas using BU index Compute a Built-Up (BU) index for the year 1992 using Landsat 5 Surface Reflectance data. It first generates a median image from cloud-filtered imagery, then calculates NDVI and NDBI using specific band ratios. Binary masks based on NDVI are created to isolate vegetated areas, which are then used to derive binary versions of NDBI and NDVI. The BU index 
- **证据**：T=0.6667，B=0.2087，有效目标=['built', 'up']，共享数据族=[]，共享资产=0，链相同=False，目的=detect/detect，任务类型相同=False，共享输出=0。
- **资产证据范围**：`unclear`；依据 {'shared_assets': 0}。
- **资产样本**：
- **Agent 初步建议**：`MERGE_provisional` — 2 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R04691 — C_undetermined / `same_title_diff_source` / D2_star_group — split t-v

- **端点半族**：`F925c318fd4d0208a` (10312 组件) ↔ `F3319a746907cde74` (1 组件)；族大小和 10313 （cap 10000，超限=True）。
- **截断组**：`Sfd79630fb61db7ed`，组记录 {'bucket_size': 501, 'anchor': 7772, 'decision': 'merge', 'purpose_class': 'detect', 'bucket': ['built', 'up']}；该边在组内强度排名 194/356。
- **端点 A**：component `7772`，family `F925c318fd4d0208a`，split `t`，script `script_228160`，task_type `Human settlements`。
  - 指令：Task: Identify built-up areas Identify built-up and non-built-up areas in Sri Lanka using Sentinel-2 surface reflectance imagery from January to August 2021. It performs cloud masking by joining S2_CLOUD_PROBABILITY, computes a median composite, and creates a mosaic based on minimum spectral distance to the median. Training samples for built-up (id=1) and non-built-up (id=2) are balanced and split
- **端点 B**：component `55012`，family `F3319a746907cde74`，split `v`，script `script_240882`，task_type `Land use/land cover`。
  - 指令：Task: Identify non-forest built-up areas Identify built-up areas within non-forest and non-water regions using Landsat 8 surface reflectance imagery from October to December 2020. It applies cloud and shadow masking, clips to a study area, and masks out forested areas (using an external forest mask 'fmask') and permanent water bodies (from JRC Global Surface Water dataset). The final output is a m
- **证据**：T=0.6667，B=0.2035，有效目标=['built', 'up']，共享数据族=[]，共享资产=0，链相同=False，目的=detect/detect，任务类型相同=False，共享输出=1。
- **资产证据范围**：`unclear`；依据 {'shared_assets': 0}。
- **资产样本**：
- **Agent 初步建议**：`MERGE_provisional` — 2 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01374 — A_merge_candidate / `same_title_diff_source` / D2_star_group — split t-s

- **端点半族**：`F925c318fd4d0208a` (10312 组件) ↔ `F5fb95067f1fbbd5a` (6019 组件)；族大小和 16331 （cap 10000，超限=True）。
- **截断组**：`Sfd79630fb61db7ed`，组记录 {'bucket_size': 501, 'anchor': 7772, 'decision': 'merge', 'purpose_class': 'detect', 'bucket': ['built', 'up']}；该边在组内强度排名 199/356。
- **端点 A**：component `7772`，family `F925c318fd4d0208a`，split `t`，script `script_228160`，task_type `Human settlements`。
  - 指令：Task: Identify built-up areas Identify built-up and non-built-up areas in Sri Lanka using Sentinel-2 surface reflectance imagery from January to August 2021. It performs cloud masking by joining S2_CLOUD_PROBABILITY, computes a median composite, and creates a mosaic based on minimum spectral distance to the median. Training samples for built-up (id=1) and non-built-up (id=2) are balanced and split
- **端点 B**：component `17621`，family `F5fb95067f1fbbd5a`，split `s`，script `script_86380`，task_type `Human settlements`。
  - 指令：Task: Identify built-up areas with nighttime lights Identify built-up areas by combining multitemporal built-up surface data from the JRC GHSL dataset with median nighttime light intensity from VIIRS DNB monthly composites in 2014. It applies a threshold on median radiance (gt(2)) and masks it with built-up areas greater than 2 to refine human settlement detection, producing binary layers before a
- **证据**：T=0.6667，B=0.1827，有效目标=['built', 'up']，共享数据族=[]，共享资产=0，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=1。
- **资产证据范围**：`unclear`；依据 {'shared_assets': 0}。
- **资产样本**：
- **Agent 初步建议**：`MERGE_provisional` — 2 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R01372 — A_merge_candidate / `same_title_diff_source` / D2_star_group — split t-s

- **端点半族**：`F925c318fd4d0208a` (10312 组件) ↔ `F5fb95067f1fbbd5a` (6019 组件)；族大小和 16331 （cap 10000，超限=True）。
- **截断组**：`Sba49287fdf0f54b4`，组记录 {'bucket_size': 153, 'anchor': 3146, 'decision': 'merge', 'purpose_class': 'detect', 'bucket': ['affected', 'fire']}；该边在组内强度排名 28/120。
- **端点 A**：component `3146`，family `F925c318fd4d0208a`，split `t`，script `script_66872`，task_type `Natural hazards`。
  - 指令：Task: Identify fire affected areas Analyze wildfire boundaries within a specific region (small_poly_mnts) by filtering a feature collection of fires from 2003 onward, computing the union of all fires, and comparing spatial differences between the study area and both individual (Santiago) and combined fire perimeters. It visualizes the remaining non-burned areas after subtracting fire extents.
- **端点 B**：component `126317`，family `F5fb95067f1fbbd5a`，split `s`，script `script_162795`，task_type `Natural hazards`。
  - 指令：Task: Identify fire-affected areas using dXBR and dNBR Identify fire-affected areas by computing the difference in XBR (eXist Burn Ratio) and dNBR (differenced Normalized Burn Ratio) from Sentinel-2 imagery before and after a fire event. It uses cloud-masked images to calculate pre- and post-fire spectral indices, applies thresholds to detect burn anomalies (dXBR > 0.15 and dNBR > 0.10), counts an
- **证据**：T=0.6667，B=0.1683，有效目标=['affected', 'fire']，共享数据族=[]，共享资产=0，链相同=False，目的=detect/detect，任务类型相同=True，共享输出=0。
- **资产证据范围**：`unclear`；依据 {'shared_assets': 0}。
- **资产样本**：
- **Agent 初步建议**：`MERGE_provisional` — 2 independent axes (target/source/chain/text)。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R05668 — C_undetermined / `task_type_diff` / D2_star_group — split t-s

- **端点半族**：`F925c318fd4d0208a` (10312 组件) ↔ `Fd3847540ade9533b` (1 组件)；族大小和 10313 （cap 10000，超限=True）。
- **截断组**：`Sf6b531621399112e`，组记录 {'bucket_size': 167, 'anchor': 7480, 'decision': 'merge', 'purpose_class': 'detect', 'bucket': ['featur', 'terrain']}；该边在组内强度排名 67/143。
- **端点 A**：component `7480`，family `F925c318fd4d0208a`，split `t`，script `script_129418`，task_type `Land use/land cover`。
  - 指令：Task: Classify land cover using Sentinel-2 and terrain features Classify land cover types in a region of southern Africa (EPSG:32734) using a time series of Sentinel-2 surface reflectance data combined with SRTM-derived terrain variables (elevation, slope, aspect, CHILI, TPI) and angular-based synthetic bands generated via the OGC function. Classification is performed using a spatial k-fold cross-
- **端点 B**：component `115102`，family `Fd3847540ade9533b`，split `s`，script `script_35848`，task_type `Land surface/agriculture indicators`。
  - 指令：Task: Extract terrain-corrected SAR and optical features for agricultural plots the workflow performs terrain flattening on Sentinel-1 GRD data using a volume scattering model and SRTM elevation data, computes a VV-VH ratio, and combines it with cloud-masked Sentinel-2 SR data. It then extracts stratified samples from user-defined plot buffers, combining SAR and optical bands into a unified featur
- **证据**：T=0.1538，B=0.1343，有效目标=['terrain']，共享数据族=['sentinel-2', 'srtm', 'usgs']，共享资产=1，链相同=False，目的=detect/detect，任务类型相同=False，共享输出=1。
- **资产证据范围**：`task_specific`；依据 {'shared_assets': 1, 'custom_assets': 0, 'asset_families': ['usgs']}。
- **资产样本**：USGS/SRTMGL1_003
- **Agent 初步建议**：`UNRESOLVED` — task_type differs and text evidence is weak。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

### R05660 — C_undetermined / `task_type_diff` / D2_star_group — split s-t

- **端点半族**：`F5fb95067f1fbbd5a` (6019 组件) ↔ `F925c318fd4d0208a` (10312 组件)；族大小和 16331 （cap 10000，超限=True）。
- **截断组**：`S23b2cc43a6c778d6`，组记录 {'bucket_size': 269, 'anchor': 5295, 'decision': 'merge', 'purpose_class': 'detect', 'bucket': ['1', 'vv']}；该边在组内强度排名 110/134。
- **端点 A**：component `5295`，family `F5fb95067f1fbbd5a`，split `s`，script `script_98645`，task_type `Land surface/agriculture indicators`。
  - 指令：Task: Extract Sentinel-1 VV backscatter the workflow retrieves the first available Sentinel-1 GRD image with VV polarization for each month within the date range from May 2015 to December 2017 at a specific point location, forming a monthly time series of SAR backscatter observations.
- **端点 B**：component `120050`，family `F925c318fd4d0208a`，split `t`，script `script_174658`，task_type `Land use/land cover`。
  - 指令：Task: Detect land cover changes using Sentinel-1 VV Analyze temporal changes in backscatter from Sentinel-1 GRD data using VV polarization to detect land surface changes between two periods (2021-07–2021-12 and 2022-01–2022-07). It separates ascending and descending orbits, computes mean composites for each period, calculates a ratio-based change metric, applies focal smoothing, and derives a bina
- **证据**：T=0.3333，B=0.1759，有效目标=[]，共享数据族=['sentinel-1']，共享资产=1，链相同=False，目的=detect/detect，任务类型相同=False，共享输出=0。
- **资产证据范围**：`task_specific`；依据 {'shared_assets': 1, 'custom_assets': 0, 'asset_families': ['sentinel-1']}。
- **资产样本**：COPERNICUS/S1_GRD
- **Agent 初步建议**：`UNRESOLVED` — task_type differs and text evidence is weak。
  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。
- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED
  - counter_evidence：____________________
  - evidence_needed：____________________

## 4. 试审核对清单（逐条回答）

1. 相同资产集合是否被误当成同任务证据？（看资产是任务特异还是项目共享）
2. 截断是否破坏了关系证据？（组记录、端点、原始规则、族大小是否可复现）
3. 同标题异来源究竟需要哪些附加证据才算同任务族？
4. 地区/年份/输入条件不同，是否仍属于需要同侧隔离的同一任务族？
5. KEEP_SEPARATE 是否有明确、可复查的反证（目的/对象/输出/来源冲突）？

## 5. 协议草案 v0（试审后按 owner 反馈锁定，不现在生效）

1. **MERGE**：至少 2 个独立证据轴，取自 {有效目标 ≥2、链相同、标题 J≥0.60、正文 J≥0.60、任务特异资产重叠}；**项目共享资产重叠不能单独作为一轴**。
2. **KEEP_SEPARATE**：必须有明确反证（对象/目的/输出/来源冲突），并写入 `counter_evidence`；不能仅因“标题不同”或“没时间看”而 KEEP。
3. **UNRESOLVED**：证据不足或冲突；跨 split 的 UNRESOLVED 不得以正式评估状态进入冻结，需隔离或保守同 split 处置。
4. **条件差异**（地区/年份/输入组合不同）：暂不作为自动合并或自动分离依据；需 owner 先给统一口径。
5. **资产范围**：`project_shared` 至少需要 2 个强文本/链轴；`task_specific` 资产可计 1 轴；`unclear` 不计资产轴。
6. 每条裁定记录 `review_id / decision / evidence / counter_evidence / adjudicator / date`，可机器回写。

## 6. 本批不做什么

- 不合并任何族，不改变 V3 split，不重算配额，不恢复 S1；
- `MERGE` 只是试审记录，正式合并须在协议锁定并完成全量裁定后进入 V3.1；
- `UNRESOLVED` 必须保留在风险台账，不得静默转为 KEEP。
