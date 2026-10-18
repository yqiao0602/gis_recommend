# A1 变化样本复核包 V1（预注册优先序）

决策不一致或选择集合变化的对：52。判读口径：对照 v0_5 卡面（changed_oids 所列算子）判断每臂决策是否被卡证据支持。

## [P1] PCA2-T-009#S3 — ABST → POS
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:spectralangleclassification, otb:classificationmapregularization, otb:traindimensionalityreduction
- 对照臂选择：(无) ｜ 实验臂选择：['saga:multibandvariation']
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
Because none of the provided operators support calculating vegetation indices (e.g., NDVI, NDSI) which require arithmetic combinations (ratio/difference) of specific bands; available operators only offer classification, buffering, recasting, or simple band-wise statistics.
```
### 实验臂 (v0_5) 决策摘录

```
SELECT saga:multibandvariation - It computes statistical variations (mean, std dev, difference) across specified bands, generating new derived feature rasters from multi-band input.
```

## [P1] PCA2-T-009#S6 — ABST → POS
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:trainvectorclassifier, otb:trainimagesclassifier, otb:vectorclassifier, otb:trainregression, otb:classificationmapregularization, otb:fusionofclassifications, otb:trainvectorregression, otb:imageclassifier
- 对照臂选择：(无) ｜ 实验臂选择：['otb:trainvectorclassifier']
### 对照臂 (v0_4) 决策摘录
```
REJECT otb:trainvectorclassifier - no parameters documented, cannot confirm CART implementation.  
REJECT otb:trainimagesclassifier - no parameters documented, cannot confirm CART implementation.  
REJECT otb:vectorclassifier - no parameters documented, output not specified.  
REJECT saga:fuzzylandformelementclassification - specialized for landform element classification, not general CART.  
REJECT otb:trainregression - intended for regression tasks, not classification.  
REJECT otb:classificationmapregularization - regularizes existing classifications, does not train new models.  
REJECT otb:fusionofclassifications - fuses multiple classifications, does not train new models.  
REJECT otb:t…
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:trainvectorclassifier - It can train a CART classifier from the vector training data (using io.vd port) and the engineered features (via feat field parameter).
```

## [P1] PCA2-T-042#S1 — ABST → NODEC
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:trainimagesregression, otb:imageregression, otb:trainimagesclassifier
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the candidate operators provide functionality to retrieve or acquire precipitation imagery from an external dataset such as GPM IMERG; all listed operators assume pre-existing local raster or vector files as input.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P1] PCA2-T-056#S5 — ABST → NODEC
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:spectralangleclassification, otb:trainvectorclassifier
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
Because none of the candidate operators explicitly implement a Random Forest classifier; the closest candidate (saga:supervisedclassificationforrasters) has a generic METHOD enum whose specific algorithms are undocumented, and thus cannot be guaranteed to train a Random Forest model.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P1] PCA2-T-056#S6 — ABST → POS
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:trainimagesclassifier
- 对照臂选择：(无) ｜ 实验臂选择：['saga:supervisedclassificationforrasters']
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the listed operators support applying a pre-trained machine learning model (such as a Random Forest) to a raster; they either require training data, perform unsupervised tasks, or serve unrelated purposes.
```
### 实验臂 (v0_5) 决策摘录
```
SELECT saga:supervisedclassificationforrasters - Loads the trained Random Forest model via FILE_LOAD and applies it to the preprocessed mosaic raster through the TRAINING source, producing the classified land cover raster at the CLASSES output port.
```

## [P1] PCA2-T-083#S6 — ABST → NODEC
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:trainimagesclassifier, otb:trainvectorclassifier, otb:traindimensionalityreduction, otb:fusionofclassifications, otb:trainvectorregression, otb:trainimagesregression
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the provided operators are capable of training a Random Forest model from a vector file; all either operate on raster/vector data differently or lack explicit support for such a task.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P1] PCA2-T-083#S7 — POS → POS
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:trainimagesclassifier, otb:imageclassifier, otb:spectralangleclassification, otb:trainimagesregression, otb:classificationmapregularization, otb:imagedimensionalityreduction
- 对照臂选择：['saga:supervisedclassificationforrasters'] ｜ 实验臂选择：['otb:imageclassifier']
### 对照臂 (v0_4) 决策摘录
```
SELECT saga:supervisedclassificationforrasters - applies a trained model to a multilayer grid of raster predictors to generate a classified raster via the CLASSES output port, supporting both discrete class predictions and continuous probability scores based on method and threshold parameters.
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:imageclassifier - Applies a trained model to an input image containing stacked raster predictors to generate a classified raster output.
```

