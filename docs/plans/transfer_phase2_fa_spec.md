# FA 规格：Gate 2 失败归因诊断（Failure Attribution，预注册）

日期：2026-09-23 冻结（跑前成文；判据跑后不得回改）
定位：roadmap §3"Gate 2 不过 → 归因分析"的执行件。**零新增训练**；除 FA-D1 的教师强制前向（GPU 分钟级）外全部 CPU/离线复用已锁工件。
待裁决问题：A1 的负迁移落在哪一层——**Planning（任务→该做什么）/ Grounding（语义→具体算子）/ Generation Control（停止/重复/长度）**。

## 0. 对 owner 提案的两处设计修正（理由）

1. **D2/D3 不用生成式探针**。"Task→抽象工作流生成"与"给定抽象工作流→QGIS 实现"对三臂都是**从未训练过的任务格式**——生成式测量会混入"能否服从未见格式"，无法归因到 Planning/Grounding 本身。替代：
   - D2 = **已有锁定预测的语义投影**（预测与 gold 的算子都映到语义类后算 F1）——零推理，直接测"实际行为在计划层的好坏"；
   - D3 = **假阳性分解**——A1 相对 C0 多出的错误算子，按"同族混淆（grounding 失败）vs 异族注入（generation control 失败）"分解。
2. **QGIS 语义映射不存在**（catalog 无语义字段，已核验），FA-D2 前置构建 `qgis_op_semantic_map_v1`：确定性关键词规则表，只覆盖实际出现词汇（test-111 gold∪三臂预测 ∪ train gold 的算子并集），歧义→OTHER_UNMAPPED，规则表+覆盖率审计随结果冻结。

## 1. FA-D1：QGIS 输出空间能力（GPU 分钟级）

- 序列：v2a_A train（1,334）graph 目标经 `graph_to_text` 的 **P: 算子序列**——两臂训练目标的原格式，真 in-distribution；held-out = dev+test 链（231），与 train 做链不相交核验。
- 测量：teacher-forced next-op **top-1/top-3**，三臂（base+C0 ep20 / base+A1 ep15 / base+B1 ep18），频率基线 B0/B1/B2（train 链统计，Gate 1 同款构造）；输出按各自训练格式。
- 控制子探针 FA-D1c：gold 前缀起始的**自由续写 256 token**，量化 EOS 命中/重复 run/长度比——单独暴露 Generation Control 层。
- 判读：A1 next-op ≈ C0 但续写控制差 → 故障在控制层；A1 next-op 即差 → 输出空间受损。

## 2. FA-D2：Planning 层（CPU，零推理）

- `qgis_op_semantic_map_v1` 冻结规则表 → 对 test-111 三臂锁定预测与 gold 做类投影 → **投影 op F1 / 投影 precision-recall / 投影 class-pair link F1**。
- 判读：A1 投影 F1 ≈ C0 而具体 F1 ≪ → Planning 完好、故障在 Grounding/控制；A1 投影也 ≪ → Planning 受损（此时 GEE 数据的唯一正确用法是 B1 式结构监督，而非 DAPT）。

## 3. FA-D3：Grounding vs Control 分解（CPU，零推理）

- 对 A1 相对 C0 的假阳性算子实例分解：**同族混淆**（投影类 ∈ gold 类集合 = "想对了做错了"）vs **异族注入**（投影类不属于任何 gold 类 = "不该说的说了"）。
- 判读：A1 的精度损失以异族注入为主 → Generation Control 故障（与 FA-D1c 互证）；以同族混淆为主 → Grounding 故障。

## 4. 预注册结果→行动矩阵

| FA 读数 | 归因 | 下一轮杠杆 |
|---|---|---|
| D1≈ 且 D2≈ 且 D3 异族为主 | Generation Control | 解码/输出机制（V2a-P2 的结构化解码资产在此复用）；**不加任何数据** |
| D1 差 且 D2≈ | QGIS Grounding | QGIS 侧 grounding 强化（catalog 感知解码/更多 QGIS SFT，配方不变） |
| D2 差 | Planning 受损 | GEE 数据若再用只能走 B1 式结构监督通道；DAPT 路线关闭 |
| 全差 | 全面受损 | 回到 QGIS 监督数据本身 |

**硬纪律：FA 完成前不启动任何新训练**；GEE DAPT v2/v3、更大 probe 等在归因落定前一律不排。

## 5. 产物

`scripts/fa_semantic_map_v1.json`（规则表+审计）、`scripts/fa_d1_nextop_probe.py`、`docs/reports/transfer_phase2/fa/fa_report.md`（诊断矩阵 + 判读）。全部判据与规则表先于运行冻结。

## 6. 已核验资产状态

- P:/L: 序列格式 = 训练目标原格式 ✓（`harness.graph_to_text`）
- QGIS 算子→语义类映射：**不存在**，FA-D2 前置构建（见 §0.2）✓
- test-111 锁定预测：在盘（RESULTS_LOCK_v1）✓；GPU 窗口：FA-D1 仅需分钟级，排卡待 3f 线/yyt 训练间隙
