# V3 泄漏优先集 1,504 条（有序台账）

- **定义**：跨 V3 split 的全部高置信截断组边（105）+ A_merge_candidate 中跨 V3 split 的 pending（1,399）。
- **顺序**：T1 截断跨 split → T2 pending A；层内按 `strength` 降序，再按 pattern、组件对升序；`priority_rank` 1–1,504。
- **机器台账**：`B_TRACK_V3_LEAKAGE_PRIORITY_V1.json`；**表格**：`B_TRACK_V3_LEAKAGE_PRIORITY_V1.csv`（UTF-8 BOM，可直接打开）。
- 每条保留 `review_id`，可回查 `B_TRACK_V3_HIGH_CONF_REVIEW_V1.json`。

## 1. 构成

- T1 截断跨 split：**105**（A 94 / C 11）
- T2 pending A 跨 split：**1399**
- 合计：**1504**；受影响组件 1751，族 946。

> T1 中 11 条被分诊为 C 的边仍保留在泄漏队列：分类是“证据是否足够”，不影响“该边跨 split”这一事实。

## 2. 模式分布

| 模式 | 数量 |
| --- | --- |
| `same_title_diff_source` | 1333 |
| `same_targets_diff_title` | 49 |
| `task_type_diff` | 43 |
| `same_assets_diff_title` | 35 |
| `mixed_or_weak` | 34 |
| `body_only` | 10 |

## 3. 前 30 条（按 priority_rank）

| rank | tier | review_id | pattern | split | title_a | title_b | T | B | O | AS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | T1_deferred_cross | R00787 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using multi-source remote sensing d | 0.3333 | 0.3469 | cover,land | 78 |
| 2 | T1_deferred_cross | R00888 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using multi-source remote sensing d | 0.3333 | 0.3226 | cover,land | 78 |
| 3 | T1_deferred_cross | R00769 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using multisource remote sensing da | 0.375 | 0.3241 | cover,land | 50 |
| 4 | T1_deferred_cross | R00916 | `same_assets_diff_title` | v-t | identify land cover probability | classify land cover types | 0.3333 | 0.4362 | cover,land | 21 |
| 5 | T1_deferred_cross | R00150 | `mixed_or_weak` | s-t | classify land cover in bangladesh | classify land cover types | 0.6 | 0.4787 | cover,land | 15 |
| 6 | T1_deferred_cross | R00652 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using rf | 0.6 | 0.463 | cover,land | 11 |
| 7 | T1_deferred_cross | R00653 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using rf | 0.6 | 0.3051 | cover,land | 11 |
| 8 | T1_deferred_cross | R00257 | `mixed_or_weak` | t-s | classify land cover types | classify land cover in january | 0.6 | 0.4848 | cover,land | 9 |
| 9 | T1_deferred_cross | R00733 | `same_assets_diff_title` | t-v | classify land cover types | classify land cover in february 2020 | 0.5 | 0.4623 | cover,land | 9 |
| 10 | T1_deferred_cross | R00356 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using rf | 0.6 | 0.375 | cover,land | 8 |
| 11 | T1_deferred_cross | R00575 | `mixed_or_weak` | t-s | classify land cover types | classify bosque land cover types | 0.8 | 0.5067 | cover,land,typ | 6 |
| 12 | T1_deferred_cross | R00768 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using stratified sampling | 0.5 | 0.2907 | cover,land | 8 |
| 13 | T1_deferred_cross | R00350 | `mixed_or_weak` | v-t | classify land cover in zvishavane | classify land cover types | 0.6 | 0.433 | cover,land | 5 |
| 14 | T1_deferred_cross | R00555 | `mixed_or_weak` | v-t | classify land cover in umzingwane | classify land cover types | 0.6 | 0.4 | cover,land | 5 |
| 15 | T1_deferred_cross | R00831 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using multi-source data | 0.4286 | 0.2941 | cover,land | 6 |
| 16 | T1_deferred_cross | R00781 | `same_assets_diff_title` | s-t | classify land cover using multi-source data | classify land cover types | 0.4286 | 0.4583 | cover,land | 5 |
| 17 | T1_deferred_cross | R00200 | `mixed_or_weak` | s-t | classify land cover using rf | classify land cover types | 0.6 | 0.4923 | cover,land | 5 |
| 18 | T1_deferred_cross | R00923 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using landsat and dem | 0.5 | 0.4839 | cover,land | 4 |
| 19 | T1_deferred_cross | R00920 | `same_assets_diff_title` | t-v | classify land cover types | classify mangrove extent and land cover | 0.5 | 0.3981 | cover,land | 4 |
| 20 | T1_deferred_cross | R00796 | `same_assets_diff_title` | t-v | classify land cover types | classify land cover using sentinel-2 and elevation data | 0.375 | 0.4478 | cover,land | 4 |
| 21 | T1_deferred_cross | R00407 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.5439 | cover,land | 4 |
| 22 | T1_deferred_cross | R00410 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.4828 | cover,land | 4 |
| 23 | T1_deferred_cross | R00397 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.4531 | cover,land | 4 |
| 24 | T1_deferred_cross | R00400 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.4265 | cover,land | 4 |
| 25 | T1_deferred_cross | R00405 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.4265 | cover,land | 4 |
| 26 | T1_deferred_cross | R00403 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.4262 | cover,land | 4 |
| 27 | T1_deferred_cross | R00402 | `mixed_or_weak` | t-s | classify land cover types | classify land cover using gcps | 0.6 | 0.3636 | cover,land | 4 |
| 28 | T1_deferred_cross | R00866 | `same_assets_diff_title` | t-s | classify land cover types | classify land cover using multi-sensor rf | 0.4286 | 0.4661 | cover,land | 4 |
| 29 | T1_deferred_cross | R00660 | `mixed_or_weak` | t-v | classify land cover types | classify land cover types by season | 0.8 | 0.5126 | cover,land,typ | 2 |
| 30 | T1_deferred_cross | R00799 | `same_assets_diff_title` | t-v | classify land cover types | classify land cover using sentinel-2 and elevation data | 0.375 | 0.549 | cover,land | 4 |

## 4. 使用方式

1. 先按 `priority_rank` 从 1 开始复核；CSV 已含全部字段。
2. 每条只允许三种裁定：合并进 V3.1 / 记录反证保持独立 / 保持 pending。
3. 保持 pending 的跨 split 组件不得以正式评估状态进入冻结。
4. 裁定结果按 `review_id` 回写；不得覆盖 V2/V3 历史。
