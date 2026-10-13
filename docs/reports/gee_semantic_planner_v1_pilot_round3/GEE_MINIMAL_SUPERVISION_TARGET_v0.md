# GEE Minimal Supervision Target v0（设计草案）

状态：DESIGN_DRAFT / NOT_AUTHORIZED / NOT_ADMITTED
日期：2026-10-09
前置证据：六脚本四层对账（extractor_reconciliation_v3，37/37 已分类，0 unknown）

## 1. 本文档回答的问题

> GEE 数据应该教模型**什么能力**，以及**如何区分"学到规划"与"只学到算子共现"**。

这不是 schema 设计，不是训练计划，不修改任何冻结物。

## 2. 证据边界（来自 37 单元对账，不外推全库）

| 失效层 | 数量 | 含义 |
|---|---:|---|
| mapping_loss | 21 | canonical 链有操作，映射到 30 类时身份/区分消失 |
| extraction_loss | 14 | v2.3.2 可解析，旧生产管线未保留 |
| representation_gap | 2 | 全层存活但因子/依赖绑定缺失 |
| RLE 损失 | 0 | 压缩层无损失 |

结论：G0 semantic chain 的信息瓶颈在**映射层**，不在压缩层。
修复映射层或重建监督表示之前，G0 chain 不能作为完整 Workflow Gold。

## 3. 最小监督目标（从四个候选中选两个）

四项候选能力与证据状态：

| 能力 | 当前证据 | 是否入选 |
|---|---|---|
| A. 粗粒度阶段顺序 | G2 已证（E1 0.664） | 否——已有，无需重复验证 |
| B. 任务分解（task → 阶段职责序列） | mapping_loss 显示阶段身份在映射层丢失，但 canonical 链有信号 | **入选（主目标）** |
| C. 重复子流程识别（task → N 段同构子流程） | script_302840 周期性在 chain 可见但绑定丢失 | **入选（辅目标）** |
| D. 多因子汇合点识别 | canonical 有信号，语义层丢失 | 否——需依赖图表示，超出最小目标 |

### 主目标 B：任务分解

定义：

```text
输入：Task 文本
输出：有序阶段职责序列
      [{"seq": 1, "duty": "DATA_ACQUISITION", "purpose": "..."},
       {"seq": 2, "duty": "FACTOR_COMPUTATION", "purpose": "..."},
       ...]
```

与 G2 Blueprint 的区别：G2 的 stage 是从 implementation trace RLE 出来的，**阶段身份由算子类别决定**；B 的阶段职责从 Task 语义导出，允许多个底层操作属于同一职责、同一操作在不同任务中承担不同职责。

### 辅目标 C：重复子流程识别

定义：

```text
输入：Task 文本
输出：{"repeat_count": N, "unit_structure": [阶段职责序列], "binding": "per-target-variable | per-year | per-region | unknown"}
```

证据来源：script_302840 有 8 个目标变量、8 段周期性子流程；Task 明确列出目标变量名。

## 4. 数据来源（不是 G0 chain，而是"Task + parser 证据"）

对账已证明 v2.3.2 parser 覆盖远好于旧管线。因此最小监督的构造路径是：

```text
原始脚本
  ↓ v2.3.2 parser（已有，6 脚本验证过）
AST evidence（ordered_calls + core chain）
  ↓ 新的阶段归属规则（待设计，不等于 G0 的 30 类映射）
阶段职责序列
  ↓ 与 Task 对齐
监督对（task → duty sequence / repeat structure）
```

关键区别：**不再经过 G0 的 mapping 层**。30 类映射正是 21/37 损失发生的地方。

## 5. 可区分性评价（先于任何训练）

目标：区分"模型学到了工作流规划"与"模型只学到了算子共现/模板"。

### E1. 任务分解 counterfactual

构造真实任务对（不是改写）：

- 同域不同分解：如"作物分类" vs "作物分类+面积统计"——后者多出统计阶段；
- 同骨架不同职责：NDVI 计算 vs LST 反演——同为影像分析但阶段职责不同。

通过标准：分解输出在预期职责位置发生改变，且其余阶段不变。

### E2. 重复结构识别

用 script_302840 类样本：

- Task 列出 N 个目标 → 期望 repeat_count=N、unit_structure 同构；
- Task 单目标 → 期望 repeat_count=1；
- 传入打乱目标的 Task（control）→ repeat_count 不变（结构由数量决定，不由具体名字决定）。

通过标准：N 准确率 ≥ 80%（小样本 binomial 下限），control 无差异。

### E3. 与 G2 skeleton baseline 对照

同一批 Task：

- G2 Blueprint（现有）输出的 stage 序列；
- B 目标输出的 duty 序列。

判别问题：B 是否输出了 G2 无法表达的信息（如"因子计算"与"因子汇合"分开、重复段计数）。
如果 B 与 G2 输出高度一致（normalized edit distance < 0.1），则 B 无增量价值，应放弃。

### E4. 泄漏检查

所有构造产物运行 leakage scan（GEE API/资产 ID/波段 ID 不进入 duty 文本）。

## 6. 执行顺序与门禁

```text
Step 1  在 6 个已有 parser evidence 的脚本上手工构建 6 条 duty-sequence gold
        （纯人工，半天工作量；同时验证第 4 节路径可行）
Step 2  通过后，设计阶段归属规则的初版（规则必须可审计、fail-closed）
Step 3  在 30–50 条样本上做规则 vs 人工 gold 的一致性检验
Step 4  通过后，才讨论是否扩大、是否训练、schema 是否需要演进
```

每步产出独立报告；Step 1 未通过则整个方向停在这里。

## 7. 边界（不变）

- 不修改 G0/G1/G2/G3；
- 不重建 G3；不训练、不推理、不 RL；
- Blueprint-v3 不冻结；locked test 不触碰；
- 本文档不是 schema freeze，不是训练准入；
- G0 semantic chain 不升级为 Workflow Gold；
- 37 单元分类规则在写入论文前需 matcher 可靠性核验（本节 6 的 Step 3 同时承担该核验）。
