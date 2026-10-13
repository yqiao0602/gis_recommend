# 执行记录 v1：小规模验证启动

状态：LEDGER_FROZEN / BLIND_UNITS_READY / 盲标未开始
日期：2026-10-10
授权依据：owner 裁定（2026-10-10）——有条件批准启动小规模验证。

## 1. 已完成

1. **判定单位补齐**：`EXECUTION_CHECKLIST_JUDGMENT_UNITS_V1.md` 冻结。
2. **抽样框构建**：G0 SHA 复核一致（`09c37104…02a2`）；train split 101,232 行（缺源 281 如实记录）；清单 SHA `72d80c45…fc2`。
3. **全池扫描完成**：101,227 脚本全部扫描（11,863 s，缓存 `_pool_scan_cache_v1.jsonl`，解析失败 15 个按预注册规则记录不中断）。层命中分布：0 层 1,571 / 1 层 10,198 / 2 层 23,933 / 3 层 32,185 / 4 层 31,273 / 5 层 2,067。
4. **一次性账本冻结**：`sample_ledger_v1.json`（SHA `05af094d…5de`）。
   - L1–L5 每层 5（冻结规则：命中分降序、id 升序；五层为同 5 个脚本——全五层命中者的 id 最小者，池内全五层命中共 2,067 个，规则确定性结果）；
   - C 对照 10（零命中）；R 独立随机 10（Algorithm-R，seed 20261009）；
   - **去重脚本总数 25**；25/25 源码 SHA pin 核验一致。
   - ⚠️ 25 略低于 owner 预估带 30–60 下缘：原因是五层命中高度重叠（冻结规则下每层 top5 同为 5 个脚本）。账本已冻结不可改；**如需扩大 N 须 owner 另行裁定**（重开会改账本）。
5. **盲标单位清单生成**：`blind_annotation_units_v1.json`（SHA `14f9735b…a17`，**不含自动化结论**）：A1 判定单位 45、A2 676、A3 1,796（A4 待自动重建后按冻结 RNG 流补齐边对样本）；各检测器有效判定样本均远超 ≥10 门槛。

## 2. 封存

`automation_sealed_v1.json`（SHA `f34dd427…b8`，封存结论 SHA `91b32ba4…aeb`，open_event=null）：两名标注者**完成盲标并登记完成事件前不得开启**；开启时记录时间戳。

### 2a. 事故记录：陈旧并发进程覆盖账本（2026-10-10，已恢复并验证）

重构 `_assemble_ledger` 之前启动的旧抽样进程（`--execute` 全池实扫，含**重复 append 缺陷**：每脚本登记两次）在数小时后完成，把已冻结的 `sample_ledger_v1.json` 覆盖为损坏版本（available=202,454、每层选样重复、dedup=18、R 组漂移）。处置：

1. 缓存 `_pool_scan_cache_v1.jsonl` 与冻结规则未受影响；
2. 立即用 `--from-cache` 重新装配 → 恢复文件 SHA **逐字节一致**（`05af094d…5de`，与冻结记录及盲标清单内引用完全匹配）；哈希账本同步恢复一致；
3. 25/25 SHA pin 与盲标清单一致性复核通过；
4. 教训登记：后台长任务与冻结产物写入路径冲突——此后任何 `--execute` 全池实扫启动前必须确认无陈旧进程存活；冻结产物写入后应尽快移出可写路径或加只读保护。

**账本有效性不受影响**：冻结判定以 SHA `05af094d…5de` 为准。

## 3. 待办

1. **标注**：owner（标注者 1）依据 `annotator1_workspace_v1/` 标注单探索性标注（2518 判定单位 / 24 脚本）；第二名标注者到位后补双盲正式轮；
2. 双盲完成后开封对照 → `compute_expansion_metrics_v1.py` 按冻结口径计算 A1–A4 分列一致率与 C1–C4 指标；
3. 任一停止条件（S1–S4）触发 → 立即暂停提交复审；不自行扩大样本或转入全库。

## 3a. 自动重建完成（2026-10-10）

`scripts/run_auto_reconstruction_v1.py` → `auto_reconstruction_v1/`（25 脚本，汇总 SHA `f65f04bf…`）：

- **24 个 JS 脚本全部成功重建**：变量 3–92 个/脚本，数据流边 0–93 条/脚本（原始=去重：自动生成的边按构造无重复，A4 在本轮自动边集上无合并候选 → **A4 有效判定样本=0，将按清单规则报 `insufficient_sample`**，不补抽）；
- **外部候选 45 个** 全部以 `candidate_pending_human` 登记，零自动定性；未决项同源；
- **task_duty 全部 `pending_human_task_binding`**——任务语义标签不自动生成（这正是验证要测的人工对照部分）；
- **语料质量发现**：`script_10` 为 **Python QGIS 插件文件混入 GEE 语料**（解析失败、0 判定单位）→ 按 `not_judgeable` 从全部分母剔除并登记；账本保持冻结不改。

## 3b. 覆盖局限记录（owner 裁定 2026-10-10 落实）

