# V2a 描述一致性验证（终版：100 样本全量判读，2026-09-16）

抽样：seed 20260916，与主审计同池（多步 + DAG 合法 + SHA 通过 + ≥2 可解析算子），确定性 100 条清单 `sample100_wids.json`；判读辅助 `scripts/show_wf_judgment_batch.py`
方法：逐条人工语义判读（描述 vs 解析后算子链），三层标准；机械正则层已弃用（r1 报告记录）

## 结果

| 判定 | 定义 | 数量 | 占比 |
|---|---|---:|---:|
| **Tier-1** | 描述真实 + 算子链承载任务主语义（多步逐步对应，如 W055935 "SAGA fillsinks → GRASS r.watershed → native:hillshade" 三步全对、W067992 "reproject→buffer→reproject" 完美对应） | **74** | **74%** |
| **Tier-2** | 描述真实无矛盾，但链欠承载（核心逻辑在纯 Python：如 W067118 chordal-axis 的 tessellate+skeleton 不在链上；W068052 的 Voronoi 缺失；或属性公式类任务链只见外围） | 26 | 26% |
| **Reject** | 描述与链/源码相悖（幻觉） | **0** | **0%** |

95% CI：Tier-1 [64.5%, 81.8%]；Reject [0%, 3.6%]。
源码回溯（r1 轮 3 条 + 判读中发现的可疑样本）：链条算子全部在 provenance 源码中字面出现。

## 三个判读中形成的结构性观察

1. **Export/PostGIS 家族高度可靠**：refactorfields→importvectorintopostgis 家族（W001977/W001982/W002006/W055691/W055712）全部 Tier-1，描述-链逐步对应——此类是干净监督
2. **"计算在算子里" vs "计算在 Python 里"是 Tier-1/Tier-2 的分界**：同是指标计算任务，W066913（advancedpythonfieldcalculator×5 承载 SPI 计算）判 Tier-1，W055730（statisticsbycategories 只承载外围）判 Tier-2——分界不是任务类型而是**链是否承载主语义**
3. **0 Reject 的含义**：2,265 行全部是"真实监督"（描述诚实、链真实、源码可回溯）；A/B 之争是**权重问题不是有效性问题**

## 对 2,265 的最终量化

| 口径 | 估计 |
|---|---:|
| Tier-1（强信号，全权重候选） | **≈ 1,676**（CI 1,461–1,854） |
| Tier-2（弱信号，降权重候选） | ≈ 589 |
| Reject（剔除） | ≈ 0 |

**Profile A（Tier-1 only）≈ 1,676；Profile B（Tier-1 全权重 + Tier-2 半权重）≈ 2,265 行、有效 exposure ≈ 1,970。**

## 交 owner 的 A/B 决策材料（本报告即决策输入）

- 两个 Profile 的差 ≈ 589 行弱信号（真实但链是任务算子的真子集）
- 判读记录保留全部 100 条 wid 清单，可复核查证
- spec（`docs/plans/v2a_spec.md`）已把 A/B 实现为可切换 data profile，切换只需 manifest 字段，不动训练/评测协议
