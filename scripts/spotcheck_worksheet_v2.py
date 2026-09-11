"""Spot-check instance-level call sites in worksheet v2."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
rows = [json.loads(l) for l in (WT / "benchmarks" / "qgis_planner_v1" / "authority" / "v02_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for e in rows[1:]:
    if e["packet_entry_id"].startswith("recovered-361c5eb306"):
        print("entry #4 (11 nodes, repeated operators) instance call sites:")
        for m in e["source_call_sites"]:
            print("  node %d: %s %s -> %s" % (m["node_index"], m["operator"], m["lines"], m["output_target"]))
        print("strip:", e["parameter_strip"]["status"], "| keys:", len(e["parameter_strip"]["keys"]))
        print()
    if e["packet_entry_id"].startswith("recovered-fc01749f30"):
        print("entry #21 (corrected hybrid) instance call sites:")
        for m in e["source_call_sites"]:
            print("  node %d: %s %s" % (m["node_index"], m["operator"], m["lines"]))
        print("output_cardinality:", e["output_cardinality"]["cardinality"], e["output_cardinality"]["output_count"])