`COVERAGE_LIMITATIONS_V1.md` 冻结：五层入选完全同批（全池 2,067 个五层命中脚本的 id 最小前 5）；25 脚本 = 5 复杂(5/5) + 8 复杂(3–4/5) + 2 混合 + 10 普通(全为 C 对照)；**独立随机组 10 个中 8 个命中 3–4 层困难特征**——困难特征在语料中是常态，真正零命中脚本仅占全池 1.6%；本轮结论仅适用于方法验证，不外推总体。

## 3c. 标注者裁定（owner 2026-10-10）

- 第二名标注者不得由检测器作者担任；owner 担任标注者 1（"我来吧"）；
- 第二人到位前为**单人探索性标注**：不得称双盲验证、不得宣称双标一致性；
- 标注纪律与流程见 `annotator1_workspace_v1/README_ANNOTATION_PROTOCOL.md`；
- 自动化结论**继续封存**（open_event=null）。

## 4. 边界（不变）

仅 25 新脚本（账本冻结数）；不改冻结试点产物；无全库重建；无 gold 认定；无训练/推理/RL；G0/G1/G2/G3、Blueprint、GATE_B、S3、locked test 冻结。

## 3d. 标注过程发现（标注者 1，script_7900 首标，2026-10-10；开封前登记）

- **F1 工作区设计缺陷**：标注单只给源码节选，未给完整源码路径，导致 A2 全局后继计数与函数调用核对无法最终落盘。修复：标注单补源码路径（机械修改，不含任何自动化结论）；本轮 A2 若干条目按规范保留 `undeterminable` 属正确行为，不视为标注失败。
- **F2 检测器作用域疑点（留待开封裁定）**：标注者指出 A2 若按文件级同名合并计数，会把不同函数中的同名形参（如 `image` 在多个函数中是不同绑定）错误合并。此为潜在 `detector_rule_defect`——**开封对照时**专项核对，现在不查看自动化输出。
- **F3 规则确认**：A1 自引用赋值只是线索、非外部来源充分证据（与冻结规则一致，确认无需修改）；函数名/形参须与数据变量区分标注；A3 按调用语句实际角色判定（与冻结规范一致）。

标注者 1 当前已给裁定：A1 genhe=indeterminable、landsat8=indeterminable（自引用线索待完整源码核实）；A2 逐变量表（多项诚实保留 undeterminable/待确认）；A3 逐行角色表（213/221=presentation、225=export、195=analysis+定义来源待核查）。

## 3e. 标注者 1 提交记录（batch 1，2026-10-10）

- **script_7900 A2 定稿已机械转录**（53/53 单位）：`annotation_results_v1_20261010T1608.jsonl`；状态分布 analysis_chain 47 / unconsumed 6；仅誊值，无任何添加判断；
- 两条保留区别逐字写入备注：`nbr`=analysis_chain 但"仅函数内部链，父函数未调用"（局部存在、全局不可达）；`landsat8` 的 A2 状态不代表 A1 来源问题已解决；
- **粒度冲突登记（留待 F2 开封裁定）**：文件级单位 `image`/`mask`/`img_plus_ic` 各合并多个作用域绑定（如 cloudMask 第 9 行 mask 与第 217 行 mask），标注者按作用域给出裁定值，文件级单位与作用域裁定的对照口径在开封时统一，不预改；
- 该脚本 A1（genhe/landsat8 三分类）与 A3（角色表）按标注者明确划分仍为待定项；
- 封存文件未开封（open_event=null）。

## 3f. 标注者 1 提交记录（batch 2，2026-10-10）

- **script_10021 A2+A3 定稿已机械转录**（A2 8/8、A3 20/20 单位）：标注者按行给 A3 角色（14 行），行内多个调用单位共享该行角色（机械扩展，已注明）；A2 状态分布 analysis_chain 5 / presentation_only 3；
- 标注者口径逐字保留：presentation_only = 变量结果只用于展示（生成该结果的计算本身属分析操作）；三种 NDVI 计算路径不因输入相同而合并；
- script_10021 无 A1 候选单位（与冻结单位清单一致）；
- 累计结果文件由模板+全部批次重建（transcribe_annotation_v1.py），旧批次文件清理，保留最新；
- 累计已填：script_7900 A2 53 + script_10021 A2/A3 28 + script_10 not_judgeable 预填；封存文件未开封。

## 3g. 标注者 1 提交记录（batch 3，2026-10-10）

- **script_10224 A2+A3 定稿已机械转录**（A2 11/11、A3 28/28 单位）：A2 analysis_chain 9 / presentation_only 2；
- 标注者自纠逐字保留：`dwImage` 直接引用口径 4→3（Map 展示链的衍生间接使用不计）；
- 标注者边界逐字保留：`dwRgb` 虽由 visualize() 生成但继续参与乘法调制 → analysis_chain；仅 `dwRgbHillshade` = presentation_only（中间渲染 ≠ 最终展示用途）；
- **首个混合角色行**：第 33 行（.select/.visualize/.divide 链）标注者按调用分别裁定（analysis/presentation/analysis）——单位身份经源码 AST 机械解析（sealed 未开封），A3 单位级与行级的口径差异首次实测；
- A1 交叉验证：标注者判"无未声明候选变量"，与冻结单位清单（A1=0）一致；
- 累计：A2 72 + A3 48 已填，封存未开封。

