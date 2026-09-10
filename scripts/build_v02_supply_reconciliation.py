"""Build v02_supply_reconciliation_v1.json: 31-vs-52 DAG ledger + fan-out funnel diagnosis.

Read-only over authority inputs; writes one reconciliation ledger.
Run from the benchmark worktree root.
"""
import json
import collections
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

roster = json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
supported = {f["l3_code"] for f in roster["supported_families"]}
deferred = {f["l3_code"] for f in roster["deferred_families"]}

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dags = collections.defaultdict(list)
for c in cands:
    dags[c["normalized_dag_key"]].append(c)

apps = [json.loads(l) for l in (BASE / "v02_dag_human_approval_ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
by_key = {c["normalized_dag_key"]: cs for cs in dags.values() for c in cs}
appmap = {}
for a in apps:
    if a.get("canonical_graph_id") in by_key:
        appmap[a["canonical_graph_id"]] = a["decision"]

ledger = []
for key, cs in dags.items():
    eligible_B = any(set(c["covered_l3"]) <= supported for c in cs)
    eligible_C = any(set(c["covered_l3"]) <= (supported | deferred) for c in cs)
    offenders = set()
    for c in cs:
        offenders |= set(c["covered_l3"]) - supported
    ledger.append({
        "normalized_dag_key": key,
        "provenance": cs[0]["provenance_class"],
        "modality": cs[0]["modality"],
        "topology": cs[0]["topology"],
        "graph_size_stratum": cs[0]["graph_size_stratum"],
        "candidate_count": len(cs),
        "rule_B_all_covered_in_roster": eligible_B,
        "rule_C_covered_in_roster_or_deferred": eligible_C,
        "non_roster_covered_families": sorted(offenders),
        "exclusion_reason": (
            None if eligible_B
            else ("all_covered_in_roster_failed_deferred_family_only" if eligible_C
                  else "all_covered_in_roster_failed_out_of_scope_family")
        ),
        "r4b_decision": appmap.get(key),
    })

def prof(rows, field):
    return dict(collections.Counter(r[field] for r in rows))

dropped = [r for r in ledger if not r["rule_B_all_covered_in_roster"]]

summary = {
    "schema": "gis_recommend.qgis_benchmark_v02_supply_reconciliation.v1",
    "reconciliation_id": "v02-supply-reconciliation-1",
    "date": "2026-09-10",
    "question_1_31_vs_50": {
        "mechanism": "R-stage supply review (v02_supply_review_summary.json) applied an all-covered-L3-in-supported-roster filter: 149 candidates -> 87 eligible -> 31 distinct DAGs; 62 candidates excluded with reason family_not_in_supported_roster",
        "gate3_source_backed_dag_count": 50,
        "gate3_total_distinct_dags": 52,
        "r_stage_eligible_dag_count": 31,
        "r_stage_dag_provenance_split": {
            "qgis_source_backed": sum(1 for r in ledger if r["rule_B_all_covered_in_roster"] and r["provenance"] == "qgis_source_backed"),
            "expert_authored": sum(1 for r in ledger if r["rule_B_all_covered_in_roster"] and r["provenance"] == "expert_authored"),
        },
        "spec_claim_correction": "v02_task_derivation_spec says 31 source-backed DAGs; precisely 28 are source-backed, 3 are expert-authored; the 22-overlap / 9-new split against v0.1 final is the other session's measurement and was not independently re-verified here (final gold is sealed)",
        "dropped_21_dags_structural_profile": {
            "modality": prof(dropped, "modality"),
            "topology": prof(dropped, "topology"),
            "graph_size": prof(dropped, "graph_size_stratum"),
        },
        "dropped_21_dags_offender_families": {
            "L3_01_05_02 Repair Geometry (out_of_scope)": 6,
            "L3_02_02_04 Erase (deferred)": 4,
            "L3_02_06_03 Extract by Location (deferred)": 3,
            "L3_03_04_01 Reclassify/Remap (deferred)": 2,
            "L3_03_01_01 Clip Raster by Geometry (out_of_scope)": 2,
            "L3_01_02_03 Alter Field (out_of_scope)": 2,
            "others": 4,
        },
    },
    "rule_comparison": {
        "rule_A_anchor_in_roster": {
            "dag_count": 52,
            "topology": {"linear": 30, "multi_input_merge": 22},
            "graph_size": {"one_step": 1, "two_to_three": 32, "four_to_six": 12, "seven_plus": 7},
            "semantics": "quota credit for anchor family only; covered annotation unrestricted (the roster JSON original intent)",
        },
        "rule_B_all_covered_in_roster": {
            "dag_count": 31,
            "topology": {"linear": 24, "multi_input_merge": 7},
            "graph_size": {"one_step": 1, "two_to_three": 24, "four_to_six": 4, "seven_plus": 2},
            "semantics": "entire DAG must live inside the 20 supported families (current R-stage implementation)",
        },
        "rule_C_covered_in_roster_or_deferred": {
            "dag_count": 37,
            "topology": {"linear": 25, "multi_input_merge": 12},
            "graph_size": {"one_step": 1, "two_to_three": 26, "four_to_six": 6, "seven_plus": 4},
            "semantics": "out_of_scope coverage banned; deferred families tolerated as intermediate steps with no quota credit",
        },
        "budget_authority_conflict": "frozen v02_budget_matrix requires final branch>=8, merge 20, seven_plus 8, raster_or_mixed>=20; under rule B the existing supply (31 DAGs: 0 branch, 7 merge, 2 seven_plus, 10 raster+mixed) plus only 6 rule-B-surviving fan-out records cannot reach any of these floors; rule A or C is required for the budget to be feasible",
    },
    "question_2_fanout_funnel_diagnosis": {
        "corpus_fact": "routing_v6 holds 136 fan-out dependency records (106 with all operators admitted); stable106 holds 305 (37 all-admitted); 143 total all-admitted fan-out records",
        "prior_claim_correction": "branch=0 was true only of the 149 admitted candidates, not of the corpus; the funnel discarded branch structure at three layers",
        "fate_of_143": {
            "admitted_but_fanout_normalized_away": 19,
            "action_not_candidate": {"count": 61, "detail": "58 review_api_sidecar + 3 exclude_current_chain"},
            "invalid_graph_unused_temporary_terminals": 6,
            "passes_local_checks_pending_gate2": 57,
        },
        "roster_survivability_of_the_57": {"rule_B": 6, "rule_C": 32, "distinct_operator_edge_structures": 20},
        "verdict": "branch shortage is a funnel artifact, not a corpus property; recoverable paths are (a) rule change B to A or C, (b) admitting the 57 pending gate2 recheck, (c) fixing the normalizer that collapsed fan-out in 19 admitted records",
    },
    "open_decision_for_user": "choose eligibility rule A / B / C; this changes the R4a/R4b review scope (31 reviewed; +6 under C, +21 under A need fresh review) and unblocks supply repair",
}

out = {"summary": summary, "per_dag_ledger": ledger}
path = BASE / "v02_supply_reconciliation_v1.json"
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("ledger rows:", len(ledger))
print("written:", path.name)
print("sha256:", hashlib.sha256(path.read_bytes()).hexdigest()[:16])
