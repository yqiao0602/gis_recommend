"""②-1: Re-check the 57 pending fan-out records under eligibility rule C through the REAL Gate 2.

Uses the repository's own exclusion machinery (fingerprint_record,
build_overlap_indexes, check_candidate_overlap) and the candidate-pool
builder's gate1 mapping rule and anchor rule. Also computes the corrected
four-way topology taxonomy (linear / pure_merge / pure_branch / hybrid)
for the existing 52-DAG pool and the re-checked records.

Writes v02_gate2_recheck_fanout_v1.json next to the other v02 authority
artifacts. Read-only over all inputs.
"""
import json
import sys
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WT))

from scripts import build_qgis_benchmark_exclusion_ledger as exclusion  # noqa: E402
from scripts.build_qgis_benchmark_candidate_pool import ALLOWED_ACTIONS, graph_profile  # noqa: E402

BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
LEDGER = BASE / "source_exclusion_ledger.jsonl"
MAPPING = BASE / "qgis_operator_l3_mapping.json"
CAPABILITY = BASE / "capability_matrix.jsonl"

roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"] for f in roster["deferred_families"]}
OUT_OF_SCOPE = {f["l3_code"] for f in roster["out_of_scope_families"]}

mapping_artifact = json.loads(MAPPING.read_text(encoding="utf-8"))
mappings = {row["operator_id"]: row for row in mapping_artifact["entries"]}

cap_rows = [json.loads(l) for l in CAPABILITY.read_text(encoding="utf-8").splitlines() if l.strip()]
admitted_ops = set()
for r in cap_rows:
    admitted_ops.update(r["admitted_operator_ids"])

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
adm_refs = {c["discovery_ref"] for c in cands if c.get("discovery_ref")}

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

print("building exclusion overlap indexes (streaming 104.7MB ledger)...")
def ledger_rows():
    with LEDGER.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
indexes = exclusion.build_overlap_indexes(ledger_rows())
print("overlap indexes built:", {k: len(v) for k, v in indexes.items()})

def four_way(node_count, edges):
    indeg = [0] * node_count
    outdeg = [0] * node_count
    for s, t in edges:
        outdeg[s] += 1
        indeg[t] += 1
    has_in = any(d > 1 for d in indeg)
    has_out = any(d > 1 for d in outdeg)
    if has_in and has_out:
        return "hybrid_merge_and_branch"
    if has_in:
        return "pure_merge"
    if has_out:
        return "pure_branch"
    return "linear"

# corrected taxonomy over the existing 52-DAG pool
pool_taxonomy = collections.Counter()
for key, cs in {c["normalized_dag_key"]: None for c in cands}.items():
    pass
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)
for key, cs in dag_groups.items():
    c = cs[0]
    n = len(c["processes"])
    edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in c["links"]]
    pool_taxonomy[four_way(n, edges)] += 1
print("existing 52-DAG pool, four-way topology:", dict(pool_taxonomy))

# select the 57: fan-out, all ops capability-admitted, candidate action, locally passing, not admitted
targets = []
for ref, r in recs.items():
    edges_raw = r.get("dependency_edges") or []
    if not edges_raw:
        continue
    outdeg = collections.Counter(e[0] for e in edges_raw)
    if not any(v >= 2 for v in outdeg.values()):
        continue
    ops = set(r.get("operator_ids") or r.get("canonical_operator_ids") or [])
    if not (ops and ops <= admitted_ops):
        continue
    if r.get("action") not in ALLOWED_ACTIONS or ref in adm_refs:
        continue
    if r.get("unresolved_output_references") or []:
        continue
    targets.append((ref, r))
print("re-check targets:", len(targets))

results = []
verdicts = collections.Counter()
for ref, r in targets:
    operators = [str(v).lower() for v in (r.get("ordered_operator_ids") or r.get("operator_ids") or [])]
    codes = [str(v) for v in (r.get("mapped_l3_chain") or [])]
    row = {"discovery_ref": ref, "action": r.get("action"), "n_ops": len(operators)}
    # gate1 (pool builder's strict rule)
    gate1 = bool(operators) and len(operators) == len(codes) and all(
        op in mappings
        and mappings[op]["strict_catalog_present"]
        and mappings[op]["mapping_status"] == "stable101_direct"
        and mappings[op]["stable101_l3"] == code
        and mappings[op]["headline_eligible"]
        for op, code in zip(operators, codes)
    )
    row["gate1"] = gate1
    if not gate1:
        verdicts["rejected_gate1"] += 1
        results.append(row)
        continue
    # graph profile
    edges = [(s, t) for s, t, _k in exclusion._edges(r)]
    profile = graph_profile(len(operators), edges)
    row["graph_profile_valid"] = profile is not None
    if profile is None:
        verdicts["rejected_invalid_graph"] += 1
        results.append(row)
        continue
    row["topology"] = profile["topology"]
    row["four_way_topology"] = four_way(len(operators), edges)
    row["graph_size_stratum"] = profile["graph_size_stratum"]
    # gate2 real check
    overlap = exclusion.check_candidate_overlap(r, indexes)
    row["gate2_overlap_fields"] = list(overlap.keys())
    if overlap:
        verdicts["rejected_gate2_overlap"] += 1
        results.append(row)
        continue
    # C eligibility
    analytical = [c for op, c in zip(operators, codes) if mappings[op]["task_role"] == "analytical"]
    anchor = (analytical or codes)[0]
    covered = set(codes)
    row["quota_anchor_l3"] = anchor
    row["covered_l3"] = sorted(covered)
    c_ok = (
        anchor in SUPPORTED
        and covered <= (SUPPORTED | DEFERRED)
        and not (covered & OUT_OF_SCOPE)
    )
    row["c_eligible"] = c_ok
    if not c_ok:
        bad = sorted(covered & OUT_OF_SCOPE)
        row["c_rejection_reason"] = (
            f"out_of_scope_coverage:{bad}" if bad else f"anchor_not_supported:{anchor}"
        )
        verdicts["rejected_c_out_of_scope" if bad else "rejected_c_anchor"] += 1
        results.append(row)
        continue
    row["verdict"] = "c_eligible_gate2_clean"
    verdicts["c_eligible_gate2_clean"] += 1
    results.append(row)

