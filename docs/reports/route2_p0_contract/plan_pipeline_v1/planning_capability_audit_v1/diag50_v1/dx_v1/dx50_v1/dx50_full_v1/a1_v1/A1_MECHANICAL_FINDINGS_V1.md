# A1 机械层结果 V1（2026-10-18 收口；四指标判定待 owner 复核包裁定）

> 预注册：`A1_PREREGISTRATION_V1.md`（生成前冻结）。本文只报机械层——决策三分
> （POS=正选∈候选 / OOC=越选 / ABST=显式弃权 / NODEC=无有效判定）与配对转移；
> **正确选择率/错误选择率/合理弃权率/误弃权率的判定依据 owner 已终审的 63 行抽查表
> 口径，需对 52 对复核包人工裁定后才能成立。**

## 完整性与运行事实（A1_RUN_RECORD_V1.json）

- 生成 158/158，76.4 min（pid 3229138，mdzhang，冻结 runner/recorder 副本）。
- ledger `item_audit_complete=True`；双端 tar SHA 一致（`cb0a84f2…`）；
  本地重验 raw 158/158 + gen 158/158 哈希全对 commit 标记。
- 空 raw 38/158（24.1%）——与全量基线 25.3% 同水平（生成侧现象不受卡面影响）。
- 对照臂=冻结 dx50_full_v1 记录（对齐证明 158/158，见受影响步集文件）。

## 三分结果（n=158 受影响步，唯一变量=OTB 卡 v0_4→v0_5）

| 臂 | POS 正选 | OOC 越选 | ABST 显式弃权 | NODEC 无判定 |
|---|---|---|---|---|
| 对照 v0_4 | 24 (15.2%) | 0 | 68 (43.0%) | 66 (41.8%) |
| 实验 v0_5 | 31 (19.6%) | 1 (0.6%) | 59 (37.3%) | 67 (42.4%) |

**配对转移**：POS→POS 17 ｜ **OTHER→POS（收益）14** ｜ **POS→OTHER（损失）7** ｜
ABST→ABST 46 ｜ NODEC→NODEC 45 ｜ ABST→NODEC 17 ｜ NODEC→ABST 11 ｜ NODEC→OOC 1。

## 统计（预注册：任务级 cluster bootstrap，49 任务，10,000 次，seed 20261018）

- POS 率差 **+4.4pp**，95% CI **[−1.4pp, +10.5pp]**（跨零）；
  符号检验（14 vs 7）双侧 **p≈0.189**——**方向为正、不显著，不作能力结论**。

## 关键明细（全部进入复核包人工裁定）

- **T-009 家族**：S6 `ABST→POS(otb:trainvectorclassifier)`（owner 优先复核步+此前
  人工确认恢复目标——补卡后直接正选）；S3 `ABST→POS(saga:multibandvariation，选中
  未改卡算子)`；**S4/S5 `ABST→ABST`**——S4（RF 训练步）在卡面已出现
  `classifier(Choice)` 后**仍弃权**：冻结渲染器不展开 choice 候选值，"卡是否展示
  RF"的答案仍是**否**——owner 警示（Choice≠充分证据）在数据中精确命中，
  **指向表现层（full_card 渲染）而非知识缺失**（预注册解释表第三行的机制候选）。
- **15→修正为 14 个收益对**中 7 个选中**本次未改卡**的算子（上下文变化改变整体
  作答倾向）——合理性全部待裁定；1 例修正为越选（T-090#S4 模型笔误
  `otc:ImageClassifier`，parser v2 正确判出，初版分析口径已修）。
- **损失 7 对**中 5 对是 POS→NODEC（生成侧退化，非知识回归）；2 对 POS→ABST
  （T-001#S6 saga:mosaicking→弃权等——对照选择本属弱候选，可能是合理化，待裁定）。
- **`provenance_unverified` 6 算子在实验臂被选中次数 = 0**（可用性风险未被富上下文
  引爆；目标环境核验任务不变）。

## 判读（对照预注册解释边界表）

机械层不足以选择三行结论中的任何一行：方向证据（+4.4pp、14:7）倾向第一行
（"卡片知识有帮助"），但不显著且正确性维度未裁。**下一动作 = owner 按复核包
52 对（P1 分类器族 11 / P3 IO 纠正 15 / P4 其余 26）裁定四指标**；裁定前不启动
A2、不冻结任何"补卡有效"表述。

## 产物

`A1_PAIRED_RESULTS_V1.json` / `A1_PAIRED_REPORT_V1.md`（机械）｜
`A1_REVIEW_PACKET_V1.md` + `A1_REVIEW_PACKET_INDEX_V1.json`（52 对复核包）｜
`A1_RUN_RECORD_V1.json`（运行事实）｜ 脚本 `dx_a1_paired_analysis_v1.py` /
`dx_a1_review_packet_v1.py`。分析口径修正记录：classify 初版把越选计为 POS，
已按预注册定义修正（本文数字为修正后）。
