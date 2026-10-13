# PCA Stage-2 原链一致性审计报告 v1（2026-10-13）

> 账本：`pca_b_chain_audit_v1.json`（SHA `2433e51e7ae5a930`，19 行）。
> 绑定：金标 `0dc643980e8d4b8e`（唯一当前版本）× 冻结题面 `1a13ad8d…` × 原链源
> dev-120（frozen benchmark，processes/links 零转录提取）。
> 协议：`pca_chain_audit_labels_v1.md`（round-7 收口版）。

## 1. 主标签分布

| 标签 | 数量 | wid |
|------|------|-----|
| CONSISTENT | 13 | W000473 W068342 W067404 W000635 W033927 W056274 W067268 W055908 W055494 W067092 W007046 W000674 W055913 |
| PARTIALLY_CONSISTENT | 5 | W068582 W000890 W066995 W068833 W055534 |
| INCONSISTENT | 1 | W056058 |
| UNDERDETERMINED | 0 | —（无人定维度决定整链可判定性；维度级不确定性 5 条均以 dimension_evidence 记录，未升级） |

ESCALATE-OWNER：**W056058**（唯一）——INCONSISTENT 判定 + 任务可用性需 owner 裁定。

## 2. 各判定依据摘要

- **CONSISTENT 13 条**：链满足冻结题面语义与全部可判硬约束（W067268 按 round-7 主标签
  边界仅评结构四因素 + 数值合规记 DIM-UNDERDETERMINED；W068342 仅结构筛选 + CRS，
  约束绑定维度不可判不参与）。
- **PARTIALLY_CONSISTENT 5 条**（核心 outcome 主干在，尾部/编排缺失照实记录）：
  - W068582：缺 Manning 查找赋值 + 面积计算（链仅 重投影→修复→裁剪）；
  - W000890：缺市政分区面积聚合/主导选择 + 表格输出（等级优先差分 + 相交在）；
  - W066995：缺要素服务获取 + GeoPackage 导出/样式（范围限制 + 合并在）；
  - W068833：缺多栅格循环表示 + 参数 manifest（warp 对齐在）；
  - W055534：缺多指标×年份循环表示 + CSV 导出（单实例分区统计在）。
- **INCONSISTENT 1 条**：
  - W056058：链 = clip + 单一 buffer；任务要求的三级分离、三差异化半径、逐级输出结构
    **完全缺失**——产出结构与 required_outcome 结构不符。

## 3. 元发现（owner 需知，影响后续解读）

**dev-120 原链是 Processing 算子链，Python/PyQGIS 层操作不在链中。** 5 条
PARTIALLY_CONSISTENT 中的 4 条（W068582/W066995/W068833/W055534）的缺失项均属此类
（属性计算、网络下载、文件导出、批处理循环在原脚本 Python 层完成，gold 链只捕获
Processing 调用）。这不是原链"错误"，而是**链表示力边界**：
- 对 Stage-2 审计：已照实记录为 missing_required_operations（判定依据 = 链内可见语义），
  未推测链外内容；
- 对 PCA 评测解读：当模型计划含"属性计算/导出/循环编排"步骤而原链没有对应算子时，
  **不应据原链判模型多余**——评分须以金标（题面语义）为准，原链只是审计参照。此点
  已由协议纪律 6 覆盖，此处为实证提示。

## 4. Owner 裁定清单

| wid | 事项 | 需裁定内容 |
|-----|------|-----------|
| W056058 | INCONSISTENT | 该任务是否保留在 PCA 审计池（原链与任务结构严重不符）；若保留，其评分基线如何处理（金标语义 vs 原链缺失） |

（其余 18 条 adjudication=NONE，无强制升级项。）

## 5. 下一步（owner 流程）

1. owner 审阅本报告 + 账本 + W056058 裁定；
2. Stage 3：A/C 组金标与配对（按冻结协议）；
3. Stage 4：评测账本冻结 → 才申请正式生成。
