#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Stage-1 gold authoring — B-group acceptable-solution worksheet.

Per owner ruling (stage sequence): the ONLY task-semantics source is the
frozen input set `pca_b_group_final_inputs_v1.json` (SHA
1a13ad8d95c33771...). Gold is authored FROM THE TASK TEXT (what counts as
correct) BEFORE looking at any original chain; the `gold_chain_audit` field
is left PENDING-STAGE-2. The original QGIS chains are NOT read here.

Field set (owner-specified):
  required_outcome / required_constraints / required_capabilities /
  acceptable_alternatives / failure_conditions / gold_chain_audit /
  evidence.  Task text is copied verbatim from the frozen file (zero
  transcription) and bound by assertion.
"""
import json, hashlib

FROZEN = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_final_inputs_v1.json"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_gold_worksheet_v1.json"
PENDING = "PENDING-STAGE-2 (chain-consistency audit; gold authored independently of chains)"

GOLD = {
"W000473": {
 "required_outcome": "A polygon layer containing exactly the areas covered by one and only one of the two input polygon layers (symmetric difference / XOR of extent vs survey).",
 "required_constraints": ["Two polygon inputs (exterior-extent layer, survey layer)",
                          "Output = polygons of non-overlapping areas",
                          "Any valid route is acceptable (stated in the task)"],
 "required_capabilities": ["Pairwise spatial overlay reasoning (what XOR means geometrically)",
                           "Producing a clean polygon result"],
 "acceptable_alternatives": ["Direct symmetric-difference operator", "(A−B) ∪ (B−A) via two differences + merge",
                             "XOR after prior dissolution to single parts", "Union + subtract intersection",
                             "Line-based boundary difference routes"],
 "failure_conditions": ["Overlap (covered by both) appears in output", "One side's exclusive area missing",
                        "Result area deviates materially from true XOR", "Input layers silently dropped/unprocessed"],
 "evidence": "task: 'regions present in one layer but not in both'; 'Any valid route to this result is acceptable.'"},
"W068342": {
 "required_outcome": "A 'Safe Points' layer: candidate drone-photo locations that satisfy the stated spatial safety constraints relative to the flight grid and the area plot polygon.",
 "required_constraints": ["Use the required projected CRS", "Inputs: candidate points, optimized grid, area plot polygon",
                          "Output = Safe Points layer"],
 "required_capabilities": ["CRS handling", "Spatial containment/proximity screening of points against two reference layers"],
 "acceptable_alternatives": ["Negative buffer on grid then point-in-polygon selection", "Distance-threshold filtering to grid/plot",
                             "Spatial join then attribute filter"],
 "failure_conditions": ["Points violating safety constraint retained", "CRS not handled (mixed/mis-projected)",
                        "Valid points wrongly dropped", "Grid or plot constraint ignored"],
 "evidence": "task: 'must satisfy the specified spatial safety constraints and use the required projected coordinate reference system'"},
"W068582": {
 "required_outcome": "AOI land-cover polygons carrying Manning's n and area in m² and hectares.",
 "required_constraints": ["Lookup strictly via provided CODE_18→n table", "Area in both m² and ha",
                          "All outputs in a common CRS", "Result loaded for visualization"],
 "required_capabilities": ["AOI subsetting semantics", "Attribute lookup/join from mapping table", "Area computation with units"],
 "acceptable_alternatives": ["Clip then attribute join", "Join then clip", "Field mapping via expression vs table join",
                             "Reproject-then-clip vs clip-in-source-CRS-then-reproject"],
 "failure_conditions": ["Features outside AOI remain", "Manning missing or mis-mapped from CODE_18",
                        "Area absent or wrong units", "Outputs in mixed CRS"],
 "evidence": "task: 'using the provided CODE_18→n lookup table, and compute each polygon's area in square metres and hectares. All outputs must be in a common CRS.'"},
"W067404": {
 "required_outcome": "Species-occurrence points enriched with neighbourhood statistics of the environmental raster.",
 "required_constraints": ["Circular neighbourhood with user-specified radius", "Requested statistics computed inside each neighbourhood",
                          "Statistics attached to the ORIGINAL point locations"],
 "required_capabilities": ["Neighbourhood definition around points", "Zonal/raster statistics", "Attribute attachment back to points"],
 "acceptable_alternatives": ["Buffer→zonal statistics→centroid re-attachment", "Per-point raster window statistics",
                             "Sample raster via proximity field with radius mask"],
 "failure_conditions": ["Statistics computed without the radius neighbourhood", "Results not re-attached to point locations",
                        "Requested statistic types missing", "Points displaced (e.g., centroids kept instead of originals)"],
 "evidence": "task: 'circular neighbourhood of a user-specified radius: compute the requested statistics … attach them to the original point locations'"},
"W000635": {
 "required_outcome": "A polygon layer of uniform-width bands tracing input polygon boundaries (tactile-map edge rendering).",
 "required_constraints": ["Band width = user-specified", "Bands centred on original outlines",
                          "Free of geometry artefacts", "Bands combined into a clean output"],
 "required_capabilities": ["Offset/band geometry construction", "Geometry cleaning", "Dissolving artifacts"],
 "acceptable_alternatives": ["Inward+outward buffer difference", "Polygon→boundary line→centred line buffer",
                             "Boundary extraction then buffer with cleanup"],
 "failure_conditions": ["Band not centred (one-sided)", "Wrong width", "Self-intersections/slivers retained",
                        "Polygon interior filled instead of edge band"],
 "evidence": "task: 'bands must be centred on the original outlines, free of geometry artefacts, and combined into a clean output'"},
"W000890": {
 "required_outcome": "(1) Municipality layer symbolized by dominant drought class; (2) table of municipality → dominant class code/name + area.",
 "required_constraints": ["Overlapping severity classes resolved by hierarchical exclusivity (more severe takes precedence; original-text requirement)",
                          "Dominant = class covering the largest area within each municipality",
                          "Two outputs (map layer + table)"],
 "required_capabilities": ["Ranked overlap resolution", "Spatial intersection with municipalities", "Per-group area aggregation and argmax"],
 "acceptable_alternatives": ["Sequential difference chain by severity order", "Sort-by-severity layered overwrite",
                             "Rasterized class-vote then per-municipality majority"],
 "failure_conditions": ["Overlaps resolved without severity precedence", "Dominant class chosen wrongly (not largest area)",
                        "Missing table fields (code/name/area)", "Municipal boundaries not intersected"],
 "evidence": "task: 'more severe classes take precedence (hierarchical exclusivity)' — verified as original-text requirement; 'drought class covering the largest area within it'"},
"W033927": {
 "required_outcome": "Polygon layer of seafloor substrate mapping units, each carrying a single substrate class, with standardized styling.",
 "required_constraints": ["Inputs: ROV navigation tracks + annotations", "Each annotated location's camera-visible area represented as substrate-classified polygon",
                          "Overlapping areas combined so each final unit has one class", "Styled output"],
 "required_capabilities": ["Viewshed-like polygon construction along track geometry", "Class-wise merging of overlapping units"],
 "acceptable_alternatives": ["Wedge buffers oriented along track", "Sector/limited-rectangle visibility approximation",
                             "Dissolve-by-class after union", "Merge-then-assign vs assign-then-merge"],
 "failure_conditions": ["Final units carry mixed substrate classes", "Annotation class ignored",
                        "Unit geometry unrelated to track/visibility semantics", "Unstyled/unordered output"],
 "evidence": "task: 'represent the area of seafloor visible to the camera as a substrate-classified polygon oriented along the track, then combine overlapping areas so each final unit carries a single substrate class' — orientation verified as original wedge/viewshed semantics"},
"W056274": {
 "required_outcome": "One georeferenced distance raster per paddock (named after the paddock): for every location inside the paddock, distance to the nearest water point located within that same paddock.",
 "required_constraints": ["Water points restricted to the SAME paddock (verified task semantics)", "Distances in map units of the working CRS",
                          "Only paddocks containing ≥1 water point produce output (task_text-defined)",
                          "The per-paddock raster set is the final output — no extra summary statistic"],
 "required_capabilities": ["Group-wise processing per polygon", "Point-to-distance-field computation", "Clipping/masking to paddock extents"],
 "acceptable_alternatives": ["Rasterize points→proximity→clip by paddock", "Vector nearest-point distance field then rasterize",
                             "Per-paddock temporary layer construction (any order that respects semantics)"],
 "failure_conditions": ["Distance computed to GLOBAL nearest water point (violates inside-paddock semantics)",
                        "Units not map units / CRS inconsistent", "Empty paddocks silently included or naming lost",
                        "Unrequested aggregation (max extraction etc.) presented as the deliverable"],
 "evidence": "task: 'distance to the nearest water point located within that same paddock, in map units of the working CRS'; original task_text defines output set 'one per paddock containing at least one water point'"},
"W067268": {
 "required_outcome": "A noise-level value (dBA) per receptor location + a styled source-point layer.",
 "required_constraints": ["BS 5228 as the governing standard", "Account for terrain (DEM), distance attenuation, ground type, and barriers",
                          "Inputs: point source, receptor polygons, DEM", "Handle in projected CRS"],
 "required_capabilities": ["Source–receptor geometric relationship (distance/visibility)", "Multi-factor attenuation combination",
                           "Attaching results to receptors"],
 "acceptable_alternatives": ["Viewshed + zonal sampling route", "Receptor-point sampling with correction fields",
                             "Raster attenuation-surface route — any route honouring BS 5228 semantics and all four physical factors"],
 "failure_conditions": ["Terrain/barrier/ground-type factor ignored", "No per-receptor noise value produced",
                        "CRS mishandled (geographic units) or standard ignored", "Source-point layer missing"],
 "evidence": "task text (all five elements traced to original task sentences; see final_status §6 check#2)"},
"W055908": {
 "required_outcome": "A new point layer with the sampled features, carrying X and Y coordinate fields.",
 "required_constraints": ["Support simple random mode AND stratified mode", "Strata derived from a numeric attribute (method flexible, e.g., quantiles/equal intervals)",
                          "Sampling occurs within each stratum"],
 "required_capabilities": ["Numeric-field classification", "Within-class random selection", "Coordinate field generation"],
 "acceptable_alternatives": ["Classification operator + per-class random selection", "Dedicated stratified-sampling tool",
                             "Quantile/equal-interval boundary computation then filtered selection"],
 "failure_conditions": ["Only simple random sampling implemented (stratified unsupported)", "Classes ignored (sampling across strata)",
                        "X/Y fields absent", "Sample not a subset of input points"],
 "evidence": "task: 'must support both a simple random mode and a stratified mode, in which the numeric field is first divided into classes (e.g., by quantiles or equal intervals)'"},
"W066995": {
 "required_outcome": "A single styled GeoPackage layer covering exactly the target property area with the property's natural-resource features.",
 "required_constraints": ["Source: government feature service", "Selection by lot/plan boundaries or given extent",
                          "Final coverage = exactly the target property area", "Single merged layer; GeoPackage; styled"],
 "required_capabilities": ["Service query/download", "Spatial restriction to property/extent", "Combining multi-part retrieval"],
 "acceptable_alternatives": ["Download all then clip", "Server-side spatial filter", "Batch download + merge + clip",
                             "Extent-from-boundary construction then service query"],
 "failure_conditions": ["Coverage exceeds or falls short of the property area", "Multiple unmerged outputs",
                        "Wrong format / unstyled layer", "Features unrelated to the property included"],
 "evidence": "task: 'so that the final dataset covers exactly the target property area. Output: a single styled GeoPackage layer'"},
"W055494": {
 "required_outcome": "A merged polygon layer; each feature flagged merged=1/0; merged groups retain the largest stand's attributes.",
 "required_constraints": ["Eligibility: touches a larger neighbour AND relative dominant-height difference within threshold AND neighbour type 'classified'",
                          "Attribute retention rule (largest stand per group)", "Per-feature merged flag with defined semantics"],
 "required_capabilities": ["Adjacency/touch detection", "Threshold-based candidate filtering", "Group-wise merge with attribute inheritance"],
 "acceptable_alternatives": ["Aggregate/dissolve after spatial-join screening", "Pairwise merge iteration",
                             "Expression-based eligibility then dissolve by target id"],
 "failure_conditions": ["Merges violating any eligibility criterion", "Attributes inherited from a smaller stand",
                        "Flag missing or semantics inverted", "Neighbour type constraint ignored"],
 "evidence": "task: three eligibility criteria verbatim; 'each output feature must state whether it was merged (merged = 1) or not (merged = 0)'"},
"W068833": {
 "required_outcome": "A set of aligned rasters with identical grid structure + a manifest summarizing alignment parameters.",
 "required_constraints": ["Identical CRS, extent, pixel size across outputs", "Honour reference (snap) grid where provided",
                          "Manifest of alignment parameters included"],
 "required_capabilities": ["Multi-raster reprojection/resampling orchestration", "Grid consistency verification"],
 "acceptable_alternatives": ["Warp each raster to reference grid", "Align to first raster then verify",
                             "Translate+resample combinations"],
 "failure_conditions": ["Grid parameters differ across outputs", "Snap grid ignored when provided",
                        "Manifest absent", "Nodata handling creates spurious data holes"],
 "evidence": "task: 'identical CRS, extent, and pixel size'; 'honour a reference (snap) grid where provided'; 'a manifest summarizing the alignment parameters used' (original-text manifest)"},
"W067092": {
 "required_outcome": "Input features with area-weighted average attached + a report layer with per-feature details.",
 "required_constraints": ["Weighting strictly by overlay fragment area", "Duplicated overlay geometry not counted twice (genuine overlaps unaffected)",
                          "CRS check expected for geographic/mismatched layers"],
 "required_capabilities": ["Overlay decomposition into fragments", "Area weighting and per-input aggregation", "Numeric consistency (weights sum to overlay area)"],
 "acceptable_alternatives": ["Intersect→weight→aggregate-by-input", "Area-join after dedup", "Per-feature overlay iteration"],
 "failure_conditions": ["Unweighted average used", "Duplicate overlay counted twice", "Aggregation keyed wrongly (not per input feature)",
                        "Report layer missing"],
 "evidence": "task: 'area-weighted average … ensuring duplicated overlay geometry is not counted twice'; 'a report layer with per-feature details'"},
"W007046": {
 "required_outcome": "Matching features carrying both counts + ONE centroid point feature carrying the same counts.",
 "required_constraints": ["Case-insensitive pattern match on a string attribute", "Count (a)=total input features, (b)=matching features",
                          "Point (c) = centroid of matching features' MERGED geometry"],
 "required_capabilities": ["Attribute pattern selection", "Counting", "Merged-geometry centroid computation"],
 "acceptable_alternatives": ["Expression filter + field calculator + collect→centroids", "Aggregate statistics + single-point construction"],
 "failure_conditions": ["Match case-sensitive or wrong field", "Counts wrong or attached to wrong layer",
                        "Centroid computed per-feature or on unmatched set", "Multiple centroid points emitted"],
 "evidence": "task: 'the centroid of the matching features' merged geometry as a single point'"},
"W055534": {
 "required_outcome": "Countries layer carrying all statistics + exported CSV of the final attribute table.",
 "required_constraints": ["Zones = country boundaries", "Indicators: land quality (single epoch) + population density (1500, 1990, 2000)",
                          "Retain country name and ISO fields", "Distinct prefix per indicator epoch", "CSV export"],
 "required_capabilities": ["Multi-raster zonal-statistics orchestration", "Field retention management", "Table export"],
 "acceptable_alternatives": ["Per-raster zonal stats then field merge", "Multi-band batch statistics",
                             "Per-year loops then combined export"],
 "failure_conditions": ["Years attached to land quality or dropped from population density", "Name/ISO fields dropped",
                        "Prefixes colliding/ambiguous", "CSV missing or schema inconsistent with layer"],
 "evidence": "task: 'land quality (one epoch) and population density for the years 1500, 1990, and 2000'; 'distinctly prefixed set of statistics per indicator epoch'; 'export the final attribute table as CSV'"},
"W000674": {
 "required_outcome": "Three georeferenced terrain rasters: slope (degrees), aspect (degrees), hillshade.",
 "required_constraints": ["Computation in projected metric CRS (geometric meaningfulness)", "Slope/aspect in degrees",
                          "Hillshade with stated/reasonable illumination", "Three files added to project"],
 "required_capabilities": ["CRS management prior to derivation", "Terrain derivative computation ×3"],
 "acceptable_alternatives": ["Reproject→derive each", "Derive in native CRS then reproject results (acceptable only if geometry stays valid)",
                             "GDAL/GRASS/SAGA derivative families"],
 "failure_conditions": ["Derivatives computed in geographic CRS", "Slope/aspect not in degrees",
                        "A derivative missing", "Outputs not georeferenced"],
 "evidence": "task: 'must be geometrically meaningful, which requires working in a projected metric CRS'; 'slope in degrees, aspect in degrees, and a hillshade'"},
"W055913": {
 "required_outcome": "One polygon layer of non-overlapping atomic zones (unique combination of the two zonings), single-part, uniquely identified, with area/perimeter.",
 "required_constraints": ["Each output polygon = unique combination of the two zonings", "Valid single-part polygons",
                          "Unique zone ID", "Geometry attributes (area, perimeter)"],
 "required_capabilities": ["Two-layer overlay algebra", "Multipart resolution", "Unique ID generation"],
 "acceptable_alternatives": ["Union operator route", "Intersection + two differences combined",
                             "Intersect then symmetrical-difference cleanup"],
 "failure_conditions": ["Zones not atomic (overlaps remain or combinations duplicated/missing)", "Multiparts unresolved",
                        "IDs not unique", "Area/perimeter missing"],
 "evidence": "task: 'each output polygon represents a unique combination of the two zonings'; 'must consist of valid single-part polygons, each uniquely identified'"},
"W056058": {
 "required_outcome": "Study-area network + one filtered layer per level + one buffer layer per level.",
 "required_constraints": ["Restrict to study area", "Three levels (Principal, Secundaria, Terciaria) per level attribute",
                          "Each level buffered at its own distinct radius"],
 "required_capabilities": ["Attribute-based level separation", "Differentiated buffer parameters per group", "Multi-output organization"],
 "acceptable_alternatives": ["Clip→filter→buffer or filter→buffer→clip (order-free)", "Expression filters + three buffer runs",
                             "Level loop with parameter table"],
 "failure_conditions": ["Level misclassification (wrong attribute mapping)", "Radius assigned to wrong level",
                        "A level's layer/buffer missing", "Results exceed study area"],
 "evidence": "task: 'three hierarchical levels (Principal, Secundaria, Terciaria) according to the level attribute'; 'each level has a distinct radius'; 'Output: the study-area network, one filtered layer per level, and one buffer layer per level'"},
}

def main():
    frozen = json.load(open(FROZEN, encoding="utf-8"))
    frozen_sha = hashlib.sha256(open(FROZEN, "rb").read()).hexdigest()
    rows = []
    for fr in frozen["rows"]:
        wid = fr["wid"]
        g = GOLD[wid]
        assert fr["final_text"] and g, wid
        rows.append({
            "task_id": wid,
            "task_text": fr["final_text"],          # verbatim from frozen file
            "task_sha256": fr["text_sha256"],
            "required_outcome": g["required_outcome"],
            "required_constraints": g["required_constraints"],
            "required_capabilities": g["required_capabilities"],
            "acceptable_alternatives": g["acceptable_alternatives"],
            "failure_conditions": g["failure_conditions"],
            "gold_chain_audit": PENDING,
            "evidence": g["evidence"],
        })
    missing = set(GOLD) ^ {r["task_id"] for r in rows}
    assert not missing, f"gold/frozen mismatch: {missing}"
    payload = {"_meta": {
        "stage": "PCA Stage-1 gold authoring (acceptable-solution sets)",
        "authority": "frozen inputs ONLY; chains not read",
        "frozen_inputs_sha256": frozen_sha,
        "chain_audit": PENDING,
        "n_rows": len(rows)},
        "rows": rows}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("rows:", len(rows), "| frozen_inputs_sha:", frozen_sha[:16])
    print("file_sha256:", hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16])
    print("saved:", OUT)

if __name__ == "__main__":
    main()
