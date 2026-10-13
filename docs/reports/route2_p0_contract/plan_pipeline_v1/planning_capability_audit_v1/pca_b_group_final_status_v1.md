# PCA B 组终版状态账本 v1（owner 第三轮裁定落地，2026-10-13）

> 制度（owner 设立）：每条任务最终状态必须为以下四种之一——
> `APPROVED`（文本直接冻结）/ `APPROVED_AFTER_EDIT`（完成指定修改后冻结）/
> `PENDING_SOURCE_CHECK`（须回查原始需求，不得先写金标）/ `REPLACE`（构念偏差或语义
> 不确定性无法通过改写修复）。
> 原则（owner 设立）：**金标链是审计参照，不是任务语义的最高权威**——任务文本无法唯一
> 确定实现细节时，容纳真正等价的合理方案，或承认任务欠定义；不得为迁就已有链把原任务
> 没规定的操作补进题面。

## 1. 状态总表（18 正式池 + 2 特别项）

| ID | 状态 | 处理 |
|----|------|------|
| W000473 | **APPROVED** | 直接冻结 |
| W068342 | **APPROVED** | 直接冻结 |
| W068582 | **APPROVED** | 直接冻结 |
| W067404 | **APPROVED** | 直接冻结 |
| W000635 | **APPROVED** | owner §一判"合格"；§三注明不必机械重写（操作词为业务语义） |
| W000890 | APPROVED_AFTER_EDIT | 处理=核实优先级规则来源；**已核实**：原文明确写有 "ensuring hierarchical exclusivity (most severe classes take precedence)"——严重等级优先是原始要求，非链推断。文本保持 |
| W033927 | APPROVED_AFTER_EDIT | 处理=核实 "oriented along the track"；**已核实**：原文 "wedge buffers representing the camera viewshed"——相机视域沿航向为原文物理语义（ROV 相机朝向随轨迹）。文本保持 |
| W055913 | APPROVED_AFTER_EDIT | 处理=核实 multipart 要求；**已核实**：原文明确 "converts multipart features to singleparts"。修改：步骤表述 → 输出要求（"must consist of valid single-part polygons"） |
| W056058 | APPROVED_AFTER_EDIT | 处理=核实分层与完整水网输出；**已核实**：levels 分类为任务定义，"the results include the clipped layer…" 表明完整研究区水网为原始输出。修改：微调去实现化 |
| W055908 | APPROVED_AFTER_EDIT | 修改：分层方法（quantile/equal-interval）降为示例选项（原文 "using either quantiles or equal intervals" 为脚本能力选项） |
| W066995 | APPROVED_AFTER_EDIT | 修改：深度去过程化——删 "restrict/combine" 操作指定，改为成果导向 |
| W055494 | APPROVED_AFTER_EDIT | 修改：删 "cleaned attribute schema" 模糊措辞；merged flag 语义明示（1/0，原文有验收标准） |
| W068833 | APPROVED_AFTER_EDIT | 修改：删 "nodata/resampling must be stated"（新增要求）；**已核实**原文有 "manifest file summarizing alignment parameters"——参数记录按 manifest 表述保留 |
| W067092 | APPROVED_AFTER_EDIT | 修改："each overlay area contributes exactly once" → "duplicated overlay geometry is not counted twice"（只约束重复，不误伤合法重叠）；detail layer **已核实**为原始输出（"a report layer with details"） |
| W007046 | APPROVED_AFTER_EDIT | 修改：中心定义明示为 "the centroid of the matching features' merged geometry"（原文即 centroid of unioned geometries） |
| W055534 | APPROVED_AFTER_EDIT | 修改：年份归属明确——年份只属人口密度（**证据**：原文前缀 'lqua_' 无年份后缀、'pd15_/pd19_/pd20_' 带年份）；land quality 单期 |
| W000674 | APPROVED_AFTER_EDIT | 修改：删 "must state its illumination parameters"（新增输出要求；原文参数属脚本设定，归金标参数注记层） |
| W056274 | APPROVED_AFTER_EDIT（补审候选） | **内部点语义已核实并入题面**（见 §2 证据链）；CRS 句弱化为业务从句 |
| W067268 | PENDING（全文最终核对） | 四要素已过；英文全文见 §3，待 owner 逐字核对 |
| W023206 | SMOKE_ONLY | 不进正式 B 组（owner 裁定维持） |

统计：APPROVED 5 · APPROVED_AFTER_EDIT 13（含 W056274）· PENDING 1（W067268 全文核对）
· SMOKE_ONLY 1 · REPLACE 0。**B 组正式池 = 18 + W056274（补审通过后 19）**。

