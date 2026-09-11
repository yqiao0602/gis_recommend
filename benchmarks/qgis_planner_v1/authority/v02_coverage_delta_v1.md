# v0.1 → v0.2 Coverage Delta（边界级，方案 B）

裁决（2026-09-11 owner 三连裁）：①方案 B 边界级 delta，不披露 sealed 内部；②冻结 spec 为上位约束，v0.1 task 逐条受检（retain/rebind/replace）；③#5 采用 A+B 合并修订（待管道恢复时落文本）。

## Q1: v0.1 已有什么（结构层面，全部来自无密封侧）

**Final 侧**（来源：v0.1 审计 + 52-DAG queue summary——final 40 是其子集，具体 40 选哪些在 sealed 内，方案 B 不披露）：

| 维度 | queue 侧实测 | final-40 边界推论 |
|---|---|---|
| linear / merge | 30 / 22 | linear ∈ [22,30]；merge ∈ [7,22] |
| **pure_branch** | **0** | **final 不可能含任何 branch** |
| **hybrid** | **0** | **final 不可能含任何 hybrid** |
| 1-step | 1 | ≤ 1 |
| 2-3 / 4-6 / 7+ | 32 / 12 / 7 | — |
| vector / mixed / raster | 34 / 13 / 5 | — |

**Dev 侧**（gold 无密封，全量实测）：8 canonical DAG × 5 变体，**全部 linear**，零 branch/merge。

## Q2: 集中在哪里

```text
branch = 0、hybrid = 0（全库为零）
1-step ≤ 1
dev 全 linear、8 DAG、12 算子
```
结论：**不是 task 数量不够（120），是结构分布失衡**——这正是 v0.2 要修的全部。

## Q3: 58-DAG 修复池补什么

| 维度 | 修复池（58） | 其中既有 C-eligible（37） | 其中恢复审毕（21） |
|---|---|---|---|
| linear | 39 | 25 | 14 |
| pure_merge | 12 | 10 | 2 |
| **pure_branch** | **3** | 0 | **3** |
| **hybrid** | **4** | 2 | 2 |
| 1-step / 2-3 / 4-6 / 7+ | 1 / 38 / 13 / 6 | — | — |

**修复池是 branch/hybrid 的唯一来源**（v0.1 侧为零）；1-step 池内也仅 1 个。

## Q4: v0.1 task 保留原则（裁决 ②）

> **冻结 spec 是检查者，不是被检查者。**

120 条 final task 逐条受检：合规 → retain；不合规 → rebind（源溯源绑定+参数剥离+source-disjoint 重检+task-to-gold 审查）或从修复池 replace。task↔DAG 绑定在 sealed 内（方案 B），**逐条标记在 rebind 阶段增量产出，不在此预估**。

## Q5: 需要替换多少

边界级算法：branch/hybrid/1-step 全部来自池（结构必需替换数下界 = 池内这些类别的入册量）；linear/merge/2-3/4-6/vector 质量由保留的 v0.1 task 承担。**精确替换数在逐条 rebind 时定**，不预设“重造 120”。

另一会话的 22 carry-forward / 9 new 测量：**记录为其申报值，未独立复核**（final 选择在 sealed 内）。与现有 C-eligible 的交集边界 ∈ [25, 37]。

## 管道路线（已定格）

```text
v0.1 (frozen) → coverage audit → [retain] + [gaps → 58-DAG repair pool]
   → v0.2 candidate set → dev/final selection → v0.2 freeze
```

下一步：落 #5 合并修订文本 → v0.1 final 逐条 rebind 受检（spec 为准）→ dev 重建（从池选，v0.1 dev 是最弱处）→ refusal 12 继承重绑 → 选图 → freeze。
