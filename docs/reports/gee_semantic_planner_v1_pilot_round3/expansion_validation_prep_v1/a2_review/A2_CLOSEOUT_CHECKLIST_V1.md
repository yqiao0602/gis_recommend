# A2 复审收尾总清单（v1）

状态：A2_CLOSEOUT_CHECKLIST_V1 / 按 owner 指示停止逐变量展开、按清单收尾
日期：2026-10-10
数据底册：`A2_ADJUDICATION_TABLE_V1_3.jsonl`（676 单位全量）+ `A2_SOURCE_AUDIT_PACKET_V1` + `A2_COUNT_LOCK_EVIDENCE_V1`

## A. 已确认，无需任何动作（630 项）

| 组 | 数量 | 说明 |
|---|---:|---|
| 一致单位 | 530 | 自动化与人工在状态+计数完全吻合 |
| 分歧已裁定且无修订 | 100 | 146 项分歧中 final 值与人工值一致的项（accept_human / reject / scope / count_locked 等且无状态或计数修订） |

## B. 修订队列（47 项，机械执行，已获批待应用）

Owner 已逐项裁定的标签/计数修订，仅待统一写入标注修订版：

- **状态修订 11 项**（如 100110 图表参数族 data/xVals/xField/yField presentation_only→analysis_chain、100870 collTOres_im_mean→presentation_only、35821 illuminationCorrection unconsumed→analysis_chain+gr=false）
- **计数修订 41 项**（审计包逐处核验：stats 10→18、maxValue 2→4、GHSLbud 9→10、45485:image 8→6、35821 五项、7900:dem/ic 等；其中 5 项与状态修订重叠）
- 修订写入方式：生成 `annotation_results_v2`（v1 原样保留+SHA），不覆盖原始标注

## C. 一次批准即可锁定（5 项，证据已齐）

| # | 项 | 证据结论 | 待批内容 |
|---|---|---|---|
| 1 | `100145:year` 计数 | 5 处 var 声明全在顶层=**单一绑定**；29 处读取（含 2 闭包引用）；无左值、无形参遮蔽 | 按冻结规则确认 **final=29**（证据支持 29 非 11） |
| 2 | `101095:image` 计数 | 审计包恰好 3 处（L11/L13/L15 各含 image 一次，同调用不重复） | 确认 **final=3**（human 4 系重复计 L15 接收对象） |
| 3 | `landsatTOAcloudmask` 状态 | 静态引用 1；别名链断头 | 批准 unconsumed 定义条款（unconsumed:=零有效后继引用，纯静态；下游断头归 globally_reachable/downstream_effective 层）→ 本项=非 unconsumed，修订为 analysis_chain+downstream_effective=false |
| 4 | `maxValue`/`maxMedian` 状态 | L279/281 由 stats 百分位更新，L351 仅用于图表 max 配置 | 确认维持 analysis_chain 或改 presentation_only（二选一） |
| 5 | `myRows`/`blank` 状态 | myRows 唯一引用=图表行数据；blank→outline→仅 Map.addLayer | 确认均 presentation_only |

## D. 批准后的机械收尾序列（owner 批 C 后自动执行）

1. 应用 B-1/2 两个计数 + B-3/4/5 状态 → V1_4 终表；
2. 生成 `annotation_results_v2`（应用 47+新增修订；v1 归档）；
3. 冻结协议 v1.0（写入 unconsumed 定义、图表参数族规则、两层可达性）；
4. 按冻结协议计算**复核后 A2 一致率** + 错误类型分布（此时才发布数字）；
5. A2 复审结论报告 → 回到毕设主线。

## 边界（重申）

A2 为辅助性数据质量工作，目标是评估口径可靠、过程可复现、结论有据——**不追求边缘案例的零歧义**：无法确定者按协议保留 undeterminable/unknown，不强行裁定。