## [P1] PCA2-T-084#S2 — NODEC → ABST
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:classificationmapregularization, otb:morphologicalclassification, otb:imageclassifier
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP
because none of the provided operators perform direct threshold-based reclassification of a continuous aridity index raster into discrete aridity classes; they either require additional input layers (e.g., temperature and precipitation separately) or serve different purposes (albedo, wetness, evapotranspiration, regularization, etc.).
```

## [P1] PCA2-T-084#S5 — ABST → NODEC
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:smallregionsmerging, otb:polygonclassstatistics, otb:somclassification, otb:kmeansclassification
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because no candidate operator can conditionally override one raster based on another to produce two separate output masks (cold_land_mask and cold_ocean_mask) while handling the interaction between base_aridity_classes and temp_severity_raster.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P1] PCA2-T-090#S4 — NODEC → OOC
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:trainimagesclassifier, otb:imageclassifier
- 对照臂选择：(无) ｜ 实验臂选择：['otb:ImageClassifier']
### 对照臂 (v0_4) 决策摘录
```
REJECT grass7:r.watershed - calculates hydrological parameters, not applicable to applying a trained model for classification.  
REJECT saga:
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:ImageClassifier - Applies a trained model file to an input image (feature stack) to produce a classified raster output.
```

## [P1] PCA2-T-092#S9 — NODEC → ABST
- 优先理由：T-009 family / classifier-training card changed
- 卡面变化算子：otb:smoothing, otb:classificationmapregularization, otb:trainimagesclassifier
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: "Post-Classification Smoothing & Validation". The purpose is to reduce speckle noise and assess accuracy against reference data. Inputs: Step 8 output (classified ras
[tail] ctionality, I'm leaning towards rejecting unless we know it can smooth.
- **otb:smoothing**: Select because it accepts a raster and presumably smooths it. Output is unspecified but likely a smoothed raster.
- **otb:classificationmapregularization**: Select because it regularizes a classification map
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because no candidate operator provides both speckle reduction for a classified raster and generation of a validation confusion matrix/accuracy report from reference data.
```

## [P3] PCA2-T-001#S3 — NODEC → POS
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:imageregression, otb:segmentation, otb:smallregionsmerging, otb:mosaic, otb:concatenateimages
- 对照臂选择：(无) ｜ 实验臂选择：['otb:concatenateimages']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to decide if any of the given candidate operators can accomplish the task described in Step 3: "Combine multiple acquisitions temporally for each pixel location to enable statistical o
[tail] kprocessing: Same as #5, bulk version. Reject.

9. saga:superpixelsegmentation: Produces superpixels, not combining multiple acquisitions. Reject.

10. otb:concatenateimages: As discussed, seems capable of concatenating images, which could include temporal stacking. Select.

So only one candidate is
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:concatenateimages - Combines multiple acquisitions temporally by accepting a list of images of the same size and outputting a single multi-channel image, enabling statistical operations per pixel across channels.
```

## [P3] PCA2-T-001#S4 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:sarpolarmatrixconvert, otb:sardecompositions, otb:sarcalibration, otb:sarburstextraction, otb:multiimagesamplingrate
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the provided operators offer dedicated speckle filtering capabilities (such as Lee, Frost, or Kuan filters) that reduce coherent noise while preserving features in SAR imagery; all listed operators focus on calibration, mosaicking, statistical summaries, or frequency-domain filtering without adaptive speckle suppression.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: "Speckle Filtering". The purpose is to reduce coherent noise inherent in SAR imagery while preserving features. Input is from Step 3 output, and output should be filt
[tail] ckle filter, but it does transform the data. However, the step is about reducing noise, not transforming the representation.

 Conclusion: No operator fits.

 However, let's consider if any of these operators could be misinterpreted as performing speckle filtering. For instance, the `saga:resampling
