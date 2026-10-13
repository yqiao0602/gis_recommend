# Gate B 解盲报告 v1（独立集 80 候选人工盲评 vs r5 v0.5.1）

> 日期：2026-10-13 ｜ 标签冻结：`gate_b_labels_frozen_v1.json` ｜ 对照数据：`gate_b_unblind_v1.json`
> 判定粒度：阶段族级（owner 八轮口径），非 DAG 级正确性认证；B*（包装器不透明）按 owner 指令单列，不入 O/C 统计。

## 1. 总账（234 个槽位实例）

| 桶 | 实例数 | 占 r5 对应分母 |
|---|---|---|
| **TP**（r5 missing = owner omission） | **128** | — |
| **FP 误伤**（r5 missing = owner covered） | **4** | **2.74%**（4/146） |
| `unresolved_wrapper`（r5 missing = owner B*） | 14 | 9.6%（单列） |
| **FN 漏报**（r5 covered = owner omission） | **0** | **0%**（0/88） |
| TN（r5 covered = owner covered） | 88 | — |
| requirement_disagreement / false_requirement | 0 / 0 | — |

**误伤率 2.74% ≪ 预注册红线 10%；漏报率 0%。** 八~九轮登记的"独立集误伤未量化"风险（owner 十二轮风险 #1）**现已量化并处于低位**。

## 2. 4 个误伤实例的定位（单一结构原因）

全部集中在 **k=25159 的 COMPOSITE 槽位**（cand0/1/4/7）：这些候选含 ITERATIVE_APPLY，owner 判"迭代可能封装掩膜及中值处理"为**可见合成证据（C）**，而 r5 的族匹配保守地要求 AGGREGATION 在场 → 判 missing。**这不是随机误伤，是 wrapper 语义归属的口径分歧**：owner 在包装器+上下文足以推断时判 covered，r5 按冻结的保守规则不采信包装器。cand3（owner 对 M 和 C 均判 B*）正确落入 unresolved 桶——两套判据在"确实不可见"时一致保守。

**含义**：误伤可通过一个明确规则修正消除（wrapper+聚合上下文 → COMPOSITE covered_coarse），但它**必须走 owner 批准的规则变更流程**，不在影子评估中途修改。

## 3. 任务级分布（owner 缺失槽位数 vs r5 缺失槽位数，8 候选合计）

| 组 | owner O | r5 missing | 差 | 解释 |
|---|---|---|---|---|
| 2235 | 6 | 8 | +2 | 2 例 B*（r5 missing，owner 未确认） |
| 3084 | 20 | 22 | +2 | 2 例 B* |
| 10540 | 11 | 11 | 0 | 精确一致 |
| 10893 | 2 | 3 | +1 | 1 例 B* |
| 24025 | 12 | 12 | 0 | 精确一致 |
| 24515 | 11 | 11 | 0 | 精确一致 |
| **25159** | **5** | **15** | **+10** | **wrapper 口径分歧集中地（§2 的 4 FP + 5 B*）** |
| 29444 | 23 | 23 | 0 | 精确一致 |
| 31187 | 22 | 23 | +1 | 1 例 B* |
| 31609 | 16 | 18 | +2 | 2 例 B* |

**除 25159 外，r5 与 owner 的逐任务缺失计数偏差 ≤2，且全部偏差由 B* 桶解释**——r5 没有发现 owner 未见的遗漏类别，也没有漏掉 owner 见过的类别（FN=0）。

## 4. 无效阶段与冗余（按 owner 指令分记）

- 无效阶段 4 处：3084/cand6 `None×1`、24515/cand6 `None×2`、31187/cand2 `None×2`、10540/cand7 `TEMORAL_FILTER`（拼写）——单列，不计入冗余；
- 冗余阶段：owner 判定现有摘要不足以确认任何必然冗余（`unnecessary_stages` 全空）——r5 本就不罚冗余（结构奖励 harmful-extra 通道另计），无冲突。

## 5. 影子评估门位与结论

| Gate | 状态 |
|---|---|
| A 冻结+入库 | ✅ commit 7ba729a3 |
| **B 独立集盲评+解盲** | ✅ **通过**：80/80 全量人工核验；误伤 2.74%（低且可定位）；漏报 0%；wrapper 9.6% 单列 |
| C 反事实排序 | 待执行（构造基础=Gate B 确认的 covered 槽位） |
| D 离线排序分析 | 待执行（指标已在 `GATE_CD_PREREGISTRATION_V1.md` 预注册） |

**十二轮风险清单更新**：风险 #1（误伤未量化）→ **已量化：2.74%，且集中在单一可修正的 wrapper 口径**；风险 #2（组内区分价值）→ Gate D 待测（初步：本组内 owner O/C 混合的组有 10540/24515/3084 等，存在可区分内容）；风险 #3（过度生成诱导）→ Gate C 的 CF3 硬门槛待测。

## 6. 下一步

Gate C 反事实构造与执行（按 `GATE_CD_PREREGISTRATION_V1.md`）→ Gate D 分析 → 影子评估总结论提交 owner。规则修改（含 §2 的 wrapper 口径）作为 v0.6 账本项**待 owner 批准**，影子评估期间不改规则。
