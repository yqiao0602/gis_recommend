# 标注单 script_10021

源码 SHA-256: `60f6938a24842715b982fa986fd865b5d710c004e35e035243e8970500201126`
完整源码路径: `.tmp_gee_batch13_sources/Data/data20000/script_10021.txt`

## A1 未声明候选变量（三分类裁定）

分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| `missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| `undeterminable`（无法裁定）

## A2 声明变量使用分类

状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| `analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数

### script_10021:A2:c

变量: `c`  定义行: 1

```javascript
    1 | var c = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017').filter(ee.Filter.eq('country_na', 'Thailand'));
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:landsat

变量: `landsat`  定义行: 3

```javascript
    2 | 
    3 | var landsat = ee.ImageCollection("LANDSAT/LC08/C01/T1")
    4 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:composite

变量: `composite`  定义行: 9

```javascript
    8 | 
    9 | var composite = ee.Algorithms.Landsat.simpleComposite({
   10 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:b5

变量: `b5`  定义行: 17

```javascript
   16 | 
   17 | var b5 = composite.select("B5")
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:b4

变量: `b4`  定义行: 19

```javascript
   18 | 
   19 | var b4 = composite.select("B4")
   20 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:ndvi_1

变量: `ndvi_1`  定义行: 21

```javascript
   20 | 
   21 | var ndvi_1 = b5.subtract(b4).divide(b5.add(b4))
   22 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:ndvi_2

变量: `ndvi_2`  定义行: 23

```javascript
   22 | 
   23 | var ndvi_2 = composite.normalizedDifference(["B5", "B4"])
   24 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_10021:A2:ndvi_3

变量: `ndvi_3`  定义行: 25

```javascript
   24 | 
   25 | var ndvi_3 = composite.expression("(b5 - b4) / (b5 + b4)", {
   26 | 
```

状态: ____________  后继使用数: ______  备注: ____________

## A3 调用语句角色

角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，按你的判断给出应属角色）| `undeterminable`

### 行 1（script_10021:A3:17、script_10021:A3:18、script_10021:A3:19）

```javascript
    1 | var c = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017').filter(ee.Filter.eq('country_na', 'Thailand'));
```

角色: ____________

### 行 3（script_10021:A3:14、script_10021:A3:15、script_10021:A3:16）

```javascript
    3 | var landsat = ee.ImageCollection("LANDSAT/LC08/C01/T1")
```

角色: ____________

### 行 9（script_10021:A3:13）

```javascript
    9 | var composite = ee.Algorithms.Landsat.simpleComposite({
```

角色: ____________

### 行 17（script_10021:A3:12）

```javascript
   17 | var b5 = composite.select("B5")
```

角色: ____________

### 行 19（script_10021:A3:11）

```javascript
   19 | var b4 = composite.select("B4")
```

角色: ____________

### 行 21（script_10021:A3:8、script_10021:A3:9、script_10021:A3:10）

```javascript
   21 | var ndvi_1 = b5.subtract(b4).divide(b5.add(b4))
```

角色: ____________

### 行 23（script_10021:A3:7）

```javascript
   23 | var ndvi_2 = composite.normalizedDifference(["B5", "B4"])
```

角色: ____________

### 行 25（script_10021:A3:4）

```javascript
   25 | var ndvi_3 = composite.expression("(b5 - b4) / (b5 + b4)", {
```

角色: ____________

### 行 27（script_10021:A3:6）

```javascript
   27 |     b5: composite.select("B5"),
```

角色: ____________

### 行 29（script_10021:A3:5）

```javascript
   29 |     b4: composite.select("B4")
```

角色: ____________

### 行 33（script_10021:A3:3）

```javascript
   33 | Map.addLayer(ndvi_3, {min:0, max:1} , "NDVI_3")
```

角色: ____________

### 行 35（script_10021:A3:2）

```javascript
   35 | Map.addLayer(ndvi_2, {min:0, max:1} , "NDVI_2")
```

角色: ____________

### 行 37（script_10021:A3:1）

```javascript
   37 | Map.addLayer(ndvi_1, {min:0, max:1} , "NDVI_1")
```

角色: ____________

### 行 39（script_10021:A3:0）

```javascript
   39 | Map.centerObject(c, 8)
```

角色: ____________
