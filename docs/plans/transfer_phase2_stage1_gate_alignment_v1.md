# Route-2 v2 Stage 1 验收门对接文档 v1（账本 + 双维判据）

日期：2026-09-24
状态：**FROZEN**（owner 最终签核 2026-09-24：维度 A 沿用 Step⑦ 逻辑池重算基线、维度 B 独立二轴、生成行为面 C0/A1 中点锚定、Plan 面分立不混量纲、Base zero-shot 共用=预注册计算复用非改门、Stage 1 只出 A/B 判定+诊断不反向设计实验——五点全部确认）
地位：owner 指令②的执行件——**只做账本与判据对接，不烧 GPU、不训练、不注册任何新干预**。
协调声明：Route-2 v2 Step①-⑦ 已由并行线冻结（Stage-1 协议 v1：单流混合 60/10/10/20、Chain LM 0%、双条件门 + 硬优先加权选点 .20/.25/.40/.15、成功标准=门非 loss）。本文档是其**验收维度的对齐输入**；§3 门槛为提案，冻结需 owner + 并行线双签，不单方自冻。

## 1. Stage 1 验收输入集（冻结指定，全部已入库）

| 输入 | 工件 | commit |
|---|---|---|
| Gate 0 冻结报告 | `docs/reports/transfer_phase2/gate0_v2_report.md` | d1d0ec9（勘误 15d9caa） |
| Gate 0 v2 结果 | `gate0_v2_results.json` + `gate0_v2_results_corrected.json` | 15d9caa |
| Gate 1 冻结 spec | `docs/plans/transfer_phase2_gate1_spec.md` | ea8862a |
| Gate 1 终局报告 | `docs/reports/transfer_phase2/gate1/gate1_report.md` | 975ebba |
| Gate 2 报告 | `docs/reports/transfer_phase2/gate2/gate2_report.md` | 613d732 |
| FA v1 报告 | `docs/reports/transfer_phase2/fa/fa_report.md` | afc5120 |
| A1 机制结论 v1（冻结） | `docs/reports/transfer_phase2/a1_mechanism_conclusion_v1.md` | 82b0dd4 |
| DC-1 报告 | `docs/reports/transfer_phase2/dc/dc1_report.md` | 618fac1 |
| DC-2A-R1 spec + 终局 | `docs/plans/transfer_phase2_dc2a_r1_spec.md`、`dc/dc2ar1_*` | eae51b9 / 618fac1 |
| L-bench 报告（P0-6 补齐） | `docs/reports/transfer_phase2/dc/route2_lbench_report.md` | 60946c4 |
| 并行线冻结件 | Stage-1 协议 v1 / 接口合同 / B2 数据构造 / Plan 管线 PASS（Step①-⑦ 记忆件） | 并行线管理 |

## 2. 双维验收表（维度 × 问题 × 当前证据）

| 维度 | 要回答的问题 | 证据来源 | 当前证据状态（v2 开跑前基线） |
|---|---|---|---|
| **A. Composition Learnability** | GIS workflow 组合/结构能力是否可被学习并验收 | Gate 0（结构存在）+ Gate 1（可学性）+ FA-D2（planning 探针工具） | 结构存在（PASS）；可学性 = MIDDLE（局部统计为主，超越 n-gram 未证）；C0/B1 的 planning 投影 F1 ≈ 0.53 → planning 空间可行 |
| **B. Generation Control** | 模型能否稳定产出合法、完整、可停止、不过度重复的 workflow | FA-D1②（自由续写探针）+ DC-1 + DC-2A-R1 + L-bench 可靠性块 | 健康锚（C0：stopped 91.3%、hit_cap 4.5%、rep 13.5%、注入 1.23）与失败锚（A1：76.6%、18-34%、28-32%、4.74）均已实测；decode 期边际干预两连败 → 控制必须进训练目标 |

**核心重定位（owner 2026-09-24）**：Stage 1 验收**不再以 GEE→QGIS transfer 为目标**。GEE 角色 = 结构/composition supervision 源；Stage 1-A 的监督源可为 GEE/synthetic/structural 任意组合。

