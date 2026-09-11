"""Build fidelity worksheet v2 with owner-adjudicated fixes.

Changes over v1 (rendering layer only; no data/DAG/Gate changes):
  1. Instance-level source call sites: each DAG node maps to ONE call
     site (consumption-order matching by operator id), never
     operator-id -> first-match.
  2. parameter_strip_status three-state: complete / not_applicable /
     incomplete_source_recovery -- an empty key list never silently
     means "no parameters".
  3. output_cardinality / output_count / output_nodes from graph sinks,
     so multi-output DAGs (#3, #5, #20, ...) are explicit for task
     derivation.

Header records the owner adjudication of 2026-09-10, including the
fixed fidelity principle (downstream validation computation does not
change scope; auxiliary non-standard code that changes the task's
semantic boundary does) and the multi-sink task rule.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

acct = json.loads((BASE / "v02_recovered_dag_final_accounting_v1.json").read_text(encoding="utf-8"))
cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
rev = json.loads((BASE / "v02_recovered_dag_revision_batch_v1.json").read_text(encoding="utf-8"))
roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"]: f["l3_name"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"]: f["l3_name"] for f in roster["deferred_families"]}

ledger = [json.loads(l) for l in (BASE / "v02_recovered_dag_reviews_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
reviews = collections.defaultdict(dict)
for r in ledger:
    if r.get("record_type") == "review":
        reviews[r["packet_entry_id"]]["reviewer"] = r

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

by_key = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}
rev_by_pid = {r["packet_entry_id"]: r for r in rev["resolutions"]}

def instance_call_sites(ops, call_sites):
    """Map each DAG node to one call site by consumption order per operator id."""
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
            "node_index": idx,
            "operator": op,
            "lines": (f"L{found['line_start']}-L{found['line_end']}" if found else None),
            "output_target": (found.get("output_role") or {}).get("target") if found else None,
            "param_keys": (found.get("param_keys") if found and "param_keys" in found else None),
        })
    return mapped

rows = []
for pid, outcome in sorted(acct["final_outcomes"].items()):
    if outcome == "rejected":
        continue
    key = pid.replace("recovered-", "")[:10]
    d = by_key[key]
    r = rev_by_pid.get(pid)
    ref = d["discovery_refs"][0]
    rec = recs[ref]
    ops = [str(v).lower() for v in (rec.get("ordered_operator_ids") or rec.get("operator_ids") or [])]
    codes = [str(v) for v in (rec.get("mapped_l3_chain") or [])]
    edges = [list(e) for e in (rec.get("dependency_edges") or [])]
    scope = "subchain_scoped" if outcome == "accept_subchain_scoped" else "full_workflow"
    if r and r.get("resolution") == "CORRECTED_GRAPH_REVIEW_REQUIRED":
        edges = r["edges"]
    call_sites = rec.get("call_sites") or []
    inst = instance_call_sites(ops, call_sites)
    n = len(ops)
    indeg = [0] * n
    outdeg = [0] * n
    for s, t in edges:
        outdeg[s] += 1
        indeg[t] += 1
    sinks = [i for i in range(n) if outdeg[i] == 0]
    roots = [i for i in range(n) if indeg[i] == 0]
    # parameter strip status
    # three states per owner spec; an EMPTY extracted param_keys list is an
    # extractor gap (processing.run always carries parameters), never a
    # confirmation that no parameters exist -- so it maps to
    # incomplete_source_recovery, and not_applicable stays reserved for a
    # genuine confirmed-none case (none exists in this cohort).
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
    if field_absent:
        strip_status = "incomplete_source_recovery"
        strip_note = "param_keys field absent from discovery call sites; recover from source before task derivation"
    elif field_empty or not keys:
        strip_status = "incomplete_source_recovery"
        strip_note = "param_keys recorded as empty lists (extractor gap; processing.run calls always carry parameters); recover from source before task derivation"
    else:
        strip_status = "complete"
        strip_note = None
    amb = []
    if r and r.get("note"):
        amb.append(r["note"])
    rr = reviews[pid].get("reviewer")
    if rr and rr.get("reason"):
        amb.append(f"[dual-review] {rr['reason'][:280]}")
    rows.append({
        "packet_entry_id": pid,
        "final_outcome": outcome,
        "task_scope": scope,
        "source": {
            "primary_discovery_ref": ref,
            "supporting_discovery_refs": d["discovery_refs"],
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
        "output_cardinality": {
            "cardinality": "multi" if len(sinks) >= 2 else "single",
            "output_count": len(sinks),
            "output_nodes": [{"node_index": i, "operator": ops[i]} for i in sinks],
            "task_rule": "task text must explicitly express the multiple output goals" if len(sinks) >= 2 else None,
        },
        "parameter_strip": {
            "status": strip_status,
            "keys": sorted(keys),
            "note": strip_note,
        },
        "potential_ambiguities": amb[:4],
        "quota_anchor_l3": d["quota_anchor_l3"],
        "covered_l3": d["covered_l3"],
    })

assert len(rows) == 21, len(rows)
unmapped = [e["packet_entry_id"] for e in rows for m in e["source_call_sites"] if m["lines"] is None]
print("entries:", len(rows), "| call sites missing:", unmapped if unmapped else "NONE")
print("strip status:", dict(collections.Counter(e["parameter_strip"]["status"] for e in rows)))
print("output cardinality:", dict(collections.Counter(e["output_cardinality"]["cardinality"] for e in rows)))
for e in rows:
    if e["output_cardinality"]["cardinality"] == "multi":
        print("  multi-output:", e["packet_entry_id"][:20], e["output_cardinality"]["output_count"], "sinks")

out_jsonl = BASE / "v02_task_fidelity_worksheet_v2.jsonl"
with out_jsonl.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_task_fidelity_worksheet.v2",
        "worksheet_id": "v02-task-fidelity-worksheet-2",
        "date": "2026-09-10",
        "supersedes": "v02_task_fidelity_worksheet_v1.jsonl (rendering-layer fixes only; no data, DAG, Gate, or pool changes)",
        "purpose": "define what each task text MAY say before any text is written; no task text is authored here",
        "owner_adjudication": {
            "scope": "15 full_workflow / 6 subchain_scoped -- MAINTAINED",
            "entry_14_ruling": "clip->rastersampling stays full_workflow: downstream RMSE is result-validation arithmetic, not a gold-chain operator",
            "fixed_fidelity_principle": "auxiliary non-standard code that changes the task's semantic boundary forces subchain_scoped; downstream result-validation computation does not",
            "io_layering": "io_scope (roots/sinks) constrains the task I/O boundary; the gold DAG determines the middle structure; task text expresses user intent naturally and never becomes a DAG description",
            "multi_sink_rule": "a gold DAG with >=2 semantically valid sinks mapping to different output goals must have its task text express the multiple outputs explicitly",
        },
        "entries": len(rows),
    }, ensure_ascii=False) + "\n")
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("written:", out_jsonl.name)
