# domain_corpus_v1 构建规则（Spec v1）

状态：v1 已冻结（2026-09-11 owner 批准，三项决策见 §11）
服务对象：M1-R2/R3/R4（M1 增强消融路线）、M2-P1（Qwen3.5-9B-Base DAPT）
上游依据：`docs/qgis_three_model_routes_zh.md` §4.5 / §6.1（`domain_corpus_v1` 与 `paper_v1` 双 manifest 设计，名称沿用该文档）
实验背景：M1-R1 在 benchmark v0.2.1 final-100 上 OOD 塌缩（88 空图、100/100 以 L3_01_10_02 Define Projection 开头、val Top1 13.75%），M3 输出跟随任务文本（74% token 覆盖内）。M1-R1 与 M3 的 benchmark 对比表明，具备大规模预训练先验的模型表现出显著更强的 OOD 任务条件化能力；**但该差异同时受模型规模（117M vs 9B）、语言覆盖（英文 BERT vs Qwen 双语）、task_type 条件（M1 使用、M3 不使用）以及预训练方式等因素影响，不能单独归因于预训练先验**。本轮通过 M1-R2 的领域自适应预训练消融，量化领域预训练对 scratch decoder OOD 泛化的独立贡献；domain_corpus_v1 是该消融的数据基础设施。

## 1. 定位与边界

- domain_corpus_v1 是**无监督领域语料**：只做 causal/MLM language modeling，不带任何 L3 标签。
- 与 `paper_v1`（监督 manifest）并存为两个独立 manifest；监督数据的使用规则不变。
- 构建与使用**不修改**：paper_v1 各 split、benchmark v0.2.1 全部 release、M1-R1/M3-P1 checkpoint 与冻结的推理/预测结果。
- 一个 manifest 管多个 recipe（§9）：数据 authority 统一，配方差异显式记录。

## 2. 前置确认（构建启动前必须完成）

| 编号 | 内容 | 目的 | 成本 |
|---|---|---|---|
| A | 任务文本语言分布实测：benchmark v0.2.1（dev 20 / final 100 / refusal 12）与 paper_v1 train 8,817 的中/英/混合占比 | 决定语言池设计（§7.3）；决定论文中 M1 失败归因是否需单列"英文 BERT vs 中文任务文本"混杂 | 只读统计，分钟级 |
| B | task_type oracle vs Unknown 推理消融：同 M1-R1 checkpoint，49 行 val 上分别用真实 task_type 与 Unknown 推理，比较 SetF1 / P / R / Top1 / 空图率 / 首 token / 输出长度 / Define Projection 比例 | 量化 FiLM 条件 + 动态长度先验缺失的混杂（task_type OOD）。若 Oracle 明显恢复，则 M1 collapse 有部分来自推理条件分布外而非语言/领域先验不足——这会直接改变 M1-R2 结果的解读框架。结果只作论文注脚与 M1-R2 归因依据，不修改 R1 正式结果 | 零训练，单次推理 |

A 是语料构建的前置；B 是 M1-R2 实验的前置，二者都先于任何 DAPT 运行。

## 3. 语料池定义

| 池 | 内容 | 供 DAPT | 供 TAPT |
|---|---|---|---|
| D1 QGIS/PyQGIS 领域知识 | 算子描述、参数语义、I/O 契约文本 | ✅ | — |
| D2 GIS/OGC/GDAL 基础知识 | CRS、投影、几何、格式、NoData 等概念文本（v1 仅含 KG 本地概念描述；外部文档本轮不纳入，owner 决策 ①） | ✅ | — |
| D3 QGIS API/Processing 代码 | 源码文本（作为代码语言） | ✅ | — |
| D4 GIS 工作流描述 | docstring、任务性注释、README、plugin/tutorial metadata、工作流叙述（**不含 L3 标签**） | ✅ | ✅ |
| D5 SFT train 任务文本 | paper_v1 train split 的任务文本（仅文本，不带 L3） | — | ✅（限 1 epoch，见 §5） |

