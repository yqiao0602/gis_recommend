# Route-2 v2 总账本（MASTER LEDGER v1）

生成：2026-09-28（Stage-1 训练前的路线总审计；test 半边基线在租卡机上运行中，未触碰）
性质：owner 决策辅助文档。四列口径：**①已证明（有实验证据）/ ②已准备但尚未证明 / ③当前未知与风险 / ④已明确失败或否定（禁止复活）**。
每个条目附证据指针。与 `CURRENT_STATE*.md` 的分工：本文是"科学状态总账"，不记录日常工程进展。

---

## 0. 我们到底在验证什么（主假设的两层结构）

**总科学问题**：大规模 GEE 工作流监督能否帮助 QGIS 工作流生成/grounding？

拆成两层证据（缺一不可）：

```text
第一层（Stage-1 Capability Gate）
  "GEE 数据能把一个 Base 模型训出可测量的 W1–W4 Workflow Reasoning 能力吗？"
  → 回答"能力可形成、可测量"

第二层（Stage-2 QGIS Grounding，须带对照臂）
  "这种能力能迁移并具体帮助 QGIS 吗？提升来自 GEE reasoning 还是普通 domain adaptation？"
  → 回答"可迁移、有因果贡献"
```

**只有第一层 = 只证明了"我们训出了一个 Workflow Reasoning 模型"；
只有第二层 = 无法归因（重蹈三臂覆辙）。** 因此 Stage-2 的对照臂（纯 QGIS SFT 的 C0 式基线）
必须在 Stage-1 出结果**之前**就写进预注册——出结果后再补对照的诱惑是可以预见的。

**2026-09-28 owner 复核定稿：完整因果结构是三扇门，缺一不可**

```text
门一  Stage-1 Capability Gate      —— GEE 数据能否训出可测量的 W1–W4？
门二  Stage-2 Grounding            —— Task+Plan 能否帮助 QGIS 落地？
门三  Causal Comparison（对照臂）  —— 提升是否真来自 GEE Workflow Reasoning？

                         Base
                          │
             ┌────────────┴────────────┐
             ↓                         ↓
       Control Arm                Treatment Arm
     Base → QGIS SFT           Base → Stage-1(GEE) → Stage-2(QGIS)
             └────────────┬────────────┘
                    同一 QGIS 评测面
```

当前在跑的实验（Base zero-shot）回答的是门一的**锚点**部分（见 ①-C）。

---

## ① 已证明（每条有实验证据与产物指针）

### A. 旧路线判决（Route-2 v2 的立项证据）

| # | 结论 | 关键数字 | 证据 |
|---|---|---|---|
| A1 | 三臂排序假设 H1 不成立：GEE 两阶段"拟合成功、迁移未现"，三臂全在噪声带 | dev opF1：C0 .5611 / B1 .5541 / A1 .5510；test：.5059/.4788/.4584 | `test111_final_v1/RESULTS_LOCK_v1`；progress.md 2026-09-23 |
| A2 | **Oracle 判决（情况 B）**：37 类语义链 grounding 全体贴地 | Oracle opF1 .077–.117，EM 恰好全 0；任务文本算子线索（.479）反而多于 gold 语义链（.096） | `ORACLE_RESULTS_LOCK_v1` |
| A3 | 机制终定位：断点在 semantic→operator grounding；被训过两个方向的模型不能零样本组合出第三个方向 | A3 为 A1/A2 的归因结论 | 同上 + error_audit_v1 |
| A4 | error audit：主瓶颈是部分正确的 ops_mixed（55–58%）；parse 失败率单调 C0<B1<A1 在 dev/test 双复现 | 每行欠生成 ~2.9 算子 | `error_audit_v1` |
| A5 | OOD 侧（L-bench final-100）C0 也最强 | C0 .432 > A1 .377 > B1 .347 | 60946c4 |
| A6 | Phase R：C0 配方训练链本身完整可复现；失败纯属 evaluator 资源生命周期 | 3 epochs / 4,002 exposures / 截断 0；evaluator OOM 7.01>6.92 GiB | `phase_r_report.md`（8a2b5b8 定性） |
| A7 | 解码期控制不可修、偏好期 EOS-SFT 净负；trie-EBNF 是唯一生成端正收益但触发 hit_cap | V2a 终局三解释全排除 | a1_mechanism_conclusion_v1（82b0dd4）；V2a 收官记录 |

