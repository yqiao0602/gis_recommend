# 标注单 script_25214

源码 SHA-256: `e0cafc2f8fec37ecd0039a790e55bee7a2f838e5dc637bcec70429827b65b0e1`
完整源码路径: `.tmp_gee_batch13_sources/Data/data30000/script_25214.txt`

## A1 未声明候选变量（三分类裁定）

分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| `missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| `undeterminable`（无法裁定）

## A2 声明变量使用分类

状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| `analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数

### script_25214:A2:tiempo1

变量: `tiempo1`  定义行: 1

```javascript
    1 | var tiempo1 = ee.ImageCollection('COPERNICUS/S2')
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_25214:A2:tiempo1b

变量: `tiempo1b`  定义行: 7

```javascript
    6 | 
    7 | var tiempo1b = tiempo1.reduce(ee.Reducer.median());
    8 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_25214:A2:tiempo2

变量: `tiempo2`  定义行: 9

```javascript
    8 | 
    9 | var tiempo2 = ee.ImageCollection('COPERNICUS/S2')
   10 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_25214:A2:tiempo2b

变量: `tiempo2b`  定义行: 15

```javascript
   14 | 
   15 | var tiempo2b = tiempo2.reduce(ee.Reducer.median());
   16 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_25214:A2:NDVI1

变量: `NDVI1`  定义行: 17

```javascript
   16 | 
   17 | var NDVI1 = tiempo1b.normalizedDifference(['B8_median','B4_median']);
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_25214:A2:NDVI2

变量: `NDVI2`  定义行: 19

```javascript
   18 | 
   19 | var NDVI2 = tiempo2b.normalizedDifference(['B8_median','B4_median']);
   20 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_25214:A2:NDVImultitemporal

变量: `NDVImultitemporal`  定义行: 21

```javascript
   20 | 
   21 | var NDVImultitemporal = NDVI1.addBands(NDVI1).addBands(NDVI2);
   22 | 
```

状态: ____________  后继使用数: ______  备注: ____________

## A3 调用语句角色

角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，按你的判断给出应属角色）| `undeterminable`

### 行 1（script_25214:A3:15、script_25214:A3:16、script_25214:A3:17）

```javascript
    1 | var tiempo1 = ee.ImageCollection('COPERNICUS/S2')
```

角色: ____________

### 行 7（script_25214:A3:13、script_25214:A3:14）

```javascript
    7 | var tiempo1b = tiempo1.reduce(ee.Reducer.median());
```

角色: ____________

### 行 9（script_25214:A3:10、script_25214:A3:11、script_25214:A3:12）

```javascript
    9 | var tiempo2 = ee.ImageCollection('COPERNICUS/S2')
```

角色: ____________

### 行 15（script_25214:A3:8、script_25214:A3:9）

```javascript
   15 | var tiempo2b = tiempo2.reduce(ee.Reducer.median());
```

角色: ____________

### 行 17（script_25214:A3:7）

```javascript
   17 | var NDVI1 = tiempo1b.normalizedDifference(['B8_median','B4_median']);
```

角色: ____________

### 行 19（script_25214:A3:6）

```javascript
   19 | var NDVI2 = tiempo2b.normalizedDifference(['B8_median','B4_median']);
```

角色: ____________

### 行 21（script_25214:A3:4、script_25214:A3:5）

```javascript
   21 | var NDVImultitemporal = NDVI1.addBands(NDVI1).addBands(NDVI2);
```

角色: ____________

### 行 23（script_25214:A3:3）

```javascript
   23 | Map.addLayer(NDVI1,{max:1,min:0, palette:['CE7E45','DF923D','F1B555','FCD163',
```

角色: ____________

### 行 27（script_25214:A3:2）

```javascript
   27 |   Map.addLayer(NDVI2,{max:1,min:0, palette:['CE7E45','DF923D','F1B555','FCD163',
```

角色: ____________

### 行 31（script_25214:A3:1）

```javascript
   31 | Map.addLayer(NDVImultitemporal,{max:0.7,min:0.1,gamma:1.0},'NDVI multitemporal');
```

角色: ____________

### 行 33（script_25214:A3:0）

```javascript
   33 | Map.setCenter(-71,-17,10);
```

角色: ____________
