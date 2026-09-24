# ⑥-3 Plan Quality Tiering 完成报告 v1（2026-09-24，owner 批准冻结 c7b568d）

## 总裁定

**Tiering v2 冻结。** v1 FAIL（prov_run ≥ 3 过度拒绝，strict agreement
0.404）→ v2 以 unconsumed-dominant F-STRUCT 测试替换，三道验收门全过：

| 门 | 判据 | v1 | v2 | 结果 |
|---|---|---|---|---|
| 1 F-STRUCT 隔离 | 硬门槛 | 2/2 | **2/2** | PASS |
| 2 agreement 改善 | vs v1 | — | strict .404→**.447**；lenient .553→**.617** | PASS |
| 3 false rejection | 保真→REJECT | 5 | **1**（−80%） | PASS |

## 最终分布（冻结）

```
Tier A  28,575   直接监督
Tier B  17,690   可用（已登记轻微偏差）
Tier C  12,457   诊断专用
REJECT   1,113   隔离（prov-run/类型流 reason 落盘）
主训练池 A+B = 46,265
```

## 措辞冻结（owner 要求）

> **46,265 是"通过 ⑥-3 自动质量分层的候选监督池"，不是宣称其中每一条
> 都经过人工确认。** 48 条人工审计只是抽样审计；agreement 不外推为
> 全量人工准确率。

## v1 失败的机制结论（保留入档）

v1 的 `prov_run ≥ 3` 是**过强的结构风险代理变量**——把"结构风险特征"
错当"失败判据"。v2 将 provision run 三分类：

```
consumed          → B / 可用
utility-heavy     → C / 诊断
unconsumed+主导    → REJECT / F-STRUCT-01
```

Tier A 完全未动（28,575）；+3,609 全部进入 B——修正回收的是 v1 的
过度拒绝，不是重排高质量核心池。

## 冻结纪律（即日生效）

- ❌ 不再调整 v2 tiering 阈值
- ❌ 不再为扩大 46,265 修改 converter
- ❌ 不根据后续 Stage-1 训练结果反向修改 ⑥-3
- ✅ REJECT 1,113 保留 reason（审计/诊断资产）
- ✅ Tier C 12,457 保留为诊断资产
- ✅ **46,265 固化为 Stage-1 Plan 监督候选池**

## 下一步：⑥-4 Open-set Grounding Sufficiency

回答：**Plan 在面对训练中未见的 QGIS 实现/候选空间时，信息是否仍足以
支撑 Stage-2 grounding？** 通过后 ⑥-5 B2 数据准备才有意义。
