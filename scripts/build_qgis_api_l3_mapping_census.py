#!/usr/bin/env python3
"""Build a fail-closed stable110 mapping census for QGIS API task units."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_api_l3_mapping_census.v1"
MAPPING_RULE_ID = "qgis-api-exact-semantic-stable110-v1"
SEMANTIC_ROLES = {"geometry_transform", "crs_transform", "composite_algorithm"}
EXACT_CALL_TO_L3 = {
    "buffer": "L3_02_01_01",
    "intersection": "L3_02_02_01",
    "simplify": "L3_02_05_01",
    "centroid": "L3_02_05_11",
    "convexHull": "L3_02_05_12",
}
COMPOSITE_CALL_TO_L3 = {
    "random_point_sampling": {
        "l3_code": "L3_02_06_06",
        "recovery_rule_id": "lexical-scope-random-point-sampling-v1",
        "recovery_status": "resolved_complete_lexical_scope_workflow",
    }
}
UNRESOLVED_REASONS = {
    "interpolate": "parameter_dependent",
    "combine": "taxonomy_contract_mismatch",
    "offsetCurve": "taxonomy_gap",
    "transform": "task_scope_insufficient",
}


def _method_name(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1]


def _intersection_output_contract(candidate: dict[str, Any]) -> bool:
    attribute_steps = [
        step
        for step in candidate.get("steps") or []
        if step.get("call_role") == "attribute_mutation"
    ]
    for step in attribute_steps:
        if _method_name(str(step.get("call_name") or "")) != "setAttributes":
            continue
        names = {
            str(name).lower().replace("_", "")
            for name in step.get("consumed_names") or []
        }
        if any(
            f"{prefix}a" in names and f"{prefix}b" in names
            for prefix in ("attr", "attrs", "attribute", "attributes")
        ):
            return True
    payloads_by_receiver: dict[str, set[str]] = defaultdict(set)
    for step in attribute_steps:
        if _method_name(str(step.get("call_name") or "")) != "setAttribute":
            continue
        receiver = str(step.get("receiver") or "")
        payloads_by_receiver[receiver].update(
            str(name)
            for name in step.get("consumed_names") or []
            if str(name) != receiver
        )
    return any(len(payloads) >= 2 for payloads in payloads_by_receiver.values())


def _verified_composite_l3(
    candidate: dict[str, Any], call_name: str
) -> str | None:
    authority = COMPOSITE_CALL_TO_L3.get(call_name)
    if authority is None:
        return None
    if (
        candidate.get("random_point_recovery_rule_id")
        != authority["recovery_rule_id"]
        or candidate.get("random_point_recovery_status")
        != authority["recovery_status"]
    ):
        return None
    return authority["l3_code"]


def classify_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    semantic_steps = [
        step
        for step in candidate.get("steps") or []
        if step.get("call_role") in SEMANTIC_ROLES
    ]
    resolved: list[str] = []
    unresolved: list[dict[str, str]] = []
    semantic_calls: list[str] = []
    for step in semantic_steps:
        call_name = str(step.get("call_name") or "")
        semantic_calls.append(call_name)
        method = _method_name(call_name)
        composite_l3 = _verified_composite_l3(candidate, call_name)
        if step.get("call_role") == "composite_algorithm" and composite_l3 is None:
            unresolved.append(
                {
                    "call_name": call_name,
                    "reason": "unverified_composite_pattern_provenance",
                }
            )
        elif composite_l3 is not None:
            resolved.append(composite_l3)
        elif method == "intersection" and not _intersection_output_contract(candidate):
            unresolved.append(
                {
                    "call_name": call_name,
                    "reason": "output_contract_insufficient",
                }
            )
        elif method in EXACT_CALL_TO_L3:
            resolved.append(EXACT_CALL_TO_L3[method])
        else:
            unresolved.append(
                {
                    "call_name": call_name,
                    "reason": UNRESOLVED_REASONS.get(method, "unsupported_semantic_call"),
                }
            )

    if not semantic_steps:
        status = "mutation_export_only"
        candidate_l3_sequence: list[str] = []
    elif unresolved:
        status = "unresolved"
        candidate_l3_sequence = []
    else:
        status = "exact_existing_l3"
        candidate_l3_sequence = resolved

    return {
        **candidate,
        "schema": SCHEMA,
        "mapping_rule_id": MAPPING_RULE_ID,
        "mapping_status": status,
        "semantic_calls": semantic_calls,
        "resolved_l3_evidence": resolved,
        "unresolved_semantic_calls": unresolved,
        "candidate_l3_sequence": candidate_l3_sequence,
        "mapping_admission": (
            "proposal_only_existing_taxonomy"
            if status == "exact_existing_l3"
            else "not_granted"
        ),
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_mapping_census_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def build_census(
    candidates: list[dict[str, Any]], stable110_extension: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if (
        stable110_extension.get("proposed_taxonomy") != "stable110"
        or stable110_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable110 taxonomy authority")
    stable_codes = set(stable110_extension.get("existing_code_to_id") or {})
    stable_codes.update(stable110_extension.get("proposed_code_to_id_additions") or {})
    mapped_codes = set(EXACT_CALL_TO_L3.values()) | {
        str(value["l3_code"]) for value in COMPOSITE_CALL_TO_L3.values()
    }
    missing_codes = sorted(mapped_codes - stable_codes)
    if missing_codes:
        raise ValueError(f"exact mappings are absent from stable110: {missing_codes}")

    classified = [classify_candidate(candidate) for candidate in candidates]
    exact = [row for row in classified if row["mapping_status"] == "exact_existing_l3"]
    deferred = [row for row in classified if row["mapping_status"] != "exact_existing_l3"]

    cluster_rows: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in classified:
        signature = tuple(_method_name(call) for call in row["semantic_calls"])
        cluster_rows[signature].append(row)
    clusters = []
    for signature, rows in sorted(cluster_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        clusters.append(
            {
                "schema": "gis_recommend.qgis_api_l3_mapping_cluster.v1",
                "semantic_signature": list(signature),
                "mapping_status": rows[0]["mapping_status"],
                "candidate_l3_sequence": rows[0]["candidate_l3_sequence"],
                "unit_count": len(rows),
                "source_authority_count": len(
                    {str(row.get("source_authority_key") or "") for row in rows}
                ),
                "candidate_ids": sorted(str(row.get("candidate_id") or "") for row in rows),
                "training_admission": "not_granted_mapping_census_only",
            }
        )

    status_counts = Counter(row["mapping_status"] for row in classified)
    unresolved_reasons = Counter(
        item["reason"]
        for row in classified
        for item in row["unresolved_semantic_calls"]
    )
    summary = {
        "schema": "gis_recommend.qgis_api_l3_mapping_census_summary.v1",
        "mapping_rule_id": MAPPING_RULE_ID,
        "taxonomy_authority": "stable110",
        "input_candidate_units": len(classified),
        "input_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in classified}
        ),
        "strong_semantic_anchor_units": sum(
            1 for row in classified if row["semantic_calls"]
        ),
        "exact_existing_l3_units": len(exact),
        "exact_existing_l3_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in exact}
        ),
        "deferred_units": len(deferred),
        "mapping_status_counts": dict(sorted(status_counts.items())),
        "unresolved_reason_counts": dict(sorted(unresolved_reasons.items())),
        "semantic_cluster_count": len(clusters),
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_admission": "not_granted_mapping_census_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return exact, deferred, clusters, summary


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--stable110-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    exact, deferred, clusters, summary = build_census(
        _read_jsonl(args.candidates), _read_json(args.stable110_extension)
    )
    output_values = {
        "exact_existing_l3_proposals_v1.jsonl": exact,
        "mapping_deferred_v1.jsonl": deferred,
        "semantic_clusters_v1.jsonl": clusters,
    }
    output_paths = []
    for name, rows in output_values.items():
        path = args.output_dir / name
        _write_jsonl(path, rows)
        output_paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    output_paths.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.candidates.name: {"path": str(args.candidates), "sha256": _sha256(args.candidates)},
            args.stable110_extension.name: {
                "path": str(args.stable110_extension),
                "sha256": _sha256(args.stable110_extension),
            },
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in output_paths
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
