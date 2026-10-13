#!/usr/bin/env python3
"""Curated reverse reference table: dev-120's 133 QGIS operator_ids -> the
21-family planning vocabulary. PURPOSE: diagnostic reference gold for
blueprint-quality measurement ONLY (owner ruling: the reverse->forward
round trip must never be presented as a grounding upper bound).
Assignments are best-effort semantic; AMBIG notes mark least-fitted cases
(structural vocabulary gaps - themselves a finding for L1 attribution)."""
import json

F = {
 # ── LOAD roles ──
 "native:filedownloader": ("RASTER_LOAD", "download role; raster/vector ambiguous"),
 "native:loadlayer": ("RASTER_LOAD", "load role; raster/vector ambiguous"),
 "native:createconstantrasterlayer": ("RASTER_LOAD", "data creation ~ load"),
 # ── ATTRIBUTE_FILTER (attribute subsetting / field ops) ──
 "native:fieldcalculator": ("ATTRIBUTE_FILTER", None),
 "native:refactorfields": ("ATTRIBUTE_FILTER", None),
 "native:deletecolumn": ("ATTRIBUTE_FILTER", None),
 "native:joinattributestable": ("ATTRIBUTE_FILTER", None),
 "native:extractbyexpression": ("ATTRIBUTE_FILTER", None),
 "qgis:selectbyexpression": ("ATTRIBUTE_FILTER", None),
 "qgis:advancedpythonfieldcalculator": ("ATTRIBUTE_FILTER", None),
 "native:extractbyattribute": ("ATTRIBUTE_FILTER", None),
 "native:retainfields": ("ATTRIBUTE_FILTER", None),
 "native:addautoincrementalfield": ("ATTRIBUTE_FILTER", None),
 "qgis:exportaddgeometrycolumns": ("ATTRIBUTE_FILTER", None),
 "native:removeduplicatesbyattribute": ("ATTRIBUTE_FILTER", None),
 "native:renametablefield": ("ATTRIBUTE_FILTER", None),
 "native:addxyfields": ("ATTRIBUTE_FILTER", None),
 # ── SPATIAL_FILTER (location-based selection / spatial join) ──
 "native:extractbylocation": ("SPATIAL_FILTER", None),
 "native:selectbylocation": ("SPATIAL_FILTER", None),
 "native:joinattributesbylocation": ("SPATIAL_FILTER", None),
 "native:extractwithindistance": ("SPATIAL_FILTER", None),
 "native:joinbynearest": ("SPATIAL_FILTER", None),
 "qgis:randomselection": ("SPATIAL_FILTER", "random subset role"),
 "qgis:randomselectionwithinsubsets": ("SPATIAL_FILTER", "random subset role"),
 # ── SPATIAL_CLIP ──
 "native:clip": ("SPATIAL_CLIP", None),
 "gdal:cliprasterbymasklayer": ("SPATIAL_CLIP", None),
 "gdal:cliprasterbyextent": ("SPATIAL_CLIP", None),
 "saga:cliprasterwithpolygon": ("SPATIAL_CLIP", None),
 "native:extractbyextent": ("SPATIAL_CLIP", None),
 # ── COLLECTION_MGMT (merge / manage collections) ──
 "native:mergevectorlayers": ("COLLECTION_MGMT", None),
 "gdal:merge": ("COLLECTION_MGMT", None),
 "gdal:buildvirtualraster": ("COLLECTION_MGMT", None),
 "native:createspatialindex": ("COLLECTION_MGMT", None),
 "native:orderbyexpression": ("COLLECTION_MGMT", None),
 "native:setlayerstyle": ("COLLECTION_MGMT", None),
 "native:setprojectvariable": ("COLLECTION_MGMT", None),
 # ── AGGREGATION (zonal / categorical / layer reductions) ──
 "native:zonalstatisticsfb": ("AGGREGATION", None),
 "native:zonalstatistics": ("AGGREGATION", None),
 "native:aggregate": ("AGGREGATION", None),
 "qgis:statisticsbycategories": ("AGGREGATION", None),
 "native:countpointsinpolygon": ("AGGREGATION", None),
 "native:rasterlayerstatistics": ("AGGREGATION", None),
 "native:rasterlayeruniquevaluesreport": ("AGGREGATION", None),
 "qgis:listuniquevalues": ("AGGREGATION", None),
 "native:rastersampling": ("AGGREGATION", "value extraction; BAND_SELECT alt"),
 # ── BAND_ARITHMETIC ──
 "gdal:rastercalculator": ("BAND_ARITHMETIC", None),
 "qgis:rastercalculator": ("BAND_ARITHMETIC", None),
 "saga:rastercalculator": ("BAND_ARITHMETIC", None),
 "gdal:rasterize_over": ("BAND_ARITHMETIC", "burn values; conversion alt"),
 # ── THRESHOLD_LOGIC ──
 "native:reclassifybytable": ("THRESHOLD_LOGIC", None),
 "native:reclassifybylayer": ("THRESHOLD_LOGIC", None),
 "grass7:r.rescale.eq": ("THRESHOLD_LOGIC", None),
 # ── TERRAIN_DERIVED ──
 "native:slope": ("TERRAIN_DERIVED", None),
 "gdal:slope": ("TERRAIN_DERIVED", None),
 "gdal:aspect": ("TERRAIN_DERIVED", None),
 "gdal:hillshade": ("TERRAIN_DERIVED", None),
 "gdal:roughness": ("TERRAIN_DERIVED", None),
 "gdal:viewshed": ("TERRAIN_DERIVED", None),
 "grass7:r.watershed": ("TERRAIN_DERIVED", None),
 "grass7:r.water.outlet": ("TERRAIN_DERIVED", None),
 # ── NEIGHBORHOOD / distance / focal ──
 "gdal:sieve": ("NEIGHBORHOOD", None),
 "gdal:proximity": ("NEIGHBORHOOD", None),
 "qgis:distancematrix": ("NEIGHBORHOOD", None),
 "native:shortestpathpointtolayer": ("NEIGHBORHOOD", None),
 "native:shortestline": ("NEIGHBORHOOD", None),
 "grass7:r.cost": ("NEIGHBORHOOD", None),
 "qgis:distancetonearesthubpoints": ("NEIGHBORHOOD", None),
 "qgis:idwinterpolation": ("NEIGHBORHOOD", "interpolation; vocab gap"),
 "saga:triangulation": ("NEIGHBORHOOD", "interpolation; vocab gap"),
 "saga:simplefilter": ("NEIGHBORHOOD", None),
 # ── MASKING ──
 "grass7:r.null": ("MASKING", None),
 "saga:rastermasking": ("MASKING", None),
 # ── EXPORT_OUTPUT ──
 "gdal:translate": ("EXPORT_OUTPUT", "format conversion"),
 "native:saveselectedfeatures": ("EXPORT_OUTPUT", None),
 "native:savefeatures": ("EXPORT_OUTPUT", None),
 "native:exporttospreadsheet": ("EXPORT_OUTPUT", None),
 "native:package": ("EXPORT_OUTPUT", None),
 "gdal:importvectorintopostgisdatabaseavailableconnections": ("EXPORT_OUTPUT", "DB store"),
 # ── GEOMETRY_DEFINE (construct / CRS) ──
 "native:creategrid": ("GEOMETRY_DEFINE", None),
 "native:extenttolayer": ("GEOMETRY_DEFINE", None),
 "native:polygonfromlayerextent": ("GEOMETRY_DEFINE", None),
 "native:createpointslayerfromtable": ("GEOMETRY_DEFINE", None),
 "native:pointtolayer": ("GEOMETRY_DEFINE", None),
 "qgis:minimumboundinggeometry": ("GEOMETRY_DEFINE", None),
 "native:randompointsinextent": ("GEOMETRY_DEFINE", None),
 "gdal:extractprojection": ("GEOMETRY_DEFINE", "CRS"),
 "qgis:definecurrentprojection": ("GEOMETRY_DEFINE", "CRS"),
 "native:assignprojection": ("GEOMETRY_DEFINE", "CRS"),
 # ── VECTOR_GEOMETRY (geometry ops / overlays / conversions) ──
 "native:buffer": ("VECTOR_GEOMETRY", None),
 "native:dissolve": ("VECTOR_GEOMETRY", "aggregation-by-geometry"),
 "native:reprojectlayer": ("VECTOR_GEOMETRY", "CRS; vocab gap"),
 "gdal:warpreproject": ("VECTOR_GEOMETRY", "CRS; vocab gap"),
 "native:fixgeometries": ("VECTOR_GEOMETRY", None),
 "native:multiparttosingleparts": ("VECTOR_GEOMETRY", None),
 "native:intersection": ("VECTOR_GEOMETRY", None),
 "gdal:polygonize": ("VECTOR_GEOMETRY", "conversion"),
 "native:lineintersections": ("VECTOR_GEOMETRY", None),
 "native:centroids": ("VECTOR_GEOMETRY", None),
 "native:extractspecificvertices": ("VECTOR_GEOMETRY", None),
 "native:extractvertices": ("VECTOR_GEOMETRY", None),
 "native:difference": ("VECTOR_GEOMETRY", None),
 "native:simplifygeometries": ("VECTOR_GEOMETRY", None),
 "native:pointsalonglines": ("VECTOR_GEOMETRY", None),
 "native:union": ("VECTOR_GEOMETRY", None),
 "native:pixelstopoints": ("VECTOR_GEOMETRY", "conversion"),
 "native:pixelstopolygons": ("VECTOR_GEOMETRY", "conversion"),
 "native:polygonstolines": ("VECTOR_GEOMETRY", None),
 "native:dropgeometries": ("VECTOR_GEOMETRY", None),
 "native:splitlinesbylength": ("VECTOR_GEOMETRY", None),
 "grass7:v.clean": ("VECTOR_GEOMETRY", None),
 "grass7:v.overlay": ("VECTOR_GEOMETRY", None),
 "native:segmentizebymaxdistance": ("VECTOR_GEOMETRY", None),
 "native:symmetricaldifference": ("VECTOR_GEOMETRY", None),
 "native:deleteduplicategeometries": ("VECTOR_GEOMETRY", None),
 "native:geometrybyexpression": ("VECTOR_GEOMETRY", None),
 "native:hublines": ("VECTOR_GEOMETRY", None),
 "qgis:linestopolygons": ("VECTOR_GEOMETRY", None),
 "native:transect": ("VECTOR_GEOMETRY", None),
 "native:multiunion": ("VECTOR_GEOMETRY", None),
 "saga:convertpolygonstolines": ("VECTOR_GEOMETRY", None),
 "native:collect": ("VECTOR_GEOMETRY", None),
 "native:wedgebuffers": ("VECTOR_GEOMETRY", None),
 "native:snapgeometries": ("VECTOR_GEOMETRY", None),
 "native:mergelines": ("VECTOR_GEOMETRY", None),
 "saga:intersect": ("VECTOR_GEOMETRY", None),
 "gdal:rasterize": ("VECTOR_GEOMETRY", "vector->raster conversion; vocab gap"),
 "qgis:voronoipolygons": ("VECTOR_GEOMETRY", None),
 "native:splitwithlines": ("VECTOR_GEOMETRY", None),
 "native:pointonsurface": ("VECTOR_GEOMETRY", None),
 "native:multiringconstantbuffer": ("VECTOR_GEOMETRY", None),
 "native:pointstopath": ("VECTOR_GEOMETRY", None),
 "native:polygonize": ("VECTOR_GEOMETRY", "raster->vector conversion"),
 "saga:addrastervaluestopoints": ("BAND_SELECT", "raster value extraction"),
}

# families with NO dev-120 operator (structural vocabulary gaps - finding
# for L1 attribution: these blueprint stages can never match a gold process):
UNCOVERED_FAMILIES = ["TEMPORAL_FILTER", "CLASSIFICATION", "ITERATIVE_APPLY",
                      "REGIONAL_STATS", "SPECTRAL_INDEX"]

if __name__ == "__main__":
    import sys
    out = {"n_operators": len(F),
           "note": "diagnostic reference gold ONLY (owner ruling; reverse->forward round trip is not grounding evidence)",
           "assign": {k: {"family": v[0], "note": v[1]} for k, v in sorted(F.items())}}
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else
                        "qgis_op_family_reverse_v1.json", "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("operators mapped:", len(F))