三者的实验边界：

```text
DAPT：GIS 世界的语言与知识（D1/D2/D3 + D4 可选）
TAPT：GIS 任务世界的表达（D4/D5）
SFT：  task → L3 序列（paper_v1，已有，本 spec 不碰）
```

## 4. 来源映射（现有资产）

| 资产 | 池 | 规模/状态 |
|---|---|---|
| Neo4j KG 节点描述：QGIS_Operator 1,291、GEE_Operator 1,425、DataType 486、L3_Primitive 350（legacy）；taxonomy_128_v1 的 128 类名称/描述 | D1/D2 | 已在库，结构化导出为文本即可，零采集成本 |
| `/home/yll` 源码 47,852 个唯一 source SHA（只读） | D3 | 百 M token 级，**待实测** |
| Asset Miner v2 侧池：api_implementation_evidence 12,410、unresolved 23,650、api_pattern 4,880、api_semantic_unit 3,209 等 | D3/D4 | SFT 筛选淘汰数据，恰为 domain corpus 富矿（筛选标准不同：前者问"能否当可靠监督样本"，本 spec 问"是否领域语言"） |
| Phase 1 inventory 描述来源（2026-07-14 记录）：plugin metadata 2,009、README 2,054、model/tutorial metadata 851、48,011 源码文件可抽 docstring | D4 | inventory 数字略旧，构建时复核 |
| GEE 侧文档/描述（GEE 工作区维护的资产） | D1/D2/D4 | 需 GEE 工作区确认可复用范围，本 agent 不改写其结论 |
| QGIS/GDAL/OGC 官方文档 | D2 | **本轮不纳入（owner 决策 ①，2026-09-11）**；未来纳入时需许可登记并升 corpus 版本 |
| paper_v1 train 任务文本 | D5 | 8,817 行（GEE 8,283 + QGIS 534） |

## 5. 准入规则（三分法）

- **进 DAPT**：D1/D2/D3/D4 全部通过 §6 泄漏隔离与 §7 去重清洗的文本。
- **进 TAPT**：D4 + D5。D5 限制：仅 train split、仅裸任务文本（剥离一切 L3/算子链字段）、最多 1 epoch、在 manifest 中显式记录占比，防止 DAPT/TAPT 与 SFT 边界模糊。manifest 必须单独记录 `D5_token_count`、`D5_ratio`、`D5_epoch`、`D5_sample_count` 四项，使"SFT 数据是否被重复预训练"可直接审计回答。
- **硬排除**：
  - paper_v1 val 49 / test 46 的任务文本及其来源（source identity 整组）；
  - benchmark v0.2.1 dev 20 / final 100 / refusal 12 的任务文本及其 source-backed 来源源码（source SHA 整组）；
  - 一切 `task → L3` 监督对、gold chain、accepted alternatives、评分规则派生物；
  - benchmark 排除签名命中的 token 序列形态（复用既有排除索引）。

## 6. 泄漏隔离（四层，全部复用现有纪律）

1. **源码层**：按 source SHA / source identity **整组**排除 benchmark 与 paper_v1 val/test 的来源，与 paper_v1 source-disjoint split 同一纪律，不做逐行豁免。
2. **文本层**：6-gram 检查复用 benchmark 冻结时的同一套工具与口径；检查对象 = benchmark dev/final/refusal 任务文本 + paper_v1 val/test 任务文本。domain corpus 全部文本对上述对象 6-gram 命中 = 0 才能冻结；命中即剔除该文档/片段并记入 ledger。
3. **结构层**：DAPT/TAPT 文本不得出现 `START/L3.../END` 监督形态、L3 码序列标注、gold 或 accepted-alternative 内容（M2 文档 §6.2 已有此条，沿用）。
4. **许可层**：每个来源登记 URL/版本/许可证/内容 hash。已知缺口：`/home/yll` 源码为 GitHub 抓取、许可证构成未审计——第一版如实记录来源与 SHA，许可分级审计列为后续待办；无法澄清来源的外部语料不用。