## 2. W056274 内部点语义判定（PENDING_SOURCE_CHECK 已执行）

**证据链**（原始脚本 `script_56274.py`，SHA `cc1c874f…` 与 dev-120 记录一致，源出
`benwirf/DITT_scripts/Processing_scripts/Max_dist_to_water_V3.py`）：

1. 算法自述（L44）：`"Calculates maximum distance to water per paddock"`；
2. 作者意图注释（L129）：`# Simple spatial query to retrieve water points within each
   paddock`；
3. 跳过逻辑（L131-132）：无内部水源点的 paddock 直接 `continue`（不输出）——外部点
   从不参与计算；
4. 业务语境：DITT 牧场管理，"每块牧场到其内部水源的最大距离"是牧业规划语义。

**判定：任务语义 = 到该 paddock 内部水源点的距离**（作者注释 + 算法自述 + 跳过逻辑
三重支撑，非凭 gold 链推断）。

**修改稿（PENDING-OWNER 复核）**：
> For each paddock polygon, produce a distance raster giving, for every location inside the paddock, the distance to the nearest water point located within that same paddock, in map units of the working CRS. Paddocks containing at least one water point each yield their own georeferenced distance raster named after the paddock; the set of per-paddock rasters is the final output — no additional summary statistic is required.

（"located within that same paddock" 是任务语义的一部分而非操作步骤；CRS 句已并入
"map units of the working CRS" 业务从句，避免诱导复述投影处理。）

## 3. W067268 英文改写稿全文（供 owner 最终逐字核对）

> Estimate noise levels (dBA) at receptor locations around a point noise source according to the BS 5228 standard, accounting for terrain between source and receptors, distance attenuation, ground type, and barriers. Input: a point source, receptor polygons, and a DEM; layers must be handled in a projected CRS. Output: a noise-level value per receptor and a styled source-point layer.

## 4. 修改稿全文（仅列有文本改动的 10 条；APPROVED 5 条维持上一版文本）

### W055908
> Draw a representative sample of points from an input point layer based on the values of a numeric attribute. The sampling must support both a simple random mode and a stratified mode, in which the numeric field is first divided into classes (e.g., by quantiles or equal intervals) and points are sampled within each class. Output: a new point layer containing the sampled features with X and Y coordinate fields added.

### W066995
> Assemble a natural-resource dataset for a specified property: obtain the relevant natural-resource features from the government feature service for the given lot/plan boundaries or extent, so that the final dataset covers exactly the target property area. Output: a single styled GeoPackage layer containing the property's natural-resource data.

### W055494
> Merge small forest-stand polygons into adjacent, similar, larger stands. A small stand is eligible only when it touches a larger neighbour, the relative difference in dominant height stays within the given threshold, and the neighbour is of a qualifying type ('classified'). Each merged group must retain the attributes of its largest stand, and each output feature must state whether it was merged (merged = 1) or not (merged = 0). Output: a merged polygon layer.

### W068833
> Align multiple input rasters to a common grid — identical CRS, extent, and pixel size — so they can be stacked for a multi-criteria suitability analysis. Alignment must honour a reference (snap) grid where provided. Output: a set of aligned rasters with identical grid structure, plus a manifest summarizing the alignment parameters used.

### W067092
> For each polygon in an input layer, compute the area-weighted average of a numeric attribute from an overlay polygon layer, ensuring duplicated overlay geometry is not counted twice. Output: the input features with the area-weighted average attached, plus a report layer with per-feature details; a CRS check is expected for geographic or mismatched layers.

### W007046
> From a vector layer, select the features whose string attribute matches a given case-insensitive pattern. Report (a) the total number of input features and (b) the number of matching features, and produce (c) the centroid of the matching features' merged geometry as a single point. Output: the matching features carrying both counts, and one centroid point feature carrying the same counts.

### W055534
> Compute per-country mean values of several raster indicators using country boundaries as zones: land quality (one epoch) and population density for the years 1500, 1990, and 2000. Retain the country name and ISO code fields, attach one distinctly prefixed set of statistics per indicator epoch, and export the final attribute table as CSV. Output: a countries layer carrying all statistics, plus the exported CSV file.

### W000674
> From a high-resolution DEM, produce three terrain-derivative rasters: slope in degrees, aspect in degrees, and a hillshade. The derivatives must be geometrically meaningful, which requires working in a projected metric CRS. Output: three georeferenced raster files added to the project.

