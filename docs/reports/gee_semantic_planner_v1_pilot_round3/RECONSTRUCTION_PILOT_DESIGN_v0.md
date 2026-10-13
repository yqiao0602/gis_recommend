# GEE 训练数据重构试点 — 设计规程 v1（已验收，单脚本试运行已授权）

> **验收记录（2026-10-09）**：规程 v1 经 owner 验收通过。
> 授权：仅对 `script_36595` 执行 R1–R4 单脚本试运行。
> 不含：其余 5 脚本、批量构造、训练/推理/RL。
> 三项执行口径澄清（约束试运行报告）见第 5a 节。

状态：MAINLINE_RECONSTRUCTION_PILOT_DESIGN_DRAFT_V1 / NOT_AUTHORIZED / NOT_TRAINING
日期：2026-10-09
前置：v0 原则采纳；本版按 owner 四项修订意见补齐 R1–R4 约束。验收通过后授权仅对 `script_36595` 单脚本 R1–R4 试运行。

## 1. 目标声明（不变）

> 构造一套从原始 GEE 源码到 GIS 工作流监督标签的重构规则，使标签**证据充分、职责合理、依赖可信**——而不是一份更长的源码操作清单。

恢复更多源码信息 ≠ 更正确的任务规划监督。本规程的一切验收指标围绕此原则。

## 2. R1 — 源码结构恢复（变量级数据流图）

### 2.1 输入与输出

- 输入：v2.3.2 parser evidence（ordered_calls、core chain、源码行号）+ 原始脚本；
- 输出：变量级数据流图，节点 = 变量/中间产物，边 = 数据流关系。

### 2.2 数据流边证据规则（修订：禁止顺序推断）

一条数据流边成立，当且仅当同时满足：

1. **定义可定位**：源变量在该行号被赋值/定义；
2. **使用可定位**：目标变量（或其成员/参数）在该行号被使用；
3. **传递可追踪**：二者之间为直接引用、函数参数传递或容器成员，无未追踪的中间重绑定。

每条边记录：

```json
{
  "from_variable": "...",
  "to_variable": "...",
  "via_operation": "...",
  "source_location": {"start_line": N, "end_line": M},
  "evidence_status": "supported | inferred | unresolved"
}
```

**禁止**：仅凭调用顺序相邻建立数据流边。先后调用只能记录为 `source_order` 关系，不是数据流。

无法确认的关系一律 `unresolved`，不猜测补全。

## 3. R2 — 职责归并（任务职责与源码操作分离）

### 3.1 四字段分离记录（修订）

每个重构单元输出四类字段，不得合并：

| 字段 | 含义 | 示例（RUSLE） |
|---|---|---|
| `task_duty` | 任务目标要求的职责 | "compute the vegetation cover (C) factor" |
| `source_operation` | 源码实际执行的操作 | "NDVI min-max normalization chain (lines 93-135)" |
| `provenance` | 证据类别（四分类，继承 GATE_B） | task_determined / source_required / undeterminable / unknown |
| `implementation_detail` | 仅由特定实现选择引入的细节 | "采用 exp() 形式的 min-max 归一化（换其他归一化同样满足任务）" |

### 3.2 升级禁令

- 源码步骤存在 ≠ 任务必需。`source_operation` 升级为 `task_duty` 的唯一条件：Task 文本或任务语义可独立支撑该职责；
- `implementation_detail` 字段**强制非空检查**：每个单元必须回答"换一种合理实现，此细节是否改变？"——若会改变，必须降级为 implementation_detail，不得进入 task_duty；
- 示例固化：源码用随机森林，不代表任务要求随机森林（"用分类器训练并预测"才是 duty；随机森林是 implementation_detail）。

### 3.3 归并粒度

以 Task 文本枚举粒度为准（继承 Step 1 Q3 裁定）。Task 未枚举而源码必需的支撑步骤归为独立 `source_required` 单元，不并入 task_duty。

## 4. R3 — 顺序、依赖与结构（修订：四类关系分离）

### 4.1 关系分类（禁止混用）

| 关系 | 定义 | 证据来源 |
|---|---|---|
| `dataflow_edge` | 变量间数据传递 | R1 边（须满足 2.2 三条件） |
| `workflow_sequence` | 工作流先后顺序 | task_explicit / task_implied，或（弱证据）source_order |
| `semantic_dependency` | 下游职责语义上依赖上游产出 | task 语义 + R1 边共同支撑 |
| `control_structure` | 条件分支 / 汇合 / 重复 | 见 4.2，默认 unknown |

