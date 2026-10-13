# R5 反向控制报告 v1（owner 八~九轮指令：32751/32593/30160 复核 + 规则假阳性量化）

> 日期：2026-10-13 ｜ 规则版本：**v0.4.1（冻结）** ｜ 性质：规则缺陷反向控制与假阳性量化
> 上游：owner 八轮（32751 INDEX 疑似假阳性等）+ 九轮（三态口径 + `requirement_uncertain` 第四态）

## 1. 确认并修复的规则缺陷（5 处，全部由反向控制暴露）

| # | 缺陷 | 案例 | 修复 |
|---|---|---|---|
| 1 | **`EVI` 无词边界 → "de**vi**ation" 触发 INDEX**（纯正则事故；32751 两次 INDEX 命中全部来自 "standard deviation"） | 32751（owner 八轮疑似假阳性——坐实） | `\b(?:NDVI\|NDWI\|EVI\|SAVI)\b` |
| 2 | SPATIAL 的 `within the`/范围词把"结果范围限定"当"空间操作" | 32593（owner 八点 B） | 范围词降 plausible；仅 clip/crop 操作动词生成 required |
| 3 | COMPOSITE 命中 "composite **indices**"（复合指标≠影像合成） | 26102（owner 九轮边界 1） | 负向断言排除 |
| 4 | STATS 把精度评估与面积统计混为一槽 | 30160（owner 八点 C） | accuracy 移出 STATS，仅由 ACCURACY_ASSESSMENT gap 信号表达 |
| 5 | **`crop` 名词/动词多义**："Parcel **crop** classification" 触发空间裁剪需求（v0.4 修复 #2 时自行引入，A4 合成例当场抓获） | 合成包 A4 | 仅认 croppED/croppING/crop to 操作形态 |

## 2. 假阳性量化（358 → 323）

| 槽位 | v0.3 | v0.4.1 | Δ | Δ 来源 |
|---|---|---|---|---|
| INDEX | 90 | 75 | **-15** | deviation 类 FP + generic-index 降级 |
| MASK | 87 | 79 | -8 | cloud-cover 元数据筛选降 plausible（k=22822 类） |
| COMPOSITE | 49 | 43 | -6 | composite indices 排除 |
| SPATIAL | 41 | 37 | -4 | 范围限定降级 |
| TEMPORAL | 45 | 43 | -2 | seasonal 降级 |
| CLASSIFY / STATS | 27 / 19 | 27 / 19 | 0 | — |
| **合计** | **358** | **323** | **-35（-9.8%）** | 全部为规则误报/口径降级，非模型行为变化 |

## 3. 核心结论对规则清理的稳健性

**INDEX+MASK = 154/323 = 47.7%**（v0.3 下 49.4%）——剔除近一成规则误报后仍是主体。X4"漏指数计算与云掩膜"的结论**不是规则伪影**；358→323 的修正是测量精度提升，不改变方向。

## 4. 合成盲评有效性核验（owner 标签基于 v0.3）

**v0.4.1 下 9 项判定 0/9 变化**——owner 的盲评标签与 0/3 误伤率结论在当前冻结版本下完全成立。A4 在 v0.4（未修 #5 时）曾翻转、v0.4.1 恢复，过程本身记录为规则演进证据。

## 5. 新口径落地状态

- `requirement_uncertain` 第四态已实现（plausible 命中 → 单列，不入覆盖分母）：k=32593 SPATIAL、k=26102 TEMPORAL、k=22822 MASK 为首批实例；
- 三态（missing_confirmed/covered_confirmed/unresolved_wrapper）维持九轮冻结；V2=51 实例（v0.3 的 53 中 2 例随 INDEX FP 消除）；
- R5 身份不变：离线审计与覆盖测量工具，RL 奖励准入等独立裁定。

## 6. 待 owner（九轮执行顺序续）

1. 本报告抽查（尤其 #1 的 deviation FP 证据链）；
2. 裁定包 32 条的三态裁定（`r5_adjudication_packet_5516_6878_9210_9854_v1.jsonl`）仍待你逐条判定；
3. 裁定后：反向对照 + 未调试任务复验 + INDEX/MASK 确认遗漏率汇总 → 奖励准入评审。