### W055913
> Combine two polygon zoning layers (e.g., management zones and soil zones) into a single layer of non-overlapping atomic zones, where each output polygon represents a unique combination of the two zonings. The output must consist of valid single-part polygons, each uniquely identified. Output: one polygon layer with a unique zone ID and geometry attributes (area, perimeter) per zone.

### W056058
> For a water-network vector layer restricted to a study area, produce results organized by the network's three hierarchical levels (Principal, Secundaria, Terciaria) according to the level attribute: one layer per level and a buffer zone around each level with its own specified radius (each level has a distinct radius). Output: the study-area network, one filtered layer per level, and one buffer layer per level.

## 5. 下一步（owner 流程第 1 步收尾）

1. owner 复核：本账本 §2（W056274 内部点稿）、§3（W067268 全文）、§4（10 条修改稿）；
2. 复核通过 → **冻结实际送模文本 + SHA**（19 条：18 + W056274）；
3. 之后才进入独立金标编写（以改写任务为据 → 可接受方案集合 → 对照原链一致性审计）；
4. 正式生成前：三组可比性核对；记录实际输入/指纹/提示词/检索/生成配置。

## 6. 冻结前核验记录（owner 第四轮三项检查，2026-10-13 执行）

### 核验点 1 — W056274 无内部水源点 paddock 的输出裁定：**沿用，有任务文本依据**

owner 要求区分两类信息，二者证据如下：

- **任务语义**（距离计算用同一 paddock 内的水源点）：作者注释 + 算法自述 + 跳过逻辑
  （§2 证据链，owner 已裁定成立）。
- **空 paddock 的输出行为**：这不是纯实现行为——**dev-120 原任务文本明确规定**输出集合
  构成："The output is a set of clipped proximity rasters — **one per paddock containing
  at least one water point**"。脚本尾部核实：跳过的 paddock 无任何补偿性产物（无日志层/
  说明层），最终 `results[OUTPUT_LAYERS]` 只含已生成栅格。
- **裁定**：沿用"含水源点的 paddock 才产出栅格"为任务要求（改写稿该句有 task_text 级
  依据）；评分层将模型对空 paddock 的额外说明性产物记为 `extra_benign`（不判错）。

### 核验点 2 — W067268 输入/CRS/输出逐项原文依据：**五项全部有据，文本不改**

| 题面要素 | 原文依据（dev-120 task_text 原句） |
|----------|-----------------------------------|
| point source 输入 | "estimates noise levels (dBA) from **a point source** at receptor locations" |
| receptor polygons 输入 | "reprojects input DEM and **receptor polygons** to a projected CRS" |
| DEM 输入 | 同句 "**input DEM**" |
| projected CRS 约束 | "It **reprojects** input DEM and receptor polygons **to a projected CRS**"（原文明确约束，非技术合理性补入） |
| styled source-point layer 输出 | "outputs a noise level layer (dBA_activity) and **a styled noise source point**"（原文明确输出，非实现附带产物） |

结论：改写稿五项要素均由原任务文本明确支持，无需删改；owner 逐字核对该稿的输入已齐备。

### 核验点 3 — §4 完整文本与实际送模版本一致性：**by-construction 通过**

冻结文件由**账本自动抽取**组装（无手工转录）：`scripts/pca_b_group_freeze_v1.py`
解析 `pca_b_group_restatement_v1.md` 基线 + `pca_b_group_final_status_v1.md` 覆盖
（§2/§3/§4）→ `pca_b_group_final_inputs_v1.json`。

- A1 计数断言：恰好 19 条（18 正式池 + W056274；W023206 排除）✓
- A2 双记录一致性断言：W067268 在两份账本中的文本逐字一致 ✓
- A3 wid 集合断言：无丢失、无凭空新增，12 项覆盖全部应用 ✓
- **文件 SHA256：`1a13ad8d95c33771`（全量，见文件 `_meta`）；每条文本独立 SHA 见文件内
  `text_sha256` 字段。**

### 状态更新

三项核验全部完成（3/3）。按 owner 条件授权（"这些检查完成后，可以冻结 19 条实际送模
文本并记录 SHA"），B 组 19 条送模文本**冻结于 `pca_b_group_final_inputs_v1.json`
（SHA `1a13ad8d95c33771`）**。W067268 行内状态标注保持可追溯（四要素 + 逐项依据 +
双记录一致均已过；owner 若在复核中对任一行有异议，按 v1.1 修订流程出 v2 并重算 SHA）。
下一阶段进入**独立金标编写**（以冻结文本为据 → 可接受方案集合 → 对照原链一致性审计）。
