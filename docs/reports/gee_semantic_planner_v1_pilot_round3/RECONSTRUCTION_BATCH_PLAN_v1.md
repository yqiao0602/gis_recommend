# 重构试点扩展 — 分批验证规程（v1，统一规范）

状态：BATCH_EXPANSION_AUTHORIZED / METHOD_VALIDATION_ONLY / NOT_TRAINING / NOT_BATCH_CONSTRUCTION
日期：2026-10-09
授权依据：owner 裁定（script_36595 修订版通过；批准其余 5 脚本分批重构验证）
授权性质：**方法验证范围扩展，不是训练集入库或模型训练授权。**

## 1. 统一技术规范（全批次强制，源自 script_36595 复核裁定的两项口径）

### 1.1 数据流边 evidence_status 双态（不得合并）

```text
supported                # 完整三条件证据：定义 + 使用 + 传递 均在源码内定位
supported_passing_only   # 使用 + 传递已确认；源端定义在脚本外（外部预绑定）
```

外部预绑定输入的变量节点必须：

- `definition_location: unavailable_in_source`
- `first_use_line` 单独记录（首次使用 ≠ 定义）
- 相关边标 `supported_passing_only`，不得标 `supported`

### 1.2 workflow_sequence 的 evidence_status 分级

```text
task_explicit   # 任务文本逐字/直接叙述该先后顺序
task_implied    # 顺序是数据流/语义推断，合理但任务未逐字叙述
```

不得为表达合理顺序而抬高证据等级。任务枚举顺序（如 R,K,LS,C,P 的列举）只记 `task_enumeration_order`，不得升级为 workflow_sequence。

### 1.3 关系类型清单（六类分离，全批次一致）

```text
dataflow_edge            # 数据传递（R1 三条件/双态）
task_enumeration_order   # 任务文本列举顺序（纯文本证据）
workflow_sequence        # 工作流先后（task_explicit/task_implied 分级）
semantic_dependency      # 语义依赖（任务语义 + 数据流共同支撑）
semantic_merge           # 任务明确命名的合并（区别于控制流 merge）
control_structure        # 真实条件分支/循环（默认 unknown，需显式证据）
```

### 1.4 任务与源码冲突记录

任务描述与源码不一致时（如 script_269131 已知不一致）：冲突、适用范围与不确定性显式记录；不得默默用源码修正任务，也不得为一致性删去源码证据。

### 1.5 可复现性

每脚本保存：源文件 hash、生成脚本、产物 hash、逐项审计结果、修订记录。

## 2. 分批计划与各批验收重点

| 批次 | 脚本 | 验收重点 |
|---|---|---|
| **第一批** | `script_275285`（LST 反演）、`script_93009`（城市扩张） | 多阶段中间链（NDVI→FV→EMM→LST）的变量级追踪；年份绑定（Task=2 vs source=5 反例）；变化检测的迭代结构（不伪造 branch/merge） |
| **第二批** | `script_302840`（多目标预测）、`script_405410`（成本面） | 重复子流程的变量级绑定（8 目标）；多因子融合的 semantic_merge 记录；归一化/导出的实现细节隔离 |
| **第三批** | `script_269131`（火灾敏感性） | **压力测试**：任务与源码公式差异的冲突记录；pi_* 变量链追踪；输出职责的不一致处理。已知不一致样本，最后执行，不用于率先校准规则 |

每批完成后先检查证据质量和规则适用性，验收通过再进下一批。若某类脚本暴露系统性缺陷：**修订规则并重新审查已完成样本**，不继续扩大。

## 3. 每脚本统一验收报告要求

1. R1：变量清单（含 definition_location / first_use）、数据流边（双态）、honest unresolved；
2. R2：四字段分离单元 + implementation_detail 强制检查（checked/judged/misassigned/undeterminable 三数上报）；
3. R3：六类关系分列 + 控制结构保守分类；
4. R4：四维验收（语义恢复分母 = 该脚本自己的审计单元；证据可追溯双态分列；固化率；gold 对照仅诊断）；
5. 失败分析：抽取遗漏 / 变量追踪失败 / 归并错误 / 任务证据不足 / 关系误判 五类分列；
6. 原始产物保留，修订另存（审计留痕）。

## 4. 授权边界

**本次批准**：其余 5 脚本的方法验证与监督候选材料构建。

**仍需单独裁定**：

- 六条试点结果推广到完整 GEE 数据库；
- 批量构造正式监督数据；
- 产物认定为 semantic gold 或训练集；
- 训练、推理、强化学习。

冻结资产（GATE_B/S3/G0/G1/G2/G3/locked test）不触碰。

## 5. 执行状态

- [x] 统一规范写入本文件（script_36595 已按新口径重新生成，结果不变：7/7 恢复、0 固化、17 supported + 4 passing_only）
- [ ] 第一批（275285 + 93009）
- [ ] 第二批（302840 + 405410）
- [ ] 第三批（269131，压力测试）
- [ ] 全批完成后：批量构造设计审查（另行裁定）
