# PCA B 组审核工作表 v1（owner 用）

> 依据：PCA_PROTOCOL_V1_FROZEN §2.1/§2.4 + owner 指令（2026-10-13）。
> 筛选：20 正选 + 10 备选（frozen rules，seed 20261013，零预测参考）。
> 词表命中**不自动判不合格**；四问逐条裁定。

## 正选 20 条

### W055908 — Agricultural plant science — 链长 5 (medium_4_6)

**任务文本**：Sample vector points by attribute. The script performs point sampling on a user-provided vector layer (points) using either random or stratified sampling. For stratified sampling, it classifies the input layer’s numeric field into classes using either quantiles or equal intervals (via a custom QGIS algorithm 'Precision Agriculture:V - Classification'), then performs random selection within each class. The output is a new vector point layer containing the sampled points, with added X and Y coordinate fields.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：qgis:randomselection -> native:saveselectedfeatures -> qgis:randomselectionwithinsubsets -> native:saveselectedfeatures -> native:addxyfields

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W005784 — Atmospheric winds — 链长 2 (short_2_3)

**任务文本**：Calculate urban wind field. The script calculates 3D spatial variations of wind speed and direction in an urban context using 2.5D building and vegetation vector data. It accepts building polygons with roof height attributes and/or vegetation polygons with crown base/top height and wind attenuation attributes; applies a vertical wind profile (power law, urban, or user-defined CSV); discretizes the domain using horizontal and vertical resolutions; performs physics-based wind flow modeling (via external Java-based solver in MainCalculation.main); and outputs 2D wind speed rasters/vectors at specified heights and/or 3D wind fields in NetCDF format. Outputs include georeferenced rasters, vector layers styled with predefined QGIS styles, metadata files (RunInfoURock_*.txt), and optional loading into QGIS.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：native:savefeatures -> native:savefeatures

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000473 — Boundaries — 链长 3 (short_2_3)

**任务文本**：Compute symmetrical difference of two polygon layers. The script computes the symmetrical difference (XOR) between two vector layers representing an exterior extent and a survey mosaic, after dissolving each layer to single-part geometries. It outputs a new vector layer containing areas present in either the exterior extent or the survey mosaic but not in both — i.e., the non-overlapping portions — and adds this result as a map layer in QGIS.

**词表命中**：`difference`, `mosaic`

**命中上下文**：
- `difference` …Compute symmetrical difference of two polygon layers. The script computes t…
- `mosaic` …representing an exterior extent and a survey mosaic, after dissolving each layer to single-part …

**gold 链（仅反推材料，非金标）**：native:dissolve -> native:dissolve -> native:symmetricaldifference

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W066995 — Environmental governance/management — 链长 4 (medium_4_6)

**任务文本**：Collect Queensland Natural Resource Data. The script collects natural resource data from the Queensland government feature server by querying objects based on lot/plan boundaries or a specified extent string. It fetches feature counts, retrieves object IDs, downloads GeoJSON features in batches, clips them to the property or extent polygon, buffers polygons to fix geometry issues, merges all clipped features, and saves the result as a styled GeoPackage layer added to the QGIS map canvas.

**词表命中**：`buffer`, `clip`, `merge`

**命中上下文**：
- `buffer` …lips them to the property or extent polygon, buffers polygons to fix geometry issues, merges all…
- `clip` … IDs, downloads GeoJSON features in batches, clips them to the property or extent polygon, buf…
- `merge` …on, buffers polygons to fix geometry issues, merges all clipped features, and saves the result …

**gold 链（仅反推材料，非金标）**：native:buffer -> native:extenttolayer -> native:clip -> native:mergevectorlayers

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W067268 — Environmental impacts — 链长 28 (long_7p)

