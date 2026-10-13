# S3 探针设计文档（v1 修订版，供最终验收——设计产物，不运行模型）

> **v1 修订说明（2026-10-09）**：按 owner 设计验收意见修订 A1/B1/C2/D1 四个探针、
> A2 因子计数表述，并新增 4b uncertainty_appropriateness 独立诊断字段。
> 修订明细见第 7 节。本版提交最终验收；验收通过后冻结为 S3_PROBES_v1。
> **冻结裁定与 hash 记录在 `S3_PROBES_V1_FREEZE.json`（本文件保持冻结基线原样，不再修改）。**

状态：S3_DESIGN_DRAFT / NOT_RUN / NOT_MODEL_INVOLVED
日期：2026-10-09
授权依据：GATE_B_DEFINITION_v1（S3 probe_design = approved_design_only_no_model_run）
前置裁定：S2 结果裁定（GeoAnalystBench 有条件采纳=投影开发；GISAgentBench 有条件采纳=获取受阻；AutoGEEval-plus 移出 B 候选；S4 暂缓）

## 0. S3 的角色限定（冻结）

> S3 探针**只用于测试评价规程本身的可用性**：判据是否可操作、预期变化是否可无歧义写出、变体空间是否可控。探针上的任何表现**不构成模型能力证据**。

映射开发（GeoAnalystBench）与独立能力评价分开记账；本文件只做评价规程调试。

## 1. 探针总体设计：4 类 × 2 = 8 个

| 类 | 变化类型 | 数量 | 基础样本 |
|---|---|---:|---|
| A | 删除任务要求 | 2 | 30_rusle / 35_cost_surface |
| B | 新增任务要求 | 2 | 30_rusle / 21_vegetation |
| C | 改变目标对象数量 | 2 | 21_vegetation / 38_urban |
| D | 信息不足或冲突 | 2 | 38_urban / 27_fire |

基础样本均来自 6 条开发样本（开发样本本身不进入任何测试集——探针只用于规程调试，此双重用途已在 Step2 v0 裁定中记录）。

## 2. 防污染规则（冻结，适用于全部探针）

1. **预期变化必须从任务修改规则推导**，不得把源码中删除/新增的代码直接当答案。推导路径：Task delta → 任务语义层面应有的职责变化 → 对照 duty gold 验证合理性；源码只用于确认 gold 本身的证据链，不用于生成 expected_duty_changes；
2. **计数服从任务而非源码/文字数字**：C 类探针显式检查模型是否服从 Task 规定的范围并识别未指定范围；`script_93009`（Task=2 年 vs source=5 年）作为反例纳入 C2 设计；
3. 每探针独立预注册，注册后不修改；争议进 adjudication_rule，不事后改预期。

## 3. 预注册条目（全部 8 探针）

### A 类：删除任务要求

#### A1 — RUSLE 移除 P 因子

```json
{
  "probe_id": "A1",
  "base_case": "30_rusle_soil_loss (script_36595)",
  "task_delta": "从任务文本中删除 'land management (P)' 要求；任务不再显式要求计算 P 因子",
  "expected_duty_changes": {
    "removed": ["compute the land management (P) factor（独立计算职责必须消失）"],
    "modified": ["combine the factors into the soil-loss equation → 组合职责必须调整，不再要求任务显式计算 P；具体方程形式不由本探针规定"]
  },
  "expected_stable_duties": ["R 因子计算", "K 因子计算", "LS 因子计算", "C 因子计算", "分类", "统计输出"],
  "dependency_expectations": "组合职责的内部构成变化属于 dependency_propagation；分类与统计职责不应无故改变",
  "acceptable_variants": [
    "组合职责可表述为四因子乘积、或'在现有因子基础上整合'、或条件性表述（如'若采用默认 P 值则注明假设'）",
    "模型可对删除 P 后的科学模型定义标记 uncertainty——这属于恰当不确定性，不判 fail",
    "组合职责可单列也可并入聚合表述"
  ],
  "uncertainty_rule": "科学模型定义未由任务充分指定时，条件性表述或 uncertainty 均正确；断言唯一的四因子公式为'经确认的科学模型'不是本探针的评分依据——本探针检验任务要求变化，不检验公式猜测",
  "failure_definition": "P 独立计算职责仍出现；或 R/K/LS/C 任一无故消失；或组合职责完全不反映 P 要求的移除；或模型虚构任务未要求的新因子",
  "adjudication_rule": "组合职责的表述粒度争议按 'Task-granularity' 规则判 partial；四因子乘积 vs 条件性表述不构成对错差异"
}
```

