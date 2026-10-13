# 标注单 script_45485

源码 SHA-256: `3097c1d551b838136d7a29ecff539d2259f7d6667aaca2c2a745230d96a4ccb9`
完整源码路径: `.tmp_gee_batch13_sources/Data/data50000/script_45485.txt`

## A1 未声明候选变量（三分类裁定）

分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| `missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| `undeterminable`（无法裁定）

### script_45485:A1:MCD12Q2_2003_Full

变量: `MCD12Q2_2003_Full`  使用行: [1]  证据线索: （无）

```javascript
    1 | var MCD12Q2_North=MCD12Q2_2003_Full.updateMask(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy.gte(0))
    2 | 
    3 | var MCD12Q2 = ee.ImageCollection("MODIS/006/MCD12Q2").filter(ee.Filter.date('2003-01-01','2004-01-01'));
```

裁定: ______________________  备注: ____________

### script_45485:A1:Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy

变量: `Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy`  使用行: [1, 51]  证据线索: （无）

```javascript
    1 | var MCD12Q2_North=MCD12Q2_2003_Full.updateMask(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy.gte(0))
    2 | 
    3 | var MCD12Q2 = ee.ImageCollection("MODIS/006/MCD12Q2").filter(ee.Filter.date('2003-01-01','2004-01-01'));
   49 | Map.addLayer(lai_2003_raw,{},"lai_2003_raw");
   50 | 
   51 | Map.addLayer(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy,{},"Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy")
   52 | 
   53 | Map.addLayer(Alashanzuoqi_T_Greenup_Dormancy,{},"Alashanzuoqi_T_Greenup_Dormancy");
```

裁定: ______________________  备注: ____________

### script_45485:A1:Alashanzuoqi_T_Greenup_Dormancy

变量: `Alashanzuoqi_T_Greenup_Dormancy`  使用行: [53]  证据线索: （无）

```javascript
   51 | Map.addLayer(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy,{},"Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy")
   52 | 
   53 | Map.addLayer(Alashanzuoqi_T_Greenup_Dormancy,{},"Alashanzuoqi_T_Greenup_Dormancy");
```

裁定: ______________________  备注: ____________

## A2 声明变量使用分类

状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| `analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数

### script_45485:A2:MCD12Q2_North

变量: `MCD12Q2_North`  定义行: 1

```javascript
    1 | var MCD12Q2_North=MCD12Q2_2003_Full.updateMask(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy.gte(0))
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:MCD12Q2

变量: `MCD12Q2`  定义行: 3

```javascript
    2 | 
    3 | var MCD12Q2 = ee.ImageCollection("MODIS/006/MCD12Q2").filter(ee.Filter.date('2003-01-01','2004-01-01'));
    4 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:DOY1

变量: `DOY1`  定义行: 5

