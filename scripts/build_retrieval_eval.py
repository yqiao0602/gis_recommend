#!/usr/bin/env python3
"""P0+P1: Fix retriever index + recall eval with 3 query types.

1. Merges facts_summary text into chain records → enriched retriever index
2. Evaluates recall@k for: full facts, short user-like, operator-masked queries

Usage:
    python scripts/build_retrieval_eval.py
"""

from __future__ import annotations

import argparse, csv, json, math, random, re, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

FACTS = ROOT / "爬取GithubQGIS" / "facts_summary1000.csv"
V2_DS = ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl"
OUT_DS = ROOT / "outputs_v2" / "qgis_chain_dataset_v2_enriched_v3.jsonl"
OUT_DIR = ROOT / "outputs_v2" / "diagnostics" / "retrieval_recall_v3"

SEED = 42
random.seed(SEED)

VECTOR_OPS = {"buffer","clip","dissolve","intersection","difference","mergevectorlayers",
    "extractbyexpression","extractbylocation","joinattributesbylocation","joinattributestable",
    "reprojectlayer","fixgeometries","simplifygeometries","snapgeometries","centroids",
    "creategrid","polygonstolines","splitwithlines","refactorfields","symmetricaldifference"}
RASTER_OPS = {"cliprasterbymasklayer","cliprasterbyextent","rastercalculator","warpreproject",
    "fillnodata","zonalstatisticsfb","buildvirtualraster","reclassifybytable","translate","merge"}

def tokenize(text):
    return {t.lower() for t in re.findall(r"[a-z0-9_]{3,}", str(text))}

def jaccard(a,b):
    if not a or not b: return 0.0
    return len(a&b)/len(a|b)

def mask_ops(text):
    """Remove explicit operator keywords from text."""
    for kw in list(VECTOR_OPS)+list(RASTER_OPS):
        text = re.sub(r'\b'+kw+r'\b','',text,flags=re.IGNORECASE)
    text = re.sub(r'from\s+\d{4}','',text)  # remove years
    return re.sub(r'\s+',' ',text).strip()

