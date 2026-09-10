"""Dump the full fidelity worksheet content for owner review."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
entries = rows[1:]
for i, e in enumerate(entries, 1):
    d = e["recovered_dag"]
    print(f"### {i}. {e['packet_entry_id']} [{e['task_scope']}] outcome={e['final_outcome']}")
    print(f"  anchor: {e['quota_anchor_l3']} | covered: {','.join(e['covered_l3'])}")
    src = e["source"]
    print(f"  source: {src['source_root_id']} | {Path(str(src['source_path'])).name} | sha={str(src['source_sha256'])[:12]} | refs={len(src['supporting_discovery_refs'])}")
    for so in e["source_operations"]:
        print(f"    - {so['op']} [{so['l3']} {so['family']}] {so['lines']}")
    print(f"  dag: {' -> '.join(d['operators']) if e['final_outcome']!='accept_corrected_graph_dual_rereviewed' else d['operators']}")
    print(f"  edges: {d['edges']}")
    print(f"  io: in={e['io_scope']['graph_inputs_roots']} out={e['io_scope']['graph_outputs_sinks']}")
    print(f"  strip: {','.join(e['parameters_to_strip'])}")
    for a in e["potential_ambiguities"]:
        print(f"  amb: {a[:220]}")
    print()