**任务文本**：Noise level prediction from point source. This script estimates noise levels (dBA) from a point source at receptor locations using the BS 5228 standard. It reprojects input DEM and receptor polygons to a projected CRS, performs a viewshed analysis from the source point to account for line-of-sight barriers, creates a hexagonal grid over the receptor area, computes distances, applies attenuation factors (distance, ground type, soft ground percentage, reflections, screening, and duration corrections) via field calculations, and outputs a noise level layer (dBA_activity) and a styled noise source point. The workflow integrates QGIS processing algorithms: point to layer, reprojection, viewshed, grid creation, centroid extraction, zonal statistics, distance to nearest hub, attribute joins, and field calculator steps.

**词表命中**：`grid`, `reproject`, `zonal statistics`

**命中上下文**：
- `grid` … line-of-sight barriers, creates a hexagonal grid over the receptor area, computes distances, …
- `reproject` …tor locations using the BS 5228 standard. It reprojects input DEM and receptor polygons to a projec…
- `zonal statistics` …iewshed, grid creation, centroid extraction, zonal statistics, distance to nearest hub, attribute joins, a…

**gold 链（仅反推材料，非金标）**：native:pointtolayer -> native:setlayerstyle -> native:reprojectlayer -> gdal:warpreproject -> native:reprojectlayer -> gdal:viewshed -> native:creategrid -> native:extractbylocation -> native:centroids -> native:zonalstatisticsfb -> native:intersection -> native:rastersampling -> qgis:distancetonearesthubpoints -> native:joinattributestable -> native:joinattributestable -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:setlayerstyle

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000863 — Environmental impacts — 链长 3 (short_2_3)

**任务文本**：Model boat movement probability. The script models probabilistic boat movement across a directed canal network in Groningen, Netherlands. It computes initial distribution probabilities based on proximity to source points, transition probabilities along network edges using wind direction data and edge angles, catching probabilities based on canal width versus boat width, and stuck probabilities incorporating dead ends, sharp corners, shore types (e.g., houseboats, vegetation), and water vegetation. Outputs are written as attributes to a GeoJSON node layer: 'init_probability', 'transition_probability' (on edges), 'catching_probability', 'stuck_probability', and 'impact_factor'.

**词表命中**：`proximity`

**命中上下文**：
- `proximity` … initial distribution probabilities based on proximity to source points, transition probabilities a…

**gold 链（仅反推材料，非金标）**：native:deleteduplicategeometries -> native:extractvertices -> native:clip

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W055625 — Erosion/sedimentation — 链长 19 (long_7p)

**任务文本**：Calculate riverbank continuity index (Indice F3). The script computes the Indice F3 for river morphological quality by evaluating longitudinal continuity of the 15m-wide erodible corridor along each river segment. It samples transects perpendicular to the river, checks for obstacles (roads, agricultural/urban land) within 15m on each bank using spatial intersection, and computes the percentage of obstacle-free transect sides. This percentage is then converted into an index score (0,2,3,5) indicating erosion capacity, and the results are written to an output vector layer with attributes for percentage and index.

**词表命中**：`intersect`

**命中上下文**：
- `intersect` … land) within 15m on each bank using spatial intersection, and computes the percentage of obstacle-…

**gold 链（仅反推材料，非金标）**：gdal:polygonize -> native:buffer -> native:dissolve -> native:mergevectorlayers -> native:dissolve -> native:buffer -> gdal:cliprasterbymasklayer -> native:reclassifybytable -> native:dissolve -> native:simplifygeometries -> native:buffer -> gdal:cliprasterbymasklayer -> native:reclassifybytable -> native:dissolve -> native:simplifygeometries -> native:buffer -> native:dissolve -> native:mergevectorlayers -> native:dissolve

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W055494 — Forest science — 链长 13 (long_7p)

**任务文本**：Merge similar forest stands. The script merges small forest stand polygons with geometrically adjacent and spectrally/structurally similar (based on relative height dominant difference and type) larger stands. It computes adjacency via spatial intersection/touching, filters candidates by area threshold (min_area_m2), relative hdom difference (min_hdom_diff_rel), and neighbour type ('classified'), resolves one-to-one merge eligibility, dissolves selected small stands into their dominant neighbours, preserves original attributes of the largest stand in each merge group, and outputs a merged GeoPackage layer (stands_merged.gpkg) with a 'merged' flag (1=merged, 0=not merged) and cleaned attribute schema (dropping 'layer', 'path', 'fid_input').

