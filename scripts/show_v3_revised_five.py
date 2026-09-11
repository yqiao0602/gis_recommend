"""Display the 5 revised entries from task set v3 with full binding context."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

v3 = [json.loads(l) for l in (BASE / "v02_task_derivation_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ws = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ws_by = {e["packet_entry_id"]: e for e in ws[1:]}

TARGETS = [
    "recovered-302f34cdd7d87920",
    "recovered-361c5eb306dbc618",
    "recovered-429556807ae79c01",
    "recovered-4cb8772d44c58cc4",
    "recovered-8c87bab93cfc8fe5",
]
for r in v3[1:]:
    if r["packet_entry_id"] not in TARGETS:
        continue
    w = ws_by[r["packet_entry_id"]]
    d = w["recovered_dag"]
    print("=" * 92)
    print(r["packet_entry_id"], f"[{r['task_scope']} | {r['output_expression'].split(' ')[0]}]")
    print("FINAL:  ", r["task_text"])
    if r.get("pre_review_original_text"):
        print("ORIG-1: ", r["pre_review_original_text"])
    if r.get("dual_review_original_text"):
        print("ORIG-2: ", r["dual_review_original_text"])
    print("REASON: ", (r.get("dual_review_reason") or r.get("pre_review_reason") or "")[:160])
    print("GOLD:   ", " -> ".join(d["operators"]))
    print("EDGES:  ", d["edges"])
    print("SRC:    ", w["source"]["source_path"].split("\\")[-1] if "\\" in str(w["source"]["source_path"]) else w["source"]["source_path"],
          "|", "; ".join(f"{m['operator'].split(':')[-1]}@{m['lines']}" for m in w["source_call_sites"]))
    print("STRIP:  ", w["parameter_strip"]["keys"])
