# 标注单 script_35821

源码 SHA-256: `17d778dedb2835235c75536dec560ba9131fd4819126f6511abcf926596b9e0f`
完整源码路径: `.tmp_gee_batch13_sources/Data/data40000/script_35821.txt`

## A1 未声明候选变量（三分类裁定）

分类: `external_prebinding`（有外部证据：require/注释/平台预绑定名）| `missing_definition`（应有定义缺失/脚本缺陷）| `indeterminable`（证据不足）| `undeterminable`（无法裁定）

### script_35821:A1:geometry

变量: `geometry`  使用行: [173]  证据线索: （无）

```javascript
  171 | var collection = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR")
  172 | 
  173 | 　　　　　　　　　.filterBounds(geometry)
  174 | 
  175 |                    .filterDate("2018-01-01","2018-12-31")
```

裁定: ______________________  备注: ____________

## A2 声明变量使用分类

状态: `unconsumed`（0 后继使用）| `presentation_only`（仅展示）| `analysis_chain`（进入分析/导出链）| `undeterminable`；同时给出后继使用计数

### script_35821:A2:scale

变量: `scale`  定义行: 1

```javascript
    1 | var scale = 300;
    2 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:dem

变量: `dem`  定义行: 3

```javascript
    2 | 
    3 | var dem = ee.Image('USGS/SRTMGL1_003');
    4 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:degree2radian

变量: `degree2radian`  定义行: 5

