# GEE 完整工作流第三批扩展与 500 行门禁

日期：2026-08-02

## 结论

新的 1,000-source source-disjoint 批次已完成确定性全批转换、分层源码抽检、train-only
准入和真实 loader/loss/backward 验证。与既有 279 条合并后的正式交付为：

| 产物 | 行数 |
| --- | ---: |
| 完整语义训练行 | 567 |
| 当前 V4-100 可加载行 | 566 |
| 155 步 length sidecar | 1 |
| 本批新增语义/V4-100 行 | 288 / 288 |
| 本批 duplicate | 0 |

因此累计 500-1000 行阶段的下限门禁已经完成。validation/test、production merge 和模型训练
仍未开放。

## 审核反馈与规则修复

初始 30-source 审核得到 29 pass / 1 critical fail。失败源码使用
`LANDSAT/LO08/C01/T1_RT`，其中 `LO08` 不是合法 Landsat 平台 token，并混用了 Sentinel-2
属性 `CLOUDY_PIXEL_PERCENTAGE`。旧 facts 层会把任何静态字符串数据源直接标为 allowed。

按 TDD 新增了保守的公共 Landsat 平台 token 门禁：仅当 `LANDSAT/` 的第二段匹配
`L[A-Z][0-9]{2}` 时检查冻结平台集合；`LO08` fail-closed，而历史
`LANDSAT/LC08/C01/T1_RT` 和 `LANDSAT/LC8_L1T_TOA` 保持接受。该规则不声称替代完整 GEE
catalog 校验。

修复后 facts A/B 双跑逐文件一致：

- mapping-complete input：368；
- fact bundle：354；
- fact fail-closed：14，其中新增 1 条正是 `LO08`；
- canonical task text：296；
- duplicate：58；
- unique candidate source：188。

## Expansion 与抽样门禁

v5 expansion A/B 双跑逐文件一致，得到 288 条 proposal、180 个 eligible source、6 条既有或
批内重复，以及 2 条未准入的超长候选。配额因移除一个 `multi_dataset_private` source 重新按
largest-remainder 冻结为 `7/9/8/3/1/2`。

新审核样本与旧样本重叠 28 条，只新增复核两条完整源码：一条 35 步 ASTER 多指数逻辑链，
一条 JRC wet/dry sibling-export 工作流。最终结果为：

- 30/30 pass；
- point precision = 1.0；
- Wilson 95% lower = 0.8864866068260312；
- critical failure = 0；
- decision = `passed_for_larger_source_disjoint_replay`。

该门禁授权同一 v5 规则 population 的全部 288 条 proposal，不进行逐行生产审核。

## 可复现性与训练路径验证

- facts SHA256：`1723391bd2057ce8268f60aaffe9a08232783d09c07357c1c4ac27bb4d5f2064`
- task-text SHA256：`0594d6be70f0717f7faef5be9bb7c0e0e021925838e25c2520c5f70d58532748`
- proposal SHA256：`efea1ec4304b282a775e0e6a2f3adc89656cc2cbf5a011c77f76e1e500c2f670`
- combined semantic SHA256：`7f241b33eb0c76c3d4f9f5ed5a1709d04de931b38152a77993f6c6339b55641f`
- combined V4-100 SHA256：`fbd3f8b8614843b9bdff6e0442363e05261221f229e64ae7344581a9bc43c749`
- stable-94 mapping SHA256：`005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558`

训练包 A/B 逐文件一致。服务器 `transformer` 环境中的真实
`TaskConditionedL3DatasetV4 + weighted_sequence_cross_entropy + backward` smoke 在两个包上均
覆盖 566/566 行，batch 为 `[512,100]` 和 `[54,100]`；loss/gradient finite，max token=92，
最大模型序列长度=92，未写 checkpoint、未运行训练。

## 权威产物

- 服务器 authority：
  `/home/qy/system_redesign/diagnostics/gee_batch3_1000_authorities_20260802/`
- 服务器训练包 A/B：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch3_rulefix_v5_20260802_a`
  与 `_b`
- 服务器 smoke A/B：
  `/home/qy/system_redesign/diagnostics/gee_expansion_training_batch3_rulefix_v5_smoke_20260802_a`
  与 `_b`
- 本机训练包：`docs/reports/gee_expansion_training_batch3_rulefix_v5/`
- 本机审核 authority：`docs/reports/gee_batch3_1000_rulefix_v5_audit/`

## 下一门禁

下一批继续使用新的 source-disjoint selection，将累计 V4-100 扩到 800-1000。当前 token gate
只能发现一类确定性畸形 ID；完整数据集权威应单独冻结官方 GEE STAC snapshot，并把 57 个旧
catalog 未覆盖的唯一 ID 按 `active/deprecated_historical/invalid/private_external` 建立规则级
manifest。该工作不能阻塞已闭合的 566 行训练包，也不得使用模糊匹配自动改写数据集 ID。
