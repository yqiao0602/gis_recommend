# DC 规格：解码层修复实验（Decoding / Output Control，预注册）

日期：2026-09-24 冻结（跑前成文）
owner 裁定（2026-09-24）：FA 收口（Generation Control）；下一主线 = DC-0 baseline freeze → DC-1 trie 结构化解码 → DC-2 状态感知 EOS；**A1 不再调/训/DAPT，C2 冻结，先不碰 RL**。
规格：`transfer_phase2_fa_spec.md`（FA 已闭环，`afc5120`）；工具链：`665723d` harness freeze + V2a-P2 xgrammar 资产。

## DC-0：Baseline freeze（零训练，今日完成）

- **自由生成 baseline = 已锁定的 test-111 三臂预测**（RESULTS_LOCK_v1 + Protocol v2 重算 + FA 分解），不再重跑；判定基准数字以 `gate2_report.md` §1 为准。
- **续写控制 baseline = FA-D1 结果**（`fa_d1_results.json`）：stopped 91.3/76.6/79.2%，续写长度 62/104/92，注入 1.23/4.74/2.66。
- 生成夹具冻结：greedy、max_new=512（生成）/256（续写探针）、eos=[eos,pad]、prompt=route2 格式、parser=route2、tokenizer=Base。DC 全程不改。
- 可选 DC-0.1（GPU 空闲时）：C0/A1 各 20 行 greedy 重跑确定性抽查（与锁定预测逐字节比对；greedy 非严格确定，±少量行差异可接受并记录）。

## DC-1：Trie 结构化解码（核心实验）

### 约束范围（与 V2a-P2 同scope纪律：格式+目录，不含链接/DAG 约束）

对 P:/L: token 格式的 EBNF：
```
root ::= unit*  （unit 间空格分隔，EOS 任意位置合法）
unit ::= "P:" pid ":" opname | "L:" pid ">" pid
pid  ::= [a-zA-Z0-9_-]+
opname ::= <QGIS catalog 1,291 算子的嵌套前缀 trie>   ← V2a-P2 教训①：必须嵌套，防 xgrammar FSM 状态合并
```

### 四条 P2 教训的强制性设计

1. **EOS 显式放行**：每步 mask = grammar mask ∪ {EOS}——只封非法算子/格式续写，**不碰停止控制**。这是与 P2 的关键差异（P2 封死逃逸口 → hit_cap +14pp）；DC-1 若 hit_cap 上升 = 设计缺陷信号，预注册为红线。
2. **算子名嵌套 trie**（FSM 状态合并 bug）。
3. **mask 尺寸 = embedding 维度**（非 len(tokenizer)）。
4. **gold walk 前置门**：111 条 gold 测试目标全部被语法接受才准开跑（Gate B-revised 1565/1565 同款）。

### 臂与规模

- 主对照：**C0+DC 与 A1+DC**（test-111 全量，同 DC-0 夹具仅加 mask）；B1+DC 列为可选第三。
- 冒烟门：8 行受限冒烟（C0）——parse_ok=1.0、无合法输出被拒、时延/显存记录。

### 预注册判读（test-111，Protocol v2 + 行级 bootstrap CI）

| 判据 | 阈值 |
|---|---|
| **DC-1 对 A1 生效** | precision Δ CI>0 且 stopped/EOS 显著恢复 且 repetition ↓；**hit_cap 不得上升**（红线） |
| **无附带损伤** | A1 recall Δ CI 下界 > −0.05；**link F1 Δ CI ≥ 0 不排除 0 以下**（P2 教训：valid↑ 但 link 可能恶化）；C0+DC 四主指标不显著退化 |
| **失效** | precision 无显著恢复，或 hit_cap 上升，或 link 显著恶化 → 记录并转向 DC-2（EOS 结构化条件），**不调 trie 参数** |

## DC-2：状态感知 EOS / repetition control（DC-1 后另立 spec）

结构化停止条件（"graph 已成合法终点 → EOS 可选；否则降权/禁止"），非 blunt λ（P1 λ=20 教训）。DC-1 结果出来后设计，本 spec 只占位。

## 产物

`scripts/dc1_constrained_gen.py`（生成）、`docs/reports/transfer_phase2/dc/dc1_report.md`、gold-walk 审计、冒烟工件。判定与对比表按 owner 固定清单：Op F1 / Link F1 / Graph EM / EOS / hit_cap / repetition / parse_ok。