**词表命中**：`difference`, `dissolve`, `intersect`, `merge`

**命中上下文**：
- `difference` …y similar (based on relative height dominant difference and type) larger stands. It computes adjacen…
- `dissolve` …ed'), resolves one-to-one merge eligibility, dissolves selected small stands into their dominant n…
- `intersect` …er stands. It computes adjacency via spatial intersection/touching, filters candidates by area thre…
- `merge` …Merge similar forest stands. The script merges sma…

**gold 链（仅反推材料，非金标）**：native:fieldcalculator -> native:extractbyexpression -> native:aggregate -> native:orderbyexpression -> native:dissolve -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:mergevectorlayers -> native:fieldcalculator -> native:deletecolumn -> native:deletecolumn -> native:fieldcalculator

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W068342 — Forest science — 链长 6 (medium_4_6)

**任务文本**：Clear Safe Canopy Points. The script filters a set of points created for drone flight planning by reprojecting them to EPSG:31981, applying a -10 m buffer to an optimized grid, and retaining only points that intersect both the buffered grid and the area plot polygon. The resulting 'Safe Points' layer represents locations valid for canopy photo capture.

**词表命中**：`buffer`, `grid`, `intersect`, `reproject`

**命中上下文**：
- `buffer` …jecting them to EPSG:31981, applying a -10 m buffer to an optimized grid, and retaining only poi…
- `grid` …981, applying a -10 m buffer to an optimized grid, and retaining only points that intersect bo…
- `intersect` …timized grid, and retaining only points that intersect both the buffered grid and the area plot pol…
- `reproject` … points created for drone flight planning by reprojecting them to EPSG:31981, applying a -10 m buff…

**gold 链（仅反推材料，非金标）**：native:reprojectlayer -> native:reprojectlayer -> native:reprojectlayer -> native:buffer -> native:extractbylocation -> native:extractbylocation

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W068833 — Geodetics — 链长 2 (short_2_3)

**任务文本**：Harmonize rasters for suitability analysis. This QGIS processing algorithm aligns multiple input rasters to a common grid geometry (CRS, extent, pixel size) using GDAL Warp. It accepts optional snap raster, target extent, resolution, resampling method, and nodata value. Outputs include a preview raster (copy of the first aligned result), a folder with aligned GeoTIFFs named sequentially, and a manifest file summarizing alignment parameters. The process ensures all outputs have identical grid structure, making them directly stackable for multi-criteria decision analysis.

**词表命中**：`grid`, `warp`

**命中上下文**：
- `grid` …hm aligns multiple input rasters to a common grid geometry (CRS, extent, pixel size) using GDA…
- `warp` …eometry (CRS, extent, pixel size) using GDAL Warp. It accepts optional snap raster, target ext…

**gold 链（仅反推材料，非金标）**：gdal:warpreproject -> gdal:translate

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W067034 — Habitat conversion/fragmentation — 链长 2 (short_2_3)

**任务文本**：Define land cover raster encoding. The script implements a dialog for the Graphab QGIS plugin to select a raster file (or vector layer), extract unique pixel values, and allow the user to define encoding mappings (old codes to new codes, with nodata handling) for further processing like rasterization or merging.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：native:rasterlayeruniquevaluesreport -> qgis:listuniquevalues

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W067092 — Land Use/Land Cover — 链长 13 (long_7p)

**任务文本**：Calculate Area Weighted Average. The script calculates area-weighted average of a given numeric attribute from an overlay polygon layer for each feature in an input polygon layer. The workflow includes adding an incremental ID field and area field to the input, dissolving overlay fields to avoid duplicates, intersecting input and overlay, computing weighted attribute (attribute * fragment area), aggregating per input feature using sum and dividing by total area, and dropping intermediate fields. It produces a result layer with the averaged attribute, a report layer with details, and an optional HTML report with pandas-generated tables. CRS warnings are issued if layers are geographic or mismatched.

**词表命中**：`intersect`

