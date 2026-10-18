# I1 前置审计报告 V1（2026-10-18）：卡片压缩规则不可行，需 owner 重新选择单变量

> 授权：owner 有条件批准 I1 实现准备；**未批准正式生成**。本报告只做字段审计、确定性压缩原型、
> Token 统计与配置冻结；**未运行任何生成**。
> 原因：owner 指出的混杂风险（"只留前 8 个 optional"可能删掉决定性证据）经审计后**成立且严重**。

## 1. 字段重要性审计（449 个受影响 Top-10 算子上的 1,132 个 optional）

分类规则（显式、可复核，见 `scripts/dx_i1_compaction_v1.py` docstring）：

- **required**：全部保留；
- **semantic**（保留 name+type）：所有 `Choice`；所有输入/输出类（raster/vector/file/model/field）；
  `Bool` 标志；`Field`；名字命中 mask/nodata/threshold/method/mode/type/level/sensor/filter/
  band/class/layer/field/feat/model/lut/stats/training/roi/table/grid/source/input/output/strategy；
- **execution**（可汇总省略）：Int/Float 调参名（radius/size/iter/eps/tol/memory/tile/…）与
  OTB 分类器子参数族 `classifier.*.{k,m,c,gamma,nu,degree,coef0,eps,term,iter,p,opt,prob,ra,cat,var,max,min}`；
- **UNKNOWN → semantic（fail-safe 保留）**。

全库结果：**required 6,094｜semantic optional 2,623｜execution 仅 137**。

→ 在"不得删减决定性证据"的约束下，**可压缩空间只有 137/1,132 ≈ 12% 的参数**（且多为短名字），
其余 88% 的 optional 都是按规则必须保留的语义证据。

## 2. 确定性压缩原型的 Token 实测（158 步，两臂各 158 条提示）

实现：保留 required/description/outputs/accepts 与全部 semantic optional；execution 参数以
`(+N execution params)` 汇总；超预算卡**标记不删**。

| 指标 | 对照（v0_5 原卡） | 压缩原型 |
|---|---|---|
| 提示 token 中位数 | 1,366.5 | 1,395.5 |
| 均值 | 1,413.9 | 1,474.6 |
| 逐对 token 比（压缩/原）中位 | — | **1.0013** |
| 总 token 变化 | — | **+9,585（22.3 万中的 +4.3%）** |
| 超预算卡（>1,200 字符） | — | 64 张（标记，不删） |

**压缩不仅没有缩短提示，反而略增**：可省略的执行参数太少，而"超预算不删"使原本被
`full_card(CARD_CAP=1800)` 截断的少数长卡不再截断（这部分是**恢复证据**，不是冗余）。

## 3. 结论：I1 的原始设计不可执行

- 在 owner 的约束下（保留全部决定性证据、不新增枚举、不改模板/候选/解码），
  **卡片压缩这一单变量无法产生有意义的长度缩减**——因此无法检验"提示长度→空输出"的因果假设。
- 此前 I1 草案中"optional 只留前 8"确实会删掉语义证据（审计支持 owner 的担心），
  而**删减版**即使有效，也无法区分"降低提示负担"与"改变卡片语义"两种机制——这正是 owner 要防的混杂。
- 因此 **不提交 I1 运行请求**。需要在以下单变量中由 owner 重新指定：

| 选项 | 单变量 | 代价/风险 | 说明 |
|---|---|---|---|
| **D1 长度因果诊断（推荐先做）** | 提示长度本身（中性填充） | 不改变任何语义内容 | 对同一批短提示（B1/B2）追加**中性分隔文本**匹配到 B5 长度，验证"长度→空输出"是否因果。若成立，再讨论可行的缩短路径；若不成立，则长度只是相关性，需转向内容/位置因素 |
| D2 模板压缩 | 固定提示模板（规则/指令块） | 改变任务指令表述 | 模板约 500–700 token，是唯一有压缩空间且不删证据的部分，但会改变指令语义，需单独立项 |
| D3 候选数 K 缩减 | 候选集大小 | 同时改变候选集（第二变量） | 不推荐（owner 已排除） |
| D4 解码/预算 | 生成参数 | 改变解码 | 冻结中，不推荐 |

## 4. 推荐

1. **先做 D1（长度因果诊断）**：单变量、无语义改动、n 可控（20–30 条短提示，中性填充到长提示
   水平）；可证伪预测：填充后空输出率显著上升（若因果）或基本不变（若仅相关）。
2. 若 D1 证实长度因果，再评估 D2（模板压缩）或"结构化提示重排"（指令前置）等单变量设计。
3. 在 D1 结果前，I1 保持未执行。

## 5. 产物与可追溯

- `i1_v1/I1_FIELD_IMPORTANCE_AUDIT_V1.json`（1,223 个算子的逐参数分类）
- `i1_v1/I1_CARD_STATS_V1.json`（每步卡片字符/超预算/省略清单）
- `_i1_prep_work/i1_prompts.json` + 服务器 token 统计 `i1_tokens.json`（316 条实测）
- 未改 profile / full_card / S2_PROMPT；未运行生成；A1/A2 状态不变。
