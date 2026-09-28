# QGIS 工作流构建的三条模型路线

状态：2026-07-21 至 2026-08-20 月度研究总计划，后续按门禁持续修订  
日期：2026-07-21  
最近修订：2026-07-31（重构 M2/M3 边界，并补充单卡 A10 模型选型）

当前实验状态：M2/M3 尚未开始训练或可行性实验；现阶段最高优先级仍是构造可训练、可追溯、source-disjoint 的高质量数据。本文中的 M2 领域继续预训练与系统化后训练、M3 任务级微调、DAPT/TAPT、preference/tool-feedback 后训练和 direct-QGIS 均为待验证方案，不代表实验结论或最终论文方法。

## 1. 唯一研究主线

本项目的核心问题保持不变：

> 根据自然语言任务，自动构建可靠、完整、顺序正确且可解释的 QGIS 工作流算子链。

模型架构、GEE 数据、L3 taxonomy、知识图谱、FiLM、QGIS landing、领域后训练、微调和评估体系都服务于这一主问题，不能分别演变成互不关联的研究目标。

当前计划采用三条模型路线并行比较：

- M1：继续训练自主工作流规划模型。
- M2：从开源 Base 模型开始的 QGIS 领域继续预训练与系统化后训练模型。
- M3：在官方已后训练模型上的普通任务级微调基线。

三条路线共享监督数据 authority、数据划分、L3 目标和最终 QGIS 评估体系。M2 额外使用的无监督领域语料是路线处理变量，必须单独冻结、审计并做消融，不能接触 validation/test 或其派生信息。

## 2. 为什么保留 L3 中间表示

项目中的主要栅格工作流监督来自 GEE，而最终目标平台是 QGIS。如果直接把所有模型改为预测 QGIS operator ID，将难以继续利用已有的大规模 GEE 栅格工作流数据。

因此，L3 不只是分类标签，而是连接不同 GIS 平台的语义中间表示，作用类似编译器中的 intermediate representation（IR）：

```text
GEE 栅格工作流
        ↓
跨平台 L3 语义工作流
        ↑
QGIS 栅格/矢量工作流
        ↓
受约束的 L3 → QGIS landing
        ↓
最终 QGIS operator chain
```

L3 的主要价值包括：

- 复用已有 GEE 栅格工作流知识。
- 统一 GEE、QGIS 及其他平台对同一 GIS 操作的不同 API 表达。
- 将自然语言语义规划和平台算子落地分离。
- 区分模型规划错误、taxonomy 表达缺口和 QGIS landing 错误。
- 为知识图谱、operator compatibility 和跨平台迁移提供统一语义节点。

当前需要验证的不是“是否删除 L3”，而是：

> 现有 94/107 L3 taxonomy 是否能作为足够保真的跨平台 GIS 工作流中间表示。

需要单独测量：

- QGIS operator 的 L3 可表达率。
- QGIS workflow 的完整 L3 映射率。
- QGIS → L3 → QGIS round-trip 可恢复率。
- 每个 L3 对应 QGIS operator 的平均歧义度。
- taxonomy 无法表达或只能部分表达的 QGIS 操作比例。

如果表达能力不足，优先研究 `L3 + modality + data type + parameter/role attributes`，而不是未经验证地无限扩展 taxonomy 或直接废弃 L3。

### 2.1 当前暂定的统一输出边界

在尚未获得 M2/M3 实验结果前，三条模型路线暂定统一输出 L3：

```text
M1 → L3 ┐
M2 → L3 ├→ capability-aware QGIS landing → QGIS operator chain
M3 → L3 ┘
```

这样做是为了：

- 保持 M1/M2/M3 的训练目标和评估接口一致。
- 继续利用以 GEE 为主的栅格 L3 监督。
- 把自然语言规划错误与 L3→QGIS 落地错误分开分析。
- 在 QGIS catalog/provider 变化时避免重新训练整个语义规划模型。

当前 M1 的模型 beam search 实际在 L3 vocabulary 中产生候选；之后 `QGISCandidateGenerator` 再根据 L3→QGIS 映射生成并排序 QGIS 候选链。后者虽然也使用 beam 扩展，但不能把映射正确性归功于 beam search。

如果 M2 后续在 L3 规划、完整性和稳定性上表现较好，再单独比较：

- L3→QGIS landing；
- L3 主头 + QGIS operator 辅助头；
- direct-QGIS 离散算子生成。

direct-QGIS 目前只是后续候选实验，不是已经决定的 M2/M3 输出形式。

### 2.2 Landing 应被视为受能力约束的编译过程

L3→QGIS 不能继续被简化为“一个 L3 查一个 QGIS 名称”。更合理的边界是：

```text
L3 semantic workflow
    ↓
QGIS capability profile
    ↓
direct/macro/API implementation lookup
    ↓
provider、版本、I/O、参数和语义保真过滤
    ↓
dependency closure 与候选排序
    ↓
QGIS operator chain 或明确拒绝
```

其中 QGIS capability profile 至少包含：

- QGIS 版本；
- 已安装 provider；
- 当前 authoritative operator catalog；
- 每个 operator 的输入输出类型；
- L3→QGIS 审核映射；
- 审核过的多算子 macro；
- 后续人工确认的 API pattern；
- 禁用、未知和不兼容能力。

Beam search 只能在以上权威候选空间内搜索，不能把语义相似度猜测出的名称直接升级为正式算子。

### 2.3 一个 L3 对应多个 QGIS 算子的处理

必须先判断是哪一种歧义：

1. **实现级一对多**：多个 provider/operator 实现同一宏观语义。L3 保持不变，由 landing 根据 provider 可用性、数据类型、参数语义、I/O 兼容、保真度和稳定性选择。
2. **语义级碰撞**：多个 QGIS operator 实际完成不同任务，却被压缩到同一 L3。此时不能只靠排序解决，应增加 `modality/data type/method/role/parameter` 属性，必要时再拆分 L3。

每个候选实现应记录：

```json
{
  "l3_code": "L3_xxx",
  "qgis_operator": "provider:algorithm",
  "provider": "native|gdal|grass|saga|otb|...",
  "input_types": [],
  "output_types": [],
  "preconditions": [],
  "semantic_fidelity": "exact|high|partial|none",
  "review_status": "reviewed|unreviewed"
}
```

存在多个同等可用实现时，评估集需要记录 accepted alternatives；不能把非唯一实现误判为错误，也不能把所有同 L3 算子都自动视为等价。

### 2.4 GEE L3 在 QGIS 中没有直接对应算子的处理

每个 L3 的 QGIS 支持状态暂定分为：

| support type | 含义 | 严格模式处理 |
|---|---|---|
| `direct` | 有单个审核过的 QGIS Processing 等价算子 | 直接候选 |
| `composite` | 无单算子，但有审核过的多算子实现 | 展开为 macro |
| `api_pattern` | 需要 QGIS Python/C++ API 或自定义算法 | 当前延后，规则审核后再准入 |
| `approximate` | 只能部分保真实现 | 明示语义损失，不冒充 exact |
| `unsupported` | 当前 QGIS/provider 环境确认无法实现 | 拒绝或建议其他平台 |
| `unresolved` | 尚未完成证据审核 | fail closed，不进入金标 |

GEE 样本可以监督 `natural language → L3 semantics`，但不能自动证明该 L3 在 QGIS 可落地。训练和评估记录必须区分：

- `source_platform`；
- `target_platform`；
- `qgis_support_type`；
- `required_provider/version`；
- `landing_fidelity`；
- `review_status`。

当目标平台明确为 QGIS 时，模型、Planner 或 landing 应消费 capability mask：只有 `direct`、`composite` 以及未来通过规则审核的 `api_pattern` 才能作为严格可实现候选。`unsupported` 和 `unresolved` 不允许由模型猜测替代算子。

### 2.5 Strict catalog mode 与探索模式

现有候选生成代码还允许 discovered semantic mappings 和 typed unknown 占位符。这些机制可用于发现映射覆盖缺口，但不能作为严格训练和正式评估的正确性来源。