**命中上下文**：
- `intersect` …ssolving overlay fields to avoid duplicates, intersecting input and overlay, computing weighted att…

**gold 链（仅反推材料，非金标）**：native:addautoincrementalfield -> native:fieldcalculator -> native:dissolve -> native:intersection -> native:fieldcalculator -> native:fieldcalculator -> native:dissolve -> native:deletecolumn -> native:deletecolumn -> native:fieldcalculator -> native:fieldcalculator -> native:orderbyexpression -> native:dropgeometries

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000084 — Land surface/agriculture indicators — 链长 4 (medium_4_6)

**任务文本**：Download Copernicus Land Cover Product. The script downloads Copernicus Global Land products by selecting a product collection (e.g., 'CLMS', 'GLOBCOVER') and a target date, then identifies the nearest available manifest file, parses it to locate the closest-date NetCDF file, downloads it, extracts the first subdataset, and converts it to GeoTIFF using GDAL Translate with compression options. Outputs include the converted GeoTIFF file and the original downloaded NetCDF URL.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：native:filedownloader -> native:filedownloader -> native:filedownloader -> gdal:translate

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W007046 — Land use/land cover — 链长 9 (long_7p)

**任务文本**：Extract features by attribute regex and compute centroid. The script selects vector features from an input layer based on a case-insensitive or custom regex pattern applied to a specified string attribute field. It computes two counts: (1) the total number of features in the input layer (stored as 'TotalCount'), and (2) the count of matching features (stored as 'AttributeCount'). It then collects the geometries of the matching features, fixes their geometry validity, computes their centroid point, and outputs two layers: (a) the original matching features augmented with both count attributes ('WithAttribute'), and (b) a single-point centroid feature containing both count attributes ('AttributeCentroid'). The centroid represents the geometric center of the unioned matching geometries.

**词表命中**：`union`

**命中上下文**：
- `union` …troid represents the geometric center of the unioned matching geometries.…

**gold 链（仅反推材料，非金标）**：native:setprojectvariable -> native:setprojectvariable -> native:fieldcalculator -> native:extractbyexpression -> native:fieldcalculator -> native:collect -> native:fixgeometries -> native:centroids -> native:retainfields

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W068582 — Land use/land cover — 链长 3 (short_2_3)

**任务文本**：Assign Manning's n from CORINE 2018. The script assigns Manning's roughness coefficient to CORINE 2018 land cover polygons within a user-defined area of interest. It subsets the CORINE vector layer by the AOI geometry (with reprojection if needed), clips, then adds Manning, area in square meters and hectares. Manning values are looked up from an internal CSV mapping CODE_18 to n. The result is loaded as 'CLC_Manning_AOI'.

**词表命中**：`clip`, `reproject`

**命中上下文**：
- `clip` … AOI geometry (with reprojection if needed), clips, then adds Manning, area in square meters a…
- `reproject` …ORINE vector layer by the AOI geometry (with reprojection if needed), clips, then adds Manning, are…

**gold 链（仅反推材料，非金标）**：native:reprojectlayer -> native:fixgeometries -> native:clip

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000890 — Natural hazards — 链长 5 (medium_4_6)

**任务文本**：Map dominant drought class by municipality. The script processes a pre-existing drought monitoring vector layer ('dezembro25') for Paraíba state, Brazil, to resolve spatial overlaps among drought severity classes (s4–si) using topological difference operations—ensuring hierarchical exclusivity (most severe classes take precedence). It intersects the corrected drought polygons with municipal boundaries ('MunicipiosPB_WGS'), computes area per municipality–class combination, identifies the dominant (largest-area) drought class per municipality, and outputs (1) a categorized municipal map layer symbolized by drought severity, and (2) an Excel table listing each municipality, its dominant drought class code and name, and the corresponding area in m².

**词表命中**：`difference`, `intersect`

**命中上下文**：
- `difference` …t severity classes (s4–si) using topological difference operations—ensuring hierarchical exclusivity…
- `intersect` …ty (most severe classes take precedence). It intersects the corrected drought polygons with municip…

