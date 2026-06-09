#!/usr/bin/env python3
"""Ablation: compare QGIS chain retrieval — stratified 200-query benchmark.

Categories (200 probes):
    50 — pure vector analysis: buffer, clip, dissolve, merge, intersection, difference
    40 — vector attribute/spatial filtering
    40 — raster processing: clip, calculator, reclassify, fill, translate, warp
    30 — vec-rast conversion / mixed
    20 — CRS / geometry cleanup
    20 — low-frequency / uncertain guard

Additional diagnostics:
    - accepted mapping contribution: was top-1 boosted by a new crosswalk entry?
    - rejected/blocklist leakage: did any rejected alg_id get treated as L3 bridge?

Usage:
    python scripts/evaluate_qgis_retrieval_ablation.py
    python scripts/evaluate_qgis_retrieval_ablation.py --num-samples 100
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.planning.qgis_chain_planner import (
    QGISChainRetriever, QGISChainEvaluator, build_qgis_chain_planner,
)

ORIGINAL_DS = ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"
CATALOG = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"

# Accepted crosswalk entries (for contribution tracking)
ACCEPTED_ALG_IDS = {
    "native:mergevectorlayers", "native:extractbyexpression",
    "native:extractbyattribute", "qgis:selectbyexpression",
    "qgis:selectbyattribute", "native:extractbylocation",
    "native:selectbylocation", "native:joinattributesbylocation",
    "qgis:joinbylocationsummary", "native:refactorfields",
    "native:multiringconstantbuffer", "qgis:minimumboundinggeometry",
    "native:symmetricaldifference", "gdal:warpreproject",
    "gdal:translate", "gdal:fillnodata", "native:fillnodata",
    "saga:slopeaspectcurvature",
}

REJECTED_ALG_IDS = {
    "native:createspatialindex", "gdal:rasterize", "gdal:polygonize",
    "native:pixelstopolygons", "gdal:rasterize_over",
    "native:joinattributestable", "native:creategrid",
}

# ── Stratified queries ─────────────────────────────────────────────

def _q(task_text, l3_codes, label, category, prefer_vector=True, prefer_mixed=False):
    return {"task_text": task_text, "l3_codes": l3_codes, "label": label,
            "category": category, "prefer_vector": prefer_vector and not prefer_mixed,
            "prefer_raster": not prefer_vector and not prefer_mixed,
            "prefer_mixed": prefer_mixed}


QUERIES = [
    # ── 50: Pure vector analysis ──
    _q("buffer roads by 100m and clip to study area", ["L3_02_01_01", "L3_02_02_06"], "v_buf_clip", "vec_analysis"),
    _q("dissolve parcels by land use type", ["L3_02_03_05"], "v_dissolve", "vec_analysis"),
    _q("merge county shapefiles into single layer", ["L3_01_03_04"], "v_merge", "vec_analysis"),
    _q("intersect roads with flood zones", ["L3_02_02_06"], "v_intersect", "vec_analysis"),
    _q("difference: remove buildings from flood zone", ["L3_02_02_06"], "v_difference", "vec_analysis"),
    _q("union watershed boundaries into one polygon", ["L3_02_02_06"], "v_union", "vec_analysis"),
    _q("create 500m buffer around river network", ["L3_02_01_01"], "v_buffer_river", "vec_analysis"),
    _q("dissolve zoning parcels and calculate total area per zone", ["L3_02_03_05", "L3_01_02_06"], "v_dissolve_area", "vec_analysis"),
    _q("merge all trail segments into continuous network", ["L3_01_03_04"], "v_merge_trail", "vec_analysis"),
    _q("clip roads to national park boundary", ["L3_02_02_06"], "v_clip_road", "vec_analysis"),
    _q("intersect crop fields with soil map polygons", ["L3_02_02_06"], "v_intersect_crop", "vec_analysis"),
    _q("dissolve city blocks by neighborhood name", ["L3_02_03_05"], "v_dissolve_block", "vec_analysis"),
    _q("buffer power lines by 200m for easement analysis", ["L3_02_01_01"], "v_buffer_power", "vec_analysis"),
    _q("merge census tracts into planning districts", ["L3_01_03_04"], "v_merge_census", "vec_analysis"),
    _q("clip land parcels to city limits", ["L3_02_02_06"], "v_clip_parcel", "vec_analysis"),
    _q("intersect building footprints with landslide hazard zones", ["L3_02_02_06"], "v_intersect_hazard", "vec_analysis"),
    _q("difference: remove water bodies from developable land", ["L3_02_02_06"], "v_difference_water", "vec_analysis"),
    _q("buffer schools by 1km walkable radius", ["L3_02_01_01"], "v_buffer_school", "vec_analysis"),
    _q("dissolve forest patches into contiguous stands", ["L3_02_03_05"], "v_dissolve_forest", "vec_analysis"),
    _q("merge state-level data into national coverage", ["L3_01_03_04"], "v_merge_state", "vec_analysis"),
    _q("clip electrical grid to service territory", ["L3_02_02_06"], "v_clip_grid", "vec_analysis"),
    _q("intersect well points with aquifer boundaries", ["L3_02_02_06"], "v_intersect_well", "vec_analysis"),
    _q("buffer rail lines by 50m for noise impact zone", ["L3_02_01_01"], "v_buffer_rail", "vec_analysis"),
    _q("dissolve agricultural fields by crop type", ["L3_02_03_05"], "v_dissolve_crop", "vec_analysis"),
    _q("clip hiking trails to park boundary", ["L3_02_02_06"], "v_clip_trail", "vec_analysis"),
    _q("merge neighborhood shapefiles for citywide analysis", ["L3_01_03_04"], "v_merge_neighborhood", "vec_analysis"),
    _q("intersect roads with protected areas", ["L3_02_02_06"], "v_intersect_protected", "vec_analysis"),
    _q("buffer hospitals by 5km for service area analysis", ["L3_02_01_01"], "v_buffer_hospital", "vec_analysis"),
    _q("dissolve county boundaries into regional units", ["L3_02_03_05"], "v_dissolve_county", "vec_analysis"),
    _q("clip utility poles to city boundary", ["L3_02_02_06"], "v_clip_utility", "vec_analysis"),
    _q("merge bike lanes into complete network", ["L3_01_03_04"], "v_merge_bike", "vec_analysis"),
    _q("intersect census blocks with floodplain", ["L3_02_02_06"], "v_intersect_flood", "vec_analysis"),
    _q("buffer wetlands by 100m protection zone", ["L3_02_01_01"], "v_buffer_wetland", "vec_analysis"),
    _q("dissolve property parcels into ownership blocks", ["L3_02_03_05"], "v_dissolve_parcel", "vec_analysis"),
    _q("clip transit routes to urban area", ["L3_02_02_06"], "v_clip_transit", "vec_analysis"),
    _q("buffer coastline by 200m setback", ["L3_02_01_01"], "v_buffer_coast", "vec_analysis"),
    _q("merge provincial road networks for national map", ["L3_01_03_04"], "v_merge_road", "vec_analysis"),
    _q("intersect species range with forest cover", ["L3_02_02_06"], "v_intersect_species", "vec_analysis"),
    _q("dissolve land use polygons into simplified classes", ["L3_02_03_05"], "v_dissolve_landuse", "vec_analysis"),
    _q("clip geological map to project area", ["L3_02_02_06"], "v_clip_geo", "vec_analysis"),
    _q("buffer urban growth boundary by 500m", ["L3_02_01_01"], "v_buffer_growth", "vec_analysis"),
    _q("merge school district boundaries for statewide analysis", ["L3_01_03_04"], "v_merge_school", "vec_analysis"),
    _q("intersect groundwater wells with contamination plume", ["L3_02_02_06"], "v_intersect_gw", "vec_analysis"),
    _q("dissolve building footprints into blocks", ["L3_02_03_05"], "v_dissolve_building", "vec_analysis"),
    _q("clip electric transmission lines to ROW", ["L3_02_02_06"], "v_clip_transmission", "vec_analysis"),
    _q("buffer fire hydrants by 300m coverage radius", ["L3_02_01_01"], "v_buffer_fire", "vec_analysis"),
    _q("merge oil pipeline segments into continuous routes", ["L3_01_03_04"], "v_merge_pipeline", "vec_analysis"),
    _q("intersect retail locations with demographic zones", ["L3_02_02_06"], "v_intersect_retail", "vec_analysis"),
    _q("dissolve traffic analysis zones into superzones", ["L3_02_03_05"], "v_dissolve_taz", "vec_analysis"),
    _q("clip rail network to metropolitan region", ["L3_02_02_06"], "v_clip_rail", "vec_analysis"),

    # ── 40: Vector attribute/spatial filtering ──
    _q("extract features where population greater than 10000", ["L3_02_06_02"], "v_extract_attr", "vec_filter"),
    _q("select by expression: land use equals residential", ["L3_02_06_01"], "v_select_expr", "vec_filter"),
    _q("extract by location: points within polygon study area", ["L3_02_06_03"], "v_extract_loc", "vec_filter"),
    _q("join census table to block groups by GEOID", ["L3_02_04_01"], "v_join_attr", "vec_filter"),
    _q("select parcels by attribute: zoning equals commercial", ["L3_02_06_01"], "v_select_attr", "vec_filter"),
    _q("extract roads by expression: highway type equals primary", ["L3_02_06_02"], "v_extract_highway", "vec_filter"),
    _q("select by location: buildings within 100m of fault line", ["L3_02_06_03"], "v_select_loc", "vec_filter"),
    _q("join soil properties to farm parcels by field ID", ["L3_02_04_01"], "v_join_soil", "vec_filter"),
    _q("extract wells by attribute: depth greater than 50m", ["L3_02_06_02"], "v_extract_well", "vec_filter"),
    _q("select tree points by expression: species equals oak", ["L3_02_06_01"], "v_select_tree", "vec_filter"),
    _q("extract by location: stations within city boundary", ["L3_02_06_03"], "v_extract_station", "vec_filter"),
    _q("join traffic count data to road segments by link ID", ["L3_02_04_01"], "v_join_traffic", "vec_filter"),
    _q("extract parcels by attribute: area larger than 5000 sqm", ["L3_02_06_02"], "v_extract_large", "vec_filter"),
    _q("select mines by expression: status equals active", ["L3_02_06_01"], "v_select_mine", "vec_filter"),
    _q("extract by location: hospitals within city limits", ["L3_02_06_03"], "v_extract_hospital", "vec_filter"),
    _q("join election results to precinct polygons by precinct code", ["L3_02_04_01"], "v_join_election", "vec_filter"),
    _q("extract buildings by attribute: construction year after 2000", ["L3_02_06_02"], "v_extract_new", "vec_filter"),
    _q("select protected areas by expression: IUCN category equals II", ["L3_02_06_01"], "v_select_iucn", "vec_filter"),
    _q("extract by location: sensors within air quality monitoring zone", ["L3_02_06_03"], "v_extract_sensor", "vec_filter"),
    _q("join demographic data to planning zones by zone code", ["L3_02_04_01"], "v_join_demo", "vec_filter"),
    _q("extract lightning strikes by attribute: current greater than 50kA", ["L3_02_06_02"], "v_extract_lightning", "vec_filter"),
    _q("select earthquake epicenters by expression: magnitude above 4.0", ["L3_02_06_01"], "v_select_eq", "vec_filter"),
    _q("extract by location: cell towers within urban boundary", ["L3_02_06_03"], "v_extract_tower", "vec_filter"),
    _q("join property tax data to parcel map by parcel number", ["L3_02_04_01"], "v_join_tax", "vec_filter"),
    _q("extract crimes by attribute: type equals burglary", ["L3_02_06_02"], "v_extract_crime", "vec_filter"),
    _q("select census tracts by expression: median income below 30000", ["L3_02_06_01"], "v_select_income", "vec_filter"),
    _q("extract by location: reefs within marine protected area", ["L3_02_06_03"], "v_extract_reef", "vec_filter"),
    _q("join weather station data to watersheds by station ID", ["L3_02_04_01"], "v_join_weather", "vec_filter"),
    _q("extract wetlands by attribute: wetland type equals marsh", ["L3_02_06_02"], "v_extract_marsh", "vec_filter"),
    _q("select bridge locations by expression: condition rating poor", ["L3_02_06_01"], "v_select_bridge", "vec_filter"),
    _q("extract by location: sampling points within contaminated area", ["L3_02_06_03"], "v_extract_sample", "vec_filter"),
    _q("join land ownership records to parcel map by owner ID", ["L3_02_04_01"], "v_join_owner", "vec_filter"),
    _q("extract roads by attribute: surface type equals gravel", ["L3_02_06_02"], "v_extract_gravel", "vec_filter"),
    _q("select commercial plots by expression: floor area ratio above 2", ["L3_02_06_01"], "v_select_far", "vec_filter"),
    _q("extract by location: turbines within wind farm zone", ["L3_02_06_03"], "v_extract_turbine", "vec_filter"),
    _q("join pollution data to monitoring stations by station code", ["L3_02_04_01"], "v_join_pollution", "vec_filter"),
    _q("extract parcels by attribute: vacant equals true", ["L3_02_06_02"], "v_extract_vacant", "vec_filter"),
    _q("select fire stations by expression: response time below 5min", ["L3_02_06_01"], "v_select_fire", "vec_filter"),
    _q("extract by location: boreholes within specified radius", ["L3_02_06_03"], "v_extract_borehole", "vec_filter"),
    _q("join species observations to grid cells by cell ID", ["L3_02_04_01"], "v_join_species", "vec_filter"),

    # ── 40: Raster processing ──
    _q("clip DEM raster to watershed boundary", ["L3_03_01_01"], "r_clip_dem", "raster_proc", False),
    _q("raster calculator: compute NDVI from NIR and RED bands", ["L3_03_03_A"], "r_calc_ndvi", "raster_proc", False),
    _q("reclassify slope raster into low/medium/high hazard zones", ["L3_03_04_01"], "r_reclass_slope", "raster_proc", False),
    _q("fill nodata gaps in land cover raster with nearest neighbor", ["L3_03_03_A"], "r_fill_nodata", "raster_proc", False),
    _q("translate raster from GeoTIFF to Cloud Optimized GeoTIFF", ["L3_07_04_05"], "r_translate_cog", "raster_proc", False),
    _q("warp Landsat scene from UTM to Albers equal area", ["L3_03_05_02"], "r_warp_landsat", "raster_proc", False),
    _q("clip precipitation raster to country boundary", ["L3_03_01_01"], "r_clip_precip", "raster_proc", False),
    _q("raster calculator: SAVI = (NIR-RED)/(NIR+RED+L)*1.5", ["L3_03_03_A"], "r_calc_savi", "raster_proc", False),
    _q("reclassify elevation into 100m interval bands", ["L3_03_04_01"], "r_reclass_elev", "raster_proc", False),
    _q("fill sinks in DEM for hydrological modeling", ["L3_03_03_A"], "r_fill_sinks", "raster_proc", False),
    _q("translate Sentinel-2 imagery to compressed GeoTIFF", ["L3_07_04_05"], "r_translate_s2", "raster_proc", False),
    _q("warp MODIS tile to WGS84 geographic", ["L3_03_05_02"], "r_warp_modis", "raster_proc", False),
    _q("clip fire risk raster to national park boundary", ["L3_03_01_01"], "r_clip_fire", "raster_proc", False),
    _q("raster calculator: compute EVI from surface reflectance", ["L3_03_03_A"], "r_calc_evi", "raster_proc", False),
    _q("reclassify population density into 5 density classes", ["L3_03_04_01"], "r_reclass_pop", "raster_proc", False),
    _q("fill missing pixels in SST raster with spatial interpolation", ["L3_03_03_A"], "r_fill_sst", "raster_proc", False),
    _q("translate drone orthomosaic to mbtiles format", ["L3_07_04_05"], "r_translate_drone", "raster_proc", False),
    _q("warp global precipitation data to country CRS", ["L3_03_05_02"], "r_warp_precip", "raster_proc", False),
    _q("clip soil moisture raster to field boundary", ["L3_03_01_01"], "r_clip_soil", "raster_proc", False),
    _q("raster calculator: compute slope stability index", ["L3_03_03_A"], "r_calc_stability", "raster_proc", False),
    _q("reclassify forest cover change into gain/loss/stable", ["L3_03_04_01"], "r_reclass_forest", "raster_proc", False),
    _q("fill nodata in digital surface model with IDW", ["L3_03_03_A"], "r_fill_dsm", "raster_proc", False),
    _q("translate aerial imagery to ECW compressed format", ["L3_07_04_05"], "r_translate_aerial", "raster_proc", False),
    _q("warp SRTM tile to local UTM zone 33N", ["L3_03_05_02"], "r_warp_srtm", "raster_proc", False),
    _q("clip urban heat island raster to city extent", ["L3_03_01_01"], "r_clip_uhi", "raster_proc", False),
    _q("raster calculator: Tasseled Cap transformation", ["L3_03_03_A"], "r_calc_tcap", "raster_proc", False),
    _q("reclassify erosion risk into very low to very high", ["L3_03_04_01"], "r_reclass_erosion", "raster_proc", False),
    _q("fill nodata in bathymetry raster with spline interpolation", ["L3_03_03_A"], "r_fill_bathy", "raster_proc", False),
    _q("translate NetCDF climate data to GeoTIFF stack", ["L3_07_04_05"], "r_translate_nc", "raster_proc", False),
    _q("warp ALOS DEM to match Landsat projection", ["L3_03_05_02"], "r_warp_alos", "raster_proc", False),
    _q("clip vegetation index to agricultural zone", ["L3_03_01_01"], "r_clip_veg", "raster_proc", False),
    _q("raster calculator: subtract pre-event DEM from post-event", ["L3_03_03_A"], "r_calc_dod", "raster_proc", False),
    _q("reclassify solar radiation into 10 equal interval classes", ["L3_03_04_01"], "r_reclass_solar", "raster_proc", False),
    _q("fill data gaps in canopy height model", ["L3_03_03_A"], "r_fill_chm", "raster_proc", False),
    _q("translate HDF MODIS to GeoTIFF for analysis", ["L3_07_04_05"], "r_translate_hdf", "raster_proc", False),
    _q("warp radar backscatter to match optical image grid", ["L3_03_05_02"], "r_warp_radar", "raster_proc", False),
    _q("clip snow cover fraction to mountain watershed", ["L3_03_01_01"], "r_clip_snow", "raster_proc", False),
    _q("raster calculator: compute burn severity index", ["L3_03_03_A"], "r_calc_burn", "raster_proc", False),
    _q("reclassify permeability into impermeable/semi/permeable", ["L3_03_04_01"], "r_reclass_perm", "raster_proc", False),
    _q("fill missing SLC-off Landsat 7 gaps", ["L3_03_03_A"], "r_fill_slc", "raster_proc", False),

    # ── 30: Vec-rast conversion / mixed ──
    _q("polygonize classified land cover raster to vector", ["L3_03_01_01"], "m_polygonize", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize building footprints to 10m grid", ["L3_03_01_01"], "m_rasterize", "vec_rast_mix", prefer_mixed=True),
    _q("zonal statistics: mean elevation by watershed polygon", ["L3_03_02_01"], "m_zonal_elev", "vec_rast_mix", prefer_mixed=True),
    _q("clip elevation raster to each county and compute statistics", ["L3_03_01_01", "L3_03_02_01"], "m_clip_zonal", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize flood extent raster after thresholding", ["L3_03_01_01"], "m_polygonize_flood", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize road centerlines for cost distance analysis", ["L3_03_01_01"], "m_rasterize_road", "vec_rast_mix", prefer_mixed=True),
    _q("zonal histogram: land cover class frequencies by parcel", ["L3_03_02_01"], "m_zonal_hist", "vec_rast_mix", prefer_mixed=True),
    _q("clip biomass raster to forest stands and compute mean", ["L3_03_01_01", "L3_03_02_01"], "m_clip_bio", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize binary water mask from SAR imagery", ["L3_03_01_01"], "m_polygonize_water", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize soil type polygons for spatial modeling", ["L3_03_01_01"], "m_rasterize_soil", "vec_rast_mix", prefer_mixed=True),
    _q("zonal statistics: max building height by census tract", ["L3_03_02_01"], "m_zonal_height", "vec_rast_mix", prefer_mixed=True),
    _q("clip nightlight raster to urban extents and aggregate", ["L3_03_01_01", "L3_03_02_01"], "m_clip_light", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize slope classes for hazard mapping", ["L3_03_01_01"], "m_polygonize_slope", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize protected area boundaries as binary mask", ["L3_03_01_01"], "m_rasterize_pa", "vec_rast_mix", prefer_mixed=True),
    _q("zonal statistics: average rainfall by river basin", ["L3_03_02_01"], "m_zonal_rain", "vec_rast_mix", prefer_mixed=True),
    _q("clip temperature raster to city boundary and calculate percentiles", ["L3_03_01_01", "L3_03_02_01"], "m_clip_temp", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize crop type classification result", ["L3_03_01_01"], "m_polygonize_crop", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize parcel boundaries with land value attribute", ["L3_03_01_01"], "m_rasterize_value", "vec_rast_mix", prefer_mixed=True),
    _q("zonal statistics: median land surface temperature by district", ["L3_03_02_01"], "m_zonal_lst", "vec_rast_mix", prefer_mixed=True),
    _q("clip population density raster to admin boundary and sum", ["L3_03_01_01", "L3_03_02_01"], "m_clip_pop", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize vegetation density classes", ["L3_03_01_01"], "m_polygonize_veg", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize wetland inventory polygons", ["L3_03_01_01"], "m_rasterize_wetland", "vec_rast_mix", prefer_mixed=True),
    _q("zonal statistics: standard deviation of NDVI by field", ["L3_03_02_01"], "m_zonal_ndvi", "vec_rast_mix", prefer_mixed=True),
    _q("clip impervious surface raster to subwatersheds", ["L3_03_01_01", "L3_03_02_01"], "m_clip_imperv", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize wind speed classification result", ["L3_03_01_01"], "m_polygonize_wind", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize cadastral boundary lines", ["L3_03_01_01"], "m_rasterize_cad", "vec_rast_mix", prefer_mixed=True),
    _q("zonal statistics: sum of precipitation by catchment", ["L3_03_02_01"], "m_zonal_precip", "vec_rast_mix", prefer_mixed=True),
    _q("clip landslide susceptibility raster to slope units", ["L3_03_01_01", "L3_03_02_01"], "m_clip_landslide", "vec_rast_mix", prefer_mixed=True),
    _q("polygonize terrain ruggedness classes for ecology", ["L3_03_01_01"], "m_polygonize_rugged", "vec_rast_mix", prefer_mixed=True),
    _q("rasterize lake polygons for hydrological correction", ["L3_03_01_01"], "m_rasterize_lake", "vec_rast_mix", prefer_mixed=True),

    # ── 20: CRS / geometry cleanup ──
    _q("reproject vector data from WGS84 to UTM zone 33N", ["L3_01_02_03"], "g_reproject_vec", "crs_geom"),
    _q("fix invalid geometries in building footprint layer", ["L3_02_07_01"], "g_fix_geom", "crs_geom"),
    _q("simplify coastline vertices for small-scale map display", ["L3_02_07_01"], "g_simplify", "crs_geom"),
    _q("check validity of parcel boundaries and report errors", [], "g_check_valid", "crs_geom"),
    _q("reproject county boundaries to state plane coordinate system", ["L3_01_02_03"], "g_reproject_county", "crs_geom"),
    _q("fix self-intersections in zoning polygon layer", ["L3_02_07_01"], "g_fix_self", "crs_geom"),
    _q("simplify road network geometry for web map display", ["L3_02_07_01"], "g_simplify_road", "crs_geom"),
    _q("validate topology of drainage network", [], "g_validate_drain", "crs_geom"),
    _q("reproject GPS points from lat/lon to local grid", ["L3_01_02_03"], "g_reproject_gps", "crs_geom"),
    _q("fix null geometries in address point layer", ["L3_02_07_01"], "g_fix_null", "crs_geom"),
    _q("simplify elevation contours for regional map", ["L3_02_07_01"], "g_simplify_contour", "crs_geom"),
    _q("check geometry validity of imported CAD data", [], "g_check_cad", "crs_geom"),
    _q("reproject mining lease boundaries to local mine grid", ["L3_01_02_03"], "g_reproject_mine", "crs_geom"),
    _q("fix ring orientation errors in watershed polygons", ["L3_02_07_01"], "g_fix_ring", "crs_geom"),
    _q("simplify protected area boundaries for atlas printing", ["L3_02_07_01"], "g_simplify_pa", "crs_geom"),
    _q("validate geometry of imported shapefile from client", [], "g_validate_client", "crs_geom"),
    _q("reproject soil survey maps to match project CRS", ["L3_01_02_03"], "g_reproject_soil", "crs_geom"),
    _q("fix topology errors in administrative boundary layer", ["L3_02_07_01"], "g_fix_topo", "crs_geom"),
    _q("simplify forest stand boundaries for mobile app", ["L3_02_07_01"], "g_simplify_forest", "crs_geom"),
    _q("check validity of field-collected GPS polygons", [], "g_check_field", "crs_geom"),

    # ── 20: Low-frequency / uncertain guard ──
    _q("create voronoi polygons from weather station points", [], "u_voronoi", "uncertain"),
    _q("generate regular grid of sampling points at 1km spacing", [], "u_grid", "uncertain"),
    _q("convert polygon boundaries to polylines for cartography", [], "u_poly2line", "uncertain"),
    _q("compute minimum bounding geometry for animal tracking points", [], "u_mbg", "uncertain"),
    _q("extract vertices from polygon boundaries for analysis", [], "u_vertices", "uncertain"),
    _q("smooth elevation contour lines for publication map", [], "u_smooth", "uncertain"),
    _q("delete holes smaller than 100sqm in building footprints", [], "u_deleteholes", "uncertain"),
    _q("split lines at intersection points for network analysis", [], "u_split", "uncertain"),
    _q("generate points along railway lines every 500m", [], "u_pts_along", "uncertain"),
    _q("compute line intersections as point layer", [], "u_line_intersect", "uncertain"),
    _q("delete duplicate geometries from merged dataset", [], "u_dedup", "uncertain"),
    _q("create random selection of 100 points from input layer", [], "u_random_sel", "uncertain"),
    _q("convert singlepart geometries to multipart by attribute", [], "u_single2multi", "uncertain"),
    _q("compute contours at 10m interval from 5m DEM", [], "u_contour", "uncertain"),
    _q("create heatmap from point observations for density mapping", [], "u_heatmap", "uncertain"),
    _q("snap road endpoints to intersection vertices", [], "u_snap", "uncertain"),
    _q("create concave hull around species occurrence points", [], "u_concave", "uncertain"),
    _q("generate Thiessen polygons from rain gauge network", [], "u_thiessen", "uncertain"),
    _q("delaunay triangulation of borehole points", [], "u_delaunay", "uncertain"),
    _q("convex hull of archaeological site locations", [], "u_convex", "uncertain"),
]


# ── Evaluation ─────────────────────────────────────────────────────

@dataclass
class QueryResult:
    label: str
    category: str
    task_text: str
    l3_codes: list[str]
    top1_score: float = 0.0
    top1_quality: float = 0.0
    top1_chain: list[str] = field(default_factory=list)
    top1_modality: str = ""
    l3_bridge_hit: bool = False
    native_bridge_hit: bool = False
    combined_bridge_hit: bool = False
    modality_match: bool = False
    accepted_boost: bool = False
    rejected_leak: bool = False
    unique_in_top5: int = 0
    score_components: dict = field(default_factory=dict)


def evaluate_retriever(retriever, evaluator, queries, retriever_name=""):
    results = []
    for q in queries:
        candidates = retriever.retrieve(
            task_text=q["task_text"],
            l3_codes=q.get("l3_codes", []),
            prefer_vector=q.get("prefer_vector", False),
            prefer_raster=q.get("prefer_raster", False),
            prefer_mixed=q.get("prefer_mixed", False),
            k=5,
            evaluator=evaluator,
        )
        top1 = candidates[0] if candidates else None
        top5 = candidates[:5]

        l3_bridge = any(c.l3_sequence and len(c.l3_sequence) > 0 for c in top5)
        # QGIS-native bridge: check if any top-5 candidate uses native bridge operators
        NATIVE_BRIDGE_OPS = {"native:reprojectlayer", "qgis:reprojectlayer"}
        native_bridge = any(
            any(op.lower() in NATIVE_BRIDGE_OPS for op in c.qgis_ops)
            for c in top5
        )
        combined_bridge = l3_bridge or native_bridge
        # Modality match
        if q.get("prefer_mixed"):
            mod_match = (
                top1.quality.get("is_mixed", False)
                if top1 else False
            )
        else:
            mod_match = bool(
                top1
                and (
                    (q.get("prefer_vector") and top1.quality.get("is_pure_vector", False))
                    or (q.get("prefer_raster") and top1.quality.get("is_pure_raster", False))
                )
            )

        # Accepted contribution: did top-1 use a newly mapped operator?
        accepted_boost = (
            top1 and any(op.lower() in ACCEPTED_ALG_IDS for op in top1.qgis_ops)
        ) if top1 else False

        # Rejected leakage: did top-1 include a rejected alg_id?
        rejected_leak = (
            top1 and any(op.lower() in REJECTED_ALG_IDS for op in top1.qgis_ops)
        ) if top1 else False

        r = QueryResult(
            label=q.get("label", ""),
            category=q.get("category", ""),
            task_text=q["task_text"],
            l3_codes=q.get("l3_codes", []),
            top1_score=top1.score if top1 else 0.0,
            top1_quality=evaluator.evaluate(top1.qgis_ops).quality_score if top1 else 0.0,
            top1_chain=top1.qgis_ops if top1 else [],
            top1_modality=("pure_vector" if top1.quality.get("is_pure_vector")
                           else "pure_raster" if top1.quality.get("is_pure_raster")
                           else "mixed") if top1 else "",
            l3_bridge_hit=l3_bridge,
            native_bridge_hit=native_bridge,
            combined_bridge_hit=combined_bridge,
            modality_match=mod_match,
            accepted_boost=accepted_boost,
            rejected_leak=rejected_leak,
            unique_in_top5=len(set(tuple(c.qgis_ops) for c in top5)),
            score_components=top1.score_components if top1 else {},
        )
        results.append(r)
    return results


# ── Reporting ──────────────────────────────────────────────────────

def _ci(rate, n):
    if n == 0: return "N/A"
    se = math.sqrt(rate * (1 - rate) / n)
    return f"[{max(0, rate - 1.96 * se):.4f}, {min(1, rate + 1.96 * se):.4f}]"


def print_report(name, results):
    n = len(results)
    avg_score = sum(r.top1_score for r in results) / n
    avg_quality = sum(r.top1_quality for r in results) / n
    l3_hits = sum(1 for r in results if r.l3_bridge_hit)
    native_hits = sum(1 for r in results if r.native_bridge_hit)
    combined_hits = sum(1 for r in results if r.combined_bridge_hit)
    mod_hits = sum(1 for r in results if r.modality_match)
    accepted = sum(1 for r in results if r.accepted_boost)
    rejected = sum(1 for r in results if r.rejected_leak)
    avg_uniq = sum(r.unique_in_top5 for r in results) / n

    print(f"\n{'='*60}")
    print(f"  {name} ({n} queries)")
    print(f"{'='*60}")
    print(f"  Avg score:           {avg_score:.4f}")
    print(f"  Avg quality:         {avg_quality:.4f}")
    print(f"  L3 bridge hits:      {l3_hits}/{n} ({l3_hits/n*100:.1f}%)")
    print(f"  Native bridge hits:  {native_hits}/{n} ({native_hits/n*100:.1f}%)")
    print(f"  Combined bridge:     {combined_hits}/{n} ({combined_hits/n*100:.1f}%)")
    print(f"  Modality matches:    {mod_hits}/{n} ({mod_hits/n*100:.1f}%)")
    print(f"  Accepted boost:      {accepted}/{n} ({accepted/n*100:.1f}%)")
    leakage_str = f"  !! REJECTED LEAKAGE: {rejected}/{n}" if rejected else f"  Rejected leakage:    0/{n} OK"
    print(f"  Avg unique in top-5: {avg_uniq:.1f}")

    # Per category
    cats = defaultdict(list)
    for r in results:
        cats[r.category].append(r)
    print(f"\n  Per category:")
    for cat in ["vec_analysis", "vec_filter", "raster_proc", "vec_rast_mix", "crs_geom", "uncertain"]:
        subset = cats.get(cat, [])
        if not subset:
            continue
        m = len(subset)
        q = sum(r.top1_quality for r in subset) / m
        l3 = sum(1 for r in subset if r.l3_bridge_hit) / m
        mod = sum(1 for r in subset if r.modality_match) / m
        rej = sum(1 for r in subset if r.rejected_leak)
        rej_str = f" LEAK={rej}" if rej else ""
        print(f"    {cat:20s}: q={q:.3f}  L3={l3:.0%}  mod={mod:.0%}  n={m}{rej_str}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-samples", type=int, default=200)
    parser.add_argument("--audit-samples", type=int, default=20)
    args = parser.parse_args(argv)

    n = min(args.num_samples, len(QUERIES))
    queries = QUERIES[:n]
    print(f"QGIS Chain Retrieval Ablation — {n} stratified queries")
    print(f"Categories: {Counter(q['category'] for q in queries)}")

    ret, ev = build_qgis_chain_planner(ORIGINAL_DS, CATALOG)
    results = evaluate_retriever(ret, ev, queries)
    print_report("Original (post-crosswalk + semantic tags)", results)

    # Audit: show accepted boost examples
    boosted = [r for r in results if r.accepted_boost]
    if boosted:
        print(f"\n  Accepted mapping contribution examples ({len(boosted)} total):")
        for r in boosted[:8]:
            acc_ops = [op for op in r.top1_chain if op.lower() in ACCEPTED_ALG_IDS]
            print(f"    [{r.category}] {r.label}: used {acc_ops}")

    leaked = [r for r in results if r.rejected_leak]
    if leaked:
        print(f"\n  !! REJECTED LEAKAGE ({len(leaked)} total):")
        for r in leaked:
            bad = [op for op in r.top1_chain if op.lower() in REJECTED_ALG_IDS]
            print(f"    [{r.category}] {r.label}: LEAKED {bad}")
    else:
        print(f"\n  OK Zero rejected leakage detected.")


if __name__ == "__main__":
    main()
