"""Build the R4c task-fidelity worksheet for the 21 surviving recovered DAGs.

Compiles per entry: DAG id, source evidence (path/sha/lines), source
operations with call-site lines and parameter keys, the recovered (or
corrected) DAG, input/output scope from graph roots/sinks, parameters to
strip, full_workflow vs subchain_scoped designation, task-scope guidance,
and potential ambiguities drawn from the dual-review reasons.

Writes v02_task_fidelity_worksheet_v1.jsonl (+ .md scan table).
No task text is authored here -- this worksheet defines what a task MAY
say before any text is written.
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
        reviews[r["packet_entry_id"]][r["reviewer_id"].split("-recovered-")[0] if "-recovered-" in r["reviewer_id"] else r["reviewer_id"]] = r

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

by_key = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}
rev_by_pid = {r["packet_entry_id"]: r for r in rev["resolutions"]}

SCOPE_GUIDANCE_SUBCHAIN = (
    "Task text may ONLY describe the recovered sub-chain (its input, the listed operations in order, its outputs). "
    "The surrounding custom code named in exclusions_below MUST NOT appear in the task text, and the original script's "
    "overall business goal MUST NOT be smuggled in."
)
SCOPE_GUIDANCE_FULL = (
    "Task text describes the whole recovered workflow as evidenced by the source: the operations in order with their "
    "input/output flow. No operations, dependencies, or goals beyond the recovered DAG."
)

rows = []
for pid, outcome in sorted(acct["final_outcomes"].items()):
    if outcome == "rejected":
        continue
    key = pid.replace("recovered-", "")[:10]
    d = by_key[key]
    r = rev_by_pid.get(pid)
    ref = d["discovery_refs"][0]
    rec = recs[ref]
    call_sites = rec.get("call_sites") or []
    ops = [str(v).lower() for v in (rec.get("ordered_operator_ids") or rec.get("operator_ids") or [])]
    codes = [str(v) for v in (rec.get("mapped_l3_chain") or [])]
    edges = [list(e) for e in (rec.get("dependency_edges") or [])]
    scope = "subchain_scoped" if outcome == "accept_subchain_scoped" else "full_workflow"
    if pid in rev_by_pid and r["resolution"] == "CORRECTED_GRAPH_REVIEW_REQUIRED":
        edges = r["edges"]
    # roots/sinks
    n = len(ops)
    indeg = [0] * n
    outdeg = [0] * n
    for s, t in edges:
        outdeg[s] += 1
        indeg[t] += 1
    roots = [i for i in range(n) if indeg[i] == 0]
    sinks = [i for i in range(n) if outdeg[i] == 0]
    # reviewer evidence for ambiguities
    rev_a = reviews[pid].get("claude-glm53")
    amb = []
    if r and r.get("note"):
        amb.append(r["note"])
    for revk, rr in reviews[pid].items():
        if rr.get("reason"):
            amb.append(f"[{revk}] {rr['reason'][:300]}")
    params_to_strip = sorted({k for cs in call_sites for k in (cs.get("param_keys") or [])})
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
            "relevant_line_ranges": [
                {"operator": cs.get("operator_id"), "lines": f"L{cs.get('line_start')}-{cs.get('line_end')}",
                 "output_target": (cs.get("output_role") or {}).get("target")}
                for cs in call_sites
            ],
            "source_snippet_capped": (rec.get("source_snippet") or "")[:500],
        },
        "source_operations": [
            {"op": op, "l3": code, "family": SUPPORTED.get(code) or DEFERRED.get(code, "OUT_OF_SCOPE"),
             "lines": (f"L{cs.get('line_start')}-{cs.get('line_end')}" if (cs := next((c for c in call_sites if c.get("operator_id") == op), None)) else "?")}
            for op, code in zip(ops, codes)
        ],
        "recovered_dag": {"operators": ops, "l3_codes": codes, "edges": edges},
        "io_scope": {
            "graph_inputs_roots": [ops[i] for i in roots],
            "graph_outputs_sinks": [ops[i] for i in sinks],
        },
        "parameters_to_strip": params_to_strip,
        "task_scope_guidance": SCOPE_GUIDANCE_SUBCHAIN if scope == "subchain_scoped" else SCOPE_GUIDANCE_FULL,
        "potential_ambiguities": amb[:4],
        "quota_anchor_l3": d["quota_anchor_l3"],
        "covered_l3": d["covered_l3"],
    })

assert len(rows) == 21, len(rows)
out_jsonl = BASE / "v02_task_fidelity_worksheet_v1.jsonl"
with out_jsonl.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_task_fidelity_worksheet.v1",
        "worksheet_id": "v02-task-fidelity-worksheet-1",
        "date": "2026-09-10",
        "purpose": "define what each task text MAY say before any text is written; no task text is authored here",
        "policy_refs": ["v02_task_derivation_spec.zh-CN.md", "v02_recovered_dag_adjudication_v1.json subchain_policy", "v02_benchmark_positioning_decision_v1.json"],
        "entries": len(rows),
    }, ensure_ascii=False) + "\n")
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

md = ["# v0.2 Task Fidelity Worksheet v1 (21 surviving recovered DAGs)", "",
      "Purpose: fix the ALLOWED scope of each task text BEFORE writing any text.",
      "6 entries are subchain_scoped (task may describe only the recovered sub-chain).", "",
      "| # | entry | scope | ops | size | source | anchor |", "|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    md.append(f"| {i} | `{r['packet_entry_id'][10:20]}` | {r['task_scope']} | {len(r['recovered_dag']['operators'])} | "
              f"{r['recovered_dag']['operators'][0]}..{r['recovered_dag']['operators'][-1]} | "
              f"{r['source']['source_root_id']} | {r['quota_anchor_l3']} |")
(BASE / "v02_task_fidelity_worksheet_v1.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("entries:", len(rows))
print("scope split:", dict(collections.Counter(r["task_scope"] for r in rows)))
print("written:", out_jsonl.name, "+ .md")
