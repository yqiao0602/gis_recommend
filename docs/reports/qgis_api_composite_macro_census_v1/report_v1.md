# QGIS API 复合宏聚类 census v1（2026-08-10）

## 背景

census_v2 的 semantic_priority 层（7 个语义 family）已全部开采完毕（+6 条 train-only，unary_union 0 产出）。
按用户决策（选 A）对 discovery 层（terminal_macro_units 5,580 行）重新聚类，寻找 priority 层之外的 family。

## 方法（v3 与 v2 的三个差异）

1. **多 producer 不再丢弃**：v2 的 `build_semantic_rollup_census` 用 `len(rollups) != 1 → continue` 丢弃所有复合宏 units（1,286/5,580）；
2. **链式调用拆解**：`qgsgeometry.frompointxy.buffer(...)` 拆为 head producer + chain-tail；只读访问器尾（aspoint/wkbtype/length）丢弃、mutation 尾归入 mutation 集；
3. **mutation-only 窗口纳入**：v2 的 `build_terminal_units` 用 `if not producers or not mutations: continue` 丢弃无 producer 窗口（3,718 个 sink 窗口 / 2,232 unique source）——本次以宽松 units（producer 与 mutation 至少其一）重建，共 10,800 units。

分组键 = (语义 producer 集合 × mutation 集合 × sink)。排除已开采语义（7 个构造/变换/union family + COMPLETED_SEMANTICS）+ 已训练 source（492/508/isolated + add_field 15/24）。

## 结果

- 复合 family 总数：1,023（defer_completed_semantic_overlap 820、below-threshold 189）
- **新 priority family：14 个，2,773 units —— 全部为 mutation-only 属性编辑宏（producers=[]）**

| source | units | mutations | sink |
|---|---|---|---|
| 575 | 883 | setattributes | addfeature |
| 252 | 355 | addattributes, updatefields | addfeatures |
| 216 | 279 | addattributes, setattributes, updatefields | addfeatures |
| 182 | 293 | setattribute | addfeature |
| 157 | 203 | setattributes | addfeatures |
| 117 | 147 | addattributes, setattributes, updatefields | addfeature |
| 114 | 186 | setattribute | addfeatures |
| 63 | 68 | addattributes, setattribute, updatefields | addfeatures |
| 63 | 97 | addattributes, updatefields | addfeature |
| 53 | 78 | addattributes, updatefields | writeasvectorformat |
| 45 | 62 | addattributes, setattribute, updatefields | addfeature |
| 40 | 45 | addattribute | addfeature |
| 33 | 38 | addattributes | addfeatures |
| 32 | 39 | addattributes, setattributes | addfeatures |

## 与既有机制的关系

- add_field_existing_layer（24 行）/ add_calculate_field（15 行）扫过的是 **addAttribute(QgsField)/setAttribute(字段名, 表达式)** 形态；
- mutation-only 池（setattributes 列表赋值 → addFeature）与其重叠仅 40/2,232——**此前未被扫描**；
- L3 承接：L3_01_02_01 Add Field（token 1）/ L3_01_02_06 Calculate Field（token 4）已在词汇表 130，无需扩展词汇表。

## 风险提示（polygon/unary_union 教训）

签名 support ≠ 可证明 support。抽样窗口显示形态多样：feature 来源（源图层遍历复制 / QgsFeature 新构造 / 插件 self 参数）、setattributes 参数（字面量列表 / 动态别名）、接收器（writer/provider/图层变量）。需服务器 calibration 200 实测可证明率后决定是否值得全池开采。

## 产物

- `discovery_units_v1.jsonl`（10,800 units，宽松口径）
- `composite_family_census_v1.jsonl`（1,023 family）
- `priority_units_v1.jsonl`（2,773 priority units，带 family_id）
- `summary_v1.json` / `hash_ledger_v1.json`

## 下一步建议

选最大 family（setattributes → addfeature，575 src / 883 units）做服务器 calibration 200：
按 source-authority 分权 100/100，实测可证明率；若 complete ≥ ~10%（对照 polygon 13.5%）则全池 replay → L3 → 四层去重 → 导出。