- **exploration mode**：允许 discovered/unknown，用于分析 taxonomy 和 catalog 缺口。
- **strict catalog mode**：只允许 authoritative catalog、人工审核映射和审核 macro；无合法实现时明确拒绝。

正式 QGIS workflow 可用性评估必须采用 strict catalog mode，并分别保存：

- 模型原始 L3 输出；
- landing 输入；
- 被过滤的候选及原因；
- 最终 QGIS chain；
- `unsupported/unresolved/partial` 状态。

### 2.6 当前数据优先级

上述 landing 设计目前只是问题定义，不应抢占训练数据主线。当前实际顺序保持为：

1. 构造高证据自然语言—L3—QGIS workflow 训练记录。
2. 优先完成显式 Processing 链的算子、顺序、artifact dependency 和完整性审核。
3. 数据 schema 现在预留 `qgis_support_type`、provider、fidelity 和 review 字段；不要求在第一批训练数据前完成全部 94/107 L3 的能力矩阵。
4. 第一批数据稳定后，再对训练集中实际出现的 L3 做增量 capability audit。
5. 在数据 authority 和小规模 held-out 冻结前，不启动 M2/M3 正式训练，也不实施 direct-QGIS。

## 3. 路线 M1：继续训练自主规划模型

### 3.1 当前架构

M1 延续当前 V4.6/V5 自主模型路线：

```text
自然语言任务
    ↓
bert-base-uncased 文本编码器
    ↓
token memory + pooled task representation
    ↓
task type embedding + condition fusion
    ↓
输入层 FiLM + 每层 Decoder FiLM
    ↓
自主 Transformer autoregressive decoder
    ↓
L3 chain
    ↓
共享 QGIS landing
```

当前 V4.6 并非完全从零训练：

- 文本编码器加载预训练 `bert-base-uncased`。
- 默认冻结 BERT 大部分参数，只解冻顶部两层和 pooler。
- BERT hidden size 768，经 projection 映射到 `d_model=256`。
- Decoder 为 6 层、8 heads、FFN 1024 的自定义 Transformer Decoder。
- L3 token embedding 与输出 projection 共享权重。
- task type embedding 与文本 pooled representation 融合为条件向量。
- FiLM 同时注入 token embedding 输入和每一层 Decoder。
- 辅助头包括长度回归、task classification/contrastive representation 和长度 bucket。
- 当前 KG 主要通过 L3/operator embedding、mapping、I/O 校验、检索和解释参与；尚未证明完整 KG 已端到端注入当前 V4.6 生成过程。

### 3.2 当前训练流程：两个不同层面的“两阶段”

项目中存在两种容易混淆的“两阶段”，后续文档、日志和论文必须明确指明是哪一种。

#### 3.2.1 SFT 内部两阶段：Teacher Forcing → AR Scheduled Sampling

从头训练的权威入口是 `scripts/train_v4_6_quality_gate.py`：

```text
阶段 S1：前 10 epoch Teacher Forcing
阶段 S2：后 40 epoch AR Scheduled Sampling
总计：50 epoch
```

Teacher Forcing 阶段使用真实前缀预测下一个 L3 token，训练稳定、速度快，但存在 exposure bias：训练时总能看到正确历史，真实推理时却必须消费自己的预测。

AR Scheduled Sampling 阶段按逐步下降的 teacher-forcing ratio，在真实 token 和模型采样 token 之间切换，使训练更接近推理。当前实现使用 nucleus sampling，并通过可配置 `ar_max_steps` 限制展开长度。

Warm-start 路线默认：

```text
加载已有 checkpoint
    ↓
TF phase = 0
    ↓
直接进入最多 30 epoch AR-SS 增量训练
```

必须长期保留的边界：如果 from-scratch 只运行 5 个 epoch，而固定 TF phase 是 10，则整个实验只有 Teacher Forcing，不能称为完成了 V4.6 两阶段训练。当前训练入口已默认阻止这种误用，除非显式声明 smoke。

#### 3.2.2 完整生命周期两阶段：SFT → DPO Preference Post-training

另一个层面的两阶段是：

```text
阶段 P1：TF + AR-SS 监督训练，学习基础 L3 生成
阶段 P2：DPO-style preference post-training，提升可用候选的相对概率
```

`scripts/train_v4_6_preference.py` 从已有 SFT checkpoint 初始化 policy，并冻结一份 reference model。对同一任务的 preferred/non-preferred L3 序列计算 policy 与 reference 的序列平均 log-prob 差，使用 DPO loss 提升 preferred chain 的相对概率，同时可用 CE anchor 防止策略模型偏离基础生成分布。

DPO 阶段不能替代基础 SFT：如果基础模型的 beam 候选没有覆盖正确链，preference training 只能重排已有候选概率，不能创造不存在的语义能力。现有 GRPO headroom 诊断也显示当前 beam 多样性不足，因此暂不把更复杂 RL 作为下一步。

### 3.3 当前训练损失和采样机制

当前 SFT/AR-SS 训练信号包括：

- per-sample weighted token cross-entropy/log loss。
- label smoothing。
- 长度回归损失。
- task type classification 辅助损失。
- length bucket regression/classification。
- early-END penalty。
- task type、vector family、source quality、confidence 和 sample weight 组合采样。
- curriculum learning：先短链，再逐步引入长链。
- validation generation composite：`0.5*SetF1 + 0.3*LCS + 0.2*(1-earlyEOS)`。

当前 AR 主损失已允许梯度回传到解冻的 BERT 顶层；历史版本曾错误 detach memory/condition，使 AR 阶段不能真正更新文本编码器。length/task auxiliary loss 历史上也曾位于 `no_grad`，现已修复。

### 3.4 已有结果应该如何解释

- DPO v2 在 3000 条 GEE test 上使 execution-aware beam top-1 usable 从 59.9% 提升到 99.1%。该结果包含 beam candidate 与规则门控，不能等同于纯模型严格语义准确率。
- QGIS vector SFT seed absorption 明显：685 条 QGIS seed 注入后，seed 上 strict-vector rate 从 1.7% 升到 53.7%；这证明模型吸收了训练信号，不是 held-out 泛化证明。
- oversampled vector warm-start 的 test AR SetF1/LCS/earlyEOS 为 0.540/0.397/11.3%。
- held-out vector prompts 上 measurable family recall 和 vector-token rate 上升，但 intersection/union/difference 等细粒度 overlay recall 仍为 0。
- 当前证据说明模型能学会“进入矢量模式”和常见矢量骨架，但仍不能可靠区分关键细粒度 QGIS 操作。

### 3.5 当前已确认问题

#### 数据与监督问题

- GEE/栅格样本长期占主导，矢量和 QGIS-native L3 token 稀缺。
- 94/107 L3 中存在大量低频或未激活 token；历史 vocab107 训练中新增 13 个 L3 码曾出现 0/13 被模型使用。
- `vector_v2`、API-trace 和部分 LLM 生成数据存在弱 prompt、低置信标签、同 prompt 多标签冲突及 val/test 污染。
- 旧训练包存在跨阶段重复、来源混用和长度统计错配风险。
- 任务描述、源码证据和 L3 chain 的忠实对齐尚未完全解决。

#### 训练协议问题

- 短 from-scratch 运行可能全程 TF，无法验证真实 AR 生成。
- AR-SS 计算昂贵，长链超过 `ar_max_steps` 后半段缺少 AR 训练信号；把 horizon 从 20 提高到 32 可将 oversampled 包中超出范围的训练链从 3,219 降到 545。
- 历史 AR-SS 将 dynamic minimum-length END mask 直接作用于 CE logits，当 gold target 是 END 时产生 `loss=inf`。代码已拆分 loss logits 和 sampling logits，但相同条件的完整训练仍需重跑验证。
- 旧 checkpoint 可能使用 legacy 128-token prompt，新模型使用 structured 256-token prompt；混用会引入输入分布漂移。
- 47-task checkpoint warm-start 到 48-task QGIS vector 包存在 task embedding/classifier shape mismatch，必须显式扩展或跳过专属权重。
- 非默认数据包若误用旧 `length_stats`，会把错误长度先验带入训练和推理。

#### 模型与任务问题

