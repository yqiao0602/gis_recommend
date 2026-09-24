# ⑥-2 Plan Contract Audit 完成报告 v1（2026-09-24，owner 裁定：条件 PASS）

## 总裁定

> **⑥-2 PASS**：当前 v1.2 Plan Contract 已通过全量 P2–P4 自动审计及 48 条
> 分层 P1 人工审计。Plan 可作为 Stage-1 Workflow Reasoning 的候选监督
> 接口，但**训练池不等同于全部 59,835 个转换结果**；已识别的 D-MOD-01
> 与 F-STRUCT-01 作为已登记限制和质量过滤条件保留。

## Contract Audit 四维结果

### A. P1 Semantic Fidelity（48 条分层人工审计，高风险过采样）

| 判定 | 数量 | 占比 | 说明 |
|---|--:|--:|---|
| 保真 | 24 | 50.0% | 核心数据流/操作意图完整可恢复 |
| 偏差 | 21 | 43.8% | 核心 workflow 可恢复，存在 D-MOD-01 局部归属错误或 utility 噪声 |
| 失败 | 2 (+1 边缘) | 4.2% | 全部为 F-STRUCT-01 |

**P1a Chain→Plan**：判定边界 =「核心数据流/操作意图是否仍可恢复」。
**P1b Task→Plan**：fragment_chain 单列（DATA-FRAG ×4：B3#2/#9/#10、
B5#5）——converter 忠实转换残缺输入不构成 converter 缺陷。

批次分布：B1 2/6/1 · B2 6/4/0 · B3 5/4/1(追溯修正后) · B4 6/4/0 · B5 5/3/0。

### B. P2 Typed-I/O：PASS

plan-level **0.9508**（59,835 全量）。断裂已按 owner 要求分解：
ctor-induced legitimate branch 与 genuine mismatch 分开统计。

### C. P3 Slot-role：PASS（带累积效应说明）

**step-level 0.953 / plan-level 0.7990**。落差主因 = 长链尾部 slot-role
稀疏的累积效应，非全步普遍缺失。两个数字并列保留。

### D. P4 De-identification：PASS

**59,835 / 59,835 = 100%**。三层验证：schema MUST-REMOVE +
renderer 检查 + 全量 leakage scan。

## 三条冻结限制

### F-STRUCT-01（Known Failure Family）

连续无消费 provision（裸 Image/Feature/Collection ctor 连跑 ≥3）导致
线性化不可恢复。确认 2 例 + 边缘 1 例，全部有 reason 落盘。**不修改
当前 converter**；`≥3 provision → fail-closed` 规则留待下一版工程，
不回填本轮审计。

### D-MOD-01（Known Limitation）

**modifier/reducer attribution error under linearized multi-branch or
multi-block context**。亚型：a) cross-branch bleed；b) cross-block
bleed（reducer 附到下一块首 filter）；c) wrong tail-host attachment。
这是 Stage 1 = Linear Workflow Reasoning 边界的实证支撑，非 converter
缺陷；DAG recovery 属 Stage 2 职责。

### DATA-FRAG（Data Quality Flag）

fragment/truncated canonical chain 与 converter 质量分开统计
（P1b 维度）。

## 关键实证结论

1. **长链 ≠ 低保真**：B4#8（65 token、8 月度块、双层分类器栈）完整
   忠实；B2#5/#10、B5#1/#7 同证。结构信息丢失（branch provenance /
   消费关系）才是风险变量，长度本身不是。
2. **重复 ≠ 失真**：月度循环、多预测子、多源 collection 的顺序重复
   在线性 plan 中忠实保留。
3. **失败可识别、可隔离、有因**：唯一失败家族 F-STRUCT-01 有明确
   结构特征与 reason 记录，无第二种独立 failure family 出现。
4. **必要层有量化保证**：Audit-A 实证的 typed I/O + slot roles 两个
   MUST-PRESERVE 层，在已转换行实测 99.2% / 95.3%。

## 训练池定义（措辞冻结）

> 训练池不再等同于全部 59,835 个 converter 输出。实际训练池由自动
> 审计通过且满足既定质量门槛的候选 Plan 构成；P1 人审发现的已知偏差
> 类型作为过滤/标记依据，而不以 48 条样本比例直接估计全量可用率。

**禁止表述**：把 50% 当成 59,835 的训练池通过率；把 48 条比例外推全量。

## 工程资产与产物

- 转换器：`route2_training/plans/chain_to_plan_v1_1.py`（R1-R4 规则冻结）
- 知识表：`gee_op_knowledge_v1_2.py`（v1.2 冻结，123+9+31 条）
- Coverage：`plan_pipeline_v1/coverage_report_round2.json`
  （46.6% chain / 80.3% token）
- Pilot：`pilot_human_audit_48.jsonl` + 五批审计记录 `_p1_batch1-5.txt`
- Profile：`qgis_operator_capability_profile_v0_4.json`（test-111 148/148）

## 下一步

⑥-3（Plan quality 分级）/ ⑥-4（open-set grounding sufficiency）/
⑥-5（B2 数据准备）按 ⑥ 冻结序列推进。Stage-1 训练启动仍需 owner
单独批准；Teacher Plan 生成仍以 Capability Gate PASS 为前置。
