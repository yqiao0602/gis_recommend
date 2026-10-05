# C1-2a Zero-shot Cross-platform Reasoning Transfer 结果报告（v1，2026-10-05）

> 依据 owner 放行（`36a845e`）：Planner-v2 adapter（GEE 训练，零 QGIS 训练）对 QGIS
> held-out 任务（v2a_A dev+test 231 行）直接生成 semantic stage plan，与映射后
> QGIS gold 对比。零训练；命名 C1-2a（区别于 A1' 的 C1-2b）。
> 产物：`c12a_zero_shot_metrics.json`（metrics + 231 逐项）。

## 1. 结果（n=231 QGIS OOD 任务）

| 指标 | 结果 | 参照 |
|---|---|---|
| S1 parse 率 | **0.4892**（51% 输出合法 JSON；其余回退散文先验） | in-domain 0.8089 |
| **M family bag-F1** | **0.0472** | trivial baseline（同 rows）0.0；in-domain 0.6636 |
| M ordered LCS-F1 | 0.0473 | — |
| 预测长度 | **1.8 stages/行** | gold mapped 4.5 ops/行 |

**family 分布对比（本结果的机制）**：

| pred top（GEE 先验） | n | gold top（QGIS 现实） | n |
|---|---|---|---|
| RASTER_LOAD | 122 | **VECTOR_GEOMETRY** | **373** |
| BAND_SELECT | 110 | BAND_ARITHMETIC | 203 |
| AGGREGATION | 89 | SPATIAL_CLIP | 87 |
| ATTRIBUTE_FILTER | 51 | RESAMPLE_REPROJECT | 81 |

**模型面对 QGIS 矢量任务时发射的是 GEE 遥感 repertoire（raster 三族），
而 QGIS gold 的主体是 VECTOR_GEOMETRY（32%）——两个分布几乎不相交。**

## 2. 判定（按预注册判读树）

**零样本 family 级迁移失败**——bag-F1 0.047，虽高于 trivial 0.0，但绝对水平接近零，
且远低于 in-domain 0.6636。按 owner 判读树：**A1'（reasoning prior → grounding gain）
训练实验成为唯一判据**。

**但三个度量与解释的注意事项必须登记**：

1. **粒度伪影**：pred 是 stage 级（1.8/行），gold 是映射后 operator 实例级（4.5/行）——
   长度不匹配本身压低 bag-F1；
2. **gold 映射覆盖 69.7%**：30.3% 的 gold op 无语义 family（VECTOR_GEOMETRY 部分命中），
   gold 分母不完整；
3. **域差是真实的**：QGIS 任务以矢量/几何工作流为主（VECTOR_GEOMETRY 32%），
   GEE 训练分布以 raster/遥感为主——**这不是模型缺陷，而是两个平台任务本质不同**
   （GEE=遥感栅格分析，QGIS=矢量空间分析为主）。

## 3. 对 A1'（C1-2b）设计的关键输入

1. **零样本失败 ≠ A1' 无价值**——恰恰相反：零样本失败说明 **QGIS grounding 的
   知识必须从 QGIS gold 训练**（1,334 行），而 GEE reasoning prior 的价值假设
   （更好的初始化/更通用的规划结构）只能由 A1' 训练实验检验；
2. **Gate 2 的负迁移教训必须纳入 A1' 设计**：A1' 不能是"把 GEE 蓝图数据当 DAPT"；
   合理形态 = GEE-trained Planner 作为 reasoning 初始化 + QGIS grounding head
   （小规模 QGIS gold 训练）——但存在 Gate 2 式负迁移风险，**A1' 实验本身需要
   对照设计**（vs C0 fresh SFT）；
3. **1,334 行 QGIS gold 的规模问题**：A1' 的价值假设之一是 GEE reasoning 缓解
   QGIS 数据稀缺——若 A1' ≈ C0，则稀缺问题需另行解决（数据增广/主动学习/缩小目标）。

## 4. 对 R3 证据链的更新

```text
C1-0 GEE reasoning 可学        ✓（E1 0.664/E2 0.967）
C1-1 跨平台结构同源            ✓（17 family/69.7% 映射）
C1-2a 零样本迁移               ✗（bag-F1 0.047——family 分布不相交：
                                  raster 先验 vs vector 现实）
C1-2b grounding gain           待 A1'（唯一判据）
```

**C1-2a 的科学结论**：**GEE workflow reasoning prior 在 family-selection 层面
不具备向 QGIS 任务分布的零样本迁移能力**——两平台的 workflow 词汇与结构分布
（raster vs vector）存在实质性域差。这与 Transfer Audit 的"69.7% 可映射"不矛盾：
可映射的是语义标签系统，不可迁移的是**任务-解决方案的分布**。

## 5. 状态

- 零训练；GPU 空闲；locked test 与冻结物未动。
- **待 owner 裁定**：A1' 实验是否启动（含对照设计）；或先进行其他方向。
