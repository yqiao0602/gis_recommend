# Phase 0 前置确认 B：task_type Oracle vs Unknown 2×2 消融（M1 增强路线）

日期：2026-09-14（运行 09:53–10:09，A10 服务器）
性质：只读诊断；零训练、零 checkpoint 变更、benchmark lock 未触碰
checkpoint：`m1_r1_ckpt/best_gen_composite_model.pth`（epoch 18，SHA256 `97e61fd4…` 与 INFERENCE_CONFIG_FREEZE_v1 精确一致，运行前断言通过）
评测集：paper_v1 val 49 行（与 9月9日 M1-R1 诊断、M3-P1 评测同一文件 `m3_p0_val_49.jsonl`）

## 实验设计

9月9日的 49 行诊断（0/49，P/R 0.153/0.198）本身就是 **Oracle 条件**（`m1_r1_dev_eval.py` 从 platform/record_id 恢复真实 task_type 传入，并按类型设 expected_length）；benchmark 冻结协议则是 **Unknown + 固定长度 8**。两者之间混着三个变量（task_type、长度策略、任务分布），故在同一 49 行、同一进程内做 2×2：

| 条件 | task_type（模型输入） | expected_length | 对应协议 |
|---|---|---|---|
| oracle_len_type | 真实类型 | 按类型 mean（GEE 6 / qgis_506 2 / pattern 8，cap 15） | 9月9日诊断复刻 |
| unknown_len_type | "Unknown" (id 0) | 同上（用行元数据的真实类型） | 隔离 task_type 输入 |
| oracle_len_8 | 真实类型 | 8 | 长度分解 |
| unknown_len_8 | "Unknown" (id 0) | 8 | benchmark 冻结协议复刻 |

task_type 进入模型只有两个通道：task_type_id embedding（FiLM 条件）+ structured prompt 文本（paper_v1 profile 无 per-type median，动态长度先验从未建立）。eos_suppress 随 expected_length（按 9月9日公式；len 8 时 = 2，与冻结协议一致）。

## 主表（49 行，L3 层，无 bridge）

| 指标 | oracle_len_type | unknown_len_type | oracle_len_8 | **unknown_len_8** |
|---|---:|---:|---:|---:|
| Top-1 exact | 0 | 0 | 0 | 0 |
| code P | 0.1151 | 0.0075 | 0.1308 | **0.0000** |
| code R | 0.1391 | 0.0040 | 0.1966 | **0.0000** |
| SetF1 | 0.1216 | 0.0052 | 0.1478 | **0.0000** |
| 空预测率 | 0/49 | 0/49 | 0/49 | 0/49 |
| 首 token 去重数 | 26 | **5** | 27 | **5** |
| Define Projection 首 token | 0% | 24.5% | 2.0% | 24.5% |
| 首位吸引子 | L3_03_02_03 ×9 | L3_04_05_09 ×29（59%） | L3_03_02_03 ×5 | L3_04_05_09 ×25（51%） |
| 平均输出长度 | 5.45 | 3.88 | 6.29 | 4.12 |
| 平均长度误差 | +0.96 | −0.61 | +1.80 | −0.37 |
| EOS 终止 | 49/49 | 48/49 | 49/49 | 48/49 |
| wrong_family | 25 | 46 | 20 | **48** |

分平台：unknown_len_8 下 GEE（41 行）与 QGIS（8 行）**双双归零**（0.0/0.0）——塌缩是全局的；oracle_len_8 下 QGIS 行反而高于 GEE 行（P 0.176/R 0.347 vs 0.122/0.167）。

## 四个对比（同进程内，唯一/成对变量）

| 对比 | 含义 | ΔP | ΔR | ΔF1 | ΔDefProj首token |
|---|---|---:|---:|---:|---:|
| oracle_len_type → unknown_len_type | **task_type 效应**（长度策略不变） | −0.108 | −0.135 | −0.116 | +24.5pp |
| oracle_len_8 → unknown_len_8 | **task_type 效应**（固定长度 8） | −0.131 | −0.197 | −0.148 | +22.5pp |
| unknown_len_type → unknown_len_8 | 长度策略效应（Unknown 下） | −0.008 | −0.004 | −0.005 | 0 |
| oracle_len_type → oracle_len_8 | 长度策略效应（Oracle 下） | +0.016 | +0.058 | +0.026 | +2.0pp |

## 结论

