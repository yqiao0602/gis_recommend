# Q2 V2-P0 六对源码核验发现 V1（DIFF-6→4→5→1→12→19，6/6 完成）

- **日期**：2026-10-17；**执行**：B 轨代理（owner 队列 V2-P0，顺序按 owner 指定）
- **方法**（owner 冻结流程，未变更）：sha1 对比 → 逐行 unified diff → 字面量对照指令主张
- **语料**：`.tmp_gee_batch13_sources/Data/dataNNNNN/script_XXXXX.txt`（路径映射
  `Q2_PACKET_SCRIPT_PATHS_V1.json`；六对 12 个脚本全定位）
- **判读维度**（owner 指定四维）：源码异同与差异位置 / 指令忠实度 / 差异类别
  （规划结构 vs 参数字面量 vs 其他实现细节）/ 双方工作流是否均合理
- **前置纪律**（owner 原文）：指令与源码不一致时，不得计入"模型应学不同结构"的证据。

## 0. 总表

| 对 | 脚本 A / B | sha1 | 结构差异的真实来源 | 指令忠实度 | 归类 |
| --- | --- | --- | --- | --- | --- |
| DIFF-6 | 213853 / 213841 | 432b9520 / e299d6cc | A 末尾 ~35 行 **ui.DateSlider NDVI 时间滑块挂件**（S2_SR 加载+NDVI+图层） | B 忠实；A 忠实于核心但**漏述挂件** | 非分析性 UI 附属块 |
| DIFF-4 | 111047 / 111048 | cbf5a017 / 25eafe43 | A 多**逐类像元采样（numPixels=200）+ randomColumn 三分割 + 验证/测试误差矩阵**；B= sampleRegions 全样本+仅训练集混淆矩阵 | 双方忠实但**均未述验证协议** | 同目标两种合法实现（实现级合理多解） |
| DIFF-5 | 178822 / 292317 | abd7ee26 / e76035b9 | B 为**重复块拼接变体**（gfc2015 声明 5 次 vs 3 次、lossImage 4 vs 2）；其余=空白格式 | 双方忠实 | 脚本内部重复块伪差异 |
| DIFF-1 | 258065 / 220359 | 17518235 / 1ab3a487 | **重构+改名**（`select().sum()`↔`sum().select()`、字段名 mean_annual_precipitation→mean_precipitation、百分比先算入表 vs 相关时内联 map）；A 另加载 1 个辅助数据集（Proba-V LC 2019 显示） | 双方忠实 | 代码风格重构 + 辅助显示 |
| DIFF-12 | 146442 / 146438 | ee910525 / 7b21d71c | **Landsat7 C1_T1_SR → C2_T1_L2 数据集版本**（连带 SR_ 波段名）；云掩膜实现变体（A 的 `image.mask().reduce(min)` 在 B 被注释）=A 多出 AGGREGATION 的来源 | 双方忠实（B 明述 collection 2 level 2） | 参数/字面量（数据资产版本）+ 掩膜实现变体 |
| DIFF-19 | 73545 / 73548 | 3be434af / aea6da46 | A 多 `GEOMETRY_DEFINE` = **`Map.centerObject(ee.Geometry.Point(...))` 地图定位**；真实语义差=烧毁后 NBR 阈值字面量 `lte(0)` vs `lte(-0.02)`（RLE 不可见）；B 的 `var bands`=死代码 | B 忠实（双阈值与代码精确一致）；A 泛述无失实，但 A 脚本自身**注释与代码矛盾**（注释写 -0.02 代码写 0） | 参数/字面量（阈值）+ 修饰性几何 |

## 1. 逐对四维记录

### DIFF-6（最高优先；owner 假设"流程截断/抽取遗漏/映射不一致"检验）

