# 风险旗标定义规范 V1（P0 校准，2026-10-18）

- **状态**：`frozen_for_auxiliary_audit`；owner 已批准先校准旗标（P0）。
- **定位**：旗标是**审计分层与复核提示**，不是准入或排除依据。任何组件是否合格仍由
  语义判读 + 六桶准入决定。
- **适用范围**：GEE 脚本级静态分析（`script_*.txt`），不执行脚本、不推断运行时值。
- **实现**：`scripts/b_track_risk_flags_v1.py`（`RULES_VERSION = V1_calibrated_20261018`）。
- **旧版结果保留**：`B_TRACK_S1_SAMPLING_LIST_V1.json` 中的 `ui_scaffold /
  duplicate_lines / indirect_asset` 不覆盖、不重算；校准版本另存
  `B_TRACK_RISK_FLAG_RATES_V1.json` 与 `B_TRACK_RISK_FLAG_CALIBRATION_V1.json`。

## 1. 冻结定义

### 1.1 实质性行（substantive line）

一行同时满足：

1. 去掉 `//` 之后的内容（**已知限制**：字符串内的 `//` 也会被去掉）；
2. 去掉全部空白；
3. 去掉行尾 `;`；
4. 归一化后长度 ≥ **15** 字符；
5. 不是纯括号/标点（`});`、`}));`、`);` 等一律不算）。

### 1.2 UI 类

| 旗标 | 定义 | 风险含义 |
| --- | --- | --- |
| `ui_interactive` | `ui.Button / Select / Slider / Checkbox / Textbox / Panel / Map / SplitPanel` 或 `Map.onClick` | 交互控件代码；脚本不是纯分析工作流 |
| `ui_chart` | `ui.Chart.*` | 图表输出代码；多为结果展示，单独分类 |
| `ui_display` | `ui.Label / ui.Thumbnail` | 纯展示控件 |
| `map_display` | `Map.addLayer / setCenter / centerObject / setOptions / add / layers` | **描述性属性，不是风险旗标**（全库 85.9% 命中，无区分度） |

### 1.3 重复结构

| 旗标 | 定义 |
| --- | --- |
| `duplicate_block` | 任意**连续 3 条实质性行**组成的块出现 ≥ **2** 次 |
| `duplicate_line` | 任意单条实质性行出现 ≥ **3** 次 |
| `dup_severity` | `none / low(3–4) / medium(5–9) / high(≥10)`，取行重复与块重复的较大者 |

边界（明确不触发）：连续 **2** 行重复块不触发 `duplicate_block`（记录为已知漏报）；
短于 15 字符的行、纯标点行、被注释掉的行不参与统计。

### 1.4 资产参数

| 旗标 | 定义 |
| --- | --- |
| `literal_asset` | `ee.ImageCollection / ee.Image / ee.FeatureCollection` 首参为字符串字面量（或拼接中的字面量片段） |
| `nonliteral_asset_arg` | 首参为**裸标识符**（`ee.ImageCollection(src)`）或**字符串拼接**（`ee.Image('S2/' + id)`） |
| `nonliteral_severity` | 按非字面参数个数：`low(1) / medium(2–4) / high(≥5)` |

**语义限定**：`nonliteral_asset_arg` 表示"调用点看不到资产来源"，**不等于**间接资产。
裸标识符可能是计算得到的 `ee.Image` 对象（如 `ee.Image(image)`），并非资产 ID。

明确不触发：数字常量（`ee.Image(0.0001)`）、数组（`ee.ImageCollection([a,b])`）、
其他表达式（`ee.Image(image.select('B4'))`）。

### 1.5 其他（沿用）

`empty_rle`（空/退化语义链）、`known_Q1`、`known_Q2` 沿用 Q2 准入台账，定义不变。

## 2. 回归集

- 夹具：`risk_flag_regression_v1.json`，**20 例**（正例 10、负例 4、边界 6）。
- 结果：**20/20 通过**（精确集合相等）。
- 命令：`python -I scripts/b_track_risk_flags_v1.py --json <fixture>`。
- 覆盖：交互控件、图表、标签、展示调用、onClick、重复块、重复行、裸标识符、
  字符串拼接、纯标点重复、数字/数组/表达式参数、2 行重复块、重复注释、嵌套数字。

## 3. 12 个校准组件：预期 vs 实际

每个组件的"预期"来自逐脚本人工核对（计数命中行、重复行、参数字面量），
"实际"为校准实现输出；**12/12 完全一致**。明细见
`B_TRACK_RISK_FLAG_CALIBRATION_V1.json`。

