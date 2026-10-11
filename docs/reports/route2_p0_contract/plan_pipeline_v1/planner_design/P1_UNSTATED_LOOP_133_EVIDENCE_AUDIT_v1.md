# P1 133 行未声明循环证据审计报告 v1（2026-10-11，第 1 步执行件）

映射可靠性：blueprint `source_row_id` → G0 母语料行号，task-match 200/200 全对（上一验证）。
审计范围：全部 216 行未声明退化循环行（此前口径"133"为 top-200 抽检残留 + 语义信号分类的近似；
本轮以机械规则全量重扫得 216 行，0 行 unmapped）。

## 判定性发现：**213/216（98.6%）的循环金标来自 legacy run-cap 截断伪影**

每行证据 = G0 母语料字段：`run_cap_applied` / `original_semantic_length` / `final_semantic_length` /
`semantic_chain_raw+rle` 中 load 类调用实际出现次数。

| 判定 | 行数 | 证据 |
|---|---:|---|
| **gold_capped_by_legacy_run_cap** | **213** | G0 记录 `run_cap_applied=true`：原始脚本语义链被**旧 run-cap 截断**后写入金标（original_len 16–58 → final_len 3–9）。金标并非脚本的真实完整展开 |
| script_grounded_repetition | 3 | 原始链 load 次数 ≥ 循环次数（6↔6 / 56↔28 / 8↔8）——真实脚本级重复 |
| unmapped | 0 | 全部成功映射 |

循环窗分布（213 行）：`RASTER_LOAD→TEMPORAL_FILTER` 71 / `→BAND_SELECT` 53 / `→SPATIAL_FILTER` 34 /
`VECTOR_LOAD→ATTRIBUTE_FILTER` 14 等；循环次数 6–**228** 次。95/213 行任务文本带迭代信号词
（任务确实需要迭代，但**金标是被 cap 截断的假展开**，二者不矛盾——需要的是正确表示，不是假序列）。

## 机制假设裁定（对照 owner v2 计划的第 1/3 步）

- **第 3 步（P0 vs 金标偏离起点）已可预答**：P0 的 2-stage 循环**不是金标结束后模型自己续出来的**——
  金标本身就是一个被 run-cap 硬截断在半途的循环序列，模型学到的是"循环没有终点"这一模式。
  循环失控 = **忠实复现了残缺金标**。
- 与既有裁定吻合：R3-CD-2 曾裁定"run-cap=RLE 循环折叠，零 family 损失"——当时结论是 family 层面
  无损；本轮证明**展开长度/终止边界层面损害是实在的**（P0-B2 失败 283 条的直系来源）。

## 处置（按 owner v2 规则，等最终确认）

| 组 | 行数 | 处置 |
|---|---:|---|
| 213 capped 行 | **排除出终止增强组**（金标为 cap 伪影，非可信完整标注；既不补声明也不当终止正例） | 保留原始记录标记 `gold_run_cap_artifact` |
| 3 script_grounded 行 | 进入终止增强组（补 declaration——真实脚本级重复但元数据缺失） | |
| 合法重复对照 8,959 行 | 不变（P1 反遗忘基线内） | |

**对 P1 的含义**：终止增强组按证据规则目前只有 3 行脚本级真重复——**定向终止监督的证据基础
比预想薄得多**。P1 若开训，其数据主体只能是"全量基线 + 合法重复对照"，终止专项监督的加强
需另寻来源（如从 G0 原始脚本重建 uncapped 完整链作为新金标——属新数据工程，须 owner 立项）。
在拿到更强证据前，不建议开 P1 训练。

## 证据文件

`p1_unstated_133_evidence_audit.json`（216 行逐行：G0 长度/截断标记/load 次数/判定/任务信号）

---

## ⚠️ 重大更正（2026-10-11 晚，逐例对齐后）

本报告初版结论"P0 循环 = 忠实复现被 cap 截断的金标"**有误**。逐例对齐（sid 39969 等 208 行重建配对）显示：

- **planner_v2_train 的金标 = G0 raw 的完整展开**（98 行与 raw 逐 family 完全一致；110 行仅尾部清理差异；**0 行**匹配 G0 的 RLE 折叠短版）
- G0 的 `final_len 3-9` / RLE 折叠描述的是 **G0 自身 B1 时代语义链文件的状态**，Planner 线转换时用的是 raw 全量展开——**训练金标没有被截断**

**修正后的判定**（与 owner 机制假设一致，且有直接证据）：

> 金标把合法迭代任务**显式展开为 6–24 次无终止边界的字面循环**（sid 39969：AGGREGATION→RASTER_LOAD ×24 字面展开，无 repetition_group 声明，尾部另有 RASTER_LOAD ×8 连发），且无终止监督。P0 的 2-stage 循环失控 = **忠实复现了这种过度展开、无终止监督的金标模式**。run-cap 伪影存在于 G0 的 RLE/final 字段层面，但不在 Planner 训练目标的路径上。

**未决设计问题（须 owner 裁定，影响全部 8,959+ 合法重复行）**：长迭代任务的 Planner-v2 正确表示应为哪种——
(i) 字面展开 + declaration（现行约定，但正是教会循环失控的形态）
(ii) 折叠 repeat stage + declaration（AGGREGATION repeat=24 → RASTER_LOAD repeat=24，终止自然）
(iii) 单次覆盖声明（一次遍历声明覆盖全部对象，最抽象）

此裁定决定 213+ 行重建件的目标形态，也决定 P1 的数据方向。
