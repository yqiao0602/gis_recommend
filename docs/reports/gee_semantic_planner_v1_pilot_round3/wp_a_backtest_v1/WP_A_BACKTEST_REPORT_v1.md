# 工作包 A 检测器回测报告（v1）

状态：WP_A_BACKTEST_COMPLETE / SIX_PILOT_SCRIPTS_ONLY / NOT_TRAINING
日期：2026-10-09
授权依据：owner 裁定（2026-10-09）——实现 A1–A4 检测器，仅回测六个试点脚本。
设计依据：EXPANSION_DESIGN_V1.md（已按 owner 三处修订落实）。
产物：`wp_a_backtest_results_v1.json`、`wp_a_backtest_hash_ledger_v1.json`（同目录）。
代码：`scripts/run_wp_a_detector_backtest_v1.py`；单元测试 `tests/test_wp_a_detector_backtest_v1.py`（13/13 通过，合成 fixtures）。

## 1. 总体结果：A1–A4 全部通过

| 检测器 | 判定 | 关键锚点 |
|---|---|---|
| A1 外部预绑定候选 | **PASS** | 六脚本已知外部变量全部进入候选集；in-source 声明变量零误报 |
| A2 死代码/后继使用 | **PASS** | pi_all = 0 uses → unconsumed；Fire_Sus = 11 uses → analysis_chain |
| A3 展示层分类 | **PASS** | 269131 全部 ui.Chart 调用归 presentation，0 个进 unknown 队列（C2 锚点）；未知 API 一律进人工复核队列，不默认 analysis |
| A4 重复边去重 | **PASS** | 269131：40 原始记录 → 38 逻辑边（2 组合并，via 冲突双保留）；其余 5 脚本 0 合并 |

## 2. 回测中发现的三处 ground-truth 修正（重要）

回测的真实价值：检测器以源码为准，暴露了冻结试点记录中的三处偏差。**冻结产物未被修改**（originals preserved），修正仅登记于此并已纳入检测器的预注册预期：

### 2.1 36595：外部变量清单不完整且有误判

| 变量 | 冻结记录（R1_variables） | 源码事实 |
|---|---|---|
| elevation | `unavailable_in_source`（def_line=None） | **L63 明确 `var elevation = DEM.select('elevation')`——声明在源码内，记录错误** |
| lulc | `unavailable_in_source` | **L139 明确 `var lulc = modis.filterDate(...)`——同上，记录错误** |
| soil / s2 | `unavailable_in_source` | L27/L83 为**赋值式隐式全局**（`soil = soil.select('b0')`），RHS 自引用属未声明使用；赋值仅从本行起构成定义 |
| CHIRPS / DEM / modis | **未记录** | 真实的未声明外部预绑定（L19/L63/L139），人工重建完全遗漏 |

检测器新增候选：CHIRPS、DEM、modis（36595）、coi1、tfoiSmpLst1、scale、tileScale、table、AIM（302840）等——302840 冻结记录只登记了 ftTrain/bands/predLst/tfoiLst/stK 五个，检测器共发现 11 个候选。另：302840 首语句为裸表达式（`ee.Geometry.Polygon(...)` 缺失 `var geometry =` 前缀，快照截断），`table`/`AIM` 为逗号表达式中的赋值式隐式全局。

### 2.2 269131：Fire_Sus 后继使用计数 12 → 11

第三批叙述记 "12 处后继使用"；AST 逐一核对源码为 **11 处**（class1–class5 阈值链 8 处、min/max reduceRegion 2 处、图表 image 引用 1 处）。12 不可从源码复现，登记为人工计数分歧案例；检测器**不迁就**人工数，预期已更正为 11。

### 2.3 A4 规则细化：via 不同的重复对

269131 的两组重复边同 `(from, to, use_line)` 但 `via` 不同——每组一条为真实操作（如 `multiply 47.9819`）、一条为描述性注记（如 `also source of count chain`）。按"合并不丢失原始证据"的裁定，A4 实现为两级去重：主键 `(from, to, use_line)` 合并；`via` 不一致记 `via_conflict: true` 且**两条 via 全部保留**在合并记录内。严格四元组（含 via）下这 2 组不合并，结果并列报告（strict_dups=0, logical_dups=2）。

## 3. A1 候选分类状态（owner 修订 1 的落实）

所有未声明使用一律输出 `candidate_pending_human`，**零个自动判为 external_prebinding**。三分类（external_prebinding / missing_definition / indeterminable）留待人工裁定，检测器只提供证据线索（源码注释提及、自引用赋值等）。269131 的 AOI/image/HP_11_09_2019 三者均以候选身份出现，且未产生任何伪造边。

## 4. A3 未知 API 复核队列规模（工作包 B 的人工成本信号）

| 脚本 | presentation | export | analysis | unknown（复核队列） |
|---|---:|---:|---:|---:|
| 36595 | 26 | 1 | 39 | 103 |
| 275285 | 12 | 0 | 8 | 37 |
| 93009 | 10 | 0 | 13 | 45 |
| 302840 | 9 | 8 | 117 | 150 |
| 405410 | 3 | 1 | 25 | 95 |
| 269131 | 6 | 1 | 54 | 127 |

unknown 队列偏大，主因是**声明数据变量上的方法链在根名层无法全判**已由 classify 修正（root∈declared → analysis）后仍剩余的未声明根调用（与 A1 候选同源）与少量非常规 API。该队列应与 A1 候选合并后人工裁定，避免重复劳动——此为工作包 B 人工协议的设计输入。

## 5. 边界

本回测仅覆盖六个试点脚本；结果不外推至 128,447 行语料。未抽取新样本、未重建新脚本、未触碰冻结资产。工作包 B 抽样方案与工作包 C 指标口径待 owner 审查，之后另行裁定是否批准实际小规模验证。
