# RL 线预注册协议 v1（CANDIDATE）

> 路径：`docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line/RL_LINE_PREREGISTRATION_V1_CANDIDATE.md`
> 日期：2026-10-13 ｜ 状态：**V1 CANDIDATE——owner 审查轮裁定已全部落入本文（见 §0.2）；
> §4 修订项（r4 可执行定义 / mask+合成合同 / S4 停止条件）已补齐。按 owner 执行授权结论，
> 本文定稿并核对文件配置后 Phase 1 即可按协议启动。** v0 DRAFT 留档为历史。
> Schema 权威：`planner_design/PLANNER_V2_CONTRACT_FREEZE_v1.md`（2026-10-04 FREEZE）。

## 0. 裁定记录

### 0.1 立项裁定（2026-10-13，第一轮）

- **R1**：采纳四阶段 RL 路线（Phase 1 GRPO 工程 smoke → Phase 2 RAFT/DPO 对照 →
  Phase 3 亲和采样+门控 GRPO → Phase 4 过程奖励/估计增强消融）。
- **R2**：输出空间 = **Blueprint v2（P0 规划器）**；QGIS Graph RL 属 Stage 2，维持冻结。
- **R3**：Phase-1 场地 = **mdzhang 共享**（共租纪律适用）。

### 0.2 审查轮裁定（2026-10-13，owner 协议审查；v0 → v1 的全部修订依据）

| OQ | 裁定 | 落实位置 |
|---|---|---|
| OQ-1 | **批准**：24 任务 × 8 候选，seed 20261013；工程 smoke，非能力评测 | §4.5 |
| OQ-2 | **有条件批准**：四分量保留；等权仅为首选候选——先冻结分量定义+校验规则，合成写成显式可执行合同，经正反例电池验证后方可冻结；若电池证明分量不独立/量纲不一致，**修定义不调权重** | §4.3/§4.4 |
| OQ-3 | **批准初值**：KL β=0.04 仅作 smoke 初值，记录实测 KL 与更新幅度，不宣称最优 | §4.5 |
| OQ-4 | **批准**：S4 硬上限 = 24 组 × 2 轮 = **≤48 task-group updates，先到为准**；另设异常停止条件（KL 中止阈值与 β 分开定义） | §4.5 |
| OQ-5 | **批准等待**：Phase 2 不自动放行——S2 吞吐外推报告完成后由 owner 单独批准；不阻碍 Phase 1，也不等待 PCA/多解线 | §5 |

补充裁定（审查轮）：r1 须区分 JSON 语法错误/字段缺失/schema 不合法三级；r2 不得把频率
高低作为奖励；r3 不得对无法确定真实次数的维度判负；r4 必须给可执行定义+正反例，
**P0 schema 未禁止的限制奖励实现不得自行增加**；S2 验收拆为工程验收与信号诊断双结论。

### 0.3 审查轮二次裁定（2026-10-13，owner 对本地实现与 D1–D4 的裁定）

- **D1 有条件接受，已修订**：回归本协议 r1c 原文——entry 级畸形只 mask **受影响分量**
  （r2 对可读 family 照常评估；r3 在 {not_dict, family, repeat} 缺陷下不可判定→masked；
  r4 在任何 entry 缺陷下不可判定→masked）；级联 mask 仅保留给 r1a/r1b 整体失败。
  rg-not-a-list 只 mask r4，不再株连 r2/r3。统一 mask 规则：**可判定违规(0) > 不可判定
  (masked) > 通过(1)**。
- **D2 接受**：原样评分、记录解析失败原因、不悄悄修复。
- **D3 接受并升级**：`repetition_groups` 键缺失 → V3 不可判定 → **r4 masked**（绝不静默
  视为正确），缺失率经 field_presence 落账。
- **D4 不接受无条件放行**：空序列 5/6 是真实奖励漏洞。合同核查结论：冻结合同**无显式
  minItems:1**（preflight 构造不可能产出空 stages）——"空=违规"目前是语义必要性而非合同
  文本。独立漏洞测试已建（`test_d4_hole_quantification`：空=0.833 / 最小合法=1.0 /
  解析失败=0.0）。处置选项 (a) 保留 r4 fail 接受 5/6 漏洞 / (b) 空序列作 gateway 级退化
  (R=0) / (c) owner 修订合同解释（minItems:1）使其成为可判定 schema 违规——**S2 放行前
  由 owner 定夺**。
