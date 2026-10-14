# GRPO 冒烟启动就绪核验报告 v1（owner 十八轮签字前清单执行）

> 日期：2026-10-14 ｜ 契约：`GRPO_SMOKE_CONTRACT_V3_FINAL.md`（v2 内容 + §8 冻结附录）
> 性质：**签字前核验材料**——全部 SHA 由本轮独立重算，非引用先前汇报。

## 六项核验清单

| # | 核验项 | 结果 | 证据 |
|---|---|---|---|
| 1 | §8 冻结规格与契约一致 | ✅ | C_E0=0.4975 / F_E0=0.3577 与 v3 引用值精确一致；四项投机基线齐全（`eval_set_frozen_spec_v1.json`） |
| 2 | E0 基线复核 | ✅ | 从冻结结果重读核对；E0 评分文件 SHA `2ade2e79…` 前缀记录于 S2 报告、全 SHA 入本报告附件 |
| 3 | 7 个排除 ID | ✅ | 冻结清单 = 不可评分行缺席集合，**精确匹配**（24 任务 = 17 可评分 + 7 排除） |
| 4 | 奖励解析器 SHA | ✅ | `1cfd48c99c4e…030d3f`（完整 64 位）= v0.6 账本记录 |
| 5 | 模型与数据身份（服务器侧重算） | ✅ | adapter `82095811dc11…`（15,737,216 B）/ adapter_config `9bb98f9c…` / base config `d0883072…` / planner_v2_train `443d5d31…`（51,313,438 B）——**与 §0 全部精确一致** |
| 6 | GPU 与资源安全 | ⏳ **启动时点条件** | 当前 22,285/23,028 MiB 被外部进程占用（空闲 743 MiB）——**当前不满足**；启动前须重检 ≥12GB（纪律不变） |

## 本地工件完整 SHA-256（附件 `launch_verification_local_v1.json`）

| 文件 | SHA-256 |
|---|---|
| `scripts/r5_requirement_parser_v0.py` | `1cfd48c99c4e9f2d13b946df430ce5a0eea3e2eccd89e1d4dae38bd81c030d3f` |
| `scripts/rl_reward_v1.py` | `2ade2e793c3f51f6e5ef3b78146879b6c87eb19967633f1dbf54ba1599669596` |
| `vocab23_server_verified.json` | `8562982d159406b05e806b7bd4c3f3586730d0891eb02eb3fb7fe9e15bbe6889` |
| `eval_set_24_tasks.jsonl` | `b9983488b12efebbf2c567a56dc40883825ca47cf7452254a2586b161d97a41e` |
| E0 评分文件 | `2ade2e79…` 时代产物，全 SHA 见附件 JSON |

## 结论

**身份与规则核验：全部通过（6 项中 5 项 ✅，第 6 项为启动时点动态条件）。** 契约 v3 FINAL 具备签字条件；签字后启动仍受两道动态检查约束：①GPU 窗口 ≥12GB 裕量预检；②外部进程零影响确认。任一不满足 → 继续等待，不干预外部进程。
