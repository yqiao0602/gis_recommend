# PCA Phase 1 工作注记 — v1（2026-10-13）

> 协议：`PCA_PROTOCOL_V1_FROZEN.md`。本注记记录 Phase 1（任务+金标构建）的执行状态与
> 数据链路侦察结论。金标 owner 审核通过前不运行任何模型生成。

## 1. 数据链路侦察结论（A 组隔离判定基础）

| 资产 | 位置 | 状态 | 用途 |
|------|------|------|------|
| `blueprint_v2_gold_v3.jsonl`（37,044 行，SHA 621090bc） | **无本地镜像**；F 盘迁移包 `E:/Route2_Migration_20260928/` 不在本机（本机仅 C/D/E 盘）；服务器 /home/qy 与 /data/qy maxdepth-5 内未找到 | 待定位（可能在租卡机或已被清理） | 协议 §1 引用的 gold 候选池参照 |
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
- 协议 v0 → v1 冻结（owner 五处修订+七项 OQ 落实），commit d3623e6c。

## 3. 下一步（Phase 1 剩余，顺序即依赖）

1. **B 组金标反推**：20 正选的 processes/links → 语义步骤+依赖+条件（de-grounding 规则
   先冻结）→ owner 逐条审核；
2. **A 组构建**：GEE 任务候选池（b1_gee_stage 任务文本 ∉ planner_v2_train 文本池）→
   隔离判定脚本（source_row_id 级）→ 分层选 20 → 语义金标撰写（禁 GEE API 链直译）；
3. **C 组起草**：覆盖矩阵（多源融合/CRS/栅格矢量组合/分区统计/质量分支/长链）20 条 +
   金标 → owner 逐条审核；
4. **配对任务设计**：≥6 对（A↔B/C 同目标双表述），占组内名额；
5. **去重账本**：60 条对训练文本池 8-gram + 近似重复扫描；
6. 复杂度/task_type 配平复核 → 提交 owner 审核（**审核通过前不运行正式 180 生成**）。
