# Q2 优先核验包 V1（指令 x 原始 canonical 链 x 粗标签 三对齐材料）

- **日期**：2026-10-17；**来源**：`Q2_OWNER_ADJUDICATION_V1.json` 优先核验队列
- **池**：`04_DIAG_WORK/b1_gee_stage_train.jsonl`（128,447 行，只读，未修改）
- **渲染纪律**：RLE 以游程计数显示（`LABELxN`）；每对附自动链 diff——DIFF-20 教训（1 个重复块肉眼不可辨）自本包起不可能再现
- **用途**：owner 逐步对照指令、原始 GEE API 序列与 30 类粗标签，判断结构差异来自真实分析逻辑、工作流抽取，还是标签体系。canonical 链在 JSON 中完整、在此处截断至前 1200 字符（总长已标注）

## 机械预观察总表（canonical = API 名级序列，不含字面量）

| 对 | 队列 | 粗链步数 A/B | 模板支持 A/B | 双侧 canonical 一致 |
| --- | --- | --- | --- | --- |

**预观察读法（登记人，供对照时参考，非结论）**：双侧 canonical 一致的对（含全部 V3 SAME 对）= 两行共享同一 API 调用序列，指令差异属描述层，核验重心转为'哪一侧描述忠实于源码'（字面量差异须读 script 源码）；canonical 不同的对（全部 DIFF 对）= 程序确实不同，核验重心转为'程序差异是否任务驱动'。

## DIFF-6  (J=0.8163 / suspicious / V2-P0 原始程序对照)

**owner 判读注记**：最高优先：指令几乎一致而 A 链 8 步 vs B 链 4 步；优先核查流程截断、步骤抽取遗漏或标签映射不一致（结构抽取一致性最好的检查样本）

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 2/4 行

### DIFF-6 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **2 行**
- 粗链（8 步，游程显示）：`AGGREGATION -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER`

- **canonical**（208 字符，sha16 0ecfe40016fe7a4a，row script_213853）：
```
ee.Reducer.median -> ee.Reducer.mean -> ee.Filter.equals -> ee.Image -> ee.Image.clip -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.lt -> ee.Dictionary
```

### DIFF-6 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **4 行**
- 粗链（4 步，游程显示）：`AGGREGATION -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP`

- **canonical**（85 字符，sha16 983dea8767d41b0c，row script_213841）：
```
ee.Reducer.median -> ee.Reducer.mean -> ee.Filter.equals -> ee.Image -> ee.Image.clip
```

### DIFF-6 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -4,5 +4 @@
 SPATIAL_CLIP
-RASTER_LOAD
-SPATIAL_FILTER
-TEMPORAL_FILTER
-ATTRIBUTE_FILTER
```

---

## DIFF-4  (J=0.8478 / suspicious / V2-P0 原始程序对照)

**owner 判读注记**：A 多出 VECTOR_LOAD->ATTRIBUTE_FILTER->CLASSIFICATION，指令未解释额外分析步骤；疑似结构或标签映射差异

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 1/1 行

### DIFF-4 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **1 行**
- 粗链（13 步，游程显示）：`CLASSIFICATION -> OTHER_UNMAPPED -> RASTER_LOAD -> AGGREGATION -> REGIONAL_STATS -> RASTER_LOAD -> THRESHOLD_LOGIC -> AGGREGATION -> VECTOR_LOAD -> COLLECTION_MGMT -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> CLASSIFICATION`

- **canonical**（573 字符，sha16 7c99128fe565dbae，row script_111047）：
```
ee.Clusterer.wekaKMeans -> ee.Clusterer.train -> ee.Image -> ee.Reducer.max -> ee.Image.reduceRegion -> ee.List.sequence -> ee.Image -> ee.Number -> ee.Number.toInt -> ee.Image.eq -> ee.Reducer.mean -> ee.Reducer.sum -> ee.Reducer.sum -> ee.Reducer.sum -> ee.Number -> ee.Number.multiply -> ee.Number.toLong -> ee.FeatureCollection -> ee.FeatureCollection -> ee.FeatureCollection.first -> ee.FeatureCollection.get -> ee.FeatureCollection -> ee.Number -> ee.Number.multiply -> ee.Filter.lt -> ee.Filter.gte -> ee.Filter.lt -> ee.Filter.gte -> ee.Classifier.smileRandomForest
```

### DIFF-4 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **1 行**
- 粗链（9 步，游程显示）：`CLASSIFICATION -> OTHER_UNMAPPED -> RASTER_LOAD -> AGGREGATION -> REGIONAL_STATS -> RASTER_LOAD -> THRESHOLD_LOGIC -> AGGREGATION -> CLASSIFICATION`

- **canonical**（287 字符，sha16 53c4cfc8b371de30，row script_111048）：
```
ee.Clusterer.wekaKMeans -> ee.Clusterer.train -> ee.Image -> ee.Reducer.max -> ee.Image.reduceRegion -> ee.List.sequence -> ee.Image -> ee.Number -> ee.Number.toInt -> ee.Image.eq -> ee.Reducer.mean -> ee.Reducer.sum -> ee.Reducer.sum -> ee.Reducer.sum -> ee.Classifier.smileRandomForest
```

### DIFF-4 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -8,6 +8,2 @@
 AGGREGATION
-VECTOR_LOAD
-COLLECTION_MGMT
-VECTOR_LOAD
-ATTRIBUTE_FILTER
 CLASSIFICATION
```