## 3. PASS / MIDDLE / FAIL 门槛提案（跑前冻结；双签前不生效）

**锚定规则（表面自适应）**：FA-D1② 探针设计冻结（gold 前缀自由续写 + 可靠性块），**锚点在同一输出表面上实测**——健康锚 = 同面 C0 类基线，失败锚 = 同面 A1 特征值；维度边界 = 两锚中点。P:/L: QGIS 面直接沿用已冻结实测锚（下表）；Plan/语义面在 v2 数据上按同规则实测后回填。

### 维度 B（Generation Control）门槛提案（P:/L: 面锚已实测）

| 判定 | 条件（对同面基线自由解码） |
|---|---|
| **PASS** | 全部落健康区：stopped ≥ 锚[健康]−5pp 且 hit_cap ≤ 锚[失败]−5pp 且 repetition ≤ 锚[失败]−5pp 且 harmful_extra ≤ 55% 且注入算子均值 ≤ 失败锚的一半 |
| **MIDDLE** | 各指标显著优于失败锚但不达 PASS 带（逐指标落健康-失败中点内侧） |
| **FAIL** | 任一核心指标落入失败区：stopped ≤ 中点 或 hit_cap ≥ 中点 或 repetition ≥ 中点 |

（P:/L: 面中点参考：stopped 83.9%、hit_cap 11.3%、repetition 20.7%。）

### 维度 A（Composition Learnability）门槛提案（沿用 Gate 1 阶梯结构）

| 判定 | 条件（对 v2 Stage-1 训练池的链不相交 held-out，频率基线重算） |
|---|---|
| **PASS** | next-step（plan-step）预测 ≥ 强基线（trigram 类）+ 5pp **且** 语义投影 F1 不低于同面健康基线 −0.03 |
| **MIDDLE** | 高于弱基线 + 5pp、未达 PASS |
| **FAIL** | ≤ 弱基线 + 5pp |

## 4. Stage 2 输入变量（§4 边界条款）

Stage 1 验收**只输出**：维度 A/B 各自 PASS/MIDDLE/FAIL + 逐仪器诊断 → 映射表：A-FAIL → 结构监督源重设计（B1 通道）；B-FAIL → Stage 2 强制纳入 output-discipline 目标（已冻结原则）；A/B 双 PASS → Stage 2 聚焦 grounding。**Stage 1 验收不设计 Stage 2 实验。**

## 5. 双签记录

### 并行线签署（2026-09-24，Route-2 v2 持有会话，originSessionId d164ab87…）——已签

**§3 一致性核对：通过与 Step⑦ 双条件门无冲突**：① 锚中点规则作用于生成行为面，⑦ 的 .20/.25/.40/.15 加权与双条件作用于 Plan 能力面——两套仪器不同面不同量，无数值交叠；② 维度 A 的链不相交 + 频率基线重算口径与 ⑦ 的 author-disjoint split + fail-closed 覆盖完全兼容；③ 操作性建议——维度 A 的 Plan 面锚实测与 ⑦-3 的 Base zero-shot 预注册**共用一次 Base 评测会话**，一次 GPU 同时产出两套预注册基线。

**维度 B 裁定：独立二轴，不并入 .20/.25/.40/.15**（三点理由：⑦ 权重已随 owner 批准冻结，塞入=重开 ⑦；B 为生成行为探针，与 W1-W4 plan 能力探针正交，合并互相稀释；§4 映射本就是路由机制非冻结门槛）。**边界划分：W-gate 独占 checkpoint 冻结决策；A/B 独占 Stage-2 设计路由；B 探针在 W-gate 冻结后的同一 checkpoint 上跑，不参与选点。**

**并行线通报**：Stage-1 训练数据集 v1 已构建（59,411 样本，60/10/10/20 精确达标，~30.2M tok，池门控 = ⑥-3 Tier A+B）；开跑前最后前置 = W1-W4 Gate builder + Base zero-shot 预注册跑。

### owner 签核：待录（确认即 v1 → FROZEN）