- BERT 是英文 encoder，对中文或中英文混合 GIS 任务的覆盖有限。
- 自定义 Decoder 大部分从随机初始化开始，需要大量高质量序列监督。
- 自回归生成同时承担算子集合、顺序、长度、终止和依赖，错误耦合严重。
- 当前模型主要学习线性 L3 序列，未直接学习 artifact dependency DAG。
- FiLM 和 KG 的独立增益尚缺少严格、同数据、同评估的消融证明。

#### 评估问题

- raw exact match 对存在合法等价顺序的 workflow 过于严格，但只看 SetF1 又会忽略顺序和完整性。
- train-source seed absorption、retrieval landing、规则修复和纯模型生成曾被混合解释。
- 当前需要一套固定的 L3 planning、landing 和最终 QGIS usability 三层评估，避免再移动指标。

### 3.6 M1 后续执行计划

1. 冻结一份真正 source-disjoint 的训练/validation/test authority。
2. 固定一个 M1 baseline checkpoint，并登记数据、taxonomy、task vocab、prompt style、length stats、解码和 landing 版本。
3. 先复跑已修复 `loss=inf` 的受控小规模训练，确认 AR loss、梯度和 checkpoint selection 稳定。
4. 只允许一个正式 M1 主实验配置，避免同时维护多个 vector_v2/unified/oversampled 入口。
5. 使用同一 canonical training records 运行 M1，保留 GEE 栅格能力，同时评估 QGIS vector family recall。
6. 做最小消融：task type、FiLM、KG/operator embedding、family sampler、AR-SS。
7. 如果 M1 在冻结评估集上仍明显低于 retrieval/通用 LLM，停止继续堆叠训练技巧，把资源转向 M2/M3。

### 3.7 研究意义和当前边界

- M1 保留现有模型、训练结果、FiLM、KG和任务类型条件等积累。
- M1 是自主架构基线，用来判断改进来自数据、语言基座还是训练策略。
- 数据 authority 和评估集冻结前不启动新一轮正式训练。
- 不因新增 M2/M3 删除或重写 M1。
- 历史 checkpoint 的数据暴露和旧评估结果必须与新受控实验分开报告。

## 4. 路线 M2：开源 Base 模型的 QGIS 领域继续预训练与系统化后训练

### 4.1 定义与术语边界

M2 不从随机权重开始做通用基础预训练，而是从开源的 **pre-trained-only Base checkpoint** 出发，依次完成 QGIS/GIS 领域知识注入、领域指令监督、工作流过程监督以及偏好/工具反馈对齐，形成面向“自然语言 → QGIS 工作流”的项目领域模型。

这里必须区分四个不同维度：

| 维度 | 本文含义 |
|---|---|
| 基础预训练 | 从随机权重和海量通用语料训练基础模型；M2 不承担这一阶段 |
| 领域继续预训练（DAPT/TAPT） | 在无监督 GIS/QGIS 语料上继续 causal language modeling，注入领域知识 |
| 系统化后训练 | 领域 SFT、过程监督、偏好优化、工具/校验反馈和安全拒绝等连续阶段 |
| 参数更新方式 | Full fine-tuning、LoRA 或 QLoRA；它与“处于哪个训练阶段”不是同一概念 |

因此，M2 的研究贡献不是“使用了 LoRA”，也不是给现成聊天模型再做一次问答微调，而是从 Base checkpoint 开始建立可复现的领域继续预训练与后训练生命周期。最终成果可以称为“基于 Qwen3.5 Base 训练的 QGIS 领域模型”，但仍属于 Qwen 基座的派生模型，不能表述为从零自主预训练的基础模型。

### 4.2 与 M3 普通微调路线的区别

M2 与 M3 的差别包括起始 checkpoint 和训练生命周期：

| 路线 | 起点 | 训练生命周期 | 研究作用 |
|---|---|---|---|
| M2 领域模型 | 官方 pre-trained-only Base | 领域继续预训练 → 领域 SFT → 过程监督 → 偏好/工具反馈 | 检验项目自己的领域知识注入和后训练方法能否形成专用模型 |
| M3 普通微调 | 官方已后训练的 Instruct/Post-trained 模型 | 直接做 `task_text → L3 chain` 的任务级 QLoRA/SFT | 检验在成熟聊天模型上做一次普通微调能达到什么水平 |

这两条路线是现实工程方案比较，不是只改变一个变量的严格因果实验。为解释收益来源，M2 必须增加一个 `Base → 直接任务 SFT` 的受控消融，并逐阶段保存 checkpoint；否则不能判断改善来自领域继续预训练、过程监督、额外算力，还是起始 checkpoint 不同。

### 4.3 单卡 A10 23 GB 的模型选型调研

截至 2026-07-31，Qwen3.5 官方提供 `0.8B / 2B / 4B / 9B / 27B` 稠密模型以及更大的 MoE 模型，并提供 Base 与官方已后训练版本。官方 Base model card 明确将 fine-tuning 和 LoRA-style PEFT 列为预期用途；模型采用 Apache-2.0。Qwen 官方列出的后训练工具包括 Unsloth、MS-SWIFT 和 LLaMA-Factory，MS-SWIFT 与 LLaMA-Factory 当前列表均已包含 Qwen3.5。

候选分层如下：

| 候选 | M2 起点 | M3 起点 | A10 定位 | 决策 |
|---|---|---|---|---|
| Qwen3.5-9B | `Qwen/Qwen3.5-9B-Base` | `Qwen/Qwen3.5-9B` | 4-bit QLoRA，冻结视觉编码器，text-only | **正式主候选，准确度优先** |
| Qwen3.5-4B | `Qwen/Qwen3.5-4B-Base` | `Qwen/Qwen3.5-4B` | QLoRA 或 BF16 LoRA，训练余量更大 | 工程 pilot 与 9B 失败时的正式降级 |
| Qwen3.5-2B | `Qwen/Qwen3.5-2B-Base` | `Qwen/Qwen3.5-2B` | 快速 smoke、数据和 loss 验证 | 不作为准确度优先的最终模型 |
| Qwen3.5-27B/35B-A3B 及以上 | 对应 Base | 对应已后训练模型 | 总权重、激活和优化器状态超过单卡预算 | 排除本机训练；active parameters 小不等于总权重能装入显存 |
| Qwen3.6-27B/35B-A3B | 当前官方对应模型 | 当前官方对应模型 | 版本更新但没有 A10 可训练的 9B 档 | 排除本机训练，不因版本号更新忽略总权重 |
| Qwen3-8B | `Qwen/Qwen3-8B-Base` | `Qwen/Qwen3-8B` | 成熟的纯文本同规模备选 | 仅在 Qwen3.5 hybrid/multimodal 工具链失败时启用，M2/M3 必须整组切换 |

Qwen3.5 官方通用 benchmark 中，9B 相比 4B 在与本任务相关的能力维度上整体更强，例如 `MMLU-Pro 82.5 vs 79.1`、`C-Eval 88.2 vs 85.1`、`IFEval 91.5 vs 89.8`、`IFBench 64.5 vs 59.2`、`LongBench v2 55.2 vs 50.0`。这些结果只支持把 9B 作为优先候选，不能替代本项目的 QGIS workflow pilot，也不能直接写成算子链准确度证据。

选型资料：