---

## DIFF-5  (J=0.7937 / suspicious / V2-P0 原始程序对照)

**owner 判读注记**：AGGREGATION 与 BAND_ARITHMETIC 相对顺序变化；false-color composites 措辞差异不足以解释，需查实际数据依赖

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 3/8 行

### DIFF-5 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Habitat conversion/fragmentation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **3 行**
- 粗链（10 步，游程显示）：`ATTRIBUTE_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（269 字符，sha16 7730d89bd4ee1f8c，row script_178822）：
```
ee.Filter.eq -> ee.Reducer.sum -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Filter.eq -> ee.FeatureCollection -> ee.Filter.bounds -> ee.Filter.neq -> ee.Filter.lt -> ee.Filter.and -> ee.FeatureCollection.filter -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Reducer.sum
```

### DIFF-5 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Habitat conversion/fragmentation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **8 行**
- 粗链（11 步，游程显示）：`ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> AGGREGATION -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（285 字符，sha16 82dbae5002b4a198，row script_292317）：
```
ee.Filter.eq -> ee.Reducer.sum -> ee.Filter.eq -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Filter.eq -> ee.FeatureCollection -> ee.Filter.bounds -> ee.Filter.neq -> ee.Filter.lt -> ee.Filter.and -> ee.FeatureCollection.filter -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Reducer.sum
```

### DIFF-5 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -2,2 +2,3 @@
 AGGREGATION
+ATTRIBUTE_FILTER
 BAND_ARITHMETIC
```

---

## DIFF-1  (J=0.8226 / suspicious / V2-P0 原始程序对照)

**owner 判读注记**：末尾差异（A 多 RASTER_LOAD->AGGREGATION）缺少明确任务依据；A 的派生指标 FeatureCollection 是否对应额外统计待核

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 1/5 行

### DIFF-1 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **1 行**
- 粗链（14 步，游程显示）：`ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> COLLECTION_MGMT -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> AGGREGATION`

- **canonical**（477 字符，sha16 291553588bbb35fd，row script_258065）：
```
ee.Filter.eq -> ee.Filter.eq -> ee.String -> ee.String.cat -> ee.String -> ee.String.cat -> ee.String -> ee.String.cat -> ee.Array -> ee.Reducer.pearsonsCorrelation -> ee.Array -> ee.Array.get -> ee.String -> ee.String.cat -> ee.Filter.eq -> ee.Reducer.mean -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Reducer.mean -> ee.ImageCollection -> ee.ImageCollection.first -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Image -> ee.Reducer.mean
```

### DIFF-1 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **5 行**
- 粗链（12 步，游程显示）：`ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> COLLECTION_MGMT -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（465 字符，sha16 3338b0111acd7b70，row script_220359）：
```
ee.Filter.eq -> ee.Filter.eq -> ee.String -> ee.String.cat -> ee.String -> ee.String.cat -> ee.String -> ee.String.cat -> ee.Array -> ee.Reducer.pearsonsCorrelation -> ee.Array -> ee.Array.get -> ee.String -> ee.String.cat -> ee.Filter.eq -> ee.Reducer.mean -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Reducer.mean -> ee.ImageCollection -> ee.ImageCollection.first -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Reducer.mean
```

### DIFF-1 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -12,3 +12 @@
 AGGREGATION
