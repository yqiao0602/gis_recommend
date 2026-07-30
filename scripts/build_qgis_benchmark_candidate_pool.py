#!/usr/bin/env python3
"""Build the Gate 3 parameter-free QGIS candidate supply ledger."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_qgis_benchmark_exclusion_ledger as exclusion


DEFAULT_DISCOVERY_POOLS = (
    (
        "stable101_routing_v6",
        "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/"
        "stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl",
    ),
    (
        "stable106_catalog_miss_replay",
        "docs/reports/qgis_processing_mapping_gap_stable106_v1/"
        "l3_replay_v1/l3_gated_manifest_v1.jsonl",
    ),
)
ALLOWED_ACTIONS = {"auto_accept_candidate", "recover_call_graph", "split_subworkflow"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def required_supply(quota: int) -> int:
    return quota + max(math.ceil(0.25 * quota), 3)


def graph_profile(
    node_count: int, edges: Iterable[tuple[int, int]]
) -> dict[str, str] | None:
    edges = sorted(set(edges))
    if node_count < 1 or (node_count == 1 and edges):
        return None
    if node_count > 1 and not edges:
        return None
    if any(
        source < 0
        or target < 0
        or source >= node_count
        or target >= node_count
        or source == target
        for source, target in edges
    ):
        return None

    adjacent = [set() for _ in range(node_count)]
    outgoing = [[] for _ in range(node_count)]
    indegree = [0] * node_count
    outdegree = [0] * node_count
    for source, target in edges:
        adjacent[source].add(target)
        adjacent[target].add(source)
        outgoing[source].append(target)
        indegree[target] += 1
        outdegree[source] += 1

    seen = {0}
    pending = [0]
    while pending:
        current = pending.pop()
        for neighbor in adjacent[current] - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    queue = [index for index, degree in enumerate(indegree) if degree == 0]
    visited = 0
    remaining = list(indegree)
    while queue:
        current = queue.pop()
        visited += 1
        for target in outgoing[current]:
            remaining[target] -= 1
            if remaining[target] == 0:
                queue.append(target)
    if len(seen) != node_count or visited != node_count:
        return None

    if any(degree > 1 for degree in indegree):
        topology = "multi_input_merge"
    elif any(degree > 1 for degree in outdegree) or sum(
        degree == 0 for degree in outdegree
    ) > 1:
        topology = "branch_or_multi_output"
    else:
        topology = "linear"
    size = (
        "one_step"
        if node_count == 1
        else "two_to_three"
        if node_count <= 3
        else "four_to_six"
        if node_count <= 6
        else "seven_plus"
    )
    return {"graph_size_stratum": size, "topology": topology}


def _modality(operators: list[str], catalog: dict[str, dict[str, Any]]) -> str:
    types = {
        value.lower()
        for operator in operators
        for value in (
            catalog[operator].get("input_types", [])
            + catalog[operator].get("output_types", [])
        )
    }
    raster = any(value == "raster" or "image/tiff" in value for value in types)
    vector = "vector" in types
    return (
        "mixed"
        if raster and vector
        else "raster"
        if raster
        else "vector"
        if vector
        else "unknown"
    )


def _family_supply(
    rows: list[dict[str, Any]], capability_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("quota_credit_eligible", True):
            grouped[row["quota_anchor_l3"]].append(row)
    result = []
    for capability in capability_rows:
        if capability["admission_tier"] != "headline_core":
            continue
        candidates = grouped.get(capability["l3_code"], [])
        distinct_sources = len(
            {
                row.get("supply_authority_key", row.get("source_authority_key", ""))
                for row in candidates
            }
        )
        result.append(
            {
                "l3_code": capability["l3_code"],
                "l3_name": capability["l3_name"],
                "candidate_count": len(candidates),
                "distinct_source_authorities": distinct_sources,
                "distinct_normalized_dags": len(
                    {row["normalized_dag_key"] for row in candidates}
                ),
                "modality_counts": dict(
                    sorted(Counter(row["modality"] for row in candidates).items())
                ),
                "topology_counts": dict(
                    sorted(Counter(row["topology"] for row in candidates).items())
                ),
                "graph_size_counts": dict(
                    sorted(
                        Counter(
                            row["graph_size_stratum"] for row in candidates
                        ).items()
                    )
                ),
                "quota_8_required_supply": required_supply(8),
                "quota_8_supply_met": distinct_sources >= required_supply(8),
                "quota_4_required_supply": required_supply(4),
                "quota_4_supply_met": distinct_sources >= required_supply(4),
                "gate3_family_status": (
                    "quota_8_supply_eligible"
                    if distinct_sources >= required_supply(8)
                    else "quota_4_supply_eligible"
                    if distinct_sources >= required_supply(4)
                    else "diagnostic_insufficient_supply"
                ),
            }
        )
    return result


def build(
    *,
    root: Path,
    discovery_pools: Iterable[tuple[str, str]],
    mapping_path: Path,
    catalog_path: Path,
    capability_path: Path,
    exclusion_path: Path,
    expert_proposals_path: Path | None = None,
) -> dict[str, Any]:
    mapping_artifact = json.loads(mapping_path.read_text(encoding="utf-8"))
    mappings = {row["operator_id"]: row for row in mapping_artifact["entries"]}
    catalog_artifact = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = {row["operator_id"]: row for row in catalog_artifact["operators"]}
    capability_rows = _read_jsonl(capability_path)
    exclusion_rows = _read_jsonl(exclusion_path)
    overlap_indexes = exclusion.build_overlap_indexes(exclusion_rows)

    rows: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    discovery_count = 0
    input_refs = {}
    for pool_id, relative_path in discovery_pools:
        path = root / relative_path
        pool_rows = _read_jsonl(path)
        discovery_count += len(pool_rows)
        input_refs[pool_id] = {
            "path": relative_path,
            "sha256": _sha256(path),
            "record_count": len(pool_rows),
        }
        for record_index, record in enumerate(pool_rows):
            if record.get("action") not in ALLOWED_ACTIONS:
                rejection_counts["action_not_candidate"] += 1
                continue
            operators = [
                str(value).lower()
                for value in (
                    record.get("ordered_operator_ids")
                    or record.get("operator_ids")
                    or []
                )
            ]
            codes = [str(value) for value in record.get("mapped_l3_chain") or []]
            if not operators or len(operators) != len(codes) or any(
                operator not in mappings
                or not mappings[operator]["strict_catalog_present"]
                or mappings[operator]["mapping_status"] != "stable101_direct"
                or mappings[operator]["stable101_l3"] != code
                or not mappings[operator]["headline_eligible"]
                for operator, code in zip(operators, codes)
            ):
                rejection_counts["gate1_authority_failed"] += 1
                continue
            edges = [
                (source, target)
                for source, target, _kind in exclusion._edges(record)
            ]
            profile = graph_profile(len(operators), edges)
            if profile is None:
                rejection_counts["invalid_or_incomplete_graph"] += 1
                continue
            if not record.get("source_sha256"):
                rejection_counts["missing_source_authority"] += 1
                continue
            overlap = exclusion.check_candidate_overlap(record, overlap_indexes)
            if overlap:
                rejection_counts["gate2_overlap"] += 1
                continue
            modality = _modality(operators, catalog)
            if modality == "unknown":
                rejection_counts["unknown_modality"] += 1
                continue

            fingerprint = exclusion.fingerprint_record(
                record,
                artifact_id=pool_id,
                record_index=record_index,
                source_root=root,
            )
            analytical = [
                code
                for operator, code in zip(operators, codes)
                if mappings[operator]["task_role"] == "analytical"
            ]
            anchor = (analytical or codes)[0]
            source_authority = (
                "normalized_source_body_sha256:"
                + fingerprint["normalized_source_body_sha256"]
                if fingerprint["normalized_source_body_sha256"]
                else "source_sha256:" + fingerprint["source_sha256"]
            )
            candidate_id = "qgis-supply-" + _json_hash(
                [
                    pool_id,
                    record.get("record_id", record_index),
                    source_authority,
                    fingerprint["normalized_dag_key"],
                ]
            )[:20]
            rows.append(
                {
                    "schema": "gis_recommend.qgis_benchmark_candidate_supply.v1",
                    "candidate_id": candidate_id,
                    "discovery_ref": f"{pool_id}:{record_index}",
                    "discovery_record_id": str(record.get("record_id", "")),
                    "provenance_class": "qgis_source_backed",
                    "source_authority_key": source_authority,
                    "source_sha256": fingerprint["source_sha256"],
                    "source_region_key": fingerprint["source_region_key"],
                    "call_graph_signature": fingerprint["call_graph_signature"],
                    "processes": [
                        {
                            "process_id": f"p{index}",
                            "operator_id": operator,
                            "stable101_l3": code,
                        }
                        for index, (operator, code) in enumerate(
                            zip(operators, codes)
                        )
                    ],
                    "links": [
                        {"source_process_id": f"p{source}", "target_process_id": f"p{target}"}
                        for source, target in edges
                    ],
                    "parameters_included": False,
                    "quota_anchor_l3": anchor,
                    "covered_l3": sorted(set(codes)),
                    "modality": modality,
                    **profile,
                    "normalized_dag_key": fingerprint["normalized_dag_key"],
                    "forbidden_near_dag_key": fingerprint[
                        "forbidden_near_dag_key"
                    ],
                    "semantic_dag_key": fingerprint["semantic_dag_key"],
                    "gate1_status": "passed",
                    "gate2_overlap_fields": [],
                    "supply_admission": "provisional_gate3_candidate",
                }
            )

    expert_input_ref = None
    if expert_proposals_path is not None:
        expert_rows = _read_jsonl(expert_proposals_path)
        expert_input_ref = {
            "path": str(expert_proposals_path),
            "sha256": _sha256(expert_proposals_path),
            "record_count": len(expert_rows),
        }
        for proposal in expert_rows:
            required_state = (
                proposal.get("provenance_class") == "expert_authored"
                and proposal.get("graph_review_status") == "independent_reviewed"
                and proposal.get("gate1_status") == "passed"
                and proposal.get("gate2_status") == "passed"
                and proposal.get("dedup_status") == "canonical"
                and proposal.get("human_approval_status") == "approved"
                and proposal.get("supply_admission") == "gate3_candidate_admitted"
            )
            processes = proposal.get("processes", [])
            authority_valid = bool(processes) and all(
                process.get("operator_id") in mappings
                and mappings[process["operator_id"]]["strict_catalog_present"]
                and mappings[process["operator_id"]]["mapping_status"]
                == "stable101_direct"
                and mappings[process["operator_id"]]["stable101_l3"]
                == process.get("l3_code")
                and mappings[process["operator_id"]]["headline_eligible"]
                and process.get("operator_id") in catalog
                for process in processes
            )
            if not required_state or not authority_valid:
                rejection_counts["expert_proposal_not_fully_admitted"] += 1
                continue
            proposal_id = str(proposal["proposal_id"])
            rows.append(
                {
                    "schema": "gis_recommend.qgis_benchmark_candidate_supply.v1",
                    "candidate_id": "qgis-expert-" + _json_hash(proposal_id)[:20],
                    "proposal_ref": proposal_id,
                    "provenance_class": "expert_authored",
                    "source_authority_key": "",
                    "supply_authority_key": "expert_proposal:" + proposal_id,
                    "source_sha256": "",
                    "source_region_key": "",
                    "call_graph_signature": "",
                    "processes": [
                        {
                            "process_id": process["process_id"],
                            "operator_id": process["operator_id"],
                            "stable101_l3": process["l3_code"],
                        }
                        for process in processes
                    ],
                    "links": [dict(link) for link in proposal.get("links", [])],
                    "parameters_included": False,
                    "quota_anchor_l3": proposal["quota_anchor_l3"],
                    "quota_credit_eligible": proposal.get(
                        "quota_credit_eligible", True
                    ),
                    "covered_l3": proposal["covered_l3"],
                    "modality": proposal["modality"],
                    "topology": proposal["topology"],
                    "graph_size_stratum": proposal["graph_size_stratum"],
                    "normalized_dag_key": proposal["normalized_dag_key"],
                    "forbidden_near_dag_key": proposal["forbidden_near_dag_key"],
                    "semantic_dag_key": proposal["semantic_dag_key"],
                    "gate1_status": "passed",
                    "gate2_overlap_fields": [],
                    "supply_admission": "gate3_candidate_admitted",
                }
            )

    rows.sort(key=lambda row: row["candidate_id"])
    family_supply = _family_supply(rows, capability_rows)
    quota8 = [row["l3_code"] for row in family_supply if row["quota_8_supply_met"]]
    quota4 = [row["l3_code"] for row in family_supply if row["quota_4_supply_met"]]
    modality_counts = dict(sorted(Counter(row["modality"] for row in rows).items()))
    topology_counts = dict(sorted(Counter(row["topology"] for row in rows).items()))
    graph_size_counts = dict(
        sorted(Counter(row["graph_size_stratum"] for row in rows).items())
    )
    provenance_counts = {
        "expert_authored": sum(
            row["provenance_class"] == "expert_authored" for row in rows
        ),
        "qgis_source_backed": sum(
            row["provenance_class"] == "qgis_source_backed" for row in rows
        ),
    }
    failures = []
    if provenance_counts["expert_authored"] == 0:
        failures.append("expert_authored_minimum_unmet")
    if len(quota8) < 10 or len(quota4) < 20:
        failures.append("twenty_family_quota_plus_reserve_unmet")
    for modality, minimum in {"vector": 60, "raster": 36, "mixed": 24}.items():
        if modality_counts.get(modality, 0) < minimum:
            failures.append(f"modality_{modality}_minimum_unmet")
    for topology, minimum in {
        "linear": 60,
        "multi_input_merge": 36,
        "branch_or_multi_output": 24,
    }.items():
        if topology_counts.get(topology, 0) < minimum:
            failures.append(f"topology_{topology}_minimum_unmet")
    for size, minimum in {
        "one_step": 18,
        "two_to_three": 36,
        "four_to_six": 42,
        "seven_plus": 24,
    }.items():
        if graph_size_counts.get(size, 0) < minimum:
            failures.append(f"graph_size_{size}_minimum_unmet")

    summary = {
        "schema": "gis_recommend.qgis_benchmark_candidate_supply_summary.v1",
        "taxonomy_id": "stable101-paper-v1",
        "discovery_inputs": input_refs,
        "gate1_inputs": {
            "mapping_sha256": _sha256(mapping_path),
            "catalog_sha256": _sha256(catalog_path),
            "capability_matrix_sha256": _sha256(capability_path),
        },
        "gate2_exclusion_sha256": _sha256(exclusion_path),
        "discovery_record_count": discovery_count,
        "candidate_count": len(rows),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "distinct_source_authorities": len(
            {
                row["source_authority_key"]
                for row in rows
                if row["provenance_class"] == "qgis_source_backed"
            }
        ),
        "distinct_normalized_dags": len(
            {row["normalized_dag_key"] for row in rows}
        ),
        "provenance_counts": provenance_counts,
        "modality_counts": modality_counts,
        "topology_counts": topology_counts,
        "graph_size_counts": graph_size_counts,
        "family_supply": family_supply,
        "quota_8_supply_eligible_families": sorted(quota8),
        "quota_4_supply_eligible_families": sorted(quota4),
        "family_roster_status": "not_frozen",
        "proposed_family_roster": [],
        "joint_feasibility_evaluated": False,
        "joint_feasibility_reason": "necessary_supply_conditions_failed",
        "gate_status": "failed_insufficient_candidate_supply",
        "failure_reasons": failures,
        "next_action": (
            "add independently reviewed expert-authored candidates and source-backed "
            "raster/merge/branch/long-graph supply, then rebuild Gate 3"
        ),
    }
    if expert_input_ref is not None:
        summary["expert_proposal_input"] = expert_input_ref
    return {"rows": rows, "summary": summary}


def write_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "candidate_supply": output_dir / "candidate_supply.jsonl",
        "candidate_supply_summary": output_dir / "candidate_supply_summary.json",
    }
    paths["candidate_supply"].write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in result["rows"]
        ),
        encoding="utf-8",
    )
    paths["candidate_supply_summary"].write_text(
        json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "benchmarks/qgis_planner_v1/authority",
    )
    parser.add_argument(
        "--expert-proposals",
        type=Path,
        default=None,
        help="Optional fully reviewed and admitted expert proposal ledger.",
    )
    args = parser.parse_args(argv)
    result = build(
        root=ROOT,
        discovery_pools=DEFAULT_DISCOVERY_POOLS,
        mapping_path=ROOT / "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json",
        catalog_path=ROOT / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json",
        capability_path=ROOT / "benchmarks/qgis_planner_v1/authority/capability_matrix.jsonl",
        exclusion_path=ROOT / "benchmarks/qgis_planner_v1/authority/source_exclusion_ledger.jsonl",
        expert_proposals_path=args.expert_proposals,
    )
    write_outputs(result, args.output_dir)
    print(
        f"candidates={len(result['rows'])} "
        f"sources={result['summary']['distinct_source_authorities']} "
        f"dags={result['summary']['distinct_normalized_dags']} "
        f"status={result['summary']['gate_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