## 3h. 标注者 1 提交记录（batch 4，2026-10-10）

- **script_25214 A2+A3 定稿已机械转录**（A2 7/7、A3 18/18 单位）：A2 analysis_chain 6 / presentation_only 1；
- NDVI1/NDVI2 口径保留：虽参与地图展示但同时进入 NDVImultitemporal 构建 → analysis_chain（与 batch 3 的 dwRgb 边界一致：中间用途 vs 最终展示分层）；
- **标注者记录疑似源码缺陷**：`NDVI1.addBands(NDVI1).addBands(NDVI2)` 将 NDVI1 添加两次（可能重复引用错误，不影响使用状态判定）——已入备注，供重建阶段冲突/缺陷登记对照；
- A1 交叉验证：标注者判无未声明候选，与冻结清单（A1=0）一致（第 3 个脚本一致）；
- 累计：A2 79 + A3 66 已填，封存未开封。

## 3i. 标注者 1 提交记录（batch 5，2026-10-10）

- **script_35821 A1+A2+A3 定稿已机械转录**（A1 1/1、A2 48/48、A3 133/133 单位）；
- **首个 A1 三分类判定**：geometry = external_prebinding，备注逐字保留"疑似 Code Editor 平台预绑定；源码内无显式证据（若规程要求源码内证据则应改判 indeterminable）"——该备注将在开封对照时作为标注者对自身裁定证据等级的自觉声明进入分歧归因；
- **首个可达性敏感 A2 判定**：illuminationCorrection = unconsumed 但后继使用数=1（唯一使用位于未被调用的 terrainCorrection 函数体内）——四类体系在"局部有引用、全局不可达"处的张力正式出现（呼应 F2 与 batch 1 的 nbr 判例）；
- 标注者三处结构问题标记逐字保留（terrainCorrection 未被主流程调用 / 5 个典型未使用定义 / SCSc_output 疑似返回值缺陷建议单独审计）；
- 标注者结论保留：实际主流程 = Landsat 筛选→云掩膜→重命名→中位数合成→展示/导出；地形照明校正不在实际执行链；
- collection 计数口径保留开放（6，取决于赋值左值是否计入）；
- 累计：A1 1 + A2 127 + A3 199 已填，封存未开封。

## 3j. 标注者 1 提交记录（batch 6，2026-10-10）

- **script_45485 A1+A2+A3 定稿已机械转录**（A1 3/3、A2 16/16、A3 43/43 单位）；
- **A1 三项判例**（预绑定判定的证据梯度样本）：MCD12Q2_2003_Full=indeterminable（仅命名）/ Lai_Global…=external_prebinding（多行使用+地图展示，附"严格口径应改判 indeterminable"自觉声明）/ Alashanzuoqi…=indeterminable（仅 Map.addLayer）；标注者口径建议逐字保留：不因出现在 Map.addLayer 就认定平台预绑定；
- **计数口径统一裁定（本批起采用，将写入开封对照规则）**：return 计为一次后继使用；定义表达式内操作不计入。Image_2003 按新口径=1/analysis_chain（原注保留）；lai_2003_raw=2；
- 注释代码不计实际使用（QA/bitMask_Dormancy_1 的 unconsumed 依据）；
- 补充审计备注逐字保留（QA 掩膜被注释、两条实际主链、无显式导出）；
- 累计：A1 4 + A2 143 + A3 242 已填，封存未开封。

## 3k. 标注者 1 提交记录（batch 7，2026-10-10）

- **script_100110（5/5 困难层脚本）A1+A2+A3 定稿已机械转录**（A1 2/2、A2 58/58、A3 77/77 单位）；
- **A1 模块形态判例**：LandsatLST（命名空间式调用）与 cloudmask（模块接口回调）均判 external_prebinding，均附"无 require 显式证据，严格口径应改判 indeterminable"自觉声明；两项均明确**不建议 missing_definition**——外部模块 vs 缺失定义的区分判例；
- **A2 语义判例**：emptyImage 三处 var 重复赋值 = 同一变量（var 函数作用域语义），3 次 paint 引用合并计数；landsatTOAcloudmask 有 1 次别名赋值但别名链无下游 → unconsumed（引用事实保留在备注）；
- A3 大量 console 调试输出（125/181/183/185 行）判 presentation；getInfo() 判 analysis（统计行构造，不属导出）；脚本无显式 Export；
- 标注者五条额外注意事项逐字保留（外部依赖证据、LandsatColl 主链、反照率分支未接入、无导出、getInfo 阻塞性说明）；
- 累计：A1 6 + A2 201 + A3 319 已填（约八分之一进度），封存未开封。

## 3l. 标注者 1 提交记录（batch 8，2026-10-10）