-RASTER_LOAD
-AGGREGATION
```

---

## DIFF-12  (J=0.75 / suspicious / V2-P0 原始程序对照)

**owner 判读注记**：A 在 GEOMETRY_DEFINE 后多一个 AGGREGATION；田块缓冲/日尺度拼接/区域均值统计间是否有真实额外操作待核（局部操作标注差异）

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 7/22 行

### DIFF-12 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **7 行**
- 粗链（10 步，游程显示）：`GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> VECTOR_LOAD -> OTHER_UNMAPPED`

- **canonical**（602 字符，sha16 a7cb579e1bfadbc4，row script_146442）：
```
ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Reducer.min -> ee.Image.constant -> ee.Image.uint16 -> ee.Date -> ee.Image.constant -> ee.Image.uint16 -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.ImageCollection.map -> ee.List.sequence -> ee.Algorithms.If -> ee.List -> ee.List -> ee.Reducer.mean -> ee.Feature -> ee.Feature.setGeometry
```

### DIFF-12 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Vegetation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **22 行**
- 粗链（9 步，游程显示）：`GEOMETRY_DEFINE -> BAND_ARITHMETIC -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> VECTOR_LOAD -> OTHER_UNMAPPED`

- **canonical**（584 字符，sha16 9bfa45d6a5f7df4a，row script_146438）：
```
ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Geometry.Point -> ee.Geometry.buffer -> ee.Geometry.bounds -> ee.Image.constant -> ee.Image.uint16 -> ee.Date -> ee.Image.constant -> ee.Image.uint16 -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.ImageCollection.map -> ee.List.sequence -> ee.Algorithms.If -> ee.List -> ee.List -> ee.Reducer.mean -> ee.Feature -> ee.Feature.setGeometry
```

### DIFF-12 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -1,3 +1,2 @@
 GEOMETRY_DEFINE
-AGGREGATION
 BAND_ARITHMETIC
```

---

## DIFF-19  (J=0.7857 / suspicious / V2-P0 原始程序对照)

**owner 判读注记**：B 双阈值条件（delta NBR>0.3 且 post-fire NBR<-0.02）未对应结构增量；A 反多 GEOMETRY_DEFINE；粗标签表达能力可能不足（owner 三字段示例样本）

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 2/69 行

### DIFF-19 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Natural hazards；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **2 行**
- 粗链（5 步，游程显示）：`ATTRIBUTE_FILTER -> RASTER_LOAD -> GEOMETRY_DEFINE -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（118 字符，sha16 bc190a298c063b91，row script_73545）：
```
ee.Filter.eq -> ee.Image -> ee.Geometry.Point -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Number -> ee.Number.divide
```

### DIFF-19 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Natural hazards；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **69 行**
- 粗链（4 步，游程显示）：`ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（97 字符，sha16 236a6d2a87396af6，row script_73548）：
```
ee.Filter.eq -> ee.Image -> ee.Image.pixelArea -> ee.Reducer.sum -> ee.Number -> ee.Number.divide
```

### DIFF-19 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -2,3 +2,2 @@
 RASTER_LOAD
-GEOMETRY_DEFINE
 BAND_ARITHMETIC
```

---

## SAME-15  (J=0.8491 / conditional_accept_priority_check / V3 标签表达力核验)

**owner 判读注记**：本批最重要核验对象：GEDI L4B 平均冠层高度 vs 平均生物量——目标变量语义不同；CLASSIFICATION 无法区分分类与回归；若确认将是标签粒度不足的直接证据

**机械预观察**：双侧 canonical API 序列一致（程序同构；字面量差异需读源码）；模板支持 A/B = 17/17 行

### SAME-15 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Forest science；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **17 行**
- 粗链（12 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD -> ATTRIBUTE_FILTER -> TERRAIN_DERIVED -> RASTER_LOAD -> ATTRIBUTE_FILTER -> CLASSIFICATION -> AGGREGATION -> BAND_ARITHMETIC`

- **canonical**（603 字符，sha16 6d85f81095ae36f6，row script_21438）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.Filter.listContains -> ee.ImageCollection.filter -> ee.Filter.listContains -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Reducer.percentile -> ee.Image -> ee.Number -> ee.Number.pow -> ee.Number -> ee.Number.pow -> ee.Filter.lt -> ee.Terrain.slope -> ee.ImageCollection -> ee.Filter.lt -> ee.Filter.gte -> ee.Classifier.smileRandomForest -> ee.Classifier.setOutputMode -> ee.Reducer.min -> ee.Reducer.max -> ee.Image.pixelLonLat -> ee.Dictionary -> ee.Dictionary.get
```

### SAME-15 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Forest science；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **17 行**
- 粗链（12 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD -> ATTRIBUTE_FILTER -> TERRAIN_DERIVED -> RASTER_LOAD -> ATTRIBUTE_FILTER -> CLASSIFICATION -> AGGREGATION -> BAND_ARITHMETIC`