- **P0 方言问题**：contract 方言是合理假设但未证实；S1 必须在服务器核验
  `planner_v2_train` 目标方言 + 至少 1 条 `p0_dev_full_preds` 真实输出 + 词表 SHA。
  方言不一致→先查数据链路，**不得让奖励模块兼容两种格式掩盖问题**。
- 实现状态：v1.1（模块 SHA `5d5b6789f938980a…`），电池 23/23、pytest 10/10、contract
  方言 755/755 复验不变；`REWARD_BATTERY_REPORT_V1_1.json`（v1 报告留档不覆盖）。

### 0.4 三轮裁定（2026-10-13，owner：D4=(b) gateway）

- **D4 选 (b)**：空序列 = gateway 级退化输出，**正式奖励 R=0**（reason
  `empty_stages_gateway`）。执行细则：①gateway 在解析+类型门之后检查空 `stages`；
  ②分量诊断保留（r4 V1_empty_stages fail、C0=5/6 照记，仅最终训练奖励置 0，不被 C0
  覆盖）；③不扩大其他惩罚（非空序列仍按 r1–r4+C0）；④回归测试覆盖空/缺失/类型错/
  最小合法 × gateway 开关差异；⑤v1/v1.1 报告留档，新实现新 SHA。
- **重要限定（owner 原文）**：这是针对已知奖励漏洞的**工程裁定**，不等于冻结合同已规定
  空序列违反 schema；若未来把非空 `stages` 正式写入 Planner 合同，另行走合同变更流程。
- **gateway 语义变更**：`gateway_mode` 默认 **True = 正式 RL 奖励路径**；OFF 仅为诊断
  模式（保留 v1.2 前行为）。`composite` 恒载 C0 诊断值；`composite_gateway` 为训练用
  最终奖励。
- **实现状态：v1.2**（模块 SHA `18c4e5a51d7f916b…`）：pytest 12/12（含 owner 要求的
  gateway on/off 回归矩阵）、电池 23/23（含 formal reward 期望）、contract 方言 755/755
  formal 路径复验、D1/D3 回归测试不变通过；`REWARD_BATTERY_REPORT_V1_2.json`
  （v1.1/v1 留档）。
- **放行顺序（owner）**：①gateway 修订+回归 ✅ → ②v1.1→v1.2 差异与 SHA 审查（等
  owner）→ ③S1 只读核验（方言/词表 SHA/adapter 指纹/共租）→ ④S1 结果审查后单独裁定
  S2。**当前不授权 S2。**

## 1. 设计原则

- **P1 GRPO ≠ 去偏**：组内归一化只消加性共模偏移；与候选内容相关的评分偏差会被组内
  比较当作"质量差异"强化。去偏职责 = 奖励验证 + 置信门控。
- **P2 RAFT 不能创造验证器看不见的正确性**：同任务全体候选共有的缺陷会被筛选训练得更
  稳定；RAFT 首轮限定可核验错误类型。
- **P3 单变量纪律**：E1–E7 每级只改一个模块；底座、数据切分、采样预算、评测口径固定。
- **P4 奖励分量分开记录**：合成权重预注册；不可核验分量**显式 mask**（非 0 分），
  mask 数量与原因逐条落盘。
- **P5 成功标准 = 预注册验收条件**，非 loss、非单一 reward 上升。
- **P6 奖励不加码**：冻结 schema 未禁止的结构限制，奖励实现不得自行增加（r4 规则槽位
  全部对齐 Contract Freeze v1 条款）。
- **P7 无猜测原则**：JSON/schema 不可解析时不对不可读字段做任何判断（r2–r4 mask）；
  绝对 repeat 量级只记录不评分（Contract：量级不在 Planner 目标内，E4=diagnostic only）。

## 2. 钉死的配置

| 项 | 裁定 | 依据 |
|---|---|---|
| 输出空间 | Blueprint v2（P0 schema，见 §4.1） | R2 |
| 任务来源 | Phase 1–2 训练任务 ⊂ `planner_v2_train.jsonl`（33,339 行，mdzhang，SHA `443d5d31…`）；扩量从 128,447 权威池切新片并披露 | 泄漏纪律 |
| 禁用材料 | dev-1852、PCA 60 任务、test 任何 split 一律不作训练材料 | 冻结边界 |
| seed | 20261013 | 项目标准 |
| rollout 解码 | repetition_penalty 1.15，固定并披露；禁 ngram/trie 类约束 | P0-B2；V2a 教训 |
| 评测仪器 | 冻结批式三臂脚本 / 6-metric 协议不变，与 rollout 解码分开披露 | 同机纪律 |
| E0 基线 | 复用既有 P0 dev-1852 预测（`p0_dev_full_preds`），不重新生成 | 零成本 |
| 场地 | mdzhang 10.191.2.38；启动前 `nvidia-smi --query-compute-apps`；**资源冲突先停，绝不清理外部进程**；产物及时回迁桌面仓库 git | R3 |
| 吞吐预算 | Qwen3.5 混合架构 vLLM 未验证，rollout 按 HF generate 慢路径预算；S2 量出 tokens/s | E3 冒烟记录 |

