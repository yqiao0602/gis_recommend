# A1 待 owner 裁决清单 V1（46 对）

位置：本目录 `A1_FULL_EVIDENCE_PACKET_V1/`。每对一卷宗（任务全文/步骤定义/Top-10/双版本卡面/双臂完整决策）。裁决写入 `LEDGER_V1.json` 对应条目的 `ledger_fields_pending_owner`（decision_quality × output_validity × mechanism）。

已裁决 6/52（owner_ruled）；待裁决 28 对。

## A 级：裁决会改变结论或 agent 判定非显然（18 对，建议先做）

| 步骤 | 对照(agent) | 实验(agent) | validity | 卷宗 | 待你裁的问题 |
|---|---|---|---|---|---|
| PCA2-T-001#S6 | wrong_selection | reasonable_abstention | valid/valid | [P3_PCA2-T-001_S6.md](P3_PCA2-T-001_S6.md) | 对照判错（mosaicking 做资产打包）→实验合理弃权；请确认对照的'错误选择'标签 |
| PCA2-T-033#S1 | indeterminate | correct_selection | truncated/valid | [P4_PCA2-T-033_S1.md](P4_PCA2-T-033_S1.md) | 实验正确但所用算子卡未变（gdal:rearrange_bands）——上下文诱发，按 R5 不能归因补卡；请确认判定 |

## B 级：低杠杆（多为弃权/截断标签确认，28 对）

| 步骤 | 对照(agent) | 实验(agent) | validity | 卷宗 | agent 依据 |
|---|---|---|---|---|---|
| PCA2-T-056#S6 | reasonable_abstention | indeterminate | valid/valid | [P1_PCA2-T-056_S6.md](P1_PCA2-T-056_S6.md) | 所选 supervisedclassificationforrasters 卡载 FILE_LOAD(file) 无语义、METHOD 枚举未展开——能否加载预训练 RF 不可由卡 |
| PCA2-T-083#S6 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P1_PCA2-T-083_S6.md](P1_PCA2-T-083_S6.md) | RF-from-vector 不可见；实验臂无判定 |
| PCA2-T-084#S2 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P1_PCA2-T-084_S2.md](P1_PCA2-T-084_S2.md) | 候选无阈值重分类能力（regularization=众数平滑）；实验弃权合理 |
| PCA2-T-084#S5 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P1_PCA2-T-084_S5.md](P1_PCA2-T-084_S5.md) | 冷气候例外覆盖需双输出掩膜；实验臂无判定 |
| PCA2-T-001#S4 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-001_S4.md](P3_PCA2-T-001_S4.md) | 候选无 SAR 斑点滤波；实验臂无判定 |
| PCA2-T-001#S5 | indeterminate | reasonable_abstention | truncated/valid | [P3_PCA2-T-001_S5.md](P3_PCA2-T-001_S5.md) | 候选无跨影像中值合成（镶嵌≠中值）；弃权合理 |
| PCA2-T-060#S1 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-060_S1.md](P3_PCA2-T-060_S1.md) | 无可做 tile 划分的候选；实验臂无判定 |
| PCA2-T-062#S4 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P3_PCA2-T-062_S4.md](P3_PCA2-T-062_S4.md) | 交互式查看属架构层；实验臂无判定 |
| PCA2-T-073#S1 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-073_S1.md](P3_PCA2-T-073_S1.md) | 无昼夜均值合成算子；实验臂无判定 |
| PCA2-T-079#S5 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P3_PCA2-T-079_S5.md](P3_PCA2-T-079_S5.md) | 可视化制图超出处理算子；弃权合理 |
| PCA2-T-086#S4 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-086_S4.md](P3_PCA2-T-086_S4.md) | 无堆叠+逐像元计数的复合能力；实验臂无判定 |
| PCA2-T-089#S5 | reasonable_abstention | indeterminate | valid/truncated | [P3_PCA2-T-089_S5.md](P3_PCA2-T-089_S5.md) | 无掩膜+DEM 条件精化；实验臂无判定 |
| PCA2-T-092#S5 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P3_PCA2-T-092_S5.md](P3_PCA2-T-092_S5.md) | 无相干性计算；实验臂无判定 |
| PCA2-T-005#S3 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-005_S3.md](P4_PCA2-T-005_S3.md) | 云量百分比不可得（clouddetection 仅二值掩膜）；弃权合理 |
| PCA2-T-005#S5 | indeterminate | indeterminate | valid/self_contradictory | [P4_PCA2-T-005_S5.md](P4_PCA2-T-005_S5.md) | 实验臂同时输出 SELECT r.mask.vect 与 NO OPERATOR（语义自相矛盾）；对照 r.mask.vect 卡无参数/输出记载（不可判） |
| PCA2-T-012#S3 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-012_S3.md](P4_PCA2-T-012_S3.md) | 候选无跨时相均值；弃权合理 |
| PCA2-T-021#S4 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P4_PCA2-T-021_S4.md](P4_PCA2-T-021_S4.md) | 无多掩膜融合；实验臂无判定 |
| PCA2-T-052#S2 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-052_S2.md](P4_PCA2-T-052_S2.md) | 候选 native:polygonize 卡面 accepts=vector（栅格→矢量未由卡面证实）——弃权与卡面一致；实验臂无判定 |
| PCA2-T-056#S2 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-056_S2.md](P4_PCA2-T-056_S2.md) | 候选中值合成能力缺（averagewithmask1=均值）；弃权合理 |
| PCA2-T-056#S4 | n/a_no_decision | reasonable_abstention | no_decision/valid | [P4_PCA2-T-056_S4.md](P4_PCA2-T-056_S4.md) | 候选无样点光谱提取到特征表；弃权合理 |
| PCA2-T-079#S3 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-079_S3.md](P4_PCA2-T-079_S3.md) | variabledistancebuffer=单缓冲按字段距离，非多级同心环；弃权合理；实验臂无判定 |
| PCA2-T-080#S4 | reasonable_abstention | n/a_no_decision | valid/no_decision | [P4_PCA2-T-080_S4.md](P4_PCA2-T-080_S4.md) | 候选无 BAI/BAIS2/TBR 指数；弃权合理；实验臂无判定 |
| PCA2-T-081#S5 | indeterminate | reasonable_abstention | truncated/valid | [P4_PCA2-T-081_S5.md](P4_PCA2-T-081_S5.md) | 无掩膜+DEM 条件精化；弃权合理 |
| PCA2-T-084#S4 | indeterminate | reasonable_abstention | truncated/valid | [P4_PCA2-T-084_S4.md](P4_PCA2-T-084_S4.md) | 候选与 hs_ratio+纬度带输入不匹配；弃权合理 |
| PCA2-T-086#S5 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-086_S5.md](P4_PCA2-T-086_S5.md) | 无逐像元观测频次统计；实验臂无判定 |
| PCA2-T-098#S1 | reasonable_abstention | indeterminate | valid/truncated | [P4_PCA2-T-098_S1.md](P4_PCA2-T-098_S1.md) | 候选无 QA 条件去云；弃权合理 |

## 裁决口径（已冻结）

R1 复合步骤闭合；R2 截断≠无判定（截断→validity=截断+不可判，空输出才是无判定，不得追溯补答）；R3 笔误不改算子身份；R4 卡面字段完整度≠证据完整度；R5 因果归因保守（改善≠补卡解锁）。

裁决不需要重写卷宗：在回复中按『步骤 | control | experiment | mechanism』给出即可，由账本脚本落库。