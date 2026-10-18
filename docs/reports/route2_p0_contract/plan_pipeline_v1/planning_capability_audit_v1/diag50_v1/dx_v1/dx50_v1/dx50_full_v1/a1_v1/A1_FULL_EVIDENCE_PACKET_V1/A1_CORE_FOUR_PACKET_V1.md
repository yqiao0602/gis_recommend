# A1 核心四对复核包 V1（补卡解锁正向候选）

owner 指定优先级：T-003#S2 / T-001#S3 / T-025#S5 / T-057#S4。四对能否成立，直接决定『卡片补全是否解锁正确选择』的核心结论。

裁决格式：`步骤 | control | experiment | mechanism`（可直接回复）。

# PCA2-T-003#S2

**请裁问题**：步骤=DN→物理反射率（单一定标，无大气校正附加要求）。v0_5 卡写明 TOA/TOC + 手动参数通路（Landsat 不在内置传感器表）。是否判『正确选择』？（请对照 T-032 的 R1 判定：那一步复合了大气校正，故降为不可判。）

**运行事实**：control: gen_tokens=2048/2048 term=END_MARK; experiment: gen_tokens=1954/2048 term=EOS

注：gen_tokens 达 maxnew 的臂按 R2 记 output_validity=截断；若 SELECT/NOT 行已完整出现，截断只影响尾部列表——请按 R2 裁定。

## 步骤定义

Step 2：Radiometric Correction ｜ purpose: Convert digital numbers to physical reflectance units ｜ input: Raw DN bands from Step 1 ｜ output: Reflectance-corrected image stacks

## 候选集合（Top-10）

1. otb:radiometricindices 2. otb:opticalcalibration 3. grass7:i.albedo 4. qgis:convertgeometrytype 5. gdal:convertformat 6. native:symmetricaldifference 7. native:convertgpsdata 8. otb:pixelvalue 9. qgis:heatmapkerneldensityestimation 10. native:transect

## 所选算子 `otb:opticalcalibration` 双版本卡面

### v0_4（对照臂所见）
```
### otb:opticalcalibration  [otb] OpticalCalibration
accepts: raster
outputs: none documented
params: not documented (no parameter layer for this operator)
```

### v0_5（实验臂所见）
```
### otb:opticalcalibration  [otb] OpticalCalibration
accepts: raster
outputs: out(OutputImage)
params: acqui.day(Int, required, default=1); acqui.month(Int, required, default=1); acqui.gainbias(InputFilename, required, default=None); acqui.solarilluminations(InputFilename, required, default=None) || optional(22): in(InputImage), level(Choice), milli(Bool), clamp(Bool), acqui.minute(Int), acqui.hour(Int), acqui.year(Int), acqui.fluxnormcoeff(Float), acqui.solardistance(Float), acqui.sun.elev(Float), acqui.sun.azim(Float), acqui.view.elev(Float)
description: Perform optical calibration TOA/TOC (Top Of Atmosphere/Top Of Canopy). Supported sensors: QuickBird, Ikonos, WorldView2, Formosat, Spot5, Pleiades, Spot6, Spot7. For other sensors the application also allows providing calibration parameters manually.
```

## 对照臂完整决策段
```
REJECT otb:radiometricindices - lacks documented parameters for performing radiometric correction (e.g., gain/offset application).  
REJECT otb:opticalcalibration - lacks documented parameters for performing radiometric correction (e.g., gain/offset application).  
REJECT grass7:i.albedo - computes albedo from surface reflectance, not from
```

## 实验臂完整决策段
```
SELECT otb:opticalcalibration - Converts raw Digital Numbers (DN) to Top-Of-Atmosphere (TOA) or Top-Of-Canopy (TOC) reflectance values through sensor-specific radiometric calibration, requiring acquisition metadata (date/time, sun/view angles) and sensor-dependent calibration coefficients.
```

---

# PCA2-T-001#S3

