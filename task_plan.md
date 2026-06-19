# 任务计划：QGIS 工作流推荐系统 — 评测体系 + 矢量修复

## 目标
建立系统无关的多指标 QGIS 链评测体系（①②③），用 V4.6 模型实测并定位"矢量能力缺失"的根因（数据缺口），补矢量训练数据并在 A10 上重平衡重训，验证矢量能力可修复。

## 当前阶段
阶段 7 — V4.6-vector-fix-v2 重训中（A10，1374 矢量训练集，freq_weight_alpha=0.8，cron 1846c88d 盯进度）

## 各阶段

### 阶段 1：T3 评测体系架构 ✅
- [x] `score_qgis_chain` (①②③) 纯函数、依赖注入、无 Neo4j
- [x] `qgis_operator_registry` (alg-id keyed, 1291 算子)
- [x] `aggregate_by` / `open_landing_report` / `score_open_landing` CLI
- [x] **21 测试绿**，已合并 main（`dd3f1a6`）
- [x] 检索基线 80 题实测 → **关键发现：可执行 ≠ 正确**（C 档有效率 > A 档）
- **状态：** complete

### 阶段 2：V4.6 模型实测（Phase A + B）✅
- [x] Phase A：V4.6 text-only 80 题 → 对比检索基线（按模态）
- [x] **发现：模型把矢量任务塌成栅格 L3**（vec executable 0.875→0.350，unique_ratio 0.525→0.200）
- [x] Phase B：150 题 held-out（真实 task_type + 金标 L3）→ **首个 correctness 数 L3 set_f1=0.531**
- [x] 证实 ② 和 ③ 解耦（executable≠correct）
- [x] 25 测试绿，已合并 main（`78ae715`）
- **状态：** complete

### 阶段 3：根因诊断 — 语料模态偏斜 ✅
- [x] `analyze_corpus_modality.py`：训练语料 **99.3% 栅格 / 0.2% 矢量**
- [x] task_type 词表 = 47 个主题类，**无模态轴、无矢量为主的主题**
- [x] 结论：**矢量是数据缺口，不是推理能修的**
- **状态：** complete

### 阶段 4：建矢量训练集 ✅
- [x] 服务器数据审计（`docs/server_data_inventory.md`）
- [x] 从 yll 的 QGIS 抽取池挖链（~4,097 raw → 2,175 去重）
- [x] `facts_summary1000` 真实描述 join → **2,733 完整样本(链+描述+类型)**
- [x] ①+② 归一化 + crosswalk 扩充（101→186 l3_bridge）
- [x] **v2 矢量训练集：1,097 条（描述→L3），954 矢量相关**，≈ 本地 323 的 3x
- [x] LLM 全局切换 deepseek-v4-pro（含移除 3 处明文旧 key）
- [x] 28 测试绿，已合并 main
- **状态：** complete

### 阶段 5：交互式 Demo ✅
- [x] workflow JSON 格式（参数 description 无 value + links）
- [x] `workflow_json_builder`（TDD, 3 测试）+ `build_workflow_jsons.py`
- [x] `demo_interactive_workflow_qa.py`（NL 输入→JSON 链→deepseek 对话式 QA）
- [x] 实测验证：追问参数+数据流，LLM 基于 workflow context 回答
- **状态：** complete

### 阶段 6：重训（矢量修复 v1）✅
- [x] 合并 1,097 矢量样本进 labeled_workflows（77,981 total）
- [x] 重平衡通过 `compute_token_freq_weights`（L3_02 罕见码高 CE 权重）
- [x] 推代码+数据到服务器（qy@10.191.2.38，A10 GPU，conda env transformer）
- [x] 干训冒烟通过（cuda:0，数据加载 OK）
- [x] 全量训练完成（50 epoch，composite=0.5972 best@epoch 41，0 错误）
- [x] 三向对比评测完成：vec executable 0.35→**0.40**(+0.05), unique_ratio 0.20→0.25, io_exec 0.787→0.812
- [x] **核心发现：L3 层没变** — vecfix 对 40 个矢量任务，0/40 是矢量主导 L3，98% 仍是栅格码
- [x] **1,097 条矢量在 76,341 条栅格中被绝对淹没。freq_weights 不足够。需要 50x+ 上采样 + 大幅扩数据。**
- **状态：** complete（git: `d0d4468`）

### 阶段 7：大幅扩矢量 + 激进上采样 + ③ 真·L3 缺口补全 🔄
- [ ] ③ 真·L3 词表缺口补全（~7 个核心矢量原语：Simplify/Heatmap/SplitLines/DeleteHoles 等→94→~101）
- [ ] 放宽严格映射（含不可映算子则保留其余，不整链丢弃）→ mapped_rate 40%→~70%，得 ~1,500+
- [ ] 合并本地 323 + v2 1,097 → 统一矢量训练集
- [ ] 上采样 50x+（矢量占训练步 ~50%+，改 merge&train 配置）
- [ ] 服务器重训 V4.6-base（epoch 匹配、early stop）
- [ ] harness 重评矢量（Phase A 40 题 + 可能选有金标 L3 的链做 ③）
- **状态：** in_progress

### 阶段 7：后续（待定）
- [ ] 若重训有效 → 扩大量（放宽映射 / 扩 crosswalk ③ 真·L3 缺口 / 抽 data-QGIS 53k）
- [ ] GPT-4o 横评（等矢量能力补齐后）
- [ ] 服务器环境长期化（配 SSH key 免密 / 训练常态化）

## 已做关键决策
| 决策 | 理由 |
|------|------|
| 评测多指标（①②+③④）而非单维度 | 数据证明 executable≠correct，横评必须多轴 |
| ③ correctness 走 L3 级 set_f1 | 平台无关、order-invariant，金标 L3 必有 |
| 矢量修复走重训（非推理 trick） | 语料 99.3% 栅格、无矢量 task_type 可 cue |
| crosswalk 补全走①② 不动词表 | 大多缺映射非缺原语；③ 真 gap 仅 ~7 个核心算子 |
| LLM 换 deepseek-v4-pro | 推理模型，描述质量好；max_tokens 需 ≥4000 |
| 重平衡走 WeightedRandomSampler（token freq），非重复索引 | splits 校验拒绝重复；CE loss 给罕见 L3_02 更高权重更优雅 |

## 遇到的错误
| 错误 | 情况 | 解决方案 |
|------|------|---------|
| exec 分类器 outage（~2 小时） | Bash 全部被门控 | 设 cron 自动重试 + 用户 `!` 前缀绕过 |
| split 校验：train_indices 重复 | WeightedRandomSampler 不应复制索引 | 改 splits 为单次添加，靠 freq_weights 重平衡 |
| deepseek 描述生成频密空返回 | 推理模型 max_tokens=800 偏小 | 改为 4000 + reason_content 回退 + JSON 子串提取 |
| L2 池 steps.csv glob 返回 0 | 93,900 文件炸 shell argument list | 改用 `find` 命令 |
| qgis↔native 别名未归一化 | 106 个 pending + 21 native_bridge 未生效 | expand_qgis_l3_crosswalk.py 加别名 |
| paramiko ssh 超时 | 大输出时管道超时 | 后台 nohup + Monitor + cron 异步查 |

## 备注
- 服务器密码/API key 不落盘，仅本会话内联使用
- 服务器 `/home/yll/GEE` 只读 / `/home/qy/system_redesign` 为工作区
- git-workflow 使用 feat 分支、Conventional Commits、`--no-ff` 合并
- 详细发现见 `docs/server_data_inventory.md` + `memory/v46-eval-findings-2026-06.md`
