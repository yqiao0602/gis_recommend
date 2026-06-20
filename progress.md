# 进度日志

## 2026-06-20：C++ API 痕迹→LLM→L3 规模化生产

### 全量 68k 批量生产（运行中）
- A10 上 `nohup server_batch_api_to_l3.py --max-scripts 0` 全量跑 68,845 脚本
- deepseek-chat + quality gates (前置 tool-name 筛 + conf≥0.60 + 自拒检测)
- 当前进度：~800 已处理/400 条产出，产率 ~62%（加前置筛后略高）
- 预计最终产出：~**20,000-30,000 条**

### 3k 批次完成（40 码扩充验证）
- 产出 1,011 条，产率 57%，置信度均值 0.70
- 39/40 码被使用，14 个新码激活
- 反复抽查质量稳定：高置信度(0.85+)几乎不犯错，低置信度(0.50-0.55)主要是纯参数定义脚本

### 2k 批次完成
- 产出 804 条，产率 62%，置信度均值 0.71
- 2k+3k 合并去重：1,815→1,150 唯一链

### 脚本
- `llm_generate_l3_from_api_traces.py`：本地版 API 痕迹→L3（提取+LLM+质量门控）
- `server_batch_api_to_l3.py`：服务器批量版（checkpoint 恢复+find 扫描）
- 辅助脚本：`_analyze_poc_traces.py`, `_analyze_3k_quality.py`, `_audit_3k_final.py`, `_merge_dedup.py` 等

### Key 管理
- deepseek-chat 临时 key: sk-89eb3f39563c470180aedeb6da3db5c1（批量生产用）
- 服务器端代码通过 env var DEEPSEEK_API_KEY 读取，不落盘

### Git 提交（待提交）
- 新增脚本 + task_plan/findings/progress 更新
- 专利材料修改（`docs/patent/`，无关）

## 2026-06-19/20：LLM 描述→L3 大规模生成 + Phase 7 完成 + Phase 8 启动 + C++ API 路线

### LLM 批量生成（突破）
- `llm_generate_l3_from_facts.py`：deepseek-chat + 精简 25 码 prompt，20k 描述→L3
- **产出：19,754 条训练样本**，矢量 token 占 78%
- POC v3 验证：13/15 成功（87%），0 空返回

### 统一训练集
- 合并 LLM(19,754) + AST(1,374) + 种子(323) → 去重后 **10,768 条**
- 94% 矢量相关，是 Phase 6/7 的 **7.8 倍**
- 输出：`vector_training_samples_UNIFIED.jsonl`

### Phase 7（AST 1,374 + relax + α=0.8）
- 训练 32/50 epoch early stop（composite=0.2842, best epoch 20）
- 评测结果 vs Phase 6 **基本持平**（vec exec 0.40→0.40）——1,374 条仍不足以克服 99.3% 栅格

### Phase 8（统一训练集 10,768，已在跑）
- 10,768 样本合并进 labeled_workflows（87,652 total, 72,263 train）
- `train_v4_6_vector_unified.py` 在 A10 运行中（epoch ~14/50）
- 目标：10,768 条 94% 矢量能否真改 L3 输出

### C++ API 痕迹→LLM→L3 POC（新路线，2026-06-20）
- 思路：把 C++ API 调用序列（semantic_role + description）喂给 LLM→反推 L3
- script_03 验证：API_only=Reproject→Buffer→SpatialJoin→FieldCalc→Export **完全吻合**真实链
- 10 脚本小规模：6/10 合法 L3（BAD 因 prompt 格式，好修）
- 这是融合路线 1(地面真相约束) + 路线 2(LLM 理解) 的最优解

### Git 提交
- `10414ee` LLM L3 generation + QGIS ops converter
- `8a3ea86` task plan update

## 2026-06-17：重训 + Demo

### 重训（阶段 6）
- **10:48** 训练启动：`train_v4_6_vector_fix.py` 在 A10 上
  - 77,981 workflows（76,884 原版 + 1,097 矢量）
  - train/val/test = 62,592 / 7,694 / 7,695
  - 50 epoch（前 10 TF → 后 40 AR-SS），~11.5 it/s
  - checkpoint 目录：`outputs_v2/transformer_checkpoints_v4_6_vector_fix/`