- **canonical**（603 字符，sha16 6d85f81095ae36f6，row script_72061）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.Filter.listContains -> ee.ImageCollection.filter -> ee.Filter.listContains -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Reducer.percentile -> ee.Image -> ee.Number -> ee.Number.pow -> ee.Number -> ee.Number.pow -> ee.Filter.lt -> ee.Terrain.slope -> ee.ImageCollection -> ee.Filter.lt -> ee.Filter.gte -> ee.Classifier.smileRandomForest -> ee.Classifier.setOutputMode -> ee.Reducer.min -> ee.Reducer.max -> ee.Image.pixelLonLat -> ee.Dictionary -> ee.Dictionary.get
```

### SAME-15 粗链自动 diff（A→B，上下文 1）
```
(identical)
```

---

## SAME-19  (J=0.8085 / conditional_accept_priority_check / V3 标签表达力核验)

**owner 判读注记**：日尺度/月度累计/年度累计/动画步长多个时间维度被同一 AGGREGATION 概括；模型预测对标签也可能生成错误流程；三步粗链不足以验证时间语义保留

**机械预观察**：双侧 canonical API 序列一致（程序同构；字面量差异需读源码）；模板支持 A/B = 60/60 行

### SAME-19 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Precipitation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **60 行**
- 粗链（3 步，游程显示）：`TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION`

- **canonical**（58 字符，sha16 ced1af7b2177acb1，row script_15683）：
```
ee.Filter.calendarRange -> ee.Filter.eq -> ee.Reducer.mean
```

### SAME-19 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Precipitation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **60 行**
- 粗链（3 步，游程显示）：`TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION`

- **canonical**（58 字符，sha16 ced1af7b2177acb1，row script_15682）：
```
ee.Filter.calendarRange -> ee.Filter.eq -> ee.Reducer.mean
```

### SAME-19 粗链自动 diff（A→B，上下文 1）
```
(identical)
```

---

## SAME-11  (J=0.7714 / accept / V3 标签表达力核验)

**owner 判读注记**：高层结构相同合理；awei_ns vs awei 变体与阈值定义属参数/算法语义层核验点，非结构问题

**机械预观察**：双侧 canonical API 序列一致（程序同构；字面量差异需读源码）；模板支持 A/B = 49/49 行

### SAME-11 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Terrestrial hydrosphere indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **49 行**
- 粗链（4 步，游程显示）：`RASTER_LOAD -> SPATIAL_FILTER -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（93 字符，sha16 1ac26606303a3dc3，row script_62643）：
```
ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.Image.pixelArea -> ee.Reducer.sum
```

### SAME-11 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Terrestrial hydrosphere indicators；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **49 行**
- 粗链（4 步，游程显示）：`RASTER_LOAD -> SPATIAL_FILTER -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（93 字符，sha16 1ac26606303a3dc3，row script_62640）：
```
ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.Image.pixelArea -> ee.Reducer.sum
```

### SAME-11 粗链自动 diff（A→B，上下文 1）
```
(identical)
```

---

## SAME-9  (J=0.8519 / conditional_accept / V3 标签表达力核验)

**owner 判读注记**：A 三指标明确、B 概括；多个 AGGREGATION 不能证明三指标及时间维度完整表达（指标完整性核验）

**机械预观察**：双侧 canonical API 序列一致（程序同构；字面量差异需读源码）；模板支持 A/B = 51/51 行

### SAME-9 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Water quality；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **51 行**
- 粗链（62 步，游程显示）：`VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> OTHER_UNMAPPED -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> BAND_ARITHMETIC -> MASKING -> AGGREGATION`

- **canonical**（2,296 字符，sha16 48760ec9d3de6f8c，row script_38679）：
```
ee.Feature -> ee.Number -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.ImageCollection.sort -> ee.ImageCollection.first -> ee.Date -> ee.Date.format -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic -> ee.PixelType.float -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.ImageCollection.sort -> ee.ImageCollection.first -> ee.Date -> ee.Date.format -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic -> ee.Image.constant -> ee.Image.updateMask -> ee.Reducer.sum -> ee.Number -> ee.Number.divide -> ee.Reducer.mean -> ee.Algorithms.If -> ee.Image.constant -> ee.Image.updateMask -> ee.Reducer.sum -> ee.Number -> ee.Algorithms.If -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.Filter.calendarRang…
```

### SAME-9 臂 B
- 匹配池行：3（canonical 形态 1 种，物化前 3 种）；task_type：Water quality；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **51 行**
- 粗链（62 步，游程显示）：`VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> OTHER_UNMAPPED -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> BAND_ARITHMETIC -> MASKING -> AGGREGATION -> BAND_ARITHMETIC -> MASKING -> AGGREGATION`

- **canonical**（2,296 字符，sha16 48760ec9d3de6f8c，row script_38703）：
```
ee.Feature -> ee.Number -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.ImageCollection.sort -> ee.ImageCollection.first -> ee.Date -> ee.Date.format -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic -> ee.PixelType.float -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.ImageCollection.sort -> ee.ImageCollection.first -> ee.Date -> ee.Date.format -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic -> ee.Image.constant -> ee.Image.updateMask -> ee.Reducer.sum -> ee.Number -> ee.Number.divide -> ee.Reducer.mean -> ee.Algorithms.If -> ee.Image.constant -> ee.Image.updateMask -> ee.Reducer.sum -> ee.Number -> ee.Algorithms.If -> ee.ImageCollection -> ee.ImageCollection.filterBounds -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.ImageCollection.filter -> ee.Filter.calendarRang…
```

### SAME-9 粗链自动 diff（A→B，上下文 1）
```
(identical)
```

---

## DIFF-2  (J=0.75 / suspicious / 第二批)

**owner 判读注记**：时间范围差异不足以证明结构必变；COLLECTION_MGMT/ATTRIBUTE_FILTER 差异可能标注不一致

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 1,339/8 行

### DIFF-2 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **1,339 行**
- 粗链（3 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION`

