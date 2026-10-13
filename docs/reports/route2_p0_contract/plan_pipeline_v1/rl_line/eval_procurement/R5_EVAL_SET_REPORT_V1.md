# 评估集采购与盲评报告 v1（奖励准入评估集，从未训练任务）

> 日期：2026-10-13 ｜ 规则 v0.5.1 ｜ manifest SHA `4366a0c4…` ｜ 任务文件 SHA `b9983488…`
> 产物：`eval_procurement/`（manifest / 24 任务 / preds / config / r5 输出 / 盲评包）

## 1. 采购审计（owner 十四轮三约束落实）

- **无训练污染**：源池 = b1_gee_stage 128,447 权威备份 − planner_v2_train 全部指令匹配（33,371 排除）= **94,445 从未训练候选**。披露：训练文件无源 id 字段（provenance=null），归一化指令匹配为唯一可行且充分的排除；
- 分层：长度带 8/8/8、22 种任务类型、seed 20261013；
- SHA：manifest `4366a0c4…`、任务 `b9983488…`、preds/config 均入 `eval_set_scored_v051.json`。

## 2. 生成（mdzhang，S2 同配置）

192 候选，wall 201.9s，**115.76 tok/s**，峰值 8,231 MiB；解碼 temp 1.0 + rep-pen 1.15，max 768。
过程事故 2 起（均已修复入档）：适配补丁两次静默失配（旧字段加载 + p_script 未定义）——教训与 Gate A 纪律一致：**补丁必须经语法断言+残留断言后才部署**。

## 3. r5 v0.5.1 评分分布（从未训练集，规则口径）

| 判定 | 候选 |
|---|---|
| abstain | 32（4/24 组全弃权——任务无可解析需求，F3 正确弃权） |
| incomplete | 100 |
| complete_coarse_uncertain | 16 |
| complete | 17 |
| unparseable | 27（生成端 JSON 失败，待区分截断/格式） |

缺失分布（规则口径，未经人工确认）：**MASK 44、TEMPORAL 38、SPATIAL 29、TERRAIN 23**（新任务构成引入）、INDEX 16、COMPOSITE 14、CLASSIFY 9、STATS 7。

## 4. 盲评包

`EVAL_SET_BLIND_PACKET_V1.md`：24 组 × 8 候选全量槽位矩阵，r5 判定隐藏，协议/SHA 先冻结。**等 owner 盲评**（与 Gate B 同口径）。

## 5. 下一步

owner 盲评 → 解盲对照（一致性/误伤/漏报，四态+requirement_determination 双轨）→ **S0-S3 评分方案在"校准集选型、本集一次性验证"纪律下的正式比较** → 奖励准入评审。全程 Phase 2/3 冻结，无参数更新。
