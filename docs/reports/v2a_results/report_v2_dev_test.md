# V2a A/B 完整结果（dev + test，含配对修正与两个诊断发现）

日期：2026-09-16/17
状态：A/B 的 dev 与 test 原始指标已冻结；canonicalization 诊断复跑进行中
数据与协议：manifest_v2（63b5db1）+ spec v1；A/B 唯一变量 = Tier-2 是否进入及其权重；评测脚本、解码（greedy / 512 token / 显式 EOS）与指标定义四处一致

## 1. 原始指标（各 split 全量，脚本内全文本计分）

### dev

| 指标 | A（120 行） | B（147 行） |
|---|---:|---:|
| parse 成功率 | **0.633** | 0.558 |
| operator micro P / R / **F1** | 0.360 / 0.258 / **0.301** | 0.319 / 0.217 / **0.259** |
| operator macro F1 | 0.335 | 0.301 |
| link micro P / R / **F1** | 0.539 / 0.362 / **0.433** | 0.592 / 0.348 / **0.438** |
| link macro F1 | 0.548 | 0.571 |
| graph EM | 0.033 | 0.027 |
| hit_cap（截断） | 42/120（35%） | 64/147（44%） |
| 预测算子实例 / gold | 236 / 671 | 238 / 811 |
| 越界算子实例 | 93 | 89 |

### test

| 指标 | A（111 行） | B（149 行） |
|---|---:|---:|
| parse 成功率 | **0.577** | 0.409 |
| operator micro P / R / **F1** | 0.293 / 0.202 / **0.240** | 0.381 / 0.235 / **0.291** |
| operator macro F1 | 0.274 | 0.319 |
| link micro P / R / **F1** | 0.534 / 0.339 / **0.415** | 0.599 / 0.328 / **0.424** |
| link macro F1 | 0.546 | 0.547 |
| graph EM | 0.009 | 0.013 |
| hit_cap | 46/111（41%） | 88/149（59%） |

## 2. ⚠️ 关键修正：全量口径的 A/B 比较无效（population artifact）

**A 的 test 集是 B 的严格子集**（A = Tier-1 only；B = Tier-1 + Tier-2）。上表 test 中 "B(0.291) > A(0.240)" 因此**不可解读为 Tier-2 有效**——两组不是同一批样本。

**配对比较（共同 Tier-1 行，原始未规范化口径）**：

| split | 共同行 | A op F1 | B op F1 | 结论 |
|---|---:|---:|---:|---|
| dev | 120 | **0.301** | 0.267 | A > B |
| test | 111 | **0.206** | 0.189 | A > B |

**配对后 A 在两个 split 上都优于 B**（与 dev 全量口径一致），且 B 多用 12.8% 有效曝光。

**A/B 结论（定稿）**：**Tier-2 弱监督在本轮无正向价值，接近略负**——建议 B 不进入后续主线；A（Tier-1 only）作为 V2a 的正式基线配置。

## 3. 两个诊断发现（比 F1 更重要）

### 3.1 主要损失是**重复失控**，不是选错算子

- A dev：44 个 parse 失败中 **42 个跑满 512 token**；B test：88/149 行截断
- 截断行尾部是同一算子无限重复（`native:extractbydistance` 连续 20+ 次）
- **正常行很短**：可解析行生成长度 p50=73 / p90=189 token；预测中位 2 个算子（gold 中位 3）
- 同型问题在 M3-P1（L3 空间）已出现 → **序列终止控制是跨架构、跨输出空间的共同短板**，不是 V2a 特有

### 3.2 越界算子名几乎全是**真算子的截断/前缀损坏**

A test：123/242（51%）预测实例不在 catalog，但绝大多数是：
```
native:reproject      → native:reprojectlayer
native:reclassify     → native:reclassifybytable
native:merge          → native:mergevectorlayers
native:gdal:translate → gdal:translate        （provider 前缀叠错）
gdal:ras              → gdal:rastercalculator （截断）
native:voronoi_polygons / native:project / native:remove（下划线化或截断）
```
**含义：模型常常知道该做哪个操作，只是写不对算子 ID。** 这指向一个**不改变架构、不引入 L3** 的改进：catalog 约束解码 + 名称规范化层。精确增量由正在跑的 `--canonicalize` 复跑给出（初版估计 A 的 precision 0.326→0.508，但该估计基于被截断到 400 字符的预测文本，**偏低且不可靠**——见 §5）。

## 4. 与 V1 的关系（口径纪律）

V2a 是**原生算子空间**（`processes + links`），V1 是 **L3 → bridge → 算子**。两者的 operator 指标**输出空间不同，不构成门槛比较**：
- M3-P1 0.1605 / M3-P2-T1 0.1991（V1，含 bridge 损耗）
- V2a-A 0.301（dev）/ 0.240（test），另新增 V1 无法测的 **link F1（0.433 / 0.415）**

可比的是"各自体系内的 operator 指标"与"V2a 独有的结构指标（link F1）"。V2a 的架构级价值需在**同一 benchmark v0.2.1** 上对照才能定论（下一步）。

## 5. 工程事故（如实记录，含本轮新发现）

| 事故 | 代价 | 修复 |
|---|---|---|
| pre-training audit 过浅（未验 loss 数学与落盘） | B 训练 68 min + A dev 32 min | 新增 `--smoke`（真实 loss 路径 + HF 对齐断言 + 真实评测 + 落盘验证） |
| 逐样本加权实现为"行均值加权"（≠ HF token 加权） | 同上 | 改 token 级；smoke 断言精确对齐（1.598273 = 1.598273） |
| F1 用"逐行 P/R 累加"（可 >1） | 无（早发现） | 改 micro TP/FP/FN + macro 双报 |
| eval 写文件前崩溃 | A dev 首次 32 min | 移除崩溃源 + 先落盘 |
| **预测文本被截断到 400 字符** | 使已存的 predictions 无法重新计分（17/76 可解析行受影响） | 改为存全文；canonicalization 复跑中 |

**纪律固化**：新 loss/评测路径必须 `--smoke` PASS 才允许正式运行；预测必须存全文方可复计分。
