# B1-PRE-QC 50 条放行判定

日期：2026-09-17
对象：`outputs_v2/gee_b1_stage_data_v1/b1_pre_qc_50.jsonl`（random 20 / long 10 / cap3 触发 10 / diversity 10，seed 20260917）
判定人：模型预审 + owner 复核
问题（owner 三问）：① 任务→语义链是否成立？② RLE 是否只删重复实现？③ cap3 是否误把模板循环当噪声？

---

## 结论：**PASS（附 2 项如实记录的观察，不阻塞放行）**

### 三问逐项回答

**① 任务 → 语义链成立（50/50 通过）**

抽验全部行的语义链与 instruction 描述的处理逻辑一致：
- 火山地表温度（Landsat8 TIR B10）→ `RASTER_LOAD→TEMPORAL_FILTER→AGGREGATION` ✓
- Zimbabwe 森林变化分类（多时相合成+分类）→ `RASTER_LOAD→TEMPORAL_FILTER→COMPOSITE→VECTOR_LOAD→CLASSIFICATION→BAND_ARITHMETIC→AGGREGATION` ✓
- 火烧迹地（Sentinel-2 前后对比）→ `VECTOR_LOAD→RASTER_LOAD→SPATIAL_FILTER→TEMPORAL_FILTER→ATTRIBUTE_FILTER` ✓
- ERA5 气候变量年度统计 → `RASTER_LOAD→TEMPORAL_FILTER→ATTRIBUTE_FILTER→BAND_SELECT→AGGREGATION`（×多变量，未折叠——正确，不同变量的处理是真实结构）✓

**② RLE 只删重复实现，未删真实步骤**

- script_71198：`AGGREGATION×4`（同一分类的多次统计调用）→ 折为 1，语义不变 ✓
- script_8（Milwaukee 分类）：`RASTER_LOAD×2→1`（NAIP 两景加载）——多实例加载折叠，符合"学 reasoning 不学实例数"的设计意图 ✓
- 反例确认保护生效：script_23（ERA5 多变量）raw 148 = final 148，**RLE 没有跨变量折叠**（不同变量各自的结构都保留）✓

**③ cap3 折叠的是模板展开，不是真实工作流（有一例需要如实说明）**

- script_98030（森林变化）：GEE 证据链显示 `calendarRange→simpleComposite` ×3 周期——是**三个年份的同一处理**，折为一个周期。这正是你说的 `A(影像1)→B(影像1)→A(影像2)→B(影像2)` 情形：类别序列相同、实例不同。**判定：保留折叠**——B1 学的是"任务→处理模式"，年份迭代属于实例维度；且 GEE 证据链完整保留在行内可审计。
- script_130042（FVC）：`RASTER_LOAD→TEMPORAL_FILTER→SPATIAL_FILTER→COLLECTION_MGMT` ×3——同一年度处理跨多个年份/传感器，同上判定 ✓
- script_107364（海洋栖息地）：`THRESHOLD_LOGIC×6`（对 6 个环境变量分别重分类）→ 折为 1。语义上"对多个变量做阈值重分类"的模式保留，变量数是实例维度 ✓

### 两项如实记录的观察（不阻塞）

1. **cap3 的"多实例折叠"是设计选择而非无损**：owner 已在裁定中预判此情形（"语义类别序列相同≠workflow 结构等价"），本 QC 实测此类行占 cap 触发行的主体。判定依据是"B1 目标=学 reasoning 模式而非恢复实例"，若第二轮要恢复实例信息，可在 target 前缀加重复计数（`THRESHOLD_LOGIC×6`），一行改动，不动数据。
2. **长链层（raw>100）的语义链仍有 74-148 长**（多变量/多阶段真实复杂工作流），p90=26 是全量口径。训练时 max_target_len 截断策略会切掉超长尾部——需要在训练脚本里统计截断率并记录，不静默。

### QC 记录

- 随机 20：全部通过（含 3 条 capped）
- 长链 10：全部通过（结构保留、无 RLE 误折）
- cap3 触发 10：全部通过（折叠对象均为周期模板/多实例迭代，GEE 证据链在行内）
- 多样性 10：10 个任务类型全通过

**放行。按执行链进入三臂训练脚本实现（GPU 不启动，等 owner 确认）。**