- 进度：Epoch 1→10 TF 完成，Epoch 11→进入 AR-SS 阶段
- 当前状态：**Epoch ~18/50**，loss 正常下降（~5→10 范围），0 错误
- cron `aac9349b` 每 45 分钟监控

### 提交记录（6月17日）
- `feat(data): expand QGIS-L3 crosswalk + alias normalization (+85 l3_bridge, 39.8% mapped)` → `1ccef83`
- `feat(data): v2 vector training set from complete QGIS samples (real descriptions)` → `2360191`
- `feat(train): merge + training wrapper for vector-rebalanced V4.6 retrain` → `9d26837`
- `feat(eval): 3-way comparison scorer (baseline vs V4.6 vs V4.6-vector-fix)` → `24ff54c`
- `feat(eval): standard QGIS workflow JSON builder (alg-id chain -> processes + params + links)` → `0a8d545`
- `feat(demo): interactive QGIS workflow QA demo (NL task -> JSON chain -> conversational Q&A)` → `f77a6d8`

### 测试
- 28 测试绿（`test_qgis_chain_metrics` 10 + `test_open_landing_report` 9 + `test_vector_training_builder` 3 + `test_workflow_json_builder` 3 + `test_qgis_operator_registry` 1 + `test_runtime_consistency` 2）

## 2026-06-13/14：T3 评测 + V4.6 实测

### Phase A (open_landing 80 题) — 2026-06-13
- 21 测试绿（T3 评测框架），已合并 main
- 检索基线数：overall validity=0.951 io_exec=0.801 executable=0.537
- 关键发现：executable ≠ correct（C 档有效性 > A 档）
- V4.6 数（commit `78ae715`）
- Phase A: 基线 vs V4.6 模态对比表产出

### Phase B (held-out 150 题) — 2026-06-13
- L3 set_f1=0.531（首个 correctness 数）
- ② 和 ③ 通过 task_type 分解证实解耦
- 合并 main（`78ae715`）

### LLM 切换 deepseek — 2026-06-14
- 全局替换 6 个配置点的 qwen→deepseek-v4-pro
- 移除 3 处硬编码 `sk-6d6a…` 旧 key
- 描述脚本鲁棒性修复（max_tokens 4000 + reasoning_content 回退）

### 语料诊断 — 2026-06-15
- `analyze_corpus_modality.py`：量化 99.3% 栅格 / 0.2% 矢量
- 合并 main（`c6b1573`）

### 服务器数据探查 — 2026-06-14/15
- paramiko 只读连接，A10 GPU 确认
- 全量数据盘查：`docs/server_data_inventory.md`
- QGIS 链抽取（4,097 raw → 2,175 唯一去重）
- 链↔描述 join（2,733 完整样本）

### 矢量训练集构建 — 2026-06-16
- crosswalk 扩充（101→186 l3_bridge）+ alias 归一化
- v2 矢量训练集：1,097 条（954 矢量相关），已合并 main

### 交互 Demo — 2026-06-17
- workflow JSON 格式敲定 + builder（TDD 3 测试）
- `demo_interactive_workflow_qa.py` NL→JSON→deepseek QA 实测通过
- 参数追问 + 数据流追问均基于 workflow context 正确回答

## 环境
- 本地：Windows 11 Pro，Python 3.12.6，Git Bash
- 服务器：10.191.2.38 (mdzhang)，qy@10.191.2.38
  - GPU：NVIDIA A10，CUDA 12.1
  - conda env：transformer（torch 2.2.2+cu121）
  - 项目：`/home/qy/system_redesign`
  - yll 数据：`/home/yll/GEE`（只读）
- LLM：deepseek-v4-pro via api.deepseek.com/v1（key 环境变量，不落盘）
- Git workflow：feat 分支、Conventional Commits、`--no-ff` 合并
