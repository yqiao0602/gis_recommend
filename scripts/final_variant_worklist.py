"""Enumerate the 6 final-admitted DAGs and their variant authoring needs.

3 of 6 already carry adjudicated first-variant texts (from the 21-candidate
pool); 3 need first variants; all 6 need second variants. Outputs the
authoring worklist.
"""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

sel = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
admitted = sel["final_side"]["pool_admitted"]

v4 = [json.loads(l) for l in (BASE / "v02_task_derivation_v4.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
cand = {r["provenance"]["canonical_dag_key"][:10]: r for r in v4[1:]}

worklist = []
for d in admitted:
    k10 = d["key"][:10]
    has = k10 in cand
    worklist.append({
        "pool_key": k10, "topology": d["topology"], "size": d["size"], "modality": d["modality"],
        "origin": d.get("origin", "existing"),
        "first_variant": "ADJUDICATED_REUSE" if has else "DERIVE_NEW",
        "second_variant": "DERIVE_NEW",
    })
print("final-admitted DAGs:", len(worklist))
for w in worklist:
    print(f"  {w['pool_key']} [{w['topology']}/{w['size']}/{w['modality']}] first={w['first_variant']}")

n_first_new = sum(1 for w in worklist if w["first_variant"] == "DERIVE_NEW")
print(f"\nauthoring work: {n_first_new} first variants + 6 second variants = {n_first_new + 6} texts; "
      f"{6 - n_first_new} first variants reused as-is")

out = BASE / "v02_final_variant_worklist_v1.json"
out.write_text(json.dumps({
    "schema": "gis_recommend.qgis_benchmark_v02_final_variant_worklist.v1",
    "date": "2026-09-11",
    "rule": "3 adjudicated first variants are reused without re-derivation; remaining first variants and all second variants go through worksheet->derivation->dual review; DAGs are frozen, never re-adjudicated",
    "entries": worklist,
}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
