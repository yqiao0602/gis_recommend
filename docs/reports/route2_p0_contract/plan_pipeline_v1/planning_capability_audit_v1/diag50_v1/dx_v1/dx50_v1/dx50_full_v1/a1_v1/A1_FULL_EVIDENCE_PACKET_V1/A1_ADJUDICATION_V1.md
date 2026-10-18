# A1 逐对裁决 V1.1（owner 六条裁决已并入；其余 46 对=agent 裁决待抽检）

规则：A1_OWNER_ADJUDICATION_V1.md + owner 五条横切规则（R1-R5，见 A1_OWNER_RULINGS_V1.md）。NODEC（空输出）不入四指标；截断=不可判（R2）。

## 四指标（owner 裁决后）

| 指标 | 对照 v0_4 | 实验 v0_5 |
|---|---|---|
| 形成判定步数 | 30 | 24 |
| 正确选择 | 6 (20.0%) | 9 (37.5%) |
| 错误选择 | 1 (3.3%) | 3 (12.5%) |
| 合理弃权 | 23 (76.7%) | 12 (50.0%) |
| 误弃权 | 0 | 0 |
| 证据不足不可判（截断等） | 14 | 20 |
| 无判定（空输出，不计入） | 8 | 8 |

## 逐对裁决（★owner=owner 已裁决；其余待抽检）

| 步骤 | 批次 | 对照 | 实验 | validity 对照/实验 | 机制 | 状态 |
|---|---|---|---|---|---|---|
| PCA2-T-009#S3 | P1 | reasonable_abstention | wrong_selection | valid/valid | 其他——功能泛化型错误选择，可能受上下文影响（补卡⇒错误：间接，未认定直接因果） | ★owner |
| PCA2-T-009#S6 | P1 | reasonable_abstention | indeterminate | valid/valid | 其他——卡面暴露分类器配置入口，但关键枚举证据缺失 | ★owner |
| PCA2-T-042#S1 | P1 | reasonable_abstention | n/a_no_decision | valid/no_decision | 其他——实验臂空输出（无判定），不能评价为能力改善或退化 |  |
| PCA2-T-056#S5 | P1 | reasonable_abstention | n/a_no_decision | valid/no_decision | 其他——实验臂无闭合决策（空输出），不构成卡片补全效果证据 |  |
| PCA2-T-056#S6 | P1 | reasonable_abstention | indeterminate | truncated/valid | 其他（待 P2/官方文档） |  |
| PCA2-T-083#S6 | P1 | reasonable_abstention | n/a_no_decision | truncated/no_decision | 生成波动 |  |
| PCA2-T-083#S7 | P1 | indeterminate | correct_selection | valid/valid | 补卡解锁正确选择 |  |
| PCA2-T-084#S2 | P1 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他（能力边界经卡面明确化） |  |
| PCA2-T-084#S5 | P1 | reasonable_abstention | n/a_no_decision | truncated/no_decision | 生成波动 |  |
| PCA2-T-090#S4 | P1 | indeterminate | correct_selection | truncated/valid | 其他——卡面补全使已有正确候选的功能变得可验证（非新增候选解锁） | ★owner |
| PCA2-T-092#S9 | P1 | indeterminate | reasonable_abstention | truncated/valid | 其他——复合步骤能力边界识别；不能归因为补卡解锁 | ★owner |
| PCA2-T-001#S3 | P3 | indeterminate | correct_selection | truncated/valid | 补卡解锁正确选择 |  |
| PCA2-T-001#S4 | P3 | reasonable_abstention | indeterminate | truncated/truncated | 生成波动 |  |
| PCA2-T-001#S5 | P3 | indeterminate | reasonable_abstention | truncated/truncated | 其他 |  |
| PCA2-T-001#S6 | P3 | wrong_selection | reasonable_abstention | truncated/valid | 其他（对照错误被纠正为合理弃权） |  |
| PCA2-T-025#S5 | P3 | indeterminate | indeterminate | truncated/valid | 其他——目标变换语义证据不足（线性拉伸能力缺少明确证据） |  |
| PCA2-T-046#S4 | P3 | correct_selection | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-046#S5 | P3 | correct_selection | wrong_selection | valid/valid | 其他——冗余双选（补卡诱发未认定，按 R5 保守归因） |  |
| PCA2-T-056#S3 | P3 | indeterminate | wrong_selection | truncated/valid | 其他——步骤目标覆盖不足（补卡诱发未认定） |  |
| PCA2-T-060#S1 | P3 | reasonable_abstention | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-062#S4 | P3 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-073#S1 | P3 | reasonable_abstention | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-079#S5 | P3 | n/a_no_decision | reasonable_abstention | no_decision/truncated | 其他 |  |
| PCA2-T-086#S4 | P3 | reasonable_abstention | indeterminate | truncated/truncated | 生成波动 |  |
| PCA2-T-089#S5 | P3 | reasonable_abstention | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-092#S5 | P3 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-003#S2 | P4 | reasonable_abstention | correct_selection | valid/valid | 补卡解锁正确选择 |  |
| PCA2-T-005#S3 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-005#S5 | P4 | indeterminate | indeterminate | valid/self_contradictory | 生成波动（自相矛盾输出） |  |
| PCA2-T-012#S3 | P4 | n/a_no_decision | reasonable_abstention | no_decision/truncated | 其他 |  |
| PCA2-T-021#S4 | P4 | reasonable_abstention | n/a_no_decision | truncated/no_decision | 生成波动 |  |
| PCA2-T-022#S6 | P4 | reasonable_abstention | indeterminate | valid/valid | 其他（待输入结构） |  |
| PCA2-T-025#S4 | P4 | n/a_no_decision | correct_selection | no_decision/truncated | 其他（上下文诱发正确选择） |  |
| PCA2-T-026#S4 | P4 | correct_selection | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-032#S2 | P4 | reasonable_abstention | indeterminate | valid/valid | 其他——卡片补全暴露有效辐射定标能力，但任务要求超出单算子已证实能力 | ★owner |
| PCA2-T-033#S1 | P4 | indeterminate | correct_selection | truncated/truncated | 其他（上下文诱发正确选择） |  |
| PCA2-T-052#S2 | P4 | reasonable_abstention | indeterminate | truncated/truncated | 生成波动 |  |
| PCA2-T-056#S2 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-056#S4 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-057#S4 | P4 | indeterminate | correct_selection | truncated/valid | 补卡解锁正确选择 |  |
| PCA2-T-068#S4 | P4 | indeterminate | reasonable_abstention | truncated/valid | 其他——从开放式推理转为明确弃权；不能证明补卡收益 | ★owner |
| PCA2-T-068#S6 | P4 | indeterminate | correct_selection | truncated/truncated | 其他（上下文诱发正确选择） |  |
| PCA2-T-070#S1 | P4 | n/a_no_decision | correct_selection | no_decision/truncated | 其他（上下文诱发正确选择） |  |
| PCA2-T-079#S3 | P4 | reasonable_abstention | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-080#S4 | P4 | reasonable_abstention | n/a_no_decision | truncated/no_decision | 生成波动 |  |
| PCA2-T-081#S5 | P4 | indeterminate | reasonable_abstention | truncated/truncated | 其他 |  |
| PCA2-T-084#S4 | P4 | indeterminate | reasonable_abstention | truncated/valid | 其他 |  |
| PCA2-T-086#S5 | P4 | reasonable_abstention | indeterminate | truncated/truncated | 生成波动 |  |
| PCA2-T-089#S4 | P4 | correct_selection | indeterminate | valid/truncated | 生成波动 |  |
| PCA2-T-092#S2 | P4 | correct_selection | indeterminate | valid/truncated | 生成波动（正确→无判定） |  |
| PCA2-T-098#S1 | P4 | reasonable_abstention | indeterminate | truncated/truncated | 生成波动 |  |
| PCA2-T-098#S6 | P4 | correct_selection | indeterminate | valid/truncated | 生成波动 |  |

