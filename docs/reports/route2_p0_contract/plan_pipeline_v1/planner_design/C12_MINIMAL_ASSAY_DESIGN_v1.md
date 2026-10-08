# C1-2 重新定义后的最小 assay 设计（v1，2026-10-05，待 owner 批准）

> 依据 owner 概念修正（`8259bab`）：C1-2 = **"加入 GEE 学到的 workflow reasoning 后，
> 模型选择和组合 QGIS operators 的能力有没有提升？"**——同任务双臂对照，
> 唯一变量 = GEE blueprint 预训练的有无。本文档为 assay 设计提案，**未经批准不执行**。

## 1. 双臂设计（最小因果对照）

| | **C0-QGIS 臂** | **A1'-QGIS 臂** |
|---|---|---|
| 起点 | Base Qwen3.5-9B（fresh） | **Planner-v2 formal adapter**（GEE blueprint SFT 1,041 步，已冻结在位） |
| QGIS SFT | v2a_A_train 1,334 行，1 epoch | **完全相同**（同数据/同超参/同预算） |
| 唯一变量 | 无 GEE blueprint 预训练 | 有 GEE blueprint 预训练 |

- **两臂 QGIS SFT 完全同构**：同 1,334 行、同 epochs/超参、同 evaluator——
  任何 dev/test 差异只能归因于 GEE blueprint 预训练的存在；
- 成本：每臂 1,334 行 / 32 ≈ 42 steps × ~31s ≈ **22 分钟**；双臂合计 **~45 分钟 GPU**。

## 2. 评测口径（QGIS operator 选择与组合）

在 v2a_A_dev（120 行，两臂均未训练）上评测：

| 指标 | 定义 |
|---|---|
| **Op selection F1** | 预测 operator_id 序列 vs gold 的 bag-F1（多重集） |
| **Op sequence F1** | LCS-F1（顺序敏感） |
| **Exact graph rate** | processes+links 完全匹配率 |
| **Graph edit distance** | 预测图 vs gold 图的最小编辑距离（节点+边） |
| Operator coverage | 预测的 distinct operator 数 / gold distinct 数 |
| 长度比 | 预测 process 数 / gold process 数 |

三参照：① Base 零样本（无 SFT 下限）② C0-QGIS 臂（核心对照）③ 历史 Planner-v1
bag-F1 0.6718（不同粒度，仅参考）。

## 3. 判读树

- **A1' > C0 显著** → GEE blueprint 预训练**正向迁移到 QGIS grounding** →
  两层架构的核心假设成立 → Planner-v3 = GEE reasoning + QGIS grounding 正式路线；
- **A1' ≈ C0** → GEE 先验无增益 → 稀缺问题需另行解决（QGIS 数据增广/缩小目标）；
- **A1' < C0** → Gate 2 式负迁移复现（blueprint 预训练干扰 QGIS 学习）→
  重大设计警示。

## 4. 前置条件与风险

1. **P1-C 遗留**：Planner-v2 formal adapter = GEE blueprint 训练后的权重（无 P1-C 加权，
   该实验已暂停）——起点干净 ✓；
2. **operator_id 直接学习**：QGIS SFT 目标含 309 真实算子 ID（owner 裁定第一版
   不抽象化）——309 类分类对 1,334 行 SFT 是可行的学习任务；
3. **变量级 I/O 暂缺**：第一版 links 为 process 级（owner 裁定 ✓），typed I/O 留待
   Phase 3；
4. **门控风险**：QGIS 数据 1,334 行较小，双臂都可能欠拟合——判读以**相对差异**为准
   （A1' vs C0），非绝对分数；
5. **locked test-111（v2a_A_test）不动**：双臂均在 dev-120 上评测；test 留给最终裁定。

## 5. 执行清单（批准后）

1. 构建 QGIS SFT 训练文件（v2a_A_train 1,334 行 → Stage1PlanCollator 行格式，CPU）；
2. 写两份 config（c0_qgis.yaml 从 Base 起 / a1_qgis.yaml 从 Planner-v2 adapter 起——
   后者需确认 trainer 支持 adapter 初始化（P0 遗留问题：trainer 从 Base 加载，
   A1' 臂需从 Planner-v2 adapter 起步——实现方式 = 将 Planner-v2 adapter 预合并到
   base 权重，或修改 trainer 加载逻辑——**需 owner 批准实现方式**）；
3. 双臂各 1 epoch（~25 min/臂）；
4. dev-120 评测（E 系列 + S 系列）；
5. 对照报告 → owner 裁定。

## 6. 状态

- 本文档为设计提案；**未执行任何训练/GPU**；冻结物未动；
- Planner-v2 formal adapter 在位（stage1_run_planner_v2/stage1_adapter）；
- GPU 空闲。