#### A2 — 成本面移除水库掩膜

```json
{
  "probe_id": "A2",
  "base_case": "35_ancient_road_cost_surface (script_405410)",
  "task_delta": "删除 'reservoir presence (GRanD-based vector mask)' 因子要求；任务改为移除水库约束后，按剩余任务要求融合成本因素",
  "expected_duty_changes": {
    "removed": ["apply the reservoir mask"],
    "modified": ["fuse all factors → 融合职责不再包含水库项；融合构成随任务剩余要求确定，不以固定因子数量为独立判据"]
  },
  "expected_stable_duties": ["slope/altitude 成本", "snow 成本", "sea/surface-water 障碍", "potable-water accessibility", "归一化 0-255", "导出"],
  "dependency_expectations": "融合职责的构成变化 = dependency_propagation；归一化与导出不变",
  "acceptable_variants": ["融合表述允许乘法链或逐项叠加描述", "因子数量表述以任务文本实际剩余要求为准，不预设'六因子'"],
  "uncertainty_rule": "无",
  "failure_definition": "reservoir 职责仍出现；或融合职责未反映水库要求移除；或新增任务未要求的空间约束",
  "adjudication_rule": "融合职责的构成描述粒度争议判 partial，不影响 necessary_change 判定；因子计数本身不作为对错判据"
}
```

### B 类：新增任务要求

#### B1 — RUSLE 增加沉积物输移输出

```json
{
  "probe_id": "B1",
  "base_case": "30_rusle_soil_loss (script_36595)",
  "task_delta": "任务新增：'并输出每个子流域的潜在沉积物输移量（假定与土壤流失量成正比，比例系数由数据经简单缩放得到）'",
  "expected_duty_changes": {
    "added": ["output per-subbasin sediment yield（新增输出职责，覆盖沉积物输移要求）"],
    "modified": ["输出职责集扩展"]
  },
  "expected_stable_duties": ["五个因子计算", "土壤流失组合", "流失分级", "原有面积统计"],
  "dependency_expectations": "新输出职责应依赖土壤流失估计或其汇总结果；依赖方向正确即可，内部计算流程不预注册",
  "acceptable_variants": [
    "沉积物职责可并入统计职责或独立成段",
    "比例系数/缩放方法保持抽象、以占位符表示、或标注待定——均为正确",
    "不要求任何具体缩放算法出现"
  ],
  "uncertainty_rule": "缩放规则未由任务指定时，保持抽象或标注待定 = 正确；虚构具体缩放算法或标定流程不加分也不判 fail（不作正确性标准），但若将其表述为任务要求则记 implementation-detail 固化",
  "failure_definition": "无新增输出职责覆盖沉积物要求；或新职责与土壤流失无依赖关系；或原有职责消失",
  "adjudication_rule": "新增职责与统计职责合并表述时判 correct（不强制独立段）"
}
```

#### B2 — 植被预测增加精度报告