def load_records():
    facts = {}
    with open(FACTS,"r",encoding="utf-8",errors="replace") as f:
        for row in csv.DictReader(f):
            facts[row["File Name"].strip()] = row
    records=[]
    with V2_DS.open("r",encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            r=json.loads(line); ops=r.get("qgis_ops",[])
            if len(ops)<2: continue
            fn=r.get("source_file","")
            fact=facts.get(fn,{})
            task_name=fact.get("Task Name","")
            task_desc=fact.get("Task Description","")
            task_type=fact.get("Task Type","")
            op_names=" ".join(r.get("operator_names",ops))
            has_fact=bool(fact)
            # Build index texts
            idx_full=f"{task_name} {task_desc} {task_type} {op_names}".strip()
            idx_short=f"{task_name} {op_names}".strip() if task_name else op_names
            idx_masked=mask_ops(idx_full)
            records.append({"file":fn,"ops":ops,"has_fact":has_fact,
                "idx_full":idx_full,"idx_short":idx_short,"idx_masked":idx_masked,
                "task_name":task_name,"task_desc":task_desc,"op_names":op_names})
    return records

def build_index(records, key="idx_full"):
    return [{"file":r["file"],"ops":r["ops"],"tokens":tokenize(r[key])} for r in records]

def eval_recall(index, records, query_key="idx_full", label=""):
    hits=defaultdict(int); n=len(records)
    for r in records:
        q=tokenize(r[query_key])
        scored=[(jaccard(q, e["tokens"]),e) for e in index]
        scored.sort(key=lambda x:-x[0])
        gold=tuple(r["ops"])
        for rank,(_,e) in enumerate(scored[:20]):
            if tuple(e["ops"])==gold:
                for kk in [1,5,10,20]:
                    if rank<kk: hits[kk]+=1
                break
    return {kk:hits[kk]/max(n,1) for kk in [1,5,10,20]}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-ds",default=str(OUT_DS))
    args=parser.parse_args(argv)
    records=load_records()
    has_fact=sum(1 for r in records if r["has_fact"])
    print(f"Records: {len(records)}, with facts: {has_fact} ({has_fact/len(records)*100:.1f}%)")

    # Save enriched dataset with quality fields + semantic tags for retriever
    Path(args.output_ds).parent.mkdir(parents=True,exist_ok=True)
    legacy = {}
    with open(CATALOG,"r",encoding="utf-8",errors="replace") as f:
        for row in csv.reader(f):
            if len(row) < 6: continue
            aid = row[5].strip().lower(); dt = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector","raster"): dt = col.strip(); break
            legacy[aid] = dt

    # Semantic tags (sync with retriever)
    SEM_TAGS = {
        "reprojectlayer":"vector_crs_transform","fixgeometries":"geometry_repair",
        "snapgeometries":"geometry_repair","simplifygeometries":"geometry_simplify",
        "smoothgeometry":"geometry_smooth","checkvalidity":"geometry_validation",
        "deleteholes":"geometry_cleanup","deleteduplicategeometries":"geometry_dedup",
        "polygonstolines":"geometry_boundary","linestopolygons":"geometry_conversion",
        "extractvertices":"geometry_vertices","pointsalonglines":"geometry_sampling",
        "splitwithlines":"geometry_split","createspatialindex":"index_maintenance",
        "saveselectedfeatures":"data_export","savefeatures":"data_export",
        "rasterize":"rasterize_convert","polygonize":"polygonize_convert",
        "pixelstopolygons":"polygonize_convert","contour":"surface_derivative",
        "joinattributestable":"table_join","joinattributesbylocation":"spatial_join",
        "creategrid":"grid_generation","extractbyexpression":"attribute_filter",
        "selectbyexpression":"attribute_select","extractbylocation":"spatial_filter",
        "selectbylocation":"spatial_select","refactorfields":"field_restructure",
        "renametablefield":"field_rename","deletecolumn":"field_remove",
        "addautoincrementalfield":"field_add","fieldcalculator":"field_calculate",
        "centroids":"centroid_extract","minimumboundinggeometry":"bounding_geometry",
        "symmetricaldifference":"spatial_overlay","mergevectorlayers":"layer_merge",
        "multiringconstantbuffer":"buffer_variant",
        "voronoi":"voronoi","thiessen":"voronoi",
        "heatmapkerneldensityestimation":"density_heatmap",
        "joinbynearest":"nearest_neighbor","distancetonearesthub":"nearest_neighbor",
        "concavehull":"concave_hull","convexhull":"convex_hull",
        "delaunaytriangulation":"triangulation",
        "rastersampling":"raster_sampling","rastersurfacevolume":"surface_volume",
        "zonalstatistics":"zonal_statistics","zonalstatisticsfb":"zonal_statistics",
        "extractbyextent":"spatial_clip","difference":"spatial_overlay",
        "countpointsinpolygon":"point_count",
        "randompointsinpolygons":"random_sampling",
    }
    with open(args.output_ds,"w",encoding="utf-8") as f:
        for r in records:
            ops = r["ops"]
            vc = sum(1 for o in ops if legacy.get(o.lower(),"")=="vector")
            rc = sum(1 for o in ops if legacy.get(o.lower(),"")=="raster")
            modality = "vector" if vc>rc else ("raster" if rc>vc else "mixed")
            # Derive semantic tags
            tags = []; seen_s = set()
            for o in ops:
                n = o.lower().replace("native:","").replace("qgis:","").replace("gdal:","")
                for kw, tag in sorted(SEM_TAGS.items(), key=lambda x:-len(x[0])):
                    if kw in n and tag not in seen_s:
                        tags.append(tag); seen_s.add(tag); break
            f.write(json.dumps({
                "source_file":r["file"],"qgis_ops":ops,
                "operator_names":r.get("op_names","").split(),
                "task_name":r["task_name"],"task_description":r["task_desc"],
                "idx_full":r["idx_full"],"idx_short":r["idx_short"],
                "quality":{"is_pure_vector":modality=="vector","is_pure_raster":modality=="raster",
                            "is_mixed":modality=="mixed","all_in_catalog":True},
                "qgis_semantic_tags":tags,
            },ensure_ascii=False)+"\n")
    print(f"Enriched DS: {args.output_ds}")

    # Evaluate
    idx_full=build_index(records,"idx_full")
    idx_short=build_index(records,"idx_short")
    idx_masked=build_index(records,"idx_masked")

    r_full=eval_recall(idx_full,records,"idx_full","full facts")
    r_short=eval_recall(idx_short,records,"idx_short","short query")
    r_masked=eval_recall(idx_masked,records,"idx_masked","operator-masked")

    print(f"\n{'Query type':25s} {'R@1':>8s} {'R@5':>8s} {'R@10':>8s} {'R@20':>8s}")
    for label,res in [("Full facts",r_full),("Short (name only)",r_short),("Op-masked",r_masked)]:
        print(f"{label:25s} {res[1]*100:>7.1f}% {res[5]*100:>7.1f}% {res[10]*100:>7.1f}% {res[20]*100:>7.1f}%")

    OUT_DIR.mkdir(parents=True,exist_ok=True)
    with (OUT_DIR/"recall_report.json").open("w",encoding="utf-8") as f:
        json.dump({"n":len(records),"full":r_full,"short":r_short,"masked":r_masked},f,indent=2)
    print(f"\nReport: {OUT_DIR}/recall_report.json")


if __name__=="__main__": main()
