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
- 起点量级：100M 参数级模型 DAPT/TAPT 经验值为 **50–200M token** 即可有可测增益；D3 全量源码可能已数百 M token，**第一版不追求大规模，不为此爬取新数据**。
- 若做规模敏感性，仅对主路线（M1-R2 或 M2-P1 之一）设 2–3 个规模点，其余单点，对齐三路线文档 §6.4 的规模曲线纪律。

## 9. Recipe 分离（一个 manifest，多个配方）

| 消费方 | 配方 | 备注 |
|---|---|---|
| M1-R2/R3/R4 | 以 D1/D4（文本）为主，D3 少量或不用；D2 仅含 KG 本地概念描述 | M1 任务是英文任务文本 → L3，代码语言分布价值有限；BERT 为英文；外部文档本轮不纳入（决策 ①） |
| M2-P1 | D1–D4 全量（含 D3 代码） | 与三路线文档 §M2-1 的领域语料定义一致 |
| M3 | 不消费 | M3 按定义不做 DAPT/TAPT |

每个实验的运行 manifest 必须记录所用 recipe、池构成、epoch、token 数；配方差异在实验表中显式列出（对齐 §6.5"允许差异"条款）。

## 10. M1-R2 实验合同（已冻结）

- **目标定义（owner 2026-09-14，Phase 0-B 后修订）**：R2 不是"修复 M1-R1 benchmark"，而是在 task conditioning 与推理协议完全不变的前提下，测试 decoder-only domain DAPT 能否提高 M1 对 GIS 领域语言/工作流语义的泛化——即使 F1 0.00→0.08 也有明确解释价值。R1→R2 唯一主动变量 = decoder DAPT；不得因 Phase 0-B 发现 Unknown 有害而在 R2 改用 Oracle task_type。
- **DAPT 对象固定为 decoder-only causal-LM DAPT**：BERT encoder 保持 M1-R1 冻结配置不变（大部分冻结、解冻顶部两层 + pooler 的原状）。R1→R2 唯一新增变量 = decoder 的领域预训练，归因最干净。
- **BERT 领域 MLM（encoder 侧适配）不属于 M1-R2**，作为后续 M1-R3 候选消融（Phase 3 视 R2 结果决定）。届时 R2→R3 唯一新增变量 = encoder 领域适配，才能分别回答 decoder 与 encoder 领域适配各自的贡献。
- 架构与 SFT 协议完全复用 M1-R1（V4.6、70:30 平台分层采样、paper_v1 train 8,817、20 epochs、同 checkpoint 选择标准）。
- 评测协议与 M1-R1 完全一致（含 `INFERENCE_CONFIG_FREEZE_v1.json` 的 task_type=Unknown 与解码配置），保证 R1↔R2 差异可单独归因于 decoder DAPT。
- 验收：主指标 = benchmark（先 dev-20 后 final-100）空图率下降与首 L3 token 多样性恢复（不再单一 Define Projection 开头）；次指标 = val Top1 相对 13.75% 的增量、49 行诊断 P/R 相对 0.153/0.198 的增量。
- 归因声明：M1-R2 vs M1-R1 同架构、同 encoder 冻结状态、同 SFT、同解码 → 差值 = decoder 领域 DAPT 的独立贡献。前置确认 B 的结果作为归因解读的注脚，不改变比较协议。

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