- **script_100133 A1+A2+A3 定稿已机械转录**（A1 6/6、A2 65/66、A3 85/85 单位）；
- **A1 全 indeterminable 判例**：6 个候选全部 indeterminable——与 script_100110（同类模块形态判 external_prebinding）形成**跨样本口径张力**，标注者自己给出统一说明（可能来自 Imports 但无法证实；若项目有经核实的 Imports 统一规则应一致调整）——此为开封时 A1 一致率计算的最大分歧风险点，两条判例组已并列登记；
- **首个 A3 unknown 判定**：第 157 行 require('users/...legend') 标注者判 unknown（非 presentation/export/analysis）——自动化分类器将其归 import（预注册表），这是预注册分类表 vs 标注体系的直接对照点；
- **A2 标注者自纠**：AQrange 原稿误写 presentation_chain，更正为 presentation_only（转录按更正值）；
- **chartPanel 覆盖判例**：第 447/509 行重复声明，var 语义下第二次覆盖第一次——第一个箱线图面板实际不可见；与 script_100110 emptyImage 判例同构但结论更细（覆盖导致的部分不可达）；
- 同名作用域区分继续：image（25 行 vs 41 行回调）、chart（369 局部 vs 473 全局）——文件级单位合并的 F2 问题第三、四次实证；
- **转录缺口（待标注者补定）**：模板 A2 单位 AQlgnd 在标注表中无对应行，保持未填；
- 累计：A1 12 + A2 266 + A3 404 已填，封存未开封。

## 3m. 标注者 1 提交记录（batch 9，2026-10-10）

- **script_100145 A1+A2+A3 定稿已机械转录**（A1 15/15、A2 30/30、A3 146/146 单位，与模板全对齐）；
- **A1 最大批次全 indeterminable**：15 个候选（GHSL/AUE/Kigali 系列数据对象）——证据不足一致口径，与 batch 8 的 6 项同构；标注者总体判断保留（能证明未声明，不足以区分预绑定 vs 定义遗漏；取得导入区/元数据后可复核）；
- **同名覆盖+自引用判例组**（此前最复杂的一份）：GHSLbud 自引用风险（var GHSLbud = visfilter(GHSLbud) 右侧读当前绑定值）、GHSLueyear 分支来源差异、GHSL2023releaseYear/GHSLyear 反复覆盖——五条特别注意事项逐字保留；
- 死代码判例延续：BU/BU_GHSL/BU_DW/wsf_evoImg 构造后未消费（不因含分析操作判入分析链）；
- 展示链判例：GHSLyear/GHSLbud/GHSLueyear 涉及影像运算但最终用途为 Map.addLayer → presentation_only（中间用途 vs 最终展示口径的又一次应用）；
- A3 无 Export；全部 Map.addLayer=presentation、数据处理=analysis，与既有口径一致；
- 累计：A1 27 + A2 296 + A3 550 已填；封存未开封。剩余脚本：14 个 JS + 待补项（script_7900 A1/A3、script_100133 AQlgnd）。

## 3n. 标注者 1 提交记录（batch 10，2026-10-10）

- **script_100870 A1+A2+A3 定稿已机械转录**（A1 1/1、A2 15/15、A3 60/60 单位——标注者按 38 行给角色，行内多调用单位共享行角色，与模板全对齐）；
- **三处标注者自纠（1→4）**：collTOres_im / collTOres_im_mean / mean_cur 在四个重复统计区块中按区块累计——**重复区块累计口径**首次显式化（模板单位是文件级绑定，四区块累计与自动化 A2 的文件级计数预期一致，是开封时的高价值一致样本）；
- 两条审计备注逐字保留：collTOres 重复赋值覆盖（图表实际用 Rrs_412 集合而非前三个变量对应集合）；image.divide(1).select([0],['l3smi']) 仅重命名——数据实为 Rrs_412（名称≠数据来源，重建阶段冲突登记的典型素材）；
- 回调形参判例：xValue=analysis_chain（用于过滤构建）vs yValue/seriesName=unconsumed（未使用）——同一回调内逐参数区分；
- 累计：A1 28 + A2 311 + A3 588 已填；封存未开封。

## 3o. 标注者 1 提交记录（batch 11+12，2026-10-10）

- **script_100916（对照）A2+A3 已转录**（A2 6/6、A3 14 单位/6 行）；A1 交叉验证：无候选（mapVis 已定义），与冻结清单一致；
- **script_101051（对照）A2+A3 已转录**（A2 3/3、A3 16 单位/11 行）；A1 交叉验证一致；
- 图表链判例（两脚本互证）：100916 datasetTRUECs2=print+addLayer→presentation_only；101051 regions/temps2013 参与统计计算→analysis_chain、仅最终图表变量=presentation_only——"参与计算→analysis / 只被展示→presentation"口径稳定应用；
- 混合用途判例：DayStart 兼分析参数与展示标签，主状态取 analysis_chain（主用途优先）；
- 标注者审计备注保留：100916 图层标签 SENTINEL-1 ≠ 数据源 S2_SR（命名不一致，重建冲突登记素材）；101051 的 B11 与历史数据集匹配性需另行核验；
- 累计：A1 28 + A2 320 + A3 640 已填；封存未开封。

## 3p. 标注者 1 提交记录（batch 13+14，2026-10-10）