## 3. 四阶段总览与 E0–E7 阶梯

| 阶段 | 内容 | 出口条件 |
|---|---|---|
| Phase 1 | GRPO 工程 smoke + 奖励模块验证（§4） | §4.6 双验收，**不证能力** |
| Phase 2 | RAFT / DPO 低风险对照（§5） | **S2 吞吐外推 + owner 单独批准后**启动 |
| Phase 3 | 失败模式/亲和采样 + 门控 GRPO 主实验 | 依赖并行线交付可信子集/多解结论 |
| Phase 4 | 过程奖励 / 估计增强消融 | Phase 3 结果可解释后 |

| 实验 | 训练方法 | 回答的问题 |
|---|---|---|
| E0 | 当前 checkpoint，不训练（复用既有预测） | 基线 |
| E1 | RAFT + SFT | 筛选候选回灌是否有效 |
| E2 | DPO | 明确偏好对能否改善错误区分 |
| E3 | 基础 GRPO + 结构奖励 | 在线优化能否改善结构错误 |
| E4 | GRPO + 置信门控 | 不可靠反馈降权是否有额外收益 |
| E5 | E4 + 失败模式/亲和分层采样 | 定向组织训练任务是否进一步改善 |
| E6 | E5 + 分项过程奖励 | 阶段级反馈能否改善阶段选择与计数 |
| E7 | 最优稳定基线 + Kalman/其他估计增强 | 优势估计改进是否有独立收益 |

E1/E2 可独立分支；E3–E7 按依赖逐级。每级观测统一：parse 率、阶段遗漏率（X4）、臆造率
（X5）、重复结构错误率（X6，presence 口径）、under-emit、harmful-extra、平均长度、
held-out 对照集表现——**禁止只看总 reward**。

## 4. Phase 1：GRPO 工程 smoke

### 4.1 Schema 权威（Contract Freeze v1 原文）

```json
{
  "stages": [{"seq": 1, "family": "<semantic family>", "repeat": <run length>}],
  "repetition_groups": [{"stage_seq": i, "family": f, "repeat": c,
                          "iteration_hint": [<labels>]}],
  "total_iterations": N
}
```

- `stages` = pre-RLE **极大游程**序列（相邻同 family 必须已合并——这是 schema 定义，
  可执行）；语义粒度 **30 类封闭词表**（权威 = 冻结合同数据派生的 family 全集，S1 时
  物化为 `rl_line/vocab30.json` 并 SHA 落账）。
- `iteration_hint` ACTIVE 标签集 = {per_year, per_band, per_class, generic_each,
  unspecified}；**per_feature = disabled（diagnostic_only），预测出现即非法**；
  ABSTAIN 归一化为 unspecified。
- **绝对 repeat / total_iterations 量级不在 Planner 目标内**（Contract 冻结条款）——
  只记录，永不评分。

### 4.2 奖励分量（每分量输出 ∈ {1 PASS / 0 FAIL / MASKED}，附 reason code）

**r1 schema/parse（三级）**
- r1a JSON 语法：整体不可解析 → r1a=0，**r2–r4 全部 MASKED**（P7）；
- r1b 字段缺失：可解析但 `stages` 缺失 → r1b=0，r2–r4 MASKED；
  `repetition_groups` / `total_iterations` 为合同期待字段：缺失**不判负**，登记
  field-presence 观测（S2 报告呈现率，偏差交 owner——防对 P0 输出格式过度假设）；
- r1c schema 类型：字段在但类型不合法（stages 非 list、stage 非 dict、seq/repeat 非 int
  等）→ r1c=0；仅坏条目所属分量 mask，不株连全部分量。

**r2 词表封闭**
- 每个 `stages[i].family` 必须**精确匹配**（大小写敏感、无模糊匹配）∈ 30 类词表；
- 任何未知 token → r2=0（并登记未知 token 清单）；
- **禁止任何频率、长度、亲和族标签加分**（审查轮裁定）。

