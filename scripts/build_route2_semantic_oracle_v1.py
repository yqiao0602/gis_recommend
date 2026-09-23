"""Build the Route-2 Oracle Grounding diagnostic inputs (v1).

For each v2a test row, replaces task_text with the GOLD SEMANTIC WORKFLOW
rendered in B1's exact target vocabulary/serialization, leaving gold
processes/links untouched so evaluate_dev.py scores it identically.
Diagnostic only — does not modify test-111, gold, scorer, or any arm.

Mapping: deterministic QGIS operator_id -> semantic category table below
(37-category GEE semantic vocabulary, same as B1 stage-1 targets).
Serialization: ' -> ' joined, consecutive duplicates dropped (matches the
B1 pipeline's consecutive-dedup step; run_cap is a no-op after dedup).

Borderline calls are marked BORDERLINE in comments and summarized in the
coverage report. Unknown operators fail closed (script errors) so the
table can never silently drift.
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/reports/route2_p0_contract/test111_final_v1"

# category constants (same vocabulary as scripts/gee_route2_semantic_workflow_v1.py)
TEMPORAL, SPATIAL_F, ATTR_F = "TEMPORAL_FILTER", "SPATIAL_FILTER", "ATTRIBUTE_FILTER"
BAND_SEL, ARITH, MASKING = "BAND_SELECT", "BAND_ARITHMETIC", "MASKING"
AGG, REGSTAT, CLASSIF = "AGGREGATION", "REGIONAL_STATS", "CLASSIFICATION"
CLIP, VGEOM, NEIGH = "SPATIAL_CLIP", "VECTOR_GEOMETRY", "NEIGHBORHOOD"
TERRAIN, COMPOSITE, SJOIN = "TERRAIN_DERIVED", "COMPOSITE", "SPATIAL_JOIN"
RESAMP, EXPORT, COLMGMT = "RESAMPLE_REPROJECT", "EXPORT_OUTPUT", "COLLECTION_MGMT"
RLOAD, VLOAD, GEOMDEF = "RASTER_LOAD", "VECTOR_LOAD", "GEOMETRY_DEFINE"
R2V, V2R, OTHER = "RASTER_TO_VECTOR", "VECTOR_TO_RASTER", "OTHER_UNMAPPED"
THRESH = "THRESHOLD_LOGIC"

MAP = {
    # --- gdal ---
    "gdal:aspect": TERRAIN,
    "gdal:buildvirtualraster": COLMGMT,
    "gdal:cliprasterbyextent": CLIP,
    "gdal:cliprasterbymasklayer": CLIP,
    "gdal:clipvectorbyextent": CLIP,
    "gdal:clipvectorbypolygon": CLIP,
    "gdal:contour": R2V,
    "gdal:contour_polygon": R2V,
    "gdal:convertformat": COLMGMT,
    "gdal:fillnodata": NEIGH,  # BORDERLINE: interpolation fill ~ neighborhood
    "gdal:importvectorintopostgisdatabaseavailableconnections": EXPORT,
    "gdal:merge": COMPOSITE,
    "gdal:pansharp": COMPOSITE,
    "gdal:polygonize": R2V,
    "gdal:rastercalculator": ARITH,
    "gdal:rasterize": V2R,
    "gdal:rasterize_over": V2R,
    "gdal:rasterize_over_fixed_value": V2R,
    "gdal:rearrange_bands": BAND_SEL,
    "gdal:sieve": NEIGH,  # BORDERLINE: mode-filter cleanup
    "gdal:translate": COLMGMT,
    "gdal:warpreproject": RESAMP,
    # --- grass7 ---
    "grass7:r.drain": TERRAIN,  # BORDERLINE: flow-path trace
    "grass7:r.fill.dir": TERRAIN,
    "grass7:r.rescale.eq": ARITH,
    "grass7:r.rgb": BAND_SEL,  # BORDERLINE: ~ composite of 3 bands
    "grass7:r.thin": NEIGH,
    "grass7:r.to.vect": R2V,
    "grass7:r.walk.coords": TERRAIN,
    "grass7:r.water.outlet": TERRAIN,
    "grass7:r.watershed": TERRAIN,
    "grass7:v.distance": REGSTAT,  # BORDERLINE: distance analysis -> stats bucket
    "grass7:v.generalize": VGEOM,
    "grass7:v.split": VGEOM,
    # --- native: attribute/schema management ---
    "native:addautoincrementalfield": COLMGMT,
    "native:addfieldtoattributestable": COLMGMT,
    "native:deletecolumn": COLMGMT,
    "native:refactorfields": COLMGMT,
    "native:renametablefield": COLMGMT,
    "native:retainfields": COLMGMT,
    "native:createspatialindex": COLMGMT,
    "native:renamelayer": COLMGMT,
    "native:setlayerstyle": COLMGMT,
    "native:package": COLMGMT,
    "native:filedownloader": COLMGMT,
    "native:spatialiteexecutesql": COLMGMT,  # BORDERLINE: generic execute
    "native:splitvectorlayer": COLMGMT,
    "native:orderbyexpression": COLMGMT,
    "native:removeduplicatesbyattribute": COLMGMT,
    # --- native: terrain ---
    "native:aspect": TERRAIN,
    "native:slope": TERRAIN,
    "native:ruggednessindex": TERRAIN,
    "native:setzfromraster": TERRAIN,  # BORDERLINE: raster->vector z transfer
    # --- native: neighborhood/zonal/stats ---
    "native:cellstatistics": ARITH,  # BORDERLINE: per-cell across-band stats
    "native:zonalstatistics": REGSTAT,
    "native:zonalstatisticsfb": REGSTAT,
    "native:zonalhistogram": REGSTAT,
    "native:rasterlayerstatistics": REGSTAT,
    "native:rasterlayeruniquevaluesreport": REGSTAT,
    "native:rastersampling": REGSTAT,  # BORDERLINE: sample values at points
    "native:countpointsinpolygon": REGSTAT,
    "native:meancoordinates": REGSTAT,
    "native:calculatevectoroverlaps": REGSTAT,
    "native:fillnodata": NEIGH,
    "native:fuzzifyrasterlinearmembership": THRESH,  # BORDERLINE: membership ~ threshold logic
    "native:reclassifybytable": THRESH,
    "native:rasterbooleanand": ARITH,  # BORDERLINE: logical combine of rasters
    "native:polygonize": R2V,
    "native:pixelstopoints": R2V,
    "native:pixelstopolygons": R2V,
    "native:generatepointspixelcentroidsinsidepolygons": R2V,
    "native:createconstantrasterlayer": RLOAD,  # BORDERLINE: synthetic source
    # --- native: vector geometry ---
    "native:buffer": VGEOM,
    "native:centroids": VGEOM,
    "native:convexhull": VGEOM,
    "native:densifygeometriesgivenaninterval": VGEOM,
    "native:explodelines": VGEOM,
    "native:extendlines": VGEOM,
    "native:mergelines": VGEOM,
    "native:simplifygeometries": VGEOM,
    "native:smoothgeometry": VGEOM,
    "native:snapgeometries": VGEOM,
    "native:splitlinesbylength": VGEOM,
    "native:translategeometry": VGEOM,
    "native:multiparttosingleparts": VGEOM,
    "native:removeduplicatevertices": VGEOM,
    "native:fixgeometries": VGEOM,
    "native:deleteholes": VGEOM,
    "native:collect": VGEOM,
    "native:dissolve": VGEOM,
    "native:deleteduplicategeometries": VGEOM,
    "native:extractvertices": VGEOM,
    "native:extractspecificvertices": VGEOM,
    "native:dropmzvalues": VGEOM,
    "native:geometrybyexpression": VGEOM,
    "native:polygonstolines": VGEOM,
    "native:orientedminimumboundingbox": VGEOM,
    "native:pointsalonglines": VGEOM,
    "native:pointstopath": VGEOM,
    "native:serviceareafromlayer": VGEOM,  # BORDERLINE: network analysis
    "native:difference": CLIP,
    "native:intersection": CLIP,
    "native:clip": CLIP,
    "native:extractbyextent": SPATIAL_F,
    "native:extractbylocation": SPATIAL_F,
    "native:selectbylocation": SPATIAL_F,
    "native:extractbyattribute": ATTR_F,
    "native:extractbyexpression": ATTR_F,
    "native:aggregate": AGG,
    "native:assignprojection": RESAMP,
    "native:condition": THRESH,
    "native:fieldcalculator": ARITH,  # BORDERLINE: attribute arithmetic
    "native:mergevectorlayers": COMPOSITE,
    "native:reprojectlayer": RESAMP,
    "native:splitwithlines": VGEOM,
    "saga:profilesfromlines": TERRAIN,
    "native:joinattributesbylocation": SJOIN,
    "native:joinbynearest": SJOIN,
    "native:union": SJOIN,  # BORDERLINE: overlay union ~ join semantics
    "native:joinattributestable": SJOIN,  # BORDERLINE: attribute join (non-spatial)
    # --- native: sources/geometry define ---
    "native:creategrid": GEOMDEF,
    "native:extenttolayer": GEOMDEF,
    "native:polygonfromlayerextent": GEOMDEF,
    "native:createpointslayerfromtable": VLOAD,
    "native:loadlayer": VLOAD,  # BORDERLINE: loads vector or raster
    "native:savefeatures": EXPORT,
    "native:saveselectedfeatures": EXPORT,
    # --- qgis: ---
    "qgis:advancedpythonfieldcalculator": ARITH,  # BORDERLINE: attribute arithmetic
    "qgis:basicstatisticsforfields": REGSTAT,
    "qgis:definecurrentprojection": RESAMP,
    "qgis:delaunaytriangulation": VGEOM,
    "qgis:distancematrix": REGSTAT,
    "qgis:eliminateselectedpolygons": VGEOM,
    "qgis:exportaddgeometrycolumns": COLMGMT,
    "qgis:idwinterpolation": NEIGH,  # BORDERLINE: interpolation ~ neighborhood est.
    "qgis:joinbylocationsummary": SJOIN,
    "qgis:linestopolygons": VGEOM,
    "qgis:listuniquevalues": REGSTAT,
    "qgis:randompointsinlayerbounds": VLOAD,
    "qgis:randompointsinsidepolygons": VLOAD,
    "qgis:rastercalculator": ARITH,
    "qgis:selectbyattribute": ATTR_F,
    "qgis:setstyleforrasterlayer": COLMGMT,
    "qgis:setstyleforvectorlayer": COLMGMT,
    "qgis:statisticsbycategories": AGG,
    "qgis:tininterpolation": NEIGH,
    "qgis:variabledistancebuffer": VGEOM,
    # --- saga ---
    "saga:intersect": CLIP,
}


def main() -> None:
    gold_rows = [json.loads(l) for l in
                 (BASE / "v2a_A_test.gold.jsonl").open(encoding="utf-8")]

    usage, unmapped = {}, set()
    oracle_rows = []
    for r in gold_rows:
        cats, prev = [], None
        for p in r["processes"]:
            op = p["operator_id"]
            if op not in MAP:
                unmapped.add(op)
                continue
            cat = MAP[op]
            usage[cat] = usage.get(cat, 0) + 1
            if cat != prev:  # consecutive dedup, same as B1 pipeline
                cats.append(cat)
            prev = cat
        chain = " -> ".join(cats)
        oracle_rows.append({**r, "task_text": chain,
                            "oracle_chain": chain, "orig_task_text": r["task_text"]})

    if unmapped:
        raise SystemExit(f"FAIL-CLOSED: unmapped operators: {sorted(unmapped)}")

    out = BASE / "oracle_semantic_input_v1.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in oracle_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    coverage = {
        "rows": len(oracle_rows),
        "distinct_operators_mapped": len(MAP),
        "category_usage_over_gold_steps": dict(sorted(usage.items(), key=lambda kv: -kv[1])),
    }
    (BASE / "oracle_mapping_coverage_v1.json").write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(coverage, indent=2, ensure_ascii=False))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