**请裁问题**：步骤=把多次获取按时相堆叠（逐像元跨通道统计的前提）。v0_5 卡：'Concatenate a list of images of the same size into a single multi-channel image'，参数 il(InputImageList)。是否判『正确选择』？是否接受『堆叠』由多通道拼接实现？备注：对照臂为截断（think 内已倾向 concatenateimages，但无闭合决策）。

**运行事实**：control: gen_tokens=2048/2048 term=END_MARK; experiment: gen_tokens=2048/2048 term=END_MARK

注：gen_tokens 达 maxnew 的臂按 R2 记 output_validity=截断；若 SELECT/NOT 行已完整出现，截断只影响尾部列表——请按 R2 裁定。

## 步骤定义

Step 3：Time Series Stack Creation ｜ purpose: Combine multiple acquisitions temporally for each pixel location to enable statistical operations ｜ input: Step 2 output ｜ output: Separate stacked datasets for ascending and descending orbits

## 候选集合（Top-10）

1. otb:imagetimeseriesgapfilling 2. otb:imageregression 3. otb:segmentation 4. otb:smallregionsmerging 5. saga:lapseratebasedtemperaturedownscaling 6. saga:traveltimecalculation 7. otb:mosaic 8. saga:lapseratebasedtemperaturedownscalingbulkprocessing 9. saga:superpixelsegmentation 10. otb:concatenateimages

## 所选算子 `otb:concatenateimages` 双版本卡面

### v0_4（对照臂所见）
```
### otb:concatenateimages  [otb] ConcatenateImages
accepts: literal, raster
outputs: none documented
params: not documented (no parameter layer for this operator)
```

### v0_5（实验臂所见）
```
### otb:concatenateimages  [otb] ConcatenateImages
accepts: raster
outputs: out(OutputImage)
params: none required || optional(1): il(InputImageList)
description: Concatenate a list of images of the same size into a single multi-channel image.
```

## 对照臂完整决策段
```
[no closed think - full raw]
<think>
We need to decide if any of the given candidate operators can accomplish the task described in Step 3: "Combine multiple acquisitions temporally for each pixel location to enable statistical operations". The inputs are from Step 2 output, but we don't know what that is. However, the purpose is clear: combine multiple temporal stacks per pixel. This sounds like a time series stacking operation, where we have multiple images over time at each pixel, and we want to stack them into a single multi-layer image or something similar.

Looking at the candidate operators:

- **otb:imagetimeseriesgapfilling**: Accepts a raster, outputs nothing documented. It might be used for gap filling in time series data, but does it actually combine multiple acquisitions? Possibly, but its parameters are undocumented, so we don't know if it can do stacking.

- **otb:imageregression**: Accepts a raster, outputs nothing documented. Might perform regression on an image, not necessarily combining multiple acquisitions.

- **otb:segmentation**: Accepts a raster, outputs nothing documented. Likely performs segmentation, not combination.

- **otb:smallregionsmerging**: Accepts a raster, outputs nothing documented. Probably merges small regions, not relevant.

- **saga:lapseratebasedtemperaturedownscaling**: Outputs two rasters (LORES_SLT and HIRES_T), accepts several rasters including DEM and temperature layers. Not about combining multiple acquisitions temporally.

- **saga:traveltimecalculation**: Outputs travel time minutes raster, accepts destinations, landcover, etc. Not relevant.

- **otb:mosaic**: Accepts literals and rasters, outputs nothing documented. Typically mosaics combine spatially adjacent images, not temporally stacked ones. But maybe it could be used to create a mosaic of multiple dates? However, the description says "combine multiple acquisitions temporally", meaning same locations across different times, not just spatial tiling. A mosaic usually combines non-overlapping areas. So likely not suitable.

- **saga:lapseratebasedtemperaturedownscalingbulkprocessing**: Similar to the previous lapse rate downscaling but bulk processing. Still not about temporal stacking.

- **saga:superpixelsegmentation**: Outputs polygons and superpixels raster. Not about combining multiple acquisitions.

- **otb:concatenateimages**: Accepts literals and rasters, outputs nothing documented. This seems promising because concatenating images could mean joining them along some dimension. In remote sensing, concatenating images often means creating a mult
```

