"""v0.2.1: author the single operator_explicit second variant for dec749a979.

The adjudicated first variant (planning_oriented, thermal refugia) already
exists in v02_task_derivation_v4.jsonl and enters v0.2.1 unchanged with the
DAG. Only ONE new text is authored here: the style-paired operator_explicit
second variant, derived from the same sha-verified source evidence.
"""
import json
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# gold: polygonize -> extractbyattribute -> fieldcalculator -> extractbyexpression -> zonalstatistics (linear 5)
# source: script_6649.py (sha 8e5f3b705e...) -- polygonize mask, keep valid patches, add area, further condition, zonal MEAN
V201_V2 = ("Convert the valid cells of the classified raster to polygons, filter the polygons by attribute "
           "to keep the qualifying patches, add a computed area attribute, apply a further attribute-based "
           "condition to the patches, and run zonal statistics over each remaining patch.")

record = {
    "packet_entry_id": "final-201-dec749a979-v2",
    "pool_key": "dec749a979",
    "variant": "v2",
    "variant_role": "second_paired_with_adjudicated_v1",
    "task_text": V201_V2,
    "derivation_method": "L3_deterministic_paraphrase",
    "task_style": "operator_explicit",
    "task_scope": "full_workflow",
    "output_expression": "single",
    "evidence": ("style-paired with the adjudicated planning_oriented v1 (thermal refugia, dual-reviewed, "
                 "owner re-adjudicated ACCEPT after the fb-hallucination was overturned by direct source check); "
                 "this variant leads with the operators (polygonize, attribute filter, field calculation, "
                 "expression filter, zonal statistics); mask values, field names, expressions, and statistics "
                 "kinds stripped per the 18 recovered parameter keys"),
    "provenance": {
        "source_authority_key": "source_sha256:8e5f3b705ede",
        "source_sha256": "8e5f3b705ede" + "0e58f7b0c0b9b0e02b1c3ee9d21c2c5a" [:32],
        "derivation_method": "L3_deterministic_paraphrase",
        "derived_text_sha256": jhash(V201_V2),
        "canonical_dag_key": "dec749a979996d6f",
        "review_status": "draft_pending_dual_fidelity_review",
        "split": "final_v02_1",
    },
}

# fix provenance fields properly
ws = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
w = next(x for x in ws[1:] if x["packet_entry_id"].startswith("recovered-dec749a979"))
record["provenance"]["source_sha256"] = w["source"]["source_sha256"]
record["provenance"]["source_authority_key"] = "source_sha256:" + w["source"]["source_sha256"]

out = BASE / "v02_1_dec749a979_v2_draft_v1.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_1_variant_draft.v1",
        "date": "2026-09-11",
        "note": "v0.2.1 adds ONE task total: the adjudicated v1 enters with the DAG; only this operator_explicit v2 is newly authored",
        "records": 1,
    }, ensure_ascii=False) + "\n")
    f.write(json.dumps(record, ensure_ascii=False) + "\n")
print("written:", out.name)
print("task:", V201_V2)
