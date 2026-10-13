# 标注单 script_7900

源码 SHA-256: `8760100f63f1690dc75eda22f31583698b1599040abab8b2ab66e3a7ce5460b7`
完整源码路径: `.tmp_gee_batch13_sources/Data/data10000/script_7900.txt`

## A1 未声明候选变量（三分类裁定）

分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| `missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| `undeterminable`（无法裁定）

### script_7900:A1:genhe

变量: `genhe`  使用行: [199, 215, 225]  证据线索: （无）

```javascript
  197 | .filterDate('2018-06-01','2018-08-31')
  198 | 
  199 | .filterBounds(genhe.geometry())
  200 | 
  201 | .filter(ee.Filter.lte('CLOUD_COVER',90))
  213 | print(landsat8);
  214 | 
  215 | var landsat8_composite = landsat8.qualityMosaic('NDVI').clip(genhe.geometry());
  216 | 
  217 | var mask = landsat8_composite.select('NDVI').lt(1);
  223 | EVI = landsat8_composite.select('EVI');
  224 | 
  225 | Export.image.toDrive(EVI,'EVI_2018','','EVI_2018','',genhe.geometry(),30);
```

裁定: ______________________  备注: ____________

### script_7900:A1:landsat8

变量: `landsat8`  使用行: [195]  证据线索: ['self_reference_in_initializing_assignment']

```javascript
  193 |   }
  194 | 
  195 | landsat8 = landsat8
  196 | 
  197 | .filterDate('2018-06-01','2018-08-31')
```

裁定: ______________________  备注: ____________

## A2 声明变量使用分类

状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| `analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数

### script_7900:A2:image

变量: `image`  定义行: 1

