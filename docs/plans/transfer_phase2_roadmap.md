# 第二阶段路线裁定：跨平台 GIS 工作流组合知识迁移

日期：2026-09-20（owner 裁定）
状态：**已批准**；本文档为路线冻结，Gate 设计与判据另立 spec，开训前须逐 Gate 预注册。

## 1. 第一阶段收官（定论）

| 线 | 定论 |
|---|---|
| M1/M2/M3 | 模型路线诊断完成：生成能力可修（M1-R2），DAPT 净负（M2），SFT 有能力但 mapping 无突破（M3）；瓶颈在**数据侧监督**，不在"再调一次模型" |
| V2a | 生成约束诊断完成：P0 正（后处理）、ngram8 负、P1 EOS 负、P2 局部正但触发附加失败条款；**V2a 封存，P3 不立项**（owner 停止条件） |

P2 定论表述（owner 采纳措辞）：**"P2 改善了 operator 合法性和条件 operator 质量，但同时加剧了长链/截断问题，因此其收益主要集中于 operator 层，而尚未转化为完整 DAG 结构质量的同步提升。"** 不得写成"显著提升整体性能"。

阶段结论：单纯提高生成合法性不自动解决 workflow 长链结构问题；后处理、n-gram、EOS 惩罚、语法/目录约束分别作用于不同 failure mode。benchmark v0.2.1 架构对照**本轮未获排期**（owner 裁定转向第二阶段；Gate 2 的 C0-vs-C1 本质上承载该对照）。

## 2. 第二阶段核心假设（可证伪）

**跨平台 GIS 工作流组合知识迁移**：GEE 大规模工作流（约 12.8 万行冻结转化语料）可先教会模型"GIS 工作流如何组合"（操作依赖、常见 motif、长链结构、数据流关系），随后用 QGIS 数据把该组合能力约束到 QGIS 算子/参数/I-O 上。

- 命名约束：**不迁移算子 ID，不做 GEE→QGIS 算子级映射；不走 L2 桥接。**
- 一句话：**GEE 教"怎么组合"，QGIS 教"用什么组合"。**
- 研究假设（须实验证明，不得默认成立）：`GEE composition pretraining → QGIS SFT` 优于 `QGIS-only SFT`（同模型、同 QGIS 数据、同 token budget、同 benchmark、同训练协议；唯一变量 = GEE 组合预训练有无）。
- 反向结果同样有效：若两臂无差异，结论为"大规模跨平台工作流组合知识在当前实现下不可直接迁移"，需归因到数据/训练目标/迁移机制。

## 3. Gate 流水线（硬纪律：任一 Gate 不过，不进下一阶段）

| Gate | 内容 | 不过则 |
|---|---|---|
| **0** | GEE 冻结语料组合能力审计（不训练）：长度/唯一率/转移/motif/长链/重复/近重复/平台通用性/组合熵 + 预注册 FAIL 判据 | 调整路线 |
| **1** | GEE 组合可学性（无 QGIS）：GEE train→held-out，next-operator/transition/motif/长链预测 | 直接停止迁移路线 |
| **2** | 核心对照：C0 QGIS-only SFT vs C1 GEE 组合预训练→QGIS SFT | 假设未获支持，归因分析 |
| **3** | 负迁移诊断：C1 输出有无 GEE API/语法/链式污染 | 迁移机制问题，非组合知识不存在 |
| **4** | QGIS 数据梯度（10/25/50/100%）× 两臂曲线，验证低资源增益 | —（诊断性） |
| **5** | 参数与 I/O 学习（QGIS 语义层，GEE 不参与） | — |
| **6** | QGIS 执行与严格任务成功（对齐 GISAgentBench 层级） | — |

先小规模验证、过 Gate 才扩大；**任何 Gate 开跑前，判据先预注册成文**。

## 4. 三级成功标准（目标区间，非及格线）

| 层级 | 指标 | 目标区间 |
|---|---|---:|
| L1 结构能力 | Valid Workflow / Op F1 / Edge F1 / 长链完整率 / motif Recall / graph EM | Valid ≥90%，Op F1 ≥0.30，Edge F1 ≥0.20 |
| L2 QGIS 工作流 | Op F1 / **Parameter Acc** / I-O 兼容率 / **Edge F1（核心）** | Op F1 ≥0.40，Edge F1 ≥0.30，Param ≥70% |
| L3 执行成功 | Strict Workflow Success（可对照 GISAgentBench：最高 32.7%，六模型均值 ~23.8%） | ≥20%；~30% 有强现实对照意义 |

裁定：**不设孤立及格线**。科研价值判定 = 跨平台迁移是否带来**显著、稳定、可解释**的增益（含低资源场景增益、无 GEE 污染）；`QGIS-only 0.20 → GEE→QGIS 0.30` 即使未达 30% 也成立；持平则如实记录假设未获支持。Operator F1 衡量"用了哪些工具"，Edge F1 衡量"怎么连接"——后者是本研究核心指标。