## 实验臂完整决策段
```
SELECT otb:concatenateimages - Combines multiple acquisitions temporally by accepting a list of images of the same size and outputting a single multi-channel image, enabling statistical operations per pixel across channels.
```

---

# PCA2-T-025#S5

**请裁问题**：步骤=把 −25/5 dB 线性拉伸用于可视化。v0_5 卡：直方图均衡实现，含 minmax.manual.min / minmax.manual.max 参数。是否判『正确选择』？（是否存在『直方图均衡≠线性拉伸』的语义差需要扣分？）

**运行事实**：control: gen_tokens=2048/2048 term=CAP_TRUNC; experiment: gen_tokens=2048/2048 term=CAP_TRUNC

注：gen_tokens 达 maxnew 的臂按 R2 记 output_validity=截断；若 SELECT/NOT 行已完整出现，截断只影响尾部列表——请按 R2 裁定。

## 步骤定义

Step 5：Visual Enhancement ｜ purpose: Apply a linear stretch to the mean raster to optimize contrast for visualization, mapping −25 dB to black and 5 dB to white ｜ input: Mean backscatter raster ｜ output: Final raster with enhanced visual appearance

## 候选集合（Top-10）

1. otb:rasterization 2. grass7:i.colors.enhance 3. saga:resampling 4. otb:multiimagesamplingrate 5. native:rastersampling 6. otb:contrastenhancement 7. otb:colormapping 8. saga:colournormalizedbroveysharpening 9. grass7:r.resamp.bspline 10. native:rasterize

## 所选算子 `otb:contrastenhancement` 双版本卡面

### v0_4（对照臂所见）
```
### otb:contrastenhancement  [otb] ContrastEnhancement
accepts: raster
outputs: none documented
params: not documented (no parameter layer for this operator)
```

### v0_5（实验臂所见）
```
### otb:contrastenhancement  [otb] ContrastEnhancement
accepts: raster
outputs: out(OutputImage)
params: none required || optional(18): in(InputImage), bins(Int), hfact(Float), nodata(Float), spatial(Choice), spatial.local.h(Int), spatial.local.w(Int), minmax(Choice), minmax.auto.global(Bool), minmax.manual.min(Float), minmax.manual.max(Float), mode(Choice)
description: This application is the implementation of the histogram equalization algorithm. It can be used to enhance contrast in an image or to reduce the dynamic of the image without losing too much contrast. It offers several options as a nodata value, a contrast limitation factor, a local version of the algorithm and also a mode to equalize the luminance of the image.
```