- **canonical**（93 字符，sha16 6e323db2d1522808，row script_54185）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.Reducer.median -> ee.Reducer.stdDev
```

### DIFF-2 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **8 行**
- 粗链（6 步，游程显示）：`RASTER_LOAD -> COLLECTION_MGMT -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`

- **canonical**（206 字符，sha16 fa27590d84aac88c，row script_54182）：
```
ee.ImageCollection -> ee.ImageCollection.merge -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.Filter.not -> ee.ImageCollection.filter -> ee.Reducer.median -> ee.Reducer.stdDev -> ee.Image
```

### DIFF-2 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -1,3 +1,6 @@
 RASTER_LOAD
+COLLECTION_MGMT
 TEMPORAL_FILTER
+ATTRIBUTE_FILTER
 AGGREGATION
+RASTER_LOAD
```

---

## DIFF-3  (J=0.7857 / likely_reasonable / 第二批)

**owner 判读注记**：B 增 S1 VV 后向散射+DEM 入特征栈，A 链未体现；需检查 A 为何未体现训练/验证步骤

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 7/2 行

### DIFF-3 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **7 行**
- 粗链（5 步，游程显示）：`ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION -> BAND_SELECT -> CLASSIFICATION`

- **canonical**（196 字符，sha16 59f2d016b9f0a052，row script_182308）：
```
ee.Filter.lt -> ee.Filter.listContains -> ee.Filter.listContains -> ee.Filter.eq -> ee.Filter.eq -> ee.ImageCollection -> ee.ImageCollection.mean -> ee.Image.cat -> ee.Classifier.smileRandomForest
```

### DIFF-3 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **2 行**
- 粗链（8 步，游程显示）：`ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> AGGREGATION -> CLASSIFICATION`

- **canonical**（250 字符，sha16 242bb2f4406c6d53，row script_182335）：
```
ee.Filter.lt -> ee.ImageCollection -> ee.Filter.listContains -> ee.ImageCollection.filter -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.ImageCollection.select -> ee.ImageCollection.median -> ee.Classifier.smileRandomForest
```

### DIFF-3 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -2,4 +2,7 @@
 RASTER_LOAD
+ATTRIBUTE_FILTER
+TEMPORAL_FILTER
+SPATIAL_FILTER
+BAND_SELECT
 AGGREGATION
-BAND_SELECT
 CLASSIFICATION
```

---

## DIFF-7  (J=0.7547 / suspicious / 第二批)

**owner 判读注记**：A 多 ATTRIBUTE_FILTER 但 B 反而明确提到辅助数据；需检查辅助数据与掩膜处理是否真的导致不同操作

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 22/44 行

### DIFF-7 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **22 行**
- 粗链（5 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`

- **canonical**（178 字符，sha16 6118d450a352f985，row script_54188）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.Filter.calendarRange -> ee.Filter.not -> ee.ImageCollection.filter -> ee.Reducer.median -> ee.Reducer.stdDev -> ee.Image
```

### DIFF-7 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **44 行**
- 粗链（4 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD`

- **canonical**（105 字符，sha16 7169cad92b0cb921，row script_54187）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.Reducer.median -> ee.Reducer.stdDev -> ee.Image
```

### DIFF-7 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -2,3 +2,2 @@
 TEMPORAL_FILTER
-ATTRIBUTE_FILTER
 AGGREGATION
```

---

## DIFF-8  (J=0.7959 / conditional_accept / 第二批)