### B. Route-2 v2 接口与数据实证（⑥ 全链，2026-09-24 冻结）

| # | 结论 | 关键数字 | 证据 |
|---|---|---|---|
| B1 | Plan 接口在**封闭候选空间**客观含区分信息（不是模型猜的，是接口自带的） | Audit-A：UG .774 / AMB .226 / INS 0 / 泄漏 0；93 个 contract-consistent prototype Plans（来自 148 语义映射组），72 uniquely groundable；essentiality：slots −39 / typed-I/O −13 | `PLAN_PIPELINE_REPORT_v1` + audit48 产物 |
| B2 | **Open-set 四层**：Plan 单独撑不住全 catalog，跨家族歧义大 → 必须走 Task+Plan 双条件 | 合同层 UG：L0 .774 / L1_family .731 / L2_catalog .419 / L3_cross .419；AMB L2=.581，amb set 最大 93；硬过滤天花板层（另一产物）1.0/.989/.892/.892 | `openset_grounding_v1_contract.json`（权威）；`openset_grounding_v1.json`（天花板层） |
| B3 | GEE chain→Plan 可规模化：46.6% chain 覆盖（80.3% token） | 59,835 候选 Plan；R1–R4 规则冻结；人工 48 行 pilot 校准 | chain_to_plan_v1_1 + coverage_report_round2 |
| B4 | 三限制如实冻结（不为数字好看而隐藏）：结构缺口 / 修饰词依赖 / 数据碎片化 | P1a 24/21/2；F-STRUCT-01 / D-MOD-01 / DATA-FRAG | `PLAN_PIPELINE_REPORT_v1` |
| B5 | 训练池冻结（是"审计门槛子集"，不是"人工确认完美集"——口径已专门纠正过） | Tier A 28,575 + Tier B 17,690 = 46,265 | `TIERING_FINAL_v1`（v2 unconsumed-dominant 判据三門全过） |
| B6 | gold 反推线零泄漏，只做诊断/上界 | de-grounding 泄漏 0、可恢复步骤 0 | gold_deground_v1 |
| B7 | family checklist 实测出 2 个真实 schema 缺口（EXPORT 语义 6 算子 / GEOMETRY 构造意图 14 算子） | SCHEMA_GAP ×2 | family_constraint_sufficiency_v1 |
| B8 | B2 反循环泄漏设计成立（Teacher Plan 主来源 + gold 禁入生成/修正/选择/重写） | 三 split 同一接口路径；B2 Schema v1 | `ROUTE2_V2_B2_DATA_CONSTRUCTION_v1` |

### C. Stage-1 预检实证 + Base 锚点（2026-09-26/28，最新）

| # | 结论 | 关键数字 | 证据 |
|---|---|---|---|
| C1 | v2_2 候选数据集全绿：精确配比 / Task 保护 / 池零违规 / Chain LM 0 | 56,710 行（core 37,044 / completion 7,876 / recon 3,803 / w4 7,987）；token 60.001/10/9.999/20；Task 截断 0；W4 子类型 delete 2723/swap 2619/insert 2645（自然分布） | `stage1_dataset_report_v2_2.json` + 溯源审计 0 违规 |
| C2 | Gate-v3 探针冻结：dev 3,236 / test 3,256，legacy W3 基集逐字节保留 + 492 改写对精确 join | probe SHA dev `c3d95f67…` / test `866c3762…` | `gate_build_report_v3.json` |
| C3 | 唯一评分器 v1.3.1 冻结（含 batch_halvings report-path bugfix：先复现后修复，9/9 回归） | evaluator SHA `c2e7d725…`；推理配置 SHA `6355bab4…` | `gate_evaluator_freeze_v1_3_1.json`（b57e3fa） |
| C4 | **Base zero-shot dev（基线锚点）：W1–W4 全 0.000** | n=1690/783/238+236/289 全 0；invalid 2795/3236=86.4%；OOM 0 / timeout 0 / halvings 0；11.16h 真实生成 | `base_zero_shot_v1/gate_report_base_zero_shot_dev.json`（0a41a6d） |
| C5 | dev 全零的**定性解读**（有逐探针证据，非猜测）：是格式不服从而非无知 | W1 9% parse（在"描述答案"）；W2 0/783 以 Yes/No 开头（输出 `<think>` 续写）；W3 0 parse 但**语义分解本能存在**（合理分解、错误格式）；W4 parse 100%——**格式可被上下文 prime 出来** | `gate_items_base_zero_shot_dev.jsonl` 逐条样本 |
| C6 | test 半边在租卡机 RTX 3090 复跑中，与 dev 严格同栈（三 SHA 预置对账） | 模型四分片清点一致；evaluator 120s 存活判定通过 | `/root/data/gate_rerun_v1/`（运行中） |

