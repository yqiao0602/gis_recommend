"""Build the dev task-fidelity worksheet for the 14 source-backed existing DAGs.

Same machinery as v02_task_fidelity_worksheet_v3: instance call sites
(consumption-order matching), parameter-strip three-state (recovery with
sha gating comes next), output cardinality, four-way topology facts.
Scope judgment applies the fixed fidelity principle (subchain_scoped
only if surrounding custom code changes the task's semantic boundary).
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

led = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
dev_entries = led["dev_side"]["entries"]

v4 = [json.loads(l) for l in (BASE / "v02_task_derivation_v4.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
tasked_keys = {r["packet_entry_id"].replace("recovered-", "")[:10] for r in v4[1:]}

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)

roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"]: f["l3_name"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"]: f["l3_name"] for f in roster["deferred_families"]}

def four_way(n, edges):
    indeg = [0]*n; outdeg = [0]*n
    for s, t in edges:
        outdeg[s] += 1; indeg[t] += 1
    hi = any(d > 1 for d in indeg); ho = any(d > 1 for d in outdeg)
    return "hybrid" if hi and ho else "pure_merge" if hi else "pure_branch" if ho else "linear"

def instance_call_sites(ops, call_sites):
    cursors = collections.Counter()
    mapped = []
    for idx, op in enumerate(ops):
        found = None
        for j in range(cursors[op], len(call_sites)):
            if call_sites[j].get("operator_id") == op:
                found = call_sites[j]
                cursors[op] = j + 1
                break
        mapped.append({
            "node_index": idx, "operator": op,
            "lines": (f"L{found['line_start']}-L{found['line_end']}" if found else None),
            "output_target": (found.get("output_role") or {}).get("target") if found else None,
            "param_keys": (found.get("param_keys") if found and "param_keys" in found else None),
        })
    return mapped

# identify the 14: dev entries that are existing-origin, not already tasked, not the exception
targets = []
for e in dev_entries:
    k10 = e["key"][:10]
    if e.get("dev_track") == "DEV_EXCEPTION":
        continue
    if k10 in tasked_keys:
        continue
    if e.get("origin") not in ("existing",):
        continue
    targets.append(e)
print("dev derivation targets (existing, not tasked, not exception):", len(targets))

rows = []
for e in targets:
    key_prefix = e["key"][:10]
    match = None
    for k, cs in dag_groups.items():
        if k.startswith(key_prefix):
            match = (k, cs)
            break
    if not match:
        print("UNRESOLVED:", e["key"])
        continue
    k, cs = match
    c = cs[0]
    ref = c["discovery_ref"]
    rec = recs[ref]
    ops = [str(v).lower() for v in (rec.get("ordered_operator_ids") or rec.get("operator_ids") or [])]
    codes = [str(v) for v in (rec.get("mapped_l3_chain") or [])]
    edges = [list(x) for x in (rec.get("dependency_edges") or [])]
    call_sites = rec.get("call_sites") or []
    inst = instance_call_sites(ops, call_sites)
    n = len(ops)
    # candidate graph edges from links for topology (normalized form)
    g_edges = [(int(l["source_process_id"][1:]), int(l["target_process_id"][1:])) for l in c["links"]]
    topo = four_way(n, g_edges)
    sinks = [i for i in range(n) if not any(s == i for s, t in g_edges)]
    roots = [i for i in range(n) if not any(t == i for s, t in g_edges)]
    # param strip status (pre-recovery)
    keys = set()
    field_absent = False
    field_empty = False
    for m in inst:
        if m["param_keys"] is None:
            field_absent = True
        elif not m["param_keys"]:
            field_empty = True
        else:
            keys.update(m["param_keys"])
    if field_absent or field_empty or not keys:
        strip_status = "incomplete_source_recovery"
    else:
        strip_status = "complete"
    # scope: dev DAGs are whole-scope direct-call chains (single discovery record);
    # subchain applies only where reason/ambiguity flags custom code -- check reason fields
    reason = rec.get("reason") or {}
    structure_class = reason.get("structure_class", "") if isinstance(reason, dict) else ""
    custom_code = isinstance(reason, dict) and (reason.get("intermediate_data_transform_calls") or reason.get("downstream_data_transform_calls"))
    scope = "subchain_scoped" if (custom_code and "blocked" in structure_class) else "full_workflow"
    rows.append({
        "packet_entry_id": "dev-" + k[:16],
        "pool_key": k[:16],
        "task_scope": scope,
        "source": {
            "primary_discovery_ref": ref,
            "supporting_discovery_refs": [ref],
            "source_path": rec.get("source_path") or rec.get("relative_path"),
            "source_root_id": rec.get("source_root_id"),
            "source_sha256": rec.get("source_sha256"),
        },
        "source_call_sites": inst,
        "recovered_dag": {"operators": ops, "l3_codes": codes, "edges": edges},
        "io_scope": {
            "graph_inputs_roots": [{"node_index": i, "operator": ops[i]} for i in roots],
            "graph_outputs_sinks": [{"node_index": i, "operator": ops[i]} for i in sinks],
        },
        "output_cardinality": {"cardinality": "multi" if len(sinks) >= 2 else "single",
                                "output_count": len(sinks),
                                "output_nodes": [{"node_index": i, "operator": ops[i]} for i in sinks],
                                "task_rule": "task text must explicitly express the multiple output goals" if len(sinks) >= 2 else None},
        "parameter_strip": {"status": strip_status, "keys": sorted(keys)},
        "topology_class": topo,
        "quota_anchor_l3": c["quota_anchor_l3"],
        "covered_l3": sorted(set(c["covered_l3"])),
        "potential_ambiguities": [f"structure_class={structure_class}"] if structure_class else [],
    })

print("worksheet entries:", len(rows))
print("scope:", dict(collections.Counter(r["task_scope"] for r in rows)))
print("strip:", dict(collections.Counter(r["parameter_strip"]["status"] for r in rows)))
print("cardinality:", dict(collections.Counter(r["output_cardinality"]["cardinality"] for r in rows)))
print("topology:", dict(collections.Counter(r["topology_class"] for r in rows)))

out = BASE / "v02_dev_task_fidelity_worksheet_v1.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_dev_task_fidelity_worksheet.v1",
        "worksheet_id": "v02-dev-task-worksheet-1",
        "date": "2026-09-11",
        "scope": "the 14 source-backed existing dev DAGs needing derivation; 4 dev DAGs already carry reviewed tasks; 1 DEV_EXCEPTION DAG handled on a separate track",
        "policy_refs": ["v02_task_derivation_spec.zh-CN.md", "fixed fidelity principle", "multi-sink rule", "owner dev-exception ruling a04c772"],
        "entries": len(rows),
    }, ensure_ascii=False) + "\n")
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("written:", out.name)
