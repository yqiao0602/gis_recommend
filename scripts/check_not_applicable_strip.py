"""Check raw param_keys in discovery call_sites for the not_applicable entries."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for e in rows[1:]:
    if e["parameter_strip"]["status"] == "not_applicable":
        r = recs[e["source"]["primary_discovery_ref"]]
        cs = (r.get("call_sites") or [])[:2]
        sample = [{"operator": c.get("operator_id"), "param_keys": c.get("param_keys", "ABSENT"), "keys_in_call": sorted((c.get("param_keys") or []) or [])[:6]} for c in cs]
        print(e["packet_entry_id"][:24], "|", e["source"]["source_root_id"], "|", sample)