---

## ② 已准备但尚未证明

| 项 | 就绪程度 | 依赖 |
|---|---|---|
| Stage-1 训练本身 | 数据/配方/截断合同全冻结，一键可发 | owner 放行令 + GPU |
| test 半边基线 | 运行中（~11–12h） | 无 |
| W1–W4 阈值预注册 | 材料齐（dev 锚点 + 本账本 ③ 的平凡策略基线表） | owner 裁定数值 |
| Teacher Plan 生成 | 流程冻结（Stage-1 冻结后 QGIS Task→Plan） | Stage-1 Gate PASS |
| B2 数据包生产 | Schema v1 + assembly 合同 + family checklist 就绪 | Teacher Plan + Audit-A 已过 |
| Stage-2 设计骨架 | L1 纯 SFT 主轨 / L2 温和终止 / L3 完成度多任务 / L4 偏好对，D1–D4 待裁 | B2 |
| Phase R evaluator-repair rerun | 仅生命周期修复的注册条款在案 | owner 另批；排程在 Stage-1 Gate 后 |

---

## ③ 当前未知与风险（按重要性排序）

### R1（最高）。模型能否真的学会——未回答
所有 ② 都是"准备"，无一证明学习会发生。这是 Stage-1 的唯一存在理由。

### R2（本账本新识别）。**Base=0 使 Δ 条件失效，绝对下限成为唯一真门**
dev 四项全 0 ⇒ 任何非零提升都自动满足 "Base+Δ"。阈值预注册时若下限设得过低
（例如仅"比 0 大"），Gate 将毫无判别力。**下限设定是现在整个实验链上最重要的一个数值决定。**

#### R2 阈值评审共识（2026-09-28，owner 复核裁定——冻结性裁定，后续评审按此执行）

1. **Δ 条件正式降级为诊断记录**：预注册文本须明确写
   *"Base-relative margin is recorded diagnostically but is non-discriminative on the
   current dev baseline because Base zero-shot scores are 0."*
   保留记录、不再作为有效门槛条件。
2. **Floor 分三层思考，禁止直接跳数字**：
   - 第一层 非平凡性下限：严格压过 trivial baseline（W2 >0.7903 / W3 >0.5044，test 口径）
   - 第二层 有意义能力门槛：真正要注册的门（须同时满足"击穿平凡策略"与"现实可达性"）
   - 第三层 参考性能：oracle/human/strong baseline——只帮助解读，**不参与 Gate，且不得事后临时找**
3. **W2 采用双条件门结构**（数值留待评审裁定）：`overall ≥ X AND No-class ≥ Y`。
   No-class 准确率可从 gate_items 事后计算（gold 字段在案），**无需改 evaluator**。
   设计动机：结构性堵死"恒答 Yes"路径；W2 的本质是合法/非法连接的判别，
   Yes=100%/No=0% 即零判别。
4. **W3 rewrite 维持诊断位**，不转正为 Gate 条件、不设事后阈值；gap 大→查表面模板依赖，
   属解释性证据。
5. **W1/W4 不套用 W2/W3 逻辑**：二者 trivial 基线恒 0、无非平凡锚点，
   floor 只能由"合理可达性 + dev 二项噪声"推理得出，留待评审逐项裁定。
6. **程序裁定**：现在不定任何数值。等 test Base 返回后开 **R2 Gate Threshold Review**
   专场，一张表对齐（dev/test Base × 平凡基线 ×2 split × 各能力探针数 × No 类数），
   逐项裁定后注册，随即进入 Stage-1。在此之前**不动训练、不动数据、不动 evaluator**。

辅助思考工具——**平凡策略基线表**（2026-09-28 已在 CPU 上对冻结探针精确算出，非估计）：

