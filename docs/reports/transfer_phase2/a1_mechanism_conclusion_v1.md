# A1 负迁移机制结论（冻结版 v1）

日期：2026-09-24 冻结
地位：**Gate 2 → FA → DC 诊断链的终稿结论**。本文档冻结后，该问题视为已回答；后续工作（Stage 2）以本结论为设计输入，不再重新打开诊断。
owner 裁定（2026-09-24）：选项 3 收口；选项 1 转化为 Stage 2 设计原则（Output-discipline post-training）；选项 2 不注册；RL 维持押后；**A1 不再调/训/DAPT，C2 冻结**。

## 1. 被冻结的机制陈述（论文句，措辞已锁定）

> **正确 token 仍然经常位于最高概率位置，但其概率优势下降，概率质量向其他候选续写分散；在自由解码过程中，这种分布变化进一步表现为过度续写和停止控制失败。**

补充表述（措辞纪律）：结果呈现出**与 exposure-bias / autoregressive error accumulation 一致的路径依赖特征**——此为机制解释，非已证因果；严格因果确认需要额外干预（gold-prefix 条件即已证明方向一致：D1① 对比 D1②）。

一句话版本：**A1 并没有失去 next-step selection 能力；失去的是自由自回归生成中的控制稳定性。**

## 2. 三类简单解释的排除记录（全部单变量、全部预注册）

| 假设 | 实验 | 结果 | 排除依据 |
|---|---|---|---|
| 模型"不知道下一步" | FA-D1① teacher-forced | top-1 acc：C0 78.5% vs A1 **78.8%**（Δ +0.003，CI ∋ 0） | 选择能力统计无差 |
| 非法 token 抢走生成空间 | DC-1 trie mask（EOS 显式放行） | hit_cap 18.0% → **34.2%**（EOS 合法仍复现 ≈P2 事故） | 删选项反致合法跑马加剧 |
| 提高 EOS 相对 logit 即可解决 | DC-2A-R1 EOS bias（β=3.5625，C0 健康边际标定，触发覆盖 100%） | hit_cap 仅 −2.7pp；repetition −0.9pp；precision −0.025；op F1 −0.031 | 边际补偿不足以恢复控制 |

## 3. 证据链全貌

```text
Gate 0  GEE 语料含真实组合结构（PASS，覆盖率/多样性/结构保留 94.56% 映射另证）
Gate 1  可提取信号以局部统计为主（MIDDLE：探针 38.03% vs trigram 39.69%）
Gate 2  GEE DAPT → QGIS：负迁移（op e2e 0.267 vs 0.343，CI<0；Gate 3 零污染）
FA      Planning 保留（D2 CI∋0）· 非主因 Grounding（D3 72% 同族）·
        teacher-forced acc = C0（D1①）· 自由续写失控（D1②：EOS −14.7pp、注入 ×3.9）
DC-1    trie mask：C0+DC 净收益（F1 0.370 = C0 最佳）· A1 反向恶化（红线）
DC-2A-R1 EOS bias：五判据 FAIL（F1 −0.031）
        ↓
诊断终点：知识完好 · 控制失效 · decode 期边际干预（删选项/补边际）均无法恢复
```

关键对照（同 mask 反向符号）：C0+DC F1 0.343→**0.370**（precision 0.518，C0 迄今最佳）vs A1+DC 0.267→0.216——mask 对分布健康臂是纯增益、对摊平臂是纯伤害，**构成 Control 归因的近实验证明**。

## 4. 设计原则（转入 Route-2 v2 Stage 2）

1. **Output-discipline post-training**：Stage 2 训练目标链 = Task → Workflow plan → QGIS grounding → Structured graph → **正确结束**——EOS/长度/非重复/完整结构本身是训练目标的一部分，不是解码期补丁。
2. **对照设计**：C0（baseline）vs C0+（output-discipline post-training）；**A1 仅作已诊断失败案例保留，不进入修复实验**——"A1 为什么失败"（FA 已答）与"知道机制后怎么训练"（Stage 2 待答）两问永不混合。
3. **GEE 位置重定义**：GEE 不是直接优化 QGIS decoder 行为的 DAPT 数据源；其合理位置 = **结构 / workflow composition supervision**（"GEE 教怎么组合，QGIS 教怎么落地"在机制层重新对上）。
4. **Stage 1 能力验收门（v2）**：Learnability（next-op acc / semantic planning / grounding）与 Generation Control（EOS / repetition / runaway / valid graph formation）**分开验收**。

## 5. 溯源（全部入库）

Gate 2 报告 `613d732`；FA 报告 `afc5120`（D1/D2/D3 + 语义映射 v1）；DC-1 报告 `618fac1`；DC-2A 原版 spec `9a23c13`（冒烟门捕获覆盖洞，未执行全量，归档）；DC-2A-R1 spec `eae51b9`；DC-2A-R1 终局与本文档同批提交。工件：`docs/reports/transfer_phase2/{gate2,fa,dc}/`（锁定预测、评分 JSON、β 锁、日志、全量预测）。

## 6. 遗留与未决

- L-bench（final-100 + refusal-12）：P0-6 辅判据，未执行，主判据不依赖；
- C2（n-gram 特征注入）：冻结，注册权在 owner；
- RL：押后至输出纪律基线成立后（届时 RL 的角色 = 优化已具 workflow knowledge 模型的整体生成策略）；
- Route-2 v2 Stage 1 接口/验收门设计：由并行线推进，本结论作为其设计输入。
