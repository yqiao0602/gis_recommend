# W056058 处置核验记录 v1（owner round-8 三分支裁定材料，2026-10-13）

> 状态：`OWNER-REVIEW / BASELINE-INVALIDITY-REVIEW`（暂不入主评分分母）。
> 本记录 = owner 三分支核验标准的对照材料；**分支选择归 owner**，本记录含起草推荐。

## 1. 三方对照

**冻结题面**（`pca_b_group_final_inputs_v1.json`，task_sha256 见账本）：
> For a water-network vector layer restricted to a study area, produce results organized by the network's three hierarchical levels (Principal, Secundaria, Terciaria) according to the level attribute: one layer per level and a buffer zone around each level with its own specified radius (each level has a distinct radius). Output: the study-area network, one filtered layer per level, and one buffer layer per level.

**金标**（`pca_b_gold_worksheet_v2.json`，SHA `0dc643980e8d4b8e`）：
- required_outcome = 研究区水网 + 逐级过滤层 + 逐级缓冲层；
- required_constraints = 三级按 level 属性、各级独立半径、研究区限制；
- failure_conditions = 级别错分 / 半径错配 / 某级缺失 / 超出研究区。

**原链**（dev-120，零转录）：
`native:clip` → `native:buffer`（2 步，单 buffer）。

**原始 task_text（改写来源，研究者参考）**：
"...classifies the clipped layer into three water network levels (Principal, Secundaria, Terciaria) based on the 'Descripc' attribute... generates buffer zones of 100m, 50m, and 20m respectively for each level. The results include the clipped layer, filtered level-specific layers, and buffer layers..."

## 2. 三分支核验

| owner 分支 | 对照结果 |
|-----------|----------|
| ① 题面金标一致 + 原链确实遗漏核心要求 + 任务本身有效 | **事实成立**：题面三级/三半径/输出清单明确；金标与题面一致（金标直接由题面编写）；原链无任何分级/差异化缓冲步骤——遗漏的是核心任务结构 |
| ② 题面存在歧义 | 不成立：三级分离与逐级半径在题面中为明确列举要求，非指代表述 |
| ③ 样本损坏 / 任务与金标错配 | 不成立：题面、金标、原 task_text 三者语义一致；错配仅存在于原链（原脚本未实现其描述，或链提取未捕获分级步骤——两种情形原链都不是合格参考） |

**证据边界注记**：原链缺失的精确原因（原脚本未实现 vs 链提取遗漏分级步骤）无法从
链表示判定——但两情形下原链都不能作为正确参考基线，不影响分支判定。

## 3. 起草推荐（owner 终裁）

按 owner 倾向（"核验确认有效任务→保留任务、原链标记为无效参考基线、用冻结金标评估
模型输出"）与上表（分支①成立、②③排除），推荐：

- **保留任务**于 PCA B 组（任务本身有效，且有诊断价值：检验模型能否补全原链缺失的
  核心结构）；
- **原链标记 `BASELINE-INVALID`**（失败案例，不作正确参考链、不入相似度类评分参照）；
- **评分以冻结金标为唯一语义基准**；
- 审计账本记录与 INCONSISTENT 标签保持不变（adjudication_resolved 回填本推荐 +
  owner 最终裁定）。

owner 裁定：＿＿＿＿（分支①/②/③ 或其他）