- **script_101095（对照）A2+A3 已转录**（A2 11/11、A3 36 单位/22 行）；A1 交叉验证一致（无候选）；
- **script_101218（对照）A2+A3 已转录**（A2 15/15、A3 26 单位/15 行）；A1 交叉验证一致；
- 最终消费判例延续：descChange/ascChange 虽入分析链但仅用于地图显示 → presentation_only；L8IC 仅 print → presentation_only；
- **名称≠语义判例（第二例）**：ee.Image.cat() 合并三时段均值 ≠ 计算 Change 差分——图层名 'Change' 不代表实际计算（与 100870 的 l3smi 重命名判例同构）；
- **同一调用不重复计数判例**：imagen 的 return imagen.mask(mask) 中 mask 接收对象与调用为同一处，严格计数 3；
- **定义表达式内链式调用不计后继判例**：BA 的 filterMetadata/geometry(200) 属定义表达式，不计（与 batch 6 的 lai_2003_raw 口径一致）；
- 累计：A1 28 + A2 346 + A3 699 已填；封存未开封。

## 3q. 标注者 1 提交记录（batch 15+16，2026-10-10）

- **script_101353（5/5 困难层）A1+A2+A3 已转录**（A1 1/1、A2 20/20、A3 182 单位/107 行，零缺口）；
- **A1 跨样本对照（第二组 geometry 判例）**：35821 geometry=external_prebinding（多行使用+定位）vs 101353 geometry=indeterminable（12 次 clip 但无来源证据）——标注者逐样本独立裁定，两判例并列登记，构成 A1 证据梯度的完整光谱；
- **A2 五处计数自纠**：map1 7→6、map7–map12 各 4→5；modis_chlor_a 的双口径注明（各区块 1 vs 同绑定合并 12）——模板单位为文件级绑定，**计数口径留待开封统一**（直接对照 emptyImage 判例与自动化文件级计数）；
- linker 判例：构造函数参数不计后继使用 → unconsumed；
- **A3 异质脚本**：107 行中 analysis 仅 38 行（12 个月重复区块的 ImageCollection/filter）+1 处 pixelLonLat（图例色带流程中的影像操作仍判 analysis——API 自身角色不被消费场景改变）；
- **script_102167（对照）已转录**（A2 5/5、A3 13 单位/8 行）；Brazil 标注者自纠 presentation_only→analysis_chain（进入 filterBounds 影像筛选）；
- 累计：A1 29 + A2 371 + A3 894 已填；封存未开封。

## 3r. 标注者 1 提交记录（batch 17–21，2026-10-10）

- **script_102466 + script_102794（对照，同源重复）已转录**（各 47 单位零缺口）：**语料质量发现——两脚本字节级相同（SHA 一致）且同入 C 对照组**，账本冻结保留，重复事实登记；
- **script_116725（R 组）已转录**（A1 2/2、A2 29/29、A3 57/57）：A1 limit/l8_col 均 indeterminable；cloudScore=unconsumed（定义未调用，与 35821 terrainCorrection 判例同构）但 rescale 记 4/analysis_chain（按引用计数）——**可达性与引用计数分层判例再现**；
- **script_184426（R 组）已转录**（A2 24/24、A3 44/44）：三处计数自纠（recent 3→2、list 3→2、anomalies 口径澄清）；本组**首个含显式导出**的 R 组脚本（Export.image.toDrive→export 行）；标注者补充 vis 未在模板清单（模板无该单位，仅登记）；
- **script_191158（R 组，最大）已转录**（A2 92/92、A3 299 单位/158 行，全对齐）：repeat-var 判例（lagged34/merged34 按后一次定义行统计）；lagBand 全局变量 vs 函数同名形参分开；**第 327 行疑似变量使用错误**（标签 lag=30 实传 cov1PrecipNDVI）——重建冲突登记素材第三例；
- 累计：**A1 31 + A2 538 + A3 1366** 已填（约四分之三判定单位）；封存未开封。
- **剩余仅 3 个 JS 脚本**：script_216850 / script_217669 / script_271544（均为 R 组）；另待补项 2 处（script_7900 的 A1/A3、script_100133 的 AQlgnd）。

## 3s. 标注者 1 提交记录（batch 22–24，2026-10-10）——24/24 JS 脚本主体完成

- **script_216850（困难层 5/5）已转录**（A1 9/9、A2 47/47、A3 153/153）：A1 九项全 indeterminable；11 处计数核算更正按更正值转录（img=4/image=1/filtered=9 等）；trainAccuracy/testAccuracy/Area_Sqm/final_table/classAreas/S1Layer 等 8 项 unconsumed（保存后未用的中间审计量）；
- **script_217669（R 组）已转录**（A2 64/64、A3 83/83）：**require 跨样本口径差正式登记**——217669 两处 require 判 presentation vs 100133 一处 require 判 unknown，开封时按 annotator_criteria_divergence 候选核对（两条均为标注者明确裁定，如实转录）；对象放入返回面板但变量名不再引用（colorBox/description）→ unconsumed 判例；
- **script_271544（R 组）已转录**（A1 3/3、A2 26/26、A3 52/52）：标注者四条源码问题备注逐字保留（karnataka/Ukraine 命名不一致、回调参数 i 实为要素、回调内 var img 遮蔽外部 img 致 reduceRegion 统计常量影像、covGrid 无 return）——遮蔽判例是 F2 作用域问题的最强实证；
- **24/24 JS 脚本标注主体完成**：A1 43 + A2 675 + A3 1654 （JS 判定单位合计 2517，已填 2372）；
- **待补清单（145 项）**：script_7900 A1 两项 + A3 全部（~142）；script_100133 AQlgnd 一项。
- 封存文件未开封（open_event=null）。

