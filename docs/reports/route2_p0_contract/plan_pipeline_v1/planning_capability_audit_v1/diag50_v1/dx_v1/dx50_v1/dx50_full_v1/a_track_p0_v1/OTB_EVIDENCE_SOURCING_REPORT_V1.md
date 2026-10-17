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
