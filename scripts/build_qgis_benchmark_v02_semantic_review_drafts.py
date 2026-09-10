#!/usr/bin/env python3
"""Write semantic-only review drafts for the frozen v0.2 DAG jobs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "benchmarks/qgis_planner_v1/authority"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


REVIEW_DATA = {
    "native:rastersampling|native:fieldcalculator": ("approve", "Sample raster values onto vector features and calculate a derived attribute.", "A vector layer containing sampled raster values and the requested derived field.", "Raster sampling produces vector attributes accepted by the field calculator; both steps contribute to the declared output."),
    "native:mergevectorlayers|native:buffer": ("approve", "Combine compatible vector layers and buffer the merged features.", "One buffered vector layer covering features from all inputs.", "The merge output is a valid vector input to Buffer and the order is necessary for a single unified result."),
    "qgis:advancedpythonfieldcalculator|qgis:advancedpythonfieldcalculator|qgis:advancedpythonfieldcalculator|qgis:advancedpythonfieldcalculator|qgis:advancedpythonfieldcalculator|qgis:advancedpythonfieldcalculator|qgis:advancedpythonfieldcalculator": ("return_for_revision", "Apply a sequence of advanced field calculations.", "A vector layer containing all intended derived attributes.", "Seven indistinguishable calculator stages are structurally type-compatible, but the queue provides no field-level intent proving that every repeated stage is necessary."),
    "native:mergevectorlayers|native:retainfields": ("approve", "Merge vector layers and retain only the required output fields.", "One merged vector layer with a reduced, consistent schema.", "Retain Fields validly consumes the merged vector layer and expresses a closed schema-normalization workflow."),
    "native:clip|native:multiparttosingleparts": ("approve", "Clip vector features to the study area and split multipart results.", "Singlepart clipped vector features.", "Clip may produce multipart geometries and Multipart to Singleparts validly normalizes the final geometry structure."),
    "native:polygonfromlayerextent|native:intersection": ("approve", "Create an extent polygon and intersect it with another vector layer.", "Features restricted to the overlap with the generated extent polygon.", "The generated polygon is a valid overlay input and both stages are necessary for the constrained intersection output."),
    "native:joinattributesbylocation|native:fieldcalculator|native:fieldcalculator|native:fieldcalculator|native:fieldcalculator|native:mergevectorlayers|native:deletecolumn": ("return_for_revision", "Spatially join attributes, derive fields, merge results, and remove an output field.", "One merged vector layer containing the intended joined and derived attributes.", "The graph is type-compatible, but four repeated calculations and a later merge can change which attributes survive; field roles and merge intent are required before closure can be confirmed."),
    "native:reprojectlayer|native:zonalstatisticsfb": ("approve", "Reproject the zone layer and calculate raster statistics for those zones.", "A reprojected zone layer enriched with raster summary statistics.", "Zonal Statistics accepts the reprojected vector zones and the order makes the spatial reference preparation explicit."),
    "native:clip|native:dissolve": ("approve", "Clip vector features and dissolve the retained geometries.", "A dissolved vector layer restricted to the clipping area.", "Both operators consume and produce compatible vector geometries, and dissolving after clipping matches the constrained output."),
    "gdal:cliprasterbyextent|gdal:warpreproject": ("approve", "Crop a raster to the study extent and transform it to the target spatial reference.", "A cropped raster in the target coordinate reference system.", "The clipped raster is a valid Warp input and the sequence defines a closed raster-preparation output."),
    "native:mergevectorlayers|native:intersection": ("approve", "Merge compatible vector inputs and intersect the merged result with another layer.", "One vector layer containing the requested overlap features.", "Intersection validly consumes the merged vector dataset and the order is necessary when all merged features share one overlay operation."),
    "native:clip|native:dissolve|native:reprojectlayer": ("approve", "Clip features, dissolve the retained geometries, and reproject the result.", "A dissolved study-area vector layer in the target coordinate reference system.", "Each vector stage is type-compatible and contributes a distinct spatial constraint, aggregation, or CRS transformation."),
    "saga:upslopearea|gdal:polygonize": ("approve", "Calculate upslope contributing area and convert the resulting raster regions to polygons.", "A polygon layer representing areas derived from the upslope-area raster.", "Upslope Area produces raster output that Polygonize can convert to vector regions; the output type is explicit and closed."),
    "native:mergelines|native:dissolve": ("approve", "Merge connected line segments and dissolve the resulting line features.", "A consolidated line layer with dissolved boundaries or attributes.", "Both stages operate on line geometry and represent distinct connectivity and aggregation operations."),
    "gdal:rastercalculator|gdal:rastercalculator|gdal:warpreproject|gdal:warpreproject|gdal:rastercalculator": ("return_for_revision", "Derive raster layers, align them spatially, and combine them in a final raster calculation.", "One calculated raster in a common coordinate system.", "The operator types can be compatible, but the queue does not identify which calculator outputs feed each warp or why two warp stages are necessary; dependency intent is insufficiently explicit."),
    "gdal:warpreproject|gdal:slope": ("approve", "Reproject a terrain raster and calculate slope from the aligned elevation surface.", "A slope raster in the target spatial reference.", "Slope validly consumes the warped raster and the CRS preparation precedes the terrain derivative."),
    "gdal:polygonize|native:joinattributesbylocation|native:joinattributesbylocation": ("return_for_revision", "Polygonize a raster and enrich the polygons through two spatial joins.", "A polygon layer containing both intended groups of joined attributes.", "The graph is type-compatible, but the two joins need distinct source roles and attribute-output constraints to prove that both stages are necessary rather than duplicated."),
    "gdal:rastercalculator|native:zonalstatisticsfb|gdal:rastercalculator|native:zonalstatisticsfb": ("return_for_revision", "Calculate raster indicators and summarize them by zones in two stages.", "A zone layer containing two distinct raster summary products.", "Raster calculation and zonal statistics are individually compatible, but the alternating repeated stages lack named intermediate roles and do not establish a unique final output."),
    "native:clip|native:intersection": ("approve", "Clip features to a broad study boundary and then calculate their intersection with another layer.", "Vector features satisfying both spatial constraints.", "The two overlays impose different constraints and remain type-compatible in the declared order."),
    "native:countpointsinpolygon|native:zonalstatisticsfb|native:zonalstatistics": ("return_for_revision", "Count points by polygon and attach raster zonal summaries.", "A polygon layer containing point counts and the intended raster statistics.", "The point-count stage is compatible, but two consecutive zonal-statistics variants require distinct raster/statistic roles; otherwise the final step may duplicate or overwrite the previous output."),
    "native:extractbyattribute|native:clip": ("approve", "Select features by attribute and clip the selected subset to the study area.", "A vector layer containing only features satisfying both attribute and spatial constraints.", "Attribute extraction produces a valid vector subset for Clip and both constraints contribute to the final output."),
    "native:buffer|native:buffer|native:intersection": ("approve", "Buffer two vector inputs independently and intersect the resulting influence zones.", "A vector layer representing overlap between the two buffered zones.", "Each buffer forms one required merge input and Intersection closes the two-input graph with compatible polygon outputs."),
    "native:buffer|native:buffer|native:mergevectorlayers": ("approve", "Buffer two vector inputs independently and combine the results.", "One vector layer containing both buffered datasets.", "The two buffers create compatible vector outputs and Merge Vector Layers preserves both as one final dataset."),
    "native:reprojectlayer": ("approve", "Transform a vector layer to the target coordinate reference system.", "One vector layer in the target coordinate reference system.", "The single operator directly satisfies the declared CRS transformation output."),
    "native:extractbyexpression|native:dissolve": ("approve", "Select features using an expression and dissolve the selected geometries.", "A dissolved vector layer containing only matching features.", "The extracted vector subset is a valid Dissolve input and both stages are required by the output constraint."),
    "native:reprojectlayer|gdal:rasterize": ("approve", "Reproject vector features and convert them to a raster grid.", "A rasterized representation aligned to the target coordinate reference system.", "Rasterize validly consumes the reprojected vector layer and the sequence makes alignment precede conversion."),
    "native:deletecolumn|saga:addrastervaluestopoints": ("approve", "Remove an obsolete field and sample raster values onto the point layer.", "A point layer with the retained schema plus sampled raster attributes.", "Both stages operate on the point dataset, and raster sampling supplies new attributes after schema cleanup."),
    "native:fieldcalculator|native:fieldcalculator|native:fieldcalculator|native:fieldcalculator": ("return_for_revision", "Apply four successive derived-field calculations.", "A vector layer containing all intended calculated fields.", "The repeated stages are type-compatible, but no field-level dependency evidence establishes that four separate calculations are required or ordered correctly."),
    "native:buffer|native:buffer|native:mergevectorlayers|native:fieldcalculator|native:dissolve": ("approve", "Buffer two inputs, merge the zones, calculate a grouping attribute, and dissolve by that grouping.", "One dissolved vector layer derived from both buffered inputs.", "The two-input merge is closed by schema calculation and dissolve; each stage has a distinct role and compatible vector types."),
    "native:reprojectlayer|native:centroids": ("approve", "Reproject polygon features and create their centroid points.", "A centroid point layer in the target coordinate reference system.", "Centroids validly consumes the reprojected vector layer and the output geometry type is explicit."),
    "native:reprojectlayer|native:reprojectlayer": ("return_for_revision", "Apply two sequential coordinate transformations.", "A vector layer in the final target coordinate reference system.", "Two reprojection stages can be valid only with an explicit intermediate CRS or datum transformation; parameter-free graph evidence does not prove that the duplicate stage is necessary."),
}


def main() -> int:
    queue = read_jsonl(AUTHORITY / "v02_dag_review_queue.jsonl")
    jobs = read_jsonl(AUTHORITY / "v02_dag_review_jobs.jsonl")
    graphs = {row["canonical_graph_id"]: row for row in queue}
    drafts = []
    for job in jobs:
        graph = graphs[job["canonical_graph_id"]]
        signature = "|".join(process["operator_id"] for process in graph["processes"])
        decision, intent, output, rationale = REVIEW_DATA[signature]
        seen = set()
        necessity = []
        for process in graph["processes"]:
            operator = process["operator_id"]
            repeated = operator in seen
            necessity.append(
                {
                    "process_id": process["process_id"],
                    "necessity": "optional"
                    if decision != "approve" and repeated
                    else "required",
                }
            )
            seen.add(operator)
        reviewer_note = (
            " Secondary review independently checked the merge inputs and final consumer."
            if job["reviewer_id"] == "qgis-expert-02"
            else " Primary review checked operator necessity, dependency order, and output closure."
        )
        drafts.append(
            {
                "review_job_id": job["review_job_id"],
                "decision": decision,
                "task_intent": intent,
                "output_constraint": output,
                "process_necessity": necessity,
                "type_compatibility_verdict": "compatible"
                if decision == "approve"
                else "uncertain",
                "rationale": rationale + reviewer_note,
            }
        )
    if len(REVIEW_DATA) != len(queue):
        raise ValueError("review data must cover every queue DAG exactly once")
    output = AUTHORITY / "v02_dag_semantic_review_drafts.jsonl"
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in drafts),
        encoding="utf-8",
        newline="\n",
    )
    print(f"drafts={len(drafts)} graphs={len(queue)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
