# Gate 2 规格：C0 vs C1 —— GEE 组合预训练迁移检验（预注册）

日期：2026-09-21 冻结（跑前成文；判据跑后不得回改）
owner 裁定（2026-09-21）：**方案 A 批准启动 Gate 2；B（n-gram 注入）冻结为候选 C2，主协议冻结后单独注册；C（Gate 1 仪器升级）拒绝，Gate 1 不重开。**
前置：`transfer_phase2_roadmap.md`、`docs/reports/transfer_phase2/gate1/gate1_report.md`（MIDDLE）、Route-2 `P0_CONTRACT_v1.md`（33cc614，不解冻）。

## 1. 与 Route-2 四臂的衔接（roadmap §5 遗留项，本文档闭环）

- **C1 ≡ Route-2 A1**。证据链：`route2_training/configs/A1_gee_dapt_qgis_sft.yaml`（`gee_stage: dapt`，`gee_data: outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl`，`gee_epochs: 1`，base=Qwen3.5-9B-Base）；`route2_training/data/gee_stage_datasets.py` docstring——**DAPT 语料 = instruction 文本 + GEE canonical chain 纯文本，causal-LM 下一词预测，无 prompt/target 切分**（即组合预训练）；`run_ledger_A1.json`——stage-1 完成（3,172 步，loss 1.454→0.893，已 merge），stage-2 完成（20 epoch，best ep15）。
- **C0 ≡ Route-2 C0**（同 base、同 v2a-A 数据与 SHA、同 QGIS SFT 协议 20 epochs、同 dev-120 选点规则；best ep20）。
- **Gate 1 证据的附着点注记**：Gate 1 探针作用于 canonical chain 面；A1 DAPT 混料另含 instruction 文本——Gate 1 的 MIDDLE 结论适用于 DAPT 的链组分。
- **B1**（Task→Semantic Workflow→QGIS SFT）= 机制判别第三臂，不进 Gate 2 主对照，共享终评；其训练归 3f 线管理。
- **Gate 2 主对照零新增训练**。本 Gate 只冻结评价层与判读，不改 P0 契约、不重选 checkpoint（C0=ep20 / A1=ep15，dev-120 opSetF1 规则，P0-5）。

## 2. 问题（可证伪，roadmap §2 原文）

C1（GEE 组合预训练→QGIS SFT）相对 C0（QGIS-only SFT）是否带来 QGIS 工作流生成的**显著、稳定、可解释**改善；改善集中于算子选择还是连接结构（Edge F1）。

## 3. 评价层（三层，全部用已冻结资产）

| 层 | 内容 | 时点 | 地位 |
|---|---|---|---|
| L-dev | Protocol v2（v2a_eval 生成 + v2a_score 评分，冻结 512 token greedy 自由解码、同 prompt 模板）在 dev-120 评 C0、C1 | GPU 窗口（3f 排卡）即可 | **早期信号 + Gate 3 输入，不作终局判定** |
| L-test | test-111 一次性：Protocol v2 + canonicalize 列；prediction lock → SHA | B1 训练完成后（P0-6） | **终局主判据** |
| L-bench | final-100 + refusal-12（qgis-planner-benchmark v0.2.1 冻结 scorer），与 L-test 同批 | 同上 | 终局辅判据 |

checkpoint 路径以 run ledger 为准，执行时记录。dev-120 既有内部口径（C0 0.5611 / A1 0.5510 opSetF1）为**另一 scorer**，不得与 Protocol v2 数字混读，仅作背景。

## 4. Gate 3（负迁移诊断）并入评价管线

对 C1 全部预测文本扫描 GEE 残留：正则族 `ee\.` / `Map\.` / `ui\.` / `ImageCollection` / `FeatureCollection` / `filterDate` 等 + canonical 算子名匹配；报告污染行率、分布与样例。仅报告不设阈值，解读归 Gate 3（roadmap 单列）。

## 5. 预注册判读矩阵（owner 情形 A-D + P0 判读表合并）

主判据 = L-test e2e Operator F1；核心次判据 = Edge/Link F1（roadmap L2）。Δ = C1 − C0，附 bootstrap 95% CI（预测行重采样 1,000 次）：

- **A 正迁移**：Op F1 与 Edge F1 同升且 CI>0 → H1 支持；
- **B 仅连接性**：Edge F1 升、Op F1 平 → "GEE 教组合、QGIS 教算子"机制成立；
- **C 仅算子**：Op F1 升、Edge F1 平/降 → 警惕，不得表述为迁移成功；
- **D 负迁移**：任一显著下降（CI<0）→ 结合 Gate 3 污染证据归因机制，不得盲目调参；
- **B1 机制判读**（P0 契约原文沿用）：A1≈C0 且 B1>C0 → 迁移来自 workflow supervision；A1>C0 且 B1>A1 → 组合预训练与监督都有贡献；三者皆平 → Gate 0 观察到的组合结构在当前 QGIS 监督规模下无可用迁移收益（诚实记录）。
- 不设孤立及格线（roadmap §4）；论文级结论措辞按 owner Gate 1 定性模板执行。

## 6. 执行序

1. GPU 窗口（3f 排卡）：L-dev Protocol v2 × {C0, C1}；
2. Gate 3 扫描（CPU，随时）；
3. B1 完成 → L-test + L-bench 三臂一次性终评；
4. 判读矩阵套用 → Gate 2 报告 → owner 裁决 →（可选）单独注册 C2。

## 7. 纪律

- 主对照零新增训练；**C2 未注册前不得混入任何实验**；
- 不重选 checkpoint、不解冻 P0 契约；
- scorer 逐字导入冻结版本；prediction lock → SHA → append-only；
- 任何偏离本 spec 之举 = 协议修订，须 owner 批准且 FAIL 原样保留。

## 8. 实现注记（窗口前预验，2026-09-21）

预验发现并修正两处**表面失配**（指标核心零改动）：

1. **Prompt 前缀**：route-2 两臂 SFT prompt = `task_text + "\nQGIS workflow:"`（无 "Task: " 前缀；collator `PROMPT_SUFFIX` 与 `evaluate_dev.py` L87 双重证实），与 V2a 的模板不同 → `v2a_eval.py` 增加 `--prompt-style route2`（默认 v2a 不变，历史运行可复现）。
2. **输出格式**：route-2 目标为 token 制（`P:pid:operator L:src>dst`，`harness.graph_to_text`），非 JSON → `v2a_score.py` 增加 `--parser route2`：逐字导入 `route2_training.harness.text_to_graph`，首非空行、行级 fail-closed（与 `evaluate_dev.parse_generation` 语义一致）；分类学行 `empty_output`/`malformed_graph` 对应替换 `no_json`/`json_error`/`shape`，其余指标代码零改动（单一指标实现纪律）。悬空 link 按 Protocol v2 既有规则丢弃。
3. **生成配置逐字对齐 evaluate_dev**：greedy、max_new_tokens=512、eos=[eos,pad]、prompt 截断上限 768；批内 left-padding（commit a1a5336）。
4. 单元冒烟（服务器）：多冒号算子、畸形行、空文本、JSON 回归共 5 项全过（2026-09-21）。
5. Gate 3 扫描器就绪：`scripts/gate3_ee_contamination_scan.py`（7 个 GEE 残留族正则，纯报告）。
