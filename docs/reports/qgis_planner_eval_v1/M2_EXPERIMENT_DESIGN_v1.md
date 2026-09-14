# M2 实验设计 v1（待 owner 批准后执行）

日期：2026-09-14
状态：**DESIGN — 未开跑**。语料组装、训练配置、判定框架均需 owner 确认。

---

## 1. 研究问题（单一）

> **GIS domain adaptation（DAPT）能否在已具备基础 workflow generation 能力的通用 LLM 上，进一步提升 operator selection（recall / 长尾覆盖），而不损害 sequence control？**

注意：M3-P2-T1 已证明 sequence control 可由训练监督改善。M2 的 SFT 阶段**统一使用 P1 的 plain SFT 配方**（不叠 T1 的 EOS 加权），保证与 M3-P1 严格可比；T1 是已知的独立改进分支，不进入 M2 的变量空间。

## 2. 实验臂与变量隔离

```text
M3-P1   post-trained Qwen 9B ──────────────→ SFT          （已有：F1 0.1605）
M2-C0   Qwen 9B-Base ──────────────────────→ SFT          （对照：隔离"后训练/instruction tuning"效应）
M2-P1   Qwen 9B-Base ─→ DAPT ────────────────────────────（中间检查点：DAPT-only）
M2-P2   Qwen 9B-Base ─→ DAPT ─→ SFT                       （主线）
```

| 比较 | 隔离的变量 | 回答 |
|---|---|---|
| M2-C0 vs M3-P1 | 底座差异（Base vs post-trained），SFT 完全相同 | 后训练对 GIS workflow 生成的影响 |
| M2-P2 vs M2-C0 | 仅 DAPT | **domain adaptation 的净增益（M2 核心问题）** |
| M2-P1 vs M2-C0 | 仅 DAPT（无 SFT） | DAPT 单独能带来什么 |

所有臂的 SFT 数据 = paper_v1 8,817 行（与 M3-P1 同一份 `m3_p1_train.jsonl`，SHA 锁定）；推理/评测/lock/scorer 全部沿用冻结栈，仅 checkpoint 不同。

## 3. DAPT 语料（Gate 1——需 owner 拍板的第一个决定）

### 3.1 候选语料盘点（2026-09-14 实查）

| 候选 | 位置/状态 | 性质 | 规模估计 |
|---|---|---|---|
| A. GEE JavaScript 脚本 | `data80000/script_*.txt`（SFT 8,283 行的 source_path 指向它；**服务器常规路径未找到**，需定位或从来源恢复） | 真实 GIS 工作流代码 | ~8 万脚本 |
| B. QGIS Processing 源码 | 服务器有 `qgis_raw_py_hashes_20260721.tsv` + strong-signal 路径清单；资质审查线已处理过全文 | 算子实现+docstring | 1291 算子源码 |
| C. 算子调用点描述 | `docs/reports/.../direct_descriptions_v4/`（source_snippet + task_description，896KB 样例已验证） | 源码回放的结构化描述 | 数千单元 |
| D. GEE 算子目录 | 服务器 `/home/qy/gee-operators/*.json`（full/by_category，2025-11 快照） | 算子语义描述 | 1,425 算子 |
| E. API 语义/模式行数据 | 数据建设阶段产物（3,209 API 语义单元 / 4,880 API 模式） | PyQGIS API 调用语义 | ~8k 单元 |
| F. Neo4j KG 算子描述 | 本地 bolt://localhost:7687（QGIS 1291 + GEE 1425 带 description） | 结构化算子知识 | 2,716 算子 |

### 3.2 资格标准（什么数据有资格做 DAPT）

1. **领域正当性**：真实 GIS 源码/文档（非合成、非 LLM 生成）
2. **train-only 血缘**：只允许来自 paper_v1 训练侧血缘的源（benchmark 的 source_exclusion_ledger 已保证 final/dev/refusal 与训练源互斥——DAPT 语料继承同一排除）
3. **泄漏门（Gate 2 复用）**：对 benchmark final-100/dev-20/refusal-12 任务文本做 6-gram + token-signature 检查，ALL CLEAN 才能冻结
4. **不含答案结构**：DAPT 文本不得包含 L3 链或 task→chain 配对本身（A/B/C 候选是源码与描述，天然不含；需断言检查）
5. **组成配比冻结**：各候选的混合比例在 Gate 1 产出 manifest 后冻结，不再中途调整