- [Qwen3.5-9B-Base model card](https://huggingface.co/Qwen/Qwen3.5-9B-Base)
- [Qwen3.5-9B post-trained model card 与官方 benchmark](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwen3.5-4B-Base model card](https://huggingface.co/Qwen/Qwen3.5-4B-Base)
- [Qwen3-8B-Base model card](https://huggingface.co/Qwen/Qwen3-8B-Base)
- [Qwen 官方模型与微调工具说明](https://github.com/QwenLM/Qwen3.6)
- [MS-SWIFT 支持模型清单](https://github.com/modelscope/ms-swift/blob/main/docs/source_en/Instruction/Supported-models-and-datasets.md)
- [LLaMA-Factory 支持模型清单](https://github.com/hiyouga/LLaMA-Factory)

9B 的 Ollama 量化推理模型已能在本机 A10 上运行，但推理显存不能推导训练显存。正式训练必须使用 Hugging Face/ModelScope 的 `safetensors` checkpoint，不能直接训练 Ollama GGUF。Qwen3.5 原生上下文虽为 262,144 tokens，本任务不得照搬该长度；pilot 从 1,024 tokens 开始，按训练样本 token 长度的 P95 和长链召回决定是否提高到 2,048。超长上下文既无当前任务证据，也会显著挤压训练显存。

### 4.4 基座与工具链门禁

正式锁定 9B 前必须在 A10 上完成真实训练 smoke，而不是只看理论显存：

- M2/M3 使用同一 Qwen3.5 预训练家族、相同参数规模、tokenizer revision 和文本输入边界；M2 用 Base，M3 用其对应官方 post-trained checkpoint。
- 冻结视觉编码器，不输入图像；若训练框架仍常驻视觉部分，必须记录其显存成本。
- 默认 4-bit NF4 QLoRA、BF16 compute、double quantization、gradient checkpointing、micro-batch 1 和梯度累积；LoRA rank 首轮比较 `32/64`。
- 审计 Qwen3.5 hybrid architecture 的实际 module names 后再冻结 target modules，禁止机械复制旧 Qwen/Llama 的 module 列表。
- 依次验证 forward/backward、保存/恢复 Adapter、合并 checkpoint、raw generation 和 100 条 overfit test；任何一步失败都不能进入正式训练。
- 记录 CUDA/PyTorch/Transformers、bitsandbytes、PEFT、TRL/训练框架版本。Qwen3.5 需要较新的工具链，不能默认沿用服务器旧环境。
- 若 9B 在 1,024 tokens、micro-batch 1 和 gradient checkpointing 下仍不稳定 OOM，降级到 4B；不得通过截断 gold workflow 换取“能训练”。

### 4.5 M2 训练阶段设计

#### 阶段 M2-0：Base、数据与接口冻结

- 主候选冻结为 `Qwen/Qwen3.5-9B-Base` 的明确 revision；4B 仅作 pilot/降级。
- 冻结无监督领域语料 manifest、监督 `paper_v1` manifest、prompt schema、L3 输出 schema、tokenizer、最大长度和评估集。
- 无监督领域语料不得包含 validation/test task、gold、accepted alternatives 或其改写；文档版本、许可证、来源和内容 hash 必须可追溯。
- 保存原始 Base 只读副本，每个阶段另存 Adapter/checkpoint，禁止覆盖基座。

#### 阶段 M2-1：领域继续预训练（DAPT/TAPT）

- 使用 QGIS 文档、Processing 算子说明、GIS 教材/规范、可合法使用的插件文档、工作流说明和高证据源码文本做 causal language modeling。
- 文档清洗必须保留算子名、参数语义、输入输出类型和版本信息，同时去除导航、重复模板、测试泄漏和无许可证来源。
- 混入预声明比例的通用/指令 replay 数据或采用保守学习率，监控灾难性遗忘；不能只报告领域训练 loss。
- 评估领域 held-out perplexity、GIS 术语/算子 probe 和通用能力保持率。该阶段尚不能直接宣称会生成正确 L3 chain。

#### 阶段 M2-2：领域指令监督后训练

- 从 M2-1 checkpoint 使用高质量 `task_text → canonical L3 workflow` 和必要的 GIS 指令数据做 SFT，参数更新仍采用 QLoRA。
- 输出严格限定为 `START/L3.../END` 或等价 canonical 结构；思考内容不得混入最终 L3 输出。
- 同时报告 token CE、operator SetF1、LCS、链长、early-END、非法 L3、family recall 和人工 workflow 可用率。
- 栅格、矢量、mixed、链长和 operator family 的采样权重必须显式记录。

#### 阶段 M2-3：过程监督与结构学习

只有标签证据可靠时才增加：operator presence、长度 bucket、pairwise precedence、artifact dependency、start/end 和 catalog/KG compatibility。训练期辅助 loss、约束解码和训练后 repair 是三种不同干预，必须分开实现和消融；不能把约束解码写成模型后训练收益。

#### 阶段 M2-4：偏好与工具反馈后训练

当模型已经具备候选覆盖后，使用规则、QGIS 执行/校验和盲审构造 preferred/rejected workflow。优先从拒绝采样 SFT 或单卡友好的 ORPO 开始；DPO 只有在 9B reference/Adapter 共享方案通过显存 smoke 后实施。偏好数据构造规则与最终评分规则必须解耦，并保留独立人工/QGIS 验证集，避免循环证明。

#### 阶段 M2-5：统一系统推理

对入选 checkpoint 统一比较 raw generation 与 grammar/catalog constrained generation、KG validation、dependency repair 和拒绝机制。该阶段属于系统层，不属于参数训练；相同后处理必须同时应用于 M3。

### 4.6 M2 可行性实验矩阵

| 编号 | 起点与训练 | 目的 |
|---|---|---|
| M2-C0 | 9B Base → 直接任务 QLoRA/SFT | 受控判断 DAPT 和后续阶段的增量收益 |
| M2-P0 | 9B Base，不训练 | 只做领域 continuation/probe；Base 不作为成熟聊天模型能力结论 |
| M2-P1 | P0 + 领域继续预训练 | 判断领域知识吸收与通用能力遗忘 |
| M2-P2 | P1 + 领域指令 SFT | 建立可生成 L3 workflow 的 M2 主 checkpoint |
| M2-P3 | P2 + 可靠的过程/结构监督 | 判断完整性、顺序和依赖是否改善 |
| M2-P4 | P3 + 偏好/拒绝采样/tool feedback | 判断人工可用率和可靠性是否改善 |
| M2-P5 | 入选 raw checkpoint + 统一约束/校验 | 只报告额外 system 收益 |

Go/No-Go：

- P1 若领域 held-out 不改善或通用能力明显遗忘，停止扩大 DAPT，并回退 Base 或调整 replay/学习率。
- P2 若不优于 C0，说明领域继续预训练尚无可信增益，不进入复杂 P3/P4。
- P3 只有在 order/dependency 标签达到预声明覆盖和一致性后实施。
- P4 只有在模型已有候选覆盖且独立偏好验证有效时实施；偏好训练不能修复基础语义失败。
- P5 与 M3 使用同一 system 规则，raw/system 分开报告。
- M2 若不能在人工 QGIS workflow 可用率、可靠性、可解释性或数据效率上优于 M3，则作为负结果或方法消融，不因训练阶段更多就自动成为主路线。

## 5. 路线 M3：官方已后训练模型的普通任务级微调

### 5.1 定义

M3 不重复建立后训练生命周期，而是直接使用官方已经完成通用后训练的 Qwen3.5 模型，通过任务级 SFT 学习 `task_text → L3 chain`。参数更新默认采用 4-bit QLoRA；这里的准确表述是“使用 SFT 目标，通过 QLoRA 进行参数高效微调”，而不是把 LoRA、PEFT 和 SFT 写成同级训练方法。

```text
自然语言任务
    ↓
官方已后训练的 Qwen3.5-9B
    ↓
任务级 QLoRA/SFT
    ↓
L3 chain
    ↓
共享 QGIS landing
```

M3 的主候选为 `Qwen/Qwen3.5-9B`，与 M2 的 `Qwen/Qwen3.5-9B-Base` 共享预训练家族、参数规模和 tokenizer lineage，但不是相同训练阶段的 checkpoint。M3 不使用 M2 的领域继续预训练语料、过程监督、偏好后训练、工具反馈或额外结构化规划模块。

### 5.2 研究作用

M3 的主要作用是回答：

> 在官方成熟后训练模型上只做一次任务微调，能达到什么水平；项目自建的领域继续预训练与系统化后训练是否值得其额外数据和算力成本。

M3 是准确度优先的强工程基线。它可能因为继承了 Qwen 官方大规模通用后训练而优于 M2，不能预设 M2 必胜。M2 与 M3 的主比较回答现实路线选择；`M2-C0` 与 M2 各阶段消融负责更严格地解释训练信号贡献。

### 5.3 公平性要求

- 与 M2 使用同一 Qwen3.5 预训练家族、相同参数规模、tokenizer lineage 和冻结 revision；M2 使用 Base，M3 使用对应官方 post-trained checkpoint，并明确这不是同起点比较。
- 任务 SFT 使用与 M2-SFT 相同的监督记录、split、输入字段和 L3 target；M2 独有的无监督领域语料必须单独报告。
- 使用相同 QGIS landing、catalog、accepted alternatives 和评估集。
- 单独报告总参数、可训练参数、显存、训练时间和推理成本。
- 主结果同时给出 `M2 vs M3` 的现实路线比较，以及 `M2-C0 vs M2-P2/P3/P4` 的阶段消融。
- 不得给任何路线提供 validation/test gold、源码片段或评分规则派生标签。

### 5.4 M3 暂定执行计划

#### 阶段 M3-0：官方后训练 checkpoint 与接口冻结

- 主候选冻结为 `Qwen/Qwen3.5-9B` 的明确 revision；`Qwen/Qwen3.5-4B` 只做工程 pilot 或 9B 降级。
- 记录许可证、上游 Base、模型 revision、tokenizer、chat template、thinking 开关、上下文长度和量化支持。
- M2/M3 使用相同自然语言输入字段、canonical L3 输出 schema 和同一 `paper_v1` split。
- 正式 raw 评估默认关闭 thinking content，避免 `<think>` 文本污染严格 L3 输出；若保留隐式推理能力，必须由 chat template 正确分离最终答案。

#### 阶段 M3-1：不训练 prompting 基线

- 在冻结 prompt 和解码参数下测试官方 Qwen3.5-9B 的原始 L3 能力。
- 报告 raw generation，不用 grammar 修复掩盖模型格式和语义错误。
- 该结果既是 M3 的起点，也是判断微调是否值得的必要基线。

#### 阶段 M3-2：任务级 QLoRA/SFT

- 单卡 A10 上 9B 固定使用 4-bit QLoRA，不把 BF16 LoRA 或全参数 SFT 作为本月默认方案。
- 输出限定为 L3 chain，不允许混入自然语言解释。
- 训练主损失为 autoregressive token negative log-likelihood/cross-entropy。
- 先在 4B 或 9B 小样本上完成 overfit/smoke，再运行 9B 主 pilot；smoke 模型结果不能替代 9B 正式结果。
- 记录 NF4/double quant、BF16 compute、LoRA rank/alpha/dropout、target modules、可训练参数、sequence length、峰值显存和训练时长。
- 第一轮单 seed；只有 raw 语义指标通过门禁的配置才进入最终多 seed。

#### 阶段 M3-3：统一约束生成对照

- 比较 raw generation、L3 grammar constrained generation 和 catalog mask。
- 输出解析失败、非法 L3、重复、提前结束必须单独统计。
- 任何规则修复后的结果与原始模型输出分开报告。
- 约束、repair 和拒绝机制必须与 M2-P5 使用同一实现和配置。

### 5.5 M3 停止条件

- 小规模 LoRA 不能稳定输出合法 L3 格式。
- held-out 指标未超过不训练的官方 Qwen3.5-9B prompting，且成本明显更高。
- 只有训练 loss 改善，workflow 指标没有改善。
- 需要读取测试集或增加额外弱标签才能取得优势。
- 在 A10 上无法在论文期限内完成可复现实验。

### 5.6 M3 本月默认实现合同与 Pilot 矩阵

M3 固定为普通任务微调基线，避免和 M2 的领域继续预训练及系统化后训练混在一起：

- 默认采用与 M2 Base 对应的官方 Qwen3.5-9B post-trained checkpoint，不另换模型家族或更大参数规模。
- 默认 4-bit QLoRA；QLoRA 只是参数更新和显存策略，不会把 M3 变成系统化后训练路线。
- 默认直接生成 canonical L3 序列，不增加独立 planner head、过程监督、偏好优化或工具反馈目标。
- 输入只包含统一自然语言字段；输出只包含 `START/L3.../END` 或等价的严格 L3 code string。
- target modules、rank、alpha、dropout、量化方式、sequence length 和 trainable parameter count 必须进入运行 manifest。

最小矩阵：

| 编号 | 训练 | 解码 | 目的 |
|---|---|---|---|
| M3-S0 | 4B 小样本 QLoRA | raw generation | 验证数据、loss、保存恢复和生成管线；非正式模型 |
| M3-P0 | 官方 Qwen3.5-9B，不微调 | raw generation | 判断官方后训练模型的原始 L3 能力 |
| M3-P1 | 9B 任务级 QLoRA/SFT | raw generation | 测量普通微调本身的语义和格式收益 |
| M3-P2 | 与 P1 相同 checkpoint | grammar/catalog constrained | 测量约束带来的额外系统收益 |
| M3-P3 | rank `32/64` 或长度 `1024/2048` 最小消融 | raw generation | 只在 P1 有效且预算允许时选择准确度配置 |

M3 进入最终多 seed 的最低条件：raw 合法 L3 输出率达到预声明门槛，SetF1 与 LCS 均超过 M3-P0，同一 source-disjoint validation 上没有明显 family collapse，并且提升不只来自 grammar 修复。否则 M3 保留为单 seed 对比，不扩大训练，也不转做全参数 SFT。

## 6. 共享监督 authority 与 M2 领域语料

### 6.1 数据 authority 与冻结版本

三条路线的任务监督阶段原则上使用同一批 canonical records。模型可以使用不同 tokenizer、chat template、序列化方式和张量表示，但不得使用不同的 gold authority，也不得为了某条路线单独挑选更容易的训练或测试样本。

M2 的领域继续预训练允许额外使用不带任务 gold 的 `domain_corpus_v1`，这是 M2 相对 M3 的明确处理变量，而不是“所有路线数据完全相同”的受控条件。必须同时维护两个独立 manifest：

- **`domain_corpus_v1`**：只供 M2-DAPT 使用的 QGIS/GIS 无监督领域文本，记录 URL/仓库、版本、许可证、内容 hash、清洗规则和去重簇。
- **`paper_v1`**：M1/M2-SFT/M3-SFT 共享的监督记录、source-disjoint split、L3/QGIS gold 和证据等级。

`domain_corpus_v1` 不得包含 validation/test 任务文本、gold workflow、accepted alternatives、人工评分或其直接改写。若领域文档与 held-out 源码/任务同源，必须按 source identity 一并排除或归入 train，避免 DAPT 形成隐性测试泄漏。

本月论文实验不应被 `/home/yll` 全量数据资产总账无限阻塞。数据工作拆成两个并行层次：

- **长期全量 authority**：继续梳理所有 QGIS/GEE/ArcGIS/派生数据簇，回答完整数据资产问题。
- **论文 `paper_v1` authority**：只从已经能够追溯源码、内容 hash、平台、L3 和 QGIS 映射状态的高证据记录中冻结一个可复现实验子集。

`paper_v1` 不宣称代表全部语料，也不用于推断“40 万脚本最终能产生多少训练行”。它只承担本月三路线公平比较。冻结后必须生成 manifest，至少包含：

```json
{
  "dataset_version": "paper_v1",
  "record_id": "stable-id",
  "source_hash": "sha256",
  "source_identity": "repository-or-authority/path",
  "task_text": "natural-language task",
  "task_text_authority": "human|source-grounded-llm|legacy",
  "source_platform": "GEE|QGIS|mixed",
  "source_operator_chain": [],
  "l3_chain": [],
  "qgis_operator_chain": [],
  "source_to_l3_alignment": [],
  "l3_to_qgis_alignment": [],
  "artifacts": [],
  "dependencies": [],
  "mapping_status": "full|partial|unresolved",
  "evidence_level": "gold|high|weak|unresolved",
  "split": "train|validation|test"
}
```

manifest 还必须记录：输入文件 hash、catalog 版本、taxonomy 版本、生成脚本/提交、去重规则、split seed、样本数、平台/模态/operator family 分布和排除原因统计。任何训练日志必须反向指向唯一 manifest，禁止只用目录名描述数据版本。

### 6.2 数据准入规则

- GEE 数据主要提供栅格工作流与跨平台 L3 监督；不能因为最终目标是 QGIS 就删除主要栅格监督。
- QGIS 数据提供矢量/栅格工作流、QGIS operator、依赖结构和高置信 L3 对齐。
- 首批新增 QGIS gold 优先来自显式 `processing.run()` 和 `processAlgorithm()` 内可证明的 Processing 子链。
- `partial` 只可用于 operator-presence、局部顺序等与其证据相符的辅助目标，不可用于完整序列 CE。
- `unresolved` 只进入诊断、规则库研究或无监督表示分析，不进入完整工作流监督。
- M2-DAPT 的原始文档必须具有可用许可证和可追溯来源；无监督不等于可以忽略版权、质量或测试泄漏。
- M2-DAPT 文本不得串入 `START/L3.../END` 测试 gold 或评分反馈，否则会把继续预训练伪装成泛化能力。
- LLM 生成但未经人工或源码门禁确认的任务描述，不进入 held-out；弱描述进入训练时必须单独标记并做去除消融。
- 动态 operator ID、跨 helper 顺序不明、artifact 断裂、catalog 未命中和低层 API 强行宏观映射的记录不得伪装成 gold。

### 6.3 去重与划分

划分必须先按 source identity、repository/fork lineage 和源码内容 hash 分组，再将整个组放入同一 split。只做逐行随机划分会造成 fork、镜像、同脚本改名和任务描述改写泄漏。

最低要求：

- train/validation/test 的 source group 不相交；
- test 不参与 prompt 模板、解码阈值、operator 约束或 accepted-alternative 规则调试；
- 同一源码生成的多个自然语言表述不得跨 split；
- 历史 M1 checkpoint 已暴露的数据必须在结果表中标注，不能冒充 clean controlled comparison。

论文应同时报告两类结果：

1. **Controlled-from-authority**：使用同一 `paper_v1` 监督 authority；M2 额外的 `domain_corpus_v1` 作为显式处理变量，并通过 `M2-C0` 和逐阶段消融解释。
2. **Best-available-system**：允许使用各路线已有最佳 checkpoint，用于说明当前系统上限。

两类结果必须分表或明确分栏，不能混成一个排名。

### 6.4 模态比例、采样与规模曲线

原始 GEE/QGIS 数量不等于有效训练采样比例。为避免栅格样本再次淹没 QGIS/vector 信号，三条路线的监督训练阶段共享相同的 family-aware sampler 配置，并同时报告：

- 原始记录分布；
- 每个 epoch 的实际采样分布；
- raster/vector/mixed、常见/稀有 family 和链长 bucket 的有效权重；
- oversampling 后的 unique-record coverage，避免把重复曝光当作新增数据。

本月至少做三个训练规模点的学习曲线，例如 `25% / 50% / 100% paper_v1 train`。若算力不足，可只对最终主路线做三点曲线，其他路线做 `100%` 对照。比例冻结后所有路线复用，不能根据测试结果为某条路线单独调比例。

### 6.5 模型特定预处理允许范围

允许差异：tokenizer、padding、Base/Post-trained checkpoint 对应的官方 chat template、L3 token 的离散编码方式和模型所需 tensor packing；M2 允许使用已冻结的 `domain_corpus_v1` 完成 DAPT。

禁止差异：在任务 SFT 阶段新增语义字段、使用不同 gold chain、不同监督 record IDs、不同测试描述、隐藏的 retrieval 证据或只有某条路线可见的 validation/test 信息。任何 model-specific field 和 M2 独有语料都必须在实验表中列出。

## 7. 共享评估体系 E1

评估不是第四条模型路线，而是三条路线和外部基线共同的裁判。必须在主要训练完成前冻结评分脚本、人工说明和论文主判定，避免看到结果后移动目标。

### 7.1 评估集构成

建议冻结一个 **200 条 source-disjoint QGIS held-out** 作为论文核心集；若一个月内双人审核能力不足，最低降级为 120 条，但必须保留分层和完整人工金标，不能用更多弱样本替代少量可靠样本。

分层至少覆盖：

- vector、raster、mixed；
- 1–2、3–5、6+ 步链；
- 高频和低频 operator family；
- 明确 Processing、ProcessingAlgorithm 显式子链；
- 需要拒绝或信息不足的负样本；
- 同一任务存在多个等价可用链的 accepted alternatives。

前期用于数据管线核查和方法调试的 50 条不再进入最终 test；它们应归入 development/audit set。最终 test 的任务文本、gold chain 和人工结论在评分前保持封存。

### 7.2 第一层：L3 规划能力

- L3 operator precision、recall、F1；
- L3 顺序准确率、normalized LCS 和 exact chain match；
- 缺失步骤、额外步骤和重复步骤；
- vector/raster/mixed 模态一致性；
- 链长误差、early-END 和 non-termination；
- 按 family、链长和数据来源分层结果。

这一层评价自然语言理解和语义工作流规划。集合指标不能替代顺序与完整性指标。

### 7.3 第二层：L3 → QGIS Landing

- L3 到 QGIS 的 catalog coverage；
- QGIS operator candidate ambiguity；
- provider/operator exact match；
- 输入输出类型兼容率；
- artifact dependency closure；
- QGIS → L3 → QGIS round-trip recoverability；
- taxonomy unsupported/unresolved rate；
- accepted alternative 覆盖率。

这一层评价 taxonomy、KG、mapping 和 landing。必须分别报告“模型给错 L3”和“正确 L3 无法可靠落地”，不能把 landing 错误全部归因于模型。

### 7.4 第三层：最终 QGIS Workflow

- 最终 QGIS operator precision、recall、F1；
- 算子顺序准确率和 exact/accepted chain match；
- **人工完整 workflow 可用率（论文主指标）**；
- unsupported/hallucinated operator rate；
- 缺失、额外、重复算子和依赖断裂率；
- 对信息不足任务的正确拒绝率；
- 源码、catalog 和映射证据可追溯率；
- 同一输入重复生成及跨随机种子的稳定性。

人工可用性建议采用三级评分：`usable`、`partially usable`、`unusable`。主结果只把 `usable` 计为成功；`partially usable` 单独报告，不得并入成功率。至少 20% test 由第二位审核者盲审，报告一致率或 Cohen's kappa；争议项在解盲前按预定规则仲裁。

### 7.5 Raw model 与完整系统必须分开

每条路线至少输出两组结果：

- **Raw**：模型直接产生的 L3/QGIS chain，仅做解析所必需的格式处理；
- **System**：允许使用预先声明的 catalog mask、dependency repair、KG validation、beam/reranking 或拒绝机制。

系统后处理必须对所有可适用路线使用同一规则，或明确标成路线组件并做消融。不能把规则修复后的 99% candidate usability 写成模型本身 99% accuracy。

### 7.6 统一基线与公平预算

至少比较：

- Retrieval workflow baseline；
- M1 自主规划模型；
- M2 Qwen3.5-9B-Base + 领域继续预训练 + 系统化后训练模型；
- M2-C0 同 Base 直接任务 QLoRA/SFT 的受控消融；
- M3 官方 Qwen3.5-9B + 普通任务级 QLoRA/SFT 基线；
- 强通用 LLM prompting baseline。

所有方法使用相同 held-out task、QGIS catalog authority、最大输出长度、accepted alternatives 和人工评分说明。通用 LLM 可获得任务说明和同一 catalog/schema，但不得额外看到 gold、源码或其他路线不可见的检索证据。

报告总参数、可训练参数、训练 token 数、训练 GPU-hours、峰值显存、单样本时延、吞吐和外部 API 成本。M2/M3 使用同一 Qwen3.5 预训练家族与 9B 规模，但 M2 从 Base 开始、M3 从官方 post-trained checkpoint 开始，因此主表必须明确标成“现实路线比较”，不能声称只隔离了训练方法。领域继续预训练及后续阶段的因果收益由 M2-C0 和逐阶段消融承担；另报告近似等 GPU-hours 的效率比较，避免把更多算力本身包装成方法优势。

### 7.7 统计与复现

- 最终 M1/M2/M3 至少对通过门禁的路线运行 3 个随机种子；pilot 可先单 seed。
- 对同一 test records 的方法差异使用 paired bootstrap 计算 95% confidence interval。
- 人工可用率、hallucination rate 和 dependency closure 报告样本数及置信区间，不能只给百分比。
- 通用 LLM 若具有采样随机性，至少重复 3 次并固定模型版本、日期、temperature 和 prompt。
- 所有结果保存逐样本预测、raw/system 输出、评分、运行配置、checkpoint hash 和环境信息。

### 7.8 论文主判定预声明

当前论文目标是路径 A/B，不把数据集论文作为结果不理想时的临时退路：

- **A：性能优势**。候选主路线的人工 workflow 可用率显著优于强通用 LLM，同时可靠性指标不恶化。
- **B：可靠性优势**。人工 workflow 可用率相对强通用 LLM 的 paired 差值下界不低于暂定 `-5` 个百分点，并且 hallucinated/unsupported operator、依赖断裂或证据不可追溯至少一项显著改善，同时具备成本或可部署性优势。
- **失败条件**。可用率明显低于通用 LLM，且可靠性、解释性和效率均无可信优势，则本月结果不足以支撑当前方法型期刊主张，不能用更换指标包装为成功。

`-5` 个百分点是暂定 non-inferiority margin，必须在 Day 7 根据 test 规模和领域容忍度正式冻结，之后不得根据结果修改。

## 8. 失败归因与错误分类

统一错误 taxonomy：

```text
任务描述不充分/本应拒绝
    ↓
自然语言或任务类型理解错误
    ↓
L3 算子选择错误
    ↓
L3 顺序、长度或完整性错误
    ↓
artifact dependency 未闭合
    ↓
taxonomy 表达缺口
    ↓
L3 → QGIS landing 歧义
    ↓
QGIS catalog/provider 错误
    ↓
规则修复引入的新错误
```

每条失败样本只设一个 primary cause，可附多个 secondary causes。论文至少给出：错误类别分布、各路线共同失败、某路线特有失败，以及 5–10 个可追溯案例。只有这种分解才能判断提升来自语言编码、planner、KG/FiLM、微调还是后处理。

## 9. 本月一个月倒排计划

当前时间窗按 **2026-07-21 至 2026-08-20** 管理。M2/M3 尚未开始实验，当前资源首先投入训练数据构造。三条路线只有在数据 authority、最小 held-out 和输出边界冻结后才进入 pilot；不会承诺三条路线都完成大规模调参，最终资源集中给通过门禁的 1–2 条路线。

### Week 1：07-21 至 07-27——冻结裁判和最小数据 authority

- 冻结 `paper_v1` record schema、去重/split 规则和数据 manifest。
- 完成 50 条显式 Processing audit set，验证链、顺序、依赖、完整性和 L3 landing。
- 起草并冻结 E1 人工审核表、错误 taxonomy、raw/system 边界和 A/B 判定。
- 固化 M1 baseline checkpoint、训练代码提交、prompt style、解码配置和可复现结果。
- 审计 Qwen3.5-2B/4B/9B 的许可证、Base/Post-trained 配对、结构化输出、训练工具链、显存和推理成本；冻结 9B 主候选与 4B 降级候选。
- 不做三路线大规模训练。

**Day 7 硬门禁（07-27）**：若数据 schema、M1 baseline、评估协议或 Qwen3.5 Base/Post-trained 候选仍未冻结，停止新增模型设想；将 test 降级到不少于 120 条，并以现有高证据 `paper_v1` 子集继续，不能继续等待全量数据总账。

### Week 2：07-28 至 08-03——A10 训练门禁与 M2 领域继续预训练可行性

- 对 M1 做一次同条件受控复跑，验证修复后的 AR loss、prompt、sampler 和生成指标；不同时加入新模块。
- 冻结 `domain_corpus_v1` 的来源、许可证、hash、去重与 held-out 排除规则。
- 依次完成 2B smoke、4B 工程 pilot 和 9B QLoRA forward/backward、保存恢复、合并及 100 条 overfit 门禁；2B/4B 只验证管线，不替代 9B 正式结果。
- 在 9B-Base 上运行 M2-P1 最小领域继续预训练，并与未训练 Base 比较领域 held-out loss/probe 及通用能力保持率。
- 同时准备 M2-C0 和 M3-P0/P1 的冻结配置，确保监督记录、schema 和评估接口一致。
- 完成 held-out test 人工金标与 accepted alternatives 的封存。

**Day 14 硬门禁（08-03）**：9B 若在 1,024 tokens、micro-batch 1、gradient checkpointing 下仍不能稳定训练，则正式降级 4B；M2-P1 若领域 held-out 不改善或出现明显灾难性遗忘，则回退 Base，不进入领域 SFT。M1 若仍出现数值异常，不再继续架构优化，回退最后稳定 checkpoint。

### Week 3：08-04 至 08-10——M2 领域 SFT/增强与 M3 普通微调对照

- 只有 M2-P1 通过领域吸收与遗忘门禁时，才运行 M2-P2 领域指令 SFT；并运行 M2-C0 Base 直接 SFT 作为受控消融。
- 在官方 Qwen3.5-9B 上运行 M3-P1 任务级 QLoRA/SFT；使用同一 `paper_v1` 监督记录和输出 schema。
- 只有 M2-P2 优于 M2-C0 时，才实现 M2-P3 的 operator-set、precedence、length/end 和可靠 dependency/process signals。
- 比较自由生成与 grammar/catalog-constrained decoding，但 raw/system 结果分开。
- 对候选主路线做第一次盲测，不查看逐题 gold 后调参。

**Day 21 硬门禁（08-10）**：根据冻结 validation 结果只保留最多两条路线进入最终多 seed。M3-P1 若只改善格式而不改善 workflow 语义则停止；M2-P2 若不优于 M2-C0，停止 P3/P4；M2-P3/P4 若缺少可靠过程/偏好数据或不优于上一阶段，则回退上一稳定 checkpoint。

### Week 4：08-11 至 08-20——最终实验、统计和论文材料

- 对入选的 1–2 条路线运行 3 seeds；其余路线保留单 seed 对照。
- 冻结后统一运行 retrieval、M1、M2、M3 和通用 LLM baseline。
- 完成人工可用性审核、20% 双审、paired bootstrap、效率统计和错误分析。
- 完成 FiLM、KG、约束、preference training 等与论文主张直接相关的最小消融。
- 生成论文方法图、数据流图、主结果表、可靠性/效率表、学习曲线、错误案例和限制章节。

**Day 26 硬门禁（08-15）**：停止新训练配置和新模型模块，只允许补失败运行、统计复核和必要消融。  
**Day 31 交付（08-20）**：形成可复现实验包、结果判断和论文初稿骨架。若未达到 A/B，不伪造强结论，明确记录负结果与下一轮最小改进。

## 10. 算力与实验预算

当前按单卡约 23 GB A10 条件规划，正式运行前重新核实可用 GPU、存储和排队情况。

- 训练前检查：启动前记录 `nvidia-smi`、其他进程和可用显存；9B pilot 峰值应保留约 1.5 GB 余量，不能以偶发不 OOM 作为稳定可训练证据。
- 模型分层：2B 只做 smoke，4B 做工程 pilot/降级，9B 才是准确度优先的正式候选；27B/MoE 不进入本机训练。
- 参数策略：9B 的 M2/M3 固定使用 text-only 4-bit NF4 QLoRA、BF16 compute、冻结视觉编码器、gradient checkpointing、micro-batch 1 和梯度累积；不直接加载 Ollama GGUF 训练。
- 长度策略：先按 1,024 tokens 做真实 AR generation pilot，只在 gold 长链覆盖需要且显存门禁通过时提高到 2,048；不得截断 gold 换取显存。
- Pilot：小数据、单 seed、短 epoch，但必须包含真实 AR generation validation、保存/恢复和逐样本预测；不能用 teacher-forcing smoke 代替。
- 正式训练：最多 1 次 M1 受控复跑、1 组 M2-P1 DAPT、1 组 M2-C0、通过门禁后 1 组 M2-P2 及最多 1 组 P3/P4、1 个 M3-P1 任务 QLoRA pilot。
- Final：只对通过 Day 21 门禁的最多两条路线做 3 seeds。
- 9B full-parameter training 不适合单张 A10，本月明确不做；若未来获得多卡高显存资源再独立立项，不能把单卡 CPU offload 的极慢运行当作可复现实验方案。
- DPO 只在 reference/Adapter 共享的显存 smoke 通过后运行；否则优先拒绝采样 SFT 或 ORPO。偏好训练不作为修复基础语义失败的手段。

每次运行必须保存：配置、代码版本标识（存在 Git 仓库时记录 commit）、dataset manifest/hash、seed、环境、参数量、峰值显存、训练时间、best/last checkpoint、逐 epoch 指标和逐样本 prediction。缺少这些信息的运行只能算诊断，不能进入论文主表。

## 11. 论文最小交付物

### 11.1 方法与数据图

1. 总体问题图：自然语言 → L3 IR → QGIS landing → QGIS workflow。
2. 三路线对照图：M1 自主 decoder、M2 Base→DAPT→SFT→偏好/反馈、M3 官方 post-trained→任务 QLoRA/SFT。
3. 数据 authority 与 source-disjoint split 流程图。
4. raw model、约束/repair 与最终 system 输出边界图。

### 11.2 核心表格

1. 数据集分布、证据等级和 split 统计。
2. Retrieval/M1/M2/M3/通用 LLM 的三层主结果。
3. 人工 workflow usability、hallucination、dependency closure 和 traceability。
4. 参数量、可训练参数、显存、训练时间、时延和 API 成本。
5. 过程监督、KG、约束、偏好后训练/DPO 的最小消融。
6. 25%/50%/100% 数据规模曲线。

### 11.3 分析材料

- 按 vector/raster/mixed、链长、operator family 的分层结果；
- 统一错误 taxonomy；
- 5–10 个成功/失败案例；
- L3 表达缺口与 round-trip 分析；
- M2 领域继续预训练/系统化后训练与 M3 普通任务微调的准确度、可靠性和成本收益；
- 数据不完整、测试规模、人工审核和未执行真实 QGIS 参数化运行等限制。

本论文不要求完成 LLM 直接调用 QGIS 并执行所有参数。论文必须证明的是：生成的算子链是否可靠、完整、顺序正确、可落地且比基线更少幻觉。

## 12. 风险登记与降级方案

| 风险 | 早期信号 | 本月处理 | 降级后仍可交付 |
|---|---|---|---|
| 全量数据总账未完成 | Day 7 仍无法给出全语料 authority | 冻结高证据 `paper_v1`，全量盘点不阻塞论文实验 | 明确限定语料范围的三路线研究 |
| QGIS gold 数量不足 | 50 条 audit 的完整率低于门槛 | 只用 explicit Processing；partial 仅做辅助目标 | 小规模但高证据的受控实验 |
| M1 数值/协议不稳定 | `loss=inf`、early-END 或复现失败 | 回退稳定 checkpoint，不继续叠加模块 | 稳定 M1 baseline + 问题分析 |
| Qwen3.5 工具链不稳定 | forward、PEFT target、保存恢复或生成接口失败 | 固定可复现版本组合；先降级 4B，仍失败则使用成熟的同规模 Qwen 文本模型并重跑全部配对路线 | 工具链可行性报告，不伪造 9B 结果 |
| 9B 在 A10 上训练 OOM | 1,024 tokens、batch 1、checkpointing 仍无稳定余量 | 确认冻结视觉部分和 QLoRA 配置后降级 4B；不截断 gold | 4B 完整配对实验 |
| M2-DAPT 泄漏或许可证不清 | 领域语料与 held-out 同源或来源不可追溯 | 排除对应簇并重建 manifest；无法澄清的语料不用 | 小规模高证据 DAPT |
| M2 灾难性遗忘或收益不清晰 | 领域 loss 降但通用 probe/M2-C0 或 workflow 指标恶化 | 调低学习率、缩短 DAPT、加入 replay；仍失败则回退 Base/C0 | 领域继续预训练的可信负结果 |
| M3 微调不稳定或过拟合 | train 快速提高、source-disjoint test 不升 | 降低 LoRA rank/epoch，早停；不做全参数 SFT | 单 seed 微调对照和过拟合分析 |
| 偏好训练循环证明 | 偏好构造和最终评分使用同一规则且仅规则指标上涨 | 使用独立人工/QGIS 验证，停止 P4 或只作消融 | P2/P3 主模型与偏好阶段负结果 |
| Landing 成为主瓶颈 | L3 正确但 QGIS usability 低 | 分层报告 L3 与 landing；修复 authority，不归咎模型 | L3 planning 结果 + landing 限制 |
| 只有训练吸收、没有泛化 | seed/train 提升，held-out family 为零 | 停止扩量，检查 split、family coverage 和任务描述 | 可信负结果，不声称泛化 |
| 算力或时间不足 | Day 21 尚有多条路线未收敛 | 最多两条路线做 3 seeds，其他单 seed | 主路线 + 必要对照，而非三条都浅尝 |
| 未达到论文 A/B | 可用率落后且可靠性无优势 | 不移动指标；转为内部技术报告并继续下一轮 | 完整实验事实与失败归因 |

## 13. 已确定事项与待讨论事项

### 13.1 已确定

- 唯一主线是自然语言到可靠 QGIS 工作流算子链。
- L3 作为跨平台语义 IR 保留，三条路线统一预测 L3 并经过同一 QGIS landing。
- M1 继续作为自主架构路线；其训练包含 TF→AR-SS 和可选 SFT→DPO 两个不同层面的“两阶段”。
- M2 从 `Qwen/Qwen3.5-9B-Base` 开始，执行领域继续预训练、领域 SFT、可选过程监督和偏好/工具反馈，形成项目 QGIS 领域模型。
- M3 从官方已后训练的 `Qwen/Qwen3.5-9B` 开始，只做任务级 QLoRA/SFT，不混入 M2-DAPT、过程监督和偏好训练。
- 9B 是准确度优先的正式候选，4B 是工程 pilot/降级候选，2B 只用于 smoke；单卡 A10 不做 9B 全参数训练。
- 三条路线的监督阶段共享 record IDs、split、gold、catalog、输出 schema 和 E1；M2 独有 `domain_corpus_v1` 并通过 M2-C0/逐阶段消融解释。
- M2/M3 主表是同预训练家族的现实路线比较，不宣称相同起始 checkpoint；M2-C0 承担受控因果比较。
- 主指标是人工 workflow 可用率；raw 与 system 分开报告。
- 三条路线均做 pilot，最终资源只投入通过门禁的 1–2 条路线。

### 13.2 正式训练前必须冻结（原 Day 7 门禁）

1. `paper_v1` 具体规模、GEE/QGIS有效采样比例和数据 manifest。
2. E1 最终采用 200 条还是降级到不少于 120 条。
3. `Qwen3.5-9B-Base`/`Qwen3.5-9B` 的精确 revision、许可证、tokenizer/chat template、训练版本组合和 A10 smoke 结果。
4. non-inferiority margin 是否正式采用 `-5` 个百分点。
5. accepted-alternative workflow 的审核规则。
6. QGIS landing 中允许的 catalog mask、dependency repair 和拒绝机制。

### 13.3 后续讨论但不阻塞 Week 1

1. `domain_corpus_v1` 的具体来源比例、replay 比例、DAPT token 预算和灾难性遗忘阈值。
2. M2 在 P2 通过门禁后采用哪些可靠过程监督，以及偏好阶段选择拒绝采样 SFT、ORPO 还是 DPO。
3. L3 是否需要最小属性扩展，以及 modality/data type/role/parameter 哪些属性进入本论文。
4. 是否增加 direct-QGIS 作为无 L3 的消融；它不升级为第四条主路线。
5. preference post-training 是否作为 M2 主线增强，还是只保留为 M1/M2 消融。

后续讨论形成的新决定应继续写回本文件，并同步更新 `task_plan.md`、`progress.md`、`docs/CURRENT_STATE*.md` 和 `docs/PROJECT_CONTEXT*.md`。本文件是三路线研究计划的中文权威入口；其他进度文档只保留摘要和链接，避免多处维护互相冲突的完整方案。
