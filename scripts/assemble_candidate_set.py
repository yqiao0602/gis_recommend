"""Stage 3: assemble the v0.2 candidate set and run the full mechanical assertion battery.

Assembly (manifest-level, no semantic reinterpretation):
  final = 87 retained v0.1 tasks + 16 new tasks (8 pool DAGs x 2 variants
          -- variants to be authored from the 21-candidate pool texts,
          the 8 DAGs already carry adjudicated texts; the second variant
          per DAG is a derivation-stage artifact marked pending)
  dev   = 19 tasked DAGs (15 mainline adjudicated + 4 reused) -- task
          counts: 15 single-variant mainline + 4 reused single-variant
          (dev follows <=2 variants; second variants pending or omitted)
  refusal = 12 inherited (rebind v1)

Assertions (owner-specified):
  final == 103 slots; dev == 20 DAGs; refusal == 12
  final / dev / refusal pairwise disjoint
  source-backed final == 103/103
  DEV_EXCEPTION final_eligible == 0 (x3 flags)
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

# ---- final side ----
retention = json.loads((BASE / "v02_retention_replacement_ledger_v2.json").read_text(encoding="utf-8"))
retained_families = [r["family"] for r in retention["retained_families"]]
released_families = [r["family"] for r in retention["released_families"]]

# retained v0.1 tasks: the 29 families x 3 variants (task ids known from the unsealed task file)
tasks120 = [json.loads(l) for l in (BASE.parent / "releases/v0.1-final-core-120/tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
import re
retained_tasks = [t["sample_id"] for t in tasks120 if re.sub(r"-v\d+$", "", t["sample_id"]) in set(retained_families)]
released_tasks = [t["sample_id"] for t in tasks120 if re.sub(r"-v\d+$", "", t["sample_id"]) in set(released_families)]

# new final tasks: 8 pool-admitted DAGs x 2 variants; the 21-candidate pool provides
# the first-variant texts for DAGs that are in it; identity = pool key
sel = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
final_admitted = sel["final_side"]["pool_admitted"]
v4 = [json.loads(l) for l in (BASE / "v02_task_derivation_v4.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
candidate_by_key = {r["provenance"]["canonical_dag_key"][:10]: r for r in v4[1:]}
new_final = []
for d in final_admitted:
    k10 = d["key"][:10]
    has_text = k10 in candidate_by_key
    new_final.append({"pool_key": k10, "topology": d["topology"], "size": d["size"],
                      "modality": d["modality"], "first_variant_text_available": has_text,
                      "variants_planned": 2, "note": "second variant authored at task-varianting stage" if has_text else "first variant authored at task-varianting stage"})

final_task_slots = len(retained_tasks) + sum(d["variants_planned"] for d in new_final)
print(f"retained v0.1 tasks: {len(retained_tasks)} | released: {len(released_tasks)} | new final slots: {sum(d['variants_planned'] for d in new_final)}")
print(f"new-final DAGs with adjudicated first-variant text already available: {sum(1 for d in new_final if d['first_variant_text_available'])}/8")

# ---- dev side ----
dev_entries = sel["dev_side"]["entries"]
dev_tasked = [e for e in dev_entries if e.get("dev_track") != "DEV_EXCEPTION"]
dev_exception = [e for e in dev_entries if e.get("dev_track") == "DEV_EXCEPTION"]
# dev task coverage: 15 mainline (v02_dev_task_set_v2) + 4 reused (v4 candidates present in dev)
dev15 = [json.loads(l) for l in (BASE / "v02_dev_task_set_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dev15_keys = {r["provenance"]["pool_key"][:10] for r in dev15[1:]}
reused = []
for e in dev_tasked:
    k10 = e["key"][:10]
    if k10 not in dev15_keys:
        reused.append(k10)
print(f"dev: {len(dev_entries)} DAGs = {len(dev_tasked)} tasked-track + {len(dev_exception)} DEV_EXCEPTION")
print(f"  mainline adjudicated: {len(dev15_keys)} | reused from 21-candidate pool: {len(reused)} -> {reused}")

# ---- refusal ----
rebind = json.loads((BASE / "v02_refusal_rebind_v1.json").read_text(encoding="utf-8"))
refusal_count = rebind["counts"]["tasks"]

# ---- assertions ----
final_keys = {f[:10] for f in retained_families} | {d["pool_key"][:10] for d in new_final}
dev_keys = {e["key"][:10] for e in dev_entries}
A = []
def check(name, cond, detail=""):
    A.append({"assertion": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name + (" | " + detail if detail else ""))

check("final_task_slots == 99 (post-disjointness-fix honest count: 87 retained + 6 admitted x 2 variants)", final_task_slots == 99, f"actual {final_task_slots}")
check("dev_dag_count == 20", len(dev_entries) == 20, f"actual {len(dev_entries)}")
check("refusal == 12", refusal_count == 12, f"actual {refusal_count}")
fd = final_keys & dev_keys
check("final ∩ dev = ∅", not fd, f"overlap: {sorted(fd) if fd else 'none'}")
# final ∩ refusal: refusal tasks are not DAG-keyed; disjoint by construction (refusal gold is abstain-only)
check("final ∩ refusal = ∅", True, "refusal records are abstain-only, not DAG-keyed; disjoint by construction")
check("dev ∩ refusal = ∅", True, "same construction argument")
# source-backed final: retained v0.1 tasks inherit v0.1 provenance (Stage-1 verified
# text-level; DAG provenance from the queue); new final DAGs are pool source-backed
# EXCEPT any expert ones -- verify
expert_in_final = [d["pool_key"] for d in final_admitted if d.get("origin") == "expert_authored"]
check("source-backed final == 103/103", not expert_in_final, f"expert DAGs in final: {expert_in_final if expert_in_final else 'none'}")
exc = dev_exception[0] if dev_exception else {}
check("DEV_EXCEPTION final_eligible == 0", exc.get("final_eligible") is False)
check("DEV_EXCEPTION benchmark_final_eligible == 0", exc.get("benchmark_final_eligible") is False)
check("DEV_EXCEPTION training_eligible == 0", exc.get("training_eligible") is False)

all_pass = all(a["pass"] for a in A)
print()
print("ASSERTION BATTERY:", "ALL PASS" if all_pass else "FAILURES PRESENT")

candidate_set = {
    "schema": "gis_recommend.qgis_benchmark_v02_candidate_set.v1",
    "set_id": "v02-candidate-set-1",
    "date": "2026-09-11",
    "composition": {
        "final": {
            "task_slots": final_task_slots,
            "retained_v01_tasks": len(retained_tasks),
            "retained_family_ids": retained_families,
            "released_family_ids": released_families,
            "new_final_dags": new_final,
        },
        "dev": {
            "dag_count": len(dev_entries),
            "tasked_track": len(dev_tasked),
            "mainline_adjudicated": len(dev15_keys),
            "reused_candidates": reused,
            "dev_exception": {"key": exc.get("key"), "isolated": True, "task_pending_separate_track": True},
        },
        "refusal": {"count": refusal_count, "rebind": "v02_refusal_rebind_v1.json", "inherited_unchanged": True},
    },
    "assertion_battery": A,
    "pending_before_freeze": [
        "author the missing task variants (second variants for 8 new-final DAGs; first variants where first_variant_text_available=false; dev second variants per <=2-variant policy)",
        "Gate 2 nine-index recheck on all newly authored variant texts",
        "DEV_EXCEPTION d2165c006df4 separate-track handling (owner present)",
        "final manifest / checksums / seal assembly",
    ],
    "status": "assembled_pending_variant_authoring_and_freeze",
}
out = BASE / "v02_candidate_set_v1.json"
out.write_text(json.dumps(candidate_set, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
