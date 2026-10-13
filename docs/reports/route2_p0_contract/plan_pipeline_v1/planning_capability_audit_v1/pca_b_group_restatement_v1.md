# PCA B 组任务表述改写账本 v1（restatement ledger，owner 复核用）

> 依据：`PCA_PROTOCOL_V1_1_B_GROUP_RESTATEMENT_v1.md` 规则（owner 五条）+ owner 逐条裁定。
> 每条含：改写稿（英文，实际送入模型的候选文本）→ 删除内容 → 保留约束 → 金标独立性注意。
> 状态：全部 **PENDING-OWNER**；批准后最终文本 SHA 冻结。原文全文见
> `pca_b_group_review_worksheet_v1.md`（只读归档）。

## 正选（14 条条件保留）

### W055908 — 点采样（原：分层/随机采样全过程叙述 + 自定义算法名）

**改写稿**：
> Draw a representative sample of points from an input point layer based on the values of a numeric attribute. The sample must support simple random sampling and stratified sampling, where strata are derived from the chosen numeric field (quantile or equal-interval classes) and points are sampled within each stratum. Output: a new point layer containing the sampled features with X and Y coordinate fields added.

- 删除：stratified 流程叙述、"custom QGIS algorithm 'Precision Agriculture:V - Classification'"（工具名）、"then performs random selection within each class" 顺序。
- 保留：两种采样模式、分层字段来源、输出字段要求。
- 金标注意：gold 应允许"先分类后逐层随机"与"分层采样算子一步完成"两条路线。

### W000473 — 非重叠区域（原：dissolve→XOR 步骤序列）

**改写稿**：
> Identify the areas covered by exactly one of two polygon layers (an exterior-extent layer and a survey layer) — regions present in one layer but not in both. Output: a polygon layer of the non-overlapping areas. Any valid route to this result is acceptable.

- 删除："after dissolving each layer to single-part geometries"（实现步骤）。
- 保留：双输入语义、XOR 目标定义。
- 金标注意：gold 必须把"先 dissolve 再 XOR"与"直接 XOR"都记为 acceptable_variations（owner 明示）。

### W066995 — 政府数据汇集（原：下载/裁剪/缓冲修复/合并全过程）

**改写稿**：
> Assemble a natural-resource dataset for a specified property: obtain the relevant features from a government feature service for the given lot/plan boundaries or extent, restrict them to the property area, combine them into a single layer, and save it as a styled GeoPackage. Output: one merged layer covering the target property.

- 删除：fetch counts→IDs→batch download→clip→buffer 修复→merge 的流程链。
- 保留：数据来源（政府要素服务）、范围约束、输出格式与"单一合并图层"目标。
- 金标注意：buffer 修复几何在原链里是目的性步骤；金标把它记为 conditional（几何无效时）而非 essential。

### W067268 — 噪声预测（原：28 步全流程叙述，几乎给出答案）

**改写稿**：
> Estimate noise levels (dBA) at receptor locations around a point noise source according to the BS 5228 standard, accounting for terrain between source and receptors, distance attenuation, ground type, and barriers. Input: a point source, receptor polygons, and a DEM; layers must be handled in a projected CRS. Output: a noise-level value per receptor and a styled source-point layer.

- 删除：viewshed/hex grid/zonal statistics/distance-to-hub/join/field-calculator 全部实现路径与"integrates QGIS processing algorithms: …"清单。
- 保留：标准（BS 5228）、物理因素清单（这些是任务约束而非步骤）、CRS 要求、输出定义。
- 金标注意：此条去过程化幅度最大；金标按"必要语义步骤"撰写（距离/衰减/屏障处理为必要，网格化与具体算子路线全部归入 acceptable_variations）；owner 裁定"若目标失清晰则替换"——复核时请确认此稿目标仍清晰。

### W055494 — 林班合并（原：邻接判定/阈值/合并资格/属性保留规则全给出）

**改写稿**：
> Merge small forest-stand polygons into adjacent, similar, larger stands. A small stand is eligible only when it touches a larger neighbour, the relative difference in dominant height stays within the given threshold, and the neighbour is of a qualifying type. Each merged group must retain the attributes of its largest stand, and the output must flag which features were merged. Output: a merged polygon layer with a merged flag and a cleaned attribute schema.

- 删除："computes adjacency via spatial intersection/touching, … dissolves selected small stands …" 实现序列。
- 保留：三条资格判据（这些是业务规则而非步骤）、属性保留规则、flag 与 schema 要求。
- 金标注意：邻接/筛选/合并的语义步骤仍需模型自行分解；资格判据是输入约束不是算子提示。

### W068342 — 安全冠层点（owner 示范稿，微调采纳）

**改写稿**：
> Select valid canopy-photo locations from a set of candidate points, an optimized flight grid, and an area plot polygon. The selected locations must satisfy the specified spatial safety constraints and use the required projected coordinate reference system. Output: a 'Safe Points' layer of locations valid for canopy photo capture.

