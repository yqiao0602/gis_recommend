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

## 2b. B 组表述审核轮（2026-10-13 owner 裁定后执行）

- **构念偏差修正**：owner 判定 dev-120 `task_text` 多为"工作流说明"而非"用户任务"——
  原样送入会把"测规划"变成"测步骤提取"。已发布 **PCA v1.1 版本化修订**
  （`PCA_PROTOCOL_V1_1_B_GROUP_RESTATEMENT_v1.md`）：五条表述处理规则（原文只读归档 /
  目标导向改写 / 禁现成解法 / 改写质检 / 逐条入账），不动三臂/指标/判读。
- **owner 逐条裁定已执行**：正选 14 条件保留 + 6 替换；备选 5 条件保留 + 5 替换；
  算子 ID 拒绝 8 条维持排除。**B 组可用池 = 19 条**（差 1，不凑数）。
- **19 条去过程化改写稿完成**（`pca_b_group_restatement_v1.md`，原文-改写对照账本，
  全部 PENDING-OWNER；每条标注删除内容/保留约束/金标独立性注意；W067268 按裁定做了
  最大幅度去过程化并标记复核点；W023206 标记复杂度过低风险）。
- **补足初筛**（`scripts/pca_b_group_refill_v1.py` → `pca_b_group_refill_v1.json`）：
  82 条未审行按构念偏差启发式（叙述密度+工具类惩罚）排序，top-10 交 owner 补审；
  未经 owner 补审不得入选；owner 也可裁定按 19 条运行并在报告披露。

## 3. 下一步（Phase 1 剩余，顺序即依赖）

1. **owner 复核 19 条改写稿**（批准/修改；W067268 与 W023206 有特别标记）+ **补审
   top-10 补足名单**（选 1 条或裁定按 19 条运行）→ B 组任务集定稿；
2. **A 组金标撰写**：从 20 正选的 instruction 独立撰写语义金标（禁 GEE API 链直译）→
   owner 审核；
3. **B 组金标撰写**：基于改写稿（非原 gold 链直译）独立写必要语义步骤/依赖/条件/
   可接受替代 → owner 审核；
4. **C 组起草**：覆盖矩阵 20 条 + 金标 → owner 审核；
5. **配对任务设计**：≥6 对（A↔B/C 同目标双表述），占组内名额；
6. **去重账本**：60 条对训练文本池 8-gram + 近似重复扫描；
7. 复杂度/task_type 配平复核 + **三组表述抽象层级可比性核对**（owner 正式生成前要求）→
   冻结任务/金标/改写稿 SHA → Phase 2 smoke。

## 4. 阶段 1：B 组独立金标编写完成（2026-10-13，owner 阶段序执行）

- **控制点闭环**（owner 要求的运行环境验证）：冻结文件完整 SHA256 =
  `1a13ad8d95c33771275a5ee8aca1f8940000dafc8ed5053c07ac6920b53bc7c9`，
  工作区 = 提交 a44e665f = HEAD 三方逐字节一致；文件自此只读，修订走版本化。
- **`pca_b_gold_worksheet_v1.json`（SHA `06b30b9c810a2e6d`，19 行）**：以冻结题面为
  唯一任务语义依据（task_text 从冻结文件零转录读取并逐行绑定 text_sha256），
  按 owner 八字段结构逐条编写：required_outcome / required_constraints /
  required_capabilities / acceptable_alternatives / failure_conditions /
  gold_chain_audit（=PENDING-STAGE-2，**编写过程未读任何原始链**）/ evidence（题面原句）。
- 每条金标体现 owner 关键区分：任务要求 vs 可接受实现 vs 原链实现（例：W056274 距离
  对象锁定"同一 paddock 内水源点"不可被替代路线绕过；W000473 明确接受全部等价路线；
  W000890 等级优先以原文核实为据）。
- 待 owner 审核 B 组金标独立性与可判定性 → 通过后进阶段 2（原链一致性审计，四标签
  CONSISTENT / PARTIALLY_CONSISTENT / INCONSISTENT / UNDERDETERMINED 待正式定义入账本）
  → 阶段 3（A/C 组 + 配对）→ 阶段 4（评测账本冻结 → 才申请正式生成）。

## 5. Stage-2 完成与 Stage-3 启动（2026-10-13，owner round-8 后）

- **Stage-2 正式审计完成**（owner 批准后执行）：`pca_b_chain_audit_v1.json`
  （SHA `2433e51e7ae5a930`，绑定金标 `0dc643980e8d4b8e`）——CONSISTENT 13 /
  PARTIALLY_CONSISTENT 5 / INCONSISTENT 1 / UNDERDETERMINED 0；ESCALATE-OWNER x1
  （W056058）。报告：`pca_b_chain_audit_report_v1.md`。
- **元发现升格为评测规则**（owner round-8）：Processing 链表示力边界 →
  `pca_stage34_scoring_rules_v1.md`（五条规则 + PARTIALLY 解释边界 + W056058 特别规则 +
  A 组文体构念声明 + Stage-3 执行清单）。
- **W056058 处置**：`OWNER-REVIEW / BASELINE-INVALIDITY-REVIEW`；三分支核验记录
  `pca_w056058_disposition_v1.md`（分支①成立：题面金标一致、原链确缺核心结构、任务
  有效；起草推荐=保留任务 + 原链标 BASELINE-INVALID + 金标唯一基准）；owner 终裁待回填。
- **Stage-3 启动**：A 组金标（原生 GEE instruction 文体=域内构念，金标按语义独立写）、
  C 组起草+金标（覆盖矩阵）、≥6 对配对（依据=同分析目标）。产出 owner 审核后进 Stage-4
  账本冻结。模型生成继续未启动。

## 6. Round-9 终裁落实（2026-10-13）

- **W056058 分支①采纳并回填账本**：`adjudication_resolved` + `owner_disposition`
  （EXCLUDED_FROM_MAIN_SCORING / BASELINE-INVALID / 金标 0dc643980e8d4b8e 唯一基准 /
  日期 / round）已写入 `pca_b_chain_audit_v1.json`（新 SHA `ce224ec3bdb6f6d3`；
  回填前状态保留于 commit f7c8c256）——排除规则落账本字段而非仅说明文件。
- **评分规则文件 round-9 增补**：W056058 终裁节；A 组文体四行管理表（含配对审核扩展：
  必需步骤/分支循环/参数约束/输出要求核对——同目标≠同难度）；Stage-4 冻结确认条款
  （评分代码路径机械验证：原链覆盖率/逐步一致不得为扣分依据；evidence_source 必填 ∈
  {task_text, gold_constraint, model_output}）。
- **Stage-3 侦察完成**：A 组 20 条题面全部就位（line_id/split/task_type/instruction
  全文于 `pca_a_group_candidates_v1.json`；域内文体确认）。下一步 = A 组金标编写
  （20 条 × 八字段，题面从候选文件零转录读取），随后 C 组起草与配对设计。