| 组件 | 脚本 | 预期 = 实际旗标 |
| --- | --- | --- |
| 45165 | script_278452 | `nonliteral_asset_arg` |
| 48878 | script_79821 | `map_display, duplicate_block, duplicate_line, nonliteral_asset_arg, literal_asset` |
| 103943 | script_56389 | `ui_interactive, ui_chart, ui_display, map_display, duplicate_block, duplicate_line, nonliteral_asset_arg, literal_asset` |
| 51891 | script_69165 | `map_display, duplicate_block, nonliteral_asset_arg, literal_asset` |
| 50842 | script_184064 | `map_display, duplicate_block, duplicate_line, nonliteral_asset_arg, literal_asset` |
| 42446 | script_121276 | `map_display, duplicate_block, duplicate_line, literal_asset` |
| 58126 | script_176447 | `ui_interactive, ui_chart, map_display, duplicate_block, duplicate_line, nonliteral_asset_arg, literal_asset` |
| 74228 | script_184015 | 同 50842 |
| 17106 | script_81346 | `ui_interactive, ui_chart, ui_display, map_display, duplicate_block, duplicate_line, nonliteral_asset_arg, literal_asset` |
| 48801 | script_183961 | 同 50842 |
| 35770 | script_6756 | `map_display, duplicate_block, duplicate_line, nonliteral_asset_arg` |
| 45703 | script_131792 | `map_display, literal_asset` |

## 4. 全抽样清单旗标率（7,562 组件，7,538 可评分）

| 旧定义 | 命中率 | 新定义 | 命中率 |
| --- | --- | --- | --- |
| `ui_scaffold` | 90.86% | `ui_interactive` | **16.00%** |
| — | — | `ui_chart` | 28.28% |
| — | — | `ui_display` | 14.99% |
| — | — | `map_display`（描述性） | 85.92% |
| — | — | `literal_asset`（描述性） | 88.50% |
| `duplicate_lines` | 71.77% | `duplicate_block` | **34.28%** |
| — | — | `duplicate_line` | 41.09% |
| `indirect_asset` | 55.31% | `nonliteral_asset_arg` | **37.76%** |

- 分 split 命中率接近（train/val/test 差异 < 5 个百分点），说明旗标不是 split 伪影。
- **24 / 7,562** 组件的代表脚本在本地源码树中缺失，标为 `unscored`，不得默认为"无风险"。

## 5. 误报 / 漏报 / 不可判

### 5.1 误报（旗标触发但非治理缺陷）

| 案例 | 说明 | 处置 |
| --- | --- | --- |
| script_79821 ×5、油膜三脚本 ×27 的 `Export.image/table.toDrive({` 重复 | 多次导出的合法样板 | `dup_severity` 记录；仅提示复核，不排除 |
| script_121276 / script_69165 的年度/传感器重复 filter 链 | 合法循环式重复 | 同上 |
| `ui_chart` 28.28% | 图表是输出，不是交互 | 与 `ui_interactive` 分开 |
| `map_display` 85.92% | 展示调用几乎普遍存在 | 降级为描述性属性 |

### 5.2 漏报（已知且接受）

- 连续 **2** 行重复块不触发（script_278452 的 2 次导出块即属此类）；
- `ee.Image(image.select('B4'))` 等计算表达式不标记；
- 注释剥离会误伤字符串内的 `//`；
- 24 个缺脚本组件无法评分。

### 5.3 不可判

- 裸标识符参数可能是计算对象而非资产 ID → 需要看赋值来源才可判；
- 拼接参数的完整资产路径无法静态确定。

## 6. 治理约束

1. 旗标**不得**直接决定样本准入、排除或 split 归属；
2. 校准版本只用于抽样分层、复核排序和风险报告；
3. 若后续修改任一阈值，必须升版（V2）并重跑 20 例回归 + 12 组件校准；
4. 旧版旗标结果永久保留，报告 V1→校准版的变化，不覆盖。

## 7. 复现

```bash
python -I scripts/b_track_risk_flags_v1.py --json docs/.../risk_flag_regression_v1.json
python -I scripts/b_track_risk_flag_calibration_v1.py   # 12 组件
python -I scripts/b_track_risk_flag_rates_v1.py         # 7,562 组件旗标率
```

## 8. 溯源哈希（SHA-256）

| 文件 | SHA-256 |
| --- | --- |
| `scripts/b_track_risk_flags_v1.py` | `5e2bd667fc46f7b763b36fe5965e6ca4b823a38c2251f320c61949666add9f61` |
| `scripts/b_track_risk_flag_calibration_v1.py` | `09e826c442c6a055ce033a884c4882a7fcc83a38abec24365c6f87c1655a3a46` |
| `scripts/b_track_risk_flag_rates_v1.py` | `51d403f3ddb52aff50404d8c19d3b936c3b21214fed8c5d3e8936f583cd0e4db` |
| `risk_flag_regression_v1.json` | `ebd54073c9430f6168b54fca277521b2c063568dd79abd017c7361dde2cb5420` |
| `B_TRACK_RISK_FLAG_CALIBRATION_V1.json` | `b6de5da23eb20634f4b7bec5289641c78ce02217c274ee2367c15b1dd031cefb` |
| `B_TRACK_RISK_FLAG_RATES_V1.json` | `f9f5290c54ba5fd18b612e8dfe730388f599c5fccd2d7be98084067359df0a7b` |
