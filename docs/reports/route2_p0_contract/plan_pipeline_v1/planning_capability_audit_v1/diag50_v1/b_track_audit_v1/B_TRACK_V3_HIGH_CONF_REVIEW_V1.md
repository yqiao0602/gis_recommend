# V3 高置信复核队列分类（Gate 1 第 1 步，2026-10-18）

- **状态**：`triage_for_owner_review`；**不改变 V3、不合并、不冻结**。
- **输入**：`B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1.json.gz`、
  `B_TRACK_TASK_FAMILY_DECISIONS_V1.jsonl.gz`、`B_TRACK_SPLIT_MANIFEST_V3.json`。
- **机器台账**：`B_TRACK_V3_HIGH_CONF_REVIEW_V1.json`（5,778 条，逐条 `review_id`）。
- **实现**：`scripts/b_track_v3_high_conf_review_v1.py`（只读、确定性）。

## 1. 口径与去重

| 项 | 定义 |
| --- | --- |
| 高置信 pending | `decision=pending`、**V3 跨 split**、`title_j≥0.60 或 body_j≥0.60` |
| 高置信截断边 | G1/D2 组边连接**不同族**、`title_j≥0.60 或 asset_shared≥1` |
| 去重键 | 无序组件对 `(min(a,b), max(a,b))` |
| 分类 | 三档**分诊建议**，不是 owner 裁定 |

对账结果：

| 检查 | 值 |
| --- | --- |
| 台账 V2 跨 split pending（全部） | 36,223 |
| 重建 V2 高置信 pending | **6,092**（与验收报告一致） |
| **V3 高置信跨 split pending** | **4,391**（V3 重划分后部分变成同 split） |
| 重建高置信截断边 | **1,387**（与台账 `deferred_high_confidence` 一致） |
| 两类端点对重叠 | **0** |
| **去重后唯一关系** | **5,778** |
| 受影响组件 / 族 | 5,975 / 2,274 |

截断边细分：**跨 V3 split 105 条**，同 split 1,282 条。前者是直接泄漏优先项；
后者属族边界准确性，不改变当前 split 的跨集状态。

## 2. 分类总表

| 类别 | 数量 | 含义 | owner 处置建议 |
| --- | --- | --- | --- |
| **A_merge_candidate** | **2,739** | 有直接同任务证据（共享目标+来源/资产/链） | 逐条确认；确认后进入 V3.1 合并，**不自动合并** |
| **B_keep_candidate** | **109** | 有明确任务差异或目的冲突证据 | 记录反证后保持独立 |
| **C_undetermined** | **2,930** | 证据不足或指标冲突 | 保持 pending；跨 split 项不得静默标 keep |

其中：

| 类别×来源 | pending（跨 V3） | deferred（跨族） |
| --- | --- | --- |
| A | **1,399** | **1,340**（其中跨 split 105） |
| B | 109 | 0 |
| C | 2,883 | 47 |

**泄漏优先集** = A 中跨 split 的 1,399 + 截断边跨 split 的 105（A 94 / C 11）
= **1,504 条**。这些是“若证据成立、合并后会改变 split”的关系；应先复核。

> **顺序说明**：本 JSON 按 `class → pattern → kind → rule → pair` 排序，
> **不是**泄漏优先级；因此**前 1,504 条不等于泄漏优先集**。泄漏优先集已另存
> `B_TRACK_V3_LEAKAGE_PRIORITY_V1.json/.csv/.md`，`priority_rank` 1–1,504：
> T1 截断跨 split（105）→ T2 pending A 跨 split（1,399），层内按 `strength` 降序。

## 3. 证据模式 × 类别

| 模式 | 总数 | A | B | C | 说明 |
| --- | --- | --- | --- | --- | --- |
| `purpose_conflict` | 1,583 | 0 | 9 | 1,574 | 目的类不同（如 identify vs estimate、generate vs extract），但可能共享对象/来源 |
| `same_title_diff_source` | 2,308 | 1,336 | 0 | 972 | 标题相同/近似，但无共享资产或数据族；需查源码来源 |
| `same_targets_diff_title` | 421 | 411 | 0 | 10 | 共享 ≥2 个**有效目标词**（已剔除 series/time/multi 等泛词） |
| `same_assets_diff_title` | 263 | 263 | 0 | 0 | 共享 ≥3 个字面资产，标题不同 |
| `mixed_or_weak` | 833 | 678 | 0 | 155 | 多信号混合，未落入单一模式 |
| `task_type_diff` | 168 | 41 | 0 | 127 | 任务类型不同，但可能有对象/资产重叠 |
| `same_chain_diff_target` | 138 | 0 | 100 | 38 | 结构链相同、无共享目标；多数应为不同任务 |
| `body_only` | 64 | 10 | 0 | 54 | 正文相似但标题不相似 |