**gold 链（仅反推材料，非金标）**：native:extractbyexpression -> native:mergevectorlayers -> native:difference -> native:mergevectorlayers -> native:intersection

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W033927 — Oceans — 链长 7 (long_7p)

**任务文本**：Map ROV seafloor substrate units. The script processes ROV navigation and annotation data to generate spatially explicit, substrate-classified wedge buffers representing the camera viewshed at each annotated seafloor location; it then dissolves overlapping wedges by substrate type to produce a final polygon shapefile of CMECS-compliant substrate mapping units, symbolized with standardized QML styling for visualization in QGIS.

**词表命中**：`buffer`, `dissolve`

**命中上下文**：
- `buffer` …atially explicit, substrate-classified wedge buffers representing the camera viewshed at each an…
- `dissolve` …at each annotated seafloor location; it then dissolves overlapping wedges by substrate type to pro…

**gold 链（仅反推材料，非金标）**：native:createpointslayerfromtable -> native:pointstopath -> native:createpointslayerfromtable -> native:wedgebuffers -> native:dissolve -> native:setlayerstyle -> native:setlayerstyle

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W001034 — Package Layers to KMZ — 链长 2 (short_2_3)

**任务文本**：Package layers to KMZ. The script packages multiple QGIS vector and raster layers into a single KMZ file. It reprojects layers to a user-specified or project CRS, exports vector layers to KML using QgsVectorFileWriter with optional symbology export, converts raster layers to KML ground overlays via GDAL warp + translate (using KMLSUPEROVERLAY), and composes a master doc.kml that aggregates Folder elements from each input layer’s KML into a ZIP-compressed KMZ archive. No remote sensing analysis, classification, or time-series processing is performed; the workflow is purely geospatial packaging and format conversion within QGIS Processing Framework. Study area, time range, satellite data, bands, and classification methods are not involved — this is a desktop GIS export utility, not an Earth Engine (GEE) script despite the prompt's mischaracterization.

**词表命中**：`reproject`, `warp`

**命中上下文**：
- `reproject` …and raster layers into a single KMZ file. It reprojects layers to a user-specified or project CRS, …
- `warp` …aster layers to KML ground overlays via GDAL warp + translate (using KMLSUPEROVERLAY), and com…

**gold 链（仅反推材料，非金标）**：gdal:warpreproject -> gdal:translate

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W067404 — Plants — 链长 3 (short_2_3)

**任务文本**：Calculate continuous raster statistics for distribution points. The script generates zonal statistics for continuous environmental raster data at species occurrence points. It first creates a buffer around each input point using a user-specified radius, then calculates all available zonal statistics (e.g., count, sum, mean, median, standard deviation, minimum, maximum, range, minority, majority, variety, variance) of the environmental raster within each buffer polygon. Finally, it converts the buffers to centroids to produce a point output layer with the statistical attributes attached to each original point location.

**词表命中**：`buffer`, `zonal statistics`

**命中上下文**：
- `buffer` …pecies occurrence points. It first creates a buffer around each input point using a user-specifi…
- `zonal statistics` …or distribution points. The script generates zonal statistics for continuous environmental raster data at …

**gold 链（仅反推材料，非金标）**：native:buffer -> native:zonalstatisticsfb -> native:centroids

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W055534 — Population — 链长 3 (short_2_3)

**任务文本**：Compute country-level population statistics. The script computes zonal statistics (mean values) for raster datasets—land quality, and population density for years 1500 AD, 1990 AD, and 2000 AD—using country boundaries (ne_10m_admin_0_countries.shp) as zones. It fixes geometries, drops all attribute fields except 'ADMIN' and 'ISO_A3', appends zonal statistics prefixed by 'lqua_', 'pd15_', 'pd19_', and 'pd20_' to the vector layer, then exports the resulting attribute table—including original country fields plus computed statistics—to a CSV file at 'C:/Users/se.4537/Dropbox/PoliteconGIS/LBS_2020/PhD/lecture_3/gis_data/_output/country_level_zs.csv'.

**词表命中**：`zonal statistics`