```json
{
  "probe_id": "B2",
  "base_case": "21_predict_vegetation_cover_components (script_302840)",
  "task_delta": "任务新增：'对每个目标变量的预测输出与实测值计算 R² 并随导出文件一并提供'",
  "expected_duty_changes": {
    "added": ["compute per-target validation metric (R²)（新增：按目标变量对比预测与观测）"],
    "modified": ["export 职责扩展：导出内容含 R²"]
  },
  "expected_stable_duties": ["按目标训练 RF", "预测与采样", "过滤无效像素", "重复结构 8 目标不变"],
  "dependency_expectations": "R² 职责依赖预测采样职责；逐目标性质继承 repeat 结构（binding=per-target-variable 不变）",
  "acceptable_variants": ["R² 计算可并入导出职责或独立", "逐目标或汇总口径均可（任务说'每个目标变量'，逐目标为必要）"],
  "uncertainty_rule": "无",
  "failure_definition": "R² 职责缺失；或 R² 未按目标变量逐个对应（违反任务显式范围）；或 repeat 结构被破坏",
  "adjudication_rule": "'每个目标变量'的范围解释争议：以任务文本字面为准（逐目标），不引用源码行为"
}
```

### C 类：改变目标对象数量

#### C1 — 植被预测 8 目标 → 3 目标

```json
{
  "probe_id": "C1",
  "base_case": "21_predict_vegetation_cover_components (script_302840)",
  "task_delta": "目标变量列表改为三个：BareGround, TotalFolia, SageBrushC（其余删除）",
  "expected_duty_changes": {
    "modified": ["repeat 结构：repeat_count 8→3；unit_structure 同构不变；binding 仍 per-target-variable"]
  },
  "expected_stable_duties": ["unit_structure 内的四段职责", "acquisition 职责", "export 模式"],
  "dependency_expectations": "无额外传播——数量变化只作用于重复结构本身",
  "acceptable_variants": ["三目标可分别叙述或以'对每个目标'统一叙述"],
  "uncertainty_rule": "无",
  "failure_definition": "repeat_count 仍为 8 或跟随源码；或 unit_structure 随数量改变；或绑定关系丢失",
  "adjudication_rule": "若模型输出与源码 8 目标一致而非任务 3 目标 → 直接 fail（计数服从任务的直接检验）"
}
```

#### C2 — 城市扩张年份双分支

```json
{
  "probe_id": "C2",
  "base_case": "38_urban_expansion_change_detection (script_93009)",
  "task_delta": "两个分支（分别注册预期，评分分开记录）：(a) 任务明确 '仅比较 1985 与 2018 两个年份'；(b) 任务保持原表述——原文提到 1985 与 2018 两个比较年份但未规定处理的完整年份范围",
  "expected_duty_changes": {
    "branch_a": {"modified": ["year 提取职责的 repeat_count = 2（任务显式范围）"]},
    "branch_b": {
      "permissible": [
        "围绕任务明确提出的 1985 与 2018 构建最小比较方案（repeat_count=2，任务指定范围）——这是正确答案",
        "提出扩展至其他年份时必须标记为可选扩展或待确认范围，不得作为任务强制要求"
      ],
      "forbidden": "不得因源码处理五年而推断任务要求处理五年"
    }
  },
  "expected_stable_duties": ["历史图层加载", "频率计算", "变化 incidence", "验证职责"],
  "dependency_expectations": "年提取职责的数量变化不影响其他职责",
  "acceptable_variants": [
    "branch_a 中 2 年可分别叙述或统一叙述",
    "branch_b 中遵循任务已指定的两年且不擅自扩大范围 = 正确（不要求输出 uncertainty 才算对）",
    "branch_b 中给出两年最小方案 + 标注范围可扩展（待确认） = 正确"
  ],
  "uncertainty_rule": "branch_b 不强制 uncertainty：任务已含年份信息（非信息缺失场景），判分核心是'是否跟随源码扩大范围'；只有把源码年份数当作任务要求时才 fail",
  "failure_definition": "任何分支输出跟随源码 5 年作为任务要求；branch_a 输出非 2 年；branch_b 把扩展年份表述为强制要求",
  "adjudication_rule": "引用 script_93009 Task=2 vs source=5 反例；语义区分冻结为：'任务指定两年'（branch_b 默认正确路径）≠ '任务未指定完整年份范围'（若需测试该场景应另设删除年份范围的独立探针，本版不加）"
}
```

