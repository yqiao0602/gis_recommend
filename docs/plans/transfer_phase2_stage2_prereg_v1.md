# Stage 2 预注册 spec v1（Output-discipline post-training）

日期：2026-09-24 冻结（跑前成文；判据/面位/冒烟门跑后不得回改，改 = 协议修订且 FAIL 原样保留）
裁决链：D1 = L1 纯 SFT 主轨；D2 = (a) 纯正样本起步；D3 = (ii) B2 双条件主 + v2a_A Task-only 辅 + 三面验收；D4 = 永久排除显式负向惩罚；排程 = v2a_A 预演 → B2 正式。
签核：并行线（Route-2 v2 Step③ 接口持有线）已签 D3(ii)，附两条执行注记（本 spec §2/§6 全文采纳）。
禁令（全量有效）：A1 不调/训/DAPT；C2 冻结；RL HOLD；无 β/比例/混合率/参数扫描；无 trie/EOS bias 等 decode 干预注册；无显式负样本。

## 0. 双阶段结构

| Phase | 数据 | 目的 | 结论地位 |
|---|---|---|---|
| **R（rehearsal）** | v2a_A 全量（1,334，Task-only 格式） | L1 管线预演：数据构造/loss/EOS-完整序列处理/训练管线验证 | **标记 pipeline rehearsal；任何效果数字不得引用为 Stage 2 结论** |
| **F（formal）** | B2 双条件主（Task+Plan→graph）+ v2a_A Task-only 辅（1,334 全量） | 正式 Stage 2 | 三面验收，正式结论 |

Phase F 硬前置：Stage 1 训练+选点完成（并行线 W1-W4）→ B2 Teacher Plan 生成（⑥ 线）→ B2 装配。前置未齐 Phase F 不开。

## 1. 训练配方（L1）

- C0 配方复刻：SFT 超参与 P0 契约 C0 yaml 同款（QLoRA NF4 r16、greedy 推理、eos 表同）；**唯一差异 = 训练数据集**（Phase R: v2a_A；Phase F: B2+v2a_A）。
- 目标序列：完整 gold graph（text_to_graph 可解析的全量目标），**每样本以终止 EOS 结束**——终止可见性内建于数据。
- 选点：dev-120 primary task metric（P0-5 规则沿用）+ 可靠性块作 monitored constraint（不参与选点）。
- Task-only 辅行与 B2 双条件行共享同一批 gold graph——**装配时按 row_id 记录配对关系**（并行线注记 1），供"Plan 条件净贡献"配对诊断分析（诊断性，不承载判据）。

## 2. 装配与比例定义（并行线注记 2 采纳）

自然比例 = **装配结果，非输入参数**：B2 全量 + v2a_A 全量，无重采样、无配比参数。assembly manifest 必须记录：实际 sample 比例、实际 token 比例、每样本 row_id 配对字段、逐样本 QC 字段（终止 EOS 存在 / graph 可解析 / DAG 无环）。QC 失败样本剔除并计数（准入检查，非机制）。

## 3. 三面验收协议（面位写死，跑前不可增删；禁止择优）

| 面 | 输入 | 地位 |
|---|---|---|
| **面① 链式主面** | Task → 冻结 Stage-1 → Plan → Stage-2 → graph；test-111 + L-bench 双集，冻结 scorer | **正式系统结论** |
| **面② Oracle Plan 诊断** | Task + **Gold Plan**（⑥-5-② 去接地诊断产物，零泄漏）→ Stage-2 → graph | **Stage-2 能力诊断**（解耦 Stage-1 质量） |
| **面③ Task-only 保持面** | Task → Stage-2 → graph | **防漂移对照**（判据见 §5） |

面② 的 Plan 来源 = ⑥-5-② Gold 去接地诊断线产物（并行线确认已建、零泄漏）；不使用 Stage-1 生成 Plan 充当 Oracle。

## 4. 验收判据（Phase F，全移植冻结件）

- **Grounding 收益**：面① 相对 C0-free 基线的 op/edge F1、EM 变化（CI 口径沿用）；L-bench 面同表交付。
- **纪律防护（FAIL 线，移植对齐文档 §3 冻结锚）**：FA-D1② 探针 + 可靠性块全部落 C0 健康区——stopped ≥ 86.3%、hit_cap ≤ 8%、repetition ≤ 18%、注入算子 ≤ 失败锚一半；任一越线 = 纪律丢失，配方回滚重设计。
- **纪律改进（观察项）**：harmful_extra 相对 C0 的 62.5% 显著下降（点估计 + bootstrap CI）。
- **面③ 防漂移判据**：Task-only 面 op F1 相对 C0-free 的 CI95 下界 > −0.05。
- 判读路由：grounding 得 + 纪律守 = Stage 2 成立 → 聚焦 grounding 深化；grounding 得 + 纪律失 = 配方回滚；grounding 不得 = 回归 B2 数据/接口审计（§6）。

## 5. 冒烟门（各 Phase 训练前）

1. 装配清单核验（QC 字段全绿、配对字段齐、比例已记录）；
2. 200 步短训：loss 单调下降、终止 EOS 在目标内可见；
3. 8 行生成冒烟：输出可被 `text_to_graph` 解析、终止行为存在；
4. 冒烟失败 → 查实现，**不调配方**。

## 6. 归因预案（FAIL 时）

三面分离设计保证归因能力：面① 不得 + 面② 得 → 管线/Plan 质量问题（Stage 1 侧）；面② 不得 → B2 数据/接口审计（§6 触发，Audit 体系已在并行线就位）；面③ 崩 → 双格式干扰（届时议题，不自动扩实验）。

## 7. 禁令（全量）

无 β/比例/混合率/超参扫描；无负样本/负向惩罚；无 trie/EOS bias 等 decode 干预注册；无 beam/长度惩罚；A1 封存；RL HOLD；GEE 原始链与 A1 生成物不进任何训练集。
