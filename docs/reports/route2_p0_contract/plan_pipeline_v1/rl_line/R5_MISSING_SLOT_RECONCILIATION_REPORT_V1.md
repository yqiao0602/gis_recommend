# R5 缺失槽位对账报告 v1（owner 八轮指令：逐项对齐盲评标签、规则输出与 192 条候选）

> 日期：2026-10-13 ｜ 数据：`R5_MISSING_SLOT_RECONCILIATION_V1.json`（358 实例全清单，逐条含需求证据）
> 口径：表示充分性（owner 八轮盲评原文）；V2 包裹歧义单独列报，不入误伤讨论。

## 1. 合成包对照（owner 八轮盲评 vs r5 v0.3）

**owner 指标：误伤 0/3、omission 检出 3/3、弃权 2/9（22.2%）、S8 边界单列。** r5 输出与 owner 标签的映射：

| 项 | owner | r5 | 关系 |
|---|---|---|---|
| S1 (B3) | omission（缺 TEMPORAL） | incomplete-missing TEMPORAL | 一致 |
| S2 (A2) | complete_reasonable（**保留空间操作语义不确定性**） | complete_coarse_uncertain（SPATIAL 备选族 coarse） | **同一不确定性，r5 机械化** |
| S3 (A1) | complete_reasonable（BAND_ARITHMETIC 合理表达 NDWI，**不断言普遍等价**） | complete_coarse_uncertain（INDEX 备选族 coarse） | 同上 |
| S4 (C2) | unclear | abstain | 一致 |
| S5 (A4) | complete_reasonable（**任务未要求精度评估**） | complete_coarse_uncertain，**无 gap 信号** | 一致 + **登记一处构造标注错误**：我在 A4 预期里写"ACCURACY_ASSESSMENT gap 将触发"——错，T_CROP 无精度要求，r5 正确未触发（真实 30160 有 kappa，gap 正确触发；两处行为都对，错在我的标注） |
| S6 (B2) / S7 (B1) | omission | incomplete-missing INDEX/MASK | 一致 |
| S8 (A3) | omission（ITERATIVE_APPLY 不证明 NDWI） | incomplete-missing INDEX | 一致（边界例，双方同意不入分母） |
| S9 (C1) | unclear + 应记表达缺口 | complete_coarse_uncertain + CHANGE_DETECTION gap | 证据级一致（可表达部分照计 + 缺口单列 = partially_scorable 语义） |

**结论：0 误伤获 owner 确认；唯一"分歧"实为 r5 的 coarse 标志与 owner 手工保留的不确定性一一对应。**

## 2. 192 候选缺失槽位全量对账

**总计 358 个缺失实例，分布在 174/192 个候选上。**

### 按槽位（X4 胶水家族占绝对大头）

| 槽位 | 缺失实例 | 占比 |
|---|---|---|
| INDEX（NDVI/NDWI 计算） | 90 | 25.1% |
| **MASK（云掩膜）** | **87** | **24.3%** |
| COMPOSITE（中值合成） | 49 | 13.7% |
| TEMPORAL（时间筛选） | 45 | 12.6% |
| SPATIAL（空间裁剪/筛选） | 41 | 11.5% |
| CLASSIFY | 27 | 7.5% |
| STATS | 19 | 5.3% |

### 按歧义分类

| 类 | 实例 | 含义 |
|---|---|---|
| V1 无歧义 | **305（85.2%）** | 候选无可疑包裹，缺失判定干净 |
| V2 ITERATIVE_APPLY 包裹歧义 | **53（14.8%）** | 按 S8 先例维持 missing，但单独列报（能力理论上可被包裹） |

交叉：INDEX 缺失中 78 例 V1 / 12 例 V2；MASK 70/17；完整的 slot×category 矩阵见 JSON。

## 3. 深查样例（逐条人工复核）

1. **k=29519 cand0，INDEX | V1**：需求证据 = "Compute the Normalized D…"（NDWI 明写）；候选族 = [RASTER_LOAD, TEMPORAL_FILTER, ATTRIBUTE_FILTER, SPATIAL_FILTER]——无任何指数/波段算术族。ATTRIBUTE_FILTER 不能替代（owner 盲评同款措辞）。**真遗漏。**
2. **k=823 cand2，MASK | V1**：需求证据 = "explicit cloud/shadow masking"；候选族 = [RASTER_LOAD, TEMPORAL_FILTER, CLASSIFICATION, RASTER_LOAD]——无 MASKING。任务明写云掩膜。**真遗漏。**
3. **k=823 cand3，MASK | V2**：候选族 = [AGGREGATION, RASTER_LOAD, TEMPORAL_FILTER, ITERATIVE_APPLY, CLASSIFICATION]——含 ITERATIVE_APPLY，理论上掩膜可被包裹。按 S8 先例维持 missing 并单列。**边界例。**

## 4. 三个结构性读数（供独立裁定）

1. **INDEX+MASK 两槽位占全部缺失的一半**（177/358 = 49.4%）——X4"漏胶水阶段"有了精确到槽位的分解：最缺的是**指数计算**与**云掩膜**的表达；
2. V2 包裹歧义 15%——词表若增加"包裹语义"的表达（或 Blueprint 层引入子步骤），可缩小不可判定区；
3. 本对账与能力定位实验（X4 47.6%）、S2 审计（MASKING 覆盖 1%）**三方独立方法指向同一结论**——漏发的是 BAND 计算/掩膜类胶水阶段。

## 5. 待 owner

① 抽查本对账（建议从 V1 各槽位各抽 2-3 例核验证据链）；② 裁定 V2 包裹歧义的最终口径（维持 missing 单列 vs 引入新中间态）；③ 裁定是否进入下一轮（真实任务上的可复现判别力 + 不系统性误伤合理替代——八轮原文的 RL 奖励准入条件）。