- **源码**：6,551 vs 5,348 chars；diff 集中两处——①~35 行末尾块（A 独有）：`Map.getBounds → S2_SR filterBounds/filterDate/filter(CLOUDY_PIXEL_PERCENTAGE<10) → NDVI → ee.Dictionary.evaluate(renderSlider) → ui.DateSlider(period:5) → ui.Map.Layer`；②散布的图表标题/lineWidth/pointSize/Map.setCenter 坐标/占位符文案/图例标签/调色板。
- **RLE 差异↔代码映射**：A 多出的 4 标签 `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER` **精确对应挂件块**的 ImageCollection 加载 + filterBounds + filterDate + CLOUDY_PIXEL_PERCENTAGE 过滤。
- **指令忠实度**：两指令描述的核心（TC=线性变换、图表、可点击图、可切换尺度）两侧代码均有；A 指令未提及 NDVI 滑块（**欠描述**，非失实）；B 指令"interact with the time series"对应双方共有的可点击图表。
- **双方合理性**：分析工作流（氮含量估算）**完全一致**；结构差异由 UI 探索挂件驱动。
- **owner 假设检验结果**：非截断、非抽取遗漏、非标签映射不一致——抽取器忠实记录了挂件的 API 调用；问题是 **RLE 把 UI 脚手架与分析步骤同权计数**。

### DIFF-4

- **源码**：52,050 vs 48,531 chars，共享前 ~2,200 行；A 独有块①（~70 行）：五类样本逐类 `imagem.sample({numPixels:200, seed})` → `randomColumn` → `<0.7` 训练 / `0.7–0.85` 验证 / `≥0.85` 测试三分割；A 独有块②：验证集与测试集 `classify + errorMatrix + accuracy` 输出。B：`merge` 成总 FeatureCollection → `sampleRegions` → 训练 RF(50) → 仅训练集混淆矩阵 → 分类成图。
- **RLE 差异↔代码映射**：A 的 `VECTOR_LOAD -> COLLECTION_MGMT -> VECTOR_LOAD -> ATTRIBUTE_FILTER` 对应采样/分割块（FeatureCollection 构造、list map、random 过滤）。
- **指令忠实度**：两指令近乎相同且只写 "trained on manually labeled sample regions"——**均未要求验证协议**，均无失实。
- **双方合理性**：**均合理**（一个做留出验证、一个全样本训练）；这是"同一指令的两种合法实现"，属**实现级合理多解**，不是任务逻辑差异。

### DIFF-5

- **源码**：3,165 vs 3,632 chars；B 重复声明 `gfc2015`×5（A ×3）、`lossImage`×4（A ×2），重复重设 countries/congo 过滤；保护区过滤条件（IUCN_CAT≠VI、STATUS≠proposed、STATUS_YR<2010）、zonal 统计（scale 30、maxPixels 1e9）、输出 print 全部一致；其余 diff=缩进/合并行格式。
- **RLE 差异↔代码映射**：B 多出的 `ATTRIBUTE_FILTER` 与顺序变化=**重复块的重声明产物**；无新分析步骤。
- **指令忠实度**：双方忠实（false-color 措辞差异是红鲱鱼——两侧代码都有 false-color 图层）。
- **双方合理性**：分析完全同构；B 的"更长链"是拼接伪影。
- **owner 顺序关切检验**："顺序变化需查数据依赖"——已查：顺序变化来自重复声明，非依赖重排。

### DIFF-1

- **源码**：8,891 vs 8,884 chars；10 个签名级 hunk 全部为重构模式：`select("prec").sum()` ↔ `sum().select("prec")`（语义等价交换）、字段改名（mean_annual_precipitation→mean_precipitation、mean_NDVI→mean_ndvi、tree_cover→tree_cover_area）、tree-cover 百分比"先算入表"（A）vs"相关分析时 `map(compute_tree_cover_percentage)` 内联"（B）；A 另加载 `COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019`（辅助显示，B 无）。
- **数据集对账**：核心 5 个（GAUL/NASADEM/WORLDCLIM/WorldCover/S2_SR）两侧一致；相关+散点各 3 组一致。
- **指令忠实度**：双方忠实（"derived metrics" vs "statistical summaries" 措辞差异对两侧代码都成立）。
- **双方合理性**：均合理；结构差异=重构投影+1 个辅助数据集。

### DIFF-12

- **源码**：7,128 vs 7,134 chars；核心差异=数据集版本 `LANDSAT/LE07/C01/T1_SR` → `LANDSAT/LE07/C02/T1_L2`（连带 B4/B3/B1 → SR_B4/SR_B3/SR_B1 波段名、QA band pixel_qa→QA_PIXEL、云掩膜函数 cloudMaskL457→cloudMaskL7_level2）；A 掩膜含 `image.mask().reduce(ee.Reducer.min())`（B 注释掉）= **A 多出 AGGREGATION 的精确来源**；输出文件名字面量不同。
- **指令忠实度**：A"landsat 7 surface reflectance"与 B"landsat 7 collection 2 level 2 surface reflectance"各自与其脚本一致——**双方忠实，且指令差异真实反映了数据资产版本差异**。
- **双方合理性**：均合理；分析流程（掩膜→年/DOY 波段→NDVI/EVI→日拼接→分区均值→导出）完全同构。
- **判读**：这是六对中唯一"指令差异↔代码差异"存在真实对应关系的对，但对应物是**数据资产版本字面量**，不改变分析结构。

