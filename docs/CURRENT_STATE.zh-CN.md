# 当前项目状态

最后更新：2026-10-15（QGIS 专项训练路线冻结登记；PCA/RL 快照以 10-13 条目为准，Planner
P1/P2 与 E2E 详细过程以 `docs/CURRENT_STATE.md` 英文版为准）

## (00) QGIS 专项训练路线冻结为项目正式方向（2026-10-15，owner 终裁）

- owner 终裁：QGIS 专项训练技术路线冻结（A 算子知识底座 → B 训练数据建设 → C 两阶段
  SFT → D 完整推理链路 → E 初版交付+定向优化），A/B 并行。三项修正：①同一 Qwen3.5-9B
  连续训练配方（GEE 规划监督+QGIS 算子语义+工作流组合+DAG 监督按职责混入，不做两次独立
  训练）；②复杂任务完整性靠分工验证（模型提计划/外部证据账本追踪/结构化校验器查结构/
  独立语义评审+人工抽查——结构合法≠语义正确）；③知识整理与训练数据建设并行推进，防知识
  工程变长期项目。
- 常设原则：最终工作流质量=唯一主目标；完整约 1,200 算子目录=权威知识源（RAG+结构校验，
  不要求模型背全）；规划步骤≠算子抽象层（不引入统一算法分类层，输出=真实 QGIS 算子的
  processes+links DAG）；先完整系统后定向优化；禁自我评价代替外部验证。GRPO 与完整
  GraphRAG 后置（等第一版瓶颈实测）。第一版验收=6 项清单（算子知识/算子接地/规划完整性/
  DAG 正确性/问题修复/评估可信度）。
- 评测纪律沿用：dev-120 选点 / test-111 终判；route2_C0 dev opF1 0.5611 = 统一协议对比
  基线；系统级与模型级贡献自第一版起分开记账。
- 盘点已完成（2026-10-15，四路并行只读审计）：《QGIS 专项训练实施规范》V1 骨架已产出
  `docs/plans/QGIS_SPECIALIZED_TRAINING_IMPLEMENTATION_SPEC_V1.md`。要点：目录 = 1,291 算子
  三源一体；**309 = 1,565 行接地数据的 gold 已行使子集**（148=test111，38=benchmark
  v0.1-120）；Capability Profile v0_4 覆盖全部 1,291 且含参数 schema（1,127 ops 有默认值）
  = 知识底座主干；四项校验器现成可复用；数据头号缺口 = 参数监督为零 + 接地仅 1,565 行
  （D5 渲染管线 = 扩量路径）；`stage1_train_v2_2A` 本地缺失且行数出入——冻结勿引用；
  blueprint_v2_gold_v3 本地镜像已找回（SHA 核验，旧"无镜像"记录作废）。**快看线已执行并关闭（同日，owner 指令）**：108 held-out 任务 × P0/Base 216 生成；31 样本
  人工判分（L1 全查 22 + 三带抽查各 3）——P0 CM 31/31=Y 跨带一致（通用骨架+核心缺失）、
  Base 3/31；故障定位（原始 Blueprint 仅 2-5 通用 stage、转换无损排除）+同接口探针（P0+NL
  提示+rep-pen → 8/8 立即 EOS）闭环归因：接口脆性+内容贫瘠+schema 天花板；"二次训练毁能力"
  不成立（Base 优势=预训练先验）。**owner 终裁**：①P0 fmt 除名 Stage-1 候选；②新训练
  from-Base；③Blueprint v2 降级为辅助监督（输出目标除名）；④unified training 输出空间=
  完整 QGIS workflow（processes+links 含算子/参数/IO/DAG）。三原则：先冻结输出契约再扩数
  据；与 Base 同测试集/提示/评测器对比（格式正确率≠工作流质量）；统一≠无差别混合（GEE 仅
  辅助、禁跨平台标签错配）。执行序：D1 Unified Workflow Contract → D2 渲染管线 → D3 配方
  → D4 评估门槛 → CPU 审查后 GPU（当前不批准配方与训练）。RL 线（输出空间=Blueprint/P0）
  无限挂起。归档 `pca2_v1/QUICKLOOK_FINDINGS_V1.md`。**DIAG-50 已收口（2026-10-15）**：
  从 100 任务分层抽 50（12/18/12/8，seed 20261013）；A 臂 50/50 就绪（复用快看 Base NL 行）；
  B 臂（Base+算子卡→processes+links JSON）批前烟测五轮全 FAIL——两轮为仪器 bug 已修
  （TRUNC 1024 截掉提示词尾部指令块；greedy 未对齐 rep-pen 1.15 冻结仪器），其余为内容级
  失败（think 不收敛/字面循环/卡片循环枚举/schema 回声），全部仪器组合 parsed_ok 0/4。
  **owner 裁定：接受「裸 Base 零样本 JSON 图契约不可用」为正式诊断结论**（签名归档
  parsed_ok 0/20；同批任务 A 臂 NL 步骤正常 → **Base 能力格式条件化，SFT 优先级证据指向
  格式+接地监督**）。产物：`diag50_v1/DIAG50_SMOKE_ROUNDS_V1.md`、
  `DIAG50_BARM_FAILURE_SIGNATURES_V1.json`、`DIAG50_WORKBOOK_A_V1.md`。该评审路径已演化为
  **DX 五阶段诊断线（`dx_v1`，经 owner 多轮审查）**：冻结仪器（S0 规划 → S1 冻结 MiniLM
  Top-10 → S2 逐步选拔含完整算子卡 → S3 组合 → S4 静态验证）+ commit-marker recorder
  （raw+gen+commit 无覆盖发布；15/15 测试、mdzhang ext4 探针 8/8）。**DX smoke6（6 任务，
  2026-10-16）完成：45/45 记录 COMMITTED**；头条：第一堵能力墙 = **S2 选拔**（正选 7 /
  显式弃权 16 / 无判定 10，其中 9 个空 raw 已由 recorder 证据定位为生成侧输出、排除存储
  损坏）；S0 可解析 6/6；S3 被 S2 饿死（组合能力不可判）；GAP_COMPLETE≠成功与 S4 零缺陷≠
  好工作流均有活例证（T-086、T-062）。报告：`diag50_v1/dx_v1/dx50_v1/smoke6_v1/`
  下 `DX50_SMOKE_FINDINGS_SMOKE6_V1.md` + `DX50_SMOKE_REVIEW_SMOKE6_V1.md`。
  **owner 审查勘误（同日，已解决）**：评审表的 UNCOMMITTED 属实但仅限本地——解析阶段旧工具
  `save_record` 以文本模式重写已发布 raw（LF→CRLF，36 条）；服务器原件经同 recorder 复审计
  45/45 COMMITTED、零内容损失（CR 剥离哈希 45/45==标记，隔离存证）；镜像已从服务器原件恢复，
  解析工具改 parse-only 并加回归测试（16/16），评审表重生成（机械摘要置顶 45 条完整性）。
  findings 升 V1.1 含勘误节。**全量 DX-50 已完成（owner 授权 2026-10-16，tag dx50_full_v1）：
  392/392 记录全 COMMITTED**（S0 50/16.9min、S2 293/137.9min、S3 49/39.4min；raw
  VERIFIED 316/EMPTY 76；三 ledger complete=True；T-050 显式排除）。n=50 头条：
  **S2 选拔=确证的第一堵墙**——正选 48/293=16.4%、可判定步弃权 74.2%、无判定 37.9%
  （其中 72%=2048 截断）；S3 CAP_TRUNC 83.7%；越选 1 例。报告：
  `dx50_v1/dx50_full_v1/DX50_BATCH50_FINDINGS_V1.md` + `DX50_BATCH_REVIEW_DX50_FULL_V1.md`。
  **owner 审查已收口（2026-10-17）：S0 50/50 终审确认；S2 弃权 63 行抽查全数裁定——
  过度拒绝(明确)=0，首要根因=算子卡贫瘠，其次检索缺失。** 已冻结裁定两份：方法论
  （`dx_v1/DX_RESEARCH_ROUTE_RULING_OWNER_V1.md`：已证实 vs 待验证严格区分/A 轨四项验收/
  解析器 v2/推进顺序①补卡底座→②仪器→③重建 S2 基线→④再定训练）与实验设计
  （`dx_v1/DX_EXPERIMENT_DESIGN_RULING_OWNER_V1.md`：**A1 卡片补全 / A2 检索语料升级 /
  B 规划能力对照，单变量分离，A1 与 A2 各自完成后才测组合；「在库中/被 Top-10 召回/
  卡片足以证明适用」三态分记不合并**）。解析器 v2 修正基线：无判定 130（44.4%）、
  显式弃权 119、正选 48（16.4%）。**执行队列：A 轨 P0 补卡已构建（2026-10-17）：
  profile v0_5 以新文件落盘（SHA `dfc03628…`；构建器 `dx_a_track_build_v05_v1.py` +
  逐字段 provenance manifest）——109/109 张 OTB 卡自上游 8.1.2 经宏提取器 v2 填充
  （1,011 参数 + 134 输出 + 116 个 choice 树参数；19 处 input_types_norm 纠正；
  攻克基类头文件/CompositeApplication/ShareParameter 三类特殊 app；框架自动参数
  ram/elev/rand 排除不猜）；顶层 description 键 0/1291（S1 守卫）、非 OTB 条目与
  v0_4 逐条相等（v0_4 SHA `95ae97bc…` 未动）、6 算子标记 `provenance_unverified`
  （owner 裁定：来源与目标环境可用性未核实——后续核验任务已登记，不作定性幽灵）。
  full_card() 渲染抽查通过：trainimagesclassifier 卡可见 classifier(Choice)+io.out
  ——T-009 卡盲区解除。队列下一步：A1 pack（v0_5 卡 × 冻结 Top-10）→ 服务器 S2
  重跑 → 四分指标；再 A2 受控检索对照（不静默改检索）→ B 独立。仪器发现：S1 检索实为算子 ID 词面相似度
  （0/1291 有 description 键、layer_c_intent 未读取）——S1 修复另立受控变更；
  补卡禁写顶层 description 键。** B 轨（GEE 规划）：owner 假设裁定 + 联合审计 **Q1-Q4 全部完成**
  （`diag50_v1/B_TRACK_GEE_PLANNING_RULING_OWNER_V1.md`、`B_TRACK_Q2Q4_RULING_OWNER_V1.md`、
  `B_TRACK_GEE_POOL_JOINT_AUDIT_V1.md`[V1.1]、产物 `b_track_audit_v1/`）：全链复制度不高但
  局部高度集中（Q1）；任务条件→结构耦合存在且单调，**Q2 40 对人工判读已完成并登记（见下）**；
  精确同指令异模板可忽略、差异=局部小变体（Q3）；**规划 exact 率随训练池支持度单调上升**
  （absent 14.1%/singleton 0%/low 0%/mid 12.3%/high 25.6%）且预测向高频模板偏移 +19%
  ——低支持错误=数据支持缺口（固有），高频偏移=训练引入（干净归因需 Base vs 训练版本 B 臂）；
  813 个 AGGREGATION 模板混合时间合成/分区统计语境=30 标签抹平实证（方向②锚点）。
  owner 不干预门已过——Q2 人工判读已完成，下一步=V2-P0 原始程序逐步对照（见下）
  → 审查后参考样本构建 → 小规模对照训练。
  **Q2 40 对人工判读已登记（2026-10-17，owner 四批判读 →
  `b_track_audit_v1/Q2_OWNER_ADJUDICATION_V1.md/.json`）**：SAME 组 C 类（确认结构
  标注错误）=**0**、A 类（同结构充分合理）8/20、B 类（需原始程序核验）12/20，重点核验
  =SAME-15（分类 vs 回归被 CLASSIFICATION 抹平）与 SAME-19（多时间粒度被单一
  AGGREGATION 概括）；DIFF 组可疑 12/20、合理差异可能性较高 2（DIFF-3/18）、弱变体 1；
  **owner 三字段口径（结构变化要求/标签表达力/链条差异证据）冻结为 B 轨审查标准**。
  **机械修正：DIFF-20 两条链并非完全相同——恰差 1 个重复季节块（7 vs 6，MD 渲染不可
  辨）；抽样分组（模板集合相等判据）机械有效，该对登记为弱变体不作强正例，"分组质量
  检查"关闭（无 bug）。**核验包机械预观察：V3 全部 4 对 SAME（15/19/11/9）双侧
  canonical API 序列一致=同码双描述（字面量层须读源码确认）；14 对 DIFF canonical
  全部真实不同=程序确实不同。**V3 4/4 完成（源码级，`Q2_V3_WALKTHROUGH_FINDINGS_V1.md`：
  4/4 结构相同成立；SAME-15 指令 A 目标变量失实=代码自证 biomass；字面量层承载语义=
  双层表示分工证据）。V2-P0 6/6 完成（`Q2_V2P0_WALKTHROUGH_FINDINGS_V1.md`：6/6 结构
  差异均无任务逻辑依据——UI 挂件/实现级多解/重复块/重构/数据集版本/阈值+地图定位）。
  合并结论获 owner 裁定（`Q2_SEMANTIC_AUDIT_CONCLUSION_V1.md` §6 附记：结论 1-3 认可、
  十对边界保留、"十对零错误"收紧为仅指十对；B 双层表示主方向+A 治理手段；不批准改
  RLE/批量清洗/训练）。**池级只读复核已执行（同日，`Q2_POOL_RESCAN_MECHANICAL_V1.md/
  .json`）**：4,554 对健全门精确复现、脚本覆盖 99.6%；**结构不同总体仅 382 对（8.4%）**，
  substantive 候选 111（29.3%，任务驱动上界≈全近重复对 2.4%，真值待判读）；非实质
  机械候选 70.7%；**同码双描述 716 对（17.3%）=池级现象**；same_template_canonical_
  diff 232=Q1.5 抹平活体；校准 7/10+3 分歧机制已知（集合对称差对重复块盲；不赛后
  调参）；保真度代理=提名制（抽查 3 例全假阳性：精度舍入/变量间接/共因）。****owner 前置审查已落（`Q2_POOL_RESCAN_RULING_OWNER_V1.md` 逐字：七字段 schema+
  三防误判+优先序；统计口径锁定=分层加权 p̂=Σ(N_h/N)p̂_h、十对作既有证据、机械漏检
  另设审计样本）；材料缺口已补=117 卷宗证据包。** **117/117 判读全部完成（2026-10-17）**：
  owner 亲判 8（S001-S004/S007/S008/S010/S011）+ agent 受委托 109（逐条源码/diff 证据；
  LEDGER_V1.json+117 卷宗）。**池级加权估计已产出**（`Q2_POOL_WEIGHTED_ESTIMATE_V1.md`）：
  **P(结构等价|近重复对)=0.942 [0.90-0.97]；P(非等价)=0.057 [0.03-0.09]；P(任务逻辑驱动
  结构差异)=上界 0.057、样本点估计 0/117——owner 十对 0/10 在池级样本复现**；侧失实
  0.012、侧欠描述 0.058（机械可见下界）；层纯度：ui_scaffold 11/12 与 asset_version
  8/12 改判、reorder/multiplicity 最纯；same 桶 48/48 结构等价。仪器发现：RLE 退化
  三例（S096 空步/S100 47KB→1 标签/S110 32KB→3 标签）、间接资产引用、注释-代码矛盾、
  非互斥划分。**待 owner：抽查 agent 判读（每层 2-3 条，关键六条 S019/S023/S043/S090/
  S096/S107）→ A/B 联合设计规范冻结 → 参考样本集 → 小规模对照训练。纪律：诊断任务
  不入 B 轨训练；干预仍须 owner 放行。**
  **B 轨阶段转换（owner 决策 2026-10-18）：数据审计 → 训练数据治理与规划能力验证**。
  不再扩大人工判读、不清洗全池、不重训。本轮交付：治理规范 V1（六桶 A41/C1-26/C2-29/M14/
  Q1-5/Q2-2、判读层级+provisional 状态机、多参考规则、可追溯四问、版本/哈希/变更账本、
  任务组级划分治理）、`Q2_ADMISSION_V1.json`/`Q2_EXTRACT_SAMPLE_V1.json`（221 唯一）/
  `Q2_EXTRACT_RELATION_V1.json`/`Q2_ARCHIVE_FREEZE_INDEX_V1.md/.json`（19 文件哈希+8 commit）、
  17 条阻断深查与 8 条非阻断核验分列；双层表示规范 V1（L0 原始/L1 规划语义/L2 条件实现映射+
  L3 保真度+L4 监督；**不是更细的标签序列**，原始脚本始终保留）；可信参考集 V0 选样 24 组
  覆盖 10 类差异（语义字段待证据化策展、不得想象生成）。五步序：治理冻结（已完成）→ **阶段二：24 组参考集草案 24/24 全部起草完成
  （2026-10-18，`q2_stage2_reference_drafts/R01-R24.md`+INDEX：原始实现/L1 规划语义
  （script:line 锚点）/依赖/L2 条件映射/L3 保真度/多参考/准入/待补证据；全部
  draft_provisional，待 owner 逐组复核，风险序 R19/R18/R20/R23→R09/R05/R21/R01→其余；
  15 个待补项为二遍锚定，不改变已起草结构）。**owner 第二/三轮（2026-10-18）**：
  五组按条件一致性硬门槛修订；阶段三三规则冻结（关系≠准入、条件一致性=多参考硬门槛、
  按脚本重叠连通分量 R03+R10/R18A+R20 划分）；R01–R11 复核：R01/R11 通过、
  R02/R06/R07/R09/R10 修改后通过、R03 核心通过+口径审查（同脚本同描述却标签不同）、
  R04 partial（WorldPop 外部单位）、R05 及全部多参考暂缓、R08 拆分并修正两处事实
  （S042 双 S2 深度/双 4 段；S048 ETOPO1 vs S2、4 vs 2 段）。**owner 第四轮（R12–R15）**：
  R12 方法映射修正（145191 实为逆路径；方法差异仅在 S034/S036）；R13 L3 口径统一
  （额外平滑支路不构成失实；B8/B12 记为待核代码事实）；R14 **两侧均未见 C2 反射率缩放**
  （B 用 C2 L2 却无 0.0000275/-0.2 → 数值语义不可直接比较）；R15 六项 L2 条件字段登记。
  多参考全部暂缓。**owner 第五轮（R16/R17/R21/R22/R24）**：R16 修改后通过（仅同构模板；
  69799 用 HYBAS_ID 非 Feature Index）；R17 拆 S068/S105（TerraClimate 仅显示、不参与分类；
  S105 两期复用同一分类器）；R21 修改后通过（UI 排除保留；**45675:L351 的 cc 未定义**，
  ccc 定义于 L25 → 核心图表可执行性缺陷）；R22 拆 DIFF5/S013/S027；R24 修改后通过
  （**优营养化 a 是 56 要素列表索引非年份循环** → A/B 分析不同要素）。**28 条全部复核完成，
  无任何组获得无条件多参考准入**。**阶段三第 1–2 步已完成（2026-10-18）**：
  关系/准入冻结 V1（28 条，基线 9a418d1）；全量重叠扫描 V2（28 组/78 唯一脚本/
  本地覆盖 100%/零缺失；脚本 ID+内容哈希+任务文本三层；仍只有两个分量 R03+R10、
  R18A+R20）；划分约束 V1（共享脚本组同侧；重叠边≠多参考关系）。五项外部证据
  继续单独跟踪，不阻塞第 1–2 步。**阶段三第 3 步已完成（2026-10-18）**：近重复合并审计
  V1（四个合并分量：R03+R10 三脚本重叠 J=1.0；R18A+R20 两脚本 J=1.0；R18B+R24EUTRO
  J=0.942 优营养化同族；R19+R22S027 J=0.527 藻华同族）；R24 拆 AWEI/EUTRO；
  R17S068–R22S013（J=0.481）不合并（任务不同）。划分清单 V1：25 个原子单元，
  seed 20261018，train 18/val 4/test 3，A/B/C 共用。ABC 实验协议 V1 冻结候选
  （B−A=治理效应、C−B=双层增量、C−A 不作单独归因；同划分/模型/预算/解码/评估；
  主指标+共同门，阈值待 owner 批准）。关系/准入冻结基线升 V1.1（29 条）。**owner 有条件批准协议（2026-10-18）**：总体设计批准，
  原 +5pp/3pp/5pp 阈值原文不批准；协议升 V1.1+JSON，改为可复算规则——首要指标=必要步骤
  召回（任务级、任务组 bootstrap、语义匹配为主）；关键护栏=约束覆盖+依赖正确性（下降≤3pp）；
  四共同门=有害步骤率、长链子集（上四分位且≥20 步，冻结）、解析健康分项、异常项；成功=+5pp
  点估计且 CI 不跨 0 且护栏/门全过。测试集仅 3 独立单元→结论限初步对照证据，不得以步骤数
  夸大 n、不得拆散冻结分量扩测试集。放行清单 3/7；**训练仍未放行**。**阶段三第 4/6/7 项准备（2026-10-18）**：全量划分 V2
  （128,447 行/124,937 组件/组件级 80-10-10，seed 20261018，行级映射落盘；可复现脚本
  `scripts/b_track_full_corpus_split_v1.py`）；审计覆盖仅 221 行（97 组件），其中 A/C1/M
  合格=113 train/21 val/21 test。**阻塞：B/C 仅 113 训练行 vs A_full 102,731（0.11%），
  样本量混杂会压倒治理效应**。owner 选项：S1 分层扩审计（推荐）/S2 规则治理全量/
  S3 113 行管线烟测（不作能力结论）。ABC 样本清单 V1、评估实现冻结 V1（部分）已交付；
  第 4 项=划分完成/准入待策略，第 6 项=审计子集就绪/全量阻塞，第 7 项=部分。**owner 裁定
  （2026-10-18）：S3 烟测+S1 分层扩审计并行，S2 不启用，正式 B/C 训练集继续冻结，训练未
  放行**。S1 设计 V1：组件级分层（split×支持度×长度×任务类型），Phase-1 配额 7,562 组件
  （train 6,133/val 758/test 671），预计合格 ≈5,300 行（4,299/531/470）；长链≥20%（test
  ≥30%）、singleton+low≥40%、单任务类型≤20%。S3 烟测：数据完整性 5/5 PASS（split 原子性
  0 违反、审计映射、长链可定义、row_split 确定性 `f93e60dd…`、清单可追溯）；指标/评估器
  与模型级烟测 PENDING；仅工程验证、无能力结论。**S1 第一轮（2026-10-18）**：抽样清单 V1（7,562 组件，SHA
  `0d95ab17…`，缺口 0，seed 20261018）；校准波 12 组件。两项阻塞发现：①旗标定义过宽
  （UI 90.6%/重复 71.5%/间接 55.1%，须校准）；②**V2 划分存在同族跨 split 泄漏**——油膜
  48801(t)/74228(v)/50842(s)（J 最高 0.660）、森林退化 45165(s)/103943(v)，因 V2 只合并
  J≥0.75 或共享脚本。须先做全量任务族合并 pass → split V3，再重算配额 → 抽样清单 V2；
  本轮未估计合格率，训练继续冻结。
  ** → 划分冻结 → 三组小规模对照（A 原始序列/B 审核后序列/C 双层表示；判据=必要步骤
  召回、约束覆盖、依赖正确性、有害步骤、长链退化、多参考可用性）→ 独立评估确证后才扩全量。
  D1 契约 ADR 签核仍待 owner。活跃计划见 task_plan.md。

## ⭐ 当前主线：Planning Capability Audit（PCA）— 协议 v1 已冻结，Phase 1 进行中（2026-10-13）

- **owner 裁决（E2E A+B 双分支触发后）**：先冻结模型做独立规划能力验证——**不重训、不改
  21-family、不进 Stage 2**。目标 = 确定现有证据能支持什么结论，不是证明 Stage 1 成败。
- **设计**：60 任务（A 组 GEE held-out / B 组 QGIS 无算子 / C 组复杂组合，各 20）× 三臂
  （base / stage1 / stage1+tool）+ B′ 诊断臂（常设 6 任务，content_assessable_rate<0.70
  机械扩全）。格式健康（format_valid / content_assessable / hit_cap / termination_status）
  与规划质量分开报告；迁移读数 = 配对任务差 + task_type 分层 + 域内外分解（A vs B/C 原始
  均值差**不称迁移效应**）；C 臂结论限定"工具信息对计划质量的影响"；人工复核统计口径预注册
  （quadratic weighted κ，seed 20261013）。
- **权威文件**：`plan_pipeline_v1/planning_capability_audit_v1/PCA_PROTOCOL_V1_FROZEN.md`
  （owner 五处修订+七项 OQ 裁定已落；v0 留档）+ `PCA_PHASE1_WORKNOTES_v1.md`。commit d3623e6c。
- **状态**：B 组筛选完成（20 正选 + 10 备选；规则先于查看预测冻结，seed 20261013）。A 组
  隔离可到 `source_record_verified` 级（b1_gee_stage 的 source_row_id + 服务器实际训练文本
  池 planner_v2_train；注意 blueprint_v2_gold_v3 **无本地镜像**、F 盘迁移包不在本机——退路
  = 按协议 §2.3 标 text_dedup_only 披露）。下一步：B 组金标反推 → A 组构建 → C 组起草 →
  配对 → 去重账本 → owner 逐条审核。**金标获批前不运行正式 180 次生成。**

## (0b) RL 线立项（Route-2 Stage-3 位）：四阶段路线采纳，预注册 v0 DRAFT（2026-10-13）

- **owner 裁定（本会话）**：采纳四阶段 RL 路线（Phase 1 GRPO 工程 smoke → Phase 2 RAFT/DPO
  对照 → Phase 3 亲和采样+门控 GRPO → Phase 4 过程奖励/估计增强消融）；输出空间钉死
  **Blueprint v2（P0 规划器）**——QGIS Graph RL 维持 Stage-2 冻结；Phase-1 场地 = mdzhang
  共享（共租纪律）。本裁定将 10-12 的"RL 未授权"条款修订为"按下列预注册协议放行"。
