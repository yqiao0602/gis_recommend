# 工作区未跟踪产物盘点 v1（2026-10-13）

> 状态：WORKTREE_INVENTORY_V1 —— Phase 0 安全收口的分类清单。生成时基线 commit
> `8db38100`（组①上下文与裁定文档已入库）。未跟踪 353 项（不含本文件）。
> 原则（owner 2026-10-13）：不批量提交；分批前核对账本引用与 SHA；冻结包大文件/
> 可再生缓存先确认存储规范。

## 1. 批次计划

| 批次 | 范围 | 文件数 | 处置 |
|---|---|---|---|
| ① 上下文与裁定 | 4 modified + 2 份 STAGE1_GATE 文档 | 6 | ✅ 已提交（`8db38100`） |
| ②a 代码 | `scripts/` 全部（62）+ `tests/`（6） | 68 | 待提交；核对点：各报告/LEDGER 引用的脚本名存在性（LEDGER 引用 `eval_p0b2_arm_v1.py`、协议引用 `pca_*` 系列、GEE 报告引用检测器/构建脚本——均已在盘点中确认存在） |
| ②b Planner 侧产物 | `planner_design/` 及子目录（82）+ `route2_p0_contract/g0_audit_sample_20_v1.jsonl`（1） | 83 | 待提交；核对点：`EVAL_BASELINE_FREEZE_V1.json` 七文件 SHA 抽验、`WS1_WS2_ADJUDICATION_FREEZE_V1.json` 六文件 SHA、A 实验协议引用的 `A1_SAMPLE_131.json` |
| ③ GEE 线报告 | `gee_semantic_planner_v1_pilot{,_round2,_round3}/`（199）+ `gee_frozen_data_impact_v1/`（1） | 200 | 待提交；核对点：`a3_v1_1_freeze/` 冻结包完整性、`annotation_results_v2` SHA `d3fca732`、冻结账本 `05af094d` |

## 2. 排除与待裁清单（不混入上述批次）

| 文件 | 核查结论 | 建议处置 | 状态 |
|---|---|---|---|
| `gee_semantic_planner_v1_pilot_round3/expansion_validation_prep_v1/_pool_scan_cache_v1.jsonl`（71MB） | 全池扫描（101,227 脚本 / 11,863s）过程缓存；命中分布等结论已汇总入 `EXECUTION_LOG_V1.md`；可由扫描脚本 + 服务器源池再生 | 精确路径加入 `.gitignore`（不用通配符，避免误伤同类数据）；文件本身保留在磁盘不删除 | 待 owner 确认 |
| `scripts/docs/reports/.../REP_SPEC_REV1_VALIDATION_v1.json`（1,545B） | `rep_spec_rev1_validation.py` 在 `scripts/` CWD 下运行的错位输出副本；正确路径版本（1,568B）已入库；无任何文档引用错位路径 | 删除错位副本（重复产物，非唯一拷贝） | 待 owner 确认 |
| 根目录 `qgis_op_family_reverse_v1.json`（133 op） | = tracked 版（129 op）+ 4 算子扩充（`native:multiringconstantbuffer`、`native:pointstopath`、`native:polygonize`[raster→vector note]、`saga:addrastervaluestopoints`[raster value extraction]），后两项呼应 task_plan identity-gap 清单；E2E 实验 B 冻结输入是 129 版 | **不覆盖不删除**；登记为 v1.1 扩充草稿。若 owner 采纳 133 版：重命名为 `qgis_op_family_reverse_v1_1.json` 移入 `e2e_mainline_v1/`，并登记"未来 grounding 实验用 v1.1；E2E B 历史结果绑定 129 版不变" | 待 owner 权威裁定 |
| `scripts/qgis_op_family_reverse_v1.json`（129 op） | 生成器 `scripts/qgis_op_family_reverse_v1.py` 的输出副本，与 tracked 129 版内容相同；消费脚本 import 的是 `.py` 模块而非 json | 随批次②a 提交（保持生成链自洽，避免 129/133 混淆），或 gitignore；倾向提交 | 随②a 处理 |

## 3. 批次②③提交前必做核对（执行时逐项记录到 commit message）

1. JSON/账本声明的外部文件 SHA 抽验（上表核对点）；
2. 各冻结报告引用的脚本名与产物路径存在性（只读检查）；
3. 冻结包目录（`a3_v1_1_freeze/`、`WS1_WS2_ADJUDICATION_FREEZE_V1` 六文件、`annotation_results_v2`）逐文件清点后整包提交，不拆散；
4. 提交顺序：②a → ②b → ③（报告在脚本与其产物之后入库，保证引用方向可追溯）。

## 4. 与并行会话的协调注记

PCA Phase 1（A 组金标撰写 / C 组起草，worknotes §3 第 2-3 步）与工作区收口可并行，
但同一文件不得双写：本盘点期间 PCA 目录的全部变更归属持有会话（`9cb1b18e` /
`debe66f3`），本会话仅新增 `planning_capability_audit_v1/STAGE1_GATE_*.md` 与本文件。
