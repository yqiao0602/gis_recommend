# FA 报告：Gate 2 失败归因诊断（D2/D3 已完成，D1 待 GPU 窗口）

日期：2026-09-23
规格：`docs/plans/transfer_phase2_fa_spec.md`（预注册，`0c17810`）
状态：**FA-D2/D3 完成；FA-D1 待分钟级 GPU 窗口——当前归因为初步判定，D1 落地后终判**

## 0. 前置工件

- `scripts/fa_semantic_map_v1.json`：确定性规则映射 v1（29 类、404 观测算子、**覆盖率 94.56%**；188 长尾算子/639 实例如实保留 OTHER_UNMAPPED，未强行归类）。精化遍声明：两小批规则修订（规则的系统性缺口：select/extract 同意图对、mapcalc/proximity/statistics 族、select-extract 不对称修正），随后冻结。

## 1. FA-D2：Planning 层（语义投影 F1，test-111，bootstrap CI 行级 1 万次）

| | C0 | A1 | B1 |
|---|---:|---:|---:|
| 投影 op F1（行均） | 0.528 | 0.485 | **0.531** |
| 投影 link F1（行均） | 0.328 | 0.299 | **0.355** |

| Δ | 点估计 | CI95 | 判读（预注册：CI∋0 = Planning 保留） |
|---|---:|---|---|
| A1 − C0 投影 op | −0.043 | [−0.089, +0.004] | **Planning 保留**（边界，点估计轻度负） |
| A1 − C0 投影 link | −0.029 | [−0.084, +0.024] | n.s. |
| B1 − C0 投影 op | +0.003 | [−0.047, +0.054] | ≈ C0 |
| B1 − C0 投影 link | +0.027 | [−0.039, +0.090] | n.s.（点估计正，与 Gate 2 route2 link 信号同向） |
| B1 − A1 投影 op | +0.046 | [+0.001, +0.092] | B1 > A1（显著） |

**结论：A1 的 Planning 层未受显著损伤**——语义类选择质量与 C0 统计不可区分（轻度负趋势）。Gate 2 的 −0.077 具体 F1 差距**不是**"不知道该做什么类型的操作"。

## 2. FA-D3：假阳性分解（Grounding vs Generation Control）

| | FP 总量 | 同族（Grounding 侧） | 异族（Control 侧） | 异族占比 |
|---|---:|---:|---:|---:|
| C0 | 309 | 136 | 173 | 56.0% |
| **A1** | **688** | 410 | 278 | 40.4% |
| B1 | 426 | 274 | 152 | 35.7% |

- A1 的额外 FP 量（688−309=379）分解：**同族 +274（72%）/ 异族 +105（28%）**——精度损失的主体是"**对的族、说过头**"，不是"说错族"。
- A1−C0 异族占比差 −0.156 CI [−0.390, +0.108]（n.s.，点估计偏同族）。
- **A1 的签名注入**：`native:fixgeometries` 单算子 200 个 FP 实例（异族 111 + 同族 89）——一个高频"万能整形"算子被大量注入到 gold 完全没有该族的行里；同族侧 `fieldcalculator` 92 / `countpointsinpolygon` 91 / `fixgeometries` 89 同样是**训练频次最高的管道算子**。A1 异族 top 里还有 4 个 `n` token（截断半 token 解析伪影，已识别）。

## 3. 初步归因（待 FA-D1 终判）

三线证据收敛指向 **Generation Control（输出纪律）层**：

1. D2：Planning 保留（投影 CI∋0）——"选哪类操作"没坏；
2. D3：额外 FP 的 72% 是同族过量发射（"对的族说过头"），异族注入集中于最高频管道算子——不是 Grounding 混淆主导；
3. Gate 2 可靠性块：hit_cap ×4、repetition ×2、recall 完好 precision 崩——同一个故事。

与 Gate 1 闭合：GEE 语料的局部转移统计（高频管道算子的高频续写模式）经 DAPT 成为生成先验，在 QGIS 输出上表现为**过度生产**。

**待 FA-D1 终判的两问**：① teacher-forced next-op：A1 在正确上下文中的单步选择是否真 ≈ C0（排除 D2 投影掩盖具体劣化）；② gold 前缀自由续写：A1 的 EOS/重复/长度控制是否显著劣于 C0（直接证伪/证实控制层归因）。

## 4. 行动矩阵落点（若 D1 证实）

→ **Generation Control**：下一轮杠杆 = 解码/输出机制（V2a-P2 结构化解码资产直接适用），**不加任何数据、不重启 DAPT、不调 A1**。

## 5. 工件

`scripts/fa_semantic_map_v1.json`（冻结映射）、`scripts/fa_build_semantic_map.py`、`scripts/fa_d2_d3_analyze.py`、`docs/reports/transfer_phase2/fa/fa_d2_d3_results.json`（全量 bootstrap + 分解明细）。
