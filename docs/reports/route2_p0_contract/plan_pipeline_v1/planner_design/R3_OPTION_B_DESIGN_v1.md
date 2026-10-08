# Planner-v2 输出目标重定义——Option B 设计分析（v1，2026-10-04，CPU 数据支撑）

> 依据 owner 指令：暂停 P2；三层重复框架（语义保留 / group 保留 / 绝对次数移除）；
> Option B（保留 repetition semantics + dimension，删除绝对次数）为倾向方向。
> 本文档用全量数据回答 Option B 的三个设计问题，供 owner 做 schema 定稿。

## 1. Option B 的 Schema v2.5 草案

```json
{
  "stages": [
    {"seq": 1, "family": "RASTER_LOAD"},
    {"seq": 2, "family": "BAND_ARITHMETIC", "repetition": {"dimension": "per_band"}},
    {"seq": 3, "family": "AGGREGATION"}
  ]
}
```

- **stage 每个游程出现一次**（不再有数值 repeat 字段）；
- **`repetition.dimension`** = per_band/per_class/per_year/per_feature/unspecified——
  表达"此操作作用于一个对象集合"的 GIS 语义；
- **绝对次数完全移出 Planner**（Grounding 从实际数据解析）。

与现 schema 的差异：仅删除 `repeat` 数值、`repetition_groups` 改为 stage 内联
`repetition.dimension`。转换机械无损（游程→1 stage + 维度标记）。

## 2. Option B 解决了什么（数据确认）

1. **不可识别量移除**：绝对 repeat（深尾 bias −70~−365、Task 不可识别）从监督目标中消失——
   R3-B-1/P1-B/长度分桶三轮证据闭环。
2. **迭代语义保留且可学习**：~80% instruction 含迭代维度线索（A4）；repetition-presence
   探针 AUC 0.940——"哪些 stage 是重复的"高度可学习。
3. **S5 的重新定义**：hint 不再绑定到具体 ×N，S5 的"keyword shortcut"问题转化为
   **dimension 分类问题**（per_band vs per_class vs per_year vs unspecified）——
   这正是 hint 探针已经证明可学习的部分（0.968）。

## 3. Option B 不能解决什么（诚实的边界）——语义级长度极端性仍在

**全量语义级长度分布（B-form 输出长度）**：

| 指标 | 语义级 stage_count | 原始迭代（对照） |
|---|---|---|
| p50 / p90 / p99 | 6 / 16 / **68** | 7 / 22 / 88 |
| max | **1,830** | 1,830 |
| ≥30 stages 行 | **1,393（3.8%）** | — |
| ≥100 stages 行 | ~200（0.5%） | — |

- 删除绝对次数**只解决了循环迭代部分（深尾的 ~24.5%）**；
- **语义级长尾的主体是大量不同语义阶段**（51+ 原始桶 stages 均值 114，repeat_share 仅
  0.245——R3-CD-2 结论在 v2 粒度复现）；
- **1,830-stage 的极端行在 B-form 下依然是 1,830 个 stage**——B 不缩短它们；
- 长行（≥30 stages）中 repeat>1 stage 仅占 **7.5%**——长行长度主体也是**不同语义阶段**，
  不是循环。

**含义**：Option B 解决"不可识别的循环次数"，但**不解决"极长 workflow 的生成长度"**。
后者需要（未来）：分段生成/层次化规划/或接受极端行在本代 Planner 范围外
（0.5% 的行 >100 stages，97% 的行 ≤30 stages——多数任务在可生成范围内）。

## 4. 长行（≥30 stages）的结构画像（1,393 行）

- repeat>1 stage 占比仅 0.075（vs 短行 0.152）——长行的长度来自**不同语义阶段的累积**；
- hint 维度：none 462 / unspecified 425 / generic_each 245 / per_year 154——
  **长行大多数没有明确的迭代维度**，与"长=多子目标累积"一致；
- 判读：**长 workflow 是"多子目标链"，不是"大循环"**——对 Planner 而言这是
  生成长度问题（可分段），对 Grounding 而言是正常的有向图。

## 5. 冻结 gate 兼容性

- B-form stage 序列（语义粒度、无展开）与冻结 gate（plan-family bag-F1、含展开重复）
  **单位不同**——B 线的评测必须走 v2 诊断口径（E1-E4），冻结 gate 不动；
- 统一对比管线（v1/v2 → 同口径）在 B-form 下依然需要 semantic→plan-family 的映射——
  该映射的工程问题保持不变，但 B-form 的 stage 序列（无重复展开）与 plan 序列的差异
  比含展开版本**更小**（B-form 不展开循环，plan 的循环展开来自 family 粗化）——
  映射保真度预期优于含展开版本，待验证。

## 6. 建议（供 owner 裁定）

1. **采纳 Option B（Schema v2.5）**：stages + repetition.dimension，绝对次数移除；
2. **B-form 的长度边界明确登记**：97% 的任务 ≤30 stages 在可生成范围内；
   >30 的 3.8%（尤其 >100 的 0.5%）是本代 Planner 的已知边界（论文级 limitations）；
3. **统一对比管线照旧执行**（family-selection 对比不受 B 重定义影响——映射问题另测）；
4. **S5 的处理随 B 自动简化**：hint=dimension 分类，绑定监督不再需要
   （dimension 分类 AUC 0.968 已证明可学习）；Planner-v2 round 2 = 用 B-form
   目标重训（数据转换 CPU 即可），S4/S5 在新目标下重测。