### 3.3 建议（待拍板）

首轮 DAPT 组成建议 **B+C+E 为主、A 为辅**（若 A 能定位恢复）：QGIS 侧知识是 benchmark 的直接攻击面，GEE 脚本量大但与 final-100 的 QGIS 任务域距离更远。规模目标：**20-50M token**（DAPT 常规量级；超出无益于首轮单变量问题）。

## 4. 训练配置

| 阶段 | 配置 | 备注 |
|---|---|---|
| DAPT（M2-P1/P2） | QLoRA NF4，LoRA r16 α32 qkvo（与 SFT 同栈），causal LM loss，lr 1e-4，**epoch 数待定（建议 1-2）** | 语料 manifest SHA 锁定后开训 |
| SFT（M2-C0/P2） | 与 M3-P1 逐字节同配方（plain SFT，batch 4×8，lr 1e-4，1 epoch，max_len 512，样本权重） | 唯一差异是初始化权重 |
| M2-P2 的衔接 | DAPT adapter → SFT（从 DAPT 后权重继续，同一 LoRA 或先合并再开新 LoRA——**待定，建议后者以保持 SFT 阶段与 C0 对称**） | 需 owner 确认 |

## 5. 评测与判定（预注册）

流程：每臂 pilot（49 行 val + dev-20 runaway 探针）→ 门通过才跑 final-100 + refusal-12 → lock → 冻结 scorer → 账本。

### 成功标准（三层，同 M3-P2 框架）

```text
第一层（性能）    Operator F1 / Recall / Precision / Edge F1 / EM
第二层（选择）    首算子正确率 / set recall≥0.5 行数 / 长尾15 code 命中数
第三层（无反噬）  runaway / 空图 / recall 不得显著低于 M2-C0
```

### 预注册预期（不作结论）

- 若 M2-P2 > M2-C0 且第三层无反噬 → domain adaptation 有净增益
- 若 M2-P2 ≈ M2-C0 → M3 的 operator selection 瓶颈不在领域语言先验（指向数据量/映射监督）
- 若 M2-P2 < M2-C0 → DAPT 干扰 workflow generation（本身就是可发表结果）
- 若 M2-C0 ≪ M3-P1 → post-trained 底座的指令跟随能力是 SFT 生效前提（重要中间发现）

### 长尾 15 code 的处理

首轮**不做定向增强**（保持单变量）。第二层指标中单独记录 15 个低覆盖 code 的命中数，作为 M2-P3（数据增强轮）的依据。

## 6. 执行序（批准后）

```text
Gate 1  DAPT 语料组装 + 定位 data80000 → 组成/配比 manifest（SHA）
Gate 2  泄漏检查（benchmark 6-gram + token-signature）ALL CLEAN
Gate 3  语料冻结 + 训练配置 freeze manifest
Run 1   M2-C0 训练 → pilot 门 → final-100 → lock → scorer → ledger
Run 2   M2-P1（DAPT-only，中间检查）→ 同上
Run 3   M2-P2 训练 → 同上
汇总    M1/M2-C0/M2-P1/M2-P2/M3-P1(/T1) 全矩阵表
```

## 7. 待 owner 拍板的 5 个决定

1. **DAPT 语料组成**：§3.3 建议（B+C+E 主、A 辅）是否接受？A（GEE 80k 脚本）是否值得花力气定位恢复？
2. **DAPT 规模目标**：20-50M token 是否接受？
3. **DAPT epoch**：1 还是 2？
4. **M2-P2 衔接方式**：DAPT adapter 合并后开新 LoRA 做 SFT（建议），还是同一 LoRA 连续训？
5. **执行顺序**：M2-C0 先行（对照先行，风险最低）确认无误后再跑 DAPT 臂？
