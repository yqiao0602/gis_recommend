"""Adjudication prep: record the source-verified status of B's six dev revisions.

All six verified against sha-verified local mirrors. A is still running;
this file records the verification layer so the final adjudication (after
A lands) has its evidence in place.
"""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

verification = {
    "schema": "gis_recommend.qgis_benchmark_v02_devfid_b_claims_verification.v1",
    "date": "2026-09-11",
    "rule": "every reviewer claim verified against a locally sha-verified source mirror before adjudication; same-name unverified mirrors are never used (the #9-textbook lesson)",
    "verdict": "ALL SIX OF REVIEWER B'S DEVIATION CLAIMS ARE SOURCE-VERIFIED CORRECT; zero hallucinations this round",
    "claims": [
        {"entry": "dev-a13596ae256c7edd", "claim": "mask built from input raster (temp_heights_raster), not from the summarized results", "evidence": "script_0004046.py (github_qgis_workflow_A mirror, sha-verified) L121-126: res_mask INPUT_A=temp_heights_raster; node 2 is a root, no edge from the summarized zone stats", "status": "VERIFIED"},
        {"entry": "dev-1275af8b1d9af30c", "claim": "fieldcalculator FORMULA is str(start_date), a date constant, not a derived-from-sampled-values attribute", "evidence": "script_36707.py (merged-dedup, sha-verified) L80-89: FIELD_NAME='DATE', FORMULA=str(start_date)", "status": "VERIFIED"},
        {"entry": "dev-6e6cdd76539d3dc4", "claim": "'percentage area distribution' is the header's larger business purpose; the gold chain is only clip->dissolve with no percentage operator", "evidence": "script_49399.py (merged-dedup, sha-verified) L2 header comment vs L27-30 chain: only qgis:clip and native:dissolve", "status": "VERIFIED"},
        {"entry": "dev-79d89a21b8f3bbce", "claim": "intersection direction inverted: INPUT=Catchments (the input layer), OVERLAY=merge(Zones,Roads)", "evidence": "script_0007944.py (github_qgis_workflow mirror, sha-verified) L236-247: INPUT=parameters['Catchments'], OVERLAY=merge", "status": "VERIFIED"},
        {"entry": "dev-8cf59ec70d53258b", "claim": "the two significance masks are computed independently from slope and p-value layers; node 1 does not consume node 0's output", "evidence": "script_0007193.py (github_qgis_workflow_A mirror, sha-verified) L133-143: both rastercalculator calls take INPUT_A=slope_layer, INPUT_B=pval_layer directly", "status": "VERIFIED"},
        {"entry": "dev-9d177117e8345d57", "claim": "first join attaches admin attributes TO the settlement points (INPUT=points, JOIN=admin), not to the polygons; task text reversed the flow", "evidence": "script_0007727.py (github_qgis_workflow mirror, sha-verified) L24-32: INPUT=pplp-sample.shp, JOIN=admin.shp, comment 'Joining admin attributes to points'", "status": "VERIFIED"},
    ],
    "next": "await reviewer A; then adjudicate (B's exact fixes are the default resolution for verified claims, pending A's independent view)",
}
out = BASE / "v02_devfid_b_claims_verification_v1.json"
out.write_text(json.dumps(verification, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