| 能力 | 平凡策略 | dev 实测分 | test 实测分 | 对设门的含义 |
|---|---|---|---|---|
| W1 | 任意输出 | ≈0 | ≈0 | 下限须显式大于 0（owner 定） |
| W2 | **恒答 Yes** | **0.7791**（Yes 610 / No 173，**标签严重偏斜，并非此前口头所称"平衡"**） | **0.7903**（Yes 520 / No 138） | **下限必须显著 >0.79**，否则"学会说 Yes"即过门；预注册应同时跟踪 **W2-No 类准确率**（dev n=173 / test n=138，可从 items 事后计算）作为反偏斜诊断 |
| W3 | 恒输出众数 family 序列 | **0.4973**（众数序列频次仅 42/474≈8.9%） | **0.5044** | **下限须显著 >0.50**；众数序列长度自适应变体仅 0.3758（dev），以固定序列 0.497/0.504 为下限锚 |
| W4 | 抄写损坏 plan（不修复） | ≡0（构造上损坏≠gold） | ≡0 | 下限 >0 即有意义 |

**由此得出的预注册硬结论**：Base=0 使 Δ 失效后，Gate 的全部判别力压在绝对下限上；
而下限的天然敌人是上表两个平凡策略（W2 恒 Yes ≈0.78–0.79、W3 众数序列 ≈0.50）。
**低于这两条线的门等于没有门。** 建议预注册文档按"平凡策略基线 + 有意义的裕量"格式
给出每项下限（例如 W2 ≥ 0.85–0.90 且 No 类准确率单独达标；W3 ≥ 0.55–0.60；数值由 owner 裁定）。
另注：probe 计数"dev 783 / test 658"是**数量**对称的口径，与标签分布无关，勿再混用"平衡"表述
（正式文档中没有该错话，仅会话摘要层出现过，已在本账本更正）。

### R3。FAIL 时的四分叉归因（防止把数据噪声误读为模型无能）
59,835 候选 ≠ 人工确认；已知 F-STRUCT-01 / D-MOD-01 / DATA-FRAG 三限制冻结在案。
若 Stage-1 FAIL，必须区分：
```text
A. 模型没学会（容量/配方问题 → ⑦ 的 FAIL 同协议续训条款）
B. 数据噪声（→ 池再收紧，如 Tier A-only 消融）
C. Plan Contract 缺信息（→ 回到 ④/⑤ 审计，B7 的两个 SCHEMA_GAP 是嫌疑）
D. GEE→Plan 转换损失过大（→ R1–R5 转换器迭代）
```
**不允许看 loss 直接下结论**（⑦ 冻结条款：成功标准 = 门，非 loss）。

### R4。跨家族歧义是结构性的，Stage-2 设计必须直面
L2 UG .419 / AMB .581 / amb set 最大 93——即便 Stage-1 满分，Plan 单独也不够。
Stage-2 必须消费 Task+Plan 双条件（已经是 ⑤ 的冻结设计，此处是提醒不要在实现时退化）。

### R5。两层证据结构（0 节）——Stage-2 对照臂现在就要预注册
最容易被"结果好看"诱惑而跳过的就是对照。已按 2026-09-28 共识把两臂结构
（Control: Base→QGIS SFT / Treatment: Base→Stage-1(GEE)→Stage-2(QGIS)，同一评测面）
写入 0 节；Stage-2 预注册文档落地时必须原样引用该结构并固定配方等价性
（除 Stage-1 中间层外，两臂的 SFT 数据/配方/评测完全一致）。
没有对照，Phase F 的任何提升都不可归因（A1–A5 的直接教训）。

### R6。统计量偏小处
W3 dev 仅 238+236 条；dev 全零后，W3 的提升幅度估计将依赖这 ~474 条，
预注册 Δ/floor 时应按二项噪声 thinking（±0.03–0.05 量级波动正常）。

### R7。工程风险（已知、可控）
租卡机 15GB RAM（NF4 加载已实证 OK）；3090 24GB 训练 batch 32 可行性待 smoke；
aria2/镜像下载教训已固化（见 progress/记忆）。

---

## ④ 已明确失败/否定（禁止复活清单）