- 删除：reproject→-10m buffer→两次 intersect 的步骤序列（owner 示范删除项）。
- 保留：三输入、空间安全约束、CRS 要求、输出语义。
- 金标注意：金标 required_steps 应为"使候选点满足安全约束"的目标级语义；投影/缓冲/相交的具体路线进 acceptable_variations。

### W068833 — 栅格对齐（原：GDAL Warp + 参数清单）

**改写稿**：
> Align multiple input rasters to a common grid — identical CRS, extent, and pixel size — so they can be stacked for a multi-criteria suitability analysis. Alignment must honour a reference (snap) grid; nodata handling and resampling method must be stated. Output: a set of aligned rasters with identical grid structure and a record of the alignment parameters used.

- 删除："using GDAL Warp"、参数枚举、preview/manifest 产物细节。
- 保留：对齐目标三要素、snap 约束、nodata/重采样须声明的约束、可堆叠目的。
- 金标注意：owner 裁定"不提供现成算法名称和执行顺序"——已满足；对齐可用 warp/translate 等多路线。

### W067092 — 面积加权平均（原：ID/面积字段→dissolve→intersect→加权→聚合→删列全流程）

**改写稿**：
> For each polygon in an input layer, compute the area-weighted average of a numeric attribute from an overlay polygon layer. Overlapping or duplicated overlay geometry must be handled so that each overlay area contributes exactly once. Output: the input features with the area-weighted average attached, plus a per-feature detail layer; a CRS check is expected for geographic or mismatched layers.

- 删除：incremental ID/area 字段、dissolve、intersect、加权和、除法、删列的实现序列。
- 保留：加权平均定义、重复几何处理要求、detail 输出、CRS 检查预期（owner 保留项）。
- 金标注意："去重/交集/加权/聚合"的分解仍是模型的推断任务；金标把具体实现全部视为路线。

### W007046 — 属性筛选与中心点（原：正则→计数→收集→修复→质心流程）

**改写稿**：
> From a vector layer, select the features whose string attribute matches a given case-insensitive pattern. Report (a) the total number of input features and (b) the number of matching features, and produce (c) a single point at the geometric centre of the matching features' combined geometry. Output: the matching features carrying both counts, and one centroid point feature carrying the same counts.

- 删除：collect/fixgeometries/centroids/retainfields 实现链、"unioned"措辞（改为 combined geometry，消除 union 算子暗示）。
- 保留：正则匹配定义、两类计数、质心语义、双输出结构。
- 金标注意：匹配集合有效性处理（修复几何）记为 conditional。

### W068582 — Manning 系数（原：AOI 子集+裁剪+字段添加步骤）

**改写稿**：
> Within a user-defined area of interest, assign a Manning roughness coefficient to CORINE 2018 land-cover polygons, using the provided CODE_18→n lookup table, and compute each polygon's area in square metres and hectares. All outputs must be in a common CRS. Output: the AOI land-cover polygons with Manning and area attributes, loaded for visualization.

- 删除："subsets by AOI geometry (with reprojection if needed), clips" 实现步骤。
- 保留：AOI 约束、查找表来源、面积单位、CRS 一致性、加载要求。
- 金标注意：CRS 不一致时"先投影"是模型的推断点，金标记 required_conditions。

### W000890 — 主导干旱等级（原：difference 优先级处理→相交→面积→主导类别全流程）

**改写稿**：
> Produce a per-municipality dominant drought-class map from a drought-severity polygon layer whose classes overlap. Overlaps must be resolved so that more severe classes take precedence (hierarchical exclusivity). For each municipality, determine the drought class covering the largest area within it. Output: (1) a municipality layer symbolized by dominant drought class and (2) a table listing each municipality's dominant class code/name and the corresponding area.

- 删除："using topological difference operations"、"It intersects … computes area … identifies" 实现序列。
- 保留：重叠解决准则（等级优先——业务规则）、市政单元、主导定义（面积最大）、双输出。
- 金标注意：等级互斥可由 difference 链或逐级过滤等路线实现，acceptable_variations 记录。

### W033927 — 海底底质制图（原：点→路径→楔形缓冲→按类别融合的具体路线）

**改写稿**：
> Map seafloor substrate units from ROV navigation tracks and annotations: for each annotated location, represent the area of seafloor visible to the camera as a substrate-classified polygon oriented along the track, then combine overlapping areas so each final unit carries a single substrate class. Output: a polygon layer of substrate mapping units with standardized styling.

- 删除：createpoints/pointstopath/wedge buffers 的算子级路线（"wedge buffers"改为语义描述"polygon oriented along the track"）。
- 保留：双输入（导航+标注）、视域多边形语义、按类别融合、样式化输出。
- 金标注意：楔形几何的具体构造是路线不是步骤；"沿航向定向"与"视域"是必要语义。

### W067404 — 物种点邻域统计（owner 给定方向）

**改写稿**：
> For each species-occurrence point, summarise a continuous environmental raster within a circular neighbourhood of a user-specified radius: compute the requested statistics of the raster inside each neighbourhood and attach them to the original point locations. Output: the occurrence points enriched with the neighbourhood statistics.