**owner 判读注记**：B 末尾多 AGGREGATION->VECTOR_LOAD；导出本身不自动解释这两个标签，需查是否对应实际必要操作

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 4/3 行

### DIFF-8 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **4 行**
- 粗链（20 步，游程显示）：`ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`

- **canonical**（733 字符，sha16 178b674d0117fba4，row script_35908）：
```
ee.Filter.inList -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.ImageCollection.select -> ee.ImageCollection.mean -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.ImageCollection.select -> ee.ImageCollection.mean -> ee.Reducer.mean -> ee.Reducer.min -> ee.Reducer.max -> ee.Image -> ee.Image.addBands -> ee.Filter.lt -> ee.Filter.gt -> ee.Classifier.smileRandomForest
```

### DIFF-8 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land use/land cover；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **3 行**
- 粗链（22 步，游程显示）：`ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION -> AGGREGATION -> VECTOR_LOAD`

- **canonical**（820 字符，sha16 38481ee4e312c91f，row script_35919）：
```
ee.Filter.inList -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.ImageCollection.select -> ee.ImageCollection.mean -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.filterBounds -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.Filter.eq -> ee.ImageCollection.filter -> ee.ImageCollection.select -> ee.ImageCollection.mean -> ee.Reducer.mean -> ee.Reducer.min -> ee.Reducer.max -> ee.Image -> ee.Image.addBands -> ee.Filter.lt -> ee.Filter.gt -> ee.Classifier.smileRandomForest -> ee.Reducer.sum -> ee.Number -> ee.Number.multiply -> ee.Number.divide -> ee.Feature
```

### DIFF-8 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -20 +20,3 @@
 CLASSIFICATION
+AGGREGATION
+VECTOR_LOAD
```

---

## DIFF-9  (J=0.84 / conditional_accept / 第二批)

**owner 判读注记**：B 明确计算作物系数 Kc 而 A 未明确；B 额外步骤可能有据，但必须确认 A 是否隐含计算 Kc，不能仅凭文本缺失断定 A 结构错误

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 80/61 行

### DIFF-9 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：True
- 模板全局支持度：该 RLE 在池内出现 **80 行**
- 粗链（68 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPATIAL_JOIN -> BAND_ARITHMETIC -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> THRESHOLD_LOGIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> THRESHOLD_LOGIC -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> RESAMPLE_REPROJECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC`

- **canonical**（3,818 字符，sha16 65eb01a7f0d7a687，row script_145258）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.select -> ee.Date -> ee.Image -> ee.Image.select -> ee.Image -> ee.Image -> ee.Image.addBands -> ee.Image.pixelLonLat -> ee.Image.select -> ee.Image.pixelLonLat -> ee.Image.select -> ee.Date -> ee.Date.format -> ee.Number -> ee.Number.add -> ee.Join.saveAll -> ee.Join.apply -> ee.Number -> ee.Image.constant -> ee.Date -> ee.Filter.equals -> ee.Join.saveAll -> ee.Join.apply -> ee.Date -> ee.Image -> ee.Image.rename -> ee.Image.float -> ee.Image.constant -> ee.Reducer.linearRegression -> ee.List -> ee.Number -> ee.List.add -> ee.List -> ee.Date -> ee.Date.difference -> ee.Image -> ee.Image.rename -> ee.Image -> ee.Image.rename -> ee.Date -> ee.Date.millis -> ee.Image -> ee.Image.select -> ee.Image.multiply -> ee.Image.reduce -> ee.Image.rename -> ee.Image.addBands -> ee.Number -> ee.Number.divide -> ee.Image -> ee.Image -> ee.Image -> ee.Image.multiply -> ee.Image -> ee.Image.multiply -> ee.Image -> ee.Image.subtract -> ee.Image -> ee.Filter.equals -> ee.Join.saveAll -> ee.Join.apply -> ee.Image -> ee.Image.get -> ee.List -> ee.List.get -> ee.Image -> ee.Image.select -> ee.Image -> ee.Image -> ee.Image.get -> e…
```

### DIFF-9 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Land surface/agriculture indicators；run_cap：True
- 模板全局支持度：该 RLE 在池内出现 **61 行**
- 粗链（70 步，游程显示）：`RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPATIAL_JOIN -> BAND_ARITHMETIC -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> THRESHOLD_LOGIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> THRESHOLD_LOGIC -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> THRESHOLD_LOGIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> RESAMPLE_REPROJECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC`

- **canonical**（4,059 字符，sha16 f83b43362fbeb591，row script_145162）：
```
ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.select -> ee.Date -> ee.Image -> ee.Image.select -> ee.Image -> ee.Image -> ee.Image.addBands -> ee.Image.pixelLonLat -> ee.Image.select -> ee.Image.pixelLonLat -> ee.Image.select -> ee.Date -> ee.Date.format -> ee.Number -> ee.Number.add -> ee.Join.saveAll -> ee.Join.apply -> ee.Number -> ee.Image.constant -> ee.Date -> ee.Filter.equals -> ee.Join.saveAll -> ee.Join.apply -> ee.Date -> ee.Image -> ee.Image.rename -> ee.Image.float -> ee.Image.constant -> ee.Reducer.linearRegression -> ee.List -> ee.Number -> ee.List.add -> ee.List -> ee.Date -> ee.Date.difference -> ee.Image -> ee.Image.rename -> ee.Image -> ee.Image.rename -> ee.Date -> ee.Date.millis -> ee.Image -> ee.Image.select -> ee.Image.multiply -> ee.Image.reduce -> ee.Image.rename -> ee.Image.addBands -> ee.Number -> ee.Number.divide -> ee.Image -> ee.Image -> ee.Image -> ee.Image.multiply -> ee.Image -> ee.Image.multiply -> ee.Image -> ee.Image.subtract -> ee.Image -> ee.Filter.equals -> ee.Join.saveAll -> ee.Join.apply -> ee.Image -> ee.Image.get -> ee.List -> ee.List.get -> ee.Image -> ee.Image.select -> ee.Image -> ee.Image -> ee.Image.get -> e…
```

### DIFF-9 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -50,2 +50,4 @@
 RASTER_LOAD
+THRESHOLD_LOGIC
+RASTER_LOAD
 BAND_SELECT
```

