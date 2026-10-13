# A2 复审结论报告（v1，A2 关闭）

状态：A2_REVIEW_CONCLUDED / PROTOCOL_V1_0_FROZEN / SINGLE_ANNOTATOR_EXPLORATORY
日期：2026-10-10
依据：EVALUATION_PROTOCOL_V1_0_FROZEN + annotation_results_v2（SHA `d3fca732…`；v1 `5dbb4308…` 归档）+ V1_4 裁定表
指标明细：`A2_FINAL_METRICS_V2.json`

## 1. 复核后主指标（发布）

| 维度 | 一致率 | 判读 |
|---|---|---|
| **状态** | **606/676 = 89.64%** | 落于 80–90% 复审带；分歧全部归因（见 §3），无不可解释项 |
| **计数** | **623/676 = 92.16%** | ≥90% 目标线 |

主指标为冻结原始口径；未做任何剔除。

## 2. 修订执行

- annotation_results_v2：50 个单位修订（47 项队列 + C 组 5 项中 4 项实质变化；v1 归档未动）；
- 协议 v1.0 冻结（unconsumed 纯静态定义、图表参数语义规则、绑定/作用域计数、两层可达性）。

## 3. 剩余 70 项状态分歧——三个已命名错误族（全部可解释）

| 错误族 | 方向 | 代表案例 | 归属 |
|---|---:|---|---|
| **F-A：UI/图表消费对象的语义用途** | auto=analysis vs human=presentation_only | 101353 map1–12/面板族、217669 图例族、maxValue/maxMedian、collTOres_im_mean | 检测器局限：ui.* 命名空间 fallback 使纯展示消费调用判 analysis，连带输入变量判 analysis_chain（冻结规则按实际下游用途判 presentation） |
| **F-B：presentation 调用内的统计输入** | auto=presentation_only vs human=analysis_chain | 101051 regions/temps2013（seriesByRegion 的分区统计输入）、100133 binary/pop_pctsFiltSort/Ppctfills 族 | 检测器局限：无法识别 presentation 调用**内部**的统计语义（冻结规则判 analysis） |
| **F-C：可达性/下游有效性两层** | 双向 | 35821 illuminationCondition/illuminationCorrection（静态引用≠unconsumed）、SCSc_output（静态 return vs 语义无效返回的边界） | 检测器 pre-v1.0 unconsumed 定义 + 静态/语义边界（SCSc_output 建议保留 documented residual） |

计数分歧 53 项：F2 文件级绑定精度（34）+ repeat_var 绑定计数（9）+ 图表族（6）+ 可达性（4）——均属已登记的检测器已知局限，非人工错误。

## 4. 裁定执行记录

- 五项批复全部落实：year=29、101095:image=3、unconsumed 定义批准并写入 v1.0、maxValue/maxMedian=presentation_only（**语义状态修订**，计数 4 不变）、myRows/blank=presentation_only 确认；
- 证据核验：rescaled 采集器完整性证实（regex 交叉）；year 绑定级审计（5 声明同一顶层绑定、29 读取、无遮蔽）。

## 5. A2 关闭声明

1. A2 复审**关闭**：146 项分歧全部有 decision + 依据 + 修订记录；协议 v1.0 冻结；标签基线 v2；
2. 三个错误族（F-A/F-B/F-C）作为**已登记检测器局限**保留——按 owner 裁定**不再启动修复轮**；若未来需要，修复目标与判例已完备（本报告即规格）；
3. A1（候选发现暂时通过）/ A3（v1.1 冻结，92.02%）/ A4（insufficient_sample）状态不变；
4. 全部数值为**单人探索性**口径；入论文核心结论前须独立验证（owner 第 4 步预留）。

## 6. 回到毕设主线

后续优先级回归：**GEE 工作流监督 → 工作流推理能力验证；QGIS 算子 grounding → processes+links 工作流图生成**。本轮 A1–A4 检测器评估与校准作为数据质量基础设施归档：协议 v1.0、检测器 v1.1、标注 v2、六脚本试点、146 项裁定台账与审计包全部可复现。
