# A1 逐对裁决 V1（agent 裁决，待 owner 抽检）

规则：A1_OWNER_ADJUDICATION_V1.md（POS≠正确、ABST≠合理、NODEC 不入四指标、OOC=错误）。裁决依据=全证据卷宗（任务/候选/双版本卡面/双臂完整决策）。

## 四指标

| 指标 | 对照 v0_4 | 实验 v0_5 |
|---|---|---|
| 形成判定步数 | 29 | 26 |
| 正确选择 | 4 (13.8%) | 11 (42.3%) |
| 错误选择 | 3 (10.3%) | 3 (11.5%) |
| 合理弃权 | 22 (75.9%) | 11 (42.3%) |
| 误弃权 | 0 (0.0%) | 1 (3.9%) |
| 证据不足不可判 | 2 (6.9%) | 4 (15.4%) |
| 无判定（不计入四指标） | 21 | 22 |

## 配对转移（裁决后）

- ('reasonable_abstention', 'n/a_no_decision'): 17
- ('n/a_no_decision', 'reasonable_abstention'): 10
- ('n/a_no_decision', 'correct_selection'): 8
- ('reasonable_abstention', 'indeterminate'): 3
- ('correct_selection', 'n/a_no_decision'): 3
- ('n/a_no_decision', 'wrong_selection'): 2
- ('wrong_selection', 'n/a_no_decision'): 2
- ('reasonable_abstention', 'wrong_selection'): 1
- ('indeterminate', 'correct_selection'): 1
- ('wrong_selection', 'reasonable_abstention'): 1
- ('correct_selection', 'correct_selection'): 1
- ('indeterminate', 'indeterminate'): 1
- ('reasonable_abstention', 'correct_selection'): 1
- ('n/a_no_decision', 'wrong_abstention'): 1

## 机制分布

- 生成波动: 24
- 其他: 18
- 补卡解锁正确选择: 5
- 补卡诱发错误选择: 2
- 选择保持: 2
- 上下文诱发误弃权: 1

## 逐对裁决