**命中上下文**：
- `zonal statistics` …l population statistics. The script computes zonal statistics (mean values) for raster datasets—land quali…

**gold 链（仅反推材料，非金标）**：native:zonalstatistics -> native:fixgeometries -> native:deletecolumn

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

## 备选 10 条

### W002004 — Infrastructure — 链长 2 (short_2_3)

**任务文本**：Export infrastructure polygon layer. The script exports a user-provided vector polygon layer (intended for 3D polygons representing civil engineering structures) to a PostgreSQL/PostGIS database table named 'obra_arte' in the 'public' schema. It adds two fields: 'inicio_objeto' (current timestamp, type DateTime) and 'valor_tipo_obra_arte' (a categorical string value selected from a predefined enumerated list via QGIS Processing UI, mapped using get_lista_codigos('valorTipoObraArte')). The export uses GDAL's 'importvectorintopostgisdatabaseavailableconnections' algorithm with append mode, no overwrite, and geometry column named 'geometria'. The input layer must be a polygon layer; no raster, satellite, or time-series processing occurs. Study area, time range, satellite data, bands, classification, or analysis methods are not involved — this is a pure vector data export and field augmentation workflow.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：native:refactorfields -> gdal:importvectorintopostgisdatabaseavailableconnections

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W055689 — Infrastructure — 链长 2 (short_2_3)

**任务文本**：Export Oil and Gas Associated Elements. The script exports a point or polygon vector layer to a PostgreSQL/PostGIS table 'elem_assoc_pgq' in a RECART database. It adds fields 'inicio_objeto' (current timestamp) and 'valor_elemento_associado_pgq' (based on a predefined code enumeration) via field refactoring, then uses GDAL import to append data to the table. The output is the database table record insertion.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：native:refactorfields -> gdal:importvectorintopostgisdatabaseavailableconnections

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000674 — Topography — 链长 4 (medium_4_6)

**任务文本**：Compute slope aspect hillshade. The script computes three terrain derivatives—slope (in degrees), aspect (in degrees), and hillshade—from a high-resolution USGS 3DEP 1/3 arc-second digital elevation model (DEM). It first reprojects the input GeoTIFF DEM from its native CRS (likely NAD83 geographic) to UTM Zone 18N (EPSG:32618) to ensure metrically accurate slope and aspect calculations; then applies GDAL’s slope, aspect, and hillshade algorithms using bilinear resampling and standard illumination parameters (azimuth 315°, altitude 45°, z-factor 2.0); outputs are three georeferenced GeoTIFFs stored in a local output directory and added as layers to the QGIS project for visualization and portfolio documentation.

**词表命中**：`aspect`, `hillshade`, `reproject`, `slope`

**命中上下文**：
- `aspect` …Compute slope aspect hillshade. The script computes three terrain…
- `hillshade` …Compute slope aspect hillshade. The script computes three terrain derivativ…
- `reproject` …cond digital elevation model (DEM). It first reprojects the input GeoTIFF DEM from its native CRS (…
- `slope` …Compute slope aspect hillshade. The script computes three …

**gold 链（仅反推材料，非金标）**：gdal:warpreproject -> gdal:slope -> gdal:aspect -> gdal:hillshade

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W055913 — Land use/land cover — 链长 6 (medium_4_6)

**任务文本**：Merge two agricultural zonings. The script merges two polygon vector layers representing agricultural zonings (e.g., management zones, soil zones, or yield zones) using geometric union and topology cleanup. It first repairs geometries of both input layers, performs a vector union operation to compute their spatial intersection and overlay, converts multipart features to singleparts, adds geometry attributes (area, perimeter), and appends a unique auto-incremented ZONE_ID field. The output is a single vector layer where each polygon represents a non-overlapping atomic zone resulting from the logical combination of the two input zonings.

**词表命中**：`intersect`, `merge`, `union`

**命中上下文**：
- `intersect` …tor union operation to compute their spatial intersection and overlay, converts multipart features …
- `merge` …Merge two agricultural zonings. The script merges …
- `union` … soil zones, or yield zones) using geometric union and topology cleanup. It first repairs geome…