## 对照臂完整决策段
```
[no closed think - full raw]
<think>
We need to apply a linear stretch to the mean raster to optimize contrast for visualization, mapping −25 dB to black and 5 dB to white. The goal is to enhance the visual appearance of the mean backscatter raster. We have several candidate operators from different software packages (OTB, GRASS7, SAGA, Native). Let's evaluate each based on their descriptions and parameters.

First, understand the task: Linear stretch means we want to remap pixel values so that the minimum value (-25 dB) becomes black (e.g., 0) and the maximum value (5 dB) becomes white (e.g., 255 if using an 8-bit image). This is essentially a min-max normalization or stretching operation. It might involve rescaling the data range to fit within a desired display range.

Now examine each candidate:

1. **otb:rasterization** 
   - Accepts: raster, vector
   - Outputs: none documented
   - Params: not documented
   - Description: Not clear. Since outputs are none documented, it likely doesn't produce a new raster? Possibly converts something else. But our input is a raster, and we need an output raster. So probably not suitable.

2. **grass7:i.colors.enhance**
   - Accepts: raster
   - Outputs: none documented
   - Params: optional(1): strength(literal)
   - Description: Process bands serially (default: run in parallel). No mention of linear stretch or specific mapping. Might be for color enhancement but not necessarily doing the exact min-max scaling we need. Also outputs are none documented, so maybe it modifies in place? Unclear.

3. **saga:resampling**
   - Accepts: literal (but note: params show INPUT as multilayer, required, default=None; OUTPUT as rasterDestination, etc.)
   - Outputs: OUTPUT(outputRaster)
   - Params: many options including scale up/down, target user size, extent, etc.
   - Description: Resampling typically changes resolution, not perform linear stretch. However, some resampling methods like nearest neighbor don't change values, others interpolate. But there is also option to keep type, scale factors, etc. Does it include linear stretch? Probably not explicitly. There is no parameter mentioned for specifying min/max values for stretching. So unlikely.

4. **otb:multiimagesamplingrate**
   - Accepts: none documented
   - Outputs: none documented
   - Params: not documented
   - Likely related to sampling rate between multiple images, not relevant.

5. **native:rastersampling**
   - Accepts: raster, vector
   - Outputs: OUTPUT(outputVector)
   - Params: source, rastercopy, sink, column_prefix
   - Description: Samples raster values u
```

## 实验臂完整决策段
```
SELECT otb:contrastenhancement - Uses minmax.manual.min (-25) and minmax.manual.max (5) to linearly stretch the mean backscatter raster, optimizing contrast for visualization.

REJECT otb:rasterization - Designed to convert vector datasets to raster, not to modify existing raster values.

REJECT grass7:i.colors.enhance - Processes bands serially but lacks explicit parameters for defining a linear stretch between specific min/max values.

REJECT saga:resampling - Changes raster resolution or extent, not pixel values within a defined range.

REJECT otb:multiimagesamplingrate - Computes sampling rates for image sets, does not alter raster content.

REJECT native:rastersampling - Extracts sample values from raster at point locations, outputs a vector.

REJECT otb:colormapping - Maps label images to RGB composites; although it accepts low/high bounds, it is intended for categorical data and produces multiband output.

REJECT saga:colourn
```

---

# PCA2-T-057#S4

**请裁问题**：步骤=对两幅影像计算均方误差（MSD，两个标量输出）。v0_5 卡：'Estimator between 2 images'，ref.in/meas.in 双输入，mse/mae/psnr 输出参数。是否判『正确选择』？（注意卡面 outputs 行写 none documented，mse 以参数形式出现。）

**运行事实**：control: gen_tokens=2048/2048 term=CAP_TRUNC; experiment: gen_tokens=2024/2048 term=END_MARK

注：gen_tokens 达 maxnew 的臂按 R2 记 output_validity=截断；若 SELECT/NOT 行已完整出现，截断只影响尾部列表——请按 R2 裁定。

## 步骤定义

Step 4：Compute Mean Squared Differences ｜ purpose: Quantitatively measure the pixel-wise deviation of each filtered version from the original ｜ input: Original image (from Step 1), Focal Median result (Step 2), EDS result (Step 3) ｜ output: Two scalar values (Focal Median MSD, EDS MSD).

## 候选集合（Top-10）

1. native:filterbygeometry 2. otb:pixelvalue 3. otb:compareimages 4. grass7:r.stats.quantile.rast 5. grass7:r.resamp.stats 6. grass7:v.rast.stats 7. saga:superpixelsegmentation 8. grass7:r.stats.quantile.out 9. saga:resamplingfilter 10. qgis:meanandstandarddeviationplot

## 所选算子 `otb:compareimages` 双版本卡面

### v0_4（对照臂所见）
```
### otb:compareimages  [otb] CompareImages
accepts: raster
outputs: none documented
params: not documented (no parameter layer for this operator)
```