## 7. 去重、清洗与语言分池

- 去重：文档级 SHA + 段落级精确 hash（MinHash 近似去重可选）；源码按已有唯一 source SHA，文件内剥离 license header 与自动生成代码。
- 清洗：保留算子名、参数语义、I/O 类型、版本信息（M2 文档 §M2-1 要求）；去除导航、重复模板、无语义 boilerplate。
- 语言分池（依赖前置确认 A 的实测结果）：
  - **英文池**：M1 的 bert-base-uncased 可消费；
  - **中文池 / 双语池**：仅 M2/M3（Qwen 系）可消费；
  - 各池规模、占比进 manifest；不得为对齐 M1 与 M2 的语料量而裁剪对方语言池（配方差异如实报告）。

## 8. 规模策略

- **先实测再定稿**：对 §4 各来源跑 token 计数（代码与文本分开统计），再冻结第一版规模。
- 起点量级：100M 参数级模型 DAPT/TAPT 经验值为 **50–200M token** 即可有可测增益。Phase 1 首轮实测（2026-09-14）：D3 权威源 47,852 文件 = 0.74GB 原始（≈185–250M token 估算）；D4 README 全树 71.7MB（≈15–17M，未过滤）；D1 taxonomy 16.2K 字符；D5 train 任务文本 2.78M 字符（≈0.65M）。
- **原始规模 ≠ 训练规模**：D3 必须过完整构建管线（排除组 → 6-gram → code cleaning → 自动生成/license boilerplate 剥离 → dedup → 语言分池）后才计入 usable corpus。**不得为凑规模放宽任何过滤条件——宁可 100M 高质量 token，不用泄漏或重复代码补数。**
- 若做规模敏感性，仅对主路线（M1-R2 或 M2-P1 之一）设 2–3 个规模点，其余单点，对齐三路线文档 §6.4 的规模曲线纪律。

## 9. Recipe 分离（一个 manifest，多个配方）

| 消费方 | 配方 | 备注 |
|---|---|---|
| M1-R2/R3/R4 | **D3 代码语料为主体，D4 英文 GIS 文本为核心语义补充，D1 为少量领域锚点；D5 不进入 M1-R2（仅 TAPT 候选）**。最终采样比例不预设死值，由构建后真实 token census 确定并固化于 manifest；可用 D4 oversampling / D3 downsampling，但实际 token exposure（D3/D4/D1 各自 token 数与占比）必须写入 manifest。D2 仅含 KG 本地概念描述 | owner 拍板 2026-09-14（选项 b）：纯文本池（D1+D4 ≈15–20M）低于经验起点一个数量级，D3（47,852 源 ≈0.74GB 原始）单独达标；任务形态"英文 → L3 结构化符号序列"与代码语料同族——D3 提供结构化序列建模先验，D4 提供 GIS 自然语言领域语义。风险控制：D3 不得淹没 D4 的语义信号，配比以实测 exposure 为准 |
| M2-P1 | D1–D4 全量（含 D3 代码） | 与三路线文档 §M2-1 的领域语料定义一致 |
| M3 | 不消费 | M3 按定义不做 DAPT/TAPT |

每个实验的运行 manifest 必须记录所用 recipe、池构成、epoch、token 数；配方差异在实验表中显式列出（对齐 §6.5"允许差异"条款）。

## 10. M1-R2 实验合同（**implementation contract 已冻结，2026-09-14 owner 确认配比**）

