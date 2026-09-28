# 冻结包修订说明：键体系对齐（2026-08-07）

## 背景

Phase 0 冻结完成后，expanded adapter 契约审查发现：**跨池去重键在项目内存在多套互不可比的算法**。若不修复，展开候选行与既有 294/507 baseline 的键将永远无法匹配，同 DAG 重复行会漏进训练集（违反方案 v2 P0-2"同一 unified_training_pair_key 即 duplicate"）。

## 调查证据（实测）

| 对比项 | 结果 |
|---|---|
| adapter 自造三键 vs `run_qgis_processing_batch._dedup_keys` 权威派生 | **全部不一致** |
| 权威派生 vs 294 行 explicit 历史键 | **200/200 不一致**（历史键由各池导出器生成，第三套算法） |
| 294 行 `unified_training_pair_key` vs batch 算法（含 operator_sequence） | **91/100 匹配** ✅ |
| 294 行 `unified_training_pair_key` vs freeze 算法（无 operator_sequence） | **0/100 匹配** ❌ |
| adapter 行经描述器后直接走 `_dedup_keys` | **KeyError**（描述器输出为纯负载，缺 source_sha256/键） |

结论：
- **权威裁决键 = `unified_training_pair_key`**（explicit 优先；派生算法 = batch `_training_pair_key`，含 task_name/task_description/operator_sequence/l3_code_sequence）；
- 结构键（source_region/call_graph/normalized_dag）在各池间本就不可互比，候选行必须用**权威派生算法**生成，保证候选内与"候选 vs baseline"比较的一致性；
- freeze 脚本的 `_training_pair_key` 派生缺 `operator_sequence` 分量——派生路径（缺 explicit 的行）会算错键。

## 修复

1. `src/gis_recommend/data/qgis_processing_expanded_adapter.py`：
   - 删除自造三键；改用权威派生算法（与 batch `_dedup_keys` 同构）；
   - `unified_training_pair_key` 不在 adapter 内预生成——描述+L3 之后由权威算法生成。
2. `scripts/freeze_qgis_processing_conversion_v2.py`：
   - 第 1 阶段：`_training_pair_key` 补 `operator_sequence` 分量（对齐 batch 权威算法）；
   - 第 2 阶段：`_training_pair_key` **删除 explicit 分支，永远派生**——因为权威 driver（`run_qgis_processing_batch._training_pair_key`）没有 explicit 分支，候选侧比较键永远是派生值；baseline 若用 explicit（9% 历史漂移行与派生分叉），候选与 baseline 只能 91% 可比。永远派生保证 **100% 同算法可比**。explicit 值保留在行内仅作审计（`dedupe_key_provenance`）。
3. `tests/`：
   - `test_qgis_processing_expanded_adapter.py`：3 个契约测试（adapter 键==权威派生逐键对比；同 DAG 同函数行键一致；描述+L3 后行走 `_dedup_keys` 全键可算 + training_pair 与同函数行一致）；
   - `test_freeze_qgis_processing_conversion_v2.py`：真实 294 行回归锁——结构三键 == 行内 explicit（explicit 优先行为），training_pair == 权威派生（永远派生行为）。
4. **冻结包重新生成**（本目录三个文件替换，两个阶段累计）。

## 冻结包影响（两个阶段）

**第 1 阶段（补 operator_sequence）**：
- 510 unique / 291 overlap **不变**；
- 510 个 `unit_reference_key` 中 **217 个变化**，与"294/507 中缺 explicit unified_training_pair_key 的行数 217"完全吻合。

**第 2 阶段（永远派生）**：
- **543 unique / 258 overlap**（+33 unit / −33 重合对）——正是"explicit 相同但派生不同"的 33 对历史漂移行被拆开。这是正确反映：候选侧比较键是派生，baseline 必须同算法可比。
- 相对第 1 阶段再变 33 个键。

**最终哈希（本目录当前版本）**：
- `cross_pool_baseline_v2.jsonl` = `7d62608275f494138d8e1b615a5aea4a5a2c3ed6ad99885e3a58812292d42bac`
- `hash_ledger_v2.json` = `074b5badf11d9ee41a5bd5586a48595b1a05b6b26a1891113986fd00d5f441b6`
- `summary_v2.json` = `559b57f629aaccc4ec4ee343dd73fb168b310fac80d8d5c5da7b289214233b16`

## 验证

- 测试 **15/15 通过**（helper_inline 5 + freeze 5 + adapter 5）；
- Ruff 0 问题；py_compile OK；
- 冻结可复现：重跑 freeze 与正式目录产物字节一致。

## 遗留风险

- 294/507 行 explicit 结构键与权威派生 200/200 不一致（历史生成器算法未统一）——**候选与 baseline 的结构键比较不可靠，跨池压重以 `unified_training_pair_key`（永远派生）为裁决键**（候选侧唯一可行公共算法）；结构键用于候选内去重与审计。
- 33 对历史漂移行（explicit 相同、派生不同）在 baseline 中成为独立 unit——压重效果等价（候选匹配任一键即压），但统计口径从 510/291 变为 543/258，引用旧数字的报告需更新。
- 若未来需要结构键全对齐，需收敛到单一共享实现（本修订未重构历史生成器，避免改动既有 authority 键值）。
