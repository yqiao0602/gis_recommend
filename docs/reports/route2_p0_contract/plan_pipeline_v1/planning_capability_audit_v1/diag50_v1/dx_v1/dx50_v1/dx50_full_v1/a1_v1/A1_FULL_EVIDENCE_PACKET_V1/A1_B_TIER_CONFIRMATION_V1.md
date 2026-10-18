# A1 B 级待确认清单 V1（26 对）

按 R2 冻结表 + 三原则（不从未闭合推理补答案；允许单步骤多次调用；空输出不入弃权率）逐条核对。
25 对与冻结规则一致，建议 owner 一次性确认；1 对（T-005#S5）需单独裁定。

| 步骤 | control | experiment | validity | 卷宗 | 核对 |
|---|---|---|---|---|---|
| PCA2-T-001#S4 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-001_S4.md](P3_PCA2-T-001_S4.md) | 一致 |
| PCA2-T-001#S5 | indeterminate | reasonable_abstention | truncated/valid | [P3_PCA2-T-001_S5.md](P3_PCA2-T-001_S5.md) | 一致 |
| PCA2-T-005#S3 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-005_S3.md](P4_PCA2-T-005_S3.md) | 一致 |
| PCA2-T-005#S5 | indeterminate | indeterminate | valid/self_contradictory | [P4_PCA2-T-005_S5.md](P4_PCA2-T-005_S5.md) | ⚠待裁 |
| PCA2-T-012#S3 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-012_S3.md](P4_PCA2-T-012_S3.md) | 一致 |
| PCA2-T-021#S4 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P4_PCA2-T-021_S4.md](P4_PCA2-T-021_S4.md) | 一致 |
| PCA2-T-052#S2 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-052_S2.md](P4_PCA2-T-052_S2.md) | 一致 |
| PCA2-T-056#S2 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-056_S2.md](P4_PCA2-T-056_S2.md) | 一致 |
| PCA2-T-056#S4 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-056_S4.md](P4_PCA2-T-056_S4.md) | 一致 |
| PCA2-T-056#S6 | reasonable_abstention | indeterminate | valid/valid | [P1_PCA2-T-056_S6.md](P1_PCA2-T-056_S6.md) | 一致 |
| PCA2-T-060#S1 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-060_S1.md](P3_PCA2-T-060_S1.md) | 一致 |
| PCA2-T-062#S4 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P3_PCA2-T-062_S4.md](P3_PCA2-T-062_S4.md) | 一致 |
| PCA2-T-073#S1 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-073_S1.md](P3_PCA2-T-073_S1.md) | 一致 |
| PCA2-T-079#S3 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-079_S3.md](P4_PCA2-T-079_S3.md) | 一致 |
| PCA2-T-079#S5 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P3_PCA2-T-079_S5.md](P3_PCA2-T-079_S5.md) | 一致 |
| PCA2-T-080#S4 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P4_PCA2-T-080_S4.md](P4_PCA2-T-080_S4.md) | 一致 |
| PCA2-T-081#S5 | indeterminate | reasonable_abstention | truncated/valid | [P4_PCA2-T-081_S5.md](P4_PCA2-T-081_S5.md) | 一致 |
| PCA2-T-083#S6 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P1_PCA2-T-083_S6.md](P1_PCA2-T-083_S6.md) | 一致 |
| PCA2-T-084#S2 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P1_PCA2-T-084_S2.md](P1_PCA2-T-084_S2.md) | 一致 |
| PCA2-T-084#S4 | indeterminate | reasonable_abstention | truncated/valid | [P4_PCA2-T-084_S4.md](P4_PCA2-T-084_S4.md) | 一致 |
| PCA2-T-084#S5 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P1_PCA2-T-084_S5.md](P1_PCA2-T-084_S5.md) | 一致 |
| PCA2-T-086#S4 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-086_S4.md](P3_PCA2-T-086_S4.md) | 一致 |
| PCA2-T-086#S5 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-086_S5.md](P4_PCA2-T-086_S5.md) | 一致 |
| PCA2-T-089#S5 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-089_S5.md](P3_PCA2-T-089_S5.md) | 一致 |
| PCA2-T-092#S5 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P3_PCA2-T-092_S5.md](P3_PCA2-T-092_S5.md) | 一致 |
| PCA2-T-098#S1 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-098_S1.md](P4_PCA2-T-098_S1.md) | 一致 |

## 需单独裁定：PCA2-T-005#S5

实验臂输出**同时**包含 `SELECT grass7:r.mask.vect …` 与结尾 `NO OPERATOR FOR THIS STEP`（自相矛盾）。
当前账本：control=不可判（截断）/ experiment=不可判，validity 有效/自相矛盾。
待定：自相矛盾输出应归为「不计入指标（输出未闭合）」还是「错误选择（断言与结论冲突）」？对照臂 r.mask.vect 卡无参数/输出记载，判不可判。

## 附：其余 25 对一致的核心理由

- 对照臂明确 `NO OPERATOR` 且候选卡无充分匹配 → 合理弃权（valid）
- 对照/实验空输出 → 无判定（不计入）
- 思考未闭合 → 截断不可判（不计入）
- 闭合 SELECT 但卡面证据不足（如 FILE_LOAD 语义、r.blend.rgb 无端口）→ 证据不足不可判（valid）