"""Detail the 16 would-pass fan-out records: distinct DAGs, anchors, modality, review markers."""
import json
import sys
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WT))
from scripts import build_qgis_benchmark_exclusion_ledger as exclusion  # noqa: E402

BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"

refs = [
    "stable101_routing_v6:178", "stable101_routing_v6:278", "stable101_routing_v6:332",
    "stable101_routing_v6:333", "stable101_routing_v6:334", "stable101_routing_v6:498",
    "stable101_routing_v6:578", "stable101_routing_v6:794", "stable101_routing_v6:795",
    "stable101_routing_v6:796",
]
# re-derive the full 16 via the same filter as the recheck secondary pass
roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"] for f in roster["supported_families"]}
mapping_artifact = json.loads((BASE / "qgis_operator_l3_mapping.json").read_text(encoding="utf-8"))
mappings = {row["operator_id"]: row for row in mapping_artifact["entries"]}
cap_rows = [json.loads(l) for l in (BASE / "capability_matrix.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
admitted_ops = set()
for r in cap_rows:
    admitted_ops.update(r["admitted_operator_ids"])

recs = {}
for i, line in enumerate(P1.read_text(encoding="utf-8").splitlines()):
    if line.strip():
        recs[f"stable101_routing_v6:{i}"] = json.loads(line)

def ledger_rows():
    with (BASE / "source_exclusion_ledger.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
indexes = exclusion.build_overlap_indexes(ledger_rows())

ALLOWED_ACTIONS = {"auto_accept_candidate", "recover_call_graph", "split_subworkflow"}
cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
adm_refs = {c["discovery_ref"] for c in cands if c.get("discovery_ref")}

from scripts.build_qgis_benchmark_candidate_pool import graph_profile  # noqa: E402

winners = []
for ref, r in recs.items():
    edges_raw = r.get("dependency_edges") or []
    if not edges_raw:
        continue
    outdeg = collections.Counter(e[0] for e in edges_raw)
    if not any(v >= 2 for v in outdeg.values()):
        continue
    ops = set(r.get("operator_ids") or [])
    if not (ops and ops <= admitted_ops):
        continue
    if r.get("action") in ALLOWED_ACTIONS or ref in adm_refs:
        continue
    if r.get("unresolved_output_references") or []:
        continue
    operators = [str(v).lower() for v in (r.get("ordered_operator_ids") or r.get("operator_ids") or [])]
    codes = [str(v) for v in (r.get("mapped_l3_chain") or [])]
    if not (operators and len(operators) == len(codes) and all(
        op in mappings and mappings[op]["strict_catalog_present"]
        and mappings[op]["mapping_status"] == "stable101_direct"
        and mappings[op]["stable101_l3"] == code and mappings[op]["headline_eligible"]
        for op, code in zip(operators, codes)
    )):
        continue
    edges = [(s, t) for s, t, _k in exclusion._edges(r)]
    if graph_profile(len(operators), edges) is None:
        continue
    if exclusion.check_candidate_overlap(r, indexes):
        continue
    analytical = [c for op, c in zip(operators, codes) if mappings[op]["task_role"] == "analytical"]
    anchor = (analytical or codes)[0]
    covered = set(codes)
    if not (anchor in SUPPORTED and covered <= (SUPPORTED | {f["l3_code"] for f in roster["deferred_families"]})
            and not (covered & {f["l3_code"] for f in roster["out_of_scope_families"]})):
        continue
    fp = exclusion.fingerprint_record(r, artifact_id="recheck", record_index=0)
    winners.append({
        "ref": ref,
        "action": r.get("action"),
        "operators": operators,
        "codes": codes,
        "edges": edges,
        "anchor": anchor,
        "normalized_dag_key": fp["normalized_dag_key"],
        "record_review_markers": {k: r.get(k) for k in ("review_index", "reason", "rule_id", "structure_class", "task_text_admission", "task_text_quality") if k in r},
    })

print("total would-pass:", len(winners))
print("actions:", dict(collections.Counter(w["action"] for w in winners)))
distinct = {w["normalized_dag_key"] for w in winners}
print("distinct normalized DAGs:", len(distinct))
print("anchors:", dict(collections.Counter(w["anchor"] for w in winners)))
for w in winners:
    print(w["ref"], "| action:", w["action"], "| anchor:", w["anchor"], "| ops:", len(w["operators"]))
    print("   ", w["operators"])
    print("   edges:", w["edges"])
    print("   markers:", w["record_review_markers"])