print("verdicts:", dict(verdicts))
eligible = [r for r in results if r.get("verdict") == "c_eligible_gate2_clean"]
print("four-way taxonomy of eligible:", dict(collections.Counter(r["four_way_topology"] for r in eligible)))
print("size strata of eligible:", dict(collections.Counter(r["graph_size_stratum"] for r in eligible)))

# gate2 overlap field breakdown for the rejected
overlap_fields_hit = collections.Counter()
for r in results:
    for f in r.get("gate2_overlap_fields", []):
        overlap_fields_hit[f] += 1
print("gate2 overlap fields hit (28 rejected):", dict(overlap_fields_hit))

# secondary informational analysis: the 61 action-rejected fan-out records
# (would they pass gate1 + profile + gate2 + C if the action policy ever changed?)
secondary = collections.Counter()
secondary_detail = []
for ref, r in recs.items():
    edges_raw = r.get("dependency_edges") or []
    if not edges_raw:
        continue
    outdeg = collections.Counter(e[0] for e in edges_raw)
    if not any(v >= 2 for v in outdeg.values()):
        continue
    ops = set(r.get("operator_ids") or r.get("canonical_operator_ids") or [])
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
        secondary["gate1_fail"] += 1
        continue
    edges = [(s, t) for s, t, _k in exclusion._edges(r)]
    if graph_profile(len(operators), edges) is None:
        secondary["invalid_graph"] += 1
        continue
    if exclusion.check_candidate_overlap(r, indexes):
        secondary["gate2_overlap"] += 1
        continue
    analytical = [c for op, c in zip(operators, codes) if mappings[op]["task_role"] == "analytical"]
    anchor = (analytical or codes)[0]
    covered = set(codes)
    if not (anchor in SUPPORTED and covered <= (SUPPORTED | DEFERRED) and not (covered & OUT_OF_SCOPE)):
        secondary["c_ineligible"] += 1
        continue
    secondary["would_pass_all"] += 1
    secondary_detail.append({"discovery_ref": ref, "action": r.get("action"),
                             "four_way": four_way(len(operators), edges)})
print("secondary (61 action-rejected fan-out, informational):", dict(secondary))
print("  would-pass-all detail:", secondary_detail[:10])

out = {
    "schema": "gis_recommend.qgis_benchmark_v02_gate2_recheck.v1",
    "recheck_id": "v02-gate2-recheck-fanout-1",
    "date": "2026-09-10",
    "policy_ref": "v02_eligibility_policy_v1.json (rule C)",
    "scope": "the 57 pending fan-out records (candidate action, all operators capability-admitted, locally passing, not previously admitted)",
    "method": "repository's own exclusion machinery: fingerprint_record + build_overlap_indexes + check_candidate_overlap over the frozen 104.7MB source_exclusion_ledger.jsonl; gate1 per build_qgis_benchmark_candidate_pool strict mapping rule; anchor per analytical-first rule",
    "existing_pool_four_way_taxonomy": dict(pool_taxonomy),
    "taxonomy_correction": "the 19 previously-described 'admitted but fan-out normalized away' records actually preserve ALL edges; graph_profile classifies merge before branch, so hybrid fan-in+fan-out DAGs are labeled multi_input_merge and their fan-out is masked by the label, not lost. Existing pool four-way taxonomy above is the corrected reading.",
    "verdict_counts": dict(verdicts),
    "eligible_four_way_taxonomy": dict(collections.Counter(r["four_way_topology"] for r in eligible)),
    "eligible_size_strata": dict(collections.Counter(r["graph_size_stratum"] for r in eligible)),
    "records": results,
}
path = BASE / "v02_gate2_recheck_fanout_v1.json"
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", path.name, "| records:", len(results))
