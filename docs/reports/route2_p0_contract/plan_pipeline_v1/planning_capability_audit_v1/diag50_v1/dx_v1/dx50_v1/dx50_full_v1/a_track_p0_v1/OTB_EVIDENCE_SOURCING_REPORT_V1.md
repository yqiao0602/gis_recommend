# A 轨 P0 · OTB 证据源侦察报告 V1（2026-10-17）

> 对应裁定：DX_EXPERIMENT_DESIGN_RULING_OWNER_V1.md（A1=卡片补全，先做已放行 OTB 115 卡）。
> 本报告只登记已核实事实；补卡本身未开始（先等 owner 对第 3 节发现的裁定）。

## 1. 补卡前哈希冻结（已完成）

`A_TRACK_P0_HASH_FREEZE_V1.json`（生成器 `scripts/dx_a_track_freeze_v1.py`）：

- profile v0_4 SHA256 `95ae97bc3600429275eb78a077850755a972105083c65b167ce1247048b2079c`；
  补卡出 v0_5+ **新文件**，禁覆盖（裁定附录条款）。
- S1 守卫快照：顶层 description 键 **0/1291**、layer_c_intent 343/1291（补卡禁写顶层 description 键）。
- **49 个 dx50_full_v1 `runs/*/S1/retrieval.json` 全量 SHA256 = A1 固定 Top-10 锚**
  （A1 S2 pack 必须复用冻结 Top-10，不重跑 S1——A1 唯一变量=卡）。
- 卡完备度基线交叉校验 4/4 过（aggregate/provider/otb_all_bare/grass7_outputs）。
- DX-50 三 pack SHA 前缀 + 仪器块（模型/HF rev/解码/编码器）登记入册。

## 2. 本地与上游证据源盘点

- 本地三源对 OTB 参数层**零证据**：catalog（115 条仅 IO 类型）、profile v0_4（OTB 全裸），
  catalog 声明的原始上游 `operators-json/qgis_operators.json` 已被后续导出覆盖（现文件
  1,291 行数字 id、无 provider），OTB 115 清单的原始出处本地无记录。
- 上游官方仓库已钉：`Algorithm_classification/_external_evidence/otb_upstream_v1`
  （仓库外，不进 git）。GitHub mirror，shallow，多 tag。
- 提取器 `scripts/dx_a_track_otb_extract_v1.py`（C++ 宏解析：SetName/SetDescription/
  AddParameter/AddChoice/Mandatory*/SetDefault*）→ 证据层 JSON（非 profile patch）：
  `a_track_p0_v1/otb_evidence_812_v1.json`。
- **提取验证通过（T-009 失败族直击）**：TrainImagesClassifier、ComputeConfusionMatrix
  全参数结构抽出（io 类、required、default、choice 树、嵌套 ref.raster/ref.vector 组）。
  8.1.2 共解析 113 app、0 解析失败。

## 3. 重大发现：6/115 为"幽灵算子"（待 owner 裁定）

**上游 OTB 6.6.2 / 7.4.2 / 8.1.2 / 9.1.1 四版本均不存在以下 6 个 app**（逐 tag 实测，
非文档推断）：

| profile oid | 状态 |
|---|---|
| otb:aggregate | 四版本无（含 9.1.1） |
| otb:genericregionmerging | 四版本无 |
| otb:imagetimeseriesgapfilling | 四版本无 |
| otb:multitempfilteringfilter | 四版本无 |
| otb:multitempfilteringoutcore | 四版本无 |
| otb:objectsradiometricstatistics | 四版本无 |

版本构成矛盾：115 集合同时含 OTB 9.0 时代的条目与 ≤7 时代条目，**不可能来自任何单一
官方 release**。假设（未证实，不作为结论）：部分条目来自 remote module 构建（如
temporal-gapfilling 模块在四版本源树内均存在，构建后才产出 app；QGIS 官方 OTB 包捆绑
了选定 remote modules），或历史 dump 合并了多次不同版本的导出。

**按 A 轨验收标准的处置（默认执行，除非 owner 另裁）**：6 卡不补、不猜测，标
"当前证据无法确认——上游 6.6.2–9.1.1 均无此 app，版本出处待定"。
其余 **109/115 卡以 8.1.2 为钉定证据源**（commit `b3eb5603…`，覆盖 109/115=94.8%）。

**诊断意义（登记，不下结论）**：若 6 个 oid 确为无法安装的幽灵算子，则 S1/S2 曾把它们
作为候选曝光给模型——"候选可含不存在算子"这一知识底座缺陷需在解读 S2 行为时纳入
（与"卡贫瘠"并列的知识层问题）。

## 4. 下一步（等 owner 第 3 节裁定后批量执行）

① 批量提取 109 卡证据 → ② v0_5 构建器（新文件；参数/输出入 layer_b_params，功能描述入
layer_c_intent，禁顶层 description 键；每字段 provenance=源文件 path+sha256+tag）→
③ full_card() 渲染抽查（验收条款）→ ④ A1 pack（复用冻结 Top-10）→ ⑤ 四分指标对比。