## 3t. 标注者 1 提交记录（batch 25–26 终稿，2026-10-10）——标注阶段完成

- **script_7900 A1+A3 终稿已转录**（A1 2/2、A3 142 单位/65 行全对齐）：genhe/landsat8 维持 indeterminable（自引用是风险线索不是充分证据）；A3 全行裁定（213/221=presentation、225=export、其余全 analysis，无待核查项遗留）；
- **script_100133 修订稿（supersedes batch 8）已转录**（A2 66/66 含 AQlgnd 补标、A3 85/85）：
  - require@157: unknown → **presentation**（导入图例 UI 工具）——batch 8 的 A3_UNKNOWN 条目移除；至此 require 判例三向齐全（presentation/unknown），开封时作口径核对样本；
  - A2 十四项由 presentation_only 改 **analysis_chain**（CLASSES/colors/Ppctfills/Afills/AOIimage/getTheChart 七参/maxValue/maxMedian/myRows/i/stats）——"传入图表/图例构建即参与计算"口径的显式化；
  - 计数修订: collection 3→2、maxMedian 4→3、stats 12→10；empty/chartPanel 保留文件级合并值（4/3）+分行裁定备注；
- **标注阶段闭环**：2517/2517 判定单位填满（A1 45、A2 676、A3 1796）+ script_10 not_judgeable 预填；结果文件 annotation_results_v1_20261010T1716.jsonl；
- 待办：标注者 1 提交归档（带时间戳+SHA）→ 开封对照（须记录开封时间戳，自动化结论才可比对）→ compute_expansion_metrics_v1.py 指标计算 → 报告。

## 4. 开封与对照（2026-10-10，owner 裁定单人终轮后执行）

- **开封**：17:21:40，结论 SHA `91b32ba4…` 开封前后一致验证通过，open_event 已记录（owner 裁定：单人自行复核终轮，无第二名标注者，保留非双盲限制）；
- **对照执行**：`compute_expansion_metrics_v1.py` → `expansion_metrics_v1.json`（795 条分歧台账）+ `EXPANSION_METRICS_REPORT_V1.md`；
- **结果**：A1 候选集 100%（45=45）；A2 状态 606/676=89.6%（计数精确 86.4%）；A3 1071/1792=59.8%（721 项分歧 100% 机械化归因：591 嵌套链路径缺陷+26 ui/console 兜底缺陷+14 未声明根级联+90 人工行级粒度，零真实边界残留）；A4 insufficient_sample；C1 不可计算；C3=0；
- **A2 分歧定性**：53 项为标注者跨样本口径漂移（100110 vs 100133 同构变量反向），4 项可达性口径差，3 项作用域粒度；
- **S3 判读**：A3 名义一致率 <80%，但分歧全部可归因——按冻结口径本报告即复审材料，检测器修复与否待 owner 裁定；本轮未改任何检测器；
- 口径限制：全部数值为单人探索性，不称双盲。

## 5. A3 检测器修复轮（2026-10-10，owner 裁定后执行完毕）

- **阶段 A 基线冻结**：`a3_fix_round_v1/baseline/`（检测器 v1/封存输出/基线指标/人工标注/报告，SHA 清单 BASELINE_MANIFEST.json）；
- **阶段 B 修复**：三项缺陷分别修复（嵌套链 fallback / ui-console 全路径 / A1 根方法分类），预注册增补 NESTED_PRESENTATION_METHODS 与 GEE_DATA_METHODS 两表；新增回归测试 6 项（WP-A 19/19 通过）；原 23 项测试无回归；
- **阶段 C 原样复测**（人工标签冻结、样本不变、单元对齐校验通过）：**严格一致率 59.77% → 92.02%（1649/1792）**；1071 个原一致样本 **0 回归**；归一化（排除 90 行级粒度单位）96.89%；
- **阶段 D 残余审计**：143 项残余**全部**为行级裁定粒度产物（134 presentation 行内嵌套 analysis + 1 export 行内嵌套 + 8 行级单位上的 kept-unknown）；**逐调用裁定单位残余 = 0；真实语义错误 = 0**；unknown 保留 8 处（规则允许）；
- A2 53 项跨样本漂移已按 owner 要求登记为标注规范一致性问题（不改旧标签，规范附则见修复轮报告）；
- A1/A2/A4 裁定维持不变；全部数值为单人探索性口径。
- 修复轮报告：`a3_fix_round_v1/A3_FIX_ROUND_REPORT_V1.md`。

