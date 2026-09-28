# GEE 分层抽样批次准入与首批训练集扩展

日期：2026-07-31

## 结论

冻结的 30-source 分层审核为 30/30 pass，point precision=1.0，Wilson 95% lower=
0.8864866，critical failure=0。按照“确定性全批门禁 + source-disjoint 分层抽样 + 批次级准入”
策略，该审核授权同一冻结规则和 authority 下的 78 条 proposal population 进入 train-only，
不再要求逐条人工审核。

## 产量

- 新授权 proposal：78
- 新语义训练行：78
- 新 V4-100 行：78
- 新 duplicate / length defer：0 / 0
- 合并既有语义行：125
- 合并 V4-100 行：124
- 合并 length sidecar：1（既有 155 步长链）

所有行保持 validation/test=false、production merge=not granted。本阶段只构造训练数据并运行
smoke，没有开始模型训练。

## 验证

- 批次 authority 同时绑定 proposal、原始审核、审核结果、source manifest、既有 reviewed packet、
  expansion ledger、evaluation profile、既有语义训练行和 stable-94 mapping。
- 服务器 `_a`、`_b` 两次导出逐字节一致。
- 41 个聚焦回归通过。
- 真实 loader/loss/backward 覆盖 124/124 行，batch shape=`[124, 100]`，loss 与 gradient
  有限，max token=92，最大模型序列长度=92，checkpoint_written=false。

## 权威产物

- 服务器主包：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch_v1_20260731_a`
- 可复现双跑：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch_v1_20260731_b`
- smoke：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch_v1_20260731_smoke_a`
- 本机同步：`docs/reports/gee_expansion_training_batch_v1/`

## 下一阶段

冻结当前规则，不继续审核剩余 proposal。下一批从母池选择新的 source-disjoint authority，目标使
累计 V4-100 训练行达到 200-300；只抽 30-50 条做分层审核。只有抽样发现系统性错误时才修一次
通用规则并全批重放，禁止恢复逐条人工审核。