---

## 5. Owner 裁定（2026-10-17 晚）：批准默认处置 + 状态精化

- **批准继续执行**：6 个算子暂不补卡、不猜测参数与功能；其余 109 卡以 OTB 8.1.2 为
  钉定证据源 → 新建 profile v0_5 → full_card() 渲染抽查 → 冻结候选集上的 A1 对照 →
  四项指标比较。
- **状态精化（术语与定性纪律）**：
  - 已证实 = 6 算子在已检查的 4 个上游官方版本均未找到；115 集合不能视为来自单一官方
    release。
  - **未证实 = 它们不存在于所有相关构建、或一定来自 remote module**——不将"幽灵算子"
    作为已定性事实；准确状态为 **`provenance_unverified`**（算子来源及其在目标运行
    环境中的可用性未核实）。
- **两条执行约束**：109 卡逐字段保留来源记录、无法确认的字段明确标未知；6 个待核算子
  保留原始记录与 ID、不补推测参数、不当作已确认可执行算子；**A1 仍复用冻结 Top-10，
  不因本发现静默改变候选集**。
- **登记要求**：6 个算子单独登记为 `provenance_unverified`（`PROVENANCE_UNVERIFIED_V1.json`），
  并立后续核验任务——检查目标 QGIS/OTB 安装环境的实际应用清单/应用目录/构建来源；
  取得证据后方可判定其为真实扩展算子还是误入 Capability Profile 的记录。
- 定性：这是潜在的知识底座完整性问题（若目标环境不可调用，卡再完整也不能让工作流可
  执行），纳入后续系统可靠性审计；当前阶段不因此暂停 A1。
- QGIS 文档核实（owner）：OTB 需单独安装配置、QGIS OTB 配置支持多个应用程序目录——
  不同安装环境的应用集合可能不同，但不能据此证明 6 算子来自 remote module（证据不足）。

---

## 6. 执行日志（2026-10-17 深夜）：v0_5 构建完成，四项校验全过

- **提取器 V2**（`scripts/dx_a_track_otb_extract_v2.py`，V1 冻结）：解决三类特殊 app——
  ①TrainImages/VectorClassifier 的参数分散在基类头文件（otbTrainImagesBase.hxx/
  otbTrainVectorBase.hxx/otbLearningApplicationBase.hxx + 每分类器一个 hxx 的
  AddChoice 树，classifier 共 10 选：libsvm/svm/boost/dt/knn/ann/bayes/rf/sharkrf/sharkkm）；
  ②BundleToPerfectSensor 为 CompositeApplication（参数=内嵌 Superimpose+Pansharpening
  按实例名前缀联合）；③ShareParameter 暴露（io.out/io.confmatout/io.imstat 从内嵌
  training=TrainVectorClassifier 解析回真实类型）。逐参数 `sources` 来源记录满足
  owner"逐字段保留来源记录"约束。修复 4 个解析缺陷：内部应用调用误收
  （GetInternalApplication("t")->SetParameter…）、`this->` 接收者误杀、`->` 箭头
  回溯漏 '-'、跨行回溯误吃上一行注释的 `...`。
- **未解析共享参数**：ram/elev/rand 为 OTB 框架运行时自动参数（源码无声明、QGIS 不
  暴露）→ 构建器排除不猜，入 manifest（5 个 app 受影响：bundletoperfectsensor 2/
  kmeansclassification 1/largescalemeanshift 1/trainimagesclassifier 3/
  trainimagesregression 6）。
- **v0_5 构建结果**（`route2_training/profile/qgis_operator_capability_profile_v0_5.json`，
  SHA256 `dfc03628ad0f842b25806ebc575e9bdc1043e087ac7445c854847f12dff4f73b`）：
  **109/109 卡填充**（1,011 参数 + 134 输出 + 116 个带 choice 树的参数）；功能描述入
  layer_c_intent（source=otb_8.1.2_SetDescription）；19 处 input_types_norm 按证据
  纠正（如 trainimagesclassifier literal→[raster,vector]，manifest 记录新旧值）；
  顶层 description 键 0/1291（S1 守卫）；非 OTB 1,176 条与 v0_4 逐条 deep-equal；
  v0_4 本体 SHA 与冻结一致（95ae97bc…未动）。6 个 provenance_unverified 算子原样保留
  + 状态标记（`PROVENANCE_UNVERIFIED_V1.json` 含后续核验任务定义）。
- **full_card() 渲染抽查（验收条款）通过**：trainimagesclassifier 卡现在直接暴露
  `classifier(Choice)` 与 io.out/io.confmatout 输出——T-009#S4 弃权理由（"卡未记载
  是否支持 RF"）在 v0_5 卡面上成为可证伪项。已知限制如实登记：冻结渲染器不展开
  choice 候选值与参数长描述（与全库其他 provider 的 enum 未展开现状一致，P2 项）。
- **下一步（未执行，待排程）**：A1 pack 构建（v0_5 卡 × 冻结 Top-10）→ 服务器 S2
  重跑 → 四分指标对比。