### D 类：信息不足或冲突

#### D1 — 成本面冲突约束

```json
{
  "probe_id": "D1",
  "base_case": "35_ancient_road_cost_surface (script_405410)",
  "task_delta": "任务同时要求 '(a) 输出必须为研究区内每一个水域像元提供有限、可通行的成本值' 与 '(b) 所有水域像元必须被标记为不可通行，不能参与任何可行路径'",
  "conflict_validity": "两要求经语义核验不可同时满足：水域像元不能既是有限可通行值又是不可通行排除项（任务文本限定'有限、可通行'，故 NoData/无穷大赋值不构成调和）",
  "expected_duty_changes": {
    "conflict_flagged": "模型应指出两要求不可同时满足，并请求澄清或给出条件分支，而非任选其一 silently"
  },
  "expected_stable_duties": ["各因子计算职责本身可保留"],
  "dependency_expectations": "水域相关职责的语义在冲突解决前不可确定",
  "acceptable_variants": ["指出矛盾并请求澄清", "给出两分支方案并标注各自满足哪一要求、依赖任务澄清", "给出无水域版本并明确声明违反了 (a)"],
  "uncertainty_rule": "识别冲突并标注 = 该探针的正确行为（矛盾可识别判据在此评分）",
  "failure_definition": "silently 满足其一而忽略另一；或输出自相矛盾的成本面；或虚构第三种'调和'规则而不声明其假设",
  "adjudication_rule": "条件分支方案若完整覆盖两要求的不同满足方式判 correct；'水域赋 NoData/无穷大'不构成调和——它满足 (b) 但直接违反 (a)"
}
```

#### D2 — 城市扩张缺数据源信息

```json
{
  "probe_id": "D2",
  "base_case": "38_urban_expansion_change_detection (script_93009)",
  "task_delta": "任务改为：'比较两个时期的城市范围'，但不提供任何分类数据来源、时间点或区域信息",
  "expected_duty_changes": {
    "uncertainty_expected": "任务信息严重不足 → 模型应标注缺少：分类数据源、具体年份、研究区；可给出 generic 职责骨架（获取分类数据→过滤→时相对比→验证）但不得填充具体实现细节"
  },
  "expected_stable_duties": ["generic 职责骨架（分类时相对比）可保留"],
  "dependency_expectations": "所有具体实例化职责（数据源、年份）在信息补全前不可确定",
  "acceptable_variants": ["纯骨架输出 + 明确的信息缺口清单", "以占位符（<data source>/<year1>/<year2>）表示待定项"],
  "uncertainty_rule": "信息不足标注 = 正确行为（矛盾/不足可识别判据在此评分）",
  "failure_definition": "虚构具体数据源/年份/区域（把领域常见选择当任务要求）；或拒绝给出任何骨架（过度 uncertainty）",
  "adjudication_rule": "'过度 uncertainty'（完全拒答）判 partial 而非 correct——规程要求标注缺口而非放弃规划"
}
```

## 4. B2 四判据适用性矩阵

| 探针 | 必要变化正确 | 无关职责稳定 | 依赖变化合理 | 矛盾/不足可识别 |
|---|---|---|---|---|
| A1 | ✓ | ✓ | ✓ | n/a |
| A2 | ✓ | ✓ | ✓ | n/a |
| B1 | ✓ | ✓ | ✓ | n/a |
| B2 | ✓ | ✓ | ✓ | n/a |
| C1 | ✓ | ✓ | n/a（无传播） | n/a |
| C2 | ✓（双分支） | ✓ | n/a | n/a（branch_b 语义修订：任务已指定两年，非信息缺失场景） |
| D1 | n/a（无必要变化） | ✓ | ✓ | **✓（主判据）** |
| D2 | n/a | ✓ | n/a | **✓（主判据）** |