## 六条 owner 裁决要点

- **PCA2-T-009#S3**：control=reasonable_abstention / experiment=wrong_selection（validity valid/valid）——其他——功能泛化型错误选择，可能受上下文影响（补卡⇒错误：间接，未认定直接因果）
- **PCA2-T-009#S6**：control=reasonable_abstention / experiment=indeterminate（validity valid/valid）——其他——卡面暴露分类器配置入口，但关键枚举证据缺失
- **PCA2-T-032#S2**：control=reasonable_abstention / experiment=indeterminate（validity valid/valid）——其他——卡片补全暴露有效辐射定标能力，但任务要求超出单算子已证实能力
- **PCA2-T-068#S4**：control=indeterminate / experiment=reasonable_abstention（validity truncated/valid）——其他——从开放式推理转为明确弃权；不能证明补卡收益
- **PCA2-T-092#S9**：control=indeterminate / experiment=reasonable_abstention（validity truncated/valid）——其他——复合步骤能力边界识别；不能归因为补卡解锁
- **PCA2-T-090#S4**：control=indeterminate / experiment=correct_selection（validity truncated/valid）——其他——卡面补全使已有正确候选的功能变得可验证（非新增候选解锁）

## 核心判据分解（动态计算）

- 合理弃权→正确选择（直接命中）：1 对 ['PCA2-T-003#S2']
- 机制标注『补卡解锁正确选择』：4 对 ['PCA2-T-083#S7', 'PCA2-T-001#S3', 'PCA2-T-003#S2', 'PCA2-T-057#S4']
- 截断→正确选择：6 对 ['PCA2-T-083#S7', 'PCA2-T-090#S4', 'PCA2-T-001#S3', 'PCA2-T-033#S1', 'PCA2-T-057#S4', 'PCA2-T-068#S6']
- 空输出→正确选择：2 对 ['PCA2-T-025#S4', 'PCA2-T-070#S1']
- 正确→正确：0 对 []
- 正确→错误（破坏）：1 对 ['PCA2-T-046#S5']