## 5. 与既有资产/契约的关系

- GEE 侧资产：Route-2 P0 契约冻结的 `outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl`（128,447 行 = 101,513/11,075/15,859；SHA256 `ab9ab2…446a5e`，0f85c83）为第二阶段 GEE 组合语料的**候选正源**；Gate 0 审计对象即该文件。
  **勘误（2026-09-20，7f 复核）**：上行 SHA256 系误记——`ab9ab2…` 属 `gee_conversion_wf_full_v1/pilot_rows.jsonl`（P0_CONTRACT_v1.md 第 12 行，同源 128,447 行的另一种序列化）。`b1_gee_stage_train.jsonl` 实测 SHA256 = `09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2`（审计运行时计算与服务器独立复核一致；mtime 2026-09-17 15:39，审计前未变更）。详见 `docs/reports/transfer_phase2/gate0_v2_report.md` §1。
- Route-2 四臂（C0/A1/B1/B2）设计与本 Gate 计划的衔接**待对齐**，在 Gate 1 设计文档中明确，不在本文档擅自改冻结契约。
- 历史资产（629 旧池、pool-A 44,220 行）不得混入（沿用 P0 契约纪律）。

## 6. 立即行动

**Gate 0 v2**（增量审计，规格见 `gee_composition_audit_gate0_v2_spec.md`）：v1 审计（`gee_workflow_diversity_audit_v1.md`，2026-09-17）已回答"raw 池是否模板化"（否，多样性真实）；v2 在**冻结训练资产本身**上补测 owner 十项清单中缺失的 ③转移分布 ④motif 谱 ⑦算子重复 ⑩组合条件熵 + canonical→semantic 结构保留率（平台通用性的直接度量）+ 跨 split 链污染。

## 7. 执行进展（2026-09-20/21）

- **Gate 0：PASS 零警告**（`d1d0ec9`；勘误 `15d9caa`：真 trigram 谱 + 两段式判重，污染实为语义面 27.4-29.5%）。报告 `docs/reports/transfer_phase2/gate0_v2_report.md`。
- **Gate 1：MIDDLE**（`975ebba`）——三种子探针 38.03% vs B2 39.69%（Δ −1.66pp，CI 全部<0）；短链反超、12-15 桶 B2 模板尖峰、探针未饱和。owner 定性（2026-09-21）：**"GEE 序列具有很强的局部转移统计结构，但当前小型从零探针未显示出超过 trigram 基线的显著 next-operator 预测优势"**——不阻断、不证明。报告 `docs/reports/transfer_phase2/gate1/gate1_report.md`。
- **Gate 2 裁定（owner 2026-09-21）**：方案 A 批准启动；B（n-gram 注入）冻结为候选 C2，主协议冻结后单独注册；C 拒绝，Gate 1 不重开。
- **衔接闭环（roadmap §5 遗留项）**：C1 ≡ Route-2 A1（DAPT 语料 = 同一冻结文件的 instruction+canonical chain 纯文本 LM；run_ledger + yaml + dataset 代码三重证据）、C0 ≡ Route-2 C0；**主对照零新增训练**。spec：`transfer_phase2_gate2_spec.md`。
- **执行状态**：B1 训练中（3f 线，语义 SFT ~1.5 天 + QGIS SFT ~5h）；L-dev Protocol-v2 双评（C0/A1）等 B1 退出后 GPU 全空连排；L-test/L-bench 三臂终评随后一次。
- **Evaluation harness freeze（owner 2026-09-21，`665723d`）**：Gate 2 评价口径就此冻结——prompt surface、route-2 parser、Protocol v2 指标核心、生成配置、Gate 3 扫描器均不得再改；模型生成问题与评价协议问题自此严格分离；**L-dev 结果不得触发对 L-test 的任何修改**，数字按预注册判读矩阵自行说话。
- **Gate 2 终局 + FA 闭环（2026-09-23/24）**：Gate 2 = 情形 D 负迁移（`613d732`）；FA 三线证据收敛 **Generation Control 层**（`afc5120`：D2 Planning 保留 / D3 72% 同族过量 / D1① teacher-forced acc=C0 统计零 + D1② 自由续写 EOS−14.7pp、注入×3.9 全显著）。报告 `docs/reports/transfer_phase2/fa/fa_report.md`。
- **DC 阶段立项（owner 2026-09-24）**：下一主线 = 解码/输出机制，三小段——DC-0 baseline freeze（已锁定工件承担）→ DC-1 trie 结构化解码（四条 P2 教训强制入设计；hit_cap 上升=红线）→ DC-2 状态感知 EOS。**A1 不再调/训/DAPT，C2 冻结，先不碰 RL。** Route-2 v2 两阶段验收重定义：Stage 1 = Learnability + Generation Control 分开验收；Stage 2 = planning→grounding→structured graph→output control 的训练目标链。spec：`transfer_phase2_dc_spec.md`。
- **诊断链正式收口（owner 2026-09-24）**：A1 机制结论冻结为 `docs/reports/transfer_phase2/a1_mechanism_conclusion_v1.md`——三类简单解释全部单变量排除（不知下一步 / 非法 token 挤占 / EOS 边际不足），机制陈述与措辞纪律（"与 exposure-bias 一致的路径依赖特征"，非已证因果）照录。**A1 保留为已诊断失败案例，不进入修复实验**。下一阶段方向 = **Stage 2 Output-discipline post-training**（C0 vs C0+ 对照；EOS/长度/非重复/完整结构进训练目标）；工作流级结构化解码（选项 2）不注册；GEE 位置重定义 = 结构/composition supervision，非 DAPT 源；RL 押后；C2 冻结；L-bench 待补。
- **① L-bench 补齐（2026-09-24，`60946c4`）**：P0-6 辅判据闭环。final-100（v0.2.1 冻结 scorer 逐字）：**C0 0.432 > A1 0.377 > B1 0.347** op F1——负迁移在第二评价面复现，C0 两面均居首；**B1/A1 排序随面翻转**（test-111 B1>A1，final-100 A1>B1）→ B1 结构优势不跨面稳健，不得作强结论；harmful_extra 63-68% 三臂全现 = 过量生成签名复现；refusal 三臂 0%（SFT-only always-plan，预期内）。预测 SHA 锁 ROUTE2_LBENCH_LOCK_v1.json。报告 `docs/reports/transfer_phase2/dc/route2_lbench_report.md`。
- **② v2 Stage 1 验收门对接完成（2026-09-24，`06a22e1`）**：对接文档 `transfer_phase2_stage1_gate_alignment_v1.md`——冻结输入集（11 件）、双维验收表（A. Composition Learnability / B. Generation Control，GEE 重定位为监督源）、PASS/MIDDLE/FAIL 门槛**提案**（锚定规则=同表面 C0 健康锚与 A1 失败锚中点；P:/L: 面锚已实测、Plan 面开跑时按同规则实测回填）、Stage-2 输入变量边界条款。**门槛待双签**（owner + 并行线 Step⑦ 一致性核对），双签后 v1→FROZEN。纯文档，零 GPU。**顺序账本：①✅ → ②✅（待双签）→ ③ Stage 2 设计原则已交付 → ④ RL 押后。**
- **② FROZEN + ③ Stage 2 设计开工（2026-09-24，owner 最终签核）**：验收门对接文档 v1→FROZEN（五点确认：A 沿 Step⑦ 逻辑池重算、B 独立二轴、行为面 C0/A1 中点锚、Plan 面分立、Base zero-shot 共用=预注册复用）。**③ 开篇**：Stage 2 设计骨架 v0（`transfer_phase2_stage2_design_v0.md`，讨论稿非预注册）——五维行为目标→训练信号映射、数据/loss 选项空间（L1 纯 SFT 主轨 / L2 温和终止加权 / L3 完成度多任务 / L4 偏好对）、验收全移植冻结件、B2 硬依赖 Stage-1 的排程约束；**待 owner 裁决 D1-D4**（目标形式/终止信号/负样本政策/排程）。核心认识入档：C0 harmful_extra 62.5% = 纪律目标在健康臂同样有改进空间。
- **Stage 2 D1-D4 裁决完成（2026-09-24，owner）**：D1 = **L1 纯 SFT 主轨**（拒绝 L2/L3/L4 首轮混入——单变量因果纪律）；D2 = **(a) 纯正样本起步**（先证"正确完整监督"本身能否改善停控，防变量纠缠）；D3 = **(ii) B2 双条件主 + v2a_A Task-only 辅 + 三面验收**（链式主面/Oracle Plan 诊断面/Task-only 防漂移面，面位固定禁择优；混合=能力保留路径非比较实验；自然比例非超参）；D4 = **永久排除显式负向惩罚**（P1/DC 警示，重启须单独注册）；排程 = **v2a_A 流程预演（标记 pipeline rehearsal，不得替代正式结论）→ B2 正式**。**最后前置 = 并行线对 D3(ii) 的接口增补签核（已发 b1 持有会话，待复）→ 签核后落 Stage 2 预注册 spec。**
- **Stage 2 预注册 spec 冻结（2026-09-24，`transfer_phase2_stage2_prereg_v1.md`）**：D1-D4 + 并行线签核（含两条执行注记：配对 row_id 分析预案、自然比例=装配结果非参数）全部落成文——双阶段结构（R 预演/v2a_A + F 正式/B2+辅行，F 硬前置 Stage-1 完成）、L1 配方（C0 配方复刻、唯一差异=数据集）、三面验收（面位写死禁增删：链式主面/Oracle Plan 诊断/Task-only 保持面）、纪律防护 FAIL 线（移植 FROZEN 锚）、冒烟门、归因预案（三面分离设计保证 FAIL 可归因）。**待 owner 批 spec → Phase R 预演开跑。**
