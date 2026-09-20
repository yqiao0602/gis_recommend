# Gate 0 v2 规格：GEE 冻结语料组合能力审计（预注册）

日期：2026-09-20 冻结（跑前成文；结果出来后不得回改判据）
性质：只读、CPU、无模型、确定性；不修改任何数据。
前置：`transfer_phase2_roadmap.md`（owner 裁定 2026-09-20）；v1 审计 `docs/reports/gee_workflow_diversity_audit_v1.md`。

## 1. 审计对象（语料身份）

`服务器:/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl`
128,447 行（train 101,513 / val 11,075 / test 15,859），SHA256 `ab9ab28575c5b9812e5994f0266efb9d032816a76ec02026011c6b197e446a5e`（运行时复核并记录）。
**勘误（2026-09-20，7f 复核）**：上行 SHA256 系误记（`ab9ab2…` 属 `gee_conversion_wf_full_v1/pilot_rows.jsonl`，见 P0_CONTRACT_v1.md 第 12 行）。本文件实测 SHA256 = `09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2`（审计运行时计算 + 服务器独立复核一致）。

这是 Route-2 P0 冻结的**转化后训练资产**——第二阶段 GEE 组合预训练实际会使用的正源。owner 引用的 295,943 raw / 117,735 unique 是上游 raw 脚本池口径（`gee_data_asset_audit_v1.md`），与本法不同层，不冲突；本审计在冻结资产上重测。

每行表面：`gee_canonical_chain`（GEE 算子空间，" -> " 分隔）、`semantic_chain_raw`（37 类语义空间，未治理）、`semantic_chain_rle`（训练目标，RLE+cap3 治理后）、`instruction`、`task_type`、`split`、`run_cap_applied`、`original/final_semantic_length`。

主审计面 = `gee_canonical_chain` + `semantic_chain_raw`；`semantic_chain_rle` 仅作治理效果参考。

## 2. 指标清单（对应 owner 十项，标注 v1 已覆盖项）

主面各算（gee / sem_raw）：

1. **长度分布**：median/mean/p90/p99/max；带 1-2 / 3-5 / 6-8 / 9-16 / 17-32 / >32
2. **唯一率**：精确链 unique/total；单例簇率；≥100 成员模板簇数；top-20 链行覆盖率；N80（覆盖 80% 行所需不同链数）
3. **转移分布**：distinct bigram 数；top-50 bigram 行为覆盖率；bigram 频谱（≥1/≥2/≥10/≥100）
4. **motif 谱**：2-gram 与 3-gram 同上频谱
5. **长链覆盖**：长度 ≥8 / ≥12 / ≥16 的行数与唯一链数
6. **组合熵**：unigram 熵 H(op)；条件熵 H(next|prev)；均匀基线 log2(V)
7. **算子重复**（sem_raw 原始面）：含连续 run 行占比；行内最大 run 分布（2/3/4-5/6-10/>10）；ABAB 交替行占比；cap3 治理效果（original vs final 长度总量损失、触发行 20,081 复核）
8. **近重复**：精确 + 算子 bag 相同链数 + 前 5 元前缀相同分组（MinHash 语义簇仍留转化期，沿 v1 §4）
9. **平台通用性（核心新增）**：canonical→semantic **结构保留率**——distinct canonical 链数 : distinct semantic 链数压缩比；两表面条件熵对比（语义抽象后剩多少组合结构）；语义层 trivial 行占比（长度 ≤2）
10. **跨 split 污染（新增）**：val/test 行的精确链（sem 与 gee 两面）出现在 train 中的比例——Gate 1 的 held-out 评测设计前提

附加报告（不设阈值）：空/缺失 canonical 链行数（canonical 覆盖率代理）；distinct canonical 算子词汇数与 top-20 频率；task_type 分布 top-15；推理层占比代理（链长 ≥4 且 distinct 算子 ≥2）。

v1 已覆盖不重算（引用）：raw 池模板镜像结论、描述-链非镜像（Jaccard 0.12-0.16）、ee 算子 9,828 Zipf。

## 3. 预注册判定（跑前冻结）

**FAIL（调整迁移路线）** 当且仅当以下三条**同时**成立（语义面，精确链口径）：
- (a) 模板化：top-20 语义链覆盖 ≥80% 行；
- (b) 短模板：`semantic_chain_raw` median 长度 <5；
- (c) 稀薄：N80(语义面) ≤ 3,000。

**WARNING（报告 owner 裁决，不自动通过/失败）**：三条中任一单独成立，或语义面条件熵 H(next|prev) < 1.0 bit（组合结构薄弱信号）。

**PASS（进入 Gate 1 设计）**：非 FAIL。WARNING 项须在报告中逐条列出并给出机制解释。

## 4. 产物

- `scripts/audit_gee_b1_composition.py`（stdlib-only，确定性，进度每 20k 行）
- `docs/reports/transfer_phase2/gate0_v2_results.json`（全指标机器可读）
- `docs/reports/transfer_phase2/gate0_v2_report.md`（判据逐条对照 + 机制解读 + Gate 1 输入）
- 服务器运行日志留存路径记录于报告
