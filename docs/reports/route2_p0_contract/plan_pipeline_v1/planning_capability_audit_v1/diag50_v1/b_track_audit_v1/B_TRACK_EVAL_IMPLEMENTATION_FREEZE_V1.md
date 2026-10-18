# 评估实现与训练配置冻结 V1（2026-10-18）

- **状态**：部分冻结——指标口径、边界测试计划、代码哈希已完成；评估器实现与训练配置待完成。

## 指标实现口径

| 指标 | 公式/口径 |
| --- | --- |
| NSR（首要） | 任务级 `|pred∩gold|/|gold|`，任务组 bootstrap；语义匹配为主、算子严格为辅 |
| TCC | 逐任务正确约束数/必需约束数（时间/区域/指标/数据/输出） |
| DRC | 金标依赖边满足比例（仅有依赖标注的任务） |
| 有害/多余步骤率 | 不在金标且改变结果的步骤/预测步骤数 |
| 长链退化 | 预定义长链子集（上四分位且≥20 步）上的 NSR/DRC |
| 解析健康 | parse/invalid/hit_cap/termination 分项 |
| 异常项 | 空工作流/相邻重复/未链接步骤，附样例 |

## 必要步骤匹配表 schema

`gold_step_id / gold_intent / operator_family / allowed_operator_ids / matching_level / evidence_ref / frozen`；
映射表随评估集冻结，不由模型自评。

## 边界测试

- parse 失败、截断、空工作流、相邻重复、未链接步骤、长链——预期行为见 JSON；
- 每项须有样例与计数，不得合并成一个总分。

## 训练配置模板（待冻结）

- 基座 Qwen3.5-9B-Base；QLoRA r16/α32 NF4；seed 20261018；decode rep-pen 1.15；
- 预算 pending owner；checkpoint 选择仅用 val NSR；test 不参与；
- 评估器版本与训练配置在启动前冻结并记录哈希。

## 代码/数据哈希

| 文件 | SHA-256（前 16） |
| --- | --- |
| `b_track_full_corpus_split_v1.py` | `519217cfb08afdbd` |
| `B_TRACK_ABC_EXPERIMENT_PROTOCOL_V1.json` | `79c5fb42e84f4d89` |
| `B_TRACK_RELATION_ADMISSION_FREEZE_V1.json` | `7cdc14d2e4804f12` |
| `B_TRACK_SPLIT_MANIFEST_V2.json` | `9cdb2e8db264f277` |
| `pool_b1_gee_stage_train.jsonl` | `09c37104d2fd3313` |

## 第 7 项状态

`partial`：指标口径/边界计划/哈希账本完成；评估器实现与训练配置未冻结。