- 删除："first creates a buffer … then calculates all available zonal statistics … finally converts to centroids" 全流程。
- 保留：邻域定义（圆形+半径）、统计量须指明、结果回挂到点。
- 金标注意：缓冲→分区统计→质心回挂是主导路线；金标把它作为 required_steps 的语义层（邻域定义/统计/回挂），buffer+centroid 实现进 acceptable_variations。

### W055534 — 国家人口统计（原：分区统计+修复+删字段+CSV 导出流程）

**改写稿**：
> Compute per-country mean values of several raster indicators — land quality and population density for the years 1500, 1990, and 2000 — using country boundaries as zones. Retain the country name and ISO code fields, attach one distinctly prefixed set of statistics per indicator and year, and export the final attribute table as CSV. Output: a countries layer carrying all statistics, plus the exported CSV file.

- 删除：fixgeometries/deletecolumn 具体步骤、文件硬编码路径。
- 保留：指标×年份清单、字段保留要求、前缀区分、CSV 导出。
- 金标注意：多指标批量执行（4 个栅格×同一分区）是结构要点；修复几何记 conditional。

## 备选（5 条条件保留）

### W000674 — 地形三派生（原：投影目标 + 三个 GDAL 算法 + 光照参数全给出）

**改写稿**：
> From a high-resolution DEM, produce three terrain-derivative rasters: slope in degrees, aspect in degrees, and a hillshade. The derivatives must be geometrically meaningful, which requires working in a projected metric CRS; the hillshade must state its illumination parameters. Output: three georeferenced raster files added to the project.

- 删除：目标 EPSG、GDAL 算法名、双线性重采样与 z-factor 等参数。
- 保留：三派生定义、米制 CRS 必要性（约束——模型仍需推断"先重投影"）、光照参数须声明。
- 金标注意：重投影是 required_steps（CRS 必要性的推论）；三个派生可并行。

### W055913 — 农业分区合并（原：修复→union→单部件→几何属性→ID 全流程）

**改写稿**：
> Combine two polygon zoning layers (e.g., management zones and soil zones) into a single layer of non-overlapping atomic zones, where each output polygon represents a unique combination of the two zonings. Geometry must be valid, multipart results resolved to single parts, and each zone uniquely identified. Output: one polygon layer with a unique zone ID and geometry attributes (area, perimeter) per zone.

- 删除：fixgeometries/union/multiparttosingleparts 实现顺序。
- 保留：原子分区语义（唯一组合）、有效性/单部件/唯一 ID 要求、面积周长。
- 金标注意：union 是主导路线但 gold 应允许交集+差集组合等路线。

### W000635 — 多边形边界带（原：编号步骤 1-6 全给出）

**改写稿**：
> Generate a polygon layer of uniform-width bands tracing the boundaries of input polygons, for tactile-map edge rendering. The band width is user-specified and bands must be centred on the original outlines, free of geometry artefacts, and combined into a clean output. Output: polygon features representing the edge bands.

- 删除：单部件转换/简化/内外缓冲/差分/融合的编号流程。
- 保留：等宽边带定义、居中与无伪影要求、宽度参数。
- 金标注意：内外缓冲差分是主导路线；边界提取类路线（polygons-to-lines + buffer）应记为可接受替代。

### W056058 — 水网分级缓冲（原：裁剪→分类→三级缓冲+颜色全流程）

**改写稿**：
> For a water-network vector layer restricted to a study area, separate the network into its three hierarchical levels (Principal, Secundaria, Terciaria) according to the level attribute, and generate a buffer zone around each level with its own specified radius (each level has a distinct radius). Output: the study-area network, one filtered layer per level, and one buffer layer per level.

- 删除：clip 实现步骤与颜色分配细节。
- 保留：研究区限制、三级定义与判据字段、逐级半径、三组输出。
- 金标注意：先裁后分 vs 先分后裁是等价路线；"分类"是属性过滤语义。

### W023206 — DEM 分块（owner：复核复杂度是否过低）

**改写稿**：
> Split a digital elevation model into regularly sized, georeferenced raster tiles that tile the DEM extent without gaps, numbered by row and column, and produce the tile scheme as a vector grid layer. Output: the set of DEM tiles and the grid layer, ready for downstream 3D-printing preparation.

- 删除：建网格→逐格裁剪的步骤叙述与插件名（DEMto3D）。
- 保留：分块目标、无缝覆盖/编号要求、网格层输出。
- 金标注意：复杂度风险标记——链长 3、语义步骤可能仅 2（网格+裁剪）；owner 复核时裁定保留或降级为 smoke 用例。

---

## 汇总

| 状态 | 数量 | 明细 |
|------|------|------|
| 条件保留已改写（PENDING-OWNER） | 19 | 正选 14 + 备选 5 |
| 替换退出 | 11 | 正选 6（W005784/W000863/W055625/W067034/W000084/W001034）+ 备选 5（W002004/W055689/W005684/W000060/W001974） |
| 补足需求 | 1 | 见 `pca_b_group_refill_v1.json`（owner 补审） |
| W023206 特别项 | 1 | 复杂度过低风险，owner 裁定保留或降级 |
