# QGIS 全量漏斗审计 v1：47,852 → 训练数据的精确淘汰账

Date: 2026-09-14

回答的问题：**"是真的没有训练数据，还是当时的数据生产 pipeline 太保守？"**

口径说明：本审计以 **47,852 source authority**（8,466 Processing + 39,386 API，
爬虫池去重后）为基数。DAPT 工作流引用的 54,240 原始脚本 / 26.3M token 是
去重前口径，与本文相容但不由本文背书。

---

## 1. 完整漏斗（全部数字来自已核验报告）

```
47,852 source authority（去重后）
│
├─【完整性硬损 338（0.7%）】310 缺失 + 28 不可解析 —— 不可回收
│
├─【角色层 source_role_census_v2】
│   user_workflow 2,209 │ implementation 1,012 │ api_semantic 9,028
│   api_plumbing 11,655 │ unclassified 23,638 │ missing 310
│
├─【价值层 source_role_tiers_v1】
│   tier1 多步 workflow 169 │ tier2 单算子 325 │ tier3 实现 983
│   api_semantic 4,737 │ plumbing 11,655 │ unclassified 29,673 │ missing 310
│
├─【SFT-workflow 通道（Processing 455 队列）】
│   455 → 结构候选 70（deferred 385：boundary 161 / operator-resolution 108 /
│   mapping 80 / extractor 36）→ fidelity 69 → Silver 21（Reject 49）
│   → 语义审核：15 Gold + 4 Silver + 2 撤销 → curated 19
│   另有 31 条子工作流候选待独立语义审核（6 个多步种子派生）
│
├─【Processing 确定性通道（8,466）】
│   8,466 → 可读一致 8,143 │ helper 内联 3 轮全池 0 命中（终止）
│   → Processing authority 294（确定性能力上限）
│   死区：空链 5,714 │ 单缺 729（L3 support<30）│ 多缺 390 │ boundary 778
│        第三方 provider 87（umep/pff/trendsearth，catalog 外，永久）
│   runalg family：148 authority，holdout 26/30，按政策冻结不推广
│
├─【API 通道（39,386）】
│   25,832 任务边界不足（16,088 无 API 步骤=GUI/插件框架/工具函数，
│     抽样 300 条：98% 是真 QGIS 脚本但非数据处理；9,744 有步骤无 sink=只读分析）
│   13,554 pattern candidate → 6,873 有 sink 锚 → 探针 T2 核心可证 4,010（58%）
│   确定性宏：semantic_priority 7 family +6 │ mutation-only 14 family +24
│   （批量 addfeatures 9 family 永久关闭：循环累加列表不可证明）
│   route1（LLM 候选+AST 验证器）：3,554 → verified 315（8.9%）
│     → 有非结构核心 104（33%）→ 四层去重 canonical 17
│
└─【产出汇总】
    508 官方 aggregate（294 Processing + 214 API）
    539 = 508 + 31 isolated（15step 1+polygon 3+ct 1+rect 2+setattributes 3+addattributes 21）
    565 = 539 + 26 route1（9 pilot + 17 scale）
    workflow-grade（2026-08-16 KPI 口径）：curated 19（15 Gold 权重 1.0 + 4 Silver 0.7）+ 31 待审
```

## 2. 损失三分法：正确选择 vs 管线保守 vs 硬地板

### A. 正确的数据选择（不可回收为 SFT，但为 DAPT 粮食）≈ 66%

| 构成 | 数量 |
|---|---:|
| 完整性（缺失+不可解析） | 338 |
| API 任务边界不足（GUI/框架/工具 + 只读分析） | 25,832 |
| Processing 无 Processing 调用（实现体为主） | ~4,841 |
| **合计（与 unclassified/plumbing 口径高度重叠）** | **~31,000（65%）** |

这些行在角色/价值 census 中体现为 unclassified 29,673 + plumbing 11,655。
**它们不是被错误丢弃的 workflow，而是本来就不构成 Task→Workflow 监督**——
但正是 M2 DAPT 的合格语料。第 9/11 节的判断（"损失的不是 GIS 数据，而是
可监督化的数据"）与证据一致。

### B. 管线保守性（可回收，且已量化）

