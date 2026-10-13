#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Stage-2 — formal chain-consistency audit ledger (owner-approved start).

Inputs (all frozen):
  - frozen task texts:  pca_b_group_final_inputs_v1.json (SHA 1a13ad8d...)
  - gold worksheet:     pca_b_gold_worksheet_v2.json (SHA 0dc643980e8d4b8e —
                        the ONLY current gold version referenced, per owner)
  - original chains:    docs/reports/v2a_manifest/v2a_A_dev.jsonl (processes/
                        links extracted verbatim per wid — zero transcription)

Discipline (pca_chain_audit_labels_v1.md): semantic consistency vs frozen
task text; route names never prove compliance; unspecified parameters are
never errors; main label covers reliably-judgeable dimensions only;
UNDERDETERMINED = audit conclusion, ESCALATE-OWNER = disposition;
adjudication=NONE -> escalation_reason=null.
"""
import json, hashlib

D = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/"
FROZEN = D + "pca_b_group_final_inputs_v1.json"
GOLD = D + "pca_b_gold_worksheet_v2.json"
DEV = "docs/reports/v2a_manifest/v2a_A_dev.jsonl"
OUT = D + "pca_b_chain_audit_v1.json"
GOLD_SHA = "0dc643980e8d4b8e"

AUD = {
"W000473": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "XOR outcome (polygon)", "support": "native:symmetricaldifference produces the symmetric-difference polygon layer", "issue": None},
  {"dimension": "route membership", "support": "dissolution-then-XOR is an endorsed alternative ('XOR after prior dissolution to single parts')", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["double dissolve (one per input layer) is preparatory, not a deviation"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Any-valid-route task; chain is one of the endorsed routes."},
"W068342": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "CRS handling", "support": "three native:reprojectlayer steps establish a projected working CRS", "issue": None},
  {"dimension": "screening occurs", "support": "two native:extractbylocation steps filter points against reference layers", "issue": None},
  {"dimension": "safety-constraint content and binding (grid/plot/both)", "support": None,
   "issue": "underdetermined per gold; chain suggests both references used but the constraint values are not judgeable (researcher note only)"}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["negative-buffer magnitude and which layer is buffered are implementation choices in the underdetermined dimension"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Main label limited to structure-level judgeable dimensions per gold."},
"W068582": {"label": "PARTIALLY_CONSISTENT",
 "dimension_evidence": [
  {"dimension": "AOI restriction", "support": "native:clip restricts land cover to AOI (with prior reprojection + fixgeometries)", "issue": None},
  {"dimension": "CRS consistency", "support": "native:reprojectlayer opens the chain", "issue": None},
  {"dimension": "Manning lookup/assignment", "support": None, "issue": "no join/lookup/field step for CODE_18->n anywhere in the chain"},
  {"dimension": "area in m2 and ha", "support": None, "issue": "no area computation step in the chain"}],
 "missing_required_operations": ["Manning coefficient assignment (CODE_18->n lookup/join)",
                                 "area computation in m2 and hectares"],
 "suspect_but_not_failures": ["fixgeometries is reasonable preparation"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Chain likely captures Processing calls only; PyQGIS-level attribute work absent. Original task_text states Manning/area are performed — chain/task mismatch recorded verbatim; flag for owner attention on chain representativeness."},
"W067404": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "circular neighbourhood", "support": "native:buffer creates radius neighbourhoods around points", "issue": None},
  {"dimension": "statistics computed", "support": "native:zonalstatisticsfb computes raster statistics per neighbourhood", "issue": None},
  {"dimension": "re-attachment to original locations", "support": "native:centroids returns results to point positions (buffer centroids coincide with original points)", "issue": None},
  {"dimension": "exact statistic set", "support": None, "issue": "underdetermined per gold; chain's statistic set not judgeable against frozen text (researcher reference only)"}],
 "missing_required_operations": [],
 "suspect_but_not_failures": [],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": ""},
"W000635": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "centred band construction", "support": "buffer -> buffer -> difference yields inward/outward offset difference = centred band (endorsed alternative)", "issue": None},
  {"dimension": "artefact cleaning", "support": "multiparttosingleparts + fixgeometries + simplify + final dissolve + final fix", "issue": None},
  {"dimension": "width semantics consistency", "support": "paired half-width buffers under total-width primary reading", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["simplify tolerance (0.0001 m) is an implementation parameter"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": ""},
"W000890": {"label": "PARTIALLY_CONSISTENT",
 "dimension_evidence": [
  {"dimension": "severity-precedence overlap resolution", "support": "extractbyexpression + mergevectorlayers + difference chain implements ranked exclusivity (endorsed route)", "issue": None},
  {"dimension": "intersection with municipalities", "support": "final native:intersection with municipal boundaries", "issue": None},
  {"dimension": "per-municipality dominant-class aggregation", "support": None, "issue": "no area aggregation / argmax-by-area step after intersection"},
  {"dimension": "dominant-class table output", "support": None, "issue": "no table/statistics output step in chain"}],
 "missing_required_operations": ["per-municipality class-area aggregation and dominant selection",
                                 "dominant-class table output (code/name/area)"],
 "suspect_but_not_failures": ["mergevectorlayers usage between stages (assembly choice)"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Core semantics (precedence + intersection) present; aggregation/report tail missing."},
"W033927": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "track-based visibility polygons", "support": "createpointslayerfromtable -> pointstopath builds track; wedgebuffers creates oriented viewshed polygons (endorsed route)", "issue": None},
  {"dimension": "single-class units", "support": "dissolve merges overlapping areas (grouped-dissolve semantics available for class-wise merge)", "issue": None},
  {"dimension": "cross-class priority rule", "support": None, "issue": "underdetermined per gold; dissolve grouping field not visible — recorded, not judged"},
  {"dimension": "styling", "support": "two setlayerstyle steps", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["dissolve grouping field not visible in chain: if ungrouped, class separation would be lost — suspect, not judgeable from chain alone",
                              "second createpointslayerfromtable purpose (annotation point reconstruction) — implementation detail"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": ""},
"W056274": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "inside-paddock distance semantics", "support": "chain (rasterize->proximity->clip) is the original per-paddock interior-point implementation; script recovery (round-3) verified interior-point selection precedes rasterization", "issue": None},
  {"dimension": "per-paddock scoping", "support": "gdal:cliprasterbymasklayer clips to paddock boundaries", "issue": None},
  {"dimension": "grid parameters", "support": None, "issue": "underdetermined per gold; resolution/origin not judged"}],
 "missing_required_operations": [],
 "suspect_but_not_failures": [],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Chain semantics match the verified inside-paddock reading."},
"W067268": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "terrain factor", "support": "gdal:viewshed over reprojected DEM (reprojectlayer + warpreproject inputs)", "issue": None},
  {"dimension": "distance attenuation", "support": "qgis:distancetonearesthubpoints + fieldcalculator corrections", "issue": None},
  {"dimension": "ground type / barriers", "support": "viewshed (barriers) + zonalstatistics/intersection sampling feeding attenuation field calculations", "issue": None},
  {"dimension": "per-receptor values + styled source", "support": "receptor-side sampling/joins/field calculations; setlayerstyle on source point", "issue": None},
  {"dimension": "numerical BS 5228 compliance", "support": None,
   "issue": "not confirmable from structure evidence alone (gold boundary); neither operator presence implies compliance nor absence implies violation"}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["hexagonal grid intermediate construction — route detail, reasonable"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Main label covers structure-level dimensions only (gold main-label boundary)."},
"W055908": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "simple random mode", "support": "native:randomselection", "issue": None},
  {"dimension": "stratified mode with within-class sampling", "support": "native:randomselectionwithinsubsets", "issue": None},
  {"dimension": "X/Y coordinate fields", "support": "native:addxyfields", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["intermediate saveselectedfeatures materializations — implementation choice"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Sampling quantities/quotas unjudgeable per gold — not assessed."},
"W066995": {"label": "PARTIALLY_CONSISTENT",
 "dimension_evidence": [
  {"dimension": "extent restriction", "support": "native:clip (+ native:extenttolayer building the extent layer)", "issue": None},
  {"dimension": "single merged layer", "support": "native:mergevectorlayers", "issue": None},
  {"dimension": "feature-service retrieval", "support": None, "issue": "no service query/download step in chain (performed outside Processing chain)"},
  {"dimension": "GeoPackage export + styling", "support": None, "issue": "no export/styling steps in chain"}],
 "missing_required_operations": ["feature-service retrieval step (outside chain)",
                                 "GeoPackage export and styling steps"],
 "suspect_but_not_failures": ["opening native:buffer (geometry-repair buffering per original description) — suspect, not judgeable"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Retrieval/export likely at Python layer; chain/task mismatch recorded verbatim."},
"W055494": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "eligibility screening", "support": "fieldcalculator + extractbyexpression implement threshold/type criteria", "issue": None},
  {"dimension": "adjacency-aware merge with attribute retention", "support": "aggregate/dissolve group merging + fieldcalculator retaining dominant-stand attributes", "issue": None},
  {"dimension": "merged flag semantics", "support": "fieldcalculator steps define flags (1/0 per original description)", "issue": None},
  {"dimension": "merge order / grouping uniqueness", "support": "one valid grouping implemented", "issue": "multiple valid groupings allowed per gold — order not judged"}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["orderbyexpression ordering purpose — implementation choice within multi-valid-grouping allowance"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": ""},
"W068833": {"label": "PARTIALLY_CONSISTENT",
 "dimension_evidence": [
  {"dimension": "grid alignment", "support": "gdal:warpreproject aligns rasters to a target grid", "issue": None},
  {"dimension": "multi-raster orchestration", "support": None, "issue": "chain shows a single warp+translate template pair; batch loop not represented"},
  {"dimension": "alignment-parameter manifest", "support": None, "issue": "no manifest generation step in chain (original-text output requirement)"}],
 "missing_required_operations": ["per-raster batch loop representation",
                                 "alignment-parameter manifest generation"],
 "suspect_but_not_failures": ["gdal:translate (preview/copy of first aligned result per original description)"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Alignment core present; orchestration/manifest absent (likely Python-layer)."},
"W067092": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "overlay decomposition + area weighting", "support": "native:intersection -> fieldcalculator (attribute*area) -> dissolve per input feature", "issue": None},
  {"dimension": "duplicate-geometry handling", "support": "addautoincrementalfield + dissolve-overlay-fields combination (original de-dup semantics)", "issue": None},
  {"dimension": "report layer", "support": "orderbyexpression -> dropgeometries produces the attribute-only detail table", "issue": None},
  {"dimension": "CRS check expectation", "support": "chain assumes layer inputs; no explicit check step", "issue": "expectation-level constraint; absence of an explicit check step is not judgeable as violation"}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["deletecolumn placements — intermediate schema management"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": ""},
"W007046": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "case-insensitive pattern selection", "support": "native:extractbyexpression with expression-based matching", "issue": None},
  {"dimension": "both counts", "support": "two fieldcalculator steps (total + matching counts)", "issue": None},
  {"dimension": "merged-geometry centroid as single point", "support": "collect -> fixgeometries -> centroids", "issue": None},
  {"dimension": "counts carried on both outputs", "support": "retainfields on centroid output; calculator fields on matched layer", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": ["setprojectvariable x2 (count storage mechanism) — implementation choice"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Empty-match behaviour: undefined edge case per gold — not assessed."},
"W055534": {"label": "PARTIALLY_CONSISTENT",
 "dimension_evidence": [
  {"dimension": "zonal statistics over countries", "support": "native:zonalstatistics (single instance)", "issue": None},
  {"dimension": "multi-indicator orchestration (land quality + population x3 years)", "support": None, "issue": "chain shows one zonalstatistics; the four-epoch loop is not represented"},
  {"dimension": "field retention + prefixed statistics", "support": "deletecolumn consistent with keep name/ISO + prefixed stats", "issue": None},
  {"dimension": "CSV export", "support": None, "issue": "no export step in chain"}],
 "missing_required_operations": ["multi-indicator/per-year orchestration representation",
                                 "CSV export step"],
 "suspect_but_not_failures": ["fixgeometries placement relative to zonal statistics (order not judged)"],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Single-instance chain likely a template; loop/CSV at Python layer."},
"W000674": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "projected-metric computation (result constraint)", "support": "gdal:warpreproject precedes all derivations", "issue": None},
  {"dimension": "slope/aspect/hillshade trio", "support": "gdal:slope, gdal:aspect, gdal:hillshade", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": [],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": "Result-constraint scoring: reproject presence consistent with requirement; degrees-units parameters not visible (not judged)."},
"W055913": {"label": "CONSISTENT",
 "dimension_evidence": [
  {"dimension": "atomic overlay zones", "support": "native:union of the two zoning layers (endorsed route)", "issue": None},
  {"dimension": "single-part validity", "support": "fixgeometries x2 + native:multiparttosingleparts", "issue": None},
  {"dimension": "unique ID + geometry attributes", "support": "addautoincrementalfield + exportaddgeometrycolumns (area/perimeter)", "issue": None}],
 "missing_required_operations": [],
 "suspect_but_not_failures": [],
 "adjudication": "NONE", "escalation_reason": None,
 "notes": ""},
"W056058": {"label": "INCONSISTENT",
 "dimension_evidence": [
  {"dimension": "study-area restriction", "support": "native:clip restricts network to study area", "issue": None},
  {"dimension": "three-level separation (Principal/Secundaria/Terciaria)", "support": None,
   "issue": "no level separation/filtering step anywhere in the chain — required_outcome structure absent"},
  {"dimension": "per-level distinct buffer radii", "support": None,
   "issue": "single native:buffer only; the three distinct radii and per-level buffer layers cannot be produced by this chain"}],
 "missing_required_operations": ["level separation into three filtered layers",
                                 "three buffers with distinct per-level radii",
                                 "per-level output organization"],
 "suspect_but_not_failures": [],
 "adjudication": "ESCALATE-OWNER",
 "escalation_reason": "INCONSISTENT verdict: chain output structure (one clip + one buffer) does not match required_outcome structure (three-level organization); per discipline #4 the task's audit-pool usability requires an owner ruling.",
 "notes": ""},
}

def main():
    frozen = json.load(open(FROZEN, encoding="utf-8"))
    gold = json.load(open(GOLD, encoding="utf-8"))
    dev = {json.loads(l)["wid"]: json.loads(l) for l in open(DEV, encoding="utf-8")}
    frozen_sha = hashlib.sha256(open(FROZEN, "rb").read()).hexdigest()
    gold_sha = hashlib.sha256(open(GOLD, "rb").read()).hexdigest()
    assert gold_sha.startswith(GOLD_SHA), f"gold file SHA {gold_sha[:16]} != {GOLD_SHA}"
    rows = []
    for fr in frozen["rows"]:
        wid = fr["wid"]
        a = AUD[wid]
        chain = [p["operator_id"] for p in dev[wid]["processes"]]
        links = dev[wid].get("links", [])
        rows.append({
            "wid": wid,
            "task_sha256_full": hashlib.sha256(fr["final_text"].encode()).hexdigest(),
            "gold_chain": chain,                      # verbatim from dev-120
            "n_links": len(links),
            "label": a["label"],
            "dimension_evidence": a["dimension_evidence"],
            "missing_required_operations": a["missing_required_operations"],
            "suspect_but_not_failures": a["suspect_but_not_failures"],
            "adjudication": a["adjudication"],
            "escalation_reason": a["escalation_reason"],
            "adjudication_resolved": None,
            "audit_notes": a["notes"],
        })
    assert len(rows) == 19
    from collections import Counter
    dist = Counter(r["label"] for r in rows)
    assert dist["INCONSISTENT"] + dist["UNDERDETERMINED"] <= 3
    for r in rows:
        if r["adjudication"] == "NONE":
            assert r["escalation_reason"] is None
    payload = {"_meta": {
        "stage": "PCA Stage-2 formal chain-consistency audit v1",
        "protocol": "pca_chain_audit_labels_v1.md (round-7 closeout)",
        "gold_version_bound": GOLD_SHA + " (FROZEN per owner; bad86ac7 not referenced)",
        "frozen_inputs_sha256": frozen_sha,
        "chain_source": DEV + " (frozen benchmark dev-120 processes/links, verbatim)",
        "discipline": ["audit-not-rewrite", "missing/suspect/unconfirmable tripartite",
                       "operator-name != semantic evidence", "impact-scope escalation",
                       "per-row evidence retained"],
        "label_distribution": dict(dist),
        "n_rows": len(rows)},
        "rows": rows}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("label distribution:", dict(dist))
    print("escalations:", [r["wid"] for r in rows if r["adjudication"] == "ESCALATE-OWNER"])
    print("file_sha256:", hashlib.sha256(blob.encode()).hexdigest()[:16])
    print("saved:", OUT)

if __name__ == "__main__":
    main()
