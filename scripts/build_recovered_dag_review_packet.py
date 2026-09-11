"""Build the review packet for the 24 recovered DAGs from the action-gate census.

Read-only over inputs. Writes:
  benchmarks/qgis_planner_v1/authority/v02_recovered_dag_review_packet_v1.jsonl  (machine)
  benchmarks/qgis_planner_v1/authority/v02_recovered_dag_review_packet_v1.md     (human scan table)

Per the user's checklist each packet entry carries: source evidence,
original action gate + reason, DAG structure, four-way topology, C-rule
family verdict, original exclusion/defer reason, and task-fidelity
evidence. Nothing is admitted; every entry is review_required.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
SUPPORTED = {f["l3_code"]: f["l3_name"] for f in roster["supported_families"]}
DEFERRED = {f["l3_code"]: f["l3_name"] for f in roster["deferred_families"]}

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

SNIPPET_CAP = 700

def evidence(ref):
    r = recs[ref]
    reason = r.get("reason")
    reason_summary = None
    if isinstance(reason, dict):
        reason_summary = {
            k: reason.get(k)
            for k in ("structure_class", "control_flow_kinds", "api_pattern_count",
                      "candidate_alignment_status", "mapping_complete", "operator_count")
            if k in reason
        }
        transforms = reason.get("intermediate_data_transform_calls") or []
        if transforms:
            reason_summary["intermediate_data_transform_calls"] = transforms[:12]
    return {
        "discovery_ref": ref,
        "source_path": r.get("source_path") or r.get("relative_path"),
        "source_root_id": r.get("source_root_id"),
        "source_sha256": r.get("source_sha256"),
        "source_snippet_capped": (r.get("source_snippet") or "")[:SNIPPET_CAP],
        "task_text_admission": r.get("task_text_admission", ""),
        "description_requirement": r.get("description_requirement", ""),
        "reason_summary": reason_summary,
        "record_rule_id": r.get("rule_id"),
    }

entries = []
for d in cen["new_dags"]:
    rep_ref = d["discovery_refs"][0]
    r = recs[rep_ref]
    operators = [str(v).lower() for v in (r.get("ordered_operator_ids") or r.get("operator_ids") or [])]
    codes = [str(v) for v in (r.get("mapped_l3_chain") or [])]
    edges = r.get("dependency_edges") or []
    entries.append({
        "packet_entry_id": f"recovered-{d['normalized_dag_key'][:16]}",
        "normalized_dag_key": d["normalized_dag_key"],
        "review_status": "review_required",
        "original_action_gate": d["original_action_gate"],
        "supporting_records": len(d["discovery_refs"]),
        "discovery_refs": d["discovery_refs"],
        "dag": {
            "operators": operators,
            "l3_codes": codes,
            "edges": [list(e) for e in edges],
            "graph_size_stratum": d["graph_size_stratum"],
            "topology_class": d["topology_class"],
            "has_fanout": d["has_fanout"],
            "has_fanin": d["has_fanin"],
        },
        "c_rule": {
            "anchor_l3": d["quota_anchor_l3"],
            "anchor_name": SUPPORTED.get(d["quota_anchor_l3"], "?"),
            "covered_l3": d["covered_l3"],
            "covered_names": {c: SUPPORTED.get(c) or DEFERRED.get(c, "OUT_OF_SCOPE?") for c in d["covered_l3"]},
            "verdict": "eligible_under_rule_C",
        },
        "source_evidence": [evidence(ref) for ref in d["discovery_refs"][:3]],
        "all_source_evidence_refs": d["discovery_refs"],
        "task_fidelity_evidence": {
            "task_text_admission": r.get("task_text_admission", ""),
            "description_requirement": r.get("description_requirement", ""),
            "note": "task text must be derived from source per v02_task_derivation_spec; fidelity gate pending",
        },
        "review_checklist": [
            "source: is the QGIS code evidence real and sufficient for this graph",
            "action: was the original gate reason (see reason_summary) semantically valid or overcautious",
            "dag: is the workflow structure correct (operators + edges match the code)",
            "topology: confirm topology_class from edges",
            "family: confirm anchor in SUPPORTED and no OUT_OF_SCOPE coverage",
            "exclusion_reason: if original action was exclude/defer, does the original reason still stand",
            "task_fidelity: can a faithful, parameter-free task be derived from this source",
        ],
    })

# machine file
out_jsonl = BASE / "v02_recovered_dag_review_packet_v1.jsonl"
with out_jsonl.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_recovered_dag_review_packet.v1",
        "packet_id": "v02-recovered-dag-review-packet-1",
        "date": "2026-09-10",
        "decision_context": "L1+L2 census recovered 24 distinct mechanically-eligible DAGs; every entry is review_required, none admitted; topology recorded as facts per deferred L3; original action states untouched",
        "entries": len(entries),
    }, ensure_ascii=False) + "\n")
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

# human scan table
md = ["# v0.2 Recovered DAG Review Packet v1 (24 entries, review_required)", "",
      "Source: v02_action_gate_reconciliation_v1.json (census cbc8269). Nothing here is admitted.",
      "Topology is a recorded fact, not an admission criterion (L3 deferred).", "",
      "| # | DAG key | action | recs | size | topology | anchor (family) | covered | source root | task admission |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for i, e in enumerate(entries, 1):
    d = e["dag"]
    cov = ",".join(e["c_rule"]["covered_l3"])
    src = e["source_evidence"][0]
    md.append(
        f"| {i} | `{e['normalized_dag_key'][:10]}` | {e['original_action_gate']} | {e['supporting_records']} "
        f"| {d['graph_size_stratum']} | {d['topology_class']} | {e['c_rule']['anchor_l3']} ({e['c_rule']['anchor_name']}) "
        f"| {cov} | {src.get('source_root_id','?')} | {e['task_fidelity_evidence']['task_text_admission'] or '?'} |"
    )
md += ["", "## Per-entry operator chains", ""]
for i, e in enumerate(entries, 1):
    d = e["dag"]
    ops = " -> ".join(d["operators"]) if d["topology_class"] == "linear" else " ; ".join(
        f"{op}[{','.join(str(t) for s,t in d['edges'] if s==j)}]" for j, op in enumerate(d["operators"])
    )
    md.append(f"**{i}. `{e['normalized_dag_key'][:10]}`** ({e['original_action_gate']}, {e['supporting_records']} record(s))")
    md.append(f"- operators: {ops}")
    md.append(f"- edges: {d['edges']}")
    md.append(f"- first source: `{e['source_evidence'][0].get('source_path','?')}` ({e['source_evidence'][0].get('source_root_id','?')})")
    rs = e["source_evidence"][0].get("reason_summary") or {}
    if rs:
        md.append(f"- original gate reason: structure_class={rs.get('structure_class')}, control_flow={rs.get('control_flow_kinds')}, intermediate_transforms={rs.get('intermediate_data_transform_calls', [])[:6]}")
    md.append("")

out_md = BASE / "v02_recovered_dag_review_packet_v1.md"
out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
print("entries:", len(entries))
print("written:", out_jsonl.name, "and", out_md.name)
tc = collections.Counter(e["dag"]["topology_class"] for e in entries)
ac = collections.Counter(e["original_action_gate"] for e in entries)
print("topology:", dict(tc), "| actions:", dict(ac))
