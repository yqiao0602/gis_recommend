# PCA Phase 1 工作注记 — v1（2026-10-13）

> 协议：`PCA_PROTOCOL_V1_FROZEN.md`。本注记记录 Phase 1（任务+金标构建）的执行状态与
> 数据链路侦察结论。金标 owner 审核通过前不运行任何模型生成。

## 1. 数据链路侦察结论（A 组隔离判定基础）

| 资产 | 位置 | 状态 | 用途 |
|------|------|------|------|
| `blueprint_v2_gold_v3.jsonl`（37,044 行，SHA 621090bc） | **确认不存在于本机与 mdzhang**（10-04~10-08 窗口唯一相关文件即 planner_v2_train；F 盘迁移包不在本机） | 已按 owner 裁定降级处理 | 原 gold 候选池参照；由实际训练消费池 + authority 来源记录替代（见 §2） |
| `planner_v2_train.jsonl`（33,339 行，SHA `443d5d31…`，51MB） | mdzhang `/home/qy/planner_v2_train.jsonl`（10-08） | ✅ 可用 | **P0 实际训练消费**的打包子集（task/context/separator/target）；去重参照的操作定义 |
| `b1_gee_stage_train.jsonl`（264MB，**带 source_row_id**） | 本地 `../server_backup_mdzhang_20260927/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/` | ✅ 可用（只读，原地引用不复制） | GEE stage 训练源 + **来源记录**（A 组 `source_record_verified` 判定） |
| `stage1_train_v2_2.jsonl`（150MB）/ `plan_pool_tiered_v2.jsonl`（234MB） | 同备份 `route2_training/plans/` | ✅ 可用 | 训练链补充参照 |
| dev-120（B 组源） | 本地 `docs/reports/v2a_manifest/v2a_A_dev.jsonl` | ✅ | B 组任务文本 + gold 反推材料 |
| 算子能力档案 v0.4 | 本地 `route2_training/profile/` | ✅ | C 臂检索源 |

**结论：A 组隔离证据可以实现 `source_record_verified` 级**（b1_gee_stage 来源记录 + 
planner_v2_train 文本池双重判定）；若最终 gold 候选池无法定位，退路是按协议 §2.3 将
无法来源核验的条目标 `text_dedup_only` 并披露。

## 2. 已完成

- **B 组筛选**（`scripts/pca_b_group_screen_v1.py`，规则先于查看预测冻结，seed 20261013）：
  120 → 112 过算子 ID 扫描（8 条含 `provider:slug` 拒绝）→ taskType×链长分层 round-robin
  → **20 正选 + 10 备选**（`pca_b_group_candidates_v1.json`，含逐条审计字段）。
  质量：17 种 taskType；链长带 9/5/6；16/20 带算子词表 flag（供 owner 审核参考，非拒绝）。
- **B 组审核工作表**（`pca_b_group_review_worksheet_v1.md`，owner 四问结构：泄露/规划价值/
  金标独立性/替代路线；全部 30 条含任务全文、命中上下文、gold 链反推材料；判定列
  PENDING-OWNER）。
- **A 组来源核验完成（owner 指令第 1-2 步）**（`scripts/pca_a_group_isolation_v1.py` +
  `pca_a_group_select_v1.py`，`pca_a_group_isolation_audit_v1.json` +
  `pca_a_group_candidates_v1.json`）：
  - `blueprint_v2_gold_v3.jsonl` 确认**不在 mdzhang**（10-04~10-08 窗口唯一相关文件即
    `planner_v2_train.jsonl`）；F 盘迁移包不在本机。按 owner 裁定以**实际训练消费池为主要
    排除依据**（`../pca_data_ref/planner_v2_train.jsonl`，33,339 行，SHA `443d5d31`，P0
    run_ledger 确认为 train_data）。
  - 权威 GEE 池 = 冻结的 128,447 行 `b1_gee_stage_train.jsonl`（备份本地只读可用；行号 =
    冻结 SHA 下稳定行标识）。**训练消费 99.9% 集中于 authority 的 train split**
    （33,368/33,371；test 仅 3、val 零命中）→ val/test 双重 held-out。
  - **A 组候选池：26,931 行**（authority val/test ∩ 未消费 ∩ 文本 authority 内唯一），
    全部 `source_record_text_aligned` 档（来源行明确 + 训练排除经由文本对齐，对齐率
    ≈100%）；75 种 task_type。
  - **预正选 20 + 备选 30**：复杂度带 6/10/4 精确配平，17 类型，test 11 / val 9。
  - 证据等级披露：当前最高可得档为 `source_record_text_aligned`（直接来源映射需 gold_v3
    找回才可升级 `source_record_verified`）；`text_dedup_only`（authority 内重复文本）
    不进入 A 组候选。

## 3. 下一步（Phase 1 剩余，顺序即依赖）

1. **owner 审核 B 组工作表**（20 正选可换备选；W005784 类 gold 链过弱条目建议裁决）；
2. **A 组金标撰写**：从 20 正选的 instruction 独立撰写语义金标（禁 GEE API 链直译）→
   owner 审核；
3. **C 组起草**：覆盖矩阵（多源融合/CRS/栅格矢量组合/分区统计/质量分支/长链）20 条 +
   金标 → owner 审核；
4. **配对任务设计**：≥6 对（A↔B/C 同目标双表述），占组内名额；
5. **去重账本**：60 条对训练文本池 8-gram + 近似重复扫描（A 组已过消费池排除，此处补
   近似重复层）；
6. 复杂度/task_type 配平复核 → 提交 owner 审核（**审核通过前不运行正式 180 生成**）。
