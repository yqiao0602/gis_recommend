"""L2: full census of all action-gated discovery records through the four real gates.

Read-only over every input. Writes one artifact:
  benchmarks/qgis_planner_v1/authority/v02_action_gate_reconciliation_v1.json

Hard rule honored: original action states are never modified; this census
only records original_action_gate + reassessment_result per record.

Gates, in order (mirroring build_qgis_benchmark_candidate_pool.build):
  1. gate1  -- strict operator mapping rule
  2. graph  -- graph_profile validity (with first-failure reason classification)
  3. gate2  -- real nine-index exclusion check over the frozen ledger
  4. rule C -- eligibility policy C (anchor/intermediate/out_of_scope)

Topology is recorded as raw facts (has_fanout / has_fanin / four-way class)
and NEVER influences admission, per the L3-deferred decision.
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

roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"] for f in roster["deferred_families"]}
OUT_OF_SCOPE = {f["l3_code"] for f in roster["out_of_scope_families"]}

mapping_artifact = json.loads((BASE / "qgis_operator_l3_mapping.json").read_text(encoding="utf-8"))
mappings = {row["operator_id"]: row for row in mapping_artifact["entries"]}

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
existing_dag_keys = {c["normalized_dag_key"] for c in cands}
existing_c_eligible_keys = set()
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)
for key, cs in dag_groups.items():
    if any(
        x["quota_anchor_l3"] in SUPPORTED
        and set(x["covered_l3"]) <= (SUPPORTED | DEFERRED)
        and not (set(x["covered_l3"]) & OUT_OF_SCOPE)
        for x in cs
    ):
        existing_c_eligible_keys.add(key)

print("streaming 104.7MB exclusion ledger...")
def ledger_rows():
    with (BASE / "source_exclusion_ledger.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
indexes = exclusion.build_overlap_indexes(ledger_rows())
print("indexes ready")

def graph_fail_reason(node_count, edges):
    if node_count < 1 or (node_count == 1 and edges):
        return "empty_or_single_node_with_edges"
    if node_count > 1 and not edges:
        return "multi_node_no_edges"
    if any(s < 0 or t < 0 or s >= node_count or t >= node_count or s == t for s, t in edges):
        return "edge_out_of_range_or_self_loop"
    adjacent = [set() for _ in range(node_count)]
    for s, t in edges:
        adjacent[s].add(t)
        adjacent[t].add(s)
    seen = {0}
    pending = [0]
    while pending:
        cur = pending.pop()
        for nb in adjacent[cur] - seen:
            seen.add(nb)
            pending.append(nb)
    if len(seen) != node_count:
        return "disconnected"
    indeg = [0] * node_count
    for s, t in edges:
        indeg[t] += 1
    queue = [i for i in range(node_count) if indeg[i] == 0]
    visited = 0
    remaining = list(indeg)
    while queue:
        cur = queue.pop()
        visited += 1
        for s, t in edges:
            if s == cur:
                remaining[t] -= 1
                if remaining[t] == 0:
                    queue.append(t)
    if visited != node_count:
        return "cyclic"
    return None

def four_way(node_count, edges):
    indeg = [0] * node_count
    outdeg = [0] * node_count
    for s, t in edges:
        outdeg[s] += 1
        indeg[t] += 1
    hi = any(d > 1 for d in indeg)
    ho = any(d > 1 for d in outdeg)
    return {
        "has_fanin": hi,
        "has_fanout": ho,
        "topology_class": "hybrid" if hi and ho else "pure_merge" if hi else "pure_branch" if ho else "linear",
    }

records = []
action_totals = collections.Counter()
per_action = collections.defaultdict(lambda: collections.Counter())
new_dag_keys = {}

for pool_name, pool_path in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(pool_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        r = json.loads(line)
        action = r.get("action")
        if action in ALLOWED_ACTIONS:
            continue
        ref = f"{pool_name}:{i}"
        action_totals[action] += 1
        row = {"discovery_ref": ref, "original_action_gate": action,
               "pool": pool_name, "task_text_admission": r.get("task_text_admission", "")}
        operators = [str(v).lower() for v in (r.get("ordered_operator_ids") or r.get("operator_ids") or [])]
        codes = [str(v) for v in (r.get("mapped_l3_chain") or [])]

        # gate 1
        if not operators or len(operators) != len(codes):
            reason = "operators_or_codes_missing_or_length_mismatch"
        else:
            bad = None
            for op, code in zip(operators, codes):
                m = mappings.get(op)
                if m is None:
                    bad = f"operator_unmapped:{op}"
                    break
                if not m["strict_catalog_present"]:
                    bad = f"operator_not_strict_catalog:{op}"
                    break
                if m["mapping_status"] != "stable101_direct":
                    bad = f"mapping_status:{op}:{m['mapping_status']}"
                    break
                if m["stable101_l3"] != code:
                    bad = f"l3_mismatch:{op}:{code}!={m['stable101_l3']}"
                    break
                if not m["headline_eligible"]:
                    bad = f"not_headline_eligible:{op}"
                    break
            reason = bad
        if reason:
            row["reassessment"] = {"stage": "gate1", "fail_reason": reason}
            per_action[action]["gate1_fail"] += 1
            records.append(row)
            continue
        row["gate1_pass"] = True

        # graph validity
        edges = [(s, t) for s, t, _k in exclusion._edges(r)]
        profile = graph_profile(len(operators), edges)
        if profile is None:
            row["reassessment"] = {"stage": "graph", "fail_reason": graph_fail_reason(len(operators), edges)}
            per_action[action]["graph_fail"] += 1
            records.append(row)
            continue
        row["graph_valid"] = True
        fw = four_way(len(operators), edges)
        row.update(fw)
        row["graph_size_stratum"] = profile["graph_size_stratum"]

        # gate 2
        overlap = exclusion.check_candidate_overlap(r, indexes)
        if overlap:
            row["reassessment"] = {"stage": "gate2", "fail_reason": "exclusion_overlap", "overlap_fields": sorted(overlap.keys())}
            per_action[action]["gate2_fail"] += 1
            records.append(row)
            continue
        row["gate2_clean"] = True

        # rule C
        analytical = [c for op, c in zip(operators, codes) if mappings[op]["task_role"] == "analytical"]
        anchor = (analytical or codes)[0]
        covered = set(codes)
        row["quota_anchor_l3"] = anchor
        row["covered_l3"] = sorted(covered)
        bad_oos = sorted(covered & OUT_OF_SCOPE)
        if bad_oos:
            row["reassessment"] = {"stage": "rule_c", "fail_reason": "out_of_scope_coverage", "families": bad_oos}
            per_action[action]["c_fail_out_of_scope"] += 1
            records.append(row)
            continue
        if anchor not in SUPPORTED:
            row["reassessment"] = {"stage": "rule_c", "fail_reason": "anchor_not_supported", "anchor": anchor}
            per_action[action]["c_fail_anchor"] += 1
            records.append(row)
            continue
        if not covered <= (SUPPORTED | DEFERRED):
            row["reassessment"] = {"stage": "rule_c", "fail_reason": "intermediate_not_in_roster_or_deferred",
                                   "families": sorted(covered - (SUPPORTED | DEFERRED))}
            per_action[action]["c_fail_intermediate"] += 1
            records.append(row)
            continue

        # survivor
        fp = exclusion.fingerprint_record(r, artifact_id="census", record_index=i)
        key = fp["normalized_dag_key"]
        row["reassessment"] = {
            "stage": "mechanically_eligible_review_required",
            "normalized_dag_key": key,
            "already_in_pool": key in existing_dag_keys,
        }
        per_action[action]["mechanically_eligible"] += 1
        if key not in existing_dag_keys:
            new_dag_keys.setdefault(key, []).append(row)
        records.append(row)

# aggregate
survivors = [r for r in records if r.get("reassessment", {}).get("stage") == "mechanically_eligible_review_required"]
new_dags = []
for key, rows in new_dag_keys.items():
    rep = rows[0]
    new_dags.append({
        "normalized_dag_key": key,
        "record_count": len(rows),
        "discovery_refs": [r["discovery_ref"] for r in rows],
        "original_action_gate": rep["original_action_gate"],
        "topology_class": rep["topology_class"],
        "has_fanout": rep["has_fanout"],
        "has_fanin": rep["has_fanin"],
        "graph_size_stratum": rep["graph_size_stratum"],
        "quota_anchor_l3": rep["quota_anchor_l3"],
        "covered_l3": rep["covered_l3"],
        "pool": rep["pool"],
    })

print()
print("action value distribution over action-gated records:", dict(action_totals))
print("per-action verdicts:")
for a in sorted(per_action):
    print("  ", a, dict(per_action[a]))
print()
print("mechanically eligible (review_required):", len(survivors))
print("distinct NEW DAGs (not in existing 52-pool):", len(new_dags))
tc = collections.Counter(d["topology_class"] for d in new_dags)
sz = collections.Counter(d["graph_size_stratum"] for d in new_dags)
print("new DAG topology_class:", dict(tc))
print("new DAG size strata:", dict(sz))

# consistency check: the 16 fan-out would-pass refs
fanout_pass = {r["discovery_ref"] for r in survivors if r["has_fanout"]}
known16 = {"stable101_routing_v6:178","stable101_routing_v6:278","stable101_routing_v6:332","stable101_routing_v6:333",
           "stable101_routing_v6:334","stable101_routing_v6:498","stable101_routing_v6:578","stable101_routing_v6:794",
           "stable101_routing_v6:795","stable101_routing_v6:796","stable101_routing_v6:954","stable101_routing_v6:1151",
           "stable101_routing_v6:1294","stable101_routing_v6:1295","stable101_routing_v6:1301","stable101_routing_v6:1393"}
print("consistency: known-16 subset of survivors:", known16 <= fanout_pass, "| fanout survivors total:", len(fanout_pass))

out = {
    "schema": "gis_recommend.qgis_benchmark_v02_action_gate_reconciliation.v1",
    "reconciliation_id": "v02-action-gate-reconciliation-1",
    "date": "2026-09-10",
    "decision_context": {
        "L1": "review_api_sidecar redefined as review_required queue: not reject, not admit; enters review then the four gates then task fidelity before any admission",
        "L2": "full census of all action-gated discovery records through the four real gates; original action states untouched; this artifact records original_action_gate + reassessment_result only",
        "hard_rules": ["original action states never modified", "topology recorded as raw facts (has_fanout/has_fanin/topology_class) and never influences admission", "L3 branch semantics and L4 expert supplement deferred", "sealed gold untouched", "task derivation spec unchanged"]
    },
    "method": "gate1 per build_qgis_benchmark_candidate_pool strict mapping rule; graph validity per graph_profile with first-failure reason; gate2 per repository nine-index exclusion check over the frozen source_exclusion_ledger.jsonl; rule C per v02_eligibility_policy_v1.json",
    "action_totals": dict(action_totals),
    "per_action_verdicts": {a: dict(per_action[a]) for a in sorted(per_action)},
    "totals": {
        "action_gated_records": len(records),
        "gate1_pass": sum(1 for r in records if r.get("gate1_pass")),
        "graph_valid": sum(1 for r in records if r.get("graph_valid")),
        "gate2_clean": sum(1 for r in records if r.get("gate2_clean")),
        "mechanically_eligible_review_required": len(survivors),
        "distinct_new_dags_not_in_52_pool": len(new_dags),
    },
    "new_dag_profile": {
        "topology_class": dict(tc),
        "graph_size_stratum": dict(sz),
        "anchors": dict(collections.Counter(d["quota_anchor_l3"] for d in new_dags)),
    },
    "consistency_check_known_fanout16_subset": known16 <= fanout_pass,
    "new_dags": new_dags,
    "survivor_records": [
        {"discovery_ref": r["discovery_ref"], "original_action_gate": r["original_action_gate"],
         "topology_class": r.get("topology_class"), "task_text_admission": r.get("task_text_admission"),
         "already_in_pool": r["reassessment"].get("already_in_pool"),
         "normalized_dag_key": r["reassessment"].get("normalized_dag_key")}
        for r in survivors
    ],
}
path = BASE / "v02_action_gate_reconciliation_v1.json"
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", path.name)