- **权威文件**：`plan_pipeline_v1/rl_line/RL_LINE_PREREGISTRATION_V1_CANDIDATE.md`（V1
  CANDIDATE；v0 DRAFT 留档）。审查轮五项 OQ 全部落定：OQ-1 批准（24 任务×8 候选，seed
  20261013）；OQ-2 有条件（等权须先过正反例 pytest 电池 + S2 失败共现检验——修定义不调
  权重）；OQ-3 β=0.04 仅初值；OQ-4 S4 硬上限 ≤48 task-group updates + 六项预注册停止条件
  （KL 中止阈值与 β 分开：per-token KL>1.0 nat 连续 5 次 或 单步>10 nat）；OQ-5 Phase 2
  等 S2 吞吐外推报告后 owner 单独放行。r4 升级为 schema 级可执行定义（非空/seq 连续/
  rg↔stages 双向一致/hint 标签合法，per_feature 出现即非法），电池 P1/N1-N7/B1-B3 全绿
  才冻结奖励实现；绝对 repeat 量级只记录不评分（Contract E4 口径）。S2 验收拆双结论：
  工程验收 + 信号诊断（有效组<8/24 登记"信号覆盖有限"，不得解读为可扩量）。schema 权威 =
  `planner_design/PLANNER_V2_CONTRACT_FREEZE_v1.md`。既有钉子：奖励 v0 gold-free 四分量、
  不可核验维度 masked；rollout 解码 rep-pen 1.15（冻结评测仪器不变）；训练任务 ⊂
  planner_v2_train；E0 复用既有 P0 dev-1852 预测；S1 只读核验、冲突先停。PCA/多解线=
  外部输入，仅 Phase 3 依赖。
- **本地实现已交付（2026-10-13）**：`scripts/rl_reward_v1.py` + `tests/test_rl_reward_v1.py`
  ——电池 22/22 全绿（pytest 7/7）。真实数据核验发现**本地语料两种 rg 方言并存**：contract
  方言（stage_seq/family/repeat/iteration_hint，755 行非空 rg）得分 **755/755=1.0**；anchor
  方言（anchor_seq/pattern/repeat_count/order_preserved，1,078 行=P1/P2 实验谱系窗口折叠）
  不在 P0 输出空间内，奖励按设计不支援。P0=contract 方言目前是推断（planner_v2_train 建
  于合同冻结后、E3 消费 iteration_hint）→ **S1 新增方言指纹核验项**（planner_v2_train
  targets + 1 条 p0_dev_full_preds 样本）。total_iterations/stage_count 在 2,985 行本地
  目标中 0 出现→只记 field-presence 不判负。5+5 行 non_maximal_run 缺陷在 anchor 谱系
  （RL 范围外已登记）。权威：`rl_line/REWARD_BATTERY_REPORT_V1.json`（D1-D4 偏差已标记
  待 owner；空序列 C0=5/6 留 S2 判）。**owner 二轮裁定已落，实现升版 v1.1**（模块 SHA
  `5d5b6789f938980a…`）：D1 修订回归 V1 局部 mask（entry 缺陷只 mask 受影响分量；级联仅
  保留 r1a/r1b；统一规则=可判定违规(0)>不可判定(masked)>通过(1)）；D2 接受（不去
  fence、原样评分）；D3 升级（rg 键缺失→r4 masked，绝不静默通过）；D4 不接受无条件放行
  ——合同**无显式 minItems:1**，漏洞已量化（空=0.833/最小合法=1.0/解析失败=0.0），处置
  选项 a/b/c 见 `REWARD_BATTERY_REPORT_V1_1.json`，**S2 放行前 owner 定夺**。**三轮裁定
  D4=(b) 已落地，实现升版 v1.2**（模块 SHA `18c4e5a51d7f916b…`）：空序列=gateway 级退化，
  **正式奖励 R=0**（`empty_stages_gateway`）；gateway 默认 ON=正式 RL 奖励路径，OFF 仅
  诊断（保留旧行为）；composite 恒载 C0 诊断（空序列 5/6 照记）、r4 诊断保留；不扩大其他
  惩罚。owner 限定：工程裁定不改冻结合同（无 minItems），非空 stages 入合同须另走变更
  流程。电池 23/23（含 formal 期望）、pytest 12/12（含 on/off 回归矩阵）、contract
  755/755 formal 复验、D1/D3 回归不变；报告 `REWARD_BATTERY_REPORT_V1_2.json`（v1.1/v1
  留档）。**状态：v1.2 待 owner 差异与 SHA 审查 → S1（只读）→ S2 单独放行（当前不授权）。**
  **S1 前核验完成 + S1 已执行（10-13，mdzhang 只读）**：①差异审查=机械回归（v1.2 关
  gateway 重放 vs v1.1 记录输出）23 电池行+3 D4 场景逐位一致；②完整 SHA 入报告；③接口
  契约=训练器只读 `training_reward`（gateway 默认 ON）。**S1=PASS 附 2 开放项**：训练
  目标方言=contract 100% 实证（21,714/21,714；P0 输出 1,852 全扫 parse 84.23%、rg 全
  stage_seq——方言链路端到端证实）；训练 SHA 精确匹配 `443d5d31…`；词表差距（合同 30 vs
  实测 23，`vocab23_server_verified.json` SHA `8562982d…`，权威 30 名单不可得——不会误
  收、可能误拒，S2 r2 报告量化）**待 owner 裁定**；P0 有 1 类 OOV 发射（CLASSIFICATION_
  LOAD）+5 训练类从未发射（X4 型欠发射证据）。adapter 指纹已录。报告
  `S1_VERIFICATION_REPORT_V1.json`。**S2 未授权，等 owner 审 S1。**
  **Owner 四轮：S1 正式登记通过（开放项 1 选 (i)，vocab23 暂定）；S2 纯评分 dry run 已
  执行（无参数更新）**：24 任务×8 候选（seed 20261013、temp 1.0+rep-pen 1.15、prompt
  同 p0b2）；吞吐 **74.46 tok/s / 峰值 8.2GB**（Phase 2 成本门：GRPO 每步≈5min、100 步
  ≈8h）；**信号=管线通过但覆盖有限**——有效组 6/24=25%（<8/24 条款）、formal 均值
  0.9809 顶饱和、差异全为"一候选缺陷 vs 其余满分"、无分级质量信号→**仅结构奖励 v0 的
  GRPO 只能学回避稀有缺陷（X5/格式），对 X4 主瓶颈零信号**；分级信号须来自 r5（Phase 3，
  依赖多解判别线）。r2 屏蔽敏感性低（5/6 组保留）→vocab23 暂定充分；OOV 完整记录=
  TEMORAL_FILTER（拼写）+VECTOR_CLIP 各 1 次、OOV 率 1%。dry run 抓到并修复 AUX13 bug
  （seq-less stage KeyError；已加回归），修复后电池 24/24、pytest 13/13、模块 SHA
  `2ade2e79…`。报告 `s2_dryrun/S2_DRYRUN_REPORT_V1.md`（全标 provisional_vocab23）。
  **Phase 2 未放行，等 owner 审 S2 报告。**
  **Owner 五轮：S2 工程验证正式通过、信号覆盖有限入档、Phase 2 继续暂停（不租卡、不排
  训练）；下一优先级 = r5 可信度与离线判别验证。** 已交付：①`R5_DESIGN_V0.md`——需求
  槽位匹配机制（10 规则族+等价类+ABSTAIN 门+反偏差审计清单；验证门槛：误伤率≤10%/
  omission 检出≥80%/ABSTAIN 如实报；DRAFT 待 owner 审）；②`R5_VALIDATION_PACKET_V1.md`
  + `r5_validation_packet_v1.json`——6 组×4 候选=24 盲评项（材料=S2 真实候选，分层乱序
  剥离奖励信息，letter→cand 映射仅存 JSON）+ 构建脚本。**等 owner：审 r5 设计 + 盲评
  标注 → 实现 r5 v0 → 盲跑 → 一致性指标 → 离线审计（有效组覆盖提升+三项偏差审计）。**
  **Owner 六轮：R5 机制通过、触发规则有条件通过、直接接 RL 暂不通过；四项实现前修正
  （required/plausible/abstain 三态、等价类带适用条件、确定性弃权门、任务级+候选级
  统计）；标注协议冻结（4 主标签+两证据字段）；owner 完成 24 项盲评=全 omission（表示
  充分性保守口径，不能据此宣告 r5 通过）。** **r5 v0 已实现+盲跑+解盲**：
  `scripts/r5_requirement_parser_v0.py`（规则 v0.2：10 槽位族+条件等价+确定性弃权+
  全审计轨迹+vocab-gap 信号）。对照 owner 标签：候选级 22/24 一致（2 分歧=k=30160
  B/C，证据级一致）；任务级 5/6+1 证据级一致（k=17970 弃权+边界信号=F3 设计成功
  案例）；**误伤率不可测量**（0 正样本）；ABSTAIN 1/6。验证中修复 2 规则缺陷（study-
  area 伪 STATS、elevation 过宽）+1 语义修正（coarse≠complete）。报告
  `R5_V0_VALIDATION_REPORT_V1.md`。**下一步等 owner：①补正样本合成包第二轮盲评；
  ②离线审计；③裁定下一阶段（不自动授权 Phase 2/3）。**
  **Owner 七轮：R5 v0.2 一轮验证通过（22/24 正面但范围有限）；合成盲评+全量离线审计
  获准（不更新参数）；RL 接入不通过；scorable 三分类永不合并分子。两份报告已交付**：
  ①`R5_SYNTHETIC_BLIND_VALIDATION_REPORT_V1.md`——合成包 9 项（规则冻结 v0.3），自检
  9/9（零自伤/遗漏精确点名/A2 初版真缺 AGGREGATION 被自检驳回），**等 owner 盲评后解
  盲误伤率**；②`R5_S2_OFFLINE_AUDIT_REPORT_V1.md`——**scorable 分类 10/13/1（词表表达
  边界=主导问题）；r5 分裂 5 组 vs formal 6 组重叠仅 1（互补不叠加）；长度偏差无；模板
  偏差 0；family 偏差=MASKING 覆盖率≈1%——X4 云掩膜欠发射首次槽位级量化**。数据
  `s2_dryrun/R5_S2_OFFLINE_AUDIT_V1.json`。**Phase 2/3 继续冻结；等 owner 盲评合成包
  9 项 → 解盲误伤率 → 独立裁定。**
  **Owner 八轮盲评：误伤 0/3、omission 检出 3/3、弃权 2/9（S8 边界单列）——多解容忍
  红线首次测量为零；owner 的 complete_reasonable（S2/S3）= r5 的 complete_coarse_
  uncertain（同一保留不确定性被机械化）。八轮裁定：R5 v0.3 准入下一轮离线验证、不批
  Phase 2/3；下一步=标签/规则输出/192 候选逐项对齐+独立复核每个缺失槽位。已交付
  `R5_MISSING_SLOT_RECONCILIATION_REPORT_V1.md`**：358 缺失实例全对账（174/192 候选）；
  **INDEX 90 + MASK 87 = 占 49.4%**（X4 精确到槽位）；V1 无歧义 305 / V2 包裹歧义 53
  （S8 先例维持 missing 单列）；3 例深查全为真遗漏（含 1 例 V2 边界）；**三方独立方法
  互证**（能力定位 X4 47.6% / S2 审计 MASKING 1% / 本对账 INDEX+MASK 49.4%）；登记 1
  处构造标注错误（A4 预期 gap——错，T_CROP 无精度要求，r5 正确未触发）。**等 owner：
  抽查对账（V1 各槽位 2-3 例）→ V2 包裹歧义最终口径 → 下一轮裁定（真实任务可复现判
  别力+不系统性误伤=RL 奖励准入条件）。**
  **Owner 十轮：32 条裁定包双轨裁定完成并冻结**（`r5_adjudication_5516_6878_9210_9854_frozen_v1.json`）：
  r5 的 61 个 missing 标记去向=**missing_confirmed 39 / unresolved_wrapper 5 /
  requirement_uncertain 8 / not_required 8 / 改判 covered 1**。**v0.5 修改账本两项
  规则发现（待 owner 批准）**：L1=`\bareas?\b` 假需求（9210 "deforested **areas**"
  类名触发 → 8 候选误标；修=统计动词语境）；L2=INDEX 槽位定义边界（9854 MODIS 产品
  波段读取+缩放≠计算指数 → 8 候选 requirement_uncertain；**INDEX 定义须 owner 先固
  定**）；L3=记录格式增补 requirement_determination 字段。**汇总纪律**：39 不作统一
  遗漏率分子，三类边界全部单列。正向：wrapper 一致规则 5/5 落 unresolved；covered_
  coarse 语义经检验一致；61 标记 39 确认（64%），推翻的 16 个集中于两个可定位问题。
  报告 `R5_ADJUDICATION_FREEZE_REPORT_V1.md`。**等 owner：①固定 INDEX 定义；②批准
  v0.5 账本；③批准后 v0.5 重跑+反向对照+复验+遗漏率汇总 → 奖励准入评审。Phase 2/3
  冻结，RAFT/DPO/GRPO 不运行。**
  **Owner 十二轮：R5 v0.5.1 暂不准入正式训练奖励，批准"候选奖励影子评估"
  （Gate A-D，无参数更新）**；三源证据分别裁定不可互替（39/317 与 74/80 均
  不可折算为准确率/遗漏率）；GRPO 前三大风险登记（独立集误伤未量化/组内区
  分价值未明/过度生成诱导）。**执行状态**：**Gate A 完成——全部工件入 Git
  （commit 7ba729a3，61 文件，含独立集逐候选输出
  `independent_set_r5_outputs_v051.json`）**；Gate B 盲评包就绪
  （`GATE_B_INDEPENDENT_BLIND_PACKET_V1.md`，五标签槽位矩阵 + 候选级
  unnecessary_stages 字段）；**Gate C/D 预注册冻结**
  （`GATE_CD_PREREGISTRATION_V1.md`：CF3 冗余非上升≥95% 硬门槛；Gate D 四
  指标预注册，n<10 标 uncertain）。**等 owner：Gate B 盲评 80 候选 → Gate C
  构造 → Gate D 分析 → 影子结论（过→奖励合成设计；不过→R5 保持 X4 离线测量
  工具）。Phase 2/3 冻结；RAFT/DPO/GRPO 不运行。** **Gate B 已执行并解盲（234 槽位实例）**：TP 128 /
  **FP 4（2.74%≪10% 预注册红线）**/ FN **0** / TN 88 / unresolved_wrapper 14（单列）/
  假需求 0——十二轮风险#1 已量化且低位。4 个误伤全部集中于 k=25159 COMPOSITE 的
  wrapper 口径分歧（单一可修原因，非随机）；任务级偏差除 25159 外≤2 且全由 B* 解释；
  FN=0。无效阶段与冗余分记。**影子门位：A✅ B✅ C/D 待执行**；wrapper 口径修正入
  v0.6 账本待批（影子期间不改规则）。报告 `R5_GATE_B_UNBLIND_REPORT_V1.md`。 **Gates C+D 已执行（commit 2018cf08）**：Gate C 反事实 6/6×4 全过（CF3 硬
  门槛成立）；Gate D 三评分排序（10 独立任务）：**结构 formal 三项全不过**
  （区分 0/10、τ=−0.737 负对齐、2 组误奖、4 饱和——排序层面佐证 S2 结论）；
  **r5 覆盖全过**（7/10、τ=+0.796、0 误奖）；组合 λ=0.3/0.5 全过（0 饱和）。
  **影子结论：r5 与低 λ 组合具备进入奖励合成设计的证据；结构 formal 单独不行**。
  边界：n=10 小样本；标签为阶段族粒度；负 τ 机制待复核。报告
  `R5_SHADOW_EVALUATION_VERDICT_V1.md`。 **Owner 十三轮：奖励合成设计获批（仅设计/离线/预注册，无训练放行）；
  v0.6 正式规则变更暂缓（四案例证据表+COMPOSITE 判定条件+正反例回归对先补）；
  INDEX 公式级验证设计获批（L1/L2/L3 分层）；GRPO 另行授权；统计口径：
  39/61 非模型遗漏率、Gate C 小样本、Gate D 恰过线——**复现优先于调权**。
  已交付 `R5_REWARD_SYNTHESIS_DESIGN_V1.md`**：S0-S3 方案（R5-only/λ 网格含
  端点/结构硬约束与连续折算分开比/audit-only 对照）+ 复现优先（现有 10 任务
  降为校准集，新 24 任务盲评为评估集，评估集数字唯一进准入）；校准与防投机
  预注册（归一化/缺失分量/重复无效处置/uncertain+wrapper 入附录/三类投机
  监控/负 τ 独立调查）；INDEX L1/L2/L3（L2/L3 待表示层，金标先行构造）；
  GRPO 契约骨架另提；v0.6 补证清单。**执行：①新评估集采购+盲评 → ②S0-S3
  比较 → ③INDEX 金标 → ④准入评审+GRPO 契约。全程无参数更新无规则修改；
  Phase 2/3 冻结。 **Owner 十五~十六轮 + trainer v2 实现**：(1) λ 终选=S0 默认；(2) v0.6 部分实现
  （TERRAIN unscored，25159 暂缓）；(3) GRPO 冒烟契约草案提交审查。**trainer v2**
  （commit 34058b6a）：P0-P4 全修——真实路径骨架、数据隔离断言、优势公式精确、
  k=8 强制、KL 参照=P0 fmt 初始策略（adapter swap）、abstain 不入统计。故障注入
  8/8 + mock 干跑 24/24 全过。**Owner 十六轮契约终审：v2 FINAL CANDIDATE 产出**
  （commit c4ddbcbb）——§3.5 四点红线、§3.7 预注册规则表、三确认落地。
  Phase 2/3 冻结。 **评估集生成+评分+盲评包完成（commit 578c8439）**：192 从未训练候选
  （115.76 tok/s 同配置）；评分传参 bug 修正（预测文本误作任务解析→154 假弃权；
  修正后 abstain 32/incomplete 100/coarse 16/complete 17/unparseable 27）；规则
  口径缺失分布：MASK 44、TEMPORAL 38、SPATIAL 29、TERRAIN 23（新任务构成）、
  INDEX 16、COMPOSITE 14、CLASSIFY 9、STATS 7；4/24 组全弃权（F3 正确）。
  **盲评包 `eval_procurement/EVAL_SET_BLIND_PACKET_V1.md` 冻结待 owner 盲评**
  → 解盲 → S0-S3 一次性比较 → 奖励准入评审。Phase 2/3 冻结。** **Owner 十四轮：新评估集采购已执行**——源池=b1_gee_stage 128,447 本地权威
  备份减去 planner_v2_train 全部指令匹配（排除 33,371；训练文件无源 id 字段——指令
  匹配为唯一可行且充分的排除，已披露）= 94,445 从未训练候选 → 24 任务（8/8/8 长度
  带、22 类型、seed 20261013）；manifest SHA `4366a0c4…`、任务文件 SHA
  `b9983488…`。component_missing 预注册已入设计文档。**候选生成被 GPU 预检停止**
  （空闲 1,365 MiB<12GB；外部进程未触碰；监视器已挂）。Phase 2/3 冻结。
  **Owner 十一轮：INDEX 定义冻结（计算新指数；产品波段≠INDEX；9854=not_required）；
  v0.5 账本获批；重跑+独立复验批准。已执行 v0.5→v0.5.1 全链**：L1/L2/L3 落地并双次
  反向对照修复回归（9854 STATS 误删恢复 + 6878 derived-from 补检，均与 owner 裁定对
  齐）。**数字：323→317（全口径修正）；INDEX+MASK=153/317=48.3% 稳定；独立集（10 任
  务×8 候选，未参与规则调试）：任务级 10/10、候选级 74/80 需求覆盖缺失（规则口径未确
  认）**。流程教训：规则演进先 commit 再重跑（v0.4.1 实例级基线被覆盖）；建议 rl_line
  工件随下次 commit 入库。报告 `R5_V05_REVALIDATION_REPORT_V1.md`（奖励准入评审材料
  清单：三源并列互不佐证）。**Phase 2/3 冻结；等 owner：奖励准入裁定。**
  **Owner 九轮：①V1 抽查批准（未声称核验全部 358）；②V2 三态口径冻结
  （missing_confirmed/covered_confirmed/unresolved_wrapper；53 个 V2 实例保留原始
  missing 为历史、新统计标 unresolved_wrapper——防"表示能力不足误判为模型能力不足"）；
  ③358=规则输出规模≠人工确认错误；Phase 2/3 冻结。owner 亲查 15 实例（按 k 合并）：
  全部"确认要求；缺失待核实"；两风险=候选非独立（三口径同报）+槽位出现≠功能实现
  （三依据判定）。已交付裁定包 `r5_adjudication_packet_5516_6878_9210_9854_v1.jsonl`
  （32 条，5 个 V2 条目 r5_missing 与 owner 枚举一致）。**等 owner：逐条三态裁定 →
  反向对照 → 未参与调试任务复验 → 奖励准入评审（此前 RAFT/DPO/GRPO 不运行）。**
- **两条机制修正冻结为设计原则**（owner 方法评审）：(C1) GRPO 组内相对比较≠去偏——归一化只消
  加性共模偏移，与候选内容相关的评分偏差会被强化，去偏归奖励验证+置信门控；(C2) RAFT 不能
  创造验证器看不见的正确性——首轮限定可核验错误类。E7（Kalman/估计增强）启动条件 = 实测
  GRPO 优势估计不稳定。

## Route-2 v2 当前交接（历史状态，2026-10-04 快照；最新见上节与英文版）

**R3 诊断链完整闭环，架构方向确立，Planner-v2 Hint Contract 已 FREEZE（2026-10-04）**。链条：R3-A/B/TRUNC/CD-2 逐层排除并定位 **Task（散文摘要）与 Plan（阶段序列）的表示鸿沟** → R3-CD-3 信息阶梯（组件信号全强：family AUC 0.913/转移 0.904）→ R3-CD-4（确定性组装 0.60 > Direct 0.499；LLM 系统性欠发射）→ **R3-PLANNER-P0 可行性成功**（Task→Blueprint JSON，parse 100%，bag-F1 0.645 vs Direct 0.499）→ P1-B（预算提升仅改善小计数区，深尾冻结）→ 长度分桶画像（**深尾=表示问题：长 workflow = ~4.4 distinct family 重复至 95%**）→ **Blueprint v2（Ordered + Repetition-aware，语义粒度，pre-RLE 游程蓝本，无损 100%）** → v2 preflight（E1-E4 全过；可学习性判别 PASS：语义 stage AUC 0.922 ≈ v1 0.915，repetition-presence 0.940 全场最强）→ **6 批人工 hint 验证完成（396 条，各维度规则校准冻结）** → **PLANNER-V2 HINT CONTRACT FREEZE v1**（`planner_design/PLANNER_V2_CONTRACT_FREEZE_v1.md`）。

**Contract 数据定稿**：`blueprint_v2_gold_v3.jsonl`（37,044 行，SHA `621090bc…`）；hint 分布（组级）：unspecified 27,259 / generic_each 16,111 / per_year 9,917 / per_band 494 / per_class 28 / per_feature 0（diagnostic_only）。**ABSTAIN 语义**：insufficient evidence → no hint emitted（归一为 unspecified）。**GEE/Planner 层次边界**：execution-level iteration ≠ graph-level stage repetition。

**架构方向**：`Task → Structured Planner → Workflow Serializer → QGIS Grounding`（量级由 Grounding 解析，Planner 只管结构）。**待 owner：Planner-v2 SFT 放行**（smoke S1-S5 设计已备）；原冻结 Stage-1 v2_2 主线与 gate 不动；RL/Stage-2 冻结。

**R3 诊断链完整闭环，架构方向已确立（2026-10-03）**：从"Stage-1 W3 卡 0.50"出发，逐层排除 epoch 不足（R3-A）、Tier B 噪声（R3-B，A-only 反降 8pp）、截断（R3-B-1/TRUNC 审计）、chain_to_plan（ρ=0.857 忠实）、run-cap（RLE 循环折叠，零 family 损失）→ 定位 **Task（散文摘要）与 Plan（阶段序列）的表示鸿沟** → R3-CD-3 信息阶梯证明**组件层信号全强**（family AUC 0.913/转移 0.904/长度 F1 0.614）→ R3-CD-4 证明**确定性组装可解**（0.60 > Direct 0.499）→ **R3-PLANNER-P0 可行性实验成功**：Task→Blueprint JSON 的 QLoRA Planner（1.69M tokens，9h）达成 **parse 100% / family bag-F1 0.645**（vs Direct 0.499，+14.6pp）。

**架构方向（owner 冻结路线）**：`Task → Structured Planner → Workflow Serializer → QGIS Grounding`。序列：**P1 = count/length 专项监督**（缺口：M3 0.5027 / M4±1 0.5231，长度偏保守 5.98 vs 8.4）→ **P2 = 顺序敏感 Blueprint v2** → Stage-1 新正式候选 → Stage-2。措辞口径：P0 = "在当前冻结数据/bag 口径/训练预算下**强支持** Planner 假说"（非"决定性证明"）。**RL 冻结**，未来定位在结构化 Blueprint/QGIS Graph 规划优化层。原冻结 Stage-1 v2_2 主线与 gate 不动。

**关键产物**（全部入 git）：诊断链报告 `r3b0/r3b1/r3btrunc/r3cd_audit/`，Planner 设计与 P0 结果 `planner_design/`，blueprint 数据 `planner_gold_blueprints_v1.jsonl`（37,044 行）与 `planner_p0_train/eval.jsonl`（本地+服务器）。