```javascript
    4 | 
    5 | var degree2radian = 0.01745;
    6 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:terrainCorrection

变量: `terrainCorrection`  定义行: 7

```javascript
    6 | 
    7 | var terrainCorrection = function(collection) {
    8 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:img

变量: `img`  定义行: 17

```javascript
   16 | 
   17 |   function illuminationCondition(img){
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:illuminationCondition

变量: `illuminationCondition`  定义行: 17

```javascript
   16 | 
   17 |   function illuminationCondition(img){
   18 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:SZ_rad

变量: `SZ_rad`  定义行: 19

```javascript
   18 | 
   19 |   var SZ_rad = ee.Image.constant(ee.Number(img.get('SOLAR_ZENITH_ANGLE'))).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
   20 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:SA_rad

变量: `SA_rad`  定义行: 21

```javascript
   20 | 
   21 |   var SA_rad = ee.Image.constant(ee.Number(img.get('SOLAR_AZIMUTH_ANGLE')).multiply(3.14159265359).divide(180)).clip(img.geometry().buffer(10000));
   22 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:slp

变量: `slp`  定义行: 23

```javascript
   22 | 
   23 |   var slp = ee.Terrain.slope(dem).clip(img.geometry().buffer(10000));
   24 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:slp_rad

变量: `slp_rad`  定义行: 25

```javascript
   24 | 
   25 |   var slp_rad = ee.Terrain.slope(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
   26 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:asp_rad

变量: `asp_rad`  定义行: 27

```javascript
   26 | 
   27 |   var asp_rad = ee.Terrain.aspect(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
   28 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:cosZ

变量: `cosZ`  定义行: 29

```javascript
   28 | 
   29 |   var cosZ = SZ_rad.cos();
   30 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:cosS

变量: `cosS`  定义行: 31

```javascript
   30 | 
   31 |   var cosS = slp_rad.cos();
   32 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:slope_illumination

变量: `slope_illumination`  定义行: 33

```javascript
   32 | 
   33 |   var slope_illumination = cosS.expression("cosZ * cosS",
   34 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:sinZ

变量: `sinZ`  定义行: 39

```javascript
   38 | 
   39 |   var sinZ = SZ_rad.sin();
   40 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:sinS

变量: `sinS`  定义行: 41

```javascript
   40 | 
   41 |   var sinS = slp_rad.sin();
   42 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:cosAziDiff

变量: `cosAziDiff`  定义行: 43

```javascript
   42 | 
   43 |   var cosAziDiff = (SA_rad.subtract(asp_rad)).cos();
   44 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:aspect_illumination

变量: `aspect_illumination`  定义行: 45

```javascript
   44 | 
   45 |   var aspect_illumination = sinZ.expression("sinZ * sinS * cosAziDiff",
   46 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:ic

变量: `ic`  定义行: 53

```javascript
   52 | 
   53 |   var ic = slope_illumination.add(aspect_illumination);
   54 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:illuminationCorrection

变量: `illuminationCorrection`  定义行: 61

```javascript
   60 | 
   61 | function illuminationCorrection(img){
   62 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:props

变量: `props`  定义行: 63

```javascript
   62 | 
   63 |     var props = img.toDictionary();
   64 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:st

变量: `st`  定义行: 65

```javascript
   64 | 
   65 |     var st = img.get('system:time_start');
   66 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:img_plus_ic

变量: `img_plus_ic`  定义行: 67

```javascript
   66 | 
   67 |     var img_plus_ic = img;
   68 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:mask1

变量: `mask1`  定义行: 69

```javascript
   68 | 
   69 |     var mask1 = img_plus_ic.select('nir').gt(-0.1);
   70 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:mask2

变量: `mask2`  定义行: 71

```javascript
   70 | 
   71 |     var mask2 = img_plus_ic.select('slope').gte(5)
   72 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:img_plus_ic_mask2

变量: `img_plus_ic_mask2`  定义行: 77

```javascript
   76 | 
   77 |     var img_plus_ic_mask2 = ee.Image(img_plus_ic.updateMask(mask2));
   78 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:bandList

变量: `bandList`  定义行: 79

```javascript
   78 | 
   79 |     var bandList = ['blue','green','red','nir','swir1','swir2'];
   80 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:compositeBands

变量: `compositeBands`  定义行: 81

```javascript
   80 | 
   81 |     var compositeBands = img.bandNames();
   82 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:nonCorrectBands

变量: `nonCorrectBands`  定义行: 83

```javascript
   82 | 
   83 |     var nonCorrectBands = img.select(compositeBands.removeAll(bandList));
   84 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:geom

变量: `geom`  定义行: 85

```javascript
   84 | 
   85 |     var geom = ee.Geometry(img.get('system:footprint')).bounds().buffer(10000);
   86 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:apply_SCSccorr

变量: `apply_SCSccorr`  定义行: 87

```javascript
   86 | 
   87 |     function apply_SCSccorr(band){
   88 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:band

变量: `band`  定义行: 87

```javascript
   86 | 
   87 |     function apply_SCSccorr(band){
   88 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:method

变量: `method`  定义行: 89

```javascript
   88 | 
   89 |       var method = 'SCSc';
   90 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:out

变量: `out`  定义行: 91

```javascript
   90 | 
   91 |       var out = img_plus_ic_mask2.select('IC', band).reduceRegion({
   92 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:out_a

变量: `out_a`  定义行: 111

```javascript
  110 | 
  111 |       var out_a = ee.Number(out.get('scale'));
  112 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:out_b

变量: `out_b`  定义行: 113

```javascript
  112 | 
  113 |       var out_b = ee.Number(out.get('offset'));
  114 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:out_c

变量: `out_c`  定义行: 115

```javascript
  114 | 
  115 |       var out_c = out_b.divide(out_a);
  116 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:SCSc_output

变量: `SCSc_output`  定义行: 117

```javascript
  116 | 
  117 |       var SCSc_output = img_plus_ic_mask2.expression(
  118 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:img_SCSccorr

变量: `img_SCSccorr`  定义行: 139

```javascript
  138 | 
  139 |     var img_SCSccorr = ee.Image(bandList.map(apply_SCSccorr)).addBands(img_plus_ic.select('IC'));
  140 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:bandList_IC

变量: `bandList_IC`  定义行: 141

```javascript
  140 | 
  141 |     var bandList_IC = ee.List([bandList, 'IC']).flatten();
  142 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:cloudMasking

变量: `cloudMasking`  定义行: 153

```javascript
  152 | 
  153 | function cloudMasking(img){
  154 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:qa

变量: `qa`  定义行: 155

```javascript
  154 | 
  155 |   var qa= img.select("pixel_qa");
  156 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:aero

变量: `aero`  定义行: 157

```javascript
  156 | 
  157 |   var aero = img.select("sr_aerosol");
  158 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:mask

变量: `mask`  定义行: 159

```javascript
  158 | 
  159 |   var mask = qa.bitwiseAnd(1<<3).eq(0).and(qa.bitwiseAnd(1<<5).eq(0)).and(qa.bitwiseAnd(1<<2).eq(0))
  160 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:inBands

变量: `inBands`  定义行: 167

```javascript
  166 | 
  167 | var inBands = ee.List(['B1','B2','B3','B4','B5','B6','B7']);
  168 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:outBands

变量: `outBands`  定义行: 169

```javascript
  168 | 
  169 | var outBands = ee.List(['aero','blue','green','red','nir','swir1','swir2']);
  170 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:collection

变量: `collection`  定义行: 171

```javascript
  170 | 
  171 | var collection = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR")
  172 | 
```

状态: ____________  后继使用数: ______  备注: ____________

### script_35821:A2:image

变量: `image`  定义行: 181

```javascript
  180 | 
  181 | var image = ee.Image(collection.median());
  182 | 
```

状态: ____________  后继使用数: ______  备注: ____________

## A3 调用语句角色

角色: `presentation` | `export` | `analysis` | `unknown`（未知 API，按你的判断给出应属角色）| `undeterminable`

### 行 3（script_35821:A3:132）

```javascript
    3 | var dem = ee.Image('USGS/SRTMGL1_003');
```

角色: ____________

### 行 9（script_35821:A3:131）

```javascript
    9 |   collection = collection.map(illuminationCondition);
```

角色: ____________

### 行 11（script_35821:A3:130）

```javascript
   11 |   collection = collection.map(illuminationCorrection);
```

角色: ____________

### 行 19（script_35821:A3:122、script_35821:A3:123、script_35821:A3:124、script_35821:A3:125、script_35821:A3:126、script_35821:A3:127、script_35821:A3:128、script_35821:A3:129）

```javascript
   19 |   var SZ_rad = ee.Image.constant(ee.Number(img.get('SOLAR_ZENITH_ANGLE'))).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 21（script_35821:A3:114、script_35821:A3:115、script_35821:A3:116、script_35821:A3:117、script_35821:A3:118、script_35821:A3:119、script_35821:A3:120、script_35821:A3:121）

```javascript
   21 |   var SA_rad = ee.Image.constant(ee.Number(img.get('SOLAR_AZIMUTH_ANGLE')).multiply(3.14159265359).divide(180)).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 23（script_35821:A3:110、script_35821:A3:111、script_35821:A3:112、script_35821:A3:113）

```javascript
   23 |   var slp = ee.Terrain.slope(dem).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 25（script_35821:A3:104、script_35821:A3:105、script_35821:A3:106、script_35821:A3:107、script_35821:A3:108、script_35821:A3:109）

```javascript
   25 |   var slp_rad = ee.Terrain.slope(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 27（script_35821:A3:98、script_35821:A3:99、script_35821:A3:100、script_35821:A3:101、script_35821:A3:102、script_35821:A3:103）

```javascript
   27 |   var asp_rad = ee.Terrain.aspect(dem).multiply(3.14159265359).divide(180).clip(img.geometry().buffer(10000));
```

角色: ____________

### 行 29（script_35821:A3:97）

```javascript
   29 |   var cosZ = SZ_rad.cos();
```

角色: ____________

### 行 31（script_35821:A3:96）

```javascript
   31 |   var cosS = slp_rad.cos();
```

角色: ____________

### 行 33（script_35821:A3:94）

```javascript
   33 |   var slope_illumination = cosS.expression("cosZ * cosS",
```

角色: ____________

### 行 37（script_35821:A3:95）

```javascript
   37 |                                            'cosS': cosS.select('slope')});
```

角色: ____________

### 行 39（script_35821:A3:93）

```javascript
   39 |   var sinZ = SZ_rad.sin();
```

角色: ____________

### 行 41（script_35821:A3:92）

```javascript
   41 |   var sinS = slp_rad.sin();
```

角色: ____________

### 行 43（script_35821:A3:90、script_35821:A3:91）

```javascript
   43 |   var cosAziDiff = (SA_rad.subtract(asp_rad)).cos();
```

角色: ____________

### 行 45（script_35821:A3:89）

```javascript
   45 |   var aspect_illumination = sinZ.expression("sinZ * sinS * cosAziDiff",
```

角色: ____________

### 行 53（script_35821:A3:88）

```javascript
   53 |   var ic = slope_illumination.add(aspect_illumination);
```

角色: ____________

### 行 55（script_35821:A3:79、script_35821:A3:80、script_35821:A3:81、script_35821:A3:82、script_35821:A3:83、script_35821:A3:84、script_35821:A3:85、script_35821:A3:86、script_35821:A3:87）

```javascript
   55 |   var img_plus_ic = ee.Image(img.addBands(ic.rename('IC')).addBands(cosZ.rename('cosZ')).addBands(cosS.rename('cosS')).addBands(slp.rename('slope')));
```

角色: ____________

### 行 63（script_35821:A3:78）

```javascript
   63 |     var props = img.toDictionary();
```

角色: ____________

### 行 65（script_35821:A3:77）

```javascript
   65 |     var st = img.get('system:time_start');
```

角色: ____________

### 行 69（script_35821:A3:75、script_35821:A3:76）

```javascript
   69 |     var mask1 = img_plus_ic.select('nir').gt(-0.1);
```

角色: ____________

### 行 71（script_35821:A3:67、script_35821:A3:70、script_35821:A3:73、script_35821:A3:74）

```javascript
   71 |     var mask2 = img_plus_ic.select('slope').gte(5)
```

角色: ____________

### 行 73（script_35821:A3:71、script_35821:A3:72）

```javascript
   73 |                             .and(img_plus_ic.select('IC').gte(0))
```

角色: ____________

### 行 75（script_35821:A3:68、script_35821:A3:69）

```javascript
   75 |                             .and(img_plus_ic.select('nir').gt(-0.1));
```

角色: ____________

### 行 77（script_35821:A3:65、script_35821:A3:66）

```javascript
   77 |     var img_plus_ic_mask2 = ee.Image(img_plus_ic.updateMask(mask2));
```

角色: ____________

### 行 81（script_35821:A3:64）

```javascript
   81 |     var compositeBands = img.bandNames();
```

角色: ____________

### 行 83（script_35821:A3:62、script_35821:A3:63）

```javascript
   83 |     var nonCorrectBands = img.select(compositeBands.removeAll(bandList));
```

角色: ____________

### 行 85（script_35821:A3:58、script_35821:A3:59、script_35821:A3:60、script_35821:A3:61）

```javascript
   85 |     var geom = ee.Geometry(img.get('system:footprint')).bounds().buffer(10000);
```

角色: ____________

### 行 91（script_35821:A3:52、script_35821:A3:57）

```javascript
   91 |       var out = img_plus_ic_mask2.select('IC', band).reduceRegion({
```

角色: ____________

### 行 93（script_35821:A3:56）

```javascript
   93 |       reducer: ee.Reducer.linearFit(), // Compute coefficients: a(slope), b(offset), c(b/a)
```

角色: ____________

### 行 95（script_35821:A3:53、script_35821:A3:54、script_35821:A3:55）

```javascript
   95 |       geometry: ee.Geometry(img.geometry().buffer(-5000)), // trim off the outer edges of the image for linear relationship
```

角色: ____________

### 行 105（script_35821:A3:51）

```javascript
  105 |        return img_plus_ic_mask2.select(band);
```

角色: ____________

### 行 111（script_35821:A3:49、script_35821:A3:50）

```javascript
  111 |       var out_a = ee.Number(out.get('scale'));
```

角色: ____________

### 行 113（script_35821:A3:47、script_35821:A3:48）

```javascript
  113 |       var out_b = ee.Number(out.get('offset'));
```

角色: ____________

### 行 115（script_35821:A3:46）

```javascript
  115 |       var out_c = out_b.divide(out_a);
```

角色: ____________

### 行 117（script_35821:A3:41）

```javascript
  117 |       var SCSc_output = img_plus_ic_mask2.expression(
```

角色: ____________

### 行 121（script_35821:A3:45）

```javascript
  121 |         'image': img_plus_ic_mask2.select(band),
```

角色: ____________

### 行 123（script_35821:A3:44）

```javascript
  123 |         'ic': img_plus_ic_mask2.select('IC'),
```

角色: ____________

### 行 125（script_35821:A3:43）

```javascript
  125 |         'cosB': img_plus_ic_mask2.select('cosS'),
```

角色: ____________

### 行 127（script_35821:A3:42）

```javascript
  127 |         'cosZ': img_plus_ic_mask2.select('cosZ'),
```

角色: ____________

### 行 139（script_35821:A3:37、script_35821:A3:38、script_35821:A3:39、script_35821:A3:40）

```javascript
  139 |     var img_SCSccorr = ee.Image(bandList.map(apply_SCSccorr)).addBands(img_plus_ic.select('IC'));
```

角色: ____________

### 行 141（script_35821:A3:35、script_35821:A3:36）

```javascript
  141 |     var bandList_IC = ee.List([bandList, 'IC']).flatten();
```

角色: ____________

### 行 143（script_35821:A3:32、script_35821:A3:33、script_35821:A3:34）

```javascript
  143 |     img_SCSccorr = img_SCSccorr.unmask(img_plus_ic.select(bandList_IC)).select(bandList);
```

角色: ____________

### 行 145（script_35821:A3:29、script_35821:A3:30、script_35821:A3:31）

```javascript
  145 |     return img_SCSccorr.addBands(nonCorrectBands)
```

角色: ____________

### 行 155（script_35821:A3:28）

```javascript
  155 |   var qa= img.select("pixel_qa");
```

角色: ____________

### 行 157（script_35821:A3:27）

```javascript
  157 |   var aero = img.select("sr_aerosol");
```

角色: ____________

### 行 159（script_35821:A3:13、script_35821:A3:16、script_35821:A3:19、script_35821:A3:20、script_35821:A3:21、script_35821:A3:22、script_35821:A3:23、script_35821:A3:24、script_35821:A3:25、script_35821:A3:26）

```javascript
  159 |   var mask = qa.bitwiseAnd(1<<3).eq(0).and(qa.bitwiseAnd(1<<5).eq(0)).and(qa.bitwiseAnd(1<<2).eq(0))
```

角色: ____________

### 行 161（script_35821:A3:14、script_35821:A3:15、script_35821:A3:17、script_35821:A3:18）

```javascript
  161 |               .and(qa.bitwiseAnd(1<<8-9).eq(0)).and(aero.bitwiseAnd(1<<6-7).eq(0));
```

角色: ____________

### 行 163（script_35821:A3:12）

```javascript
  163 |   return img.updateMask(mask);
```

角色: ____________

### 行 167（script_35821:A3:11）

```javascript
  167 | var inBands = ee.List(['B1','B2','B3','B4','B5','B6','B7']);
```

角色: ____________

### 行 169（script_35821:A3:10）

```javascript
  169 | var outBands = ee.List(['aero','blue','green','red','nir','swir1','swir2']);
```

角色: ____________

### 行 171（script_35821:A3:5、script_35821:A3:6、script_35821:A3:7、script_35821:A3:8、script_35821:A3:9）

```javascript
  171 | var collection = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR")
```

角色: ____________

### 行 181（script_35821:A3:3、script_35821:A3:4）

```javascript
  181 | var image = ee.Image(collection.median());
```

角色: ____________

### 行 183（script_35821:A3:2）

```javascript
  183 | Map.addLayer(image,{ bands:  'swir1,nir,red',min: 0, max: 4500},'original');
```

角色: ____________

### 行 185（script_35821:A3:1）

```javascript
  185 | Map.setCenter(117.40135832592352,5.379874448394949, 8);
```

角色: ____________

### 行 187（script_35821:A3:0）

```javascript
  187 |   Export.image.toCloudStorage({
```

角色: ____________