- **目标定义（owner 2026-09-14，Phase 0-B 后修订）**：R2 不是"修复 M1-R1 benchmark"，而是在 task conditioning 与推理协议完全不变的前提下，测试 decoder 骨干领域预训练能否提高 M1 对 GIS 领域工作流语义的泛化——即使 F1 0.00→0.08 也有明确解释价值。R1→R2 唯一主动变量 = **decoder 初始化（random vs domain-pretrained backbone）**；不得因 Phase 0-B 发现 Unknown 有害而在 R2 改用 Oracle task_type。
- **实验名称（owner 2026-09-14 修正）**：**decoder backbone domain pretraining**，不写 "decoder-only CLM-DAPT"。原因：decoder 的 132-token L3 词表与 DAPT 语料无共同词表，临时词表的 embedding/输出投影在 SFT 时被丢弃——**真正迁移的只有 Transformer body + FiLM，lexical embedding 不迁移**。R2 测试的是"GIS/代码领域 exposure 能否改变 decoder 骨干的参数先验、使其在后续 L3 监督生成中具有更好的结构化生成能力"。
- **Corpus recipe（owner 拍板 2026-09-14，基于 attempt-2 census）**：
  - D3 代码池：**60% 降采样**（固定 seed，记录被抽样的 SHA 清单）
  - D4 英文领域文本（docstring 112,196 + README 1,276）：**4× oversampling**（epoch/sample 级、固定 seed、可复现；不简单复制 JSONL 四遍）
  - D1 taxonomy 锚点：**原始保留（1×），不做大规模过采样**——D1 作用是锚点不是训练量来源（3.4K WP token 拉到 5% 需重复 ~2000 倍，只会过拟合 taxonomy）
  - **Target exposure：D3 ≈ 80% / D4 ≈ 20% / D1 ≈ negligible**（实测 byte 口径 80.1% / 19.8% / 0.003%）
- **双口径 token 纪律（防止口径混用）**：
  - **Census token = wordpiece**：描述 corpus 语言/文本规模（D3 174.7M / D4 6.6M / D1 3.4K，总 181.3M WP）——**不是训练预算**
  - **Training token = byte-level**：实际 DAPT budget = **487.5M byte-tokens**（D3 0.6× = 390.7 MB + D4 4× = 96.8 MB + D1 16 KB）——用于 steps/epoch/lr-schedule/GPU 时间/checkpoint 解释
  - 任何报告不得把 181M WP census 写成训练 token 数
- **初始化合同（owner 九项拍板 2026-09-14）**：
  - DAPT 阶段：临时 **byte-level** tokenizer（256 bytes + specials；不用 wordpiece——lexical transfer 本来就不发生，byte-level 简单稳定且避免"共享词表产生 lexical transfer"的错误解释）；embedding/输出投影按临时词表随机初始化；条件输入 = **哑 memory（零向量）+ task_type=Unknown**（纯序列先验，不接真实文本 memory，避免与 SFT 边界模糊）；可训练 = 临时 embedding + 输出投影 + Transformer body + FiLM。
  - SFT 阶段：**丢弃临时 embedding/输出投影**；132-token L3 词表 embedding/投影**重新随机初始化**；**Transformer body + FiLM 从 DAPT checkpoint carry over**；最终 L3 词表与 R1 完全一致（公平性保证）；SFT 协议 = R1 完全不变。
- **论文标准表述（不得偏离）**："在保持最终 L3 输出词表与 SFT 协议不变的条件下，首先利用 GIS 代码与领域文本对 Transformer 解码器骨干进行无监督领域预训练，再将预训练后的骨干迁移至 L3 工作流生成任务，以考察领域预训练对结构化工作流生成泛化能力的贡献。"**不得写**"通过 DAPT 学习 GIS 领域词汇表示并迁移至 L3 decoder"，也不得写"给 M1 增加了 181M 个领域 token"。
- **BERT 领域 MLM（encoder 侧适配）不属于 M1-R2**，作为后续 M1-R3 候选消融（Phase 3 视 R2 结果决定）。届时 R2→R3 唯一新增变量 = encoder 领域适配。
- 架构与 SFT 协议完全复用 M1-R1（V4.6、70:30 平台分层采样、paper_v1 train 8,817、20 epochs、同 checkpoint 选择标准）。
- 评测协议与 M1-R1 完全一致（含 `INFERENCE_CONFIG_FREEZE_v1.json` 的 task_type=Unknown 与解码配置）。
- 验收：主指标 = benchmark（先 dev-20 后 final-100）空图率下降与首 L3 token 多样性恢复（不再单一 Define Projection 开头）；次指标 = val Top1 相对 13.75% 的增量、49 行诊断 P/R 相对 0.153/0.198 的增量。
- 归因声明：M1-R2 vs M1-R1 同架构、同 encoder 冻结状态、同 SFT 协议、同解码 → 差值 = decoder 骨干领域预训练的独立贡献。前置确认 B 的结果作为归因解读的注脚。