**Q：task_type OOD 贡献了多少 M1-R1 的塌缩？——主导因素。**

1. **仅把 task_type 字符串从真实类型换成 "Unknown"（其余一切不变），val 上的 P/R 即从 0.13/0.20 塌到 0.00/0.00**，首 token 多样性 26–27 → 5，出现支配性吸引子（L3_04_05_09 51–59% + Define Projection 24.5%），wrong_family 46–48/49。benchmark 式塌缩在**近分布 val 文本上单独由 Unknown 条件复现**——OOD 任务文本不是产生塌缩的必要条件。
2. **长度策略是二阶效应**：Oracle 下固定 8 略有增益（ΔR +0.058）；Unknown 下无论长度策略结果都接近零。
3. **空预测率在全部四个条件下为 0/49**：benchmark 的 88/100 "空图"不是模型输出空链，而是 bridge 丢弃（50-code 覆盖外）所致——与 Phase 0-A 后的分析一致，token 层与 graph 层的"空"必须分开表述。
4. benchmark 上 Define Projection 100% 首 token vs val-Unknown 下 24.5%（首位是 L3_04_05_09）：**吸引子身份依赖文本分布，塌缩机制（Unknown 条件化失效 → 吸引子）是共有的**。
5. **对 M1 vs M3 混杂清单的量化**：task_type 条件是 M1 特有的、可量化的 handicap（M3 不消费 task_type；val 上代价 ΔP −0.13 / ΔR −0.20）。"M1 应该不至于这么弱"得到证实：benchmark 数字同时混杂了 OOD 文本 + Unknown 条件化，**低估了 M1 的近分布能力**（Oracle 下 val P/R 0.13/0.20、partial_overlap 主导），但 Oracle 条件下 M1 依然 0/49 exact——基础能力本来就低。

## 对 M1-R2 的直接含义

- R2 评测协议保持冻结（task_type=Unknown），因此 **DAPT 必须在 Unknown 条件下恢复条件化**才算数；"完美 R2"的形态就是 unknown_len_8 向 oracle 水平回归。
- 归因链更新：M1 benchmark 塌缩 = **Unknown 条件化失效（主导，本次量化）** + OOD 文本分布（放大器）+ 语言/领域先验不足（R2 量化）+ QGIS 监督半盲（Phase 0-A，训练侧结构性限制）。
- 给 owner 的备忘（**不改变当前冻结协议**）：benchmark 任务均为 QGIS 规划任务但无 task_type 元数据，未来协议版本可考虑类型推断（如喂 QGIS 侧类型），属协议变更，须升版本号并重锁 prediction hash，不追溯修改 v0.2.1 结果。

## 复现性与诚实记录

- 9月9日 anchor 复现：oracle_len_type **定性签名完全复现**（0 空预测、EOS 49/49、长度误差 +0.96 vs +1.04、首 token 多样、Define Projection 0%、0 exact），但数值漂移 P 0.115 vs 0.153、R 0.139 vs 0.198（超出 ±0.03 容差）。跨运行数值漂移疑似环境/内核差异；**本报告全部对比在同一进程内完成，2×2 对比不受漂移影响**，且效应量（ΔP −0.108/−0.131）远大于漂移幅度（~0.04–0.06）。
- 运行事故记录：首次部署的 wrapper 因显存瞬时波动误触发 + taxonomy 默认路径错误而失败（崩溃于模型加载前，无 CUDA 分配，不影响并行任务）；失败日志存档 `run_attempt1_taxonomy_path_error.log`，已修复（wrapper v2 门控改为零计算进程双确认；taxonomy 路径指向 SHA 核验一致的服务器副本）。
- 运行时长 16 分钟（4 条件）；gate：epoch 18、128 content tokens、79 transition states、beam 确定性通过。

## 复现命令

```bash
# 服务器（qwen35 环境，GIS_VOCAB_PROFILE=paper_v1_128）
python m1_phase0_b_tasktype_ablation.py \
  --checkpoint /home/qy/gee_llm_smoke/m1_r1_ckpt/best_gen_composite_model.pth \
  --out-dir /home/qy/gee_llm_smoke/m1_phase0_b
# 汇总重建（无需推理）：加 --aggregate-only
```
产物：本目录 `summary.json`（全对比）、`conditions/*.metrics.json|rows.jsonl`（逐行）、`gate.json`、`run.log`。
