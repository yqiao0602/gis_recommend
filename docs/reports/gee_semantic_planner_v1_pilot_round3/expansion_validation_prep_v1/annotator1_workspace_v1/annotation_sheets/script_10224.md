# 标注单 script_10224

源码 SHA-256: `99fdd7c16e1695c9e5d3268e68f1618caba8fc9e159ae636d06cf7d2aa1abcd6`
完整源码路径: `.tmp_gee_batch13_sources/Data/data20000/script_10224.txt`

## A1 未声明候选变量（三分类裁定）

分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| `missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| `undeterminable`（无法裁定）

## A2 声明变量使用分类

状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| `analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数

### script_10224:A2:COL_FILTER

变量: `COL_FILTER`  定义行: 1

```javascript
    1 | var COL_FILTER = ee.Filter.and(
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:dwCol

变量: `dwCol`  定义行: 7

```javascript
    6 | 
    7 | var dwCol = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filter(COL_FILTER);
    8 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:s2Col

变量: `s2Col`  定义行: 9

```javascript
    8 | 
    9 | var s2Col = ee.ImageCollection('COPERNICUS/S2').filter(COL_FILTER);
   10 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:DwS2Col

变量: `DwS2Col`  定义行: 11

```javascript
   10 | 
   11 | var DwS2Col = ee.Join.saveFirst('s2_img').apply(dwCol, s2Col,
   12 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:dwImage

变量: `dwImage`  定义行: 15

```javascript
   14 | 
   15 | var dwImage = ee.Image(DwS2Col.first());
   16 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:s2Image

变量: `s2Image`  定义行: 17

```javascript
   16 | 
   17 | var s2Image = ee.Image(dwImage.get('s2_img'));
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:CLASS_NAMES

变量: `CLASS_NAMES`  定义行: 19

```javascript
   18 | 
   19 | var CLASS_NAMES = [
   20 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:dwRgb

变量: `dwRgb`  定义行: 33

```javascript
   32 | 
   33 | var dwRgb = dwImage
   34 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:top1Prob

变量: `top1Prob`  定义行: 41

```javascript
   40 | 
   41 | var top1Prob = dwImage.select(CLASS_NAMES).reduce(ee.Reducer.max());
   42 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:top1ProbHillshade

变量: `top1ProbHillshade`  定义行: 43

```javascript
   42 | 
   43 | var top1ProbHillshade =
   44 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10224:A2:dwRgbHillshade

变量: `dwRgbHillshade`  定义行: 49

```javascript
   48 | 
   49 | var dwRgbHillshade = dwRgb.multiply(top1ProbHillshade);
   50 | 
```

状态: ____________  后继使用数: ______  备注: ____________

## A3 调用语句角色

角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，按你的判断给出应属角色）| `undeterminable`

### 行 1（script_10224:A3:24）

```javascript
    1 | var COL_FILTER = ee.Filter.and(
```

角色: ____________

### 行 3（script_10224:A3:26、script_10224:A3:27）

```javascript
    3 |     ee.Filter.bounds(ee.Geometry.Point(20.6729, 52.4305)),
```

角色: ____________

### 行 5（script_10224:A3:25）

```javascript
    5 |     ee.Filter.date('2021-04-02', '2021-04-03'));
```

角色: ____________

### 行 7（script_10224:A3:22、script_10224:A3:23）

```javascript
    7 | var dwCol = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filter(COL_FILTER);
```

角色: ____________

### 行 9（script_10224:A3:20、script_10224:A3:21）

```javascript
    9 | var s2Col = ee.ImageCollection('COPERNICUS/S2').filter(COL_FILTER);
```

角色: ____________

### 行 11（script_10224:A3:17、script_10224:A3:19）

```javascript
   11 | var DwS2Col = ee.Join.saveFirst('s2_img').apply(dwCol, s2Col,
```

角色: ____________

### 行 13（script_10224:A3:18）

```javascript
   13 |     ee.Filter.equals({leftField: 'system:index', rightField: 'system:index'}));
```

角色: ____________

### 行 15（script_10224:A3:15、script_10224:A3:16）

```javascript
   15 | var dwImage = ee.Image(DwS2Col.first());
```

角色: ____________

### 行 17（script_10224:A3:13、script_10224:A3:14）

```javascript
   17 | var s2Image = ee.Image(dwImage.get('s2_img'));
```

角色: ____________

### 行 33（script_10224:A3:10、script_10224:A3:11、script_10224:A3:12）

```javascript
   33 | var dwRgb = dwImage
```

角色: ____________

### 行 41（script_10224:A3:7、script_10224:A3:8、script_10224:A3:9）

```javascript
   41 | var top1Prob = dwImage.select(CLASS_NAMES).reduce(ee.Reducer.max());
```

角色: ____________

### 行 45（script_10224:A3:4、script_10224:A3:5、script_10224:A3:6）

```javascript
   45 |     ee.Terrain.hillshade(top1Prob.multiply(100))
```

角色: ____________

### 行 49（script_10224:A3:3）

```javascript
   49 | var dwRgbHillshade = dwRgb.multiply(top1ProbHillshade);
```

角色: ____________

### 行 51（script_10224:A3:2）

```javascript
   51 | Map.setCenter(20.6729, 52.4305, 12);
```

角色: ____________

### 行 53（script_10224:A3:1）

```javascript
   53 | Map.addLayer(
```

角色: ____________

### 行 61（script_10224:A3:0）

```javascript
   61 | Map.addLayer(
```

角色: ____________