---

## DIFF-10  (J=0.7692 / suspicious / 第二批)

**owner 判读注记**：地理范围与分组字段（subregion vs continent）变化可能影响统计组织但不必然改变结构；MASKING 差异待核

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 2/2 行

### DIFF-10 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Human settlements；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **2 行**
- 粗链（19 步，游程显示）：`ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> MASKING -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> VECTOR_LOAD -> VECTOR_GEOMETRY -> VECTOR_LOAD -> VECTOR_GEOMETRY -> VECTOR_LOAD -> BAND_ARITHMETIC -> VECTOR_LOAD`

- **canonical**（632 字符，sha16 6d3d484fba8fa002，row script_36382）：
```
ee.Filter.neq -> ee.Filter.and -> ee.Filter.eq -> ee.Filter.or -> ee.Filter.eq -> ee.Filter.eq -> ee.FeatureCollection -> ee.FeatureCollection -> ee.Image -> ee.Image.float -> ee.Reducer.countEvery -> ee.Reducer.max -> ee.Image -> ee.Reducer.sum -> ee.Image -> ee.Image.mask -> ee.Image.pixelArea -> ee.Image.divide -> ee.Reducer.sum -> ee.Image -> ee.ErrorMargin -> ee.Number -> ee.Number.neq -> ee.FeatureCollection -> ee.FeatureCollection.geometry -> ee.FeatureCollection -> length -> ee.FeatureCollection -> divide -> ee.Number -> ee.List -> ee.List.length -> ee.List -> ee.List.length -> ee.List -> ee.List.length -> ee.Feature
```

### DIFF-10 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Environmental impacts；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **2 行**
- 粗链（18 步，游程显示）：`ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> MASKING -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> MASKING -> VECTOR_LOAD -> VECTOR_GEOMETRY -> VECTOR_LOAD -> VECTOR_GEOMETRY -> VECTOR_LOAD -> BAND_ARITHMETIC -> VECTOR_LOAD`

- **canonical**（619 字符，sha16 11d56d349d20283e，row script_36370）：
```
ee.Filter.neq -> ee.Filter.and -> ee.Filter.eq -> ee.Filter.or -> ee.Filter.eq -> ee.Filter.eq -> ee.FeatureCollection -> ee.FeatureCollection -> ee.Image -> ee.Image.float -> ee.Reducer.countEvery -> ee.Reducer.max -> ee.Reducer.sum -> ee.Image -> ee.Image.mask -> ee.Image.pixelArea -> ee.Image.divide -> ee.Reducer.sum -> ee.Image -> ee.Image.mask -> ee.Number -> ee.Number.neq -> ee.FeatureCollection -> ee.FeatureCollection.geometry -> ee.FeatureCollection -> length -> ee.FeatureCollection -> divide -> ee.Number -> ee.List -> ee.List.length -> ee.List -> ee.List.length -> ee.List -> ee.List.length -> ee.Feature
```

### DIFF-10 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -6,4 +6,2 @@
 RASTER_LOAD
