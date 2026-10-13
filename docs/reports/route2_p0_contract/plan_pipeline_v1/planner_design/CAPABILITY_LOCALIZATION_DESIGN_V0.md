# 模型能力定位实验设计（v0——CPU 第一阶段即日可跑）

状态：CAPABILITY_LOCALIZATION_DESIGN_V0 / 依据 owner 研究方向重构裁定（2026-10-11）
日期：2026-10-11
定位：回答"当前模型距离目标最远的地方在哪里、该缺口能否由现有路线弥补"——**先诊断，后治疗**。P1（SFT/DEC）降级为候选方案，服从本实验结论。

## 0. 四能力 ↔ 可观测失败映射（owner 四能力框架的操作化）

| 能力 | 可观测失败模式 | 数据来源 |
|---|---|---|
| 1 任务理解与分解 | 关键处理阶段缺失（gold 有、预测无的 stage family）| P0 dev 预测逐行 family diff |
| 2 工作流组合 | 顺序错误（LCS≪bag：家族对但序错）；重复失控（同族连发展开，本应 repetition_group） | 同上 + pred_text 循环模式 |
| 3 QGIS grounding | 算子选择错误、算子空间覆盖缺口 | QGIS 侧预测（在笔记本/GPU 窗口）；本期先做 Planner 侧 |
| 4 输出可靠性 | 格式错误（parse fail 分型：截断/畸形）| parse 状态 + cap-hit |

**关键区分**（owner 原话）：合法 JSON ≠ 正确工作流；高 Bag-F1 ≠ 依赖正确。

## 1. 三阶段设计

### 阶段 1（CPU，本机，即日）：Planner 侧失败拆解
数据：P0 dev 1,852 行（Arm A 768 预测逐行 + PLANNER_UNIFIED_EVAL_P0.json 384-era 逐行）。
输出：六类失败模式的分布 + 逐 family 缺失表 + 循环展开率。**零 GPU**。

### 阶段 2（需资产同步或 GPU 窗口）：QGIS 侧失败拆解
数据：route2_C0 dev 预测（0.5611 那版的逐行，在笔记本 `E:\Route2_Migration_20260928\RENTED_SERVER_PULL_20261005` 或需重推 dev-120）。
输出：算子选择错误 vs 顺序 vs links vs 缺步的分布（QGIS 侧四能力定位）。
**依赖**：owner 从笔记本同步 C0 预测 artifact，或下一 GPU 窗口重推。

### 阶段 3（综合）：瓶颈定位
跨阶段 1/2 对比 + 训练数据覆盖核查（对照 1,334 条 v2a 训练集的 family/算子覆盖 vs 失败集中区），输出：**首要瓶颈裁定建议**（工作流推理 / grounding / 数据覆盖 / 生成控制，允许并列但排序）。

## 2. 判读规则（预注册，防"又一轮调整循环"）

- 每类失败占比 × 与训练数据的对照 → 归因到"模型没学会（数据/目标问题）"或"模型学会了但生成失控（控制问题）"或"评价指标问题"；
- **只对归因为首要瓶颈的类别立项下一实验**；P1/解码干预/数据扩充全部降为候选，服从定位结果；
- 无论结果好坏，本实验的产出都是"消除一项关键不确定性"。

## 3. 阶段 1 失败分型（预注册）

| 码 | 模式 | 判据（单行） |
|---|---|---|
| X1 格式截断 | 输出未闭合 | parse fail 且 cap_hit=1 |
| X2 格式畸形 | 其余 parse fail | parse fail 且 cap_hit=0 |
| X3 重复失控 | 同族连续展开 ≥3 次（repeat=1 形态，应为一组 repetition_group） | pred_text 模式 |
| X4 阶段缺失 | gold 有而预测无的 family（按 family 计） | family diff |
| X5 阶段捏造 | 预测有而 gold 无的 family | family diff |
| X6 计数错误 | family 对但 repeat/次数错 | multiset diff |
| X7 顺序错误 | family multiset 对但 LCS<exact | LCS vs bag |
| X0 基本正确 | exact_seq | — |

行可同时命中多码（如 X3+X4）；分布按"行主因"+“family 缺失频次”双口径报告。