**gold 链（仅反推材料，非金标）**：native:fixgeometries -> native:fixgeometries -> native:union -> native:multiparttosingleparts -> qgis:exportaddgeometrycolumns -> native:addautoincrementalfield

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W005684 — Topography — 链长 2 (short_2_3)

**任务文本**：Rasterize vector layers to topographic masks. The script generates binary (0/1) raster masks from user-selected vector layers, aligned to the spatial extent and resolution of a specified Estonian DTM tile (e.g., '54752_dtm_1m'). It uses GDAL's rasterize tool to burn vector geometries into a fixed-size (4033×4033 pixel) georeferenced TIFF at the DTM’s CRS and extent, then converts each TIFF to an 8-bit grayscale PNG with pixel values scaled to 0–255 (where input geometry = 255, background = 0), optimized for ingestion into Unreal Engine. Output PNGs are named after the source vector layer names and saved to a user-specified folder.

**词表命中**：无

**gold 链（仅反推材料，非金标）**：gdal:rasterize -> gdal:translate

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000635 — Geomorphic landforms/processes — 链长 11 (long_7p)

**任务文本**：Extract polygon boundary edges. The script processes an input vector layer of polygons and generates a new polygon layer representing the 'edges' — i.e., a buffered outline strip along each polygon boundary. It achieves this by: (1) converting multipart geometries to singlepart; (2) fixing and simplifying geometries (with 0.0001 m tolerance); (3) computing inward and outward buffers at half the user-specified width (in tenths of millimeter); (4) differencing the external buffer from the internal buffer to yield a centered edge strip; (5) dissolving the resulting strips; and (6) appending a fixed attribute 'h' = braille.DIM['f'] (likely for tactile map rendering). The output is a polygon feature sink with geometry representing uniform-width edge bands tracing original polygon perimeters.

**词表命中**：`buffer`, `simplify`

**命中上下文**：
- `buffer` …gon layer representing the 'edges' — i.e., a buffered outline strip along each polygon boundary.…
- `simplify` …art geometries to singlepart; (2) fixing and simplifying geometries (with 0.0001 m tolerance); (3)…

**gold 链（仅反推材料，非金标）**：native:multiparttosingleparts -> native:fixgeometries -> native:simplifygeometries -> native:fixgeometries -> native:buffer -> native:fixgeometries -> native:buffer -> native:fixgeometries -> native:difference -> native:dissolve -> native:fixgeometries

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W000060 — Topography — 链长 2 (short_2_3)

**任务文本**：Download and merge DTM tiles. The script downloads Digital Terrain Model (DTM) raster tiles from the City of Vienna's MA41 data portal, uncompresses them, reprojects each tile from EPSG:31256 to EPSG:4326 using GDAL warp, and merges all reprojected GeoTIFFs into a single unified DTM raster file named 'dtm.tif'. The final merged raster is registered as a QGIS raster layer with CRS EPSG:4326. All operations are orchestrated via PyQGIS processing algorithms and custom plugin utility modules (e.g., internet.download_file_list, file_management.unzip_file_list, logger).

**词表命中**：`merge`, `reproject`, `reprojected`, `warp`

**命中上下文**：
- `merge` …Download and merge DTM tiles. The script downloads Digital Terr…
- `reproject` …ienna's MA41 data portal, uncompresses them, reprojects each tile from EPSG:31256 to EPSG:4326 usin…
- `reprojected` …to EPSG:4326 using GDAL warp, and merges all reprojected GeoTIFFs into a single unified DTM raster fi…
- `warp` …tile from EPSG:31256 to EPSG:4326 using GDAL warp, and merges all reprojected GeoTIFFs into a …

**gold 链（仅反推材料，非金标）**：gdal:warpreproject -> gdal:merge

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W056058 — Surface water — 链长 2 (short_2_3)

