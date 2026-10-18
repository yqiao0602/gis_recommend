# A1 逐对裁决 V1.1（owner 六条裁决已并入；其余 46 对=agent 裁决待抽检）

规则：A1_OWNER_ADJUDICATION_V1.md + owner 五条横切规则（R1-R5，见 A1_OWNER_RULINGS_V1.md）。NODEC（空输出）不入四指标；截断=不可判（R2）。

## 四指标（owner 裁决后）

| 指标 | 对照 v0_4 | 实验 v0_5 |
|---|---|---|
| 形成判定步数 | 29 | 25 |
| 正确选择 | 4 (13.8%) | 11 (44.0%) |
| 错误选择 | 3 (10.3%) | 2 (8.0%) |
| 合理弃权 | 22 (75.9%) | 12 (48.0%) |
| 误弃权 | 0 | 0 |
| 证据不足不可判（截断等） | 13 | 17 |
| 无判定（空输出，不计入） | 10 | 10 |

## 逐对裁决（★owner=owner 已裁决；其余待抽检）

| 步骤 | 批次 | 对照 | 实验 | validity 对照/实验 | 机制 | 状态 |
|---|---|---|---|---|---|---|
| PCA2-T-009#S3 | P1 | reasonable_abstention | wrong_selection | valid/valid | 其他——功能泛化型错误选择，可能受上下文影响（补卡⇒错误：间接，未认定直接因果） | ★owner |
| PCA2-T-009#S6 | P1 | reasonable_abstention | indeterminate | valid/valid | 其他——卡面暴露分类器配置入口，但关键枚举证据缺失 | ★owner |
| PCA2-T-042#S1 | P1 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-056#S5 | P1 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-056#S6 | P1 | reasonable_abstention | indeterminate | valid/valid | 其他（待 P2/官方文档） |  |
| PCA2-T-083#S6 | P1 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-083#S7 | P1 | indeterminate | correct_selection | valid/valid | 选择保持（算子替换、实验臂证据更充分） |  |
| PCA2-T-084#S2 | P1 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他（能力边界经卡面明确化） |  |
| PCA2-T-084#S5 | P1 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-090#S4 | P1 | indeterminate | correct_selection | truncated/valid | 其他——卡面补全使已有正确候选的功能变得可验证（非新增候选解锁） | ★owner |
| PCA2-T-092#S9 | P1 | indeterminate | reasonable_abstention | truncated/valid | 其他——复合步骤能力边界识别；不能归因为补卡解锁 | ★owner |
| PCA2-T-001#S3 | P3 | indeterminate | correct_selection | truncated/valid | 补卡解锁正确选择 |  |
| PCA2-T-001#S4 | P3 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-001#S5 | P3 | indeterminate | reasonable_abstention | truncated/valid | 其他 |  |
| PCA2-T-001#S6 | P3 | wrong_selection | reasonable_abstention | valid/valid | 其他（对照错误被纠正为合理弃权） |  |
| PCA2-T-025#S5 | P3 | indeterminate | correct_selection | truncated/valid | 补卡解锁正确选择 |  |
| PCA2-T-046#S4 | P3 | correct_selection | indeterminate | valid/valid | 生成波动（正确→无判定） |  |
| PCA2-T-046#S5 | P3 | correct_selection | correct_selection | valid/valid | 选择保持（实验臂增加冗余算子） |  |
| PCA2-T-056#S3 | P3 | indeterminate | wrong_selection | truncated/valid | 补卡诱发错误选择（部分匹配/上下文） |  |
| PCA2-T-060#S1 | P3 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-062#S4 | P3 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-073#S1 | P3 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-079#S5 | P3 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-086#S4 | P3 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-089#S5 | P3 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-092#S5 | P3 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-003#S2 | P4 | n/a_no_decision | correct_selection | valid/valid | 补卡解锁正确选择 |  |
| PCA2-T-005#S3 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-005#S5 | P4 | indeterminate | indeterminate | valid/self_contradictory | 生成波动（自相矛盾输出） |  |
| PCA2-T-012#S3 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-021#S4 | P4 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-022#S6 | P4 | reasonable_abstention | indeterminate | valid/valid | 其他（待输入结构） |  |
| PCA2-T-025#S4 | P4 | n/a_no_decision | correct_selection | no_decision/valid | 其他（上下文诱发正确选择） |  |
| PCA2-T-026#S4 | P4 | wrong_selection | indeterminate | valid/valid | 生成波动（对照错误→无判定） |  |
| PCA2-T-032#S2 | P4 | reasonable_abstention | indeterminate | valid/valid | 其他——卡片补全暴露有效辐射定标能力，但任务要求超出单算子已证实能力 | ★owner |
| PCA2-T-033#S1 | P4 | indeterminate | correct_selection | truncated/valid | 其他（上下文诱发正确选择） |  |
| PCA2-T-052#S2 | P4 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-056#S2 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-056#S4 | P4 | n/a_no_decision | reasonable_abstention | no_decision/valid | 其他 |  |
| PCA2-T-057#S4 | P4 | indeterminate | correct_selection | truncated/valid | 补卡解锁正确选择 |  |
| PCA2-T-068#S4 | P4 | indeterminate | reasonable_abstention | truncated/valid | 其他——从开放式推理转为明确弃权；不能证明补卡收益 | ★owner |
| PCA2-T-068#S6 | P4 | indeterminate | correct_selection | truncated/valid | 其他（上下文诱发正确选择） |  |
| PCA2-T-070#S1 | P4 | n/a_no_decision | correct_selection | no_decision/valid | 其他（上下文诱发正确选择） |  |
| PCA2-T-079#S3 | P4 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-080#S4 | P4 | reasonable_abstention | n/a_no_decision | valid/no_decision | 生成波动 |  |
| PCA2-T-081#S5 | P4 | indeterminate | reasonable_abstention | truncated/valid | 其他 |  |
| PCA2-T-084#S4 | P4 | n/a_no_decision | reasonable_abstention | valid/valid | 其他 |  |
| PCA2-T-086#S5 | P4 | reasonable_abstention | indeterminate | valid/valid | 生成波动 |  |
| PCA2-T-089#S4 | P4 | correct_selection | indeterminate | valid/valid | 生成波动（正确→无判定） |  |
| PCA2-T-092#S2 | P4 | correct_selection | indeterminate | valid/valid | 生成波动（正确→无判定） |  |
| PCA2-T-098#S1 | P4 | reasonable_abstention | n/a_no_decision | valid/valid | 生成波动 |  |
| PCA2-T-098#S6 | P4 | wrong_selection | n/a_no_decision | valid/no_decision | 生成波动（对照错误→无判定） |  |

## 六条 owner 裁决要点

- **PCA2-T-009#S3**：control=reasonable_abstention / experiment=wrong_selection（validity valid/valid）——其他——功能泛化型错误选择，可能受上下文影响（补卡⇒错误：间接，未认定直接因果）
- **PCA2-T-009#S6**：control=reasonable_abstention / experiment=indeterminate（validity valid/valid）——其他——卡面暴露分类器配置入口，但关键枚举证据缺失
- **PCA2-T-032#S2**：control=reasonable_abstention / experiment=indeterminate（validity valid/valid）——其他——卡片补全暴露有效辐射定标能力，但任务要求超出单算子已证实能力
- **PCA2-T-068#S4**：control=indeterminate / experiment=reasonable_abstention（validity truncated/valid）——其他——从开放式推理转为明确弃权；不能证明补卡收益
- **PCA2-T-092#S9**：control=indeterminate / experiment=reasonable_abstention（validity truncated/valid）——其他——复合步骤能力边界识别；不能归因为补卡解锁
- **PCA2-T-090#S4**：control=indeterminate / experiment=correct_selection（validity truncated/valid）——其他——卡面补全使已有正确候选的功能变得可验证（非新增候选解锁）