**R3 诊断链进行中**：ep2 Gate-dev 仍 FAIL 但能力分化（W2 0.802 逼近门+No 类 0.994 过门 / W3 两轮持平 0.499 / W4 退化归零 / W1 confound 持续）→ owner 裁定走 R3-B。R3-B-0 数据诊断完成：Tier B 占训练 37.5% 且分支率 4 倍；**长 Plan 监督被构建期（1,766 行/2.5M tokens）+运行期双重截断**而 W3 探针偏长；Task↔Plan 文本级干净。报告 `r3b0_diagnosis/R3_B0_DIAGNOSIS_REPORT_v1.md`。

**R3-B Tier-A-only 消融已启动（owner 批准，严格单变量）**：数据 `stage1_train_v2_2A.jsonl`（SHA `8a9337ae…`，23,030 核心行，构建器字节级相同副本，审计全绿），PID 189898 于 10-01 19:46 干净起跑（smoke 检查点污染事故已发现+隔离+纠正），预计 **10-02 ~08:30 完成**，随后 gate-dev（label `stage1_tierA_ep1`）。判读树：W3>>0.499→数据构成主嫌疑；≈0.50→R3-C/D；<0.50→B 有正贡献。1,766 截断样本冻结（R3-B-TRUNC）。ep1/ep2 判定与全部数字见 `stage1_ep1_v1/`、`stage1_ep2_v1/`。

**Stage-1 ep1 Gate-dev = FAIL（4/4 未过门，2026-09-30）**：W1 0.0000（门0.20）/ W2 0.3052+No类0.6185（门0.85+0.70）/ W3 as-is 0.4829（门0.60）/ W4 0.0346（门0.20）。学习真实发生（Base 全 0 → W2 0.305/W3 0.483/W4 0.035）但低于注册下限，且 W2/W3 低于平凡基线——Gate 判别力成立、正确拒绝。主瓶颈=格式服从（invalid 69.2%，Base 86.4%）。判定报告：`stage1_ep1_v1/STAGE1_EP1_GATE_DEV_VERDICT_v1.md`。

**owner 裁定（2026-09-30）：FAIL 保持有效；执行 R3-A 同协议续训 1 epoch（=训练充分性诊断）**。W1 登记 contract-format confound（Gate 格式未入训练目标，parse 2.5% vs Base≈9%）；W2 表述收紧为"判别方向变化，非能力形成"。R3 顺序 A→B(Tier A-only)→C(Contract/Schema)→D(转换损失)。**R3-A 已启动**（同 yaml 同 out-dir，resume 自 step 1772；PID 156537，13:41 起，预计 ~20h → 10-01 上午完成）；ep2 完成后 gate-dev 以新 label `stage1_ep2`/新 out-dir 评测。**Teacher Plan、B2、Stage-2、RL 继续冻结。**

**Base zero-shot test 完成（2026-09-29 03:44，租卡机）**：三 SHA 对账全绿（probe `866c3762…` / config `6355bab4…` / evaluator v1.3.1），W1-W4 全 0.000（invalid 2,752/3,256 = 84.5%，零 OOM/超时/批减半）。**Base 零样本 = 地板在 dev+test 双 split 上确立**，Δ 条件无判别力（R2 共识）获 test 侧确证。R2 阈值评审一页表已组装：`route2_p0_contract/ROUTE2_V2_R2_THRESHOLD_REVIEW_INPUTS_v1.md`——**当前唯一等待事件 = owner 逐项裁定 W1-W4 绝对下限**（W2 双条件门 / W3 rewrite 仅诊断 / W1-W4 可达性推理，数值只由 owner 定）。裁定后：注册 `ROUTE2_V2_STAGE1_THRESHOLDS_v1.md` → owner 显式放行 → Stage-1 训练。

**计算服务器 mdzhang (10.191.2.38) 已于 2026-09-27 关机**（owner "方案 B" 裁定：先保全、保全完立即关机，不等在跑的 Base zero-shot test 半边）。关机前已完成全部延续性资产的 SHA 校验备份（288 tar 条目 / 248 文件，双端 SHA256 全部一致）：压缩包 `../server_backup_mdzhang_20260927.tar.gz`（sha256 6542ac1f5bee451a…）+ 解包目录 + `BACKUP_README.md`（范围、显式不拉清单、复用说明）。已保全：`stage1_train_v2_2.jsonl`（150MB 冻结 Stage-1 训练数据）、`b1_gee_stage_train.jsonl`（264MB，本地原本没有）、`plan_pool_tiered_v2.jsonl`（234MB 冻结 B2 池）、gate-v3 探针 + `gate_evaluator_v1` + plan_pipeline_v1 全套、`v2a_A_train/dev/test.jsonl`（QGIS 1,334/120/111 SFT 文件）、**Phase R qgis_sft_ep1/2/3 checkpoint**（evaluator-repair rerun 可直接复用、免重训）、route2_C0 checkpoint（可做悬置的 test-111 终评）、configs、Qwen3.5-9B-Base config/tokenizer 指纹（权重未拉——公开模型，租卡机器上重新下载）。

**Base zero-shot dev 结果（2026-09-27，evaluator v1.3.1，零 OOM/零超时/零批减半）**：W1/W2/W3(as-is,改写)/W4 全部 0.0；invalid 2,795/3,236（86.4%）。未训练 Base 就在地板上——绝对下限形同虚设，W1-W4 判读重心完全落在预注册的 Δ_i（零样本+提升量）条件上。正式判读归 owner。dev 工件已由持有线提交 git（0a41a6d），备份内有镜像。

**Base zero-shot test 半边：中途中止（owner 裁定），改在租用 GPU 上重跑**，三冻结 SHA 不变：evaluator v1.3.1 / 探针 dev `c3d95f67…`、test `866c3762…` / 推理配置 `6355bab4…`。运行中"数小时零落盘零日志"是评估器设计使然（报告只在全部探针完成后一次性写出，持有线已确认）——今后不要再用日志静默判断卡死。

Phase R 维持 **CLOSED-FAIL（Infrastructure/evaluator failure），严格非 Stage-2 FAIL**：`docs/reports/transfer_phase2/phase_r/phase_r_report.md`。

**下一步（全部等租用 GPU + owner 放行）**：① 租卡、恢复环境、重下 Qwen3.5-9B-Base → ② Base zero-shot gate-test 复跑（dev 节奏约 11h，--batch-size 1）→ ③ 预注册 W1-W4 绝对下限 + Δ_i → ④ Stage-1 开训须 owner 显式放行令。持有线已在关机前获通知并确认；其 poweroff watcher 为 fail-safe，未阻碍手动关机。

Stage-1 协议与 B2 门禁保持冻结。
**租卡机产物回迁规则**（2026-09-30 立，全文见 `route2_p0_contract/RENTED_BOX_ARTIFACT_POLICY_v1.md`）：租用服务器为临时资源，其上一切实验产物（报告/账本/adapter/日志）须先入桌面仓库再于 mdzhang 复电后同步——Stage-1 adapter 与全量训练账本已按此入库（`stage1_run_v1/`）。
；Stage-2 预注册见 `docs/plans/transfer_phase2_stage2_prereg_v1.md`。活跃路线看 `docs/plans/transfer_phase2_roadmap.md` 和 `route2_p0_contract/`。

本文是日常接手入口；活跃计划看 `task_plan.md`，详细历史证据看
`docs/PROJECT_CONTEXT.zh-CN.md`。
本文是日常接手入口；活跃计划看 `task_plan.md`，详细历史证据看
`docs/PROJECT_CONTEXT.zh-CN.md`。

## ⑦ Stage-1 训练协议冻结（2026-09-24，owner 裁定，v1）

