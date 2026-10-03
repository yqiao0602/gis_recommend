# R3-PLANNER-P0 结果报告（v1，2026-10-03，可行性实验）

> 依据 owner 放行（`769eef0`）：Task → Blueprint JSON 可行性验证，QLoRA 1 epoch，
> 独立目录，非正式 Stage-1。数据 33,339 train / 3,705 held-out（90/10，seed 20260924）。
> 训练 `[done]` 09:54（9.02h，1,694,098 tokens = A+B 全量的 6.9%，task_too_long=0）。
> 评测：独立诊断脚本（3,705 held-out 行逐条生成，greedy，max_new_tokens=192）。

## 1. 四指标全量结果（n=3,705）

| 指标 | 结果 | 对照 |
|---|---|---|
| **M1 Blueprint parse 率** | **1.0000** | Direct Generation 的 parse/有效率仅 ~15%（invalid 84.5-86.4%） |
| **M2 Family bag-F1**（冻结 gate 口径） | **0.6448** | Direct 0.499（**+14.6pp**）；R3-CD-4 线性组装器 0.60；oracle 0.846 |
| **M3 Count 精确匹配率** | 0.5027（每 family 次数完全命中） | — |
| **M4 Length** | exact 0.2443 / **±1 = 0.5231**；预测均值 5.98 vs gold ~8.4 | Planner 对长度偏保守 |

## 2. 判读（按 owner 预设判读带）

> **owner 措辞修正（2026-10-03，追加）**：不是"决定性证明 Task 信息充分"，
> 而是**在当前冻结数据、当前 bag-F1 口径和 P0 训练预算（仅 1.69M tokens feasibility run）下，
> 强支持 Planner 假说**。

- **0.6448 落在"成功"区间（>0.60），接近但未达"强提取"（0.75+）**。
- **核心假设获强支持**：Planner+RuleSerializer（0.645）> Direct Generation（0.499，+14.6pp）——
  **"一步生成完整 Plan"确实是瓶颈，而不是 Task 缺少 workflow 信息。**
- Planner（0.645）甚至超过了 R3-CD-4 的线性探针+规则组装器（0.60）——
  LLM 从 Task 中提取的信息**多于**线性可提取成分，说明有超出 TF-IDF 的语义利用。
- **M1 = 1.0000 本身就是重大对照**：Direct Generation 86% 输出无效（退回先验/格式崩塌），
  而结构化小目标下**格式问题完全消失**——保守化/回退先验是"任务太大"的症状，不是模型缺陷。

## 2b. 路线节点（owner 裁定，2026-10-03）

```text
R3-PLANNER-P0（可行性 ✓）
  ↓
R3-PLANNER-P1：count/length 专项监督（M3 0.5027 / M4 ±1 0.5231 为目标缺口）
  ↓
R3-PLANNER-P2：顺序敏感 Blueprint v2（当前 blueprint 不表达顺序）
  ↓
Stage-1 新正式候选 → Stage-2 QGIS Grounding
```

- **架构方向确立**：`Task → Structured Planner → Workflow Serializer → QGIS Grounding`，
  替代 `Task → 一次性生成完整 Workflow → QGIS Grounding`。
- **RL 继续冻结**；未来若引入，定位在结构化 Blueprint / QGIS Graph 的规划优化阶段，
  **不用于修补长文本生成**。
- 剩余缺口画像："做什么"已学得不错（M2 0.645），"做几次/做多长"偏弱（M3 0.50 / M4 ±1 0.52），
  "怎么排序"Blueprint v1 尚未表达（P2）。

## 3. 与诊断链的闭环

```text
R3-CD-3  组件信息在 Task 中（family AUC 0.913 / 转移 0.904 / 长度 F1 0.614）
R3-CD-4  组件可确定性组装（bag-F1 0.60）> Direct 0.499；oracle 0.846
R3-PLANNER-P0  LLM 可学会先做 Planner（0.645，parse 100%）✓✓
         → 剩余缺口 = count 分配（M3 0.50）+ 长度保守（M4），对应 oracle 差距（0.846−0.645）
```

## 4. 剩余缺口定位（⑦ 正式方案的改进点，供裁定）

1. **计数分配**（M3 0.50）：Planner 已输出 counts，但一半不准——可通过
   计数分布先验/更多 epoch/计数专项监督改进。
2. **长度保守**（预测 5.98 vs gold 8.4）：训练分布 + 生成倾向；±1 内 52% 说明量级感存在。
3. **顺序**：blueprint 不含顺序（bag 口径兼容）；未来顺序敏感口径需 schema v2
   （ordered stages/DAG），已在前报告登记。

## 5. 状态与建议

- 产物：`planner_p0_eval_metrics.json`（metrics + 3,705 条逐项记录，本目录）。
- **建议（供 owner 裁定）**：⑥ 对比已达成（0.645 > 0.499）→ 可进入
  **⑦ 正式 Planner→Serializer Stage-1 重设计**（planner 多任务头/计数专项/长度校准 +
  serializer 规则固化 + 顺序敏感评测口径设计）；原冻结 Stage-1 v2_2 主线与 gate 保持不动，
  新路线作为并行候选，切换与否归 owner。
- 监控自动化继续在岗（无盯守对象，例行检查）。