## 11. owner 决策记录（2026-09-11）与执行顺序

三项决策已定，spec v1 冻结：

1. **D2 外部文档（QGIS/GDAL/OGC docs）本轮不纳入**——避免新增许可证、来源与语言变量；v1 先验证本地资产是否足以缓解 collapse。
2. **M1-R2 固定 decoder-only causal-LM DAPT**；BERT encoder 保持 M1-R1 冻结配置不变。BERT 领域 MLM 移为 M1-R3 候选消融。
3. **R3/R4 暂不开**，R2 出结果后决定；若 R2 已解决大部分 collapse，则不继续堆预训练阶段。

执行顺序（锁定，Phase 3 之前不再讨论 R3/R4 具体方案、不爬官方文档）：

```text
Phase 0（前置确认，先于一切 DAPT）
├── A. 语言分布统计（paper train/val/test × benchmark dev/final/refusal 的
│      Chinese/English/Mixed 矩阵）
└── B. task_type oracle vs Unknown 消融（49 val，同 R1 checkpoint，
       指标见 §2；不修改 R1 正式结果）
Phase 1：domain_corpus_v1 构建
├── source SHA exclusion → 6-gram exclusion → L3 structure exclusion
└── dedup → token census → manifest/hash ledger → 断言电池
Phase 2：M1-R2
└── decoder CLM-DAPT → SFT（R1 同协议）→ dev-20 → final-100
Phase 3：视 R2 结果决定
├── R3：BERT domain MLM（encoder 侧）
├── R4：DAPT + TAPT
└── 或停止 M1 增强线
```

冻结流程（Phase 1 构建）：

1. 实施前置确认 A（语言分布）并记录；
2. 构建脚本（`scripts/build_domain_corpus_v1.py`，建议名）产出：语料 JSONL（按池+语言分文件）、manifest（含 §5 的 D5 四项字段）、hash ledger、构建统计（token 数、去重簇、剔除清单及原因）；
3. 断言电池：6-gram=0（对 §6.2 全部对象）、源码层排除组 0 命中、结构层 `L3_` 形态 0 命中（白名单的 D1 taxonomy 描述文本单独处理：L3 类**名称/描述**属于领域知识允许保留，但不得以 `task → L3 序列` 对形态出现）、D5 ≤1 epoch 配置校验；
4. 物化位置：`docs/reports/domain_corpus_v1/`（manifest/summary/ledger 入库，大型语料文件服务器侧 + hash 镜像，对齐既有 LFS/镜像纪律）；
5. owner 批准后冻结版本；任何修订升 v2，不覆盖。

## 12. 禁止事项

- 不得把 `task → L3` 监督对伪装成 DAPT/TAPT 数据，或把 SFT 任务文本无限重复训练（D5 限 1 epoch）。
- 不得触碰 paper_v1 val/test、benchmark 任何 release、sealed gold 及其派生物；开 gold 评分仍受 R4 规则（先锁 prediction hash）约束。
- 不得为凑 token 量爬取新数据或放宽 §6 泄漏隔离；不得用 domain corpus 结果反推修改监督数据。
- 不得修改 M1-R1 冻结结果或在 M1-R2 评测中更换推理协议。
- `/home/yll` 只读；服务器写入限定 `/home/qy`；不删除任何服务器数据。