### 4.2 控制结构保守规则（修订：数据流分叉 ≠ 条件分支）

- **一对多数据流分叉**（一个变量被两个后续操作使用）→ 只记录 `dataflow_edge` × 2，**不自动标 branch**；
- **多入汇合**（多个变量进入一个操作）→ 只记录 dataflow 边，**不自动标 merge**；
- 条件分支/merge 仅在满足以下之一时标注：Task 文本明确叙述；或源码存在显式控制流证据（if/else、条件表达式）；
- 重复结构：同构子图重复 + 绑定变量证据（per-target/per-year），绑定的数量解释服从任务（S3 反例规则继承：Task 年份数 ≠ 源码年份数）；
- 无证据的控制结构一律 `unknown`，不伪造。

## 5. R4 — 质量对账（修订：四维验收，不以节点数为主指标）

### 5.1 指标体系（替换 v0 的"信息增量 = 节点数"）

| 维度 | 指标 | 说明 |
|---|---|---|
| **语义恢复** | 对账单元恢复率：对账认定的本脚本 mapping_loss/extraction_loss 单元中，重构输出含对应变量身份/职责/依赖的比例 | **仅核对属于该脚本的审计单元**；37 单元是针对性样本，不是全库错误率，不要求单脚本恢复"全部 35 个" |
| **证据可追溯** | 每项恢复结果可定位到源码行号的比例 | 不可定位的必须标 unresolved，出现在输出中即计违规 |
| **任务合理性** | implementation-detail 固化率：源码偶然选择被标为 task_duty 的比例 | 由 R2 的强制非空检查直接产出 |
| **人工对照（诊断性）** | 与 duty gold 逐阶段吻合度（按 gold 的 acceptable_variants 逻辑） | **仅诊断指标，不单独作为重构正确的证明**——gold 本身可能受 G0-Task 循环性影响，此局限继承自 Step 1 报告 |

### 5.2 成功判定的语义

- 节点数增加既可能表示语义恢复，也可能表示实现拆碎——节点数只作背景统计，不作验收指标；
- 验收 = 四维指标齐备 + implementation-detail 固化率可控 + 无 unresolved 伪装；
- 对账单元的恢复以"该单元在本脚本对应的具体审计项"为准（如 script_36595 的 7 个单元：r/k/ls/c/p_factor、rusle_product、classification_statistics）。

## 5a. 试运行执行口径澄清（owner 验收附加，约束报告）

### 5a.1 unresolved ≠ 违规

R4 中"输出中出现 unresolved 即计违规"的准确语义：**将无法确认的关系伪装成已确认关系才是违规**。如实标记 `unresolved` 是合规的证据管理行为，规则不得惩罚诚实的不确定性而诱导过度推断。报告须区分：

- `honest_unresolved`：按规则标记，合规；
- `disguised_unresolved`：无证据却标 supported，违规。

### 5a.2 implementation-detail 固化率的分母

报告必须列出三数，不得只报错误数或以"都填了字段"视为通过：

```text
checked_units        # 检查单元总数
judged_as_detail     # 被判定为实现细节的项目数
misassigned_to_duty  # 其中被错误写入 task_duty 的项目数
undeterminable       # 无法判定的项目数（显式报告，不得默认为零错误）
```

固化率 = misassigned_to_duty / checked_units，undeterminable 单列。

### 5a.3 恢复率分母预先登记

script_36595 的分母 = 该脚本对应的 7 个审计单元（r_factor / k_factor / ls_factor / c_factor / p_factor / rusle_product / classification_statistics），逐项标注：适用且恢复 / 适用但恢复失败 / 证据不足 / 不适用。四类不得混为一类；禁止以全体 37 单元作分母。

## 6. 执行顺序（修订后，待验收）

1. owner 验收本 v1 规程；
2. 通过后授权**仅对 script_36595** 做 R1–R4 单脚本试运行；
3. 试运行结果决定是否扩展至其余 5 脚本，**不自动扩大**；
4. 批量构造另行裁定。

## 7. 边界

不训练/不推理/不 RL；不修改 G0/G1/G2/G3、Blueprint、locked test；试运行产出为方法验证与监督候选，非训练集、非 semantic gold；支线评价资产（GATE_B/S2/S3 冻结）不动。