| # | 被否定路线 | 判决证据 | 备注 |
|---|---|---|---|
| N1 | **37 类语义工作流作中间层** | Oracle 全贴地（A2/A3） | v2 架构的立项理由 |
| N2 | H1"三臂排序"假设 | 噪声带（A1） | 归因已转向接口 |
| N3 | DAPT（decoder 骨干域预训练）净正收益 | M2：A1 ≤ C0；DAPT 净效应为负 | M1 线收束 |
| N4 | M1 scratch-decoder 路线 | task_type OOD + 条件映射不解；R3/R4 关闭 | Phase 0-B 归因 |
| N5 | Chain LM 训练目标 | ③-C：A1 反例 | ⑦ 冻结 Chain LM=0% |
| N6 | 旧 B2（纯 semantic→QGIS SFT） | 被 v2 两阶段**替代**（其"需专门 grounding 训练"的预注册内核被吸收进 Stage-2） | 非失败，是被取代 |
| N7 | decode 期输出控制（mask/EOS-SFT/ngram 约束） | DC-1 反致恶化 / DC-2A FAIL / V2a 收官 | trie-EBNF 仅存档 |
| N8 | W4 过度限制生成规则（delete/swap 也要类型流断裂） | 子类型塌缩 32/11/7479 | owner 裁定恢复结构变体（现行） |
| N9 | "Plan 单独 → QGIS"（单条件 grounding） | B2 的 L2 .419 | 已由 Task+Plan 双条件替代 |
| N10 | GEE/QGIS 数量对称假设 | 数据角色定义（GEE 教 reasoning，QGIS 教 grounding） | 2026-09-02 冻结 |

---

## 下一场训练（Stage-1）成功/失败的决策树

```text
Stage-1 1 epoch → gate-dev
├─ 全四项过（绝对下限 AND Δ）……PASS
│   → 冻结 checkpoint → test 判定 → Teacher Plan → B2
│   → 立即预注册 Stage-2 对照臂（R5，趁没人被结果诱惑）
├─ W3 高、W1/W2 低 ……………… 模板记忆实锤
│   → 不进 Stage-2；查训练多样性/W1W2 权重；（C4 的 W4-priming 证据提示格式可学，非死局）
├─ 全面低 ………………………… 走 R3 四分叉，优先 B（数据噪声）消融
│   → ⑦ 条款：FAIL 同协议续训（1 epoch → 继续）
└─ W4 高、生成类低 …………… 结构判别可学、生成不行
    → 指向 core 数据质量 / 目标函数权重，B7 SCHEMA_GAP 嫌疑审查
```

---

## 附：本账本对贴出复盘的三处更正

1. "Base zero-shot ❌"→ **dev 半边已完成**（全 0.000，0a41a6d），test 在租卡机复跑中。
2. Open-set 实为**四层**（L0/L1_family/L2_catalog/L3_cross），且存在两个口径：
   硬过滤天花板层（1.0/.989/.892）与合同层 UG（.774/.731/.419/.419）。
   引用时必须注明口径，否则会高估 Plan 的独立 grounding 能力。
3. 其余数字（46,265 / 59,835 / 56,710 / W4 子类型 / v1.3.1 修复史）逐项核对无误。

---

## 2026-09-30 owner 实验总纲修订：Performance First → Explanation 两阶段

**第一阶段 Performance First（当前）**：只推 Qwen3.5-9B 在任务上的最终指标——
SFT → 数据配方 → 训练策略 → 推理策略 → 必要时 DAPT/RL → Best Model。
GEE/DAPT/RL"为什么有效"的归因问题**全部推迟**。

**第二阶段 Explanation（触发条件 = 拿到显著强于当前 baseline 的 Best Model）**：
届时跑 w/o GEE / w/o QGIS / w/o DAPT / w/o structural / w/o RL 消融——
"消融只在有 Best Model 之后才有意义"。

**对既有结构的修订**：本账本 §0 的"三扇门"框架中，门三（Causal Comparison 对照臂）
降级为第二阶段内容；双臂 artifact（C0-QGIS/A1'-QGIS）保留并核验完毕，其 paired eval
降级为**选型依据**（为 Best Model 的 grounding 阶段选最优 init）而非归因证明——
因仅 ~2–4h GPU 且可与空闲档并行，保留在队列中但优先级最低。

当前 Phase-1 主线（不变）：**P0 Planner-v2 格式修复续训**（mdzhang A10 运行中）
→ checkpoint 曲线评估（parse .809→.95+ 过程中守住结构）→ 双臂 eval（选型）
→ Planner-v2 + QGIS grounding 三方对比 → Best Model → 进入第二阶段消融。