## 6. A3 v1.1 冻结 + A2 复审启动（2026-10-10，owner 裁定四步计划）

- **第 1 步 A3 v1.1 冻结**：`a3_v1_1_freeze/`（detector_v1_1、1796 项逐项预测、测试记录、三档指标、143 项残余清单、FREEZE_MANIFEST）；状态=工程验收通过/探索性对照通过/未经独立验证；主指标=92.02% 严格口径，96.89%/100% 为敏感性分析；不再启动第三轮修复；
- **第 2 步 A2 复审启动**：`a2_review/A2_ADJUDICATION_TABLE_V1.jsonl`——676 单位中 **146 项分歧**逐项入表（54 纯状态 / 76 纯计数 / 16 双重；含此前指标台账未覆盖的纯计数分歧）；四类归因：图表参数族边界 27 / 计数口径或作用域 102 / 可达性两层 5 / repeat_var 绑定计数 12；每项含建议处理方案（PROPOSAL），decision 列留空待裁定，**旧标签未改动**；
- **第 3 步协议草案**：`EVALUATION_PROTOCOL_DRAFT_V0.md`（候选级/变量级/调用级/行级四层定义 + 八条固定规则 + 指标报告规范 + 4 个待审定点）；
- **第 4 步独立验证**：按 owner 裁定留待后续（若检测器性能入论文核心结论，规则冻结后引入独立标注者或分层独立复核）；
- 阶段性判断（owner 四条）已登记：A1 暂时通过（missing_definition 无正例，零漏检不可外推）、A2 复审中、A3 工程验收通过（行级/调用级分开呈现）、A4 insufficient_sample 不补造结论。

## 7. A2 复审裁定回填（2026-10-10，owner 两批裁定）

- **协议修订 v0.1**（`EVALUATION_PROTOCOL_DRAFT_V0_1.md`）：§2.6 改为按实际语义用途分类（禁"被 UI 函数消费⇒analysis"一刀切）；§2.2 增补同名形参不跨函数合并条款；§2.5 可达性两层正式采纳（globally_reachable 为静态近似）；新增七条统一裁定规则；总原则=状态与计数分别裁定、人工标签为待裁定基准；**仍为 DRAFT**，冻结前置=146 项复审全部写入+计数核对完成，冻结前不发布新 A2 一致率；
- **裁定回填**：`apply_a2_decisions_v1.py` → `a2_review/A2_ADJUDICATION_TABLE_V1_1.jsonl`（全 676 单位）。**83 项已裁定**：accept_human 35 / reject_proposed_resolution 9（含 owner 点名 BACKGROUND 保留 presentation_only）/ accept_human_scope 9 / needs_source_audit 26 / needs_scope_audit 2 / correct_count 2（score 6→5、illuminationCorrection 附 globally_reachable=false 并修正 batch-5 的 unconsumed 状态）；旧标签修改标记 1 项（illuminationCorrection），改动队列待未来标注修订统一执行；
- **待决 63 项**：100110/100133 图表参数族为主（收紧版 §2.6 规则的适用对象），另有 100145 GHSL 系、100870 重复区块、7900 少数计数项——按 owner 指示须回到源码逐项核验后才锁定；
- 协议冻结前**未发布**任何新 A2 一致率数字（遵守冻结前置条件）。

## 8. A2 复审第三批裁定 + 源码审计包（2026-10-10）

- **第三批 63 项全部裁定**（`apply_a2_decisions_v1_2.py` → `A2_ADJUDICATION_TABLE_V1_2.jsonl`）：**146/146 全量有 decision，pending=0**。累计分布：accept_human 67 / needs_source_audit 45 / reject_proposed_resolution 15 / accept_human_scope 14 / needs_scope_audit 3 / correct_count 2；
- 本批人工标签修订 10 项（含 collTOres_im_mean analysis_chain→presentation_only、100110 图表参数族 data/xVals/xField/yField→analysis_chain 等），全部带 basis 入表，改动队列待未来标注修订统一执行；GHSLbud/GHSLueyear 按裁定暂定 analysis_chain、源码确认前不锁旧标签；
- **源码审计包生成**（`generate_a2_source_audit_packet_v1.py` → `A2_SOURCE_AUDIT_PACKET_V1.json/.md`）：45 项 needs_source_audit 逐项列出定义位置+全部标识符出现位置（行号/父节点/行文本），附判定规则（定义表达式内不计、左值不计、同调用接收对象不重复、return 计 1）；
- 下一步：owner 依审计包逐项锁定 45 项计数 → 全部回填后按 v0.1 协议冻结条件出正式协议版本与 A2 复审结论（仍不提前发布一致率）。

## 9. 计数锁定批次（2026-10-10，owner 审计包批复后执行）