规则：`n/a` 不计通过也不计失败——**矛盾可识别只在确实存在不足/冲突的探针上评分**（D1/D2；C2-branch_b 经修订不再属于信息缺失场景，其判分核心 = 是否跟随源码扩大范围，归入必要变化正确/失败定义）。不适用不当作通过。

## 4b. uncertainty_appropriateness 独立诊断字段（新增）

四判据之外，每个探针的每次输出记录独立诊断字段：

```text
uncertainty_appropriateness:
  appropriate        # 恰当的不确定性（信息确实不足/冲突时标注）
  unnecessary_refusal # 无必要的拒答（信息充分却放弃规划）
  unspecified_fill   # 擅自补全（信息不足却虚构细节）
  none_needed        # 无需不确定性且未使用
```

- 该字段是**诊断记录，不改变四判据结构**，不计入四判据得分；
- 它把"恰当不确定性"与"过度拒答"/"擅自补全"的区分从间接约束（原先误挂在"无关职责稳定"下）升为独立记录；
- 汇总报告中按探针类别分层报告三值的分布，用于评价规程本身的校准。

## 5. 评分规程歧义记录（Q3 要求）

1. **组合/融合职责的粒度**（A1/A2）：单列 vs 并入相邻职责——按 Task-granularity 规则判，partial 不影响 necessary_change；
2. **新增职责的归属**（B1/B2）：独立段 vs 并入输出段——均 acceptable_variants；
3. **generic 骨架 vs 拒答边界**（D2）：骨架+缺口清单 correct；纯拒答 partial（由 4b 字段独立记录为 unnecessary_refusal）；
4. **C2 双分支**：一次探针两个预期集，评分时分支分开记录，不合并；branch_b 的正确路径 = 遵循任务已指定的两年；
5. **uncertainty 的双重角色**：由 4b 独立诊断字段承载，不再依赖"无关职责稳定"间接约束；
6. **A1 科学模型语义**：四因子乘积、条件性表述、uncertainty 均为 acceptable variants——探针检验任务要求变化，不检验公式猜测。

## 6. 交付清单核对

- [x] 8 个完整预注册探针（4 类 × 2）
- [x] 每探针的预期变化、允许变体、失败条件
- [x] 四判据适用性矩阵（n/a 规则显式）
- [x] 评分规程歧义记录（5 条）
- [x] 防污染规则（任务规则推导、计数服从任务）

## 7. 结论：是否具备进入独立评价设计的条件

**有条件具备**。规程层面：四判据可操作、预注册字段完整、n/a 处理明确、防循环规则（任务规则推导 + 计数服从任务）已固化、uncertainty_appropriateness 独立诊断字段已建立。

修订记录（2026-10-09，owner 设计验收意见落实）：
1. A1：不再预设四因子乘积为唯一正确答案；条件性表述/uncertainty 均可接受；
2. B1：不强制输出未指定的缩放算法；系数保持抽象或标注待定均正确；
3. C2：branch_b 语义修正——任务已指定两年（非信息缺失），遵循任务两年范围即正确；"完全未指定年份范围"场景如需测试另设独立探针，本版不加；
4. D1：冲突改写为语义上确实不可同时满足的形式（"有限可通行" vs "不可通行排除"），并显式排除 NoData/无穷大调和；
5. A2：移除"六因子"独立硬判据，因子计数以任务文本剩余要求为准；
6. 新增 4b uncertainty_appropriateness 独立诊断字段。

两个待 owner 确认项：
1. 修订后的 8 探针经 owner 最终验收后冻结为 S3_PROBES_v1；
2. B2 初步证据阈值（80%/90%）在仅 8 探针上的读数只作规程调试反馈，不作任何能力断言——此点已在 GATE_B 冻结记录中，此处重申。

## 8. 边界

不运行模型；不根据探针结果声称能力；不启动 S4；不扩量；不修改 G0/G1/G2/G3、Blueprint、locked test。探针冻结前不进入任何执行。