### v0_5（实验臂所见）
```
### otb:compareimages  [otb] CompareImages
accepts: raster
outputs: none documented
params: none required || optional(12): ref.in(InputImage), ref.channel(Int), meas.in(InputImage), meas.channel(Int), roi.startx(Int), roi.starty(Int), roi.sizex(Int), roi.sizey(Int), mse(Float), mae(Float), psnr(Float), count(Float)
description: Estimator between 2 images.
```

## 对照臂完整决策段
```
[no closed think - full raw]
<think>
We need to compute mean squared differences between two images: the original image and two filtered versions (focal median and EDS). The purpose is to quantitatively measure pixel-wise deviation. We have an original image and two results as inputs. We need to produce two scalar values (MSD for each comparison). 

Looking at the candidate operators:

- `native:filterbygeometry`: filters vector geometries by type. Not relevant because we are dealing with raster images. Reject.

- `otb:pixelvalue`: accepts raster but outputs nothing documented. It might be used to get pixel values? But we need to compare two rasters and compute a statistic over all pixels. This operator doesn't seem designed for that. Possibly could extract pixel values into something else? But description says "PixelValue", maybe it extracts pixel value? However, it has no parameters listed, so likely just returns some internal representation. Probably insufficient. Reject.

- `otb:compareimages`: compares two images. Accepts raster, outputs nothing documented. Could potentially compute difference or similarity metrics? But since outputs are undocumented, we don't know if it produces a scalar like MSD. Might be able to do something, but without knowing its behavior, we cannot assume it computes MSD. So reject.

- `grass7:r.stats.quantile.rast`: calculates quantiles of a raster. Accepts raster, outputs nothing documented. Could give us summary statistics like mean, variance, etc., but not directly the mean squared difference between two rasters. To compute MSD, we'd need per-pixel differences first. This operator works on a single raster, not comparing two. Reject.

- `grass7:r.resamp.stats`: resamples raster to coarser grid using aggregation. Accepts raster, outputs raster. Parameters include method and quantile. Could aggregate pixel values, e.g., average, sum, min, max, etc. If we set method appropriately, we could combine two rasters? Actually, looking at params: input(literal, required, default=None); output(literal, required, default=None) || optional(2): method(literal), quantile(literal). Description: Resamples raster map layers to a coarser grid using aggregation. It seems to take one input raster and aggregates it. How does it handle multiple rasters? Possibly it takes multiple input rasters? The param "input" is described as "literal, required, default=None". That suggests it expects a literal string, perhaps specifying multiple files? In GRASS GIS, many commands accept multiple file names separated by spaces. For example, `r.resamp.stats` can
```

## 实验臂完整决策段
```
SELECT otb:compareimages - Computes mean squared error between two images via its 'mse' output port; applying it with original image as reference and focal median/EED result as measurement gives the respective MSD values.

REJECT native:filterbygeometry - Operates on vector geometries, not raster pixel values, and cannot compute statistical differences between images.

REJECT otb:pixelvalue - Retrieves a single pixel value rather than comparing two images or averaging differences.

REJECT grass7:r.stats.quantile.rast - Computes quantiles of a single raster, not pairwise differences between two images.

REJECT grass7:r.resamp.stats - Aggregates raster values to a coarser grid but does not compare two images or compute MSE.

REJECT grass7:v.rast.stats - Calculates statistics from one raster map, unable to handle two-image comparison.

REJECT saga:superpixelsegmentation - Performs segmentation into regions, not designed for pixel-wise difference calculation.

REJECT grass7:r.stats.quantile.out - Computes quantiles of a single raster, lacking multi-image comparison capability.

REJECT saga:resamplingfilter - Applies low-pass/high-pass filtering, not suited for measuring deviations between images.

REJECT qgis:meanandstandarddeviationplot - Requires tabular data with named fields, not raw pixel arrays for direct MSE computation.
```

---
