# GEE 完整工作流第四批扩展与 800 行门禁

日期：2026-08-03

## 结论

第四个 source-disjoint 批次已完成确定性规则修复、整批重放、30-source 分层审核、train-only
准入和真实 loader/loss/backward 验证。正式交付为：

| 产物 | 行数 |
| --- | ---: |
| 完整语义训练行 | 842 |
| 当前 V4-100 可加载行 | 841 |
| 155 步 length sidecar | 1 |
| 本批新增语义/V4-100 行 | 275 / 275 |
| 本批 duplicate / length defer | 0 / 0 |

累计 800 行门禁已经完成。validation/test、production merge 和正式模型训练仍未开放。

## 规则修复与审核

30-source 审核发现三类可推广缺陷：对象字面量 backward slice 错误保留未使用属性的调用；
`ee.imagecollection.sort` 被旧 skip authority 错误移除；`ee.Date(Date.now())` 未明确表达为运行时
当前日期。修复后的规则分别只跟踪可静态证明的被引用键、恢复 output-relevant `sort`，并增加
`runtime_current_date` 动态参数类型。动态键和不可证明参数继续 fail-closed。

修复后审核结果为：

- 30/30 pass；
- point precision = 1.0；
- Wilson 95% lower = 0.8864866068260312；
- critical failure = 0；
- decision = `passed_for_larger_source_disjoint_replay`。

该结果授权同一冻结 v6 规则下全部 275 条 proposal，不要求逐条生产审核。

## 产物与可复现性

训练包 A/B 的 10 个文件逐字节一致。关键 SHA256：

- proposal：`e0a9c5262060d108e81b472a95976db90abca3eb374316288bda1cc6bc6512cd`
- reviewed audit：`640c01b5c81d5a8d022883cceb1899bb5db832fc407487bc448d4c42d6633b8b`
- combined semantic：`1d58d0f9a07e6c102bd31e4c626dc633f09dbb50420243216091574789cc3c47`
- combined V4-100：`fde1964dd7305ecc0f23779b440cd79cbbe02a9b5ac6a15ad32bb187f8516fad`
- stable-94 mapping：`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`

服务器产物：

- 规则与重放 authority：
  `/home/qy/system_redesign/diagnostics/gee_batch4_rulefix_v6_20260802`
- 训练包：
  `/home/qy/system_redesign/diagnostics/gee_batch4_rulefix_v6_training_a` 与 `_b`
- smoke：
  `/home/qy/system_redesign/diagnostics/gee_batch4_rulefix_v6_smoke_a` 与 `_b`

## 训练路径验证

服务器 `transformer` 环境中的真实 `TaskConditionedL3DatasetV4 +
weighted_sequence_cross_entropy + backward` 在两个包上均覆盖 841/841 行，batch 为
`[512,100]` 与 `[329,100]`。loss 和 gradient 有限，max token=92，最大模型序列长度=92，
`checkpoint_written=false`，`training_run=false`。smoke A/B JSON 逐字节一致，SHA256 为
`7ef36ae8ed5073c960ac6a4008b1cb33a711be47a0b5f1158754130933422592`。

## 下一门禁

冻结修复后的 v6 转换器，选择新的 source-disjoint 批次，把累计 V4-100 扩到 1,000 条以上。
完整 population 继续走确定性门禁，只审核 30-50 个分层源码代表；只有系统性抽样失败才修一条
通用规则并整批重放，不恢复逐条生产审核。
