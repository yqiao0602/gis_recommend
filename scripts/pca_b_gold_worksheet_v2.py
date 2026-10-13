#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Stage-1 gold worksheet v2 — owner round-1 review revisions applied.

v1 (SHA 06b30b9c810a2e6d) stays immutable. v2 incorporates the owner's
8-item minimal revision list (see worknotes); all other rows carry over.
Same authoring discipline: task text extracted verbatim from the FROZEN
input file; chains not read; gold_chain_audit = PENDING-STAGE-2.

New in v2:
  - `underdetermined_aspects` field (aspects not judgeable from the frozen
    task text; partial-scoring boundaries declared, nothing improvised).
  - Alternatives tightened: routes that cannot guarantee the required
    semantics are removed or made conditional; route NAMES never count as
    compliance (W067268 BS 5228 hard semantic constraint).
  - Failure conditions restricted to task-supported judgments; unspecified
    parameters (sample sizes, grid resolution) never hard failures.
"""
import json, hashlib

FROZEN = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_final_inputs_v1.json"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_gold_worksheet_v2.json"
PENDING = "PENDING-STAGE-2 (chain-consistency audit; gold authored independently of chains)"

GOLD = {
"W000473": {
 "rev": "R7: line-difference route made conditional (must rebuild polygon result)",
 "required_outcome": "A polygon layer containing exactly the areas covered by one and only one of the two input polygon layers (symmetric difference / XOR of extent vs survey).",
 "required_constraints": ["Two polygon inputs (exterior-extent layer, survey layer)",
                          "Output = polygons of non-overlapping areas",
                          "Any valid route is acceptable (stated in the task)"],
 "required_capabilities": ["Pairwise spatial overlay reasoning (what XOR means geometrically)",
                           "Producing a clean POLYGON result (geometry type matters)"],
 "acceptable_alternatives": ["Direct symmetric-difference operator", "(A−B) ∪ (B−A) via two differences + merge",
                             "XOR after prior dissolution to single parts", "Union + subtract intersection",
                             "Line-based routes ONLY if they reliably rebuild the required polygon areas (conditional)"],
 "failure_conditions": ["Overlap (covered by both) appears in output", "One side's exclusive area missing",
                        "Output delivered as lines/points instead of polygons",
                        "Input layers silently dropped/unprocessed",
                        "NOTE: quantified area-deviation tolerance requires separate pre-registration — 'material deviation' alone is NOT a reproducible criterion (owner round-5); hard judgments are the structural ones above"],
 "underdetermined_aspects": [],
 "evidence": "task: 'regions present in one layer but not in both'; 'Any valid route to this result is acceptable.'"},
"W068342": {
 "rev": "R5: gold lowered to what the frozen text independently supports — the binding scope of the unspecified safety constraints (grid/plot/both) is NOT determinable from task text; structural screening + CRS only; original route stays researcher-reference-only",
 "required_outcome": "A 'Safe Points' layer: candidate drone-photo locations that satisfy the stated spatial safety constraints relative to the flight grid and the area plot polygon.",
 "required_constraints": ["Use the required projected CRS", "Inputs: candidate points, optimized grid, area plot polygon",
                          "Output = Safe Points layer (a screening/selection over candidate points occurs)"],
 "required_capabilities": ["CRS handling", "Screening/selection of candidate points (structure-level)"],
 "acceptable_alternatives": ["Any screening construction; the task text fixes neither the relation type nor which reference layers it binds"],
 "failure_conditions": ["CRS not handled (mixed/mis-projected)",
                        "No screening performed (all candidates pass through unfiltered)",
                        "One or more input layers never loaded/used at all"],
 "underdetermined_aspects": ["The CONTENT of the 'specified spatial safety constraints' AND which reference layers they bind (grid only / plot only / both) are not determinable from the frozen task text; the original implementation route (negative buffer + double intersection) is researcher reference only and is NOT imported into gold (owner round-5); only structural screening + CRS are judgeable"],
 "evidence": "task: 'must satisfy the specified spatial safety constraints and use the required projected coordinate reference system'"},
"W068582": {
 "rev": "approved as-is (owner)",
 "required_outcome": "AOI land-cover polygons carrying Manning's n and area in m² and hectares.",
 "required_constraints": ["Lookup strictly via provided CODE_18→n table", "Area in both m² and ha",
                          "All outputs in a common CRS", "Result loaded for visualization"],
 "required_capabilities": ["AOI subsetting semantics", "Attribute lookup/join from mapping table", "Area computation with units"],
 "acceptable_alternatives": ["Clip then attribute join", "Join then clip", "Field mapping via expression vs table join",
                             "Reproject-then-clip vs clip-in-source-CRS-then-reproject"],
 "failure_conditions": ["Features outside AOI remain", "Manning missing or mis-mapped from CODE_18",
                        "Area absent or wrong units", "Outputs in mixed CRS"],
 "underdetermined_aspects": [],
 "evidence": "task: 'using the provided CODE_18→n lookup table, and compute each polygon's area in square metres and hectares. All outputs must be in a common CRS.'"},
"W067404": {
 "rev": "R7: statistic-set judgeability clarified — original enumeration cited as evidence; full-enumeration absence is NOT a hard failure against the frozen text",
 "required_outcome": "Species-occurrence points enriched with neighbourhood statistics of the environmental raster.",
 "required_constraints": ["Circular neighbourhood with user-specified radius", "Statistics computed inside each neighbourhood",
                          "Statistics attached to the ORIGINAL point locations"],
 "required_capabilities": ["Neighbourhood definition around points", "Zonal/raster statistics", "Attribute attachment back to points"],
 "acceptable_alternatives": ["Buffer→zonal statistics→centroid re-attachment", "Per-point raster window statistics",
                             "Sample raster via proximity field with radius mask"],
 "failure_conditions": ["Statistics computed without the radius neighbourhood", "Results not re-attached to point locations",
                        "Points displaced (e.g., centroids kept instead of originals)",
                        "No raster-statistics computation at all (only this statistic-semantics level is scorable from the frozen text)"],
 "underdetermined_aspects": ["Exact statistic set: frozen text says only 'the requested statistics'. The original enumeration ('count, sum, mean, …') is RESEARCHER REFERENCE ONLY — not model-visible and NOT a scoring basis (owner round-5): unseen statistics can never generate model failure conditions. Judgeable from frozen text: neighbourhood semantics + re-attachment + that a statistic computation occurs"],
 "evidence": "frozen task: 'circular neighbourhood of a user-specified radius: compute the requested statistics … attach them to the original point locations'; original task_text enumeration — researcher reference only (scoring basis = frozen text)"},
"W000635": {
 "rev": "R7+R5: width semantics = PRIMARY reading total band width, not sole admissible reading (owner round-5); alternatives gated on internally consistent geometry",
 "required_outcome": "A polygon layer of uniform-width bands tracing input polygon boundaries (tactile-map edge rendering).",
 "required_constraints": ["Band width = user-specified width; PRIMARY interpretation: TOTAL band width (supported by centring + uniformity), not elevated to the sole admissible reading — a consistent, reasonable alternative width semantics is adjudicated case-by-case, not auto-failed (owner round-5)",
                          "Bands centred on original outlines", "Free of geometry artefacts",
                          "Bands combined into a clean output"],
 "required_capabilities": ["Offset/band geometry construction", "Geometry cleaning", "Dissolving artifacts"],
 "acceptable_alternatives": ["Inward+outward buffer difference (half-width each side under the total-width reading)", "Polygon→boundary line→centred line buffer",
                             "Boundary extraction then buffer with cleanup — every route must deliver internally consistent geometry: a uniform band centred on the outline under SOME stated width semantics"],
 "failure_conditions": ["Band not centred (e.g., one-sided offset while claiming a centred band)", "Width semantics applied inconsistently within the plan",
                        "Self-intersections/slivers retained", "Polygon interior filled instead of edge band"],
 "underdetermined_aspects": ["Width interpretation (total band width vs one-sided offset distance): total-width is the primary reading but the task text does not exclusively fix it — alternatives adjudicated case-by-case"],
 "evidence": "task: 'uniform-width bands … centred on the original outlines' — centring + uniformity support the total-width primary reading (not exclusive; owner round-5)"},
"W000890": {
 "rev": "R7-1: raster majority-vote removed as an unconditional equivalent; conditional with pre-declared area-accuracy standard; resolution artifacts separated from semantic errors",
 "required_outcome": "(1) Municipality layer symbolized by dominant drought class; (2) table of municipality → dominant class code/name + area.",
 "required_constraints": ["Overlapping severity classes resolved by hierarchical exclusivity (more severe takes precedence; original-text requirement)",
                          "Dominant = class covering the largest AREA within each municipality (area-based semantics)",
                          "Two outputs (map layer + table)"],
 "required_capabilities": ["Ranked overlap resolution", "Spatial intersection with municipalities", "Per-group area aggregation and argmax"],
 "acceptable_alternatives": ["Sequential difference chain by severity order", "Sort-by-severity layered overwrite",
                             "Raster-based approaches ONLY if they explicitly compute or reliably approximate per-class area shares, with the accuracy/tolerance standard declared in advance (conditional; not an unconditional equivalent)"],
 "failure_conditions": ["Overlaps resolved without severity precedence", "Dominant class chosen wrongly (not largest area)",
                        "Missing table fields (code/name/area)", "Municipal boundaries not intersected",
                        "NOTE: class flips caused solely by raster resolution/boundary discretization are resolution artifacts — judged separately from semantic errors"],
 "underdetermined_aspects": [],
 "evidence": "task: 'more severe classes take precedence (hierarchical exclusivity)' — verified as original-text requirement; 'drought class covering the largest area within it' — area semantics, not pixel votes"},
"W033927": {
 "rev": "R7-2: geometry-approximation admission conditions stated; cross-class overlap priority declared UNDERDETERMINED (task text defines none; none invented)",
 "required_outcome": "Polygon layer of seafloor substrate mapping units, each carrying a single substrate class, with standardized styling.",
 "required_constraints": ["Inputs: ROV navigation tracks + annotations", "Each annotated location's camera-visible area represented as substrate-classified polygon",
                          "Overlapping areas combined so each final unit has one class", "Styled output"],
 "required_capabilities": ["Viewshed-like polygon construction consistent with camera coverage and track orientation",
                           "Class-wise merging of overlapping units"],
 "acceptable_alternatives": ["Wedge buffers oriented along track (matches original visibility semantics)",
                             "Other geometry constructions ONLY if they respect the task's camera-coverage and track-orientation definition",
                             "Sector/limited-rectangle approximations are directly equivalent ONLY if the original task explicitly endorses them (no such endorsement found → conditional, default NOT equivalent)",
                             "Dissolve-by-class after union vs merge-then-assign"],
 "failure_conditions": ["Final units carry mixed substrate classes", "Annotation class ignored",
                        "Unit geometry unrelated to track/visibility semantics", "Unstyled/unordered output"],
 "underdetermined_aspects": ["Priority rule among overlapping DIFFERENT substrate classes is NOT defined by the task text — recorded UNDERDETERMINED; adjudication must not invent a priority (class-conflict outcomes are case-by-case, not automatic failures)"],
 "evidence": "task: 'represent the area of seafloor visible to the camera as a substrate-classified polygon oriented along the track, then combine overlapping areas so each final unit carries a single substrate class'"},
"W056274": {
 "rev": "R7-5: unspecified grid parameters (resolution/origin/reference grid) declared NOT hard scoring conditions; pixel-level comparison deferred to a separately declared alignment/tolerance rule; rasterize/clip demoted from mandated steps to common capabilities",
 "required_outcome": "One georeferenced distance raster per paddock (named after the paddock): for every location inside the paddock, distance to the nearest water point located within that same paddock.",
 "required_constraints": ["Water points restricted to the SAME paddock (verified task semantics) — NOT bypassable",
                          "Distances in map units of the working CRS",
                          "Results spatially limited to the corresponding paddock extent",
                          "Only paddocks containing ≥1 water point produce output (task_text-defined)",
                          "The per-paddock raster set is the final output — no extra summary statistic"],
 "required_capabilities": ["Group-wise processing per polygon", "Distance-field computation (rasterize→proximity OR vector distance field then rasterized — rasterization and clipping are common capabilities, NOT mandated steps)"],
 "acceptable_alternatives": ["Rasterize points→proximity→clip by paddock", "Vector nearest-point distance field then rasterize",
                             "Any route honouring the distance semantics, per-paddock scoping, naming, and output-organization constraints"],
 "failure_conditions": ["Distance computed to GLOBAL nearest water point (violates inside-paddock semantics)",
                        "Distance values not expressed in the working CRS's map units (explicit task requirement — always judgeable)",
                        "CRS handling that actually corrupts coordinate or distance semantics (NOT mere absence of an explicit reprojection step — split per owner round-5)",
                        "Empty paddocks silently included or naming lost",
                        "Unrequested aggregation (max extraction etc.) presented as the deliverable",
                        "NOTE: different-but-reasonable resolution choices are NOT errors"],
 "underdetermined_aspects": ["Raster resolution, cell origin, and reference grid are unspecified by the task text — pixel-level comparison requires a separately declared alignment/tolerance rule (not improvised at scoring time)"],
 "evidence": "task: 'distance to the nearest water point located within that same paddock, in map units of the working CRS'; original task_text defines output set 'one per paddock containing at least one water point'"},
"W067268": {
 "rev": "R7-6: BS 5228 semantic compliance is the hard constraint, not route names; structural vs domain-semantic scoring boundary declared",
 "required_outcome": "A noise-level value (dBA) per receptor location + a styled source-point layer.",
 "required_constraints": ["BS 5228 as the governing standard (hard semantic constraint)",
                          "Account for terrain (DEM), distance attenuation, ground type, and barriers",
                          "Inputs: point source, receptor polygons, DEM", "Handle in projected CRS"],
 "required_capabilities": ["Source–receptor geometric relationship (distance/visibility)", "Multi-factor attenuation combination",
                           "Attaching results to receptors"],
 "acceptable_alternatives": ["Any implementation is acceptable ONLY if its resulting per-receptor noise estimates follow the applicable BS 5228 calculation requirements and account for terrain, distance attenuation, ground type, and barriers.",
                             "A generic viewshed analysis or arbitrary attenuation surface is NOT automatically compliant — route names never substitute for the standard's semantics"],
 "failure_conditions": ["Terrain/barrier/ground-type factor ignored", "No per-receptor noise value produced",
                        "CRS mishandled (geographic units)", "Source-point layer missing",
                        "Standard invoked by name while the plan's structure VISIBLY omits a required factor (structure-identifiable omissions only)"],
 "underdetermined_aspects": ["Scoring boundary: from WORKFLOW STRUCTURE alone one can judge presence of source–receptor relationship, terrain factor, attenuation factors, and barrier handling; NUMERICAL BS 5228 compliance of computed values is NOT judgeable from structure alone (this PCA evaluates workflow plans, not executed numerics) — declared partial-scoring boundary"],
 "evidence": "task text (all five elements traced to original task sentences; see final_status §6 check#2)"},
"W055908": {
 "rev": "R7-3: failure conditions restricted to task-supported judgments; sample size/ratio/quotas declared undefined — representativeness never a failure",
 "required_outcome": "A new point layer with the sampled features, carrying X and Y coordinate fields.",
 "required_constraints": ["Support simple random mode AND stratified mode", "Strata derived from a numeric attribute (method flexible, e.g., quantiles/equal intervals)",
                          "Sampling occurs within each stratum",
                          "Output = subset of input points + X/Y coordinate fields"],
 "required_capabilities": ["Numeric-field classification", "Within-class random selection", "Coordinate field generation"],
 "acceptable_alternatives": ["Classification operator + per-class random selection", "Dedicated stratified-sampling tool",
                             "Quantile/equal-interval boundary computation then filtered selection"],
 "failure_conditions": ["Only simple random sampling implemented (stratified mode unsupported)",
                        "Classes ignored (sampling across strata rather than within)",
                        "X/Y fields absent", "Sample not a subset of input points",
                        "NOTE: sample size, ratio, per-stratum quotas, random seed, and 'representativeness' are UNDEFINED by the task text — the word 'representative' is the task's own phrasing and carries NO quantifiable scoring requirement (owner round-5); none of these are failure conditions and no threshold may be improvised"],
 "underdetermined_aspects": ["Sampling quantity/proportion/stratum quotas/random seed: unspecified — unjudgeable by design; 'representative' imposes no quantifiable requirement"],
 "evidence": "task: 'must support both a simple random mode and a stratified mode, in which the numeric field is first divided into classes (e.g., by quantiles or equal intervals)'"},
"W066995": {
 "rev": "R7: interpretive note — 'covers exactly' constrains the DATA extent to the property, not spatial filling of the parcel",
 "required_outcome": "A single styled GeoPackage layer covering exactly the target property area with the property's natural-resource features.",
 "required_constraints": ["Source: government feature service", "Selection by lot/plan boundaries or given extent",
                          "Final DATA coverage restricted to the target property extent (interpretive note: features need not spatially fill the parcel — the dataset must be confined to it)",
                          "Single merged layer; GeoPackage; styled"],
 "required_capabilities": ["Service query/download", "Spatial restriction to property/extent", "Combining multi-part retrieval"],
 "acceptable_alternatives": ["Download all then clip", "Server-side spatial filter", "Batch download + merge + clip",
                             "Extent-from-boundary construction then service query"],
 "failure_conditions": ["Features outside the target property/lot-plan scope are included",
                        "Features the task explicitly required obtaining are omitted (required = the stated lot/plan or extent query — NOT a requirement that data fill every location in the parcel)",
                        "The specified query scope (lot/plan boundaries or extent) is not correctly applied",
                        "Multiple unmerged outputs", "Wrong format / unstyled layer",
                        "Features unrelated to the property included"],
 "underdetermined_aspects": [],
 "evidence": "task: 'so that the final dataset covers exactly the target property area' — read as a data-extent restriction (owner interpretive ruling); data may not exceed the parcel, but absence of features in parts of the parcel is not a failure (owner round-5)"},
"W055494": {
 "rev": "R7: no formula/iteration-order/unique-path prescriptions; relative-difference formula and merge-order ties declared multiple-valid/underdetermined",
 "required_outcome": "A merged polygon layer; each feature flagged merged=1/0; merged groups retain the largest stand's attributes.",
 "required_constraints": ["Eligibility: touches a larger neighbour AND relative dominant-height difference within threshold AND neighbour type 'classified'",
                          "Every merge must satisfy the listed eligibility criteria",
                          "Attribute retention rule (largest stand per group)", "Per-feature merged flag with defined semantics"],
 "required_capabilities": ["Adjacency/touch detection", "Threshold-based candidate filtering", "Group-wise merge with attribute inheritance"],
 "acceptable_alternatives": ["Aggregate/dissolve after spatial-join screening", "Pairwise merge iteration",
                             "Expression-based eligibility then dissolve by target id",
                             "ANY merge order/grouping in which every merge satisfies the eligibility criteria and the attribute rule — multiple valid final groupings are acceptable"],
 "failure_conditions": ["A merge violating any eligibility criterion", "Attributes inherited from a smaller stand",
                        "Flag missing or semantics inverted", "Neighbour type constraint ignored",
                        "NOTE: different valid merge orders yielding different (each valid) groupings are NOT failures"],
 "underdetermined_aspects": ["Exact 'relative difference' formula and tie-breaking among multiple qualifying neighbours are not fixed by the task text (threshold is data-given; formula delegates to data semantics) — multiple valid outcomes acceptable"],
 "evidence": "task: three eligibility criteria verbatim; 'each output feature must state whether it was merged (merged = 1) or not (merged = 0)'"},
"W068833": {
 "rev": "R7: 'spurious' holes defined precisely; legitimate NoData never a failure",
 "required_outcome": "A set of aligned rasters with identical grid structure + a manifest summarizing alignment parameters.",
 "required_constraints": ["Identical CRS, extent, pixel size across outputs", "Honour reference (snap) grid where provided",
                          "Manifest of alignment parameters included"],
 "required_capabilities": ["Multi-raster reprojection/resampling orchestration", "Grid consistency verification"],
 "acceptable_alternatives": ["Warp each raster to reference grid", "Align to first raster then verify",
                             "Translate+resample combinations"],
 "failure_conditions": ["Grid parameters differ across outputs", "Snap grid ignored when provided",
                        "Manifest absent",
                        "Holes inconsistent with input coverage and the chosen resampling rule ('spurious'); legitimate NoData regions resulting from valid resampling are NOT failures"],
 "underdetermined_aspects": [],
 "evidence": "task: 'identical CRS, extent, and pixel size'; 'honour a reference (snap) grid where provided'; 'a manifest summarizing the alignment parameters used' (original-text manifest)"},
"W067092": {
 "rev": "R7: duplicate-vs-overlap scope refined; conflicting-attribute duplicates declared adjudication cases (no implicit value choice)",
 "required_outcome": "Input features with area-weighted average attached + a report layer with per-feature details.",
 "required_constraints": ["Weighting strictly by overlay fragment area",
                          "Duplicated overlay geometry (same geometry re-appearing) not counted twice; genuine overlaps between distinct overlay areas remain in the calculation",
                          "CRS check expected for geographic/mismatched layers"],
 "required_capabilities": ["Overlay decomposition into fragments", "Area weighting and per-input aggregation", "Numeric consistency (weights sum to overlay area)"],
 "acceptable_alternatives": ["Intersect→weight→aggregate-by-input", "Area-join after dedup", "Per-feature overlay iteration"],
 "failure_conditions": ["Unweighted average used", "Duplicate overlay counted twice", "Aggregation keyed wrongly (not per input feature)",
                        "Report layer missing",
                        "NOTE: identical geometry carrying CONFLICTING numeric attribute values must NOT be resolved by implicit value choice — flagged case-by-case"],
 "underdetermined_aspects": ["Duplicate geometry with conflicting attribute values: weighted-average semantics become non-unique — recorded as adjudication cases, not auto-failures and not auto-merges"],
 "evidence": "task: 'area-weighted average … ensuring duplicated overlay geometry is not counted twice'; 'a report layer with per-feature details'"},
"W007046": {
 "rev": "R7: construction freedom affirmed (result-semantic gating); empty-match edge case declared undefined",
 "required_outcome": "Matching features carrying both counts + ONE centroid point feature carrying the same counts.",
 "required_constraints": ["Case-insensitive pattern match on a string attribute", "Count (a)=total input features, (b)=matching features",
                          "Point (c) = centroid of matching features' MERGED geometry"],
 "required_capabilities": ["Attribute pattern selection", "Counting", "Merged-geometry centroid computation"],
 "acceptable_alternatives": ["collect→centroids", "Aggregate statistics + single-point construction",
                             "ANY construction acceptable as long as the result IS the single centroid of the merged matched-geometry set"],
 "failure_conditions": ["Match case-sensitive or wrong field", "Counts wrong or attached to wrong layer",
                        "Centroid computed per-feature or on the unmatched set", "Multiple centroid points emitted"],
 "underdetermined_aspects": ["Empty match set: task text does not define centroid/count-point behaviour — recorded as an undefined edge case; do not default to requiring a centroid"],
 "evidence": "task: 'the centroid of the matching features' merged geometry as a single point'"},
"W055534": {
 "rev": "approved as-is (owner)",
 "required_outcome": "Countries layer carrying all statistics + exported CSV of the final attribute table.",
 "required_constraints": ["Zones = country boundaries", "Indicators: land quality (single epoch) + population density (1500, 1990, 2000)",
                          "Retain country name and ISO fields", "Distinct prefix per indicator epoch", "CSV export"],
 "required_capabilities": ["Multi-raster zonal-statistics orchestration", "Field retention management", "Table export"],
 "acceptable_alternatives": ["Per-raster zonal stats then field merge", "Multi-band batch statistics",
                             "Per-year loops then combined export"],
 "failure_conditions": ["Years attached to land quality or dropped from population density", "Name/ISO fields dropped",
                        "Prefixes colliding/ambiguous", "CSV missing or schema inconsistent with layer"],
 "underdetermined_aspects": [],
 "evidence": "task: 'land quality (one epoch) and population density for the years 1500, 1990, and 2000'; 'distinctly prefixed set of statistics per indicator epoch'; 'export the final attribute table as CSV'"},
"W000674": {
 "rev": "R7: illumination-report requirement removed; native-CRS-derive route demoted from general equivalence to proof-required conditional",
 "required_outcome": "Three georeferenced terrain rasters: slope (degrees), aspect (degrees), hillshade.",
 "required_constraints": ["Computation in projected metric CRS (geometric meaningfulness)", "Slope/aspect in degrees",
                          "Hillshade produced (illumination parameters are free — the task does not require reporting them)",
                          "Three files added to project"],
 "required_capabilities": ["Ensuring terrain derivatives are computed in a CRS satisfying the projected-metric requirement (RESULT constraint — no specific reprojection step mandated; data already conforming needs no reproject)",
                           "Terrain derivative computation ×3"],
 "acceptable_alternatives": ["Reproject→derive each",
                             "Native-CRS-derive routes are NOT generally equivalent (derivatives depend on coordinate scale at computation time) — acceptable ONLY if the delivered derivatives demonstrably satisfy the projected-metric requirement",
                             "GDAL/GRASS/SAGA derivative families (any honoring the requirement)"],
 "failure_conditions": ["Delivered derivatives that do not satisfy the projected-metric computation requirement (result-level judgment)",
                        "Slope/aspect not in degrees",
                        "A derivative missing", "Outputs not georeferenced",
                        "NOTE: absence of an explicit reproject step is NOT a failure (e.g., data already in a conforming CRS); presence of a reproject step does not by itself demonstrate compliance"],
 "underdetermined_aspects": [],
 "evidence": "task: 'must be geometrically meaningful, which requires working in a projected metric CRS'; 'slope in degrees, aspect in degrees, and a hillshade' (no reporting requirement)"},
"W055913": {
 "rev": "R7-4: Intersect+SymDiff-cleanup route removed as unconditional equivalent; intersection+differences route made completeness-verification-conditional",
 "required_outcome": "One polygon layer of non-overlapping atomic zones (unique combination of the two zonings), single-part, uniquely identified, with area/perimeter.",
 "required_constraints": ["Each output polygon = unique combination of the two zonings", "Valid single-part polygons",
                          "Unique zone ID", "Geometry attributes (area, perimeter)"],
 "required_capabilities": ["Two-layer overlay algebra", "Multipart resolution", "Unique ID generation",
                           "Atomic-completeness awareness (all combinations present, none duplicated)"],
 "acceptable_alternatives": ["Union operator route",
                             "(Intersection + two differences) acceptable ONLY with a completeness verification that all atomic combinations are present with correct attributes (conditional)",
                             "REMOVED: 'intersect then symmetrical-difference cleanup' as an unconditional equivalent — it does not generally guarantee atomic completeness"],
 "failure_conditions": ["Zones not atomic (overlaps remain or combinations duplicated/missing)", "Multiparts unresolved",
                        "IDs not unique", "Area/perimeter missing"],
 "underdetermined_aspects": [],
 "evidence": "task: 'each output polygon represents a unique combination of the two zonings'; 'must consist of valid single-part polygons, each uniquely identified'"},
"W056058": {
 "rev": "approved as-is (owner)",
 "required_outcome": "Study-area network + one filtered layer per level + one buffer layer per level.",
 "required_constraints": ["Restrict to study area", "Three levels (Principal, Secundaria, Terciaria) per level attribute",
                          "Each level buffered at its own distinct radius"],
 "required_capabilities": ["Attribute-based level separation", "Differentiated buffer parameters per group", "Multi-output organization"],
 "acceptable_alternatives": ["Clip→filter→buffer or filter→buffer→clip (order-free)", "Expression filters + three buffer runs",
                             "Level loop with parameter table"],
 "failure_conditions": ["Level misclassification (wrong attribute mapping)", "Radius assigned to wrong level",
                        "A level's layer/buffer missing", "Results exceed study area"],
 "underdetermined_aspects": [],
 "evidence": "task: 'three hierarchical levels (Principal, Secundaria, Terciaria) according to the level attribute'; 'each level has a distinct radius'; 'Output: the study-area network, one filtered layer per level, and one buffer layer per level'"},
}

def main():
    frozen = json.load(open(FROZEN, encoding="utf-8"))
    frozen_sha = hashlib.sha256(open(FROZEN, "rb").read()).hexdigest()
    rows = []
    for fr in frozen["rows"]:
        wid = fr["wid"]
        g = GOLD[wid]
        rows.append({
            "task_id": wid,
            "task_text": fr["final_text"],
            # FULL 64-hex digest recomputed here from the same text (the frozen
            # input file stores only 16-char prefixes in its text_sha256 field;
            # truncation convention documented in PCA_PHASE1_WORKNOTES_v1.md §4).
            "task_sha256": hashlib.sha256(fr["final_text"].encode("utf-8")).hexdigest(),
            "sha_note": "full SHA-256 recomputed from task_text; matches the "
                        "frozen file's 16-char prefix in text_sha256",
            "required_outcome": g["required_outcome"],
            "required_constraints": g["required_constraints"],
            "required_capabilities": g["required_capabilities"],
            "acceptable_alternatives": g["acceptable_alternatives"],
            "failure_conditions": g["failure_conditions"],
            "underdetermined_aspects": g["underdetermined_aspects"],
            "revision_note": g["rev"],
            "gold_chain_audit": PENDING,
            "evidence": g["evidence"],
        })
    missing = set(GOLD) ^ {r["task_id"] for r in rows}
    assert not missing, f"gold/frozen mismatch: {missing}"
    payload = {"_meta": {
        "stage": "PCA Stage-1 gold authoring v2 (owner round-1 revisions applied)",
        "supersedes": "pca_b_gold_worksheet_v1.json (SHA 06b30b9c810a2e6d) — kept immutable",
        "revision_source": "owner round-1 (8-item list) + round-5 (scoring-boundary revisions, 8 rows + SHA rule)",
        "sha_convention": "task_sha256 = FULL 64-hex digest recomputed from task_text; "
                          "the frozen input file's text_sha256 field stores only "
                          "16-char prefixes (documented truncation convention)",
        "authority": "frozen inputs ONLY; chains not read",
        "frozen_inputs_sha256": frozen_sha,
        "new_field": "underdetermined_aspects (partial-scoring boundaries, nothing improvised)",
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
