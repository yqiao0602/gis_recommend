# Route-2 v2 ⑦ Stage-1 训练协议 v1（2026-09-24，owner 裁定，冻结）

## 冻结协议总览

```
128,447 GEE → author-disjoint split（101,513/11,075/15,859，泄漏零）
──────────────── Stage-1 Mixed Training ────────────────
token 比例（按实际 token 非样本数）:
  Task → Workflow Plan      60%
  Dependency / Completion   10%
  Reconstruction            10%
  W4 判别/修复              20%（硬顶 ≤25%）
  Chain LM                   0%（一个 token 都不给——保 A1 归因清洁）
配方: Qwen3.5-9B-Base + QLoRA NF4 r16 α32 / lr 1e-4 cosine / eff batch 32
      / max_len 1024（与 P0 三臂严格同构）
第一轮 1 epoch → Gate-dev → 全单项过门 + 加权分最高 → 冻结
FAIL → 同协议续训（不换目标/不换数据/不引入新数据）
```

## 截断规则（⑦-5 修正版）

max_len 1024 保持；**Task 完整保护**（禁左截 Task——截掉任务目标即摧毁
W3 输入）；超长从 **Plan 尾部截断**；truncation 全量入审计字段。

## Capability Gate（两级 + 双条件 + 硬前置）

```
Gate-dev  → checkpoint 选择（先全部单项过门，再比加权分）
Gate-test → 最终 PASS/FAIL（永不参与 checkpoint 选择）
每项:  score ≥ absolute floor  AND  score ≥ Base_zero-shot + Δ_i
阈值:  正式训练前用冻结 Base zero-shot 跑完整 gate 后预注册
```

| 子测试 | 内容 | 修正说明 |
|---|---|---|
| W1 | 已知操作概念 + **新上下文 / 低频算子 / 词面变化** 的 I/O 预测 | **修正**：不用完全未见操作概念（模型无从知道 = 测不了 reasoning）；反背模板主力移至 W3 新组合 |
| W2 | 合法后继判别 + 非法连接识别（程序生成负例） | — |
| W3 | **改写任务 → Plan**（deepseek 意图改写，非复述）+ **新操作组合**（组合泛化主战场） | — |
| W4 | 污染链判别/修复（程序合成） | — |
| 交叉拦截 | W3 高而 W1/W2 低 → 模板记忆 flag → 直接 FAIL | ⑦-4 硬条件落实 |

**checkpoint 选择权重**：W1 0.20 / W2 0.25 / W3 0.40 / W4 0.15——但
**先过全部单项门槛，再比加权分**（高 W3 低 W1/W2 的 checkpoint 不可能
靠平均晋级）。

## 成功标准（范式转变）

> **Stage-1 的成功标准不是 loss 降够低，而是 W1-W4 能力门真正通过。**

这是"冻结 Stage-1 生成 Teacher Plan 才有逻辑意义"的前提。

## 边界（自动生效）

QGIS 数据零接触 Stage 1（含 dev/test）；gate 全自动评分无人工判卷；
gate 数据全部来自 GEE author-disjoint dev/test split + 程序合成负例 +
deepseek 改写任务（三者均不进训练流）。

## 执行序列（①→⑦ 全冻结后的工作状态）

```
⑥ 三件 CPU 工程产物（现在建）:
   Pipeline 侧可建: Schema / Validator / Generator / Leakage Audit /
   Provenance / Tests
   生成动作后置: 1334/120/111 Teacher Plans 等 Gate PASS
⑦ 协议已冻结（本记录）→ Stage-1 实验按此准备（暂不启 GPU 训练）
```

完整因果链：⑥产物 → ⑦协议 → Stage-1 训练 → 门 PASS → 冻结 →
Teacher Plans → B2。