```

## [P3] PCA2-T-001#S5 — NODEC → ABST
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:imageregression, otb:multiimagesamplingrate
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: "Median Compositing". The purpose is to generate a single representative image by taking the median value across the filtered time stack for each pixel. Input is from
[tail] ers to specify the quantile level, and others are unrelated.

Now, writing the exact lines:

For each candidate, I'll write a REJECT statement.

List of candidates in order:

1. saga:superpixelsegmentation
2. grass7:i.image.mosaic
3. gdal:viewshed
4. otb:imageregression
5. saga:imcorrfeaturetracking
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP
because no candidate operator provides a function to compute the median across multiple input images (time stack) per pixel.
```

## [P3] PCA2-T-001#S6 — POS → ABST
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:mosaic
- 对照臂选择：['saga:mosaicking'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT saga:mosaicking - uses FILE_LIST to combine multiple raster inputs into a single output raster grid via TARGET_OUT_GRID, producing the final mosaic asset.
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP
Because none of the candidate operators are capable of formatting existing mosaics into required asset deliverables; they primarily perform mosaicking operations or export vector data.
```

## [P3] PCA2-T-025#S5 — NODEC → POS
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:rasterization, otb:multiimagesamplingrate, otb:contrastenhancement, otb:colormapping
- 对照臂选择：(无) ｜ 实验臂选择：['otb:contrastenhancement']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to apply a linear stretch to the mean raster to optimize contrast for visualization, mapping −25 dB to black and 5 dB to white. The goal is to enhance the visual appearance of the mean
[tail]  step and briefly how or why not.

So let's evaluate each candidate systematically:

1. **otb:rasterization**: Reject because it does not produce a raster output (none documented) and is likely for converting vectors to rasters, not for enhancing contrast.

2. **grass7:i.colors.enhance**: Select? Or
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:contrastenhancement - Uses minmax.manual.min (-25) and minmax.manual.max (5) to linearly stretch the mean backscatter raster, optimizing contrast for visualization.

REJECT otb:rasterization - Designed to convert vector datasets to raster, not to modify existing raster values.

REJECT grass7:i.colors.enhance - Processes bands serially but lacks explicit parameters for defining a linear stretch between specific min/max values.

REJECT saga:resampling - Changes raster resolution or extent, not pixel values within a defined range.

REJECT otb:multiimagesamplingrate - Computes sampling rates for image sets, does not alter raster content.

REJECT native:rastersampling - Extracts sample…
```

## [P3] PCA2-T-046#S4 — POS → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:concatenatevectordata
- 对照臂选择：['native:joinattributestable'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT native:joinattributestable - Joins the original soil points (INPUT) with the per-point lists (INPUT_2) by their respective fields (FIELD and FIELD_2) to create a combined feature collection.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: "Feature Construction". The purpose is: "Create individual features for each point-date pair with attributes". Input: "Per-point lists and original soil points". Outp
[tail] uteindex**: Doesn't change feature count.

- **saga:featurestoraster**: Converts to raster, not desired.

- **native:pointstopath**: Converts points to paths, not splitting.

- **qgis:regularpoints**: Creates new points, not combining existing ones.

- **qgis:joinbylocationsummary**: Similar to join
```

## [P3] PCA2-T-046#S5 — POS → POS
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:concatenatevectordata
- 对照臂选择：['native:mergevectorlayers'] ｜ 实验臂选择：['otb:concatenatevectordata', 'native:mergevectorlayers']
### 对照臂 (v0_4) 决策摘录
```
SELECT native:mergevectorlayers - Combines multiple vector layers into a single layer using the LAYERS port for inputs and OUTPUT for the merged result.
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:concatenatevectordata - Concatenates all temporary feature collections (passed as a list of vector data files) into a single OutputVectorData.  
SELECT native:mergevectorlayers - Combines all temporary feature layers (provided via the LAYERS port) into a single merged vector layer.
```

## [P3] PCA2-T-056#S3 — NODEC → POS
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:mosaic, otb:hyperspectralunmixing
- 对照臂选择：(无) ｜ 实验臂选择：['saga:mosaicking']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to decide which candidate operator(s) can accomplish Step 3: "Band Stacking & Mosaic". The purpose is to combine the median bands into a full-color multispectral scene suitable for cla
[tail]  single multi-band raster. Which operator can do that? 

Looking at the parameters of saga:mosaicking, it mentions "FILE_LIST(file, required, default=False)" and "GRIDS(multilayer)". This suggests it can take a list of files and optionally treat them as multilayer grids. If we provide a list of band
```
### 实验臂 (v0_5) 决策摘录
```
SELECT saga:mosaicking - Creates a mosaic from multiple median composite rasters using specified overlap blending, resampling, and extent parameters.
REJECT saga:colournormalizedspectralsharpening - Designed for spectral sharpening, not for combining multiple rasters into a mosaic.
REJECT grass7:i.image.mosaic - While it mosaics images, lacks documented parameters for controlling output extent/resolution, making suitability uncertain.
REJECT otb:mosaic - Can perform mosaicking but requires complex configuration (feathering, harmonization) beyond basic band stacking.
REJECT saga:focalstatistics - Computes local statistics on a single raster, not for combining multiple rasters.
REJECT qgis:top…
```

## [P3] PCA2-T-060#S1 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:tilefusion, otb:sampleaugmentation
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the candidate operators accept vector input and produce tile-indexed training/testing sample arrays.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to decide which candidate operator(s) can accomplish Step 1: "Sample Preparation & Splitting". The purpose is: "Organize ground-truth samples into tile-based training/testing subsets".
[tail] d to split samples? However, the operator itself doesn't output a mapping; it only outputs a field separator. That seems insufficient.

Alternatively, maybe grass7:v.sample could be used in reverse? But it doesn't support inverse operation.

Thus, I think the correct response is NO OPERATOR FOR THIS
```

## [P3] PCA2-T-062#S4 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:stereoframework, otb:colormapping
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP
because the provided operators focus on exporting static outputs (images/PDFs) or performing spatial analyses, and none offer the interactive map viewer functionality with panning, zooming, and dynamic year toggling described in the plan step.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P3] PCA2-T-073#S1 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:dynamicconvert, otb:trainimagesregression, otb:smoothing
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the provided operators describe functionality to combine two separate raster layers (MODIS Daytime LST and MODIS Nighttime LST) into a single daily mean raster through pixel-wise averaging.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to preprocess LST data: create a single daily mean LST layer from separate daytime and nighttime inputs. The inputs are MODIS Daytime LST and MODIS Nighttime LST. We want to produce a 
[tail] transpiration - converts daily to hourly evapotranspiration, not LST.
REJECT saga:diurnalanisotropicheat - computes heat flux from DEM, not LST.
REJECT otb:dynamicconvert - changes pixel type/dynamic, not combines two rasters.
REJECT saga:soilwaterbalancedays - models soil moisture dynamics, not LST
```

## [P3] PCA2-T-079#S5 — NODEC → ABST
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:stereoframework, otb:colormapping
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the provided operators support combining a FeatureCollection (for station locations and buffers) with an LST raster to produce integrated map images; all operate solely on rasters or vectors individually and lack visualization capabilities such as symbology, labeling, or layout composition.
```

## [P3] PCA2-T-086#S4 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:pixelvalue, otb:multiimagesamplingrate, otb:imageregression
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
Because none of the candidate operators can combine multiple single-layer rasters into a multi-band stack and simultaneously compute a pixel count per band across all bands.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to decide which candidate operator(s) can accomplish the plan step: 
"Stack Layers & Count Pixels". The purpose is to combine all single-layer outputs into a multi-band stack and then 
[tail] interpret "zones" as the union of all areas covered by any layer? But we need a zone raster that partitions space into cells where we want to compute statistics. If we had a regular grid (like a shapefile of cells), we could run this operator for each layer individually and then combine the results?
```

## [P3] PCA2-T-089#S5 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:disparitymaptoelevationmap, otb:refinesensormodel, otb:contrastenhancement, otb:classificationmapregularization, otb:morphologicalclassification
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the candidate operators accept both a change detection raster and a slope/pre‑flood water mask as combined inputs to produce a refined flood candidate raster; they either operate on DEM/disparity maps alone or perform simple Boolean operations without the needed conditional logic.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: Step 5 - Refinement Using Ancillary Data
 Purpose: Incorporate topographic and prior knowledge to reduce false positives/negatives
 Input: Smoothed change detection r
[tail] on raster is actually a DEM (which it isn't, it's a change detection raster), then it might be relevant. But the step says we have a slope layer, not a DEM. So no.

 - **otb:contrastenhancement**: Might enhance the change detection raster, but doesn't use slope or water mask.

 - **otb:classifcation
```

## [P3] PCA2-T-092#S5 — ABST → NODEC
- 优先理由：input_types_norm corrected operator involved
- 卡面变化算子：otb:sardecompositions, otb:sarpolarmatrixconvert, otb:sarburstextraction, otb:sarcalibration, otb:sarconcatenatebursts, otb:sarpolarsynth, otb:computeimagesstatistics
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP
because no candidate operator provides functionality to compute coherency from SAR data.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P4] PCA2-T-003#S2 — NODEC → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:radiometricindices, otb:opticalcalibration, otb:pixelvalue
- 对照臂选择：(无) ｜ 实验臂选择：['otb:opticalcalibration']
### 对照臂 (v0_4) 决策摘录
```
REJECT otb:radiometricindices - lacks documented parameters for performing radiometric correction (e.g., gain/offset application).  
REJECT otb:opticalcalibration - lacks documented parameters for performing radiometric correction (e.g., gain/offset application).  
REJECT grass7:i.albedo - computes albedo from surface reflectance, not from
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:opticalcalibration - Converts raw Digital Numbers (DN) to Top-Of-Atmosphere (TOA) or Top-Of-Canopy (TOC) reflectance values through sensor-specific radiometric calibration, requiring acquisition metadata (date/time, sun/view angles) and sensor-dependent calibration coefficients.
```

## [P4] PCA2-T-005#S3 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:imageregression, otb:compareimages
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
Because none of the provided operators can compute a cloud cover percentage or similar metric needed to filter scenes based on low cloud cover; the closest (`saga:cloudDetection`) only outputs a binary cloud mask without aggregated statistics.
```

## [P4] PCA2-T-005#S5 — POS → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:disparitymaptoelevationmap
- 对照臂选择：['grass7:r.mask.vect'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT grass7:r.mask.vect - uses a vector fire boundary to mask a raster, producing a binary mask where pixels within the boundary are set to 1 and outside to 0.
```
### 实验臂 (v0_5) 决策摘录
```
SELECT grass7:r.mask.vect - Creates a binary raster mask by applying a vector polygon (fire boundary) to a raster, setting interior pixels to 1 and exterior to 0.  
REJECT grass7:r.mask.rast - No documented parameters or outputs; unclear if it supports vector-based masking.  
REJECT grass7:r.reclass.area - Reclassifies raster values based on thresholds, not designed to generate a mask from a vector boundary.  
REJECT qgis:heatmapkerneldensityestimation - Produces a smoothed density surface, not a binary mask.  
REJECT saga:fireriskanalysis - Calculates multi-factor fire risk indices, not a geometric mask.  
REJECT saga:morphometricprotectionindex - Generates a terrain-derived protection inde…
```

## [P4] PCA2-T-012#S3 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:compareimages
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP
because none of the provided operators can compute a mean value across multiple raster time series; they either operate on vectors, perform comparisons returning scalar metrics, or do spatial operations unrelated to temporal averaging.
```

## [P4] PCA2-T-021#S4 — ABST → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:disparitymaptoelevationmap
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP
because none of the candidate operators support combining multiple raster inputs into a single fused raster.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P4] PCA2-T-022#S6 — ABST → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:colormapping
- 对照臂选择：(无) ｜ 实验臂选择：['grass7:r.blend.rgb']
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP
because no operator is capable of extracting individual RGB bands from a multi-band raster; the closest candidate (grass7:r.rgb) only extracts the blue channel, while others either transform RGB to another color model or perform unrelated tasks.
```
### 实验臂 (v0_5) 决策摘录
```
SELECT grass7:r.blend.rgb - It blends three raster maps (typically red, green, and blue bands from the mosaic) into a single RGB image, producing the final true-color mosaic.
```

## [P4] PCA2-T-025#S4 — NODEC → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:imageregression
- 对照臂选择：(无) ｜ 实验臂选择：['saga:statisticsforrasters']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
SELECT saga:statisticsforrasters - Use GRIDS to input the aligned raster grids and retrieve the result from MEAN outputRaster.
```

## [P4] PCA2-T-026#S4 — POS → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:rasterization
- 对照臂选择：['native:rasterize'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT native:rasterize - Can combine multiple rasters into a single multi-band raster using the LAYERS parameter, producing an image stack that can be viewed interactively.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to decide which candidate operator(s) can accomplish Step 4: "Integrate Layers for Visualization". The purpose is to combine all generated rasters into a single viewable composition. I
[tail] ing multiple layers into one image. So it could work.

However, note that the input types for **native:rasterize** are literal or raster. Our inputs are rasters, so we can pass them. But the function might expect the layers to be provided as part of a map theme or something. Still, it seems possible
```

## [P4] PCA2-T-032#S2 — ABST → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:opticalcalibration, otb:sarcalibration, otb:radiometricindices
- 对照臂选择：(无) ｜ 实验臂选择：['otb:opticalcalibration']
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP
because none of the candidate operators provide both radiometric calibration (converting digital numbers to top-of-atmosphere reflectance) and atmospheric correction capabilities; they primarily operate on already calibrated or non-radiometric
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:opticalcalibration - Performs radiometric calibration to TOA/TOC, requiring acquisition metadata and optionally input image, producing calibrated output.
```

## [P4] PCA2-T-033#S1 — NODEC → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:spectralangleclassification, otb:hyperspectralunmixing
- 对照臂选择：(无) ｜ 实验臂选择：['gdal:rearrange_bands']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to decide which candidate operator(s) can accomplish Step 1: "Band Extraction". The purpose is to extract green and near-infrared spectral bands from the imagery. Input: Landsat 7 ETM+
[tail] extent` which clips the raster but retains all bands. That doesn't help.

What about `saga:multibandvariation`? It computes variations across bands, but doesn't extract individual bands.

I think the most plausible is `gdal:rearrange_bands`. Many users would use it to extract bands. They might write
```
### 实验臂 (v0_5) 决策摘录
```
SELECT gdal:rearrange_bands - Use it to extract specific bands by setting BANDS parameter to the respective band indices for green and NIR, producing separate rasters.  
REJECT native:extractlabels - Operates on vector data, not raster bands.  
REJECT gdal:extractprojection - Extracts projection information, not spectral bands.  
REJECT grass7:r.colors.out - Exports color tables, not spectral bands.  
REJECT sage:multibandvariation - Computes statistical variations across bands, not extraction.  
REJECT native:extractbyextent - Clips vector layers by extent, not bands.  
REJECT native:extractbylocation - Extracts features by location predicate, not bands.  
REJECT otb:spectralangleclassifica…
```

## [P4] PCA2-T-052#S2 — ABST → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:polygonclassstatistics
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because the task requires converting a raster into vector polygons, and none of the provided operators support that transformation.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to create vector polygons representing Water, Forest, and City features within an ROI for sampling. The inputs are processed raster stacks from Step 1. We have several candidate operat
[tail] perator that outputs a vector table from a raster, it might be the best choice.

Also, note that **grass7:r.watershed** outputs various maps including 'drainage', 'basin'. Those could be converted to polygons? But the operator itself doesn't output polygons; it outputs raster maps. You would need to
```

## [P4] PCA2-T-056#S2 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:imageregression
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the provided operators perform median computation across multiple layers/time-series; they either segment, mosaic, track features, divide, regress, composite fixed bands, or average with a mask—none generate a single-band median composite from a stack.
```

## [P4] PCA2-T-056#S4 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:spectralangleclassification
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the candidate operators provide functionality to extract spectral signatures from polygon vectors into a labeled feature table; available operators focus on classification, terrain analysis, or segmentation without generating the required tabular output.
```

## [P4] PCA2-T-057#S4 — NODEC → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:pixelvalue, otb:compareimages
- 对照臂选择：(无) ｜ 实验臂选择：['otb:compareimages']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to compute mean squared differences between two images: the original image and two filtered versions (focal median and EDS). The purpose is to quantitatively measure pixel-wise deviati
[tail]  grids. Each output cell corresponds to a block of input cells. The method is applied to the blocks. For example, if we use method="average", it averages the values of all input cells falling into that output cell. If we use method="(@A - @B)^2", it would compute the squared difference for each pair
```
### 实验臂 (v0_5) 决策摘录
```
SELECT otb:compareimages - Computes mean squared error between two images via its 'mse' output port; applying it with original image as reference and focal median/EED result as measurement gives the respective MSD values.

REJECT native:filterbygeometry - Operates on vector geometries, not raster pixel values, and cannot compute statistical differences between images.

REJECT otb:pixelvalue - Retrieves a single pixel value rather than comparing two images or averaging differences.

REJECT grass7:r.stats.quantile.rast - Computes quantiles of a single raster, not pairwise differences between two images.

REJECT grass7:r.resamp.stats - Aggregates raster values to a coarser grid but does not com…
```

## [P4] PCA2-T-068#S4 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:smallregionsmerging
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to determine which candidate operator(s) can calculate the initial forest area calculation. The purpose is to compute the total pixel count (area) classified as 'Tree Cover Lost' (or e
[tail] ons to compute cross-tabulated statistics, yielding pixel counts per class within each park zone.

No other operators seem suitable.

Check if any other operator could work: Perhaps `grass7:r.reclass.area` could be misinterpreted? But it lacks polygon input. So reject others.

Hence, output only one
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the candidate operators support processing polygon geometries (e.g., park polygons) alongside a raster to extract class-specific pixel counts within specified boundaries.
```

## [P4] PCA2-T-068#S6 — NODEC → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:smallregionsmerging
- 对照臂选择：(无) ｜ 实验臂选择：['native:aggregate']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We need to decide which candidate operator(s) can accomplish the plan step: "Cumulative Loss Aggregation". The purpose is to sum annual losses to find total loss per park zone. Input: Output f
[tail] rovided that the input from Step 5 is a vector dataset containing the necessary attributes (park zone identifier, year, and area of loss). If the input is a raster, then none of these operators fit well. But since the step mentions "per park zone", it strongly suggests that park zones are defined as
```
### 实验臂 (v0_5) 决策摘录
```
SELECT native:aggregate - takes vector input from Step 5, groups by park zone attribute, and aggregates loss values to produce summary table with cumulative area lost per zone.
```

## [P4] PCA2-T-070#S1 — NODEC → POS
- 优先理由：decision discordant
- 卡面变化算子：otb:segmentation
- 对照臂选择：(无) ｜ 实验臂选择：['saga:resampling']
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] 
[tail]
```
### 实验臂 (v0_5) 决策摘录
```
SELECT saga:resampling - Uses the optional TARGET_USER_EXTENT parameter to define the ROI bounding box and resamples the input raster to match that extent, producing a cropped output raster.
```

## [P4] PCA2-T-079#S3 — ABST → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:sampleextraction, otb:sampleaugmentation
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
Because none of the candidate operators can directly generate multiple concentric circular zones (multiple rings) around each station; they either produce a single buffer per feature, operate on raster inputs, or serve different purposes such as random point generation or distance calculation.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to generate variable buffers around stations at specific distances: 50m, 100m, ..., 300m. The goal is to create concentric circular zones for each station. This means we want to produc
[tail] nces via the FIELD parameter if the field is a string array? Not sure.

Given the information, I'll reject all.

However, let's double-check the names: "qgis:variabledistancebuffer" – the word "variable" might imply that the distance varies across features, not that multiple rings are created. So it
```

## [P4] PCA2-T-080#S4 — ABST → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:spectralangleclassification
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because the required indices (BAI, BAIS2, TBR) are not supported by any of the provided operators, which lack functionality to compute these specific burn-area-sensitive spectral indices from a vegetated pixel stack.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```

## [P4] PCA2-T-081#S5 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:disparitymaptoelevationmap
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: "Topographic Constraint Integration". The purpose is to refine a mask using elevation suitability rules. Input: Step 4 mask and SRTM DEM. Output: Final refined sugarc
[tail] ased on elevation data.

 But wait: What about **native:meshcontours**? It accepts a mesh (which could be created from the DEM?) and outputs contours. Then we could clip the mask with those contours? But that would be two separate steps, and the operator itself doesn't take a mask.

 Similarly, **gd
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP  
because none of the candidate operators can accept both a mask and a DEM to produce a refined mask.
```

## [P4] PCA2-T-084#S4 — NODEC → ABST
- 优先理由：decision discordant
- 卡面变化算子：otb:polygonclassstatistics, otb:lsmssmallregionsmerging, otb:smallregionsmerging, otb:obtainutmzonefromgeopoint
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
REJECT saga:climateclassification - requires temperature and precipitation multilayers, not available from given inputs  
REJECT otb:polygonclassstatistics - output not
```
### 实验臂 (v0_5) 决策摘录
```
NO OPERATOR FOR THIS STEP
because none of the candidate operators can directly derive monsoonal and Mediterranean precipitation patterns from hs_ratio.tif and latitude_zone_mask.tif; the climate classification operator requires temperature and precipitation multilayers instead of the given inputs, and other operators either perform unrelated spatial analyses or require additional preprocessing steps not supported by the provided tools.
```

## [P4] PCA2-T-086#S5 — ABST → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:pixelvalue
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP  
Because none of the candidate operators can simultaneously compute the mean number of observations per pixel (requiring summation and division by total pixels) and generate a binary mask of pixels with at least one valid observation from a single raster input. All listed operators either lack appropriate output types, require additional inputs not present, or perform unrelated functions.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to compute two outputs: 
   average_observation_frequency: mean number of observations per pixel (average frequency)
   effective_observation_frequency: pixels that have at least one v
[tail] ry mask; unclear if it can produce both.
 REJECT grass7:r.stats.zonal - Requires two input rasters and accumulator-based statistics, not direct mean and binary mask.

 Since none work, we output:

 NO OPERATOR FOR THIS STEP
 because none of the candidate operators can simultaneously compute the mean
```

## [P4] PCA2-T-089#S4 — POS → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:morphologicalclassification, otb:segmentation, otb:morphologicalprofilesanalysis, otb:classificationmapregularization, otb:opticalcalibration
- 对照臂选择：['saga:morphologicalfilter'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT saga:morphologicalfilter - Takes raw change detection raster as input and applies morphological filtering (e.g., opening/closing) using specified kernel and radius to produce a smoothed output raster.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We are given a plan step: 
   Step 4 - Morphological Filtering
   purpose: Remove small speckles and noise from initial change detection
   input: Raw change detection raster
   output: Smooth
[tail] rve the original classes. So I'm leaning towards rejecting it.

   Similarly, the fourth operator (otb:morphologicalprofilesanalysis) is for profiling, not smoothing.

   The fifth and sixth are for vectors.

   The seventh (otb:classifcationmapregularization) we already considered.

   The eighth (
```

## [P4] PCA2-T-092#S2 — POS → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:pixelvalue
- 对照臂选择：['saga:clouddetection'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT saga:clouddetection - Uses the blue, green, red, near-infrared, short-wave infrared bands from the Sentinel-2 stack as inputs to compute cloud probabilities and outputs a cloud mask raster for subsequent masking.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] <think>
We need to identify which candidate operator(s) can accomplish the task: "Identify and mask out cloudy pixels in optical imagery". The input is from Step 1 output (Sentinel-2 stack), and the o
[tail] ly a mask, but it's undocumented. Alternatively, maybe we can use the cloud mask as a condition in a raster calculator, but that's not an operator here.

Given the instructions, we must base our judgment solely on the provided records. Since clouddetection outputs a cloud mask, and the step includes
```

## [P4] PCA2-T-098#S1 — ABST → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:pixelvalue, otb:imagedimensionalityreduction
- 对照臂选择：(无) ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
NO OPERATOR FOR THIS STEP
because none of the operators provide a way to conditionally mask pixels based on quality assurance information; they either operate on single rasters without masks, convert formats, or perform unrelated tasks.
```
### 实验臂 (v0_5) 决策摘录
```
NO
```

## [P4] PCA2-T-098#S6 — POS → NODEC
- 优先理由：decision discordant
- 卡面变化算子：otb:smoothing, otb:meanshiftsmoothing
- 对照臂选择：['saga:resamplingfilter'] ｜ 实验臂选择：(无)
### 对照臂 (v0_4) 决策摘录
```
SELECT saga:resamplingfilter - Applies a low-pass filter to the time series when stacked as bands, reducing high-frequency noise while preserving low-frequency phenological trends.
```
### 实验臂 (v0_5) 决策摘录
```
[no closed think | head] 
[tail]
```