- **43 项计数锁定**回填 V1_3（`A2_ADJUDICATION_TABLE_V1_3.jsonl`）：每项保留 original_uses / final_uses / count_revision / status_locked 四字段；其中 40 项最终计数与原人工计数不同（多为 needs_source_audit 原未计数项）；
- **三项特殊核验完成**（`A2_COUNT_LOCK_EVIDENCE_V1.json`）：
  1. **217669:rescaled 采集器完整性**：regex 交叉核验仅多出 L191 声明行（AST 正确排除声明）→ 采集器完整，final=1 锁定；
  2. **217669 blank→outline 下游**：outline 仅被 L179 Map.addLayer 消费 → blank 展示定性证据齐，待 owner 锁定；
  3. **100145:year 绑定级审计**：5 处 var 声明（L113/129/145/163/191）全在顶层 → **同一全局绑定**；29 处读取（含 2 处闭包引用，无形参遮蔽，无裸赋值左值）→ 按冻结规则静态计数=29（证据支持 29 非 human 11），最终数待 owner 确认；
- **unconsumed 协议条款草案**已入证据册（unconsumed:=零有效后继引用，纯静态；下游链断头归 globally_reachable/downstream_effective 层）——待 owner 批准写入 v0.2；
- 开放项余 3 类：year 最终数确认、landsatTOAcloudmask 状态（待条款批准）、maxValue/maxMedian/myRows/blank 状态确认（证据已供）。

## 10. A2 收尾总清单（2026-10-10，owner 指示回主线、停止逐变量展开）

- 101095:image 当场核清（审计包 3 处，同调用接收对象不重复 → final=3，human 4 系重复计 L15 接收对象）；
- 收尾总清单 `a2_review/A2_CLOSEOUT_CHECKLIST_V1.md`：A=已确认 630（530 一致+100 分歧无修订）；B=修订队列 47（状态 11+计数 41，重叠 5）待机械应用；C=一次批准即可锁定 5 项（year=29、101095:image=3、landsatTOAcloudmask 条款、maxValue/maxMedian、myRows/blank——证据全齐）；D=批准后机械序列（annotation_results_v2 → 协议 v1.0 → 复核后一致率 → A2 结论 → 回主线）；
- A2 在批准 C 表 5 项后即收尾；不再扩展讨论范围。

## 11. A2 关闭（2026-10-10，owner 五项批复后机械收尾完成）

- V1_4 终表 + **annotation_results_v2**（50 单位修订；v1 归档 SHA 5dbb4308 未动；v2 SHA d3fca732）；
- **协议 v1.0 冻结**（`EVALUATION_PROTOCOL_V1_0_FROZEN.md`：unconsumed 纯静态定义、语义用途分类、绑定计数、两层可达性、指标规范）；
- **复核后 A2 指标（首次发布）**：状态 606/676=89.64%（复审带，全部分歧归因）；计数 623/676=92.16%（达标）；
- 剩余 70 项状态分歧归入三个已命名错误族：F-A UI/图表消费对象语义用途（检测器 ui.* fallback 局限）、F-B presentation 调用内统计输入（检测器无法识别调用内统计语义）、F-C 可达性两层/pre-v1.0 unconsumed 定义——**按 owner 裁定不再修复，本报告即未来修复规格**；
- **A2 复审关闭**。A1 暂时通过 / A3 v1.1 冻结 92.02% / A4 insufficient_sample 维持。回到毕设主线。

## 12. 主线衔接：冻结数据集抽取缺陷影响分析（2026-10-10，owner 立项）

- 报告：`docs/reports/gee_frozen_data_impact_v1/GEE_FROZEN_DATA_IMPACT_ANALYSIS_V1.md`（只读；本地代理 04_DIAG_WORK/b1_gee_stage_train.jsonl 与冻结数据 SHA 一致）；
- **F-A/F-B 零污染（实证）**：生产抽取器显式 presentation 前缀分类；20k 行扫描语义词表恰 30 类无展示类目；canonical 链 Map./ui./print 计数全 0；初筛命中为 OTHER_UNMAPPED 假阳性；
- **F-C 量级**：未消费变量占比 69/676=10.2%（0–37.5%），死分支 token 按设计存在于冻结链——非检测器缺陷，为 G0 设计属性；危害属实证训练问题；
- 重构决策框架已列三选项，当前推荐 (a) 不重构（先跑主线实验）；备选 (b) 用 v1.1 A2 检测器做 dead-branch 过滤的 25 脚本试点重抽。**待 owner 裁定**。

## 13. 影响分析裁定 (a)——审计工作流全线关闭（2026-10-10）

- owner 裁定 **(a) 不重构**：GEE 冻结数据保持不变（快照 SHA 09c37104…02a2），暂不重抽/不做清洗版本，回到 Stage-1/Planner 冻结实验状态；报告 SHA 已锁定于报告 §6；
- 触发条件登记：若模型错误分析表明未消费调用与任务分解错误相关 → 另行设计独立数据版本过滤对照实验（不覆盖基线）；
- **审计工作流（A1–A4 + 影响分析）全线关闭**。回主线。

- 主线续接状态已汇编入 `docs/CURRENT_STATE.md` §(0) 与 `task_plan.md`：待办=①P0 unified dev evaluation（eaed795e 训练已入账、评测未跑）；②Current Best Model Audit（e21b5e47 协议冻结：dev-120 processes+links 统一推理，route2_C0 同机复算强制，7 候选）——均在租卡机，launch 顺序与放行归 owner。