| 杠杆 | 证据 | 预期增量 | 成本 |
|---|---|---:|---|
| **描述模板事实化** | route1 104→17 中 87 条是 pair 压制；buffer 组嵌入参数值出 7 条 vs 其他组 1 条（7x 实证） | +40~70 | 零（315 verified 已在盘上，重导出即可） |
| **词汇表/映射决策** | PLAIN_COPY 110 auth + setgeometry-only verified 211/315 + centroid 9 + construct 12 —— 语义为"复制/写出要素"，词汇表 130 无对应类（或映射 L3_01_01_01） | +30~100 | 1-2 个 L3 类的授权决策（触碰 130 固化边界） |
| **455 队列规则层失败** | mapping 80 + extractor 36 | 未量化 | 规则工作，逐 family |
| **runalg 冻结** | 148 authority，4 个 source 可修 | ~个位数 | 政策解冻决策 |

### C. 深层能力缺口（需新协议，收益递减）

| 缺口 | 数量 | 现状 |
|---|---:|---|
| 455 队列 boundary 失败 | 161 | helper/跨函数边界恢复，route1 式协议可攻但需新设计 |
| 455 队列 operator-resolution 失败 | 108 | 动态 ID，raw-source LLM pilot 仅证明链路、未证明恢复 |
| API 无 sink 中间链 | 6,681 | 可作算子知识（API catalog/L2-L3），非 workflow |
| unclassified 全量 | 29,673 | 未尝试；census 信号表明多为 plumbing，预期产率低 |

### D. 硬地板（fail-closed 正确）

批量 sink 动态列表（9 family）│ 第三方 provider 87 │ 空链 5,714 │ 单缺
729（support<30）│ 描述变体去重（12+13+87，链+L3 相同仅描述不同 = 同任务）

## 3. 结论

> **2026-09-15 更正**：本报告初版误把 api_pattern 120 条记为"candidate-only 待
> 决策"。对账 `paper_v1_supervision` manifest 现值：该并入决策用户已于 2026-09
> 初做出并执行——**120 条全部 `granted_paper_v1_train_only`，QGIS 池现为
> 629 行**（train 616 / val 8 / test 5，其中 NEW_SILVER_PATTERN=120、
> GOLD 52、SILVER 454、NEW_SILVER_STANDALONE 3），并已进入 C0/P2 SFT
> 训练数据。以下结论按 629 修正。

1. **629 不是"QGIS 天然只有这么多"**，而是 fail-closed 审计标准下的**下界**。
   其中 ~66% 的原始损失是正确的数据选择（且是 DAPT 的合格语料）。
2. **管线确实保守，且保守的账可以算清**：已知零成本/低成本杠杆 +100~200
   （描述事实化 +40~70 已实证；词汇表决策 +30~100 待授权）→ 上限 ~700+。
3. **再往上必须买能力**：boundary（161）/ operator-resolution（108）恢复是
   新协议设计；route1 经验（8.9% verified → 33% 可导出核心 → 重去重压缩）
   表明每条新通道边际递减。
4. **口径分支（2026-08-16 KPI）**：workflow-grade SFT = curated 19（+31 待审）+
   NEW_SILVER_PATTERN 120（多步、真实源码上下文任务文本，已并入）；其余
   主体是算子语义知识资产。讨论"SFT 够不够"时必须先指明口径。
5. **遗留数据治理靶点（2026-09-15 新增）**：api_pattern 120 条中 98 条英文
   任务文本是**未清洗的原始 docstring**（含注释标记 `#`、星号线、类.方法名
   直出如 `JunctionBufferTrimAndExplode.processAlgorithm: 11 步几何处理链`），
   22 条为中文仓库 docstring。这是全项目唯一的英文 QGIS 监督，"真实用户语言"
   ✅ 但"输入分布干净"❌——与推理时干净英文规划输入存在分布失配。清洗/规范化
   应列入数据治理轮，与"522 行中文 QGIS 的英文化"增广一起权衡。

## 引用

- `qgis_source_role_census_v2/report_v1.md`、`qgis_source_role_tiers_v1/report_v1.md`
- `qgis_workflow_admission_v2_structural_replay_v1/report_v2.md`（70/69/21，替代旧 304 口径）
- `qgis_processing_8466_funnel_reconciliation_v1/report_v1.md`
- `qgis_api_pattern_full_v1/`（25,832/13,554/6,873）、`operator_core_probe_summary_v1.json`（T2 4,010）
- `qgis_api_route1_full_v1/`（3,554→315→104→17）、`qgis_api_route1_train_only_v2/`
- progress.md 2026-08-08~19 各条（294/508/539/565、死区、family 闭环）