### DIFF-19

- **源码**：3,255 vs 3,291 chars；仅 4 处差异：①B 多死代码 `var bands=[...]`（声明后未用）；②烧毁后 NBR 阈值 **A `lte(0)` vs B `lte(-0.02)`**（delta NBR `gte(0.3)` 两侧一致）；③`Map.centerObject(ee.Geometry.Point(76.535,11.78))`（A）vs `Map.centerObject(bandipur)`（B）——**A 链多出 GEOMETRY_DEFINE 的精确来源**；④无其他。
- **指令忠实度**：B 忠实（"delta nbr > 0.3 且 post-fire nbr < -0.02"与 B 代码逐字一致）；A 泛述（不给阈值）无失实；**A 脚本自身注释写 "-0.02" 而代码执行 `lte(0)`**——代码-注释矛盾登记（脚本质量问题，非指令问题）。
- **双方合理性**：均合理；结构差异由地图定位修饰调用驱动，真实语义差（阈值）在 RLE 层不可见——owner"链条差异没有直接体现 B 更具体的阈值要求"的判断**证实并精化**。

## 2. 六对汇总裁定（owner 四类映射）

| owner 四类 | 计数 | 样本 |
| --- | --- | --- |
| ① 真实规划结构差异（任务要求不同操作/依赖） | **0 / 6** | — |
| ② 参数/字面量差异（结构同、数据/阈值/波段/资产不同） | 4 / 6 含此类 | DIFF-12（数据集版本）、DIFF-19（阈值）、DIFF-6（修饰字面量）、DIFF-1（改名） |
| ③ 任务描述保真度缺陷 | 0 / 6 指令级失实；1 欠描述 | DIFF-6 A 漏述 UI 挂件（+1 脚本级注释矛盾：DIFF-19 A） |
| ④ 证据不足/其他实现差异 | 2 / 6 | DIFF-4（实现级合理多解：验证协议有无）、DIFF-5（重复块拼接伪影）；另 DIFF-6（UI 挂件）、DIFF-1（重构）亦属"非任务驱动实现差异" |

**头条结论：6/6 的链条结构差异均无任务逻辑依据**——分解为 UI 挂件（1）、实现严谨度变体（1）、重复块（1）、重构（1）、数据集版本（1）、阈值+修饰（1）。抽取器本身在六对上零错误（链差异均真实反映代码中的 API 调用差异）；**问题不在抽取噪声，而在 RLE 表示把分析步骤、UI 脚手架、重复块、重构等权投影到同一序列**。

## 3. 对训练监督的含义（建议，待 owner 裁定，不自动执行）

1. **SFT 风险具体化**：近重复指令对若以当前链差异入训，模型学到的是"相同指令可映射到差一个 UI 挂件/重复块/重构的链"——这是映射层的**不可约歧义**（监督噪声），不是可学习的任务逻辑。owner 风险登记（批次三）在源码级证实。
2. **候选数据侧动作**（均须 owner 放行）：a) 规划监督的链抽取排除/降权 UI 脚手架类调用（ui.*、Map.addLayer/centerObject、palette 类）——受控变更；b) 近重复对在 canonical+字面量层做二次去重（DIFF-5 类拼接变体并入）；c) 指令保真度闸门（SAME-15 A / DIFF-6 A 式欠描述与失实的候选检测）。
3. **双层表示获直接支持**：六对中所有真实语义差异（数据资产版本、阈值、验证协议）都在实现参数层，无一在规划层——与 V3 结论（时间范围/命名/循环参数在字面量层）完全合流。

## 4. 仪器备注

- DIFF-4 两个脚本 ~2,200 行共享前缀 + 少量独有块：长脚本 diff 需按 hunk 汇总后再分类（全量 124 行 diff 中签名级仅 10 hunk）。
- 本轮全部结论基于逐对通读 diff + 关键字面量 grep 复核；DIFF-4 的 52KB 脚本未逐行通读共享前缀（两侧一致部分由 diff 机制保证）。
