# Planner-v2-fmt P0-A 解析失败诊断（2026-10-09）

## 结论

P0 dev 1,852 条 predictions 中：

- **可解析 JSON**：1,560 / 1,852 = **84.23%**
- **不可解析**：292 / 1,852 = **15.77%**
- 292 条失败**全部归为 `truncated_or_unclosed`**：输出以 JSON 开头，但没有闭合 `}`；没有发现空输出、非 JSON 前缀、Markdown fence、缺 `stages` 或字段语法错误等类别。

## 证据

P0 生成脚本 `regen_v2_dev_preds_v1.py` 的固定配置为：

```text
max_new_tokens=384
 do_sample=False
 eos_token_id=[eos, pad]
```

292 条失败预测的输出字符长度：

```text
min=1098, p50=1221, p90=1267, max=1339
```

尾部样本均在 JSON 中途截断，例如：

```text
... {"seq":24
... {"seq":24,"family":"B
... {"seq":28,"family":"
```

因此 P0-A 的首要结论是：**失败不是 schema 设计错误或模型输出非 JSON，而是生成预算触顶导致的未闭合 JSON。**

## 当前解释边界

这能解释 P0 的 parse rate 短板，但不能自动证明增加 `max_new_tokens` 后端到端指标必然提升：较长序列还存在 under-emission（P0 under-emission 6.6462）问题，需要 P0-B 解码对照验证。

## 下一步 P0-B（不改权重）

从同一 P0 adapter、同一 1,852 dev、同一 prompt、同一 greedy 配置派生独立输出目录，唯一变量：

1. `max_new_tokens=768`（先测，覆盖当前最长失败输出的 2 倍）
2. 若仍有截断，再测 `max_new_tokens=1024`
3. 记录 parse rate、parse-inclusive/exclusive bag-F1、ordered LCS-F1、family precision、over/under emission、generation length

不使用 JSON 约束解码、不修改 checkpoint、不触碰 locked test。P0-B 结果再决定是否需要 P1 格式专项 SFT。