> 有效目标词已剔除 `series/time/temporal/multi/data/pixel/region/landsat/
> sentinel/vv/vh/sar/glcm/texture/after/before/event` 等泛词、数据集名与词干伪影
> （如 `sery`），避免 “analyze NDVI time series vs analyze Tmax time series”
> 被误判为同任务。

## 4. 代表例子（每条都有 `review_id` 可回查）

### A_merge_candidate

| review_id | 类型 | V3 split | A | B | 关键证据 |
| --- | --- | --- | --- | --- | --- |
| R00011 | deferred | t/t | identify fire affected areas | identify fire-affected zones | T=0.60, O={fire,affected}, TT |
| R00689 | deferred | t/t | classify land cover using rf and svm | classify land cover types | AS=3, T=0.50, O={land,cover} |
| R02707 | deferred | t/t | identify built-up areas | identify built-up areas in jaxa lc | T=0.67, O={built,up} |
| R00001 | pending | t/v | model evi phenology and seasonality | model seasonal evi patterns | B=0.74, CS, O={evi}, TT |

判定提示：A 仍有少量“主题相近但对象范围不同”的边界例（如 land cover types vs
urban land cover）；**A 只是优先复核，不是合并许可**。

### B_keep_candidate

| review_id | 类型 | V3 split | A | B | 反证 |
| --- | --- | --- | --- | --- | --- |
| R02757 | pending | t/s | analyze ndvi time series | analyze tmax time series | 目标不同、TT=false、仅链相同 |
| R02759 | pending | t/s | analyze ndvi time series | analyze precipitation time series | 目标不同、TT=false |
| R02748 | pending | t/s | visualize vv backscatter over time | analyze vv backscatter over time | 目的 visualize vs analyze |

### C_undetermined

| review_id | 模式 | V3 split | A | B | 未决原因 |
| --- | --- | --- | --- | --- | --- |
| R03065 | purpose_conflict | t/s | generate cloud-filtered landsat mosaic | extract cloud-filtered landsat mosaic | 内容高度相同，但 generate vs extract |
| R03066 | purpose_conflict | s/t | identify vegetation and soil fractions | estimate vegetation and soil fractions | identify vs estimate 是否实质不同 |
| R04677 | same_targets | s/t | update land cover probabilities over time | model land cover change over time | 对象相同，但“概率更新 vs 变化建模” |
| R04687 | same_title_diff_source | t/t | extract glcm texture features | extract ndvi and texture features | 标题近似、无共享资产/数据族 |
| R02858 | body_only | t/s | classify forest change type | classify forest degradation and deforestation | 对象相近，但“变化类型 vs 退化/毁林” |

## 5. 复核协议（建议）

1. **先处置泄漏优先集 1,504 条**（A 跨 split 1,399 + 截断跨 split 105）：
   - 证据成立 → 合并进 V3.1，重新分配 split；
   - 证据不成立 → 记录反证，保持独立；
   - 证据不足 → 保持 pending，相关组件不得以跨 split 状态进入正式评估。
2. **再处置 B 109 条**：记录“为何不构成泄漏”的反证（目的/对象/来源差异）。
3. **C 2,930 条**：按模式分批复核；`purpose_conflict` 1,574 条最多，建议先定
   “目的类差异是否实质性”的统一口径，再批量裁决。
4. 截断边：跨 split 105 条优先；同 split 1,282 条只影响族边界，可在 V3.1 构造时
   按同一口径处理。
5. 所有裁定保留 `review_id ↔ 原始 (a,b,rule,kind)` 对应；V2、V3、V3.1 与中间映射
   均不覆盖。

## 6. 重要限制

- 分类基于静态证据（标题/正文/资产/链/任务类型），**没有逐条读源码**；
  `same_title_diff_source` 与 `task_type_diff` 尤其需要源码级核验；
- “高置信”只表示证据强度，不表示同族结论；
- 一次自动分诊不能替代 owner 裁定；A 类不得自动合并，C 类不得自动标 keep；
- 5,778 条是去重后的关系数，不等于受影响组件数（5,975）或族数（2,274）。

## 7. 产物与复现

```bash
python -I scripts/b_track_v3_high_conf_review_v1.py
```

输出：`B_TRACK_V3_HIGH_CONF_REVIEW_V1.json`（5,778 条）与本报告。