```javascript
    1 | function cloudMask(image) {
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:cloudMask

变量: `cloudMask`  定义行: 1

```javascript
    1 | function cloudMask(image) {
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:cloudShadowBitMask

变量: `cloudShadowBitMask`  定义行: 3

```javascript
    2 | 
    3 |  var cloudShadowBitMask = (1 << 3);
    4 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:cloudsBitMask

变量: `cloudsBitMask`  定义行: 5

```javascript
    4 | 
    5 |  var cloudsBitMask = (1 << 5);
    6 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:qa

变量: `qa`  定义行: 7

```javascript
    6 | 
    7 |  var qa = image.select('pixel_qa');
    8 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:NDVI

变量: `NDVI`  定义行: 17

```javascript
   16 | 
   17 | var NDVI = function(image) {
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:ndvi

变量: `ndvi`  定义行: 19

```javascript
   18 | 
   19 |   var ndvi = image.normalizedDifference(['B5', 'B4']).rename('NDVI');
   20 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:EVI

变量: `EVI`  定义行: 25

```javascript
   24 | 
   25 | var EVI = function (image){
   26 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:evi

变量: `evi`  定义行: 27

```javascript
   26 | 
   27 |   var evi =image.expression(
   28 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:NBR

变量: `NBR`  定义行: 45

```javascript
   44 | 
   45 | var NBR = function(image){
   46 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:nbr

变量: `nbr`  定义行: 47

```javascript
   46 | 
   47 |   var nbr = image.normalizedDifference(['B4','B7']).rename('NBR');
   48 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:scale

变量: `scale`  定义行: 53

```javascript
   52 | 
   53 | var scale = 300;
   54 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:dem

变量: `dem`  定义行: 55

```javascript
   54 | 
   55 | var dem = ee.Image("USGS/SRTMGL1_003");
   56 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:degree2radian

变量: `degree2radian`  定义行: 57

```javascript
   56 | 
   57 | var degree2radian = 0.01745;
   58 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:img

变量: `img`  定义行: 59

```javascript
   58 | 
   59 | function illuminationCondition(img){
   60 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:illuminationCondition

变量: `illuminationCondition`  定义行: 59

```javascript
   58 | 
   59 | function illuminationCondition(img){
   60 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:SZ_rad

变量: `SZ_rad`  定义行: 61

```javascript
   60 | 
   61 |   var SZ_rad = ee.Image.constant(ee.Number(img.get('SOLAR_ZENITH_ANGLE'))).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
   62 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:SA_rad

变量: `SA_rad`  定义行: 63

```javascript
   62 | 
   63 |   var SA_rad = ee.Image.constant(ee.Number(img.get('SOLAR_AZIMUTH_ANGLE')).multiply(3.14159265359).divide(180)).clip(img.geometry().buffer(10000));
   64 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:slp

变量: `slp`  定义行: 65

```javascript
   64 | 
   65 |   var slp = ee.Terrain.slope(dem).clip(img.geometry().buffer(10000));
   66 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:slp_rad

变量: `slp_rad`  定义行: 67

```javascript
   66 | 
   67 |   var slp_rad = ee.Terrain.slope(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
   68 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:asp_rad

变量: `asp_rad`  定义行: 69

```javascript
   68 | 
   69 |   var asp_rad = ee.Terrain.aspect(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
   70 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:cosZ

变量: `cosZ`  定义行: 71

```javascript
   70 | 
   71 |   var cosZ = SZ_rad.cos();
   72 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:cosS

变量: `cosS`  定义行: 73

```javascript
   72 | 
   73 |   var cosS = slp_rad.cos();
   74 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:slope_illumination

变量: `slope_illumination`  定义行: 75

```javascript
   74 | 
   75 |   var slope_illumination = cosS.expression("cosZ * cosS",
   76 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:sinZ

变量: `sinZ`  定义行: 81

```javascript
   80 | 
   81 |   var sinZ = SZ_rad.sin();
   82 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:sinS

变量: `sinS`  定义行: 83

```javascript
   82 | 
   83 |   var sinS = slp_rad.sin();
   84 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:cosAziDiff

变量: `cosAziDiff`  定义行: 85

```javascript
   84 | 
   85 |   var cosAziDiff = (SA_rad.subtract(asp_rad)).cos();
   86 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:aspect_illumination

变量: `aspect_illumination`  定义行: 87

```javascript
   86 | 
   87 |   var aspect_illumination = sinZ.expression("sinZ * sinS * cosAziDiff",
   88 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:ic

变量: `ic`  定义行: 95

```javascript
   94 | 
   95 |   var ic = slope_illumination.add(aspect_illumination);
   96 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:illuminationCorrection

变量: `illuminationCorrection`  定义行: 103

```javascript
  102 | 
  103 | function illuminationCorrection(img){
  104 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:props

变量: `props`  定义行: 105

```javascript
  104 | 
  105 |     var props = img.toDictionary();
  106 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:st

变量: `st`  定义行: 107

```javascript
  106 | 
  107 |     var st = img.get('system:time_start');
  108 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:img_plus_ic

变量: `img_plus_ic`  定义行: 109

```javascript
  108 | 
  109 |     var img_plus_ic = img;
  110 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:mask1

变量: `mask1`  定义行: 111

```javascript
  110 | 
  111 |     var mask1 = img_plus_ic.select('B4').gt(-0.1);
  112 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:mask2

变量: `mask2`  定义行: 113

```javascript
  112 | 
  113 |     var mask2 = img_plus_ic.select('slope').gte(5)
  114 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:img_plus_ic_mask2

变量: `img_plus_ic_mask2`  定义行: 119

```javascript
  118 | 
  119 |     var img_plus_ic_mask2 = ee.Image(img_plus_ic.updateMask(mask2));
  120 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:bandList

变量: `bandList`  定义行: 121

```javascript
  120 | 
  121 |     var bandList = ['B1','B2','B3','B4','B5','B7'];
  122 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:compositeBands

变量: `compositeBands`  定义行: 123

```javascript
  122 | 
  123 |     var compositeBands = img.bandNames();
  124 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:nonCorrectBands

变量: `nonCorrectBands`  定义行: 125

```javascript
  124 | 
  125 |     var nonCorrectBands = img.select(compositeBands.removeAll(bandList));
  126 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:geom

变量: `geom`  定义行: 127

```javascript
  126 | 
  127 |     var geom = ee.Geometry(img.get('system:footprint')).bounds().buffer(10000);
  128 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:apply_SCSccorr

变量: `apply_SCSccorr`  定义行: 129

```javascript
  128 | 
  129 |     function apply_SCSccorr(band){
  130 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:band

变量: `band`  定义行: 129

```javascript
  128 | 
  129 |     function apply_SCSccorr(band){
  130 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:method

变量: `method`  定义行: 131

```javascript
  130 | 
  131 |       var method = 'SCSc';
  132 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:out

变量: `out`  定义行: 133

```javascript
  132 | 
  133 |       var out = img_plus_ic_mask2.select('IC', band).reduceRegion({
  134 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:out_a

变量: `out_a`  定义行: 153

```javascript
  152 | 
  153 |       var out_a = ee.Number(out.get('scale'));
  154 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:out_b

变量: `out_b`  定义行: 155

```javascript
  154 | 
  155 |       var out_b = ee.Number(out.get('offset'));
  156 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:out_c

变量: `out_c`  定义行: 157

```javascript
  156 | 
  157 |       var out_c = out_b.divide(out_a);
  158 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:SCSc_output

变量: `SCSc_output`  定义行: 159

```javascript
  158 | 
  159 |       var SCSc_output = img_plus_ic_mask2.expression(
  160 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:img_SCSccorr

变量: `img_SCSccorr`  定义行: 181

```javascript
  180 | 
  181 |     var img_SCSccorr = ee.Image(bandList.map(apply_SCSccorr)).addBands(img_plus_ic.select('IC'));
  182 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:bandList_IC

变量: `bandList_IC`  定义行: 183

```javascript
  182 | 
  183 |     var bandList_IC = ee.List([bandList, 'IC']).flatten();
  184 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:landsat8

变量: `landsat8`  定义行: 195

```javascript
  194 | 
  195 | landsat8 = landsat8
  196 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:landsat8_composite

变量: `landsat8_composite`  定义行: 215

```javascript
  214 | 
  215 | var landsat8_composite = landsat8.qualityMosaic('NDVI').clip(genhe.geometry());
  216 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_7900:A2:mask

变量: `mask`  定义行: 217

```javascript
  216 | 
  217 | var mask = landsat8_composite.select('NDVI').lt(1);
  218 | 
```

状态: ____________  后继使用数: ______  备注: ____________

## A3 调用语句角色

角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，按你的判断给出应属角色）| `undeterminable`

### 行 7（script_7900:A3:141）

```javascript
    7 |  var qa = image.select('pixel_qa');
```

角色: ____________

### 行 9（script_7900:A3:136、script_7900:A3:139、script_7900:A3:140）

```javascript
    9 |  var mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0)
```

角色: ____________

### 行 11（script_7900:A3:137、script_7900:A3:138）

```javascript
   11 |                  .and(qa.bitwiseAnd(cloudsBitMask).eq(0));
```

角色: ____________

### 行 13（script_7900:A3:135）

```javascript
   13 |                   return image.updateMask(mask);
```

角色: ____________

### 行 19（script_7900:A3:133、script_7900:A3:134）

```javascript
   19 |   var ndvi = image.normalizedDifference(['B5', 'B4']).rename('NDVI');
```

角色: ____________

### 行 21（script_7900:A3:132）

```javascript
   21 |   return image.addBands(ndvi);
```

角色: ____________

### 行 27（script_7900:A3:127、script_7900:A3:128）

```javascript
   27 |   var evi =image.expression(
```

角色: ____________

### 行 31（script_7900:A3:131）

```javascript
   31 |       'NIR':image.select('B5'),
```

角色: ____________

### 行 33（script_7900:A3:130）

```javascript
   33 |       'RED':image.select('B4'),
```

角色: ____________

### 行 35（script_7900:A3:129）

```javascript
   35 |       'BLUE':image.select('B2')
```

角色: ____________

### 行 41（script_7900:A3:126）

```javascript
   41 |   return image.addBands(evi)
```

角色: ____________

### 行 47（script_7900:A3:124、script_7900:A3:125）

```javascript
   47 |   var nbr = image.normalizedDifference(['B4','B7']).rename('NBR');
```

角色: ____________

### 行 49（script_7900:A3:123）

```javascript
   49 |   return image.addBands(nbr);
```

角色: ____________

### 行 55（script_7900:A3:122）

```javascript
   55 | var dem = ee.Image("USGS/SRTMGL1_003");
```

角色: ____________

### 行 61（script_7900:A3:114、script_7900:A3:115、script_7900:A3:116、script_7900:A3:117、script_7900:A3:118、script_7900:A3:119、script_7900:A3:120、script_7900:A3:121）

```javascript
   61 |   var SZ_rad = ee.Image.constant(ee.Number(img.get('SOLAR_ZENITH_ANGLE'))).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 63（script_7900:A3:106、script_7900:A3:107、script_7900:A3:108、script_7900:A3:109、script_7900:A3:110、script_7900:A3:111、script_7900:A3:112、script_7900:A3:113）

```javascript
   63 |   var SA_rad = ee.Image.constant(ee.Number(img.get('SOLAR_AZIMUTH_ANGLE')).multiply(3.14159265359).divide(180)).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 65（script_7900:A3:102、script_7900:A3:103、script_7900:A3:104、script_7900:A3:105）

```javascript
   65 |   var slp = ee.Terrain.slope(dem).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 67（script_7900:A3:96、script_7900:A3:97、script_7900:A3:98、script_7900:A3:99、script_7900:A3:100、script_7900:A3:101）

```javascript
   67 |   var slp_rad = ee.Terrain.slope(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 69（script_7900:A3:90、script_7900:A3:91、script_7900:A3:92、script_7900:A3:93、script_7900:A3:94、script_7900:A3:95）

```javascript
   69 |   var asp_rad = ee.Terrain.aspect(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 71（script_7900:A3:89）

```javascript
   71 |   var cosZ = SZ_rad.cos();
```

角色: ____________

### 行 73（script_7900:A3:88）

```javascript
   73 |   var cosS = slp_rad.cos();
```

角色: ____________

### 行 75（script_7900:A3:86）

```javascript
   75 |   var slope_illumination = cosS.expression("cosZ * cosS",
```

角色: ____________

### 行 79（script_7900:A3:87）

```javascript
   79 |                                            'cosS': cosS.select('slope')});
```

角色: ____________

### 行 81（script_7900:A3:85）

```javascript
   81 |   var sinZ = SZ_rad.sin();
```

角色: ____________

### 行 83（script_7900:A3:84）

```javascript
   83 |   var sinS = slp_rad.sin();
```

角色: ____________

### 行 85（script_7900:A3:82、script_7900:A3:83）

```javascript
   85 |   var cosAziDiff = (SA_rad.subtract(asp_rad)).cos();
```

角色: ____________

### 行 87（script_7900:A3:81）

```javascript
   87 |   var aspect_illumination = sinZ.expression("sinZ * sinS * cosAziDiff",
```

角色: ____________

### 行 95（script_7900:A3:80）

```javascript
   95 |   var ic = slope_illumination.add(aspect_illumination);
```

角色: ____________

### 行 97（script_7900:A3:71、script_7900:A3:72、script_7900:A3:73、script_7900:A3:74、script_7900:A3:75、script_7900:A3:76、script_7900:A3:77、script_7900:A3:78、script_7900:A3:79）

```javascript
   97 |   var img_plus_ic = ee.Image(img.addBands(ic.rename('IC')).addBands(cosZ.rename('cosZ')).addBands(cosS.rename('cosS')).addBands(slp.rename('slope')));
```

角色: ____________

### 行 105（script_7900:A3:70）

```javascript
  105 |     var props = img.toDictionary();
```

角色: ____________

### 行 107（script_7900:A3:69）

```javascript
  107 |     var st = img.get('system:time_start');
```

角色: ____________

### 行 111（script_7900:A3:67、script_7900:A3:68）

```javascript
  111 |     var mask1 = img_plus_ic.select('B4').gt(-0.1);
```

角色: ____________

### 行 113（script_7900:A3:59、script_7900:A3:62、script_7900:A3:65、script_7900:A3:66）

```javascript
  113 |     var mask2 = img_plus_ic.select('slope').gte(5)
```

角色: ____________

### 行 115（script_7900:A3:63、script_7900:A3:64）

```javascript
  115 |                             .and(img_plus_ic.select('IC').gte(0))
```

角色: ____________

### 行 117（script_7900:A3:60、script_7900:A3:61）

```javascript
  117 |                             .and(img_plus_ic.select('B4').gt(-0.1));
```

角色: ____________

### 行 119（script_7900:A3:57、script_7900:A3:58）

```javascript
  119 |     var img_plus_ic_mask2 = ee.Image(img_plus_ic.updateMask(mask2));
```

角色: ____________

### 行 123（script_7900:A3:56）

```javascript
  123 |     var compositeBands = img.bandNames();
```

角色: ____________

### 行 125（script_7900:A3:54、script_7900:A3:55）

```javascript
  125 |     var nonCorrectBands = img.select(compositeBands.removeAll(bandList));
```

角色: ____________

### 行 127（script_7900:A3:50、script_7900:A3:51、script_7900:A3:52、script_7900:A3:53）

```javascript
  127 |     var geom = ee.Geometry(img.get('system:footprint')).bounds().buffer(10000);
```

角色: ____________

### 行 133（script_7900:A3:44、script_7900:A3:49）

```javascript
  133 |       var out = img_plus_ic_mask2.select('IC', band).reduceRegion({
```

角色: ____________

### 行 135（script_7900:A3:48）

```javascript
  135 |       reducer: ee.Reducer.linearFit(), // Compute coefficients: a(slope), b(offset), c(b/a)
```

角色: ____________

### 行 137（script_7900:A3:45、script_7900:A3:46、script_7900:A3:47）

```javascript
  137 |       geometry: ee.Geometry(img.geometry().buffer(-5000)), // trim off the outer edges of the image for linear relationship
```

角色: ____________

### 行 147（script_7900:A3:43）

```javascript
  147 |        return img_plus_ic_mask2.select(band);
```

角色: ____________

### 行 153（script_7900:A3:41、script_7900:A3:42）

```javascript
  153 |       var out_a = ee.Number(out.get('scale'));
```

角色: ____________

### 行 155（script_7900:A3:39、script_7900:A3:40）

```javascript
  155 |       var out_b = ee.Number(out.get('offset'));
```

角色: ____________

### 行 157（script_7900:A3:38）

```javascript
  157 |       var out_c = out_b.divide(out_a);
```

角色: ____________

### 行 159（script_7900:A3:33）

```javascript
  159 |       var SCSc_output = img_plus_ic_mask2.expression(
```

角色: ____________

### 行 163（script_7900:A3:37）

```javascript
  163 |         'image': img_plus_ic_mask2.select(band),
```

角色: ____________

### 行 165（script_7900:A3:36）

```javascript
  165 |         'ic': img_plus_ic_mask2.select('IC'),
```

角色: ____________

### 行 167（script_7900:A3:35）

```javascript
  167 |         'cosB': img_plus_ic_mask2.select('cosS'),
```

角色: ____________

### 行 169（script_7900:A3:34）

```javascript
  169 |         'cosZ': img_plus_ic_mask2.select('cosZ'),
```

角色: ____________

### 行 181（script_7900:A3:29、script_7900:A3:30、script_7900:A3:31、script_7900:A3:32）

```javascript
  181 |     var img_SCSccorr = ee.Image(bandList.map(apply_SCSccorr)).addBands(img_plus_ic.select('IC'));
```

角色: ____________

### 行 183（script_7900:A3:27、script_7900:A3:28）

```javascript
  183 |     var bandList_IC = ee.List([bandList, 'IC']).flatten();
```

角色: ____________

### 行 185（script_7900:A3:24、script_7900:A3:25、script_7900:A3:26）

```javascript
  185 |     img_SCSccorr = img_SCSccorr.unmask(img_plus_ic.select(bandList_IC)).select(bandList);
```

角色: ____________

### 行 187（script_7900:A3:21、script_7900:A3:22、script_7900:A3:23）

```javascript
  187 |     return img_SCSccorr.addBands(nonCorrectBands)
```

角色: ____________

### 行 195（script_7900:A3:11、script_7900:A3:12、script_7900:A3:13、script_7900:A3:14、script_7900:A3:15、script_7900:A3:16、script_7900:A3:18、script_7900:A3:20）

```javascript
  195 | landsat8 = landsat8
```

角色: ____________

### 行 199（script_7900:A3:19）

```javascript
  199 | .filterBounds(genhe.geometry())
```

角色: ____________

### 行 201（script_7900:A3:17）

```javascript
  201 | .filter(ee.Filter.lte('CLOUD_COVER',90))
```

角色: ____________

### 行 213（script_7900:A3:10）

```javascript
  213 | print(landsat8);
```

角色: ____________

### 行 215（script_7900:A3:7、script_7900:A3:8、script_7900:A3:9）

```javascript
  215 | var landsat8_composite = landsat8.qualityMosaic('NDVI').clip(genhe.geometry());
```

角色: ____________

### 行 217（script_7900:A3:5、script_7900:A3:6）

```javascript
  217 | var mask = landsat8_composite.select('NDVI').lt(1);
```

角色: ____________

### 行 219（script_7900:A3:4）

```javascript
  219 | landsat8_composite = landsat8_composite.updateMask(mask);
```

角色: ____________

### 行 221（script_7900:A3:3）

```javascript
  221 | Map.addLayer(landsat8_composite);
```

角色: ____________

### 行 223（script_7900:A3:2）

```javascript
  223 | EVI = landsat8_composite.select('EVI');
```

角色: ____________

### 行 225（script_7900:A3:0、script_7900:A3:1）

```javascript
  225 | Export.image.toDrive(EVI,'EVI_2018','','EVI_2018','',genhe.geometry(),30);
```

角色: ____________