```javascript
    4 | 
    5 | var DOY1 = function(image){
    6 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:image

变量: `image`  定义行: 5

```javascript
    4 | 
    5 | var DOY1 = function(image){
    6 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:QA

变量: `QA`  定义行: 9

```javascript
    8 | 
    9 |   var QA = image.select('QA_Detailed_1');
   10 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:bitMask_Dormancy_1

变量: `bitMask_Dormancy_1`  定义行: 11

```javascript
   10 | 
   11 |   var bitMask_Dormancy_1 = 3 << 12;
   12 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:mask

变量: `mask`  定义行: 13

```javascript
   12 | 
   13 |   var mask = image.select('NumCycles').gte(1);
   14 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:time

变量: `time`  定义行: 15

```javascript
   14 | 
   15 |   var time = ee.Image.constant(image.date().difference(ee.Date('1970-01-01'), 'day')).subtract(ee.Image(1)).int();
   16 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:year

变量: `year`  定义行: 17

```javascript
   16 | 
   17 |   var year = ee.Image(image.date().difference(ee.Date('2000-01-01'), 'year')).int().rename("year");
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:Pheno

变量: `Pheno`  定义行: 25

```javascript
   24 | 
   25 | var Pheno = MCD12Q2.map(DOY1);
   26 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:Greenup_1

变量: `Greenup_1`  定义行: 29

```javascript
   28 | 
   29 | var Greenup_1=Pheno.select('Greenup_1');
   30 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:Dormancy_1

变量: `Dormancy_1`  定义行: 31

```javascript
   30 | 
   31 | var Dormancy_1=Pheno.select('Dormancy_1');
   32 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:lai_2003_raw

变量: `lai_2003_raw`  定义行: 33

```javascript
   32 | 
   33 | var lai_2003_raw= ee.ImageCollection("MODIS/006/MCD15A3H").select('Lai')
   34 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:img

变量: `img`  定义行: 37

```javascript
   36 | 
   37 |                  .map(function(img){
   38 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:Image_col_2003

变量: `Image_col_2003`  定义行: 39

```javascript
   38 | 
   39 |                   var Image_col_2003=ee.Image(img);
   40 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_45485:A2:Image_2003

变量: `Image_2003`  定义行: 41

```javascript
   40 | 
   41 |                   var Image_2003=(Image_col_2003.where(Image_col_2003.gt(100),0)).toInt();
   42 | 
```

状态: ____________  后继使用数: ______  备注: ____________

## A3 调用语句角色

角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，按你的判断给出应属角色）| `undeterminable`

### 行 1（script_45485:A3:41、script_45485:A3:42）

```javascript
    1 | var MCD12Q2_North=MCD12Q2_2003_Full.updateMask(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy.gte(0))
```

角色: ____________

### 行 3（script_45485:A3:38、script_45485:A3:39、script_45485:A3:40）

```javascript
    3 | var MCD12Q2 = ee.ImageCollection("MODIS/006/MCD12Q2").filter(ee.Filter.date('2003-01-01','2004-01-01'));
```

角色: ____________

### 行 7（script_45485:A3:37）

```javascript
    7 |   var Pheno = image.select(['Greenup_1','MidGreenup_1','Peak_1','Maturity_1','Senescence_1','MidGreendown_1','Dormancy_1']);
```

角色: ____________

### 行 9（script_45485:A3:36）

```javascript
    9 |   var QA = image.select('QA_Detailed_1');
```

角色: ____________

### 行 13（script_45485:A3:34、script_45485:A3:35）

```javascript
   13 |   var mask = image.select('NumCycles').gte(1);
```

角色: ____________

### 行 15（script_45485:A3:27、script_45485:A3:28、script_45485:A3:29、script_45485:A3:30、script_45485:A3:31、script_45485:A3:32、script_45485:A3:33）

```javascript
   15 |   var time = ee.Image.constant(image.date().difference(ee.Date('1970-01-01'), 'day')).subtract(ee.Image(1)).int();
```

角色: ____________

### 行 17（script_45485:A3:21、script_45485:A3:22、script_45485:A3:23、script_45485:A3:24、script_45485:A3:25、script_45485:A3:26）

```javascript
   17 |   var year = ee.Image(image.date().difference(ee.Date('2000-01-01'), 'year')).int().rename("year");
```

角色: ____________

### 行 19（script_45485:A3:18、script_45485:A3:19、script_45485:A3:20）

```javascript
   19 |   Pheno = Pheno.subtract(time).updateMask(mask).toInt()//.reproject('EPSG:4326',null, 500);//.updateMask(QA.bitwiseAnd(bitMask_Dormancy_1).lt(2 << 12)
```

角色: ____________

### 行 21（script_45485:A3:16、script_45485:A3:17）

```javascript
   21 |   return time.addBands(Pheno).copyProperties(image, ["system:time_start"]);
```

角色: ____________

### 行 25（script_45485:A3:15）

```javascript
   25 | var Pheno = MCD12Q2.map(DOY1);
```

角色: ____________

### 行 27（script_45485:A3:14）

```javascript
   27 | print("Pheno is",Pheno);
```

角色: ____________

### 行 29（script_45485:A3:13）

```javascript
   29 | var Greenup_1=Pheno.select('Greenup_1');
```

角色: ____________

### 行 31（script_45485:A3:12）

```javascript
   31 | var Dormancy_1=Pheno.select('Dormancy_1');
```

角色: ____________

### 行 33（script_45485:A3:4、script_45485:A3:9、script_45485:A3:10、script_45485:A3:11）

```javascript
   33 | var lai_2003_raw= ee.ImageCollection("MODIS/006/MCD15A3H").select('Lai')
```

角色: ____________

### 行 39（script_45485:A3:8）

```javascript
   39 |                   var Image_col_2003=ee.Image(img);
```

角色: ____________

### 行 41（script_45485:A3:5、script_45485:A3:6、script_45485:A3:7）

```javascript
   41 |                   var Image_2003=(Image_col_2003.where(Image_col_2003.gt(100),0)).toInt();
```

角色: ____________

### 行 47（script_45485:A3:3）

```javascript
   47 | print('lai_2003_raw',lai_2003_raw)
```

角色: ____________

### 行 49（script_45485:A3:2）

```javascript
   49 | Map.addLayer(lai_2003_raw,{},"lai_2003_raw");
```

角色: ____________

### 行 51（script_45485:A3:1）

```javascript
   51 | Map.addLayer(Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy,{},"Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy")
```

角色: ____________

### 行 53（script_45485:A3:0）

```javascript
   53 | Map.addLayer(Alashanzuoqi_T_Greenup_Dormancy,{},"Alashanzuoqi_T_Greenup_Dormancy");
```

角色: ____________