**任务文本**：Classify and buffer water network levels. The script performs a clip operation on a user-provided vector layer using a clip layer, then classifies the clipped layer into three water network levels (Principal, Secundaria, Terciaria) based on the 'Descripc' attribute, applies distinct colors, and generates buffer zones of 100m, 50m, and 20m respectively for each level. The results include the clipped layer, filtered level-specific layers, and buffer layers displayed in the QGIS map.

**词表命中**：`buffer`, `classify`, `clip`

**命中上下文**：
- `buffer` …Classify and buffer water network levels. The script performs a …
- `classify` …Classify and buffer water network levels. The script …
- `clip` … water network levels. The script performs a clip operation on a user-provided vector layer us…

**gold 链（仅反推材料，非金标）**：native:clip -> native:buffer

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W023206 — Topography — 链长 3 (short_2_3)

**任务文本**：Generate topographic raster tiles. The script automates the creation of a regular grid over a merged digital elevation model (DEM), clips the DEM to each grid cell to produce individual georeferenced GeoTIFF tiles (e.g., tile_01_01.tif), and outputs a vector grid layer (print_grid.shp); it does not perform DEM-to-STL conversion itself but prepares inputs for external 3D printing via the DEMto3D QGIS plugin using specified physical dimensions, spacing, base height, and vertical exaggeration.

**词表命中**：`clip`, `grid`, `merge`

**命中上下文**：
- `clip` …over a merged digital elevation model (DEM), clips the DEM to each grid cell to produce indivi…
- `grid` …e script automates the creation of a regular grid over a merged digital elevation model (DEM),…
- `merge` …omates the creation of a regular grid over a merged digital elevation model (DEM), clips the DE…

**gold 链（仅反推材料，非金标）**：native:creategrid -> gdal:cliprasterbyextent -> native:creategrid

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

### W001974 — Infrastructure — 链长 2 (short_2_3)

**任务文本**：Export navigable waterway transport infrastructure area. The script exports polygon features representing 'Área da infraestrutura de transporte por via navegável' (Area of Transport Infrastructure via Navigable Waterway) from a QGIS vector layer into a PostgreSQL/PostGIS database table named 'area_infra_trans_via_navegavel' in the 'public' schema. It adds two fields: 'inicio_objeto' (current timestamp, type DateTime) and 'valor_tipo_area_infra_trans_via_navegavel' (a categorical string value selected from a predefined enumerated list via get_lista_codigos('valorTipoAreaInfraTransViaNavegavel')). The input must be a 2D polygon layer; no reprojection, clipping, or geometry transformation is performed beyond field refactoring and direct PostGIS insertion using GDAL's importvectorintopostgisdatabaseavailableconnections. The target database connection is preconfigured in QGIS as a PostgreSQL provider connection. No remote sensing, raster, or time-series analysis occurs — this is a pure vector data export and attribution workflow.

**词表命中**：`clip`, `reproject`

**命中上下文**：
- `clip` …must be a 2D polygon layer; no reprojection, clipping, or geometry transformation is performed…
- `reproject` …)). The input must be a 2D polygon layer; no reprojection, clipping, or geometry transformation is …

**gold 链（仅反推材料，非金标）**：native:refactorfields -> gdal:importvectorintopostgisdatabaseavailableconnections

**owner 四问**：Q1 泄露=待裁 / Q2 规划价值=待裁 / Q3 金标独立性=待裁 / Q4 替代路线=待裁

## 因算子 ID 扫描被拒的 8 条（仅记录，不进入候选）

- W000082 — Land surface — 命中ID: gdal:translate
- W000302 — Land use/land cover — 命中ID: gdal:cliprasterbymasklayer
- W000993 — Surface mass — 命中ID: gdal:cliprasterbymasklayer, qgis:idwinterpolation
- W002419 — Water quality — 命中ID: native:zonalstatisticsfb
- W042190 — Land use/land cover — 命中ID: native:creategrid
- W050378 — Natural hazards — 命中ID: native:zonalstatisticsfb
- W055585 — Biological classification — 命中ID: native:pixelstopolygons, native:reclassifybylayer
- W055702 — Surface water — 命中ID: gdal:importvectorintopostgisdatabaseavailableconnections