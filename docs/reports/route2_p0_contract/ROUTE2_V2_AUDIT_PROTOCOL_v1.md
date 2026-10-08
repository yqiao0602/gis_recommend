# Route-2 v2 Current Best Model Audit 协议（AUDIT PROTOCOL v1，FROZEN）

冻结：2026-09-30，owner 裁定。本协议是 Performance-First Phase 的**总开关**。

## 冻结规则（一句话口径）

> **Current Best Model is selected exclusively on the frozen QGIS dev-120
> `processes + links` benchmark under a unified inference and evaluation
> protocol. Planner metrics are diagnostic intermediate metrics; QGIS
> test-111 remains held out for final evaluation and is not used for model
> selection.**

## 1. 主基准与两级基准分工

- **Primary / model selection**：QGIS **dev-120** `processes + links`
  （opF1 / linkF1 / graph 指标 + parse；与旧三臂、Phase R 数字直接可比）
- **Final held-out**：**test-111**——只做最终一次性报告，**禁止用于模型选择**
- **Diagnostic only**：Planner unified 6-metric（1,852 dev）——`.682` 等 Planner
  数字**不再是冠军判据**，仅中间能力诊断

## 2. 统一推理条件（所有候选必须一致，缺一不可）

base model / checkpoint / adapter / prompt template / max_new_tokens /
temperature / top_p / do_sample / JSON-schema 约束 / post-processing /
evaluation parser——**历史模型不豁免**：route2_C0 必须同机同协议重放，
其历史 0.5611 仅作为"该 checkpoint 的既往成绩"参考，本次以重放读数入表。

## 3. Current Best Model 判定规则

1. **第一排序**：dev-120 主指标（同协议同推理条件下的 opF1 等主指标）最高者
2. **第二排序（主指标接近时）**：灾难行为率低者优先——
   parse failure / empty graph / invalid operator / invalid links or
   malformed graph / runaway-truncation / task-irrelevant output
3. test-111 永不参与选择

## 4. 候选与产物就位状态

| 候选 | 权重/adapter | 协议核验 |
|---|---|---|
| **route2_C0 ep20**（历史冠军，dev opF1 0.5611@mdzhang `gee_llm_smoke/route2_C0/qgis_sft_ep20/`） | ✅ mdzhang 原盘 + 双备份 | 需同协议重放 |
| C0-QGIS twin（裸 Base + 41 步 QGIS SFT） | ✅ RENTED_PULL | ✅ 单变量=init 已验 |
| A1'-QGIS twin（Planner-v2 merged + 同 41 步） | ✅ RENTED_PULL | ✅ 单变量=init 已验 |
| Planner-v2-fmt（P0 续训完成后）+ Grounding | 训练中 | grounding 接线后入表 |
| Planner-v1/v2 + Grounding | adapter 在 RENTED_PULL | grounding 接线后入表 |

## 5. 执行序列（Phase-1 范围内，不新增研究问题）

```
P0 续训完成（mdzhang，进行中）
  → C0-QGIS dev-120 评测
  → A1'-QGIS dev-120 评测
  → route2_C0 ep20 同机同协议重放
  → （Planner+Grounding 就绪后补行）
  → 统一总表：Model / route / opF1 / parse / empty / invalid-op /
              invalid-graph / truncation / Overall
  → Current Best Model 判定 → 下一轮 Performance Optimization
```

## 6. 评测管线纪律

- dev-120 评测使用 `evaluate_dev.py` 管线；Phase R 注册的
  **evaluator-repair（same-process）条款**适用于本次全部评测（工程必要性，
  owner 已在 paired-eval 放行中覆盖）
- 评测输出逐件落 `progress.md` + 仓库 commit（产物规则
  `RENTED_BOX_ARTIFACT_POLICY_v1.md` 同步适用于 mdzhang 产物）
- 冻结期内**不做**：benchmark 重设计 / multi-solution 全面重做 / RL /
  大规模新数据 / 消融 / GEE 贡献归因 / 从零训练基座