**r3 重复字段语义（per-entry + 相邻性；不判绝对量级）**
- `repeat` 为整数且 ≥1 → 否则 r3=0；
- **极大游程约束**：相邻 stages 的 family 相同 → r3=0（schema 定义级约束，非自行加码）；
- 绝对 repeat 值大小、total_iterations 数值：**只落盘不评分**（P7；Contract E4 口径）；
  无法从任务文本确定真实次数的维度不判负——本分量天然不含次数判定，结构上满足
  "不可核验不判负"。

**r4 跨字段结构一致（可执行定义）**
- V1 非空：`stages` 长度 ≥1（空序列 = FAIL）；
- V2 seq 连续：`seq` 严格 = 1..N 连续递增（schema 字段定义）；
- V3 rg↔stages 双向一致（仅当 repetition_groups 存在时评估，否则 MASKED+登记）：
  (a) 每条 rg 的 `stage_seq` ∈ [1,N]、`family`/`repeat` 与 stages 对应项一致且 `repeat>1`；
  (b) 每个 repeat>1 的 stage 必有对应 rg 条目；违反任一 → r4=0；
- V4 hint 标签合法：`iteration_hint` 内标签 ∈ ACTIVE 集；出现 `per_feature` → r4=0；
  空列表/缺省 = unspecified，合法；
- V5 total_iterations 类型：存在时须为非负整数（数值不评分）。
- **正反例电池（=单元测试，实现为 pytest，S1 全绿后奖励实现才算冻结）**：
  - P1（正例）：stages=[{1,A,1},{2,B,3}]，rg=[{stage_seq:2,family:B,repeat:3,
    iteration_hint:["per_year"]}] → r1–r4 全 PASS；
  - N1（r3）：相邻同 family（非极大游程）→ FAIL；
  - N2（r4-V3a）：rg 指向 repeat=1 的 stage → FAIL；
  - N3（r4-V3b）：stage repeat=3 但 rg 无条目 → FAIL；
  - N4（r4-V4）：hint 含 per_feature → FAIL；
  - N5（r1a）：非 JSON 文本 → r1a=0 且 r2–r4 MASKED；
  - N6（r1b）：JSON 但缺 stages → r1b=0 且 r2–r4 MASKED；
  - N7（r4-V1）：stages=[] → FAIL；
  - B1（边界）：repeat=1 且无 rg 条目 → 合法；
  - B2（边界）：相邻同 family 被其他 family 隔开（A,B,A）→ 合法（极大性只约束相邻）；
  - B3（边界）：hint 空列表 → 合法（unspecified）。

### 4.3 合成合同（显式可执行，等权需先过验证）

- 评估顺序：r1a → r1b → r1c → r2 → r3 → r4；前级失败按 §4.2 mask 规则级联；
- 分量值域统一 {0,1}，MASKED 退出合成**分母**（不计 0）；
- **候选合同 C0（首选）**：R = mean(可用分量)。不可解析样本 R=r1a=0（唯一可用分量）；
- **冻结前置条件**：①§4.4 电池全绿；②S2 干跑输出逐分量失败率与失败共现矩阵——若 r3/r4
  失败近乎完全共现（冗余）或某分量恒 0/恒 1（无信息），**回报 owner 修定义，不得调权重
  掩盖**（OQ-2 裁定原文）；③上述通过后 C0 冻结，权重写入本协议增补记录。

### 4.4 规模与步骤（OQ-1/3/4 裁定落位）

- **规模**：24 任务 × k=8 rollouts；taskType × target 长度带分层，seed 20261013；
- **S1 环境/数据核验（只读）**：数据 SHA 对账、底座 checkpoint 与 adapter 指纹、
  `nvidia-smi --query-compute-apps` 共租检查、30 类词表物化+SHA、奖励单元测试电池运行、
  **rg 方言指纹**（planner_v2_train targets + 1 条 p0_dev_full_preds 样本——本地核验已证
  两种 rg 方言并存，contract 755 行全过 / anchor 1,078 行属 P1/P2 实验谱系，见
  `REWARD_BATTERY_REPORT_V1.json`；P0=contract 方言目前是推断，须 S1 实证）；
  **任何资源冲突先停**；
- **S2 纯评分干跑（24×8，不更新权重）**：产出完整吞吐（tokens/s）、逐分量奖励分布、
  mask 计数与原因、组内有效差异率、全同组原因登记、field-presence 报告；
