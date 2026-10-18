# B 轨数据治理变更账本 V1（append-only）

| 日期 | 版本 | 变更 | 影响 | 重跑/命令 | 依据 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | B_TRACK_GOVERNANCE_V1 | 初始冻结：准入规则、判读层级、多参考规则、可追溯四问、划分治理 | Q2 117 条分桶落地（A41/C1-26/C2-29/M14/Q1-5/Q2-2） | `Q2_ADMISSION_V1.json` 生成脚本（本次会话内联） | owner 2026-10-18 决策 + Q2 审计结论 |
| 2026-10-18 | — | 17 条阻断性深查项单列（其余 8 条非阻断运行核验） | 相关记录标 provisional | 待专项核验 | `Q2_ADMISSION_V1.json::pending_deep_check_blocking` |

**规则**：规则演进先 commit 再重跑；每次变更记录规则 diff、影响样本数、重跑命令、生效日期。
| 2026-10-18 | B_TRACK_GOVERNANCE_V1 (stage 2) | 24 组参考集草案起草（L1/L2/L3/多参考/准入/证据锚点） | 24/24 draft_provisional，待 owner 逐组复核；17 阻断项按 provisional 处理 | `q2_stage2_reference_drafts/` + `B_TRACK_TRUSTED_REFERENCE_DRAFTS_V1.json` | owner 2026-10-18 阶段二批准 |
| 2026-10-18 | B_TRACK_GOVERNANCE_V1.1 | owner 首轮复核统一口径：结构等价/同构模板/多参考三分；语义置信度/证据完整性/准入状态三分离；跨组素材泄漏约束 | 24 组索引升 V2；R19/R18A/R18B/R20/R23 修订 | `B_TRACK_CROSS_GROUP_OVERLAP_V1.md/.json`、`q2_stage2_reference_drafts/INDEX.md` | owner 首轮评审 |