-AGGREGATION
-RASTER_LOAD
 MASKING
@@ -12,2 +10,3 @@
 RASTER_LOAD
+MASKING
 VECTOR_LOAD
```

---

## DIFF-13  (J=0.8387 / conditional_accept / 第二批)

**owner 判读注记**：传感器（L5 vs L7）与时段变化影响筛选但不必改变插值/平滑核心流程；A 额外 VECTOR_LOAD 是否独立研究区加载待核

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 3/6 行

### DIFF-13 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Vegetation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **3 行**
- 粗链（15 步，游程显示）：`VECTOR_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> COMPOSITE -> BAND_SELECT -> ATTRIBUTE_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（493 字符，sha16 e874866b8dcf6c4b，row script_217889）：
```
ee.FeatureCollection -> ee.Filter.bounds -> ee.Filter.calendarRange -> ee.Reducer.mean -> ee.Image -> ee.ImageCollection -> ee.ImageCollection.toBands -> ee.Number -> ee.Number.format -> ee.Number -> ee.Image -> ee.List -> ee.ImageCollection.fromImages -> ee.ImageCollection.mosaic -> ee.List -> ee.ImageCollection.fromImages -> ee.ImageCollection.mosaic -> ee.Image.cat -> ee.Filter.eq -> ee.Reducer.mean -> ee.Number -> ee.Number -> ee.Number.subtract -> ee.Image.constant -> ee.Reducer.mean
```

### DIFF-13 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Vegetation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **6 行**
- 粗链（14 步，游程显示）：`SPATIAL_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> COMPOSITE -> BAND_SELECT -> ATTRIBUTE_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION`

- **canonical**（469 字符，sha16 1aafd66ae7da0709，row script_217879）：
```
ee.Filter.bounds -> ee.Filter.calendarRange -> ee.Reducer.mean -> ee.Image -> ee.ImageCollection -> ee.ImageCollection.toBands -> ee.Number -> ee.Number.format -> ee.Number -> ee.Image -> ee.List -> ee.ImageCollection.fromImages -> ee.ImageCollection.mosaic -> ee.List -> ee.ImageCollection.fromImages -> ee.ImageCollection.mosaic -> ee.Image.cat -> ee.Filter.eq -> ee.Reducer.mean -> ee.Number -> ee.Number -> ee.Number.subtract -> ee.Image.constant -> ee.Reducer.mean
```

### DIFF-13 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -1,2 +1 @@
-VECTOR_LOAD
 SPATIAL_FILTER
```

---

## DIFF-16  (J=0.7653 / suspicious / 第二批)

**owner 判读注记**：VECTOR_LOAD 与 ATTRIBUTE_FILTER 顺序互换；是否反映真实依赖关系待核（数据条件变化与步骤变化需分开）

**机械预观察**：双侧 canonical API 序列不同（程序确实不同）；模板支持 A/B = 15/10 行

### DIFF-16 臂 A
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Habitat conversion/fragmentation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **15 行**
- 粗链（12 步，游程显示）：`RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> EXPORT_OUTPUT -> RASTER_LOAD -> TEMPORAL_FILTER -> COMPOSITE -> RASTER_LOAD -> TEMPORAL_FILTER -> COMPOSITE`

- **canonical**（270 字符，sha16 7f1db0c840faa0e4，row script_187005）：
```
ee.Image -> ee.Feature -> ee.Image -> ee.Filter.equals -> ee.Image -> Export.image.toDrive -> ee.Image -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic
```

### DIFF-16 臂 B
- 匹配池行：1（canonical 形态 1 种，物化前 3 种）；task_type：Habitat conversion/fragmentation；run_cap：False
- 模板全局支持度：该 RLE 在池内出现 **10 行**
- 粗链（13 步，游程显示）：`RASTER_LOAD -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> EXPORT_OUTPUT -> RASTER_LOAD -> TEMPORAL_FILTER -> COMPOSITE -> RASTER_LOAD -> TEMPORAL_FILTER -> COMPOSITE`

- **canonical**（287 字符，sha16 b54295d7f9a5f858，row script_187007）：
```
ee.Image -> ee.Filter.lte -> ee.Feature -> ee.Image -> ee.Filter.equals -> ee.Image -> Export.image.toDrive -> ee.Image -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic -> ee.ImageCollection -> ee.ImageCollection.filterDate -> ee.ImageCollection.mosaic
```

### DIFF-16 粗链自动 diff（A→B，上下文 1）
```
--- 
+++ 
@@ -1,2 +1,3 @@
 RASTER_LOAD
+ATTRIBUTE_FILTER
 VECTOR_LOAD
```

---