单流混合（**token 比例**）：Task→Plan 60% / Dependency-Completion 10% /
Reconstruction 10% / W4 20%（≤25% 顶）/**Chain LM 0%**（A1 归因清洁）。
配方与 P0 同构（QLoRA r16α32 NF4 / 1e-4 cosine / batch 32 / max_len
1024）。**截断修正**：Task 完整保护，超长截 Plan 尾，审计全记。Gate
两级（dev 选点 / test 判定）+ 双条件阈值（绝对下限 AND 零样本+Δ，训练
前用冻结 Base 预注册）+ **硬前置**（全单项过门才比加权分：W1 .20/W2
.25/W3 .40/W4 .15——模板记忆无法靠平均晋级）。**W1 修正**：已知操作+
新上下文/低频/词面变化（不用完全未见概念）；组合泛化主力 = W3 新操作
组合。1 epoch 先行，FAIL 同协议续训。**成功标准 = 能力门通过，非 loss**。
①→⑦ 全冻结。⑥三件 CPU 工程产物与 Stage-1 预检（数据 v2_2 + Gate-v3
探针 + 评分器）已全部完成；开训只差 GPU 窗口与 owner 放行令。详见
`route2_p0_contract/ROUTE2_V2_STAGE1_PROTOCOL_v1.md`。

## ⑥ B2 数据构造 v0（2026-09-24，owner 裁定）

**工程顺序（一票否决）**：⑥-0 Operator Capability Profile → ⑥-1
Audit-A（重定义为 Information Discriminability Test——测接口是否客观
含区分信息，非测模型；148 映射组 → Grounding Discriminator Matrix；
反作弊：gold 反推 Plan 不得天然 PASS）→ ⑥-2 chain→Plan → ⑥-3 Retention
Audit → ⑥-4 配 Plan → ⑥-5 B2 包。**Plan 主来源 = Frozen Stage-1
Model(QGIS Task) 的 Teacher Plan**；gold 反推线只做 de-grounded 诊断/
上界（剥离 provider/算法 ID/QGIS 参数名 + Leakage Audit：能否从 Plan
恢复 operator ID），两线绝对不混；gold 禁止用于生成/修正/选择/重写。
**B2 双 family**：G1 Operation grounding（step+context→operator，
grounding_unit=operation）/ G2 Workflow grounding（Task+Plan→Graph，
unit=workflow），unit 标签显式入数据。三 split 同一接口路径
（1334/120/111 全由同一冻结 Stage-1 生成 Plan，test 加 prediction
lock）。**关键排序约束：Stage-1 训练+能力门 PASS 前不得批量蒸馏
Plan**（Teacher Plan 质量差是实验设计的一部分）。三件产物+Audit-A
PASS 后才进⑦。详见
`route2_p0_contract/ROUTE2_V2_B2_DATA_CONSTRUCTION_v1.md`。

## ⑤ Stage-2 Grounding 信息需求 v0（2026-09-24，owner 裁定）

Stage 2 = Task + Plan + QGIS 知识（经后训练入参数，非输入文本）→
QGIS Graph。**G1-G4 四类 grounding 信息**：I/O 约束 / 实现判别约束
（Oracle 真缺口：raster vs vector、mask 类型、CRS 行为…）/ 参数语义
（数据须含参数 schema↔任务约束对应）/ Graph realization（端口/fan-in-
out——Stage1 线性 Stage2 DAG 分工落地处）。**三审计 benchmark 化**：
Audit-A 判别性（148 映射组内选实现，**不过不训 B2**）/ Audit-B 信息
充分性（逐字段 ablation 找 minimal sufficient interface）/ Audit-C 图
realization（算子/连接/端口/扇入出分项）。三冻结：GEE API 禁入
Stage 2；QGIS 知识不塞进 Plan（What should happen / How to implement
分界）；QGIS plan 来源维持 open dependency（唯一约束：满足④合同+过
审计）。**新资产立项：QGIS Operator Capability Profile（309 算子，
建自 Neo4j QGIS_Operator 1291 节点 + processing 注册表，Stage-2 知识
底座）**。详见
`route2_p0_contract/ROUTE2_V2_STAGE2_GROUNDING_REQUIREMENTS_v1.md`。
执行顺序：①-⑤ ✅ → **⑥B2 数据（悬题：1,334 条配 Plan 防循环泄漏）**
→ ⑦训练协议。

## ④ Stage-1 接口信息合同 v0（2026-09-24，owner 裁定）

只冻结**信息合同**不冻 schema：Plan = 五信息层（P1 开放词表操作意图、
P2 typed I/O【KG 1425 节点 hasInput/hasOutput 为源——37 类的真正缺陷是
缺 typed context，非类别数】、P3 顺序与 P4 依赖**分字段**【adjacency≠
dependency，提不到标 unknown 禁伪造】、P5 步骤约束【不复制任务文本】）。
GEE provenance 双层隔离：API/AST/canonical chain 留训练审计侧，
**不暴露给 Stage 2**（防退化为 API 翻译）。禁止作唯一接口：37 类 ID/
纯 token 序列/GEE API chain；定位 = 比 37 类细、比 GEE API 平台中立。
**反 37 类瓶颈三类正式审计**（④定义⑤benchmark 化）：Plan Collision /
Information Retention / Grounding Discriminability。不冻结：schema、
序列化、Plan 语言形态、W1-W4 权重、QGIS plan 获取方式（open dependency）。
边界：④=保留什么 ✅；**⑤=还需要什么（下一步）**。详见
`route2_p0_contract/ROUTE2_V2_STAGE1_INTERFACE_CONTRACT_v1.md`。

## ③ 训练目标与接口 v0 决策（2026-09-24，owner 裁定）

**Task → Workflow Plan 为 Stage-1 核心目标**（W3 载体）；辅助目标从同一
plan 派生（Dependency/Completion/Reconstruction，W4 ≤25% token）；原始
chain LM 出局（③-C，A1 反例）；**Stage-2 接口 = Task + Workflow Plan →
QGIS Grounding**（Task 保留原则——Oracle 证明任务文本算子线索反多于
gold 语义链，Plan 的职责是把 Task 隐含的结构显式化而非取代 Task）。
Plan 表示只冻结信息约束（操作级/有序/数据流/I-O 类型/依赖/子目标对应），
**不冻结 schema、不建 37 类 ontology、不嵌 QGIS API**。训练组织 =
planning-centered multi-task（W1/W2 组织进主任务、W4 受控辅助）。A1
差异化正式回答：学习压力从 sequence continuation 转向 task-conditioned
workflow construction + 显式结构约束。能力门 answer-echo 反制：改写
Task A' → Workflow A + 新操作组合验收。详见
`route2_p0_contract/ROUTE2_V2_STAGE1_OBJECTIVE_INTERFACE_v1.md`。
执行顺序：③ ✅（v0）→ **④接口具体化（字段/可推导性/反瓶颈，下一步）**
→ ⑤Stage-2 信息需求 → ⑥B2 数据 → ⑦训练协议。

## Stage-1 能力定义已冻结（2026-09-24，owner 裁定）

**W1-W4 冻结、W5 下放**：W1 算子行为知识（基础）/ W2 数据流组合律（基础）/
W3 目标分解规划（**核心**，能力门须防背模板——W1/W2 分项交叉印证）/
W4 结构判别与修复（辅助，**token budget ≤25%、默认 ~20%**）。**W5 分支
组合下放 Stage 2**——正式边界：Stage 1 = Sequential/Linear Workflow
Reasoning，Stage 2 = QGIS-specific DAG Grounding（论文须明示）。术语
冻结：废弃"Stage 1 输出 Semantic Workflow"，改为"Stage 1 形成并显式
暴露 Workflow Reasoning representation/plan"——**只冻结能力，不冻结
表示**。继承边界：A1（须有结构学习压力+回答"为何 A1 不会"）、
B1/Oracle（禁降信息抽象）、非 API 记忆（held-out 词汇+重组验收）。
详见 `route2_p0_contract/ROUTE2_V2_STAGE1_CAPABILITY_v1.md`。
执行顺序：①架构 ✅ → ②能力定义 ✅ → **③Stage-1 输出/接口（下一步）**
→ ④Stage-2 信息需求 → ⑤B2 数据 → ⑥训练协议。

## Route-2 v2 架构已定：两阶段能力形成训练（2026-09-23，owner 裁定）

**当前主线最高决策**：新 Route-2 = 两阶段能力形成（Stage 1 GEE Workflow
Learning → 独立能力验收门 → Stage 2 QGIS Grounding Post-training；
Stage 3 RL 留位不启动）。B1 形式两段实质单段（第二段直接训 Task→QGIS，
无能力接口）是本决策直接动因；Oracle 判决（37 类语义链→QGIS 全贴地）
是证据基础。关键认识：**Stage-1 能力 ≠ 37 类 Semantic Workflow**——
Stage 1 应从原始 GEE workflow（gee_canonical_chain）自行形成 reasoning。
执行顺序：①架构（本条）→ ②Stage 1 输出/接口+能力门设计（**当前推进
点**）→ ③Stage 2 信息需求 → ④B2 数据 → ⑤训练协议。详见
`route2_p0_contract/ROUTE2_V2_ARCHITECTURE_v1.md`。

## Route-2 四块合璧：语义→算子接口断裂（2026-09-17 → 09-23）

dev + test + error audit + Oracle grounding 四块齐：

```
              dev opF1   test opF1   Oracle opF1   Oracle EM
C0 纯QGIS      0.5611     0.5059      0.0771         0.000
B1 语义→QGIS   0.5541     0.4788      0.0963         0.000
A1 DAPT→QGIS   0.5510     0.4584      0.1165         0.000
```

**Oracle 判决（情况 B）**：把 gold 语义工作流（B1 词表、148 算子映射、
21 类在用）直接喂给三臂，**全部贴地**（opF1 0.077-0.117，EM 恰好全零）——
包括在语义空间上训练过的 B1（stage-1 loss 1.020→0.336 学会了
Task→语义）。**37 类语义抽象不足以决定 QGIS 算子选择：任务文本
（0.479）携带的算子线索反而多于 gold 语义链（0.096）**。语义抽象在
"落地图"这一步丢失了必要信息——粒度断层获得直接实验支持。

**error audit 要点**：ops_mixed（部分算子对）占 55-58% 为主瓶颈；
B1 linkF1 优势在 parse-ok 子集存活（0.4917 vs C0 0.4476）但"拓扑全对"
行仅 8 vs C0 7（分布效应，非群体现象）；三臂每行欠生成 ~2.9 算子。

**机制终定位**：H1 失败点在 semantic→operator grounding 这一环，而非
Task→workflow 学习（B1 学会了）也非 QGIS grounding 本身（C0 有 0.51）。
被训过两个方向（Task→语义、Task→QGIS）的模型不能零样本组合出第三
个方向（语义→QGIS）。

**B2 分支已由 owner 预注册且命中**：oracle 低 → 专门的 semantic→QGIS
训练（Semantic Operation→Operator 与 Semantic Workflow→Graph 两个方向），
而非继续普通 QGIS SFT。B2 设计待 owner 批准后开。
产物：`test111_final_v1/`（RESULTS_LOCK_v1、ORACLE_RESULTS_LOCK_v1、
error_audit_v1、oracle_semantic_input_v1、三臂 predictions+SHA）。
audit/oracle 脚本：`scripts/audit_route2_test111_errors_v1.py`、
`scripts/build_route2_semantic_oracle_v1.py`（29178fd）。

test 明细（dev-120 选 checkpoint；test-111 一次性，SHA 已锁）：

```
           dev opF1 (best)   test opF1  test EM   test linkF1  test parse失败
C0 纯QGIS       0.5611 ep20   0.5059     0.1351     0.4355       2.7%
B1 语义→QGIS    0.5541 ep18   0.4788     0.1441     0.4607       6.3%
A1 DAPT→QGIS    0.5510 ep15   0.4584     0.1081     0.3794       9.0%
```

补充判读：parse 失败单调 C0<B1<A1 在 dev/test 双复现；dev 差异措辞 =
与 epoch 波动量级相当（无显著性检验）；GEE 两阶段拟合均成功但迁移
未随拟合而来。final-100/refusal-12（冻结 benchmark scorer）属 peer
Gate-2 线。事故史：服务器三天三重启（B1 断点续训零损失恢复实证）；
test 评测 B1 首跑瞬时 CUBLAS 错、独占重跑通过；autoboot 用毕拆除。
账本：run_ledger{,_A1,_B1}.json + RESULTS_LOCK_v1.json
（dd64280/d7b3180/8d785df/c77989a）。Gate-2 评测窗已开放。

## M1-R2 评测完成：结构性塌缩修复、任务映射未解（2026-09-16，Phase 2 收官）

M1 增强线（decoder backbone domain pretraining）全链闭环：DAPT 493.4M byte-tokens（loss 5.56→0.6257）→ migrate 审计 8/8 → SFT（R1 协议逐行不变，唯一变量 = decoder 骨干初始化，ckpt `22a77f77…`）→ 冻结协议评测（R4 纪律：prediction hash 先于 gold 锁定；M3 块重评分精确复现锁定值 0.1605）。

**R1 → R2（final-100）**：空图 88%→**20%**；bridge 丢弃 83.8%→43.9%；L3 token 154→528；Define Projection 首 token 99%→0%（新吸引子 AddSpatialIndex 70/LakeInundation 26/Simplify 4）；链长 1.5→5.3；**operator F1 0.0047→0.0857（×18）**。**近分布基本持平**（val Top1 14.87→15.24%、诊断 F1 0.173→0.187）；edge F1 仍 0、harmful extra 0.90（fixgeometries 88/100"万能开头"新偏置）。**结论（owner 定稿，M1 线收束于 5e3f818）**：R2 提升了"生成什么样的序列"的结构能力，但没有显著提升"根据任务语义生成哪一条具体工作流"的条件映射能力（层次 A 生成器状态被 DAPT 修复；层次 B 条件映射未动，与 Phase 0-B 归因闭环）。**Phase 3 裁决：R3/R4 不开**——三路线一致信号表明模型侧调整不改善 task→L3 映射，"任务语义—算子映射监督不足"为值得优先检验的主要候选瓶颈（严格措辞：非"已证明来自数据"）。**下一阶段：paper_v2 数据侧**（25.7 万描述库意图重写），R1/R2/M2/M3 为前置基线。评测环境事故 2 起已独立归档（dev-20 首跑 legacy mapping 泄漏无效；val 诊断 taxonomy 路径崩——M1 推理三环境变量必须内嵌启动入口）。证据：`docs/reports/m1_r2_eval_v1/`、`docs/reports/qgis_planner_eval_v1/SCORES_R2_v1.json` + `predictions_r2/`。

## 外部数据与评测资源全景调研（2026-09-16 → 09-18，paper_v2 前置）

调研系列三份报告（全部只读，未消费外部数据）：v1 GIS 专用数据 `docs/reports/external_gis_training_data_survey_v1.md`；v2 通用工具链文献与方法补遗 `docs/reports/external_gis_training_data_survey_v2.md`；**综合报告（新增评测对比维度）`docs/reports/qgis_data_eval_landscape_v1.md`**。

核心结论：①数据——外部不存在"NL 意图→QGIS 算子 DAG"训练集；主料仍是内部 25.7 万描述库 + GEE 44,220 行转化资产；外部三源（GeoAnalystBench Apache-2.0 / AutoGEEval-plus 2,612 用例无 license / GISAgentBench 349 任务仓库未公开）≈1,800 条意图式样本，只作 OOD 评测+种子+引用；GEE↔QGIS crosswalk 外部不存在，内部 KG 是唯一实现（论文贡献点）。②评测——benchmark v0.2.1 生态位独特（唯一评"结构化算子 DAG"而非代码、唯一 refusal diagnostic + unsafe-planning、唯一 prediction-lock + 冻结 scorer、拓扑分级 gold）；与外部标杆差距 = 执行级 GT（GISAgentBench）、规模（AutoGEEval++ 千级 vs 100）、动态/多轮（BFCL V4、GeoAgentBench 沙盒）；v0.3 四候选（执行增强层/规模扩充/拓扑细分/refusal 扩容）全部未批准。③对齐诊断——benchmark 已是意图式，错位在训练侧（GEE 100% answer-echo）：修数据不修评测；评测侧短板 = 规模与执行验证。重写管线方法锚点：back-instruct（TaskBench）/ WorkflowLLM 三阶段 / APIGen 三段验证。主线现状：M1 线收束于 5e3f818（R2 ×18 但条件映射未解）；M2 三臂收束（C0 最优 0.2236）；M3 收束于 P2-T1；下一阶段 = paper_v2 数据侧四臂重写。

## M1 增强消融路线立项 + domain_corpus_v1 spec 草案（2026-09-11）

benchmark v0.2.1 冻结（6006e49）已合并 main（c515c77/5647636）；M1/M3 推理配置冻结（45f5abb，`docs/reports/qgis_planner_eval_v1/INFERENCE_CONFIG_FREEZE_v1.json`）并完成 final-100 预测：M1 88 空图、100/100 以 L3_01_10_02 Define Projection 开头（OOD 塌缩，val Top1 13.75%）；M3 输出跟随任务文本（74% token 覆盖内）。M1-R1 冻结为 scratch baseline（准确构成 = 冻结的通用英文 BERT + 从零 decoder，非纯 random init），不重训、不翻案。据此立项 M1 增强消融（本轮唯一新增 M1-R2 = decoder-only CLM-DAPT，BERT encoder 保持 R1 冻结配置；R3=BERT MLM、R4=+TAPT 均为 Phase 3 候选，视 R2 结果再开）与 domain_corpus_v1（规则 v1 已冻结 `docs/plans/domain_corpus_v1_spec.md`，owner 三项决策 2026-09-11：外部 QGIS/GDAL/OGC 文档本轮不纳入；D1-D5 语料池、四层泄漏隔离含 6-gram=0 断言、一个 manifest 多 recipe 的 M1/M2 分离、D5 四项审计字段）。执行顺序锁定：Phase 0 前置确认（任务文本语言分布矩阵、task_type oracle vs Unknown 推理消融）→ Phase 1 corpus 构建 → Phase 2 M1-R2 → Phase 3 视结果定 R3/R4/停止。详见 `task_plan.md` "模型实验" 板块。

**Phase 0-A 已完成**（2026-09-11，`docs/reports/m1_phase0_precheck_a_language_v1/`）：benchmark 132 条任务全英文、bert [UNK]=0——推理侧无语言混杂，M1 塌缩不能归因于输入语言；但 paper train 的 QGIS 子集 616 行中 81.7% 中文/混合、69.2% 对 M1 encoder ≥50% [UNK]，M1 有效可读 QGIS 监督仅 ~190 行（M3 可读全部 8,817 行）——训练侧语言不对称列入 M1 vs M3 混杂清单，M1-R2 DAPT 只能消费英文池。

**Phase 0-B 已完成**（2026-09-14，`docs/reports/m1_phase0_precheck_b_tasktype_v1/`）：2×2 消融（task_type {oracle, Unknown} × 长度 {按类型, 固定 8}），同 checkpoint（SHA=冻结记录）、同 49 行 val、同进程——**task_type OOD 是 M1 塌缩的主要触发/放大因素（非唯一原因）**：仅把 task_type 换成 Unknown，P/R 即从 0.13/0.20 塌到 0.00/0.00，首 token 多样性 26→5，吸引子出现（L3_04_05_09 + Define Projection 24.5%），GEE/QGIS 行双归零；但 Oracle 下 exact 仍 0/49、SetF1 仅 0.148——基础能力本来就低。长度策略二阶；空预测率全条件 0/49（benchmark 88/100 空图 = bridge 丢弃，非空链；token-level 与 graph-level empty 自此分开表述）。task_type 是 M1 特有、已量化的 handicap（ΔP −0.13/ΔR −0.20；M3 不消费 task_type）。

**Phase 0 收官（2026-09-14，owner 裁定不再追加 A/B）**。四层归因定稿：M1-R1 benchmark collapse = ① task_type conditioning failure（主要触发/放大因素）+ ② benchmark 文本 OOD（放大因素，非必要条件）+ ③ domain/GIS prior 不足（R2 待验证）+ ④ QGIS 中文监督覆盖不足（训练侧结构性限制）。R2 目标：测 decoder 骨干领域预训练的独立泛化贡献（唯一主动变量 = decoder 初始化）。

**Phase 1 domain_corpus_v1 已完成并冻结（2026-09-14）**：D3 代码池 43,809 docs/174.7M WP（47,852 权威源清洗后保留 91.6%）+ D4 英文文本 6.6M WP + D1 锚点；断言电池全过。recipe 冻结：D3 60% 降采样 + D4 4× 过采样 + D1 1×，**byte-level training budget 487.5M byte-tokens**（exposure D3 80.15%/D4 19.85%）。M1-R2 §10 implementation contract 已冻结（decoder backbone domain pretraining：byte-level 临时词表 + 哑 memory + task_type=Unknown 的 DAPT → SFT 时 132 L3 词表重初始化、body/FiLM carry over、R1 协议完全不变）。构建中发现并修复泄漏集 GPL 样板误杀（paper_v1 test 1 行 task_text 本身是 GPL 许可证头——数据质量注记）。证据：`docs/reports/domain_corpus_v1/`。**下一步：Phase 2 M1-R2 DAPT 实现与训练**。




## M3-P0 与 M3-P1 完成：SFT 完成 L3 输出空间对齐（2026-09-08）

M3-P0（post-trained Qwen3.5-9B 零样本，冻结协议，val 49）：0/49 精确、code P/R
0/0、长度误差 −4.0——模型用流畅英文步骤回答 GEE 任务（语义方向正确，如
"filterDate → select → mean"）但从不输出 L3 码。干净的 Qwen 先验下限。
M3-P1（同一模型，朴素 QLoRA/SFT——NF4、r16 q/k/v/o、加权 CE、1 epoch ×
8,817 行 paper_v1 train、83 分钟、14.35GB）：冻结协议首轮读数 0/49 但 recall
0.885、长度误差 +3.71，诊断为截断伪影：EOS 感知解码下预测以精确 gold 链开头的
比例 **42/49（85.7%）**、首块完全一致 **41/49（83.7%）**、EOS 生成 46/49。
8 个失败的分类：6 个首算子/顺序错误，2 个无 EOS 重复。下一轮已知修复（一行、
无需重训）：generate 传 eos_token_id/stop 字符串。第一轮 Q2 已回答：朴素任务
SFT 把模型的 GIS 语义先验映射到 L3 输出空间；0→41/49 的增量可单独归因于 SFT
（同模型、同 prompt、同解码）。两个实验均已注册进 append-only 实验账本
（M3-P0-v1、M3-P1-v1 含 checkpoint SHA、数据版本、参数、GPU 时间）。证据：
`docs/reports/m3_p1_sft_v1/m3_p1_report_v1.md`。

## Qwen3.5-9B-Base E3 smoke + E4 overfit 门禁：全部通过（2026-09-08）

阶梯地基完成。隔离 `qwen35` 环境（torch 2.5.1+cu121 / transformers 5.16.1 含
qwen3_5 模型类与纯 torch GatedDeltaNet 回退 / peft 0.20.0 / bnb 0.50.2；2.2.2
旧环境未动）。两个 Qwen3.5-9B 变体均以 HF 原始 safetensors 下载（各 19.3GB，
hf-mirror，04:57 完成）；本地 ollama GGUF 仅保留推理用途。**E3 smoke 9/9**
（Base）：NF4 加载 7.19GB、forward/backward/累积有限、LoRA 存取字节一致（32 个
lora_A）、生成正常、峰值 18.13/23GB。**E4 100 条 overfit 门禁通过**：paper_v1
train 100 行（GEE 60 + QGIS 40）、40 epoch、首 loss 0.788 → 0.0000、训练内探针
精确 L3 链复现 10/10、28.6 分钟、峰值 12.74GB——全栈可学习任务格式已证实。下一步：
⑤ M3-P0 零样本（post-trained Qwen3.5-9B）、⑥ M3-P1、⑦ M1 受控重跑。证据：
`docs/reports/qwen35_base_a10_smoke_v1/`。
## 三条模型实验路线已定死（2026-09-07）

用户更正了 Qwen3.5-9B 的判断：架构本身可微调——问题只在于本地 ollama GGUF（Q4_K 量化）不适合
Transformers + BitsAndBytes + PEFT/QLoRA 流程。正确路径是下载 HF 原始 safetensors 权重：
`Qwen/Qwen3.5-9B-Base`（已核验，4 分片 safetensors，`Qwen3_5ForConditionalGeneration`）
用于 M2/M2-C0，`Qwen/Qwen3.5-9B`（官方 post-trained 版）用于 M3/M3-P0，训练时由
BitsAndBytes 以 NF4 加载、PEFT 挂 LoRA。路线定义已固定在 `task_plan.md`
"Model-experiment route definitions"：M1 = 自主规划模型路线（保留 V4.x，数据治理 → SFT →
AR → 可选 DPO）；M2 = Base 模型领域专业化路线（Base → DAPT → 任务 SFT → 可选过程/
偏好阶段）；M3 = 成熟 post-trained 模型直接任务适配（Qwen3.5-9B → 仅 QLoRA/SFT，不做
DAPT）。三条路线共享同一输出边界（L3 语义工作流 → 统一 L3→QGIS 落地）以保证公平比较。
M2-C0 是 M2 内部无 DAPT 对照；M3-P0 是 M3 零样本下限。待定决策：M2 的哪些阶段
（DAPT→SFT→过程监督→偏好/工具反馈）属于主实验、哪些降级为后续实验。
## A10 QLoRA smoke 9/9 全过；Qwen3.5-9B 不能作基座（2026-09-07）

阶段 ③ 完成。**关键发现：本地 `qwen3.5:9b` ollama 权重是混合 SSM+注意力多模态架构**
（ssm_* 状态空间层、mtp.* 多 token 预测头、v.blk.* 视觉塔）——transformers 4.57.5
没有 `qwen35` 模型类（实测报错），支持它意味着从零实现 SSM scan/MTP/视觉栈。实验
矩阵的基座必须替换；本机候选：Qwen2.5-7B（已验证）、Qwen2.5-14B（需 NF4 显存
检查）、或从 HF 下载 Qwen3-8B。

管线本身已在 **Qwen2.5-7B**（`/data/llms/Qwen2.5/7b`）上验证：NF4 双重量化加载
6.59 GB，forward/backward/梯度累积全有限，LoRA（r=16，q/k/v/o）保存+重载字节一致
（比对 112 个 lora_A 张量），生成正常。**峰值显存 12.86 / 23 GB。** 环境固定：
torch 2.2.2+cu121、transformers 4.57.5、peft 0.20.0、bitsandbytes 0.45.0（服务器
镜像源超时，wheel 从本机传输安装）。证据：
`docs/reports/qwen_a10_qlora_smoke_v1/`（逐步账本、报告、hash ledger）；脚本
`scripts/qwen_a10_qlora_smoke.py`。

下一步：用户定基座模型，然后 ④ paper_v1 抽 100 条 overfit（数据路径与 LoRA 配置
已验证）。

## paper_v1 监督清单 v2 —— GEE 侧更正为 8,283 权威包（2026-09-07）


用户纠正了首版 paper_v1 的一个真实错误：GEE 侧误用了被替代的 76,884 行旧基线
（旧 step1-8 管线）。当前正式 GEE train-only authority 是 Batch12 合并后的 8,283
行累计包。该包**在仓库根目录的工作文件**
`.tmp_gee_cumulative_authority_v8_9_9_batch12_20260811.json` 中完整找回——SHA256
与记录的累计 authority 哈希（`30dbfe5c…`）精确一致，即原始文件而非重生成。已物化
并附找回账本至
`docs/reports/gee_train_only_authority_v8_9_9_8283/`；方案 B 的服务器重建在发现
文件后已停止并清理。

**paper_v1 v2 = 8,912 行**（GEE 8,283 + QGIS 629）：train 8,817 / val 49 / test
46；独立复验源级不相交（8,797 个独立来源身份、0/0/0 重叠）；任务文本零空缺；
两个 held-out split 均含双平台真实多步监督（GEE val/test 37/35 条多步、QGIS
val/test 5/4）。L3 词汇：GEE 57 个码、QGIS 56、共享 25、QGIS 独有 31。权重：
GEE 0.5×8,283；QGIS 1.0×172 / 0.8×24 / 0.7×430 / 0.6×3。首版 77,513 行构建作废。
训练行 0；仅 manifest。证据：`docs/reports/paper_v1_supervision/`（manifest、
summary、`manifest_report_v1.md`、固定 8,283 输入 `30dbfe5c…` 的 hash ledger）。

## paper_v1 监督清单已冻结（2026-09-07）——已被上方 v2 替代

模型实验阶段开启。`paper_v1` 将 GEE + QGIS 统一为一个监督账本（108MB、77,513 行：
GEE 76,884 + QGIS 629），统一 schema（record id、任务文本、平台、来源身份+SHA、
L3 链、算子链或包引用、对齐、split、权重、证据级别），train/val/test **按来源身份
分割、源级不相交**（77,398 个独立来源身份；独立复验 0/0/0 重叠）。分割：train
76,733 / val 391 / test 389；QGIS val 8（6 条多步，含 9 步与 6 步链）、test 3
（全部多步，含 1 条 GOLD）。权重 1.0×77,056 / 0.8×24 / 0.7×430 / 0.6×3。L3 重叠：
两平台共享 18 个码、QGIS 独有 38 个。17 条 GEE 训练行任务文本为空（继承自冻结
基线；保留在 train）。清单验证时发现并修复了一个丢掉 3 条 standalone 任务文本的
合并 bug（池已重建、哈希刷新、测试 5/5）。证据：
`docs/reports/paper_v1_supervision/`（manifest、summary、`manifest_report_v1.md`、
固定双输入的 hash ledger）；脚本
`scripts/build_paper_v1_supervision_manifest.py`（rng seed 20260907）。

按用户路线的下一步：③ Qwen3.5-9B A10 训练 smoke（NF4 QLoRA：tokenizer/forward/
backward/梯度累积/checkpoint 保存-重载/生成）、④ 100 条 overfit、⑤ M3-P0 zero-shot、
⑥ M3-P1、⑦ M1 受控重跑——全部只消费这一份 manifest；Benchmark Gate-3 供给补充
并行推进，来源限定在 629 池之外的 QGIS source-backed 数据。尚未产出训练行；
不存在任何 checkpoint。

## 正式合并 QGIS 训练池 v1：629 行（2026-09-07）

对三个已审计来源（审计后 506 + 120 条 pattern 候选 + 3 条 standalone）的合并级准入，
全部去重层联合重放（sample 身份、source SHA+span、L3 序列+任务文本）。
**结果：629 条获准入，0 跨池拒绝**——此前各阶段的交叉去重精确成立。结构：单步
367，**多步 262**（workflow 组合监督，较旧 142 增 84.5%），277 个唯一 L3 序列
（其中多步 227：既有 107 + pattern 120，pattern 线贡献全部序列唯一），617 个唯一
任务文本，长度分布 1:367 / 2–3:138 / 4–7:89 / 8+:35，权重 1.0×172 / 0.8×24 /
0.7×430 / 0.6×3。全池 V4 smoke：真实 dataset + 真实 tokenizer，20 个 batch，最大
内容长度 55/100，loss/梯度有限，无 checkpoint/epoch。池状态为
`admitted_train_only_candidate_v1`——已版本化并哈希固定，但不是训练运行；每行
validation/test=false、production_merge=not_granted。证据：
`docs/reports/qgis_training_pool_merged_v1/`（`pool_report_v1.md`、
`qgis_training_pool_v1.jsonl`、summary、双 hash ledger）；脚本
`scripts/merge_qgis_training_pool_v1.py`。

按用户路线：下一步是 GEE vs QGIS 分布分析，并在两个选项间决策——先做第一轮
GEE→QGIS 适配训练实验（QGIS 已有 500+ 行、其中 260+ 为真实 workflow 监督），或
先做一轮专门针对 workflow 多样性缺口（262 → ~500）的 AI 重建，而非凑原始行数。

## 既有 QGIS 训练池审计：508 → 52 GOLD / 454 SILVER / 2 REJECT（2026-09-07）

按用户指令对既有 508 行 aggregate 直接审计，不做新挖掘。所有检查机械且全量（非抽样）：
服务器端 source SHA 复验 **508/508**（0 缺失/0 不符/0 不可读）、span 检查 453 通过 + 55 行
无 span、对 128 taxonomy 的 L3 合法性与 token-ID 一致性 **508/508**、任务文本 ≥15 字符
508/508、QGIS 平台属性（无 `ee.*`）508/508、真实 tokenizer 门禁 **0 淘汰**（最长 126）、
对 506 条非 REJECT 行的 V4 smoke（16 个 batch、最大内容长度 14/100、loss/梯度有限、
无 checkpoint/epoch）。重复：2 条（L3 序列 + 任务文本完全相同的孪生行）→ REJECT。
20 条无 `dependency_edges` 的多步行全部带 `normalized_dag_key` + `call_graph_key`——
数据流在准入时已证明、按序列序列化（V4 不消费 edges）；重新归类为
`sequence_serialized_dag_verified`，不是缺陷。

**池是真的：506 条结构干净（52 GOLD 权重 1.0、454 SILVER 权重 0.7/0.8/0.6）。**
注意事项：GOLD/SILVER 继承准入时的审核 tier——本次审计复核的是结构，不是人工语义
（那些审核已冻结在各源包中）；364/506 为单步行（operator 级监督；多步量为 142）；
406 行仅共享 55 个不同 L3 序列——监督主要由任务文本多样性承载。QGIS 合计现状：
审计后 506 + 120 条 pattern 候选 + 3 条 standalone + 56 个已证明 operator = 若 120
获准入，监督上限 629 行。2 条 REJECT 已标记待移除，未删除。证据：
`docs/reports/qgis_508_pool_audit_v1/`（`audit_report_v1.md`、裁定/结构/源码三个
ledger、hash ledger）。

## API pattern 875 漏斗最终结果：120 条 training candidate（2026-09-07）

875 漏斗闭环。最终数字：**875 → 120 条 training candidate**（签名级保留 13.7%，
占 4,880 实例的 2.5%），全部通过真实 `bert-base-uncased` 门禁（最长 119 token、
均值 49.3、零淘汰）和真实 V4 数据路径（8 个 batch、最大内容长度 55/100、loss
与梯度有限、sample weight 正常；无 checkpoint、无 epoch）。142 条合格行的末段
去向：任务文本拒绝（无源码上下文）4；内部 L3 序列去重 8；命中 508 池 10
（source SHA 4 / L3 序列 6 / 任务文本 0）。任务文本来源——无一凭空生成：
docstring 90、任务性注释 11、domain 命名 class.function 作用域 19（如
`JunctionBufferTrimAndExplode` 等真实插件算法类）。分布：长度众数 3、尾部到
55；L3 覆盖 Intersect 289 / Buffer 161 / Reproject 150 / Feature to Point 131 /
Collect 78 / Erase 49 / Repair 34 / Min Bounding 7 / Simplify 5 / Smooth 1 /
SymDiff 3。

**解读（按用户划定的区间）：120 落在 50–150 区间**——API pattern 有真实多步
结构，但任务监督不足以单独作为主要训练源；按事先约定的解释，AI 辅助重建等
路线正式进入规划，同时本线的存量产出是 120 条已验证候选加已冻结的谓词/算子
证据。最大已知解锁点仍是 645 个未证明 transform 步骤（238 行）。120 条是
candidate 不是训练行：并入训练包是单独的用户决策。训练行 0；
authority/评测/checkpoint 未修改。证据：
`docs/reports/qgis_api_pattern_production_final/`（`final_report_v1.md`、带阶段
原因与 token 计数的 `pattern_consumption_v1.jsonl`、`qualified_context_v1.json`、
双 hash ledger）；脚本 `scripts/consume_qgis_api_pattern_training_rows.py`；
测试 6/6。

## API pattern L3 资格化：875 → 142 QUALIFIED（2026-09-07）

pattern 线资格化跑完 875 个唯一链签名，复用**未改动**的
`human_binding_review_2026_09_04` 绑定类，加上你批准的**谓词/度量步骤政策 v1**：
谓词只有在其结果可证明控制后续变换调用（`if`/`while` 条件操作数、且分支执行
链内调用）时才进入序列（142 条合格链中 61 条带这种控制节点，用既有 Intersect
token 编码）；度量永不占位；1,796 个谓词步骤作为结构证据保留在行上。不新增
L3 码；taxonomy 未动。

漏斗：875 中 L3 完整映射 434（unresolved 306——647 个未解步骤中 645 个是
`transform:unproven_receiver`，与 standalone 线同一名字绑定 receiver 墙；deferred
动作 135 行/451 步）。**QUALIFIED 142** = 完整映射 + ≥2 变换步 + domain-named
owner。DEFERRED 733：owner 292、政策后变换步不足 127、unresolved 238、deferred
动作 76。合格链覆盖 11 个 L3 类（Intersect 298、Buffer 177、Reproject 168、
Feature to Point 141、Collect 90、Erase 52、Repair 37、Min Bounding 8、
Simplify 5、SymDiff 3、Smooth 1），长度 2–55 且没有占主导的重复 L3 序列——链
多样性在资格化后仍然保留。训练行 0；tokenizer/V4 未跑；authority 未改。
注意：census ledger 未带 `source_path`，资格化输入在服务器侧按 record_id join
回 v2 normalized ledger 后运行。证据：
`docs/reports/qgis_api_pattern_qualification_v1/`（账本、summary、双 hash
ledger、`qualification_report_v1.md`）；脚本
`scripts/qualify_qgis_api_pattern_chains.py`；测试 9/9。

下一步：142 对 508 池跨池去重，再构造任务文本/tokenizer/V4。可选解锁（需你
决定）：对 645 个未证明 transform 步骤做支配赋值证明（238 行）；对 292 条
plain-scope 完整链做单独的 owner 政策裁定。

## API pattern 多步 census：4,880 → 875（2026-09-04）

对 4,880 条 `api_pattern` 的第一轮压缩结构测量——不做 L3 映射、不构造任务文本、
不授予准入。阶段表：source 失败 0；FAIL_CLOSED 45（外部 receiver/keyword）；结构
无效 2,742（无 QGIS 可证 receiver 813、调用间无数据流连接 731、谓词/度量主导
1,198）；**2,093 条结构有效多步链**，按链签名去重后保留 **875 个唯一签名**
（2.4:1）。875 条全部有已验证的 producer→consumer 连接。任务 owner：
`domain_named` 322（签名全部唯一，且是真正的多操作形态，如
`makevalid|intersects|buffer|unaryunion|intersection|transform`）、`plain_scope`
505、`module_level` 25、`generic_verb` 23。链长众数 3–8 步、尾部到 102——不是双
调用碎片；最大签名是 `transform|transform`（257→1）。谓词污染高（531/875 含谓词，
纯变换链仅 259 条）。

解读：实例数（4,880）从来不是监督数——875 个签名才是，任务限定的训练上限从
322 条 domain-named 起算，还要过谓词过滤、逐源审核、508 池跨池去重和
tokenizer/V4 门禁。转向多步结构的决策被证实；standalone 线维持 3 条候选封存。
训练行 0；authority 未修改。证据：`docs/reports/qgis_api_pattern_census_v1/`
（逐行带阶段原因的 `pattern_census_v1.jsonl`、`census_report_v1.md`、双 hash
ledger）；脚本 `scripts/census_qgis_api_pattern_chains.py`；测试 9/9。

## API semantic standalone 消费结果：137 → 3（2026-09-04）

对 137 条已裁定 standalone 行的产出收敛流水线已跑完，无新增解析。**结果：3 条
training candidate**（Reproject 1、Intersect 1、Simplify 1）。淘汰构成：1 条与既有
508 池 source SHA 重复；66 条本批内部 payload 重复（137 行中 99 行与其他行 call_text
完全相同，39 个签名覆盖全部 137）；67 条无独立任务上下文（55 条模块级片段无任务
owner，12 条无可观测任务语义的 helper）。3 条存活行全部靠 `domain_named_scope`
（如 `AddMultipleTreesTool.get_line_segment`），通过真实 `bert-base-uncased` 门禁
（最长 35 token）和真实 `TaskConditionedL3DatasetV4` + 加权 CE + backward smoke
（loss/梯度有限，无 checkpoint，无 epoch）。它们只是 candidate——并入训练包需要
用户显式决定。

**本线结论：API semantic 单元线贡献的是 operator 语义知识（998 条已裁定动作绑定，
其中 861 条 grounding 级），不是 workflow 训练数据。** 没有任务上下文的单个几何
调用不是用户工作流；按锁死的原则，没有把不同源码包装成不同任务。API 侧下一个
产出增量必须来自多步结构：`api_pattern`（4,880）与 workflow 各线。证据：
`docs/reports/qgis_api_semantic_production_v2/consumption/`
（`consumption_report_v1.md`、`standalone_collapse_v1.jsonl`、
`training_candidates_v1.json`、双 hash ledger）；脚本
`scripts/collapse_qgis_api_standalone_candidates.py`；测试 10/10。

## QGIS API semantic 生产 v2 — L3 资格化已裁定（2026-09-04）

人工绑定复核（`human_binding_review_2026_09_04`）已应用并物化为账本：1,058 条 proof 行
**QUALIFIED 998 / DEFERRED 59 / FAIL_CLOSED 1**。整类放行：
`native_operator_slug_equivalence` 387、`transform_crs_receiver` 558（+1 条内联
`QgsCoordinateTransform` 参数的几何 transform 升格）、`taxonomy_class_equivalence`
52——逐行证据保留。`interpolate` 40 / `offsetcurve` 3 / `splitgeometry` 2 维持
DEFERRED（`action_deferred_by_adjudication`）；几何型 `transform` 拆分为 1 QUALIFIED /
14 DEFERRED（`transform_argument_not_yet_proven`，后续可用参数支配赋值恢复补证）/
1 FAIL_CLOSED（数值 `transform(float(x), float(y))`）。账本澄清了数字口径：16 条
transform 属于 61 条 unresolved、在 997 条提案之外，故 QUALIFIED = 998。

消费路由（仅 QUALIFIED）：**137 条 standalone → workflow 训练候选池**（Reproject 65、
Feature to Point 25、Buffer 21、Simplify 8、Intersect 7、Smooth 5、Collect 4、
Repair 1、Minimum Bounding 1），仍需序列构造/跨源去重/独立 workflow 上下文/tokenizer/
stable124 门禁——training-eligible ≠ training row；**861 条 intermediate →
operator-grounding 语料**。训练行 0；authority/评测/checkpoint 未修改。证据：
`docs/reports/qgis_api_semantic_production_v2/phase2_adjudicated/`
（`adjudication_v1.jsonl`、summary、双 hash ledger、`adjudication_report_v1.md`）；
脚本 `scripts/adjudicate_qgis_api_semantic_l3.py`（裁定文本冻结在脚本内）；测试 6/6。

本线 KPI 已转为：**137 条 standalone 候选最终沉淀多少独立 QGIS 训练行**
（序列构造 → 跨源去重 → 独立 workflow/任务上下文 → tokenizer → stable124/V4），
而不是继续扩大解析量。

## QGIS API semantic 生产 v2 — 第二阶段完成（2026-09-04）

第二阶段（对 1,058 条候选做 L3 证明）已完成。每个语义动作都带**显式映射证据**绑定到 L3 类，
并区分 standalone 操作与实现步骤，但只产出**提案**：所有行均为
`DEFERRED / awaiting_independent_binding_review`，因为绑定复核才是 QUALIFIED 门禁，
属于单独一次授权过的复核。`qualified_rows = 0` 是设计属性。

逐行映射证据——绝不凭方法名：`transform_crs_receiver` 558
（`QgsCoordinateTransform.transform` 按类型契约即重投影）、
`native_operator_slug_equivalence` 387（PyQGIS 是同名 Processing 算子的引擎，
其 L3 已由 `composed_stable124` 固定）、`taxonomy_class_equivalence` 52
（`convexhull` → L3_02_05_12（hull 是该类显式列举的变体）；`combine` → L3_02_03_05
Collect Features）、`unresolved_action` 61（`interpolate` 40、`offsetcurve` 3、
`splitgeometry` 2、几何型 `transform` 16——未分别裁定前不提议绑定）。

结果：**997/1,058 带 L3 提案，覆盖 11 个 L3 类**（Reproject 558、Feature to Point 174、
Buffer 92、Intersect 57、Minimum Bounding 33、Simplify 28、Repair Geometry 24、
Collect Features 19、Smooth 10、Erase 1、Symmetrical Difference 1）。standalone 划分：
**137 条 standalone 操作行**（结果 return 给调用方 62 / 模块级 75）——这是
workflow 训练线未来唯一可消费的行，构成为 Reproject 65、Feature to Point 25、
Buffer 21、Simplify 8、Intersect 7、Smooth 5、Collect 4、Repair 1、Minimum Bounding 1；
**860 条 intermediate 实现行**的结果从不离开所在函数（operator 语义知识，
不是 workflow step）。训练行 0；authority/评测/checkpoint 未修改。证据：
`docs/reports/qgis_api_semantic_production_v2/phase2/`（`l3_proof_v1.jsonl`、summary、
双 hash ledger、`phase2_report_v1.md`）；脚本 `scripts/prove_qgis_api_semantic_l3.py`；
测试 9/9。

下一步：独立绑定复核（每个映射类一次决策：slug 等价表、CRS-receiver 规则、
hull/combine 等价，以及 `interpolate`/`offsetcurve`/`splitgeometry`/几何 `transform`
的裁定）即 QUALIFIED 门禁；复核通过后 137 条 standalone 行成为本线首个
training-eligible 池（仍需下游去重/tokenizer/V4 门禁），860 条 intermediate 行
按多资产池策略进入 operator-grounding 语料。

## QGIS API semantic 生产 v2 — 第一阶段完成（2026-09-04）

API semantic 线已开。第一阶段（源码事实抽取 + 语义资格化）跑完 v2 normalized ledger
的 3,209 条 `api_semantic_unit`（哈希固定输入 `a13ce1a2…`），**明确不尝试 L3 映射**——
本阶段只有 `DEFERRED`/`FAIL_CLOSED` 可达；`QUALIFIED` 需要第二阶段 L3 证明层。结果：

- **1,058 条 candidate geometry semantic（33%）**：receiver 已证明为 QGIS、几何变换角色、
  结果被保留。构成：**558 条 `QgsCoordinateTransform.transform`（重投影语义）**、484 条
  经典几何变换（centroid 174、buffer 92、intersection 57、interpolate 40、convexhull 33、
  simplify 28、makevalid 24、combine 19、smooth 10、offsetcurve 3、splitgeometry 2、
  symdifference 1、difference 1）、16 条几何型 `transform`。1,058 个唯一 source SHA；
  非变换类中仅 26 条参数全为字面量。
- **1,168 条 ambiguous receiver**：receiver 的 QGIS 类型无法仅凭本文件证明——这是
  "语义藏在实现里"问题的实测规模，也是第三阶段的产能决策点（跨函数类型恢复），不是
  规则微调能解决的。
- **889 条谓词/度量/丢弃结果**（527 条返回标量、362 条结果未被使用）：是知识，但不是
  workflow step。
- **94 条外部库 fail closed**（osgeo 33、pyproj 23、shapely 18、sklearn 8、geopandas
  5+4、其余 3）。

方法名匹配必须先证明 receiver，因为同名方法在 shapely/geopandas/pyproj/sklearn 中
大量存在；从首轮输出检查中补了两条硬规则并已有回归测试：仅外部库才有的关键字参数
（`cap_style` 等）直接 fail closed；裸 `.geometry` 属性（GeoDataFrame 习语）不算 QGIS
receiver，而 `.geometry()` 调用算。每行保留完整事实记录（`call_span`、`call_text`、
receiver 绑定证据、`argument_facts`、`return_target`、`enclosing_scope`、
`semantic_action` 为 role:method，绝不是 L3 码），后续任何阶段都不需要重新解析源码。
裁定：DEFERRED 3,115 / FAIL_CLOSED 94 / QUALIFIED 0。训练行 0。证据：
`docs/reports/qgis_api_semantic_production_v2/`（账本、summary、双 hash ledger、
`phase1_report_v1.md`）。

## Asset Miner / 标准化 v2 重建（2026-09-04）

服务器侧 v1 树被删除后，资产账本已按 **v2 重建**（不是 v1 恢复），未覆盖任何 v1 目录。
输入为本地 manifest（Processing 8,466 + API 39,386 = 47,852）加完好的只读 `/home/yll`。
v2 解析 **47,852/47,852，source_unresolved=0**（v1 为 47,542/310）。两个 source root 在
manifest 冻结后被改名（`model_tutorial` → `…/downloaded_scripts(QGIS_Model_Tutorial_Workflows)`、
`pwc_qgis` → `…/downloaded_scripts-PWC`），正好对应 301 + 9 = 310 行；两处替换在使用前
均已按 manifest 做 SHA 核验。

v2 各池：`unresolved` 23,650（−295）、`api_implementation_evidence` 12,410（+3）、
`api_pattern` **4,880**（0）、`api_semantic_unit` **3,209**（0）、`processing_workflow`
1,337（+101）、`processing_implementation` 1,266（+178）、`processing_operator` 595（+4）、
`processing_dynamic_candidate` 505（+9）。全部增量都可追溯到这 310 条恢复源码，没有任何行
在池间迁移；3,209/4,880 是实测重合，未做 expected-output 对齐。

census 门禁通过：47,852 个唯一 source SHA 与 record ID、重复 SHA 行 0、
`unique_operator_sequences` 1,411 与 `unique_semantic_sequences` 1,729 均与 v1 一致。
口径已按证据确认：**`api_semantic_unit` = 恰好 1 个 API 语义调用**（3,209/3,209，
Processing 调用为 0）；`api_pattern` = 2 个及以上（2–102）。这是 normalizer 的定义，
刻意不沿用 miner 标签——3,209 中有 2,242 条来自 miner 的 `api_pattern_candidate`。
它既不是 boundary-unit，也不是 composite macro。

operator 池为 595 行但**唯一 operator ID 仍是 207**：新增 4 行携带的 `omm:*` 已在既有
qualification 中 `FAIL_CLOSED`，因此已封板的 56/44/107 结论不受影响，且继续绑定其自身
冻结的 591 行 v7 sidecar 输入。

保全门禁现为强制项：`preservation_ledger_v1.json` 绑定输入 manifest 哈希与行数、全部脚本
哈希、构建时 git commit，以及每个产物的哈希与第二副本位置。83MB normalized ledger 已镜像
入仓库并在传输后哈希复验（`a13ce1a2…`）；66MB 合并 miner ledger 与 479 分片树仍只在服务器，
均可确定性重生成。

历史 API 产物仅作 **reference lineage**，不并入本池：`qgis_api_boundary_v6_post_filter_v1`
（2,707 intake unit）、`qgis_api_l3_mapping_census_v1`（2,632 行，其中 2,605 为
`mutation_export_only`）、`qgis_api_composite_macro_census_v1`（10,800 discovery unit）。
2026-08 的 mutation/export 关闭结论未被重新打开。Asset Miner v2 是当前 API 资产的
canonical 来源。训练行 0；authority、评测与 checkpoint 未修改。证据：
`docs/reports/qgis_asset_normalization_full_v2/` 与 `docs/reports/qgis_asset_miner_full_v2/`。

## 最新 QGIS normalized-DAG collapse 审计（2026-09-03）

对合并后的 107 条 family admission row 完成只读归并审计。共有两个重复组：
`dissolve → multiparttosingleparts` 为 73 条、31 个 source SHA、21 个语义参数签名、
34 个父结构；`buffer → clip` 为 34 条、24 个 source SHA、10 个语义参数签名、18 个父结构。
每组内任务文本、L3、矢量 I/O 和 normalized DAG 一致，但两组都存在源码参数及父结构差异。
这对未来参数感知资产是潜在过度归并信号，但不足以修改当前 task-to-L3 workflow dedup key。
dedup 未修改，Gold=0、训练行=0，两个 survivor 仍为 candidate-only Silver。
证据：`docs/reports/qgis_normalized_dag_collapse_audit_v1/`。

## QGIS 参数与父结构资产池 v1（2026-09-03）

已将 collapse evidence 物化为独立 candidate-only 资产池：107 条源码事实记录产出 31 个
Processing 参数签名资产、52 个父结构资产和 4 个算子观测。每条资产保留 source SHA、
family、normalized-DAG provenance，训练准入为 0。该资产池不放宽 workflow dedup，也不修改
L3 authority、评测划分、生产 profile 或 checkpoint。证据：
`docs/reports/qgis_family_parameter_asset_pool_v1/`。

## Processing operator 资产线（2026-09-03）

服务器 normalized ledger 的 591-row 全池 census 已完成：全量输入 47,852 行，其中准确匹配
`asset_type=processing_operator` 的 591 行，按 operator ID 归并为 207 个唯一 operator ID，
并由 591 个唯一 source SHA 支持。591 行均有 processing-call evidence，expected-row 检查为
`matched`。normalized v1 未携带参数字典和 provider I/O 契约，因此两项明确标记为
`not_carried_by_normalized_ledger`，不能解释为资格化失败。L3 映射、训练准入、authority 和
checkpoint 仍关闭。证据：`docs/reports/qgis_processing_operator_assets_full_v3/`。

独立的 Processing operator evidence sidecar 已升级到 v7（绑定规则修复后重跑）。同一冻结输入下
591/591 条 source SHA 验证并恢复 AST 调用：**511** 条有静态参数字典、438 条有静态 INPUT/OUTPUT
key、含 positional `runalg` 后 504 条有 I/O 线索、589 条有 provider 前缀证据、12 条 deferred。
v6 用全模块 `{name: 最后一次赋值}` 就把按名传入的参数字典标为 `name_to_static_assignment`，
既不证明作用域、也不证明顺序/支配/mutation：4 条 `qgis:joinattributesbylocation` 被错误套用了
文件中另一个算法的参数字典，另有 6 条本可证明的被误 deferred。新规则
`dominating_same_scope_static_dict_v2` 要求唯一支配的同作用域赋值、调用前无重新赋值或 dict
mutation、且值为静态字典，并为全部 224 条被接受绑定记录 `assignment_lineno`/`assignment_span`/
`dominance_verified`/`mutation_guard`（五项 provenance 均 224/224）。首次给出参数完整度：
`static_parameter_complete=50`、`static_parameter_partial=529`、`parameter_unresolved=12`。
sidecar 仍只保存 source-backed evidence；L3 映射、资格化、authority 和训练均关闭。证据：
`docs/reports/qgis_processing_operator_evidence_sidecar_full_v7/`（含
`regression_v6_to_v7_v1.md`）；v6 已 superseded。

operator 池的三态 semantic/L3 qualification 已完成（仅 `QUALIFIED` / `DEFERRED` /
`FAIL_CLOSED`，无中间状态）。207 个唯一 operator ID 中：**56 个 QUALIFIED**（15 个
精确命中 `composed_stable124`（39 条 support）+ 41 个 `qgis:<slug>`→`native:<same slug>`
（241 条 support），每行都经源码重读、SHA 复验、span 精确字面量重定位完成独立 alias
证明，覆盖三种入口；其中 198 行 `processing.run` 子集与既有先例 verifier 结论 198/198
完全一致），共覆盖 **37 个不同 L3 类**；**44 个 DEFERRED**（36 个无 mapping 的 catalog
provider，含 `native:rastercalc`、`qgis:filedownloader`，保留为最少补充观察候选；8 个
无先例 alias 形态——7 个 `gdalogr:`→`gdal:` 加 1 个 `sagang:`→`saga:`）；**107 个
FAIL_CLOSED** 第三方插件 provider（210 条）。56 是当前 authority 下的 operator 级上限，
不等于 280 条训练行；参数/IO 证据仅作覆盖记录、不作门禁。训练行 0；L3 授权、authority、
评测和 checkpoint 均未修改。证据：
`docs/reports/qgis_processing_operator_qualification_v1/`（账本、alias 证明、先例交叉
验证及 `semantic_qualification_report_v1.md`）。

基础设施事件（2026-09-04）：服务器 `/home/qy/system_redesign/diagnostics/` 整树在本
会话之外被删除（`/` 释放约 450G、`/data` 约 590G），包括 operator 资产 census 的服务器
副本、冻结 normalized ledger 输入（`45a1c12d…`）和全部 GEE 批次证据。`/home/yll` 完好。
operator 线的权威链现在保存在本仓库（v7 sidecar ledger + qualification ledger）；
qualification 从本地 v7 sidecar 重建 operator 聚合并与冻结 census 完全吻合
（207/591/591）。normalized ledger 如有需要可经 `/home/yll` 用
`scripts/mine_qgis_assets.py` + `scripts/normalize_qgis_assets.py` 重生成，但尚未运行。

## 当前代理职责

本代理只负责 **QGIS 数据处理**：把 QGIS Processing 源码和低层 PyQGIS API
源码确定性转换为可审计的 train-only 候选。GEE 数据处理和评测集由其他工作区维护；
本代理不得改写它们的结论、数字、门禁或下一步。更新本文时只修改 QGIS 条目和必要的
跨区引用。

## Processing family 校准状态（2026-09-02，v1 已被替代）

首个高支持度 family packet 为 `native:dissolve ->
native:multiparttosingleparts`，按 source SHA 完成独立切分（40 个 source；calibration=20、
holdout=20；共 86 次 occurrence）。首次审计 70 条通过，16 条因跨变量/列表/循环数据流规则缺口
deferred；语义或结构失败为 0，SHA overlap 为 0。当前仍是 candidate-only：尚未授予 L3、任务、I/O、
去重、Gold/Silver、训练、authority 或评测准入。依赖审计器现已识别有界的 `append`/`extend`/`insert`
结果容器写入及 `for item in container` 传播，并有回归测试；任意 mutation 和运行时 alias 仍保持 deferred。
证据：`docs/reports/qgis_family_calibration_audit_dissolve_multipart_v1.md`。

本段历史结论已被下方服务器 v2 重跑替代。

## Processing family 校准重跑（2026-09-02）

冻结的 86 条 `native:dissolve -> native:multiparttosingleparts` packet 未重新生成，服务器使用新版有界容器/循环规则重跑：73 条通过、13 条仍 deferred、0 条失败；86/86 SHA 验证通过，calibration/holdout overlap=0。三条依赖规则 deferred 被恢复（calibration=2、holdout=1），没有结构或语义副作用。当前仍是 candidate-only，L3、任务、I/O、去重、Gold/Silver、训练、authority 和评测均关闭。下一步对 73 条通过项做独立语义资格化，并对 13 条 deferred 进行解决或明确边界。证据：`docs/reports/qgis_family_calibration_audit_dissolve_multipart_v2.md`。

两条 family 的 semantic packet 已完成确定性 source-fact review 和合并四层去重：107 条 family candidate 先形成
107 条 source-fact Silver candidate，随后仅保留 2 条 normalized-DAG 唯一样本，105 条为重复压制。Gold=0、训练行=0；
两条 survivor 仍需独立 intent adjudication 后才能进入 train-only。看板：
`docs/reports/qgis_asset_production_dashboard_v1/dashboard_v1.md`。

## 当前 Raw-source LLM 试验状态（2026-08-11）

此前 boundary v3 只测试“LLM 从预提取 steps 选择边界”，不能证明 raw-source 算子
提取不可行。当前已准备真正的隔离路线：每次请求发送一份完整原始 Python 源码，附
catalog 短名单；模型只返回候选算子和源码行号，不能生成训练数据。新增 packet builder
会按 source SHA 排除旧 mixed pilot、保存完整源码和本地 gold facts。runner 的本地校验
允许发现旧 extractor 未知的调用，并区分 `locally_confirmed` / `call_site_only`。

首轮服务器小批已完成：10 Processing + 10 API、20 SHA 唯一。API 已知 AST facts 8 条中
回收 6 条（召回 0.750、已验证精度 1.0）；Processing 的 5 条 gold 源全部遇到空/非 JSON
响应，重试 5 条仅 1 条局部返回但混入不兼容候选，按 fail-closed 不接受。全批 LLM-only
`call_site_only`=0，训练行=0。结论仅证明 raw 请求/本地校验链路可运行，尚未证明 LLM
恢复了确定性 extractor 漏掉的新算子；路线保持隔离，不扩大、不并入主线。报告：
`docs/reports/qgis_llm_raw_operator_extraction_pilot_v1/report_v1.md`。

## Processing Gold/Silver 首批产出（2026-08-12）

455 条 Processing workflow-tier 不是 workflow 数据集，但本轮已形成受控的训练产出。
修正 adapter 顺序后的 structural replay 为：候选 70、`deferred_boundary=161`、
`deferred_extractor_unsupported=36`、`deferred_mapping=80`、
`deferred_operator_resolution=108`。70 条中 69 条通过确定性描述 fidelity；相对 294
Processing 和 508 全 QGIS baseline 的四层去重后，21 条归为 **Silver**、49 条 Reject。冻结的独立完整
源码语义审核将 21 条定为 **15 Gold、4 条保留 Silver、2 条撤销**；两条撤销分别是布尔栅格表达式的
L3 语义错配和矢量/栅格输出契约冲突。

原 21 条 Silver 导出保持不变；另有独立 curated 包共 19 条 reviewed train-only（15 Gold 权重 1.0、
4 Silver 权重 0.7），不能进入
validation/test、benchmark、正式 authority 或写 checkpoint 的训练。4 条超长描述由源码已核验
的有序算子链确定性压缩。真实缓存 `bert-base-uncased` 对 21/21 无截断通过（最大 122 token），
真实 `TaskConditionedL3DatasetV4` 与 `weighted_sequence_cross_entropy` 覆盖 21/21，loss/gradient
均 finite。stable124（最大 token 118）adapter 仅用于隔离 smoke，不修改生产 94/107 profile。
证据：`docs/reports/qgis_workflow_admission_v2_structural_replay_v1/report_v2.md` 和
`docs/reports/qgis_workflow_admission_v2_structural_replay_v1/silver_semantic_review_decision_v1/`。

## `runalg` 入口校准冻结（2026-08-16）

首个 unsupported Processing family 已冻结为 legacy `processing.runalg`，尚未加入生产 extractor。
服务器对 8,466 条 Processing authority 的只读 census 得到：201 条可读 `runalg` 来源、927 次调用，
其中 775 次首参字面量、152 次动态/空首参，189 条非 authority 的字面量来源。正文规范化去重后剩 148 条
authority，并确定性冻结为 30 条 calibration + 30 条 holdout，两侧 source SHA 与正文哈希均零重叠。295 条
缺失源码继续 fail-closed；没有生成训练行。`runalg` 几乎都是历史 positional API（918/927 次），不能直接当作
字典参数 `processing.run` 的别名接入。

隔离 adapter 的 calibration 独立结构审核为 30/30，但 source-disjoint holdout 仅 26/30：三条来源混有
字面量和动态调用，一条需要 positional 静态输出路径证明规则。因此 `runalg` **不推广**。26 条结构匹配的
holdout 仍仅 candidate-only，不能进入训练路径。该 family 现已**冻结并降优先级**：除非后续 corpus-yield
决策明确重新排期，不再建立 strict-profile follow-up。不得修改生产 extractor、合并 authority、训练模型、写 checkpoint，
也不得降低 operator/boundary/L3 硬约束。证据：
`docs/reports/qgis_runalg_adapter_calibration_v1/report_v1.md`。

## Workflow 语料扩量策略（2026-08-16）

QGIS 当前主 KPI 改为累计获得多少可用、源码可追溯的 Gold/Silver workflow，而不是继续增加门禁通过数。
19 条已审核的 Processing 包是 workflow 种子语料。既有 PyQGIS 局部宏包（包括 `route1` 的 9 条）保持为独立
算子语义知识资产；不得为了抬高语料数量而把它们重标为用户 workflow。

下一条有界生产路线是以该种子包、L3 算子语义和显式 I/O/转换约束为基础的 synthetic workflow **候选**设计。
每条候选必须带 seed provenance 与 constraint profile，未来切分必须按 `parent_source_sha256` 整组处理，保持 train-only、不得进入评测，并在 Gold/Silver 准入前
完成独立语义审核；禁止任意拼接算子。跨平台算子语义继续是独立语料，不能直接放大 workflow 数量。本策略没有
授权模型训练或 checkpoint。

首个 intake 已完成：6 条多步种子产生 31 条源码派生、catalog I/O 相容的子工作流候选，13 条单算子种子被排除。
31 条均待独立语义审核，训练行仍为 0。审核包的 decision 只能是 `independent_workflow`、
`implementation_subworkflow` 或 `duplicate_or_parent_contained`，并强制保留 parent-group split lineage。报告：
`docs/reports/qgis_seed_subworkflow_candidate_intake_v1/semantic_review_packet_v1/`。

累计扩量 KPI 已更新：当前范围 52 条候选，其中 20 Gold、8 Silver、24 Reject；当前 curated train-only 为 28 条。
正式 authority、validation/test、benchmark 均未修改。报告：`docs/reports/qgis_workflow_corpus_kpi_v1/`。

31 条语义三分类现已完成：11 条 `independent_workflow`、17 条 `implementation_subworkflow`、3 条
`duplicate_or_parent_contained`。对 11 条独立候选完成源码事实任务保真度复核：5 Gold、4 Silver、2 条因与父工作流完全重复而 Reject，新增 9 条 train-only。
原 19 条与新增 9 条组合包共 28 条，真实 V4 data-path smoke 通过（BERT-128 无截断、权重/forward/loss/backward/梯度均正常），未训练、未写 checkpoint。
证据：`docs/reports/qgis_seed_subworkflow_candidate_intake_v1/semantic_review_packet_v1/task_fidelity_review_v1/`。

## 增量训练前置阻塞（2026-08-22）

28 条包的 smoke 使用隔离 `stable124`（124 content token）adapter；生产训练默认仍是
`v2_94_stable`。二者前 94 个 token 的 code-to-id 映射一致，但 28 条中有 11 条使用 token
`99/100/110/118`，超出生产 94-token 标签空间。因此不能直接运行“原始训练集 vs 原始训练集 + 28”的
可比实验：直接拼接会越界，丢弃 11 条则不再检验完整 28 条。必须先建立隔离的 stable124 实验 profile，
包括 124-token embedding、主训练数据的 94→124 兼容副本、冻结的原 validation/test split，以及统一的约束和
评测配置；不得修改 `outputs_v2`、508 authority、validation/test 或 benchmark。

## Silver 规模验证（2026-08-11）

## Raw-source 13 候选复核（2026-09-02）

## Blocker source-disjoint yield（2026-09-02）

对 `recover_call_graph` 222 条和 `review_api_sidecar` 203 条高证据 blocker 冻结了 60 条有界、source-disjoint 审核包（每 lane 15 calibration + 15 holdout）。本地按文件名+SHA 找到 35 条源码并完成 AST/call-site 重放；25 条因本地镜像缺源码记为 `deferred_source_unavailable`，不计 Reject。固定 rubric 的结果为 **6 Gold、13 Silver、16 Reject、25 Deferred**；其中 recovery 为 6 Gold/11 Silver/13 Deferred，sidecar 为 0 Gold/2 Silver/16 Reject/12 Deferred。可验证样本 accepted yield 为 19/35=54.3%，packet-level share 为 19/60=31.7%，均不是 425 条全池的无偏估计。训练行仍为 0，authority、评测划分和生产 profile 未修改；7,567 条低证据 deferred 未触碰。报告：`docs/reports/qgis_blocker_source_disjoint_audit_v1/result_v1/`。

已直接回到服务器 `/home/yll` 原始源码完成 source-backed review：DEMProcessing (`d8d9…`) 确认为真实栅格 implementation candidate，其中 `classify` 是 `calc_stats → grass7:r.reclass` 两步依赖链，`export_uniques` 为独立方法；CSV Tools (`bb18…`) 确认为真实但仅限插件 implementation/subworkflow evidence。3 条动态调用延后，4 条通用 wrapper/CLI 拒绝，1 条 detector false positive，另 3 条 implementation 延后恢复。训练行仍为 0，production merge 未授权。详见 `docs/reports/qgis_raw_unclassified_pilot_v1/review_v2/`。

`d8d9…` 的 candidate record 已物化，包含源码 span、依赖/I-O、候选 L3、任务描述和去重键；`bb18…` 已单独物化为 implementation evidence，不计入 complete-workflow。两者仍需独立语义审核和后续门禁。

`d8d9…` gate review 已完成：语义一致性通过候选级审核；严格 L3 仍 deferred（统计算子 pending、GRASS provider binding pending）；本地未发现精确算子序列重复，但完整跨池四层去重仍 deferred；真实 `bert-base-uncased` 128-token smoke 为 40 tokens、无截断。最终状态仍为 `deferred_candidate_only`。

已建立 `scripts/mine_qgis_assets.py`（Asset Miner v1），统一输出 Processing workflow/implementation/operator、dynamic recovery、API semantic-unit/pattern、plumbing 和 unresolved 资产。服务器每池 100 条 pilot：200 条中 194 parsed；训练行仍为 0。摘要见 `docs/reports/qgis_asset_miner_pilot_v1.md`。

全池直跑已验证当前瓶颈是性能：旧版逐行路径解析超过 10 分钟且无增量输出，已停止；不把该次运行当作全池结果。下一版必须按 source-root 分片并 checkpoint 后再合并。

已新增 `scripts/run_qgis_asset_miner_sharded.py`，按 pool 固定分片并写 `DONE.json` checkpoint，合并时只读取完成分片；测试已覆盖中断分片不会混入结果。

服务器 tiny 端到端验证已通过（Processing/API 各 10 条，共 20 条）：2 个 checkpoint 成功，合并 20 行（parsed=19、source_unresolved=1），训练行仍为 0。250 条分片受 `/home/yll` NFS 读取时延影响超时，未计入产量。

全量 Asset Miner 已完成（479/479 shard，47,852 条）：parsed=47,542、source_unresolved=310；workflow=1,236、implementation=1,088、operator=591、dynamic=496、API semantic-unit=1,874、pattern=6,215、plumbing=12,407、unresolved/no-known-signature=23,945。该基线不是训练准入，L3/authority/训练行均未修改。报告：`docs/reports/qgis_asset_miner_full_v1.md`。

## Source-role census（2026-08-11）

全量 47,852 条只读结构 census 已完成：`user_workflow=2,209`、
`processing_implementation=1,012`、`api_semantic_operation=9,028`、
`api_plumbing=11,655`、`unclassified=23,638`、服务器缺失=310。Processing 池内
workflow=2,068、implementation=1,011；严格初筛（run>=2 + 任务/IO 信号 + 下游依赖）
得到 169 workflow + 114 implementation 候选，仅是后续 fidelity/L3/dedup/V4 输入，
不是训练准入。API semantic 主要进入 API catalog/L2-L3 辅助，不直接混入主 workflow 训练。
报告：`docs/reports/qgis_source_role_census_v2/report_v1.md`。

## Workflow-value 分层（2026-08-11）

服务器在不重读源码、不调用 LLM 的条件下完成 47,852 行分层：tier1 多算子
workflow=169、tier2 单算子 workflow=325、tier3 Processing implementation=983、
API semantic knowledge=4,737、API plumbing evidence=11,655、unclassified deferred=29,673、
缺失=310。下一批 Processing workflow 队列为 455 行（Processing 池 tier1=169、
tier2=286）；另有 39 行 API 来源保留在独立队列，训练行仍为 0。报告：
`docs/reports/qgis_source_role_tiers_v1/report_v1.md`。

455 条 Processing replay 已完成，其替代性 70/69/21 结果已记录在上文。当前下一步为审核 31 条
源码派生的子 workflow 候选；workflow-tier deferred 总量 29,673 条，其中原始 `unclassified`
为 23,638 条；二者都不进入无约束 LLM 全量抽取。

## Workflow Admission Structural Replay（已替代的旧口径，2026-08-11）

此前 `304/3/0` 是 adapter 调用顺序缺陷造成的旧口径，已被上方 70/69/21 结果替代，
不得用于后续规划或产量估计。

当前正式 QGIS train-only 为 508 行，含 isolated 变体为 539 行；这不是 47,852 份源码的
抽取上限，而是严格 Gold 门禁和四层去重后的观测压缩结果。API census 已发现 13,554 个
pattern candidate、10,800 个 discovery unit、14 个复合宏 family 中 2,773 个 priority unit，
但它们尚未完成 normalized authority、mapping、fidelity 和准入。既有 family 的
source-authority 到 canonical 留存率介于 0.5% 与 75%，不能用一个全局比例外推。
证据见 `docs/reports/qgis_silver_scale_validation_v1/report_v1.md`。

2,773 个 priority unit 是历史 discovery 人口，其 14 个 mutation-only family 已在后续
replay 中开采、完成或永久关闭。下一步先排除这些 family 刷新 API census；只有仍有至少
5 个新的高 support family，才做无 LLM 的 150-source 规模验证（每 family 30 个
source-disjoint authority），逐层记录 replay、mapping、fidelity 和 canonical 留存率。
不修改 508 行 authority，也不放宽 Gold 门禁。

## 隔离 API LLM 边界 pilot（2026-08-11）

首个 API 边界 100-source pilot 已完成：50 条 calibration、50 条冻结 holdout，source SHA
全部无交集。`deepseek-v4-flash-0731` 返回 79 条通过本地结构校验的边界 proposal，2 条因
multiple sink 被拒，19 条为 HTTP 请求失败。当前校验只确认 JSON、源码步骤、行号和单 sink
一致性，不确认语义正确性。训练行仍为 0，pilot 仅为 candidate-only。证据：
`docs/reports/qgis_api_llm_boundary_pilot_v1/`。

重试与审计更新：19 条 HTTP failure 使用冻结 prompt hash 重试后，5 条恢复、1 条因 multiple
sink 拒绝、13 条仍失败。当前完整请求账本形成 82 条 proposal（calibration/holdout 各 41）。
独立源码语义审核已完成：75 条边界可接受、5 条错链、2 条链截断；holdout 为 38/41，未达到
零错拼/零截断推广门禁。审核包 `qgis_api_llm_boundary_pilot_v1/semantic_review_v1/`
仅 candidate-only，训练行=0，LLM 边界规则不推广。

v3 follow-up 将两条风险固化为本地 fail-closed 校验：选中控制路径步骤的 source span 必须包含
控制头；span 内每个可见 QGIS 数据变更调用必须有被选中的 AST step 表示。旧 v2 的 18 条
结构通过 proposal 重放后有 8 条因此被拒绝。新冻结的 100/100、与所有旧包 source-disjoint 的
v3 packet 先做受控 10/10 试验，得到 1 条结构通过的 holdout proposal、16 条空/无效 proposal、
3 条 HTTP failure；唯一
holdout 已独立语义审核通过，但召回与服务稳定性均远低于推广门槛。该路线停止扩大，仍仅
candidate-only：不映射 L3、不产生训练行、不修改 authority。证据：
`docs/reports/qgis_api_llm_boundary_pilot_v3/`。

范围更正：v3 输入的是有界源码窗口加上本地预提取的 AST steps，测试的是“LLM 选择任务边界”，
不是“LLM 直接从原始源码提取算子”。因此不能据此断言 LLM 无法找出确定性 extractor 漏掉的算子；
原始源码算子提取路线仍未验证，不能提前关闭。

## 隔离 LLM 算子提取 100-source pilot（2026-08-10）

已完成 50 Processing + 50 API 的服务器 SHA/AST staging，并在每池 10 个有界 scope
上调用 `deepseek-v4-flash-0731`。20/20 JSON 响应均只返回候选目录内 ID、原始行号有效，
请求失败/未验证候选均为 0；但所有发送 scope 都有本地可观测事实，因此这仅证明
scope→目录短名单→LLM→行号验证链路可运行，**不证明**动态 ID 或复杂工作流已恢复。
87 个支持 scope 仍因试验预算 deferred、3 个超长 scope 未截断。API 使用新的受限语义
目录（非 L3）。训练行=0，禁止并入 authority。当前证据：
`docs/reports/qgis_processing_llm_operator_pilot_v1/mixed_100_request_budget_10_v1/`；方案：
`docs/plans/qgis_llm_mixed_operator_pilot_v1.md`。source-disjoint 动态/部分证据对照组已完成，
未产生独立可验证的动态恢复；该隔离 LLM 路线没有获批的扩大动作。

## Processing 动态首参全池 census（2026-08-10）

对 8,466 Processing authority 在只读服务器做 SHA+AST census：8,143 条可读且一致，
295 条缺失、28 条不可解析。真正 `processing.run` 首参非字面量的仅 **484 source / 1,379
call（可读人口 5.95%）**，其中 `Name` 变量 1,190 次，表达式型 125 次，64 次无首参；4,841
条没有直接 Processing module 调用。现有 `deferred_operator=387` 不是动态 ID，而是已有
字面量 provider/algorithm ID 缺 catalog 或 mapping。LLM 只可能试验 expression lane；Name
先走静态绑定恢复，其余保持 deferred。API 路线暂冻结。

表达式型 25/25 source-disjoint LLM pilot 已完成：50 条 SHA-verified source / 74 个动态
表达式调用，20 个 scope 实际请求仅获得 15 个有效响应；6 个返回 ID 都是同 scope 已知的
静态调用，动态表达式的新增候选=0，5 个响应不可解析。扩展 JSON 解析后针对失败 source 的
retry 仍为 2 个 abstain、4 个不可解析，净增仍为 0。**不扩大 LLM 到 125 call**。确定性 AST
现在只恢复源码可证明的布尔常量条件；运行时条件保持多候选并 deferred。`mappy.matchAlgo`
已取得独立冻结的 `mappy v0.3.2` 实现哈希，但只在源码版本头、精确相对导入、无可见重绑定、
单个字面量实参及 catalog 返回值证明同时成立时恢复。8,466 条全池只读 census 仅找到 **3 条
source / 5 次调用**，三条均已按 SHA 本地重放且没有 canonical candidate：两条仍被未入 catalog
的自定义 `mappy:*` 算子阻塞，一条被既有 downstream-transform gate 拦截。因此该 wrapper
family 以不可规模化关闭。证据：
`docs/reports/qgis_processing_dynamic_operator_contract_v1/`。下一条 source-only 恢复路线是
1,190 个 `Name` 首参调用，不扩大 LLM。

该 `Name` 路线已完成 census replay：316 个 source / 997 次调用含 `Name` 首参，97 条动态链
得到唯一恢复，83 条完全规范化。8 条 route-level auto candidate 全为单算子 scope，不满足
Processing 的 2–6 链边界；20 条 call-graph/local-subworkflow replay 已完成，另有 2 条双算子
source 已进入 `review_api_sidecar`。共产出 63 个 local unit，但没有 eligible 的 2–6 单元
（31 个单算子、32 个 deferred）。训练行仍为 0。证据：
`docs/reports/qgis_processing_name_binding_split_replay_v1/`。

## QGIS API polygon_geometry_construction family（2026-08-09 完成）
## QGIS API coordinate_transform family（2026-08-09 完成）
## QGIS API rectangle_geometry_construction family（2026-08-09 完成）
## QGIS API semantic_priority 层耗尽 + 复合宏聚类发现（2026-08-10）

unary_union（最后剩余语义 family）：校准 50 → 全池 119 → **0 complete**（真实
unaryUnion 形态不匹配：sink 非字面量 68/调用不唯一 33/带参 14）。**census_v2 的
semantic_priority 层（7 family）开采完毕**：6 完成（polygon 3 + coordinate_transform 1
+ rectangle 2 = +6 条）+ unary_union 0。

**v3 复合宏聚类**（`build_qgis_api_composite_macro_census.py`）修复 census_v2 两个
盲区：多 producer 复合宏丢弃（1,286/5,580）与 mutation-only 窗口丢弃（3,718 窗口 /
2,232 unique source，add_field 机制与其重叠仅 40/2,232）。**新 priority family 14 个
/ 2,773 units，最大 setattributes→addfeature 575 src**。

## QGIS API setattributes family 闭环（2026-08-10，+3 条）

- calibration 200：v1 严格字面量 1/200（0.5%）→ 抽查发现 68% 为属性复制
  （`setAttributes(feature.attributes())` 别名/直调）→ 证据驱动放宽一轮 → **60/200
  （30%）**；同时修复 replay 模板缺陷（complete 行缺 authority key、split 无 sha 兜底）。
- 全池 883 units / 575 source → **213 complete / 173 authority（24%，历史最大）**；
  deferred 主因：sink 非字面量 239、动态值 197、调用不唯一 121、别名不唯一 113。
- L3 映射（词汇表 130 无扩展）：buffer→L3_02_01_01(8)、intersects/intersection→
  L3_02_06_03(22) Extract by Location、simplify→L3_02_05_01(104)、difference→
  L3_02_02_04(11) Erase。**defer**：PLAIN_COPY 145 units/110 auth（窗口内无几何
  处理，无属性复制类 L3）、centroid 9（词汇表无类）、construct 12（evidence 不可见）。
- 导出 45 fidelity → 四层去重 **3 canonical**（每组 1 条，描述模板压缩效应，与
  polygon 43→3 同构）→ cross-pool 0 抑制 → loader smoke（130 vocab）通过。产出
  `docs/reports/qgis_api_setattributes_train_only_v1/`（buffer 1 + extract 1 +
  simplify 1）。**语义近似提示**：extract_by_location 是 508 无的新 API 单链形态；
  buffer/simplify 与 508 API 行同 L3 近似（去留由用户裁决）。
- **累计 517 train-only**（508 + 9 isolated：15-step 1 + polygon 3 + ct 1 + rect 2
  + setattributes 3）。

## 路线 1 试点（LLM 提候选 + 确定性验证器，2026-08-14 闭环，+9 条）

用户授权"LLM 提候选 + 验证器强制过滤"边界调整。**协议演化**：v1（LLM 自找行号）
0 verified（推理模型 truncated 98 + 端点 504 61）→ 修 max_tokens 16000 + 深退避 →
v2 **5%**（10/200，12 小时）→ **v3 协议反转**（AST 预提取调用事实清单 + LLM 只选
index）→ **10.5%**（21/200）→ 导出 **9 条**（buffer 3 + centroid 1 + changeattributevalue 1
+ difference 1 + frompointxy 1 + frompolygonxy 1 + fromwkt 1；L3 全复用词汇表 130 既有类）。
cross-pool 0 抑制、loader smoke 通过。验证器 0 幻觉入库。**规模化外推**：T2 fresh 池
3,575 条 × 10.5% ≈ 导出 ~160 条。产物 `docs/reports/qgis_api_route1_train_only_v1/`、
`qgis_api_route1_pilot_v3/`。当前累计 **548 train-only**（539 + 9）。

## QGIS API mutation-only 池剩余 family 开采完毕（2026-08-10，+21 条）

- **批量 sink 不可证明**：addattributes+updatefields→addfeatures 校准 0/200
  （批量 addfeatures 列表循环动态累加）——**sink=addfeatures 的 9 个 family
  （252/216/157/114/63/53/45/33/32）永久关闭**。
- **addfeature（单数）开采**：63→4、117→19、45→5（addattributes 规则，
  QgsField 字面量+updatefields+addFeature）、setattribute→addfeature（182）→5
  （setAttribute(字段名,字面量值/别名) 新规则）、addattribute→addfeature（40）→0。
- **合并导出 21 条**（`docs/reports/qgis_api_addattributes_train_only_v1/`）：
  addattributes 19（L3_01_02_01/token 1，描述含字段名——突破"每组 1 条"压缩，
  33 fidelity→21 canonical）+ setattribute 2（L3_01_02_06/token 4）。cross-pool
  0 抑制；loader smoke 通过。
- **mutation-only 池 14 个 priority family 全部开采完毕，累计 +24 条
  （setattributes 3 + addattributes 类 21 + setattribute 类 2）**；
  **累计 539 train-only**（508 + 31 isolated：15-step 1 + polygon 3 + ct 1 + rect 2
  + setattributes 3 + addattributes 类 19 + setattribute 类 2）。


词汇表 129→**130**（L3_01_01_09/token 129）；校准 100 → 全池 153 → **4 complete
（2.6%，最低）** → 四层去重保留 **2 条 canonical** → BERT-128 + V4 smoke 通过。
导出 `docs/reports/qgis_api_rectangle_geometry_train_only_v1/`。deferred 主因：
extent 非构造/别名 46、sink 非字面量 72。**08-09 API 家族累计 +6 条（polygon 3 +
coordinate_transform 1 + rectangle 2），总计 514 train-only。**


校准 200 → 全池 370 → **27 complete（25 authority，7.3%）** → L3 复用
`L3_01_10_01 Project/Reproject`（token 100，无词汇表扩展）→ 27/27 描述过 →
四层去重保留 **1 条 canonical** → BERT-128（52 token）+ V4 smoke 通过。导出
`docs/reports/qgis_api_coordinate_transform_train_only_v1/`。deferred 主因：
transform 调用不唯一 136、sink 非字面量 113。


Processing 封闭后 API local macro 家族主攻的首个 family 已闭环：校准 200 → 全池 491 →
**43 complete（37 authority）** → stable129 L3 授权（`L3_01_01_08 Create Polygon
Features from Vertices`/token 128，词汇表 128→**129**，
`docs/reports/qgis_taxonomy_129_authority_v1/taxonomy_129_v1.json`）→ 43 条确定性
描述全过 → 四层去重保留 **3 条 canonical**（40 条 exact training-pair 压制）→ 对 508
池 cross-pool 0 压制 → BERT-128 + V4 smoke 通过（3/3、2 batches、loss/gradient
finite）。导出 `docs/reports/qgis_api_polygon_geometry_train_only_v1/`，SHA256=
`32e6035d…`；L3 授权 `qgis_api_polygon_geometry_stable129_authority_v1/`。deferred
主因：运行时顶点 179、sink 非字面量 207。产出 3 条（与 point/polyline 同量级，
四层去重是主要压制层）。

## QGIS L3 词汇表权威（2026-08-08 固化）

**唯一权威词汇表 = 128 个 L3 content tokens（0-127）**，固化于
`docs/reports/qgis_taxonomy_128_authority_v1/taxonomy_128_v1.json`
（SHA256=`45860335…`，128 类全部含名称/描述、token 连续无缺口）。
构成：stable101 的 101 + stable106/108 加 17（token 101-117）+ stable120/121/124
加 6（118-123）+ stable125-128 加 4（124-127）。
**所有 L3 存在性检查、mapping 校验、token 分配一律以此文件为基准**；
94/101/107/114 体系（v2_94_stable、stable101_taxonomy、qgis_l3_v1_114、
v3_107_experimental）全部降为 superseded 历史口径，不得再用作判定基准
（此前的 ruggednessindex/basicstats 误判即因误用 stable101 taxonomy 基准）。

## QGIS Processing Driver v2（2026-08-08 完成执行）

Processing 转换主线已完成 v2 全链路执行。全部 8,466 条 source authority 都必须过
driver，禁止在 source 级做差集跳过。**helper 内联路线已正式终止**（v1/v1.1/v1.2 三轮
全池 0 命中；真实语料 helper 形态与可静态证明白名单的鸿沟无法弥合，继续扩展将触碰
Batch-3 已证明低收益的分支唯一性区）。

真正的卡点是 **mapping authority 落后**：全池 replay 原用 stable110 时代 mapping（153
算子），升级到 stable124 composed（168 算子，含 stable120/121/124 delta）后解锁存量。
升级过程中修复了 authority 污染（composed 含 2 条指向不存在 L3 的映射已移除）与
route 对齐契约（`call_sites=None` 全量提取被误判 unaligned；修复为接受
`all_literal_calls`）。

执行结果：全池重放（direct 100→147、defer_mapping 7,913→7,255）→ 解锁批次 520 候选
→ 50 条 source-disjoint 审计（0 错拼/0 截断）→ 12 条 canonical。**正式 Processing
authority 保持 294 行**（12 条 canonical 经核对与 294 链+L3 完全相同、仅描述不同 =
0 新任务，按用户决策不并入，保留为 isolated 描述变体）；全 QGIS aggregate 为 508 行。
冻结双参照面为 `docs/reports/qgis_processing_conversion_v2_freeze_v5/`（508 unique /
294 overlap）。全部产物见 `docs/reports/qgis_processing_stable124_unlock_v1/`。
**更正记录（2026-08-08 晚）**：曾误判 `ruggednessindex`/`basicstatisticsforfields`
两条映射为"指向体系外 L3"并撤销 4 行——实为误判（L3_04_02_02=token 110、
L3_01_08_04=token 113 均为正式类，505 训练包含 basicstats 行），已恢复映射（composed
170 算子）与 4 行；302/306/516/520/freeze_v3/v4 均标记 superseded，最终 authority
为 294/508/freeze_v5（撤销 sidecar 标记 `restored_false_positive_revocation`）。

## QGIS 权威口径更正

本文先前的 454/455 行入口和 geometry-difference 29/2 口径来自已过期的并行分支，均已
被替代。495 条入口进一步通过 stable127 的严格 polyline-geometry local macro 扩展净增 3 条。
因此当前唯一正式 V4-128 train-only 入口为
`docs/reports/qgis_train_only_v4_128_498_v1/`，共 498 条，SHA256 为
`7aa61adddf5faa0ea77ed74be4df8a65d5dbbf35b271c214e1bb032cc8dec5e9`。
495/492 条入口、旧 455 条包和 geometry-difference v1/v2 均只保留为 superseded provenance，
不得作为训练 authority。

当前 API 扩展已完成 point-geometry 200-source 校准：200/200 source SHA 核验通过，193 个
normalized-body authority，107 条严格 complete macro（102 个 complete authority）和 93 条
fail-closed deferred；calibration/holdout 的 source SHA 与正文 authority 交集均为 0。complete
macro 分为 57 条 coordinate-constructor 与 50 条 prebuilt-point。coordinate-constructor
中的 55 条严格坐标对已完成 stable126 审定；prebuilt-point 50 条仍未授予 L3 或训练准入。
`L3_01_01_04 Create Points from Table` 只在证明坐标来自表格字段时才适用，不能覆盖整个
family。权威产物：`docs/reports/qgis_api_point_geometry_calibration_v1/`、
`qgis_api_point_geometry_replay_v3/`、`qgis_api_point_geometry_payload_census_v1/`。
stable126 以最少补充新增 `L3_01_01_05 Create Point Features from Coordinates` / token 125，
仅适用于 `point factory -> same-feature setGeometry -> sink` 的 source-verified local macro。
55/55 条中文描述均只使用源码事实并通过 fidelity，未调用 LLM；四层去重压制 52 个完全相同
训练对，保留 3 条，且相对 492 条基线跨池重复为 0。495/495 通过真实 tokenizer 和 V4
loader/loss/backward，未训练、未写 checkpoint、validation/test=false、production merge 未授权。
权威产物见 `docs/reports/qgis_api_stable126_authority_v1/`、
`docs/reports/qgis_api_point_geometry_train_only_v1/` 和
`docs/reports/qgis_train_only_v4_128_495_v1/`。

下一 API family `polyline_geometry_construction` 已完成 source-disjoint 边界门禁：200 条源码
校准中有 9 条 complete calibration、9 条 complete holdout，source SHA/body authority 均无泄漏。
全池 replay 核验 611/611 条源码，保留 54 条严格 local macro、34 个 normalized-body authority；
其余 557 条继续 fail-closed。stable127 以最少补充新增
`L3_01_01_06 Create Polyline Features from Vertices` / token 126，仅覆盖
`fromPolyline/fromPolylineXY -> same-feature setGeometry -> literal sink`，不声称整函数语义。
54/54 条确定性源码事实描述通过，未调用 LLM；四层去重压制 51 条完全相同训练对，跨池后保留
3 条净新增。498/498 通过真实 tokenizer 与 V4 loader/loss/backward。权威产物为
`docs/reports/qgis_api_polyline_geometry_replay_v2/`、
`qgis_api_polyline_geometry_replay_v3/`、`qgis_api_stable127_authority_v1/`、
`qgis_api_polyline_geometry_train_only_v2/` 和 `qgis_train_only_v4_128_498_v1/`。

随后 WKT geometry family 的 200 条 source-disjoint 校准在收紧跨分支几何变换检测后保留
74 条完整宏、73 个正文 authority，calibration/holdout authority 零重叠；644 条全池 replay
核验 644/644 源码，保留 270 条完整宏、156 个正文 authority。stable128 最少新增
`L3_01_01_07 Create Features from WKT Geometry` / token 127，只覆盖
`fromWkt -> same-feature setGeometry -> literal sink`，不复用栅格格式转换类。270 条确定性
中文描述均通过；四层去重压制 263 条，跨 498 条池零重复，净增 7 条。该阶段 V4-128 入口曾
为 505 条（`qgis_train_only_v4_128_505_v1/`，SHA256
`13bb886d87ce8b487f7f45e80a155e592b8c937667b61cf835e7f121b952a97a`），505/505 通过真实
`bert-base-uncased` 128-token gate 与 V4 loader/loss/backward（16 batches，loss/gradient finite）。
未调用 LLM、未训练、未写 checkpoint，validation/test=false、production merge 未授权。
**当前正式全 QGIS train-only aggregate 为 508 行**
（`docs/reports/qgis_train_only_aggregate_508_v1/`，SHA256 `4d9e64af…`），= API 214 行 +
Processing 294 行；507/516/520 条入口均降为 superseded provenance。

## 隔离 LLM catalog 抽取（2026-08-10）

pilot 修复了 canonical literal 未进入 catalog options，以及 module-level
`processing.run(name, ...)` 漏掉先前静态赋值行两项协议问题。5-source 字面量复验的 5 个实际
发送 scope 为 9/9 locally-proved ID 完整返回、0 空响应；4 条动态/负例复验中静态别名正例返回
`native:joinattributesbylocation@115`，两个 external-parameter/wrapper 负例均 abstain。

这只证明 scope/binding 协议可修复，不证明 LLM 可恢复真正运行时 dynamic ID；主要增益仍是
确定性静态别名。LLM 继续是隔离的 candidate-only 辅助，禁止批量调用 8,466 source 或生成 L3、
描述、训练行、authority merge。证据：
`docs/reports/qgis_processing_llm_catalog_extraction_pilot_v2/literal_protocol_fix_5_v1/` 与
`docs/reports/qgis_processing_llm_catalog_extraction_pilot_v2/dynamic_binding_audit_4_v2/`。

## 当前主线

围绕论文主问题“自然语言任务 -> 可靠 QGIS 工作流算子链”，当前 QGIS 主线是把源码通过
可复现的确定性流水线转换为高质量 train-only 数据。正式聚合入口为 508 行全 QGIS aggregate，
其中 **Processing 当前正式 aggregate 为 294 行**
（`docs/reports/qgis_processing_aggregate_294_v1/`；302/306 建立在误判或 0 新任务变体上，
已标记 superseded）；其余是此前已完成的 API 历史交付。
`8,466` 是 Processing 源码 replay/来源核验覆盖数，绝不是已转换训练样本数。

Processing 500-1000 目标经 2026-08-08 复盘判定**当前能力下不可达**（剩余池全部封闭：空链 5,714 死区、单缺 729 的 L3 support<30、boundary 778 分层诊断后无可开采点、多缺 390 死区；295 行为能力上限）。**API 新 family 冻结已解除**——数据建设主攻方向切回低层 PyQGIS API local macro 家族（历史最稳定产出源）。第一轮 Processing
Batch-3 已从 995 个未准入 blocker parent 构建 200 个 source-disjoint authority：
`control_flow_if`、`control_flow_for`、`helper_alias_missing_edges`、`split_local_subworkflow`、
`dynamic_or_custom_operator_resolution` 各 40，calibration/holdout 各 100；normalized-body 与
source SHA 均零交集。服务器 `/home/yll` 已重新核验 200/200 当前源码 SHA，零缺失、零不一致。
该包只用于可复用规则校准，训练行=0。下一步是规则级 calibration/holdout -> 对通过规则的完整
family replay -> source-disjoint 随机审计 -> 描述/L3/四层去重/V4 门禁；不得逐文件生产审核。

Batch-3 结构评估已在服务器完成：200 个 authority 产生 366 个局部单元，其中 31 个结构上
eligible、335 个继续 fail-closed deferred，calibration/holdout 两侧 source failure=0。helper/alias、
split 和部分控制流出现候选；dynamic/custom 40 条仍为 `catalog_provider_resolution_pending`。
当前仍不授予规则推广、L3 或训练准入。评估产物：
`docs/reports/qgis_processing_batch3_calibration_v1/structural_evaluation_summary_v1.json`。

规则级双侧归并只允许三条规则进入整族 replay 候选：`recovery-connected-local-dag-v1` 为 3/5、
`recovery-multi-root-fanin-dag-v1` 为 4/4、`split-local-structure-v9` 为 12/3 个 eligible
unit（calibration/holdout）。995-parent full replay 已完成：491/491 parent 源码 SHA 通过，
产生 44 条候选、33 个 normalized-body authority；该结果仍不是训练数据。

已固化 `scripts/admit_qgis_processing_batch3_candidates.py` 并运行 authority 级 admission/dedup：
44 条全部通过基础字段和描述 fidelity，按同正文 authority、候选池内 exact training pair、既有
原 293 条 Processing 池 exact training pair 折叠后保留 5 条 canonical pending audit；11 条同正文
authority、5 条候选内重复、23 条既有池重复均进入 sidecar。按三条规则分层抽取 5 条
source-disjoint audit manifest，calibration/holdout normalized-body overlap=0，但尚未完成源码片段
人工审定，因此 training_rows_emitted=0，不能把这 5 条称为 train-only。最终带 hash ledger 的
准入包为 `docs/reports/qgis_processing_batch3_admission_v3/`。

5 条 canonical 的 `/home/yll` 源码片段审计已完成：3 条 accepted pending downstream gates，2 条
deferred（低层编辑穿插导致边界不完整；字段计算公式引用拼写错误字段）。3 条 accepted 使用源码
事实压缩描述后全部通过真实 `bert-base-uncased` 128-token gate（最长 80 tokens）以及 V4
loader/weighted-loss/backward（3/3，loss/gradient finite，未写 checkpoint）。独立 train-only 包为
`docs/reports/qgis_processing_batch3_train_only_v2/`，其中 3 条可作为下一批 Processing 训练数据；
尚未合并到正式 aggregate，validation/test=false、production merge 未授权。源码证据与裁定分别见
`qgis_processing_batch3_source_audit_v1/`、`qgis_processing_batch3_source_adjudication_v2/`。
旧池的 BERT-128 文本门禁也已批量修复：33 条过长描述经确定性 `task name + ordered operator
run-length` 源码事实压缩恢复，2 条超长链继续 deferred。将恢复后的旧池与本批 3 条合并后，
`docs/reports/qgis_processing_aggregate_294_v1/` 的 294 条均通过真实 BERT-128（最长 127 tokens）
和 V4 loader/weighted-loss/backward（294/294，19 batches，loss/gradient finite）；未训练、未写
checkpoint，validation/test=false、production merge 未授权。随后对 stable124 历史候选的 7 条
canonical 做服务器源码审计，7/7 SHA 一致，5 条边界可接受、2 条 deferred；但五条可接受候选
均与当前 294 条池存在相同 `source_sha256` 和 `normalized_dag_key`，所以被跨池四层去重全部
压制，净新增为 0。此前临时 299-row 包和 pre-fix 5-row 导出均已标记 superseded，绝不可使用。
导出器现将 stable token authority 与 operator-to-L3 mapping 分离，并强制校验 source region、
call graph、normalized DAG 和 training pair 四类跨池重复；source SHA 只用于来源核验和
source-disjoint，不单独压制同一脚本内可能不同的局部工作流。

先前“剩余 Processing family 没有同时满足 support>=30”的结论只关闭了旧窄签名搜索，不能
解释为 Processing 完成或切换 API 的许可。validation/test、production merge 和模型训练仍关闭。

第一轮 319 个已核验子池之外的剩余 blocker authority 已完成同一套精确 provider 重锚定与结构
census。343 个选中源码中 323 个通过服务器 SHA 核验，20 个缺失源码继续 fail-closed；其中 93 个
`qgis:<slug>` 到 `native:<same slug>` 的迁移均由 AST 独立证明。剩余 recovery 与 split parent 分别
产出 6 和 94 个局部单元，但通过严格边界和描述门禁的只有 1 个，其 normalized-body support=1。
230 条剩余 operator-resolution 来源含 222 个 normalized body、124 个精确 canonical 算子序列簇；
最高 support 仅为 `native:mergevectorlayers` 的 11，其次是 `native:fieldcalculator` 的 10。这些
算子序列尚未恢复任务边界，明确不具备 calibration 准入资格。没有任何 family 达到 support=30 的
source-disjoint calibration 门槛；未授予训练、L3、描述或导出准入。权威产物：
`docs/reports/qgis_processing_expansion_remaining_census_server_v1/reanchored_family_census_v2/`；可复用
census 入口为 `scripts/census_qgis_processing_reanchored_families.py`。

不重扫上述 343 条的独立 blocker intake 已完成：排除正式 294 条与已扫描的 360/343 个 source SHA 后，
只保留 `call_sites` 和 `operator_sequence` 完全一致的真实调用证据，得到 297 个簇。6,408 条无调用证据、
365 条数据库/纯 support-export 操作均 fail-closed；没有安全簇达到 `support>=30`，selected/training 行均为 0。
初版 126 条 PostGIS 导入 selection 已为 superseded provenance。此结论只关闭精确整链 signature；下一步从独立
call-bearing 来源恢复局部子工作流边界再聚类，禁止重扫 343 条。证据：
`docs/reports/qgis_processing_independent_blocker_intake_v2/`。

该独立人口的全池 local-boundary replay 已完成：678 个安全 source representative 中 624 个服务器 SHA
核验并恢复，530 个 `qgis:<slug> -> native:<same slug>` 迁移经 AST 精确证明；得到 1,952 个局部单元、623 个
多步单元、47 个结构完整单元（33 个独立源码）和 331 个边界签名簇。最高结构签名 support=13 但混合不同算子链，
最高精确 canonical 局部链 support=8；16 个超 64-call 的 deferred 来源不可能将任一族推至 support=30。因此
source-disjoint calibration、L3、描述和训练行继续为 0。本轮关闭独立 call-bearing 人口的 boundary-signature
路线；下一入口必须是不同的 source-backed subpopulation 或新的 helper/output-alias/dynamic-ID 恢复能力。
权威证据：`docs/reports/qgis_processing_independent_local_boundary_replay_v1/replay_v6/`。

随后新的 source-backed 静态恢复 census 排除 1,565 个正式或已扫描 source SHA256，在只读 `/home/yll` 上
replay 6,820 个剩余 `deferred_mapping`/`deferred_operator` 来源。仅接受 AST 可证明的常量别名、固定字典 key
和固定 list/tuple 索引；运行时索引、多值分支、registry/wrapper 调用、catalog miss 和缺失源码继续 deferred。
该规则恢复 57 个 direct static chain，记录 55 个 helper 证据和 3 个 strict output-alias 证据，但 complete
local unit 只有来自 2 个 source 的 3 个。不存在 source-disjoint support family，故 calibration、L3、描述和
训练行均为 0。全量证据 ledger 仅在服务器，本机只镜像 summary/hash：
`docs/reports/qgis_processing_static_recovery_census_v1/`。下一能力必须恢复真实跨 helper 参数/结果传播或单路径
dynamic ID，并在 calibration 前证明完整局部边界；结构相似性继续禁止作为训练标签。

`task_plan.md` 按 GEE 数据处理、QGIS 数据处理、评测集建设三个独立板块维护。GEE 和
评测集可以同步推进，但不得覆盖或暂停上述 QGIS 主线。

本 agent 当前职责仅为 QGIS source-to-training-data conversion：负责 8,466 条 Processing
源码和 39,386 条低层 PyQGIS API 源码的 source replay、任务边界恢复、L3 映射、描述
fidelity、去重和 train-only 准入；不负责 GEE 数据或评测集建设。

## 最新已验证状态

- **2026-08-08：Processing 正式 authority 保持 294 行**。12 条 stable124 解锁 canonical（520 候选 → 50 条 source-disjoint 审计 0 错拼/0 截断 → 12 条）经核对**全部与 294 既有行算子链+L3 完全相同，仅描述不同（新压缩模板 vs 旧模板）→ 0 新任务**；按用户决策不并入（306 标记 superseded 回退 294；12 行保留为 isolated 描述变体，见 `train_only_v1/decision_note_v1.json`，供 MR 式多描述使用）。
- **2026-08-08（晚）误判纠正**：曾误判 `ruggednessindex→L3_04_02_02`、`basicstatisticsforfields→L3_01_08_04` 为"指向体系外 L3"（判定基准误用 stable101 taxonomy + added_l3，漏了 stable106/108 加入 existing_code_to_id 的 token 101-117 类；L3_04_02_02=token 110、L3_01_08_04=token 113 实为正式类，505 训练包含 basicstats 行），据此撤销 4 行并移除映射——**已确认误判并恢复**：composed 恢复 170 算子、4 行恢复、撤销 sidecar 标记 `restored_false_positive_revocation`；302/306/516/520/freeze_v3/v4 均标记 superseded。教训固化：L3 校验只用 128 权威注册表。
- **2026-08-08：全 QGIS aggregate 为 508 行**（API 214 + Processing 294），`qgis_train_only_aggregate_508_v1/`，SHA256=`4d9e64af…`；507/516/520 均降为 superseded。冻结双参照面为 `qgis_processing_conversion_v2_freeze_v5/`（508 unique / 294 overlap，SHA256=`13debc60…`）。
- **2026-08-08：helper 内联路线终止**（v1/v1.1/v1.2 三轮全池 0 命中）。真实语料 928 条 helper+processing 双特征行中，白名单（单 run helper/线性体/多链）与真实 helper 形态（控制流/表达式/嵌套/副作用）鸿沟不可弥合；继续扩展将触碰 Batch-3 已证明低收益的分支唯一性区。全池 215 条空链归因：87 条为 **catalog 外第三方 provider 算子**（umep/pff/trendsearth 等，16 条混有 QGIS 原生算子但整链含第三方）——永久 deferred，不可解锁；128 条真空链（无 processing 字面量调用）deferred。
- **2026-08-08：mapping authority 升级**。replay driver 的 mapping 从 stable110（153 算子）升级到 stable124 composed（170 算子，严格超集无 remap）；修复 route 对齐契约（`call_sites=None` 全量提取被误判 unaligned，接受 `all_literal_calls` 后与旧流程行为一致）。gap 统计：恢复后 472 个缺失算子（ruggednessindex/basicstats 已非 gap），raw support≥30 仅 4 个（deleteholes/stringconcatenation/package/orderbyexpression），normalized-body 口径均 <30，按最少补充原则**不补 L3**，仅保留观察清单（`empty_chain_and_gap_diagnosis_v1.json`、`mapping_gap_prioritization_v1.json`）。
- API 主线已完成首个可推广 family：102 条 field-schema replay 经宏合同、空间高层语义和源码作用域门禁缩为 67 条严格池，固定 20 calibration + 20 holdout，source SHA/body overlap 均为 0。源码 AST alias 全量重放得到 52 条完整局部宏、11 条缺 memory-layer constructor、3 条链不完整、1 条多链歧义；所有不完整或歧义记录继续 fail-closed。整函数单 L3 映射在 calibration/holdout 仅通过 5/20、6/20，会截断 split/import/calculate/sample/export 主任务，已正式否决。
- stable125 仅恢复 legacy 350 中已有的 `L3_01_01_01 Create Feature Class` 为 token 124，stable124 token 0–123 不变；authority 只适用于 source-verified local macro `QgsVectorLayer(..., "memory") -> schema -> optional prepared features -> writer`，`whole_function_semantics_admission=not_granted`。52/52 条 source-fact-only 描述通过，未调用 LLM；四层去重保留 28 canonical、压制 24 exact training-pair duplicate。跨 304 条既有 QGIS 训练池重复为 0，正式 JSONL 位于 `docs/reports/qgis_api_create_feature_class_train_only_v1/`，SHA256=`17cb1de9fbf469ca7cd8e4d9decdcedfd0070088160712533721e12b2d13809e`。真实 V4 loader/weighted-loss/backward 覆盖 28/28、7 batches、loss/gradient finite；未训练、未写 checkpoint、validation/test=false、production merge 未授权。
- `Vector File Export` family 已完成规则校准一次与全池重放。60 条 source-disjoint calibration/holdout 中 24 complete、36 fail-closed，complete FP、链截断和静默 fallback 均为 0；同一解析器对 211 条严格候选完成 211/211 源码 SHA 验证，得到 83 complete 与 128 deferred。83/83 source-fact-only 描述通过且 `llm_called=false`；四层去重保留 18 个训练对、压制 65 个 exact duplicate，复用 stable125 既有 `L3_07_04_01`/token 67。相对 332 条既有 QGIS 池跨池重复为 0；正式包为 `docs/reports/qgis_api_vector_file_export_train_only_v1/`，JSONL SHA256=`09f3d62ee14159f903a1f3b23d4be5e029e50d9d20401b9228bedbf93e19fa14`。真实 V4 loader/weighted-loss/backward 覆盖 18/18、5 batches，loss/gradient finite；未训练、未写 checkpoint、validation/test=false、production merge 未授权。
- `Add Field -> Calculate Field` 已完成规则收紧、全池重放和独立交付。3,190 条 Add Field sidecar 中 66 条进入该 family；v2 规则得到 30 complete macro / 28 normalized-body authority，并 fail-closed 22 条无同要素更新链、5 条相邻 schema mutation、3 条跨图层/空间计算和 6 条同字段下游变换。14/14 calibration/holdout 覆盖全部 complete authority，source SHA/body overlap=0，观察到的 FP 与链截断均为 0。30/30 source-fact 描述通过且 `llm_called=false`；四层去重保留 15 个训练对、压制 15 个 exact duplicate，相对既有 350 条跨池重复为 0。正式包为 `docs/reports/qgis_api_add_calculate_field_train_only_v1/`，JSONL SHA256=`23b14847d29470aba97817491adc085911d944298376965c048be9253dafd47a`。真实 V4 loader/weighted-loss/backward 覆盖 15/15、4 batches，loss/gradient finite；自动 family 推广因正文 support=28<30 仍未授权，但完整 authority 人口已审核，因此只授予本批 bounded train-only，未训练、未写 checkpoint、validation/test=false、production merge 未授权。
- `Raster Calculator` 与 `Set CRS Metadata` 两个 source-verified API family 已分别交付 83 条和 35 条 train-only。两批 source-disjoint 审核均为 20/20、source SHA/body overlap=0、FP=0、链截断=0，且相对各自既有池跨池重复为 0；真实 V4 loader/loss/backward 分别覆盖 83/83 与 35/35。Raster File Export 因格式契约混合继续 deferred。
- 修正版 Existing-Layer Add Field bounded batch 已闭环。2,651 个预筛 authority 经同 scope/control path/layer alias 和同一次 `updateFields()` 前完整 schema commit 规则只恢复 30 个完整单元/23 个 normalized-body authority；旧 v1 链截断人口不复用。15/15 calibration/holdout 覆盖全部 30 个 candidate unit，source SHA/body overlap=0、FP=0、链截断=0。30/30 字面字段名描述通过，复用 `L3_01_02_01`/token 1；四层去重保留 24 条、压制 6 条，相对既有 483 条跨池重复为 0。正式包 JSONL SHA256=`320bce3f65d6e8573c20f32999000ebe43f88c017cc73954ca0803e2c9288c78`；V4 smoke 24/24 通过。support=23<30，因此只授权 bounded batch，不推广整族规则。
- `geometry_difference` bounded batch 显式绑定冻结 anchor 的 31 条 `resolved_local_call_chain`，31/31 服务器源码 SHA 验证通过。控制路径修正后 29 条/17 authority 为完整 `difference -> setGeometry -> writer/sink.addFeature` 局部宏，2 条因 `convertToMultiType()` 继续 deferred；calibration/holdout 的 source SHA/body overlap、观察 FP 和链截断均为 0。29/29 确定性描述通过，四层去重压制 28 个 exact training-pair duplicate，跨 454 条池重复为 0，净新增 1 条；不授予 support<30 的自动 family 推广。权威产物为 `docs/reports/qgis_api_geometry_difference_replay_v2/`、`qgis_api_geometry_difference_source_review_v2/` 和 `qgis_api_geometry_difference_train_only_v1/`。
- 剩余 mutation/export census 的下一 family 选择已完成排除：6 个 semantic anchor 的 authority support 为 24/18/16/15/13/8，均未达 30；7 个表面 support=30–40 的组只是 `x/y`、`geometry/boundingBox/center` 和旧式参数读取等通用调用共现，混合多个任务，不能映射为训练算子。下一步必须回 13,554 条 pattern candidate，按 producer + mutation + sink 复合 terminal macro 重新聚类，而不是继续使用单调用/共现 support。
- 旧九包 507 条 provenance 与 455 条 V4-128 入口均只作为 superseded 历史证据；当前正式入口为上文 stable127 的 498 条包，validation/test 与 production merge 的关闭边界不变。
- 507 分层抽检已完成。50 条 calibration/holdout 各 25，source SHA/authority overlap=0；服务器只读 replay 验证 50/50 文件、SHA、解码、AST、source span 和 1,689 行 evidence。语义复核得到 40 条 `accepted_v4_128_audit`、10 条 `deferred_text_truncation`；任务边界、描述 fidelity 和 stable125 operator/L3 对齐失败均为 0。权威证据为 `docs/reports/qgis_train_only_aggregate_507_audit_v1/`。
- 当前 Processing 权威交付已升级为 `docs/reports/qgis_processing_delivery_293_v1_source_verified/` 下的 293 行 train-only 包。动态/空 operator-ID 的 445 条子池按 stable124 重放后得到 53 条候选、10 条 canonical 和 43 条 exact training-pair duplicate；10 条均通过源码 SHA、call-site、参数 provenance、描述 fidelity、stable124 L3 和跨池四层去重，没有授予新规则签名。293 个 sample ID、source region、call graph 和训练对均唯一，覆盖 237 个 source SHA、209 个 normalized DAG、170 个 operator sequence 和 150 个 L3 sequence；JSONL SHA256=`bc82877b644072dc803b63563a8ecbef0deb65374b73ac50f86404d845a9ed58`。真实 V4 loader/weighted-loss/backward 覆盖 293/293、19 batches，loss/gradient finite；validation/test=false，production merge 未授权。旧 283 行包降为 superseded provenance。
- 旧 Processing 窄 family 搜索的 deferred authority 为 parameter/result/output/backward/immediate/helper=18/22/16/25/23/14，true cross-function=5；`control_flow:for` 的安全 fixed-small-independent 子族仅 3。它只说明旧签名未产生 support>=30 的整族恢复，不关闭 Processing。新的 Batch-3 以五类 blocker 的 200-authority source-disjoint 校准恢复批处理规则，API 新 family 在 Processing 500–1000 交付前冻结。产物：`docs/reports/qgis_processing_batch3_calibration_v1/`。

- Processing 任务边界全池重放现已冻结在 splitter v9：同一组 hash-frozen stable124 输入覆盖 995 个 blocker parent 和 173 条 direct，source failure=0。same-if、downstream/sink、`QgsProcessingUtils` 和 output-alias 结论均已闭合，不再作为活跃工作。权威产物为 `docs/reports/qgis_processing_boundary_families_v2_condition_evidence/`、`docs/reports/qgis_processing_same_if_calibration_v1/` 和 `docs/reports/qgis_processing_downstream_transform_census_v1/`。
- stable124 只新增原 350 体系已有且与 QGIS 3.28 catalog 逐项同义的 `Define Projection`、`Flip Line` 和 `Split by Attribute`，token 121–123，旧 token 0–120 不变；83 个源文件 SHA 验证通过，normalized-body support 分别为 11、12、22。该 mapping authority 将固定 provider ID 的精确映射与 extraction signature 的 support>=30 自动推广门禁分离，不能据此自动准入训练。3,163 行 replay 将 mapping-complete 从 984 提升到 1,012；全池得到 570 条严格候选，新增 12 条全部是既有训练对重复。剩余 7 条 canonical 通过显式 candidate-ID、服务器源码/描述重放的 canonical calibration batch 准入，未授予新规则签名；authority 位于 `docs/reports/qgis_processing_stable124_authority_v1/`、`docs/reports/qgis_processing_stable124_full_population_v1/` 和 `docs/reports/qgis_processing_stable124_canonical_adjudication_v1/`。
- stable121 遵循最少补充原则：`qgis:voronoipolygons` 新增 `L3_02_07_07`/token 120，`native:removeduplicatesbyattribute` 复用既有 `L3_01_05_04`/token 102；`native:boundary`、`native:convexhull` 和 `qgis:linestopolygons` 因 normalized-body support<30 继续 deferred。3,163 行 replay 得到 fully-normalized 1,536、mapping-complete 984、direct 173；全池得到 558 条严格候选、13 条 canonical。13 条中 6 条命中 stable120 v5 已批准的精确双侧规则签名并导出，7 条未见签名继续 deferred；未逐行放宽、未调用 LLM、未训练。authority 位于 `docs/reports/qgis_processing_stable121_authority_v1/`、`docs/reports/qgis_processing_stable121_full_population_v1/` 和 `docs/reports/qgis_processing_stable121_train_increment_v1/`。
- stable120 遵循最少补充原则：`native:createspatialindex` 新增 `L3_01_07_01`/token 118，`native:snapgeometries` 在 51 个独立 normalized source body 证据下新增 `L3_02_07_09`/token 119，`native:saveselectedfeatures` 复用既有 `L3_07_04_01`。`native:serviceareafromlayer` 与无条件 `grass7:v.clean` break/snap alias 继续 deferred。3,163 行 replay 得到 mapping-complete 982、direct 173；authority 位于 `docs/reports/qgis_processing_stable120_authority_v1/`。
- stable120 v5 全池 replay 对 952/952 recovery/split/operator-resolution parent 与 173/173 direct 完成源码验证，0 source failure；`deterministic_operator_dag_zh_v5` 在不放宽 fail-closed 门禁的前提下恢复安全函数形参和同作用域支配性派生值。全池得到 530 条严格候选、61 条 canonical candidate、126 条 source-region duplicate 和 343 条 exact training-pair duplicate。seed=20260803 的审核包含 calibration/holdout 各 50 条，source SHA 和 normalized-body authority 均零交集；只批准 3 个 support>=30 且双侧覆盖的精确规则签名，导出 55 条增量。合并后的 270 行包通过真实 V4 loader/weighted-loss/backward 270/270、17 batches，loss/gradient finite；未写 checkpoint、未训练、未调用 LLM 生成描述、未合并生产数据。权威候选包为 `docs/reports/qgis_processing_stable120_full_population_v5_policy_v1/`。
- QGIS Processing-resolution 权威池为 8,466 条，源码 8,466/8,466 SHA verified，0 个源码失败。
- Processing 全量 source replay 已覆盖 8,466/8,466 个唯一 source SHA；feature extractor v8 得到 direct 100、recovery 222、API sidecar 203、mapping defer 7,913、unparseable exclude 28。该结果只用于路由审计，训练行=0。
- 已新增统一入口 `scripts/run_qgis_processing_batch.py`，以 8,466 authority 和 full replay v2 为基底，只按 `(record_id, source_sha256)` 覆盖最新 stable110/correction 3,163-row replay，并串联确定性描述、四层去重和既有 train-only authority。200 条分层校准先覆盖全部 129 条 latest direct 和 38 条既有 accepted；自动身份/链/泄漏门禁通过后，同一冻结输入完成 8,466 条全池 replay。最终唯一状态为 accepted 38、deferred 8,284、duplicate 70、excluded 74；细分为 boundary 612、operator 387、mapping 7,261、description fidelity 22、source replay 2、alignment exclude 50、unparseable 24。35 条 direct accepted 与最新 operator/L3 链完全一致，0 条不确定记录进入训练。权威产物为 `docs/reports/qgis_processing_unified_replay_v1/`；该校准只证明批处理状态机和准入不变量，不声称新增规则的人工语义 precision。
- 757 条 blocker 已全部只读重放，757/757 source SHA verified、0 source failure。v10 修复 driver 漏载 `native:extractwithindistance` existing-L3 authority 后成为当前 blocker authority：166 candidate / 45 canonical / 121 duplicate、130 fully-normalized mapping-complete、218 partial mapped-subset；该池只含 custom caller，未直接生成训练行。corrected custom implementation replay 覆盖 8,471 个唯一 source、97 个 variant，将 complete/scope parent 从 7/7 提升到 9/9；3 个 scope candidate 中 2 canonical、1 duplicate，质量门禁后导出 1 条 6 步 `filterstructures` train-only。权威报告为 `docs/reports/qgis_processing_operator_expansion_v1/report_v2.md` 和 `docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping/report_v1.md`。
- stable110 existing-L3 alias 批处理已完成：9 个 mapping authority 覆盖 21 条单缺口记录；3,163 行全池 replay 将 direct 提升到 150。本轮新增 17 条 direct 中只有 9 条通过确定性描述 fidelity，去除 3 条缺失源码、3 条 exact training-pair duplicate 后保留 3 条 canonical；3/3 源码 SHA/AST/call span replay 通过并导出 train-only。真实 V4 loader/loss/backward 覆盖 3/3，loss/gradient finite，未训练、未合并生产数据。该历史阶段累计 168 行，现已被上方 210 行 authority supersede；权威报告为 `docs/reports/qgis_processing_mapping_gap_stable110_alias_replay_v2/report_v2.md`。
- 对 73 条 description-deferred direct 完成 workflow-input provenance 全池重放：只允许可由 AST 证明来自 `parameters[...]` 或同作用域支配性 `parameterAs*()` 赋值的动态参数，裸变量、计算表达式、分支不支配赋值和字典 mutation 继续 fail-closed。描述 fidelity 从 77 提升到 97，新增 20 条中去除 1 条缺失源码和 13 条 exact training-pair duplicate，保留 6 条 canonical；6/6 source SHA/AST/call span 与真实 V4 loader/loss/backward 均通过。52-step 行的目标序列为 54<100，但其自然语言 prompt 为 1,955>128，现已从 V4-128 包 deferred。该历史阶段累计 174 行，现已被上方 210 行 authority supersede；权威报告为 `docs/reports/qgis_processing_runtime_parameter_replay_v1/report_v1.md`。
- 对剩余 53 条 description-deferred 完成 provenance census，并以 TDD 固化“支配性同作用域字面量别名 + 三类显式空默认参数”规则。阶段性新增 4 条后曾记为 178；后续语义复核撤销 `native:ruggednessindex` 和 `qgis:basicstatisticsforfields` 两条错误映射行，corrected custom-scope replay 再净增 1 条。当时的 177/178 口径现已被上方 210 行 authority supersede。撤销与新导出分别见 `docs/reports/qgis_processing_runtime_parameter_replay_v2_corrected/report_v1.md` 和 `docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping/report_v1.md`。
- corrected custom implementation resolver 使用 8,471 行源码索引查找定义，命中 167 个 instance / 97 个 implementation variant；8,471 不是 workflow 候选数。其 10 个 expanded complete、27 个 unresolved variant/16 family、4 scope candidate -> 2 canonical/2 duplicate、净新增=0 的结论，只关闭该 target-family 子问题，不能外推到全部 4,858 条 implementation/custom 记录。权威报告为 `docs/reports/qgis_processing_custom_implementation_closure_v1/`。
- 使用 corrected 153-operator stable110 mapping 重算 3,163 行旧 replay 后，fully-normalized mapping gap 为 726，而不是旧口径 708；其中仅 195 行结构 eligible，排除 142 行数据库副作用和 16 行 support/export 后，37 行 semantic review 折叠为 33 个 normalized source body / 18 个 feature signature。149/195 source SHA verified；46 行 source-unverified 全部为 sidecar（44 行数据库副作用、2 行 semantic deferred），不能充当 normalized-body support。现有 stable110 精确候选=0、训练行=0，该 lane 也已关闭。权威报告为 `docs/reports/qgis_processing_mapping_gap_stable110_closure_v1/`。
- 低层 API 强信号权威池精确为 39,386 个唯一 source SHA；未限制强信号的 broad layer 多 1 条，已排除。全量源码 AST 抽取 39,386/39,386 SHA verified 且 parsed，得到 235,795 个 API steps、13,554 个多信号 pattern candidate、25,832 个任务边界不足 deferred；L3、描述、去重和训练行均为 0。
- 最终 API 任务边界规则 `typed-terminal-control-path-dag-v4` 已完成全池 v6 replay：39,386/39,386 source SHA verified，37,901 个规范化源码主体，产出 2,708 个 candidate units（1,587 个 source authorities）和 2,327 个 deferred terminal units。新增边界 post-filter 后 L3 intake=2,707；旧 200 与新 calibration/holdout 200 的 393/393 真阳性全部保留、7/7 假阳性全部压制。
- stable110 API mapping census 已覆盖 2,707 条 intake：102 条含强语义 anchor，其中 75 条/59 个源码 authority 可完整精确映射到既有 Buffer、Intersect、Simplify、Feature to Point、Minimum Bounding Geometry；27 条 fail-closed，包括 output contract 不足 7、参数依赖 8、taxonomy 契约不匹配 10、taxonomy gap 1、任务范围不足 1；其余 2,605 条仅含 mutation/export 支撑步骤，不把 `setGeometry`、`setAttributes`、`addFeature` 当算法。
- 75 条 exact-L3 提案已完成 `/home/yll` 只读源码 replay：75/75 source SHA、AST、API call span 和参数验证通过，0 失败。确定性描述 fidelity 通过 74 条，1 条 `buffer(0, 1)` 几何修复惯用法 deferred；四层去重只保留 6 条 canonical、压制 68 条 exact training-pair duplicate。
- 6 条 canonical 与既有 118 条 QGIS train-only 行跨池对照后 0 overlap，已导出 6 条隔离 `qgis_api_training_sample_v1` train-only 行，覆盖 6 个源码 authority、5 个 L3 序列。真实 V4 loader/weighted-loss/backward 覆盖 6/6，loss/gradient finite，未写 checkpoint、未训练、未合并生产数据、未调用 LLM。
- 对 2,605 条 `mutation_export_only` 已完成 `control-path-caller-and-terminal-backward-slice-v4` 全池重放：1,429 条恢复到本地调用链、382 条分支歧义、51 条外部 payload、743 条没有可定位 `setGeometry`。743 条 terminal sidecar 中 support/custom-only=593、无本地链=109、歧义=41、已知几何语义候选=0。排除 158 条已审 family 后剩 2,447 条，完整 signature family=210，但 support>=30 新 family=0；mapping/description/training 均为 0。权威报告为 `docs/reports/qgis_api_unresolved_recovery_v1/`。
- 嵌套 centroid 的 52 条候选已完成严格 source-disjoint 闭环：正文归一化后 12 个声明 authority 折叠为 9 个，50 条边界完整、2 条因漏掉点面计数依赖而 deferred；25/25 calibration 与 25/25 holdout 的 source authority、source SHA、alias group、unit ID 交集均为 0。50/50 stable110 精确映射、源码 replay 和描述 fidelity 通过，四层去重只保留 1 个 canonical，且与既有 124 行 QGIS train-only 完全重复，净新增训练行=0。
- 44-authority geometry-return 扩展已完成。原 broad pool 为 85 条/44 个声明 authority；排除上述 52 条已审 baseline 后为 33 条/32 authority。规则 v2 将 2 条 `buffer -> WKB -> cascaded_union -> WKT` 与 1 条 `buffer -> difference` 链截断 fail-closed，并保留 8 条分支多定义 sidecar；剩余 22 条/18 个正文 authority 全部通过 source-disjoint 边界审核，calibration/holdout 各 11 且四类交集为 0。22/22 stable110 映射、源码 replay 和描述 fidelity 通过，四层去重得到凸包、缓冲区、质心、简化 4 个 canonical，但 4/4 均被既有 124 行训练池跨池压制，净新增训练行=0，未运行 loader/loss。
- authority-ranked 的下一族 `random_point_construction` 已以复合 API pattern 闭环，而非伪装为 Processing 算子。40 条/32 个 normalized-body authority 按 20/20 切为 source-disjoint calibration/holdout，source authority、source SHA、alias group、unit ID 四类交集均为 0。lexical-scope AST 恢复器同时验证双随机数、有界点数/迭代计数、点几何工厂、containment 与最小距离谓词、`setGeometry` 和声明 sink。40/40 通过源码 replay，并仅凭冻结 recovery provenance 映射到既有 `L3_02_06_06 Sample Points`（token 97）。按 5 个已核验 lexical scope 生成确定性描述，四层去重保留 5 个 canonical；与既有 124 行训练池均不重合，因此导出 5 条隔离 `qgis_api_training_sample_v1` train-only。真实 V4 loader/weighted-loss/backward 覆盖 5/5，loss/gradient 有限，未写 checkpoint、未训练、未合并生产数据、未调用 LLM。另一已复核 anchor unary-union 在 downstream-transform deferred 后只有 21 个 normalized-body authority，仍低于 support>=30 门禁。
- 剩余 mutation/export census 已正式关闭：control-path 等价分支、caller provenance 和 terminal payload 三类规则没有产生 support>=30 新 family，也没有训练行；unary-union 仍为 21 个 authority，继续 deferred。旧 v2 仅保留历史证据，当前报告为 `docs/reports/qgis_api_remaining_mutation_export_census_v4/` 与 `docs/reports/qgis_api_unresolved_recovery_v1/`。
- 已将分散的 107 unified、9 stable106、1 top20、1 correction、6 exact API、5 random-point 合并为 129 条零跨池重复 authority，并确定性分层选出 50 条首批 QGIS train-only 交付数据。50 条覆盖 6 个来源池、50 个独立 source SHA/source region/call graph/operator sequence/L3 sequence 和 41 个 L3 code；V4 loader/weighted-loss/backward 覆盖 50/50，loss/gradient finite，未写 checkpoint、未训练。39 条保留 `source_reviewed_evidence`，10 条为 `verified_sha256`，1 条为 carry-forward verified，不伪造 replay 状态。权威交付为 `docs/reports/qgis_train_delivery_50_v3/`。
- stable106 top-15 裁定冻结 5 个新 L3 和 1 个 stable101 alias；全池 mapping-complete 从 553 增至 700，direct 从 100 增至 125。
- stable106 新增 direct 经描述 fidelity、四层去重和源码 replay 后导出 9 条 train-only 增量；9 个唯一源码、9 个唯一 DAG，真实 V4 loader/loss/backward 覆盖 9/9，validation/test=false，production merge 未授权。
- stable106 新增 24 条 recovery 与 27 条 split 已完成只读服务器 replay；51/51 源码无失败，但结构门禁后只保留 2 条未准入候选，训练行=0。
- 7 个 existing-L3 mapping 已授予 source-reviewed authority；全池 replay 解锁 2 条 `native:rasterlayerstatistics` direct。2/2 描述 fidelity 通过，四层去重保留 1 条 canonical，1/1 source replay 和真实 loader/loss/backward 通过；只授权 1 条隔离 train-only，未训练、未合并生产数据。
- stable108 再授予 Smooth=`L3_02_05_02`/token 106 与 Delaunay Triangulation=`L3_06_01_02`/token 107；stable106 token 0-105 不变。全池 fully-normalized mapping-complete 754 -> 766、唯一链 268 -> 271，`defer_mapping` 2040 -> 2020，未新增 direct。
- 从 stable106 总口径看，87 条记录脱离 mapping gap，其中 66 条 fully-normalized，21 条 partially-normalized 继续 `defer_operator_resolution`。stable108-only 的 20 条变化为 recovery 2、API sidecar 6、alignment exclude 4、operator-resolution defer 8，训练行=0。
- stable108 authority/replay 重复构建全部逐字节一致，相关测试 15/15、token 0-107 连续唯一、3,163 个唯一 record ID 和零 replay 训练行断言通过。
- stable108-only 的 2 条 recovery 已完成只读服务器复核：2/2 source SHA verified，各恢复 1 个 `gdal:contour -> native:smoothgeometry` 局部单元，但均因 `control_flow:try` 与下游低层数据变换 fail-closed。两份源码只相差 7 行采集头，主体相同，canonical authority support=1<30；结构 eligible=0、训练行=0，只保留 sidecar。
- stable113 在更新防膨胀审计前曾冻结和重放，但 training/production 从未开放且训练行=0。Option A 已将其标记为 `superseded_historical_evidence_only`，token 110-112 退回未分配，其 direct 行保持关闭。
- stable110 基于 235/235 source-verified 审计，只冻结 `native:explodelines`=`L3_02_05_16`/108 与 `native:splitwithlines`=`L3_02_05_17`/109；二者 normalized source-body support 为 81/70。其余 5 类继续 deferred，`splitvectorlayer` 虽 support=32，但 multi-output 契约不可表示。
- stable110 先显式排除错误的 `native:lineintersections -> L3_02_05_06 Split Line at Point`，fail-closed replay 为 mapping-complete=775、唯一链=274、direct=127。独立 correction authority 根据 catalog、L3 契约和 59 条唯一源码证据，将该算子从 unmapped 恢复到既有 `L3_02_02_01 Intersect`；修复后为 791/282/129，不新增 L3/token。新增 2 条 direct 为 `9a7cdfe933736366640a4e1c`、`e452e53925dfe7c00eb2a1c4`，其末步现均为 Intersect。
- correction direct 已完成 train-only 闭环：2/2 确定性描述 fidelity 通过；四层去重保留 1 条 canonical、压制 1 条 exact training-pair duplicate；canonical 从冻结的 235/235 source-SHA-verified normalized-body authority carry-forward 1/1 source identity，并验证 4/4 缓存 processing call span。导出 1 条 `stable110` train-only JSONL，并以隔离 110-content-token 配置通过真实 V4 loader/loss/backward smoke；未修改生产词表、未写入 `outputs_v2`、未训练、未调用 LLM。
- GEE `mean_clip_core` 35 簇审核已完成：22 accepted / 13 deferred。原规则失败（precision=0.6286、Wilson lower=0.4634）；修复后的传递 provenance/类型门禁与人工 35/35 一致（TP/FP/TN/FN=22/0/13/0、precision=1.0、Wilson lower=0.8513）。
- deterministic task-text exporter 已覆盖全部 86 条 repaired-rule mean/clip definition，来自 24 个源码 authority。86/86 通过 source SHA、AST、依赖事实回指和 schema 门禁；按规范化文本+L3 去重后保留 27 条未准入 candidate，记录 59 条 duplicate。27 条中 26 条有唯一公开 ImageCollection，1 条使用泛化回退。风险优先的 20 条审核包覆盖该泛化行和全部 8 条省略未审核时间事实的 candidate；training/validation/test/production 仍全部关闭，训练行=0。

## 三条工作流的下一步

- QGIS 扩产主线（优先级重置）：先建立高召回、可审计的原始 `unclassified` 检测器（23,638 条），再做来源保持的 workflow/subworkflow 扩增和独立 operator-level 语义包；候选产率、准入率和覆盖增益先于固定行数目标。stable124 正式训练暂缓。
- QGIS 数据处理：当前正式 Processing authority 为 294 行、全 QGIS aggregate 为 508 行（Processing 500 目标封闭）。下一步：①全池重跑已完成（170 版 composed）：解锁批次 534 候选 → 15 canonical（13 条描述变体不并入 + 15 步链 1 条导出 isolated + 52 步链按先例 deferred）；87 条经核对为第三方 provider 算子，永久 deferred；②gap 观察清单（deleteholes/stringconcatenation/package/orderbyexpression）留待 support 证据积累后按最少补充原则独立决策，当前不补 L3；③**API 池（39,386）为主攻方向**：从剩余 13,554 条 pattern candidate 中按 producer+mutation+sink 复合 terminal macro 聚类选择下一个 support>=30 的 family，依次过 source-disjoint calibration、全池 replay、最少 L3、描述、去重、tokenizer、V4 门禁；Processing 剩余池保持封闭不再投入。所有新行必须依次通过 source-disjoint calibration、全池 replay、精确/最少 L3 契约、确定性源码事实描述、四层/跨池去重、真实 tokenizer 门禁和随机抽检。
- GEE 数据处理：共同审核 repaired-batch 的 20 条风险优先样本，逐项核对 dataset、temporal 与 retained-chain fidelity。任何不一致都返回确定性规则修复并全量重放；审核通过也不自动授予训练准入。
- 评测集：Gate 1、Gate 2 已完成。4 条 hash-bound 人工决定已通过状态机校验：`001/006/007` approved 并进入 Gate 3，`008` 因缺少 task intent/output constraint、无法证明长链语义闭合而 `returned_for_revision`。Gate 3 现为 149 条（146 source-backed + 3 expert-authored）、90 个 source authority、52 个 distinct DAG；仍仅 2 个 family 满足 8+3，状态为 `failed_insufficient_candidate_supply`。`L3_02_03_05` 是允许 dissolve/collect 等多个算子的语义类，不是一算子一类别。Gate 4、development/final/refusal 行和 family roster 继续关闭。详见 `docs/reports/qgis_benchmark_expert_human_approval_v1.md`。

## 硬性边界

- 正式主线不调用 LLM 猜链、补链或改链，不运行训练；经用户批准的隔离
  `qgis_processing_llm_candidate_extraction_pilot_v1` 仅允许提出带源码行证据的
  operator-ID 候选，必须经过 AST/catalog/单值证明，永不直接产生 L3、训练行或 authority。
  v2 pilot 必须逐条 source 本地 AST 解析，每次只发送一个有 Processing 证据、保留原始行号的
  有界 scope；禁止 whole-file 提交和静默截断。
  首个 5-scope 字面量基线的 catalog/span 校验为 TP=5、FP=0、FN=0，但五条均来自同一 source，
  只证明调用协议，不证明 dynamic/helper 恢复能力。
  source-disjoint 字面量 holdout 从只读 `/home/yll` 选取 10 条 SHA 验证 source；一次 AST 候选
  修正和一次有限重试后，8 条成功响应累计 TP=10、FP=0、FN=3（precision=1.0、recall=0.769），另有
  1 个 scope 因长度保护未发送、1 个 source 仍返回空 JSON。因此它仅是高精度但不完备的候选辅助，
  不能替换 extractor 或成为训练 authority 的入口。后续契约复验发现旧账本丢失模型返回的
  `source_lines`，已修复为 `proposed_operator_source_lines`；复验成功行号均在 scope 范围内。
  空 JSON 与超长 scope 继续单独记为 deferred。
- 不修改 `outputs/`、`outputs_v2/`、`train11397_*` 或 `/home/yll`。
- benchmark planner gold 只比较 parameter-free QGIS `processes + links`；Gate 3 未通过前不得伪造供给或进入 Gate 4。

QGIS 详细计划：`.omx/plans/2026-07-24-qgis-source-to-training-data.md`；评测集详细计划：
`.omx/plans/2026-07-28-qgis-benchmark-freeze-v1.md`。
## Stable124 实验 profile（2026-09-02）

已建立隔离的 `stable124_experimental`：主线副本 76,884 条，完整 28 条 curated
QGIS 样本仅追加到 train 后为 76,912 条；validation/test 索引保持一致。生成
124x256 embedding（前 94 行精确复用，新增 30 行固定 seed=124256）、124-ID 映射、
task vocab、length stats 和 manifest。profile 对应模型词表 128（含 4 个 special）。
baseline 与 +28 训练入口 dry-run 均通过 preflight；尚未正式训练或写 checkpoint，
生产 `v2_94_stable`、`outputs_v2`、508 authority、validation/test 和 benchmark 均未修改。
产物：`docs/reports/qgis_stable124_experiment_profile_v1/`。

## 数据角色定义（2026-09-02）

项目目标是**面向 QGIS 的 GIS 工作流生成**，不是要求 GEE/QGIS 数量或能力对称的
跨平台生成器。GEE 的主要作用是提供规模化、高质量的工作流监督，帮助模型学习通用
GIS 工作流的组合规律（算子顺序、前后依赖、多步链和常见模式）；QGIS 的主要作用是
提供目标平台的算子语义、矢量处理能力、输入/输出转换约束，以及 QGIS 算子之间的真实
组合监督。L3 是两类来源之间共享的算法语义表示层，最终输出仍以可执行 QGIS 工作流为
目标。

因此，QGIS 扩量按覆盖度而非与 GEE 的数字配平来衡量，至少要覆盖算子、L3 类别、矢量
处理、转换关系、输入/输出契约、链长度和任务语义。当前 stable124 实验的 76,884 条
基线行经实际 census 全部为 `ee.*` GEE 行，28 条 QGIS curated 行只追加到 train；
历史上的 8,283 应标为独立子集数字，不能替代当前基线总量。

## QGIS 数据生产加速主线（2026-09-02）

当前重点已从 stable124 A/B 配置转为提升 QGIS 高质量训练数据的生产率。生产顺序调整为：
首先对 23,638 条原始 `unclassified` 做确定性高召回 signature/调用检测，识别真实
Processing、API、wrapper 和局部 workflow；再从通过初筛的来源恢复 workflow/subworkflow；
随后建立独立的 operator-grounding 语料，最后才扩展 implementation/API family。已有
train-only/authority 资产作为基线和去重参照复用。LLM 只能在已有源码事实上的边界/任务
审核中作为有界辅助，不能作为无约束结构抽取主线。

每个批次必须输出 manifest-backed census、provenance、parent lineage、四层去重和
Gold/Silver/Reject/Deferred ledger，并统计新增行、接受率、人工审核成本、独立 source/
parent 数量、family 集中度和覆盖度增量。当前不把 2,000 设为硬承诺；先形成可重复的批次
产线和可测的 yield 提升。正式模型训练仍在该生产闭环之后。

## 资产语义标准化 v1（2026-09-02）

已实现 `scripts/normalize_qgis_assets.py`，作为 Asset Miner 之后的确定性语义准备层。它读取
candidate-only ledger，补充统一资产类型、词汇级操作提示、source/parent lineage、四层去重键和
下一道 gate 路由；操作提示不是 L3 映射。脚本始终输出 0 条训练行，不能修改 authority、validation、
test 或 production 状态。normalizer/miner 聚焦测试 7/7 通过；服务器已完成全量标准化：Processing
workflow=1,236、implementation=1,088、operator=591、dynamic=496，API semantic-unit=3,209、
pattern=4,880、implementation evidence=12,407、unresolved=23,945；47,542 行通过 SHA 校验。
报告：`docs/reports/qgis_asset_normalization_full_v1.md`。

第一条有界 review lane 已建立：`native:clip|qgis:multiparttosingleparts`（7 条 Processing workflow 候选）。
服务器审查包按 source SHA 确定性分为 calibration=3、holdout=4，7 个 source SHA 均校验通过，两个 split
无 SHA 重叠。当前仍是 candidate-only，没有 L3、训练、authority 或评测准入。报告：
`docs/reports/qgis_asset_family_review_clip_multipart_v1.md`。

该 packet 的确定性语义 calibration 已完成：7/7 通过 SHA、AST 字面量 ID/顺序、参数证据和跨调用结果别名依赖检查；
失败/延期均为 0，calibration/holdout SHA 无重叠，7 个 normalized template 均不同。这只验证恢复规则，任务保真度、
provider/I-O、L3、跨池去重和 Gold/Silver gate 仍关闭。报告：
`docs/reports/qgis_asset_family_semantic_audit_clip_multipart_v1.md`。

校准规则已应用到全量标准化 Processing workflow：1,236 条 workflow candidate（含两个 manifest pool 中的 Processing-shaped 资产）中命中 7 个 parent，
生成 7 条 family candidate；无多重命中 span，完整 parent 算子链只有 1 种。资格化预审显示 7/7 可由现有 L3 authority
解析，7/7 符合显式 vector I/O contract；任务保真度和跨池去重仍待审核。报告：
`docs/reports/qgis_family_expansion_clip_multipart_v1.md`、
`docs/reports/qgis_family_qualification_clip_multipart_v1.md`。

第一轮 Processing Family Census 已完成：全部 1,236 条 workflow candidate 产生 8,330 条 family 记录（support>=2；
exact=363、2-step=2,427、3-step=3,113、transition=2,427）。按支持度、source/structure diversity、L3 和 I/O
信号调度，下一轮首选 `native:dissolve → native:multiparttosingleparts`（support=86、source=40、parent structure=18，
L3/I-O 均可预解析），其次是 `native:buffer → native:clip`（support=54、source=36、structure=19）。此前
`clip → multipart` 仅作为 calibration baseline（support=7）。task/template 指标在语义审核前明确保持 unavailable。
报告：`docs/reports/qgis_processing_family_census_full_v1.md`。

已建立统一全池首轮召回 rollup：`scripts/run_qgis_full_pool_first_recall.py`。它强制以
逐行的 47,852-source census 为唯一分母，只有在提供 candidate/review ledger 后才计算
candidate recall 与 Gold/Silver yield；summary-only 文件不能用于声称召回率。当前工作区
没有保存服务器侧逐行 census，因此首轮全池 recall 尚未运行，不能提前填数字。

2026-09-02 已对完整的 8,466 条 Processing authority（不是抽样 100 条）执行首轮结构 replay，
产生 100 条 `auto_accept_candidate`；它们全部 source-linked。Processing 内 direct candidate rate
为 `100/8,466=1.1812%`。相对于 47,852 全池分母的 `100/47,852=0.2090%` 只是跨池 coverage
ratio，不是全池 candidate recall，因为 API 池尚未经过同一 replay。100 条尚未经过同一批次的
Gold/Silver 语义审核；历史 28 条仅作为未建立 linkage 的
observed yield（0.0585%），不能冒充本轮准入结果。执行产物：
`docs/reports/qgis_full_pool_first_recall_v1/first_recall_execution_v1.json`。
