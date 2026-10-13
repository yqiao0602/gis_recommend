# A2 源码审计包（45 项 needs_source_audit）

每项列出：定义位置 + 全部标识符出现位置（含行文本）。判定规则：
定义表达式内部引用不计后继；赋值左侧不计（已由采集器排除）；
同一调用表达式接收对象不重复计数；return 计一次使用。

## script_100110:A2:landsatTOAcloudmask

自动化: analysis_chain/1 ｜ 人工: unconsumed/1 ｜ 出现位置数: 1
裁定依据: 静态引用 1（别名未续用）；须先厘清 unconsumed 判定口径：无后继引用 vs 未进入最终结果，不得混用

定义: [{'line': 95, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 119 | VariableDeclarator | `landsatTOAcloudmask` |

## script_100110:A2:xValLabels

自动化: analysis_chain/2 ｜ 人工: presentation_only/1 ｜ 出现位置数: 2
裁定依据: 暂定展示（横轴标签）；计数待核绑定与作用域

定义: [{'line': 245, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 289 | MemberExpression | `{v: xValLabels[i]},  // the X axis category` |
| 421 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100110:A2:maxValue

自动化: analysis_chain/4 ｜ 人工: analysis_chain/2 ｜ 出现位置数: 4
裁定依据: 暂保留；需核对更新最大值的读取次数及是否仅用于轴范围

定义: [{'line': 257, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 279 | BinaryExpression | `maxValue = (stats.p100 > maxValue) ? stats.p100 : maxValue;` |
| 279 | ConditionalExpression | `maxValue = (stats.p100 > maxValue) ? stats.p100 : maxValue;` |
| 351 | BinaryExpression | `max: ((maxMedian * 1.5) > maxValue) ? maxValue : (maxMedian * 1.5),` |
| 351 | ConditionalExpression | `max: ((maxMedian * 1.5) > maxValue) ? maxValue : (maxMedian * 1.5),` |

## script_100110:A2:maxMedian

自动化: analysis_chain/4 ｜ 人工: analysis_chain/2 ｜ 出现位置数: 4
裁定依据: 暂保留；需核对实际引用位置后定状态与计数

定义: [{'line': 259, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 281 | BinaryExpression | `maxMedian = (stats.p75 > maxMedian) ? stats.p75 : maxMedian;` |
| 281 | ConditionalExpression | `maxMedian = (stats.p75 > maxMedian) ? stats.p75 : maxMedian;` |
| 351 | BinaryExpression | `max: ((maxMedian * 1.5) > maxValue) ? maxValue : (maxMedian * 1.5),` |
| 351 | BinaryExpression | `max: ((maxMedian * 1.5) > maxValue) ? maxValue : (maxMedian * 1.5),` |

## script_100110:A2:myRows

自动化: analysis_chain/1 ｜ 人工: presentation_only/1 ｜ 出现位置数: 1
裁定依据: 暂保留；需确认行数据是纯呈现还是承担后续分析构造

定义: [{'line': 265, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 329 | Property | `rows: myRows` |

## script_100110:A2:stats

自动化: analysis_chain/18 ｜ 人工: analysis_chain/9 ｜ 出现位置数: 18
裁定依据: 暂保留；引用数 18 vs 9 差异必须逐处核对

定义: [{'line': 267, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 279 | MemberExpression | `maxValue = (stats.p100 > maxValue) ? stats.p100 : maxValue;` |
| 279 | MemberExpression | `maxValue = (stats.p100 > maxValue) ? stats.p100 : maxValue;` |
| 281 | MemberExpression | `maxMedian = (stats.p75 > maxMedian) ? stats.p75 : maxMedian;` |
| 281 | MemberExpression | `maxMedian = (stats.p75 > maxMedian) ? stats.p75 : maxMedian;` |
| 283 | MemberExpression | `minValue = (stats.p0 > minValue) ? stats.p0 : minValue;` |
| 283 | MemberExpression | `minValue = (stats.p0 > minValue) ? stats.p0 : minValue;` |
| 285 | MemberExpression | `minMedian = (stats.p25 > minMedian) ? stats.p25 : minMedian;` |
| 285 | MemberExpression | `minMedian = (stats.p25 > minMedian) ? stats.p25 : minMedian;` |
| 293 | MemberExpression | `{v: stats.p0},  // min` |
| 295 | MemberExpression | `{v: stats.p25},  // q1` |
| 297 | MemberExpression | `{v: stats.p50},  // median` |
| 299 | MemberExpression | `{v: stats.p75},  // q3` |
| 301 | MemberExpression | `{v: stats.p100},  // max` |
| 303 | MemberExpression | `{v: '{max: ' + stats.p100 + '\n q3: ' + stats.p75 + '\n median: ' + stats.p50 + '\n q1: ' + stats.p25 + '\n min: ' + stats.p0 + ' }'}` |
| 303 | MemberExpression | `{v: '{max: ' + stats.p100 + '\n q3: ' + stats.p75 + '\n median: ' + stats.p50 + '\n q1: ' + stats.p25 + '\n min: ' + stats.p0 + ' }'}` |
| 303 | MemberExpression | `{v: '{max: ' + stats.p100 + '\n q3: ' + stats.p75 + '\n median: ' + stats.p50 + '\n q1: ' + stats.p25 + '\n min: ' + stats.p0 + ' }'}` |
| 303 | MemberExpression | `{v: '{max: ' + stats.p100 + '\n q3: ' + stats.p75 + '\n median: ' + stats.p50 + '\n q1: ' + stats.p25 + '\n min: ' + stats.p0 + ' }'}` |
| 303 | MemberExpression | `{v: '{max: ' + stats.p100 + '\n q3: ' + stats.p75 + '\n median: ' + stats.p50 + '\n q1: ' + stats.p25 + '\n min: ' + stats.p0 + ' }'}` |

## script_100133:A2:data

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: 图表数据输入；状态建议待计数审计，不批量接受

定义: [{'line': 285, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 307 | MemberExpression | `var stats = data` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100133:A2:xVals

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: 图表取值输入；逐绑定核对引用

定义: [{'line': 287, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 305 | MemberExpression | `var myRows = xVals.map(function (label, i) {` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100133:A2:xValLabels

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: 暂定展示；计数待核

定义: [{'line': 289, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 325 | MemberExpression | `{v: xValLabels[i]},  // the X axis category` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100133:A2:xField

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: 字段选择用途；计数待核

定义: [{'line': 291, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 309 | CallExpression | `.filter(ee.Filter.equals(xField, label))` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100133:A2:xLabel

自动化: analysis_chain/3 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 3
裁定依据: 横轴标题；计数待核

定义: [{'line': 293, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 373 | BinaryExpression | `title: yLabel + ' by ' + xLabel,` |
| 379 | Property | `hAxis: {title: xLabel},` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100133:A2:yField

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: 统计字段选择；计数待核

定义: [{'line': 295, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 315 | ArrayExpression | `selectors: [yField]` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100133:A2:yLabel

自动化: analysis_chain/3 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 3
裁定依据: 纵轴标题；计数待核

定义: [{'line': 297, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 373 | BinaryExpression | `title: yLabel + ' by ' + xLabel,` |
| 383 | Property | `title: yLabel,` |
| 457 | CallExpression | `chartPanel.add(getTheChart(data, xVals, xValLabels, xField, xLabel, yField, yLabel));` |

## script_100145:A2:IC

自动化: analysis_chain/9 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 9
裁定依据: visfilter 形参；需逐处区分左值与有效引用

定义: [{'line': 67, 'kind': 'param'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 69 | MemberExpression | `IC = IC.select("builtup_class").reduce(ee.Reducer.firstNonNull())//.gte(0)` |
| 71 | MemberExpression | `.updateMask(IC.select("builtup").reduce(ee.Reducer.firstNonNull()).gte(1))` |
| 73 | ReturnStatement | `return IC` |
| 79 | MemberExpression | `IC = IC.filter(ee.Filter.equals('builtup_year',year))` |
| 81 | ReturnStatement | `return IC` |
| 87 | MemberExpression | `IC = IC.filter(ee.Filter.inList('City__Name',test_cities))` |
| 89 | ReturnStatement | `return IC` |
| 185 | MemberExpression | `IC = IC.filter(ee.Filter.equals('builtup_year',year))` |
| 187 | ReturnStatement | `return IC` |

## script_100145:A2:year

自动化: analysis_chain/7 ｜ 人工: analysis_chain/11 ｜ 出现位置数: 29
裁定依据: 多次重赋值；同一绑定累计有效引用，左值不计

定义: [{'line': 191, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 79 | CallExpression | `IC = IC.filter(ee.Filter.equals('builtup_year',year))` |
| 117 | CallExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 119 | BinaryExpression | `Map.addLayer(GHSLyear,{palette:'black'},"built-up GHSL "+year+" (cell gte 2% built-up)",false)` |
| 121 | CallExpression | `var GHSLbud = yearfilter(GHSL2pctBD,year)` |
| 125 | BinaryExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (2%)",false)` |
| 133 | CallExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 135 | BinaryExpression | `Map.addLayer(GHSLyear,{palette:'black'},"built-up GHSL "+year+" (cell gte 5% built-up)",false)` |
| 137 | CallExpression | `var GHSLbud = yearfilter(GHSL5pctBD,year)` |
| 141 | BinaryExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (5%)",false)` |
| 143 | CallExpression | `var GHSLueyear = yearfilter(GHSL5pctUE2015,year)` |
| 149 | CallExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 151 | BinaryExpression | `Map.addLayer(GHSLyear,{palette:'black'},"built-up GHSL "+year+" (cell gte 10% built-up)",false)` |
| 153 | CallExpression | `var GHSLbud = yearfilter(GHSL10pctBD,year)` |
| 157 | BinaryExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (10%)",false)` |
| 159 | CallExpression | `var GHSLueyear = yearfilter(GHSL10pctUE2015,year)` |
| 161 | BinaryExpression | `Map.addLayer(GHSLueyear,{color:'orange'},"Urban Extent GHSL "+year+" (10%)",true)` |
| 167 | CallExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 169 | BinaryExpression | `Map.addLayer(GHSLyear,{palette:'black'},"built-up GHSL "+year+" (cell gte 20% built-up)",false)` |
| 171 | CallExpression | `var GHSLbud = yearfilter(GHSLbuiltup_density,year)` |
| 175 | BinaryExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (20%)",false)` |
| 177 | CallExpression | `var GHSLueyear = yearfilter(GHSLue,year)` |
| 185 | CallExpression | `IC = IC.filter(ee.Filter.equals('builtup_year',year))` |
| 195 | CallExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 197 | BinaryExpression | `Map.addLayer(GHSLyear,{palette:'black'},"built-up GHSL "+year+" (cell gte 10% built-up)",false)` |
| 199 | CallExpression | `var GHSLbud = yearfilter(KigaliBD,year)` |
| 203 | BinaryExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (2%)",false)` |
| 205 | CallExpression | `var GHSLueyear = yearfilter(KigaliUE,year)` |
| 207 | BinaryExpression | `Map.addLayer(GHSLueyear,{color:'yellow'},"Urban Extent GHSL (10%) "+year+"",true)` |
| 211 | BinaryExpression | `Map.addLayer(GHSLueyear,{color:'blue'},"Urban Extent GHSL (10%) "+year+" buffered",false)` |

## script_100145:A2:GHSL2023releaseYear

自动化: analysis_chain/2 ｜ 人工: analysis_chain/4 ｜ 出现位置数: 10
裁定依据: 同作用域多次声明/赋值，逐处核对读取

定义: [{'line': 193, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 117 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 117 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 133 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 133 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 149 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 149 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 167 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 167 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 195 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |
| 195 | MemberExpression | `var GHSLyear = GHSL2023releaseYear.updateMask(GHSL2023releaseYear.lte(year)).gt(0)` |

## script_100145:A2:GHSLbud

自动化: analysis_chain/2 ｜ 人工: presentation_only/9 ｜ 出现位置数: 10
裁定依据: 暂定分析（进入 yearfilter/visfilter）；2 vs 9 需复核；源码确认前不锁旧标签 presentation_only

定义: [{'line': 201, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 123 | CallExpression | `var GHSLbud = visfilter(GHSLbud)` |
| 125 | CallExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (2%)",false)` |
| 139 | CallExpression | `var GHSLbud = visfilter(GHSLbud)` |
| 141 | CallExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (5%)",false)` |
| 155 | CallExpression | `var GHSLbud = visfilter(GHSLbud)` |
| 157 | CallExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (10%)",false)` |
| 173 | CallExpression | `var GHSLbud = visfilter(GHSLbud)` |
| 175 | CallExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (20%)",false)` |
| 201 | CallExpression | `var GHSLbud = visfilter(GHSLbud)` |
| 203 | CallExpression | `Map.addLayer(GHSLbud,{palette:["green","pink","blue"],min:0,max:2},"class GHSL "+year+" (2%)",false)` |

## script_100145:A2:GHSLueyear

自动化: analysis_chain/2 ｜ 人工: presentation_only/8 ｜ 出现位置数: 4
裁定依据: 暂定分析（末尾缓冲处理后展示，或双重用途）；需检查缓冲作用与全部引用位置

定义: [{'line': 209, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 161 | CallExpression | `Map.addLayer(GHSLueyear,{color:'orange'},"Urban Extent GHSL "+year+" (10%)",true)` |
| 207 | CallExpression | `Map.addLayer(GHSLueyear,{color:'yellow'},"Urban Extent GHSL (10%) "+year+"",true)` |
| 209 | MemberExpression | `var GHSLueyear = GHSLueyear.map(function(feat){return feat.buffer(50)})` |
| 211 | CallExpression | `Map.addLayer(GHSLueyear,{color:'blue'},"Urban Extent GHSL (10%) "+year+" buffered",false)` |

## script_101095:A2:image

自动化: analysis_chain/3 ｜ 人工: analysis_chain/4 ｜ 出现位置数: 3
裁定依据: 备注计 4；需按'同一调用表达式接收对象不重复计数'复核

定义: [{'line': 9, 'kind': 'param'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 11 | MemberExpression | `var edge = image.lt(-30.0);` |
| 13 | MemberExpression | `var maskedImage = image.mask().and(edge.not());` |
| 15 | MemberExpression | `return image.updateMask(maskedImage);` |

## script_191158:A2:timeField

自动化: analysis_chain/9 ｜ 人工: analysis_chain/5 ｜ 出现位置数: 9
裁定依据: 状态无争议，计数待源码核验

定义: [{'line': 7, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 27 | CallExpression | `var date = ee.Date(image.get(timeField));` |
| 95 | ArrayExpression | `.copyProperties(image, [timeField]);` |
| 193 | Property | `leftField: timeField,` |
| 195 | Property | `rightField: timeField` |
| 201 | Property | `leftField: timeField,` |
| 203 | Property | `rightField: timeField` |
| 213 | Property | `ordering: timeField,` |
| 517 | Property | `leftField: timeField,` |
| 519 | Property | `rightField: timeField` |

## script_191158:A2:date

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 27, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 29 | MemberExpression | `var years = date.difference(ee.Date('1970-01-01'), 'year');` |
| 419 | CallExpression | `'system:time_start': ee.Date(date).millis()` |

## script_191158:A2:filteredLandsat

自动化: analysis_chain/11 ｜ 人工: analysis_chain/10 ｜ 出现位置数: 11
裁定依据: —

定义: [{'line': 41, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 49 | CallExpression | `print('filteredLandsat',filteredLandsat)` |
| 51 | MemberExpression | `var l8Chart = ui.Chart.image.series(filteredLandsat.select('NDVI'), roi)` |
| 77 | MemberExpression | `var trend = filteredLandsat.select(independents.add(dependent))` |
| 87 | MemberExpression | `var detrended = filteredLandsat.map(function(image) {` |
| 115 | MemberExpression | `var harmonicLandsat = filteredLandsat.map(function(image) {` |
| 297 | CallExpression | `var lag1PrecipNDVI = lag(filteredLandsat, chirps, 5);` |
| 313 | CallExpression | `var lag30PrecipNDVI = lag(filteredLandsat, chirps, 30);` |
| 333 | CallExpression | `var lagged34 = ee.ImageCollection(lag(filteredLandsat, filteredLandsat, 34));` |
| 333 | CallExpression | `var lagged34 = ee.ImageCollection(lag(filteredLandsat, filteredLandsat, 34));` |
| 433 | MemberExpression | `var first = filteredLandsat.first();` |
| 435 | MemberExpression | `var filled = ee.List(filteredLandsat.iterate(fill, [first])).slice(1);` |

## script_191158:A2:independents

自动化: analysis_chain/4 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 4
裁定依据: —

定义: [{'line': 73, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 77 | MemberExpression | `var trend = filteredLandsat.select(independents.add(dependent))` |
| 79 | MemberExpression | `.reduce(ee.Reducer.linearRegression(independents.length(), 1));` |
| 85 | ArrayExpression | `.arrayFlatten([independents]);` |
| 91 | CallExpression | `image.select(independents).multiply(coefficients).reduce('sum'))` |

## script_191158:A2:dependent

自动化: analysis_chain/9 ｜ 人工: analysis_chain/7 ｜ 出现位置数: 9
裁定依据: —

定义: [{'line': 75, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 77 | CallExpression | `var trend = filteredLandsat.select(independents.add(dependent))` |
| 89 | CallExpression | `return image.select(dependent).subtract(` |
| 93 | CallExpression | `.rename(dependent)` |
| 129 | CallExpression | `.select(harmonicIndependents.add(dependent))` |
| 257 | MemberExpression | `var lagBand = dependent.cat('_1');` |
| 259 | CallExpression | `var covariance17 = ee.Image(covariance(merged17, dependent, lagBand));` |
| 291 | CallExpression | `var covariance34 = ee.Image(covariance(merged34, dependent, dependent.cat('_2')));` |
| 291 | MemberExpression | `var covariance34 = ee.Image(covariance(merged34, dependent, dependent.cat('_2')));` |
| 345 | CallExpression | `.select(arIndependents.add(dependent))` |

## script_191158:A2:harmonicIndependents

自动化: analysis_chain/4 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 4
裁定依据: —

定义: [{'line': 113, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 129 | MemberExpression | `.select(harmonicIndependents.add(dependent))` |
| 131 | MemberExpression | `.reduce(ee.Reducer.linearRegression(harmonicIndependents.length(), 1));` |
| 137 | ArrayExpression | `.arrayFlatten([harmonicIndependents]);` |
| 143 | CallExpression | `image.select(harmonicIndependents)` |

## script_191158:A2:start

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 397, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 403 | MemberExpression | `condition: start.lt(end),` |
| 407 | Property | `start: start,` |

## script_191158:A2:end

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 399, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 403 | CallExpression | `condition: start.lt(end),` |
| 409 | Property | `end: end,` |

## script_191158:A2:ndvi

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 441, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 473 | MemberExpression | `srcImg: ndvi.unmask().where(ndvi.mask().not(), predicted).rename('NDVI'),` |
| 473 | MemberExpression | `srcImg: ndvi.unmask().where(ndvi.mask().not(), predicted).rename('NDVI'),` |

## script_216850:A2:bands

自动化: analysis_chain/4 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 4
裁定依据: —

定义: [{'line': 37, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 47 | CallExpression | `var training = imagenew.select(bands).sampleRegions({` |
| 57 | CallExpression | `var validation = imagenew.select(bands).sampleRegions({` |
| 73 | Property | `inputProperties: bands` |
| 77 | CallExpression | `var classified = imagenew.select(bands).classify(classifier);` |

## script_216850:A2:classified

自动化: analysis_chain/5 ｜ 人工: analysis_chain/4 ｜ 出现位置数: 5
裁定依据: —

定义: [{'line': 77, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 85 | SequenceExpression | `var LULC = (classified, {min:0,max:5,palette:['#1BFF00'/*green*/,'#ffff00'/*orange*/,'#FF2D00'/*red*/,'#0023FF'/*blue*/,'#FF00F7'/*pink*/,'#9B00FF']});` |
| 87 | CallExpression | `Map.addLayer(classified,{min:0,max:5,palette:['#1BFF00'/*green*/,'#ffff00'/*orange*/,'#FF2D00'/*red*/,'#0023FF'/*blue*/,'#FF00F7'/*pink*/,'#9B00FF']},"land cove` |
| 91 | Property | `srcImg : classified,` |
| 115 | MemberExpression | `var sunflower = classified.eq(0).selfMask();` |
| 139 | CallExpression | `var areaImage = ee.Image.pixelArea().divide(1e4).multiply(2.471).addBands(classified);` |

## script_217669:A2:blank

自动化: analysis_chain/1 ｜ 人工: presentation_only/1 ｜ 出现位置数: 1
裁定依据: 暂定；需确认是否还有其他分析操作

定义: [{'line': 173, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 175 | MemberExpression | `var outline = blank.paint(myGrid, 'AA0000', 2);` |

## script_217669:A2:collection

自动化: analysis_chain/4 ｜ 人工: analysis_chain/6 ｜ 出现位置数: 4
裁定依据: —

定义: [{'line': 181, 'kind': 'param'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 183 | MemberExpression | `collection = collection.randomColumn('random', seed || 1)` |
| 205 | MemberExpression | `collection.reduceColumns(ee.Reducer.toList(), ['new_id'])` |
| 209 | MemberExpression | `var sequentialIdList = ee.List.sequence(1, collection.size());` |
| 211 | MemberExpression | `var shuffled = collection.remap(randomIdList, sequentialIdList, 'new_id');` |

## script_217669:A2:rescaled

自动化: analysis_chain/1 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 1
裁定依据: —

定义: [{'line': 191, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 197 | CallExpression | `return feature.set('new_id', rescaled);` |

## script_217669:A2:year

自动化: analysis_chain/4 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 4
裁定依据: —

定义: [{'line': 245, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 247 | BinaryExpression | `var class_map_year = class_map.select('classification_'+year)` |
| 249 | BinaryExpression | `Map.addLayer(class_map_year, vis, 'RF'+year+"_"+grid_name, false);` |
| 253 | BinaryExpression | `var errorMatrix_abs = valida_reg.errorMatrix('reference','classification_'+year)` |
| 255 | CallExpression | `print(year, errorMatrix_abs.accuracy())` |

## script_35821:A2:SZ_rad

自动化: analysis_chain/2 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 19, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 29 | MemberExpression | `var cosZ = SZ_rad.cos();` |
| 39 | MemberExpression | `var sinZ = SZ_rad.sin();` |

## script_35821:A2:cosZ

自动化: analysis_chain/2 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 29, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 35 | Property | `{'cosZ': cosZ,` |
| 55 | MemberExpression | `var img_plus_ic = ee.Image(img.addBands(ic.rename('IC')).addBands(cosZ.rename('cosZ')).addBands(cosS.rename('cosS')).addBands(slp.rename('slope')));` |

## script_35821:A2:sinZ

自动化: analysis_chain/2 ｜ 人工: analysis_chain/1 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 39, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 45 | MemberExpression | `var aspect_illumination = sinZ.expression("sinZ * sinS * cosAziDiff",` |
| 47 | Property | `{'sinZ': sinZ,` |

## script_35821:A2:img_plus_ic_mask2

自动化: analysis_chain/7 ｜ 人工: analysis_chain/11 ｜ 出现位置数: 7
裁定依据: —

定义: [{'line': 77, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 91 | MemberExpression | `var out = img_plus_ic_mask2.select('IC', band).reduceRegion({` |
| 105 | MemberExpression | `return img_plus_ic_mask2.select(band);` |
| 117 | MemberExpression | `var SCSc_output = img_plus_ic_mask2.expression(` |
| 121 | MemberExpression | `'image': img_plus_ic_mask2.select(band),` |
| 123 | MemberExpression | `'ic': img_plus_ic_mask2.select('IC'),` |
| 125 | MemberExpression | `'cosB': img_plus_ic_mask2.select('cosS'),` |
| 127 | MemberExpression | `'cosZ': img_plus_ic_mask2.select('cosZ'),` |

## script_35821:A2:band

自动化: analysis_chain/3 ｜ 人工: analysis_chain/4 ｜ 出现位置数: 3
裁定依据: —

定义: [{'line': 87, 'kind': 'param'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 91 | CallExpression | `var out = img_plus_ic_mask2.select('IC', band).reduceRegion({` |
| 105 | CallExpression | `return img_plus_ic_mask2.select(band);` |
| 121 | CallExpression | `'image': img_plus_ic_mask2.select(band),` |

## script_35821:A2:out

自动化: analysis_chain/4 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 4
裁定依据: —

定义: [{'line': 91, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 103 | BinaryExpression | `if (out === null || out === undefined ){` |
| 103 | BinaryExpression | `if (out === null || out === undefined ){` |
| 111 | MemberExpression | `var out_a = ee.Number(out.get('scale'));` |
| 113 | MemberExpression | `var out_b = ee.Number(out.get('offset'));` |

## script_35821:A2:img_SCSccorr

自动化: analysis_chain/2 ｜ 人工: analysis_chain/3 ｜ 出现位置数: 2
裁定依据: —

定义: [{'line': 139, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 143 | MemberExpression | `img_SCSccorr = img_SCSccorr.unmask(img_plus_ic.select(bandList_IC)).select(bandList);` |
| 145 | MemberExpression | `return img_SCSccorr.addBands(nonCorrectBands)` |

## script_35821:A2:aero

自动化: analysis_chain/1 ｜ 人工: analysis_chain/2 ｜ 出现位置数: 1
裁定依据: —

定义: [{'line': 157, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 161 | MemberExpression | `.and(qa.bitwiseAnd(1<<8-9).eq(0)).and(aero.bitwiseAnd(1<<6-7).eq(0));` |

## script_45485:A2:image

自动化: analysis_chain/6 ｜ 人工: analysis_chain/8 ｜ 出现位置数: 6
裁定依据: —

定义: [{'line': 5, 'kind': 'param'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 7 | MemberExpression | `var Pheno = image.select(['Greenup_1','MidGreenup_1','Peak_1','Maturity_1','Senescence_1','MidGreendown_1','Dormancy_1']);` |
| 9 | MemberExpression | `var QA = image.select('QA_Detailed_1');` |
| 13 | MemberExpression | `var mask = image.select('NumCycles').gte(1);` |
| 15 | MemberExpression | `var time = ee.Image.constant(image.date().difference(ee.Date('1970-01-01'), 'day')).subtract(ee.Image(1)).int();` |
| 17 | MemberExpression | `var year = ee.Image(image.date().difference(ee.Date('2000-01-01'), 'year')).int().rename("year");` |
| 21 | CallExpression | `return time.addBands(Pheno).copyProperties(image, ["system:time_start"]);` |

## script_7900:A2:dem

自动化: analysis_chain/3 ｜ 人工: analysis_chain/2 ｜ 出现位置数: 3
裁定依据: —

定义: [{'line': 55, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 65 | CallExpression | `var slp = ee.Terrain.slope(dem).clip(img.geometry().buffer(10000));` |
| 67 | CallExpression | `var slp_rad = ee.Terrain.slope(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));` |
| 69 | CallExpression | `var asp_rad = ee.Terrain.aspect(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));` |

## script_7900:A2:ic

自动化: analysis_chain/1 ｜ 人工: analysis_chain/2 ｜ 出现位置数: 1
裁定依据: —

定义: [{'line': 95, 'kind': 'declaration'}]

| 行 | 父节点类型 | 行文本 |
|---|---|---|
| 97 | MemberExpression | `var img_plus_ic = ee.Image(img.addBands(ic.rename('IC')).addBands(cosZ.rename('cosZ')).addBands(cosS.rename('cosS')).addBands(slp.rename('slope')));` |
