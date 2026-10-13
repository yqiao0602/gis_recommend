# R5 裁定包冻结与汇总报告 v1（owner 十轮：32 条三态+需求状态双轨裁定）

> 日期：2026-10-13 ｜ 冻结文件：`r5_adjudication_5516_6878_9210_9854_frozen_v1.json`
> 口径（owner 十轮）：**槽位需求判定与阶段覆盖判定分离**——三态只用于确实要求的槽位；需求状态单列 required/not_required/requirement_uncertain；`not_required` 永不记为 covered_confirmed。

## 1. 裁定总账（r5 的 61 个 missing 标记的去向）

| 裁定 | 实例数 | 说明 |
|---|---|---|
| `missing_confirmed` | **39** | 5516:17 / 6878:8 / 9210:9 / 9854 STATS:5 |
| `unresolved_wrapper` | 5 | 5516 cand3 MASK；6878 cand4 INDEX + cand5 TEMPORAL/INDEX；9210 cand7 SPATIAL |
| `requirement_uncertain` | 8 | 9854 INDEX 全部 8 候选（产品波段边界） |
| `not_required` | 8 | 9210 STATS 全部 8 候选（**规则假需求**，见 §2） |
| `covered_confirmed`（r5 标记中被改判） | 1 | 5516 cand5 INDEX（SPECTRAL_INDEX 覆盖通用槽位；UVVR 公式正确性另议） |

**汇总纪律（owner 十轮）**：39 不等于"统一确认遗漏率"的分子——9210 非必需槽位、9854 INDEX 定义边界、9854 AGGREGATION 粒度不确定（cand3/4/6 审计注记）全部单列。

## 2. 规则层发现（v0.5 修改账本，待 owner 批准后实施）

| # | 发现 | 案例处理 | v0.5 修改提案 |
|---|---|---|---|
| L1 | **`\bareas?\b` 假需求**：9210 的 "deforested **areas**"（土地覆盖类名）触发面积统计需求 → 8 个候选全部误标 STATS missing | 8 × not_required | area 模式需统计动词语境（calculate/compute/estimate area）或排除类名列表语境 |
| L2 | **INDEX 槽位定义边界**：MODIS MOD13A1 自带 NDVI 波段，"scaled NDVI values" 是缩放不是计算 | 8 × requirement_uncertain | 需 owner 先定 INDEX 定义（"计算新指数" vs "含产品波段读取+缩放"）；若含后者，需配套"computation verb 缺失 → plausible"规则 |
| L3 | **记录格式**：需求判定与覆盖裁定分字段 | 全部 32 条已按双轨记录 | r5 输出格式增补 requirement_determination 字段（required/not_required/uncertain），仅 required 进入覆盖裁定 |

## 3. 本轮验证的正向结果

1. **wrapper 一致规则运作正常**：5 个 ITERATIVE_APPLY 实例全部按统一规则落 unresolved_wrapper（cand4/5 的处理与 owner"对所有 wrapper 同一规则"的要求一致）；
2. **covered_coarse 语义经受住检验**：9854 cand3/4/6 的 AGGREGATION 被诚实标注 coarse 而非 complete——owner 的"粒度不足审计注记"与 r5 行为一致；
3. **r5 的 61 个标记中 39 个被确认真遗漏（64%）**——经最严格口径清理后，多数标记仍然成立；被推翻的 16 个（8 假需求 + 8 需求不确定）全部集中于两个可定位的规则/定义问题。

## 4. 待 owner（十轮顺序）

1. **固定 INDEX 槽位定义**（L2 前置问题：产品波段读取+缩放是否属于 INDEX）；
2. 批准 v0.5 修改账本（L1/L3 + L2 定义落地）；
3. 批准后：r5 v0.5 重跑 192 候选 + 反向对照 + 未调试任务复验 → INDEX/MASK 确认遗漏率汇总 → 奖励准入评审。Phase 2/3 继续冻结，RAFT/DPO/GRPO 不运行。
