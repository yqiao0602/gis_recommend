# P1 Enum 展开探针 — 预注册 V1（2026-10-18，生成前冻结）

> 来源：A1 收口裁定后续优先级 P1——"先核实 T-009#S4/S6、T-056#S6 的证据缺口是否确由
> 枚举信息缺失造成，并记录新增信息是否改变决策"。

## 问题

**冻结渲染器不输出 v0_5 中已存在的 choice 值**（如 `classifier` 的 10 个选项，含
`classifier.dt`/`classifier.rf`）。把这些**已存在的证据**追加到卡面，是否改变 S2 决策？

这是渲染层干预，**不新增任何知识**：所有 choice 值均来自已冻结的 profile v0_5
（源自 OTB 8.1.2 源码 AddChoice 宏）。

## 臂与单变量

- **对照**=A1 v0_5 臂冻结结果（`_a1_work/runs_local`；提示重渲 sha16 与记录逐一相等，3/3）。
- **实验**=同步骤/同 Top-10/同模板/同模型/同解码，卡面末尾追加：
  ```
  choice values:
    classifier: classifier.libsvm, classifier.svm, ..., classifier.rf, ...
  ```
  仅对 `layer_b_params[].choices` 非空的参数追加（每参数最多 14 个值）。
- **唯一变量**=choice 值渲染；full_card() 与 S2_PROMPT 均未修改。

## 样本（owner 点名 3 步）

`PCA2-T-009#S4`（RF 训练）、`PCA2-T-009#S6`（CART 训练）、`PCA2-T-056#S6`（应用预训练模型）。

**已知缺口**：T-056#S6 的目标算子 `saga:supervisedclassificationforrasters` 的 METHOD 枚举
不在钉定证据源内（SAGA 未纳入上游镜像）——该卡**无法**补充枚举，本探针只验证 OTB 卡
（其 Top-10 中 `otb:trainimagesclassifier` 会被展开）。SAGA METHOD 需另立证据源。

## 判读（沿用 R1–R5）

- 决策三分（POS/OOC/ABST/NODEC）+ 截断/自相矛盾分列；
- 对每对比较：决策类别变化、选择算子变化、以及在 v0_5 卡面下是否可由枚举值直接支持
  （如 CART 决策树选项 `classifier.dt` 可见）；
- n=3，只做逐对描述，不报聚合率、不做显著性推断。

## 解释边界（预注册）

| 结果 | 可支持结论 |
|---|---|
| T-009#S6 由弃权/不可判变为选中含 dt 的训练器 | 枚举缺失=绑定缺口，渲染修复即可解锁 |
| 决策不变 | 枚举不是该步的绑定因素（模型未用/截断主导），需查生成侧 |
| 决策变化但选中不支持 dt 的算子 | 渲染变化可能诱发错误选择，收益需另核 |

## 纪律

- 不改 profile、不改 full_card、不改 S2_PROMPT、不重跑 S1；
- 结果只用于 P1 判定，不与 A1 结论合并计数；A2 仍冻结。