- **S3 单步更新**：梯度有限性、参数实际变化校验、adapter 保存/重载字节一致；
- **S4 短程训练（硬上限）**：最多 24 组 × 2 轮 = **≤48 task-group updates，先到为准**；
  全程记录 KL、奖励分布、梯度范数、显存；
- **S5 恢复测试**：中断→断点续跑，训练状态、配置与账本一致性核对。

**S4 异常停止条件（预注册，先触发先停）**：
1. 任何 NaN/Inf（loss/梯度/KL）；
2. 显存异常（OOM 或占用威胁同卡外部进程）；
3. **KL 中止阈值（与 β=0.04 分开定义）**：per-token KL > 1.0 nat 连续 5 次更新，或任意
   单步 > 10 nat → 硬停；KL 记录仅供判读，β 本身不作安全阈值；
4. 训练进程影响共享资源（共租纪律）；
5. adapter 保存或恢复失败；
6. 信号枯竭保护：连续 10 组全 MASKED/全同值（无可用梯度信号）→ 软停并登记。

### 4.5 双验收（审查轮裁定：两条结论不矛盾）

- **工程验收**：§4.4 电池全绿 + S2 至少 1 个非恒定奖励组且差异可归因到预期规则（非实现
  错误）+ S3/S5 通过 + 全链零事故。通过 = 链路可用。
- **信号诊断**（独立报告，不设通过线）：24 组中非恒定组数、逐分量差异贡献、因 mask/
  共同缺陷不可区分的组数。**有效组 < 8/24 时登记"信号覆盖有限"**——工程验收仍可通过，
  但该结果不得解读为可直接扩大 GRPO 训练；Phase 3 扩量前须 owner 重裁奖励区分度。

### 4.6 明确的非目标

Phase 1 不证规划能力提升；不产生对 dev-1852 的任何新读数（E0 复用既有预测）；不改
任何冻结评测配置。

## 5. Phase 2：RAFT / DPO 对照（OQ-5：单独放行）

**放行前置 = S2 吞吐外推报告 + owner 单独批准**。报告必须含：①24×8 实测成本与 tokens/s；
②候选数 k 扩大的成本增长；③RAFT/DPO 在现有资源下的合理规模判断；④Phase 2 任务池、
偏好对构造规则与 held-out 切分的固定清单。Phase 2 不依赖 PCA/多解线。

- **RAFT**：候选过 r1–r4 门槛回灌 SFT（P0 配方复用）；首轮限可核验维度（X5 捏造、格式、
  连接断裂；计数仅取任务文本明确指定子集）。不得把"过结构筛选"等同于"正确工作流"（P2）。
- **DPO**：chosen=合法完整 vs rejected=含可判定缺陷；先只建 gold-free 维度偏好对；合理
  替代工作流不得标 rejected；不为凑算法数量扩展数据工程。
- **评估**：固定 held-out 训练池切片作对照，禁止只观察训练样本改善。

## 6. Phase 3：失败模式/亲和采样 + 门控 GRPO（纲要）

- 亲和 v0 = CAPLOC 失败分解（X4/X5/X6 presence 判定）跑训练池子样本 → 失败模式分层
  采样框；策略探针亲和（直接/先分解/依赖优先/生成后自检）作为正式仪器本阶段引入。
- 任务适配奖励分量 r5（需求覆盖）上线前置 = 并行线交付可信 dev 子集 + 多解判别结论。
- 先普通 GRPO 基线，再逐个叠加采样分层、置信门控；分族报告前后变化。
- 红线：亲和标签不进运行时路由、不直接作奖励加分项。

## 7. Phase 4：过程奖励与估计增强消融（纲要）

- E6：分项过程奖励 vs 整体奖励对照。
- E7 启动条件 = Phase 3 实测 GRPO 优势估计不稳定；定位 = 论文贡献级消融
  （SFT → RAFT/DPO → GRPO → GRPO+估计增强，逐级对照）。

## 8. 禁止清单

不训练于 dev-1852 / PCA-60 / test；不动冻结评测配置；不碰 QGIS Graph / Stage 2；
不重训 P0；不动 `outputs_v2` 大文件；不改写 PCA 线结论；奖励不做频率/长度/亲和加分；
schema 未禁止的限制奖励不得自行增加；无 owner 增补不放宽本协议任何门槛。

## 9. 产物与账本

run_ledger JSON、rollout 原始 dump、逐分量奖励日志（含 reason code 与 mask 记录）、
`vocab30.json`+SHA、单元测试电池结果、执行偏差记录——全部回迁桌面仓库入 git；
任何协议偏离须在偏差记录中先行登记。