| 步骤 | 批次 | 对照 | 实验 | 机制 |
|---|---|---|---|---|
| PCA2-T-009#S3 | P1 | reasonable_abstention | wrong_selection | 补卡诱发错误选择（间接/上下文） |
| PCA2-T-009#S6 | P1 | reasonable_abstention | indeterminate | 其他（待 P2 enum 证据） |
| PCA2-T-042#S1 | P1 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-056#S5 | P1 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-056#S6 | P1 | reasonable_abstention | indeterminate | 其他（待 P2/官方文档） |
| PCA2-T-083#S6 | P1 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-083#S7 | P1 | indeterminate | correct_selection | 选择保持（算子替换、实验臂证据更充分） |
| PCA2-T-084#S2 | P1 | n/a_no_decision | reasonable_abstention | 其他（能力边界经卡面明确化） |
| PCA2-T-084#S5 | P1 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-090#S4 | P1 | n/a_no_decision | wrong_selection | 生成波动（大小写笔误→越选） |
| PCA2-T-092#S9 | P1 | n/a_no_decision | reasonable_abstention | 其他（能力边界经卡面明确化） |
| PCA2-T-001#S3 | P3 | n/a_no_decision | correct_selection | 补卡解锁正确选择 |
| PCA2-T-001#S4 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-001#S5 | P3 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-001#S6 | P3 | wrong_selection | reasonable_abstention | 其他（对照错误被纠正为合理弃权） |
| PCA2-T-025#S5 | P3 | n/a_no_decision | correct_selection | 补卡解锁正确选择 |
| PCA2-T-046#S4 | P3 | correct_selection | n/a_no_decision | 生成波动（正确→无判定） |
| PCA2-T-046#S5 | P3 | correct_selection | correct_selection | 选择保持（实验臂增加冗余算子） |
| PCA2-T-056#S3 | P3 | n/a_no_decision | wrong_selection | 补卡诱发错误选择（部分匹配/上下文） |
| PCA2-T-060#S1 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-062#S4 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-073#S1 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-079#S5 | P3 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-086#S4 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-089#S5 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-092#S5 | P3 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-003#S2 | P4 | n/a_no_decision | correct_selection | 补卡解锁正确选择 |
| PCA2-T-005#S3 | P4 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-005#S5 | P4 | indeterminate | indeterminate | 生成波动（自相矛盾输出） |
| PCA2-T-012#S3 | P4 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-021#S4 | P4 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-022#S6 | P4 | reasonable_abstention | indeterminate | 其他（待输入结构） |
| PCA2-T-025#S4 | P4 | n/a_no_decision | correct_selection | 其他（上下文诱发正确选择） |
| PCA2-T-026#S4 | P4 | wrong_selection | n/a_no_decision | 生成波动（对照错误→无判定） |
| PCA2-T-032#S2 | P4 | reasonable_abstention | correct_selection | 补卡解锁正确选择（owner 核心判据命中） |
| PCA2-T-033#S1 | P4 | n/a_no_decision | correct_selection | 其他（上下文诱发正确选择） |
| PCA2-T-052#S2 | P4 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-056#S2 | P4 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-056#S4 | P4 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-057#S4 | P4 | n/a_no_decision | correct_selection | 补卡解锁正确选择 |
| PCA2-T-068#S4 | P4 | n/a_no_decision | wrong_abstention | 上下文诱发误弃权 |
| PCA2-T-068#S6 | P4 | n/a_no_decision | correct_selection | 其他（上下文诱发正确选择） |
| PCA2-T-070#S1 | P4 | n/a_no_decision | correct_selection | 其他（上下文诱发正确选择） |
| PCA2-T-079#S3 | P4 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-080#S4 | P4 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-081#S5 | P4 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-084#S4 | P4 | n/a_no_decision | reasonable_abstention | 其他 |
| PCA2-T-086#S5 | P4 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-089#S4 | P4 | correct_selection | n/a_no_decision | 生成波动（正确→无判定） |
| PCA2-T-092#S2 | P4 | correct_selection | n/a_no_decision | 生成波动（正确→无判定） |
| PCA2-T-098#S1 | P4 | reasonable_abstention | n/a_no_decision | 生成波动 |
| PCA2-T-098#S6 | P4 | wrong_selection | n/a_no_decision | 生成波动（对照错误→无判定） |

## 对 owner 核心判据的回应

**核心判据**：找到可复核证据组，证明卡面变化使模型从合理弃权转向正确选择，且错误选择不明显增加。

- 直接命中 1 对：**T-032#S2**（ABST→POS opticalcalibration，卡面新增 TOA/TOC 与手动参数通路）——合理弃权→正确选择。
- 另有 4 对由从未形成判定（NODEC）→正确选择且所选算子卡面确有变化：T-001#S3、T-025#S5、T-003#S2、T-057#S4（补卡解锁正确选择 5 对含 T-032#S2）。
- 4 对正确选择来自**未改卡算子**（上下文诱发：T-033#S1、T-025#S4、T-068#S6、T-070#S1）——不是补卡解锁，须单列。
- **错误选择数不变（3→3），但为完全置换**：对照的 3 个错误全部消失（T-001#S6 以 mosaicking 做打包→纠正为合理弃权；T-026#S4 native:rasterize 与T-098#S6 空间低通冒充时间平滑→实验臂因无判定未形成决策）；实验的 3 个错误全为新出现（T-009#S3 补卡诱发、T-090#S4 笔误越选、T-056#S3 部分匹配）。**无正确选择被破坏为错误选择**；3 个对照正确步变为无判定（生成侧截断：T-046#S4、T-089#S4、T-092#S2）。
- **新增 1 例误弃权**（T-068#S4：grass7:r.statistics 卡面已足够，候选未变，上下文变化诱发弃权）。
- 结论（预注册解释表第一行，附边界）：正确选择 4→11、错误选择 3→3——支持『卡片知识补全对当前样本有帮助』；但增益大部分来自『无判定→正确』，『合理弃权→正确』仅 1 对直接成立；同时 NODEC 略增（21→22）且出现 1 例新误弃权。