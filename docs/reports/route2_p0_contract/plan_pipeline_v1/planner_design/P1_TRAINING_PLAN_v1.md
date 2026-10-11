# P1 训练执行计划 v1（FROZEN，owner 裁定 2026-10-11 晚）

## 裁定记录

- 批准进入 **P1 新表示监督训练**；暂不启动 RL、不叠加 decoding tricks
- 推论表述修正（三条裁定记录在案）：机制线索非因果证明；P0 不熟悉 ≠ 无泛化；需监督训练验证
- **因果归因核心比较**：P0（旧表示训练→旧表示评测）vs P1（新表示训练→新表示评测）；
  资源允许时加交叉评测（统一语义层），避免语法熟悉度误当任务能力

## 冻结基线（不再修改）

- P0 checkpoint：`/home/qy/stage1_run_planner_v2_fmt/stage1_adapter`（16MB）
- P0 基线数字：loss_old mean **0.0684** / p50 0.068 / p90 0.11；
  hit_cap **121/208**；三 SHA 对账与逐行明细见
  `p0_fit_diag/paired_fit_diagnostic.json`（已入库）

## 训练配置

| 项 | 值 |
|---|---|
| 起点 | 冻结 P0 checkpoint（`stage1_adapter`）|
| 数据 | 新金标 208 行（FREEZE_MANIFEST `c12ba7b6…`，五门全过）+ 防遗忘混合池 |
| 配方 | 与 P0 相同：QLoRA r16α32 NF4、lr 1e-4 cosine、eff batch 32（bs1×32 或 bs2×16 按显存）、max_len 1024 |
| epochs | 短程（先 2 epoch，看 dev 曲线再定是否加） |
| 推理 | 原始 greedy 384，无任何解码技巧 |
| 评测 | dev-1852 统一 6 指标 + hit_cap/循环 + 统一语义层表示（经各自 parser 归一后比较） |
| out-dir | 独立目录，不覆盖 P0 |

## 验证顺序（owner 裁定）

1. **dev 学习曲线**：新表示 teacher-forced loss、结构解析率、重复声明准确性——确认学会新语法
2. **同条件生成评测**：greedy、同 prompt、同评估器，P1(新表示) vs P0(旧表示)
3. **双条件判定**：终止改善（hit_cap/异常循环显著下降）**且** 任务保真（Ordered Stage-F1、重复模式保真不因欠生成恶化、关键步骤完整）
4. **评测细节**：P0 旧表示输出与 P1 新表示输出**各自经 parser 映射到统一语义工作流表示**后再比较——禁止直接比原始 JSON 字符串或未归一化语法指标

## 数据组装（开训前完成，质量门复查）

- 新金标 208 行（FREEZE_MANIFEST `c12ba7b6…`）转训练行格式
- 防遗忘混合池：planner_v2_train 无循环子集抽样（比例待数据组装时定，记录实际曝光权重）
- 禁止混入：循环截断生成、解码技巧产物、test-111 任何内容
