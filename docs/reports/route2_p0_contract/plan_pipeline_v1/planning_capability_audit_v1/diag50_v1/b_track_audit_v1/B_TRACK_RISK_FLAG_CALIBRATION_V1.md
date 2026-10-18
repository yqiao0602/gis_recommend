# 风险旗标校准报告 V1（P0，2026-10-18）

- **范围**：12 个校准波组件（逐脚本人工核对）+ 7,562 抽样组件的旗标率复算。
- **规则**：`B_TRACK_RISK_FLAG_SPEC_V1.md`（V1_calibrated_20261018）。
- **机器产物**：
  - `B_TRACK_RISK_FLAG_CALIBRATION_V1.json`（逐组件旧/新/预期/匹配）
  - `B_TRACK_RISK_FLAG_RATES_V1.json`（7,562 组件旗标率与分 split 统计）
  - `risk_flag_regression_v1.json`（20 例回归夹具）
- **结论**：回归 20/20 通过；12 组件**预期=实际 12/12**；旧定义的三类旗标
  命中率过高，校准版显著收窄，且保留可追溯的旧结果。

## 1. 12 组件逐项结果

| 组件 | 脚本 | 旧旗标 | 校准旗标 | 人工预期 | 一致 |
| --- | --- | --- | --- | --- | --- |
| 45165 | script_278452 | duplicate_lines, indirect_asset | nonliteral_asset_arg | 同左 | ✓ |
| 48878 | script_79821 | ui, duplicate, indirect | map_display, duplicate_block, duplicate_line, nonliteral, literal | 同左 | ✓ |
| 103943 | script_56389 | ui, duplicate, indirect | ui_interactive, ui_chart, ui_display, map_display, duplicate_block, duplicate_line, nonliteral, literal | 同左 | ✓ |
| 51891 | script_69165 | ui, duplicate, indirect | map_display, duplicate_block, nonliteral, literal | 同左 | ✓ |
| 50842 | script_184064 | ui, duplicate, indirect | map_display, duplicate_block, duplicate_line, nonliteral, literal | 同左 | ✓ |
| 42446 | script_121276 | ui, duplicate, indirect | map_display, duplicate_block, duplicate_line, literal | 同左 | ✓ |
| 58126 | script_176447 | ui, duplicate, indirect | ui_interactive, ui_chart, map_display, duplicate_block, duplicate_line, nonliteral, literal | 同左 | ✓ |
| 74228 | script_184015 | ui, duplicate, indirect | 同 50842 | 同左 | ✓ |
| 17106 | script_81346 | ui, duplicate, indirect | ui_interactive, ui_chart, ui_display, map_display, duplicate_block, duplicate_line, nonliteral, literal | 同左 | ✓ |
| 48801 | script_183961 | ui, duplicate, indirect | 同 50842 | 同左 | ✓ |
| 35770 | script_6756 | ui, duplicate, indirect | map_display, duplicate_block, duplicate_line, nonliteral | 同左 | ✓ |
| 45703 | script_131792 | ui, indirect | map_display, literal | 同左 | ✓ |

人工核对依据（逐脚本）：
- `script_278452`：无 UI/Map 调用；2 次导出块（未达 3 行块阈值）；3 个裸标识符构造参数。
- `script_79821`：4 次 `Map.addLayer/centerObject`；5 次重复 `Export.image.toDrive({` 样板；
  3 个裸参数；2 个字面资产。
- `script_56389`：13 个交互控件 + `Map.onClick`；3 个 `ui.Chart`；8 个 Label/Thumbnail；
  17 次 Map 展示；8× `.filterBounds(region)`；4 个裸参数；4 个 Landsat 字面资产。
- `script_69165`：2 次 Map 展示；2 次重复 filter 三元组；3 个裸参数；3 个字面资产。
- `script_184064/184015/183961`（油膜三脚本）：5 次 Map；27 次重复导出表样板；
  1 个裸参数 + 1 个拼接；9 个相同字面资产。
- `script_121276`：3 次 Map；3 次重复年度 filter；0 个裸参数；3 个 Landsat 字面资产。
- `script_176447`：`Map.onClick` + 1 个 Chart；9 次 Map；9 次重复 `system:time_start`；
  2 个裸参数；3 个字面资产。
- `script_81346`：12 个交互控件 + onClick；5 个 Chart；7 个 Label；6 次 Map；27 次重复
  filter；2 个裸参数；5 个字面资产。
- `script_6756`：1 次 Map；124 次重复 4 行块；3 个裸参数；无字面资产。
- `script_131792`：4 次 Map；无重复；0 个裸参数；3 个 MODIS/USDOS 字面资产。

## 2. 全抽样清单旗标率

| 旧定义 | 命中 | 旧率 | 新定义 | 命中 | 新率 |
| --- | --- | --- | --- | --- | --- |
| ui_scaffold | 6,849 | 90.86% | ui_interactive | 1,206 | 16.00% |
| — | — | — | ui_chart | 2,132 | 28.28% |
| — | — | — | map_display（描述性） | 6,477 | 85.92% |
| duplicate_lines | 5,410 | 71.77% | duplicate_block | 2,584 | 34.28% |
| — | — | — | duplicate_line | 3,097 | 41.09% |
| indirect_asset | 4,169 | 55.31% | nonliteral_asset_arg | 2,846 | 37.76% |

- 分母 7,538（24 个组件缺代表脚本，标 `unscored`）。
- 分 split 差异 < 5pp（train/val/test 分别为 ui 16.01/15.63/16.34%；
  dup_block 33.96/36.42/34.78%；nonliteral 37.82/35.63/39.58%）。

## 3. 错误分析

### 3.1 误报（触发但不是缺陷）

- 重复导出样板：`script_79821` ×5、油膜三脚本 ×27（合法多次导出）。
- 年度/传感器重复 filter 链：`script_121276` ×3、`script_69165` ×2 triad。
- `map_display` 85.9%：展示调用几乎普遍，**不作为风险旗标**。
- `ui_chart` 28.3%：图表是输出，不是交互，已与 `ui_interactive` 分离。

处置：`dup_severity` 分层（low/medium/high）；旗标只影响复核排序，不影响准入。

### 3.2 漏报（已知且接受）

- 连续 **2** 行重复块不触发（`script_278452` 的 2 次导出块）。
- `ee.Image(image.select('B4'))` 等计算表达式不标记。
- 注释剥离会误伤字符串内 `//`。
- 24 个缺脚本组件无法评分。

### 3.3 不可判

- 裸标识符可能是计算对象而非资产 ID（`ee.Image(image)`），旗标只表示
  "调用点看不到来源"。
- 拼接参数只记录字面前缀，完整资产路径静态不可判。

## 4. 治理结论

1. 校准旗标通过：定义可复现、边界有回归、错误案例可追溯。
2. **不得**用旗标替代语义准入或直接排除样本。
3. 旧版旗标结果（抽样清单 V1）保留；新版另存，不覆盖。
4. 后续抽样清单 V2 如需风险分层，使用 `ui_interactive / duplicate_block(severity) /
   nonliteral_asset_arg`，并把 `map_display` 作为描述性属性单列。
