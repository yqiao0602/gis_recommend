#!/usr/bin/env python3
"""Replay Processing workflow tiers through structural, mapping-closed gates.

This is the first admission pass after source-role scoring. It deliberately
stops before description, deduplication, tokenization, or training export.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from recover_qgis_legacy_provider_ids import canonicalize_operator_id

from gis_recommend.data.qgis_conversion_features import extract_conversion_features
from gis_recommend.data.qgis_conversion_rules import route_candidate

SCHEMA = "gis_recommend.qgis_workflow_tier_structural_replay.v1"
TIERS = {"tier1_multi_step_workflow", "tier2_single_operator_workflow"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def read_catalog(path: Path) -> set[str]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    values = {
        str(entry.get("operator_id") or "").strip().lower()
        for entry in catalog.get("operators") or []
        if isinstance(entry, dict)
    }
    if not values:
        raise ValueError("catalog has no operator IDs")
    return values


def processing_entrypoint_sites(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    sites: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        is_processing_entrypoint = (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "processing"
            and node.func.attr in {"run", "runAndLoadResults", "runalg"}
        )
        first_arg = node.args[0]
        if not is_processing_entrypoint or not isinstance(first_arg, ast.Constant):
            continue
        if not isinstance(first_arg.value, str) or not first_arg.value.strip():
            continue
        sites.append(
            {
                "operator_id": first_arg.value.strip().lower(),
                "entrypoint": str(node.func.attr),
                "line_start": int(node.lineno),
                "line_end": int(node.end_lineno or node.lineno),
            }
        )
    return sorted(sites, key=lambda value: (value["line_start"], value["line_end"]))


def _status_for_route(action: str) -> str:
    if action == "auto_accept_candidate":
        return "candidate_pending_description"
    if action == "defer_mapping":
        return "deferred_mapping"
    if action == "defer_operator_resolution":
        return "deferred_operator_resolution"
    return "deferred_boundary"


def replay_row(
    row: dict[str, Any], catalog_ids: set[str], mapping: dict[str, str]
) -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "record_id": str(row.get("record_id") or ""),
        "source_sha256": str(row.get("source_sha256") or ""),
        "source_path": str(row.get("source_path") or ""),
        "source_root_id": str(row.get("source_root_id") or ""),
        "workflow_value_tier": str(row.get("workflow_value_tier") or ""),
        "source_role": str(row.get("source_role") or ""),
        "processing_run_count_census": int(row.get("processing_run_count") or 0),
        "task_semantic_signal": bool(row.get("task_semantic_signal")),
        "input_output_signal": bool(row.get("input_output_signal")),
        "data_dependency_signal": bool(row.get("data_dependency_signal")),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_structural_replay_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    path = Path(result["source_path"])
    if not path.is_file():
        return {**result, "status": "deferred_source_missing", "reason": "source_file_missing"}
    if sha256_file(path) != result["source_sha256"]:
        return {**result, "status": "excluded_source_integrity", "reason": "source_sha_mismatch"}
    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        raw_sites = processing_entrypoint_sites(source)
    except SyntaxError as exc:
        return {**result, "status": "excluded_unparseable", "reason": str(exc)}

    supported_sites = [site for site in raw_sites if site["entrypoint"] == "run"]
    result["supported_processing_run_sites"] = supported_sites
    if raw_sites and not supported_sites:
        return {
            **result,
            "status": "deferred_extractor_unsupported",
            "reason": "processing_entrypoint_not_supported_by_structural_extractor",
        }

    canonical_sites: list[dict[str, Any]] = []
    unresolved: list[str] = []
    migrations: list[dict[str, str]] = []
    for site in supported_sites:
        canonical, rule = canonicalize_operator_id(site["operator_id"], catalog_ids)
        if canonical is None:
            unresolved.append(site["operator_id"])
            continue
        canonical_sites.append({**site, "operator_id": canonical})
        if rule != "catalog_exact":
            migrations.append({"source": site["operator_id"], "target": canonical, "rule": rule})
    result.update(
        {
            "raw_literal_call_sites": raw_sites,
            "call_sites": canonical_sites,
            "canonical_operator_ids": [site["operator_id"] for site in canonical_sites],
            "unresolved_operator_ids": list(dict.fromkeys(unresolved)),
            "provider_migrations": migrations,
        }
    )
    if unresolved:
        return {
            **result,
            "status": "deferred_operator_resolution",
            "reason": "literal_operator_not_in_catalog_or_verified_alias",
        }
    if not canonical_sites:
        return {
            **result,
            "status": "deferred_extractor_unsupported",
            "reason": "no_literal_processing_run",
        }

    # The feature extractor must see the IDs as written in source. Provider
    # migration happens only after structural evidence is recovered; otherwise
    # qgis:* -> native:* aliases falsely trigger candidate-alignment failure.
    features = dict(extract_conversion_features(source, call_sites=supported_sites).data)
    if features["candidate_alignment_status"] != "candidate_alignment_matched":
        return {
            **result,
            "status": "deferred_extractor_unsupported",
            "reason": "processing_entrypoint_alignment_not_supported",
            "feature_extractor_version": features["feature_extractor_version"],
            "candidate_alignment_status": features["candidate_alignment_status"],
        }
    canonical_operator_ids = [
        canonicalize_operator_id(operator, catalog_ids)[0]
        for operator in features["operator_ids"]
    ]
    if any(operator is None for operator in canonical_operator_ids):
        return {
            **result,
            "status": "deferred_operator_resolution",
            "reason": "post_extraction_operator_normalization_failed",
            "feature_extractor_version": features["feature_extractor_version"],
            "candidate_alignment_status": features["candidate_alignment_status"],
        }
    canonical_operator_ids = [str(operator) for operator in canonical_operator_ids]
    features["operator_ids"] = canonical_operator_ids
    features["ordered_operator_ids"] = canonical_operator_ids
    features["operator_count"] = len(canonical_operator_ids)
    result["call_sites"] = [
        {**site, "operator_id": canonical}
        for site, canonical in zip(supported_sites, canonical_operator_ids, strict=True)
    ]
    mapped_l3_chain = [mapping.get(operator, "") for operator in canonical_operator_ids]
    route_input = {
        "call_graph_status": "single_scope",
        "api_pattern_calls": [],
        "mapped_l3_chain": mapped_l3_chain,
    }
    decision = route_candidate(route_input, features)
    result.update(
        {
            "canonical_operator_ids": canonical_operator_ids,
            "operator_ids": canonical_operator_ids,
            "ordered_operator_ids": canonical_operator_ids,
            "operator_sequence": canonical_operator_ids,
            "dependency_edges": features["dependency_edges"],
            "workflow_unit_scope": features["workflow_unit_scope"],
            "feature_extractor_version": features["feature_extractor_version"],
            "candidate_alignment_status": features["candidate_alignment_status"],
            "mapping_complete": bool(features["operator_ids"]) and all(mapped_l3_chain),
            "unmapped_operator_ids": [
                operator for operator in features["operator_ids"] if operator not in mapping
            ],
            "mapped_l3_chain": mapped_l3_chain if all(mapped_l3_chain) else [],
            "l3_code_sequence": mapped_l3_chain if all(mapped_l3_chain) else [],
            "route_action": decision.action,
            "route_rule_id": decision.rule_id,
            "action": decision.action,
            "rule_id": decision.rule_id,
            "route_evidence": decision.evidence,
            "status": _status_for_route(decision.action),
            "reason": decision.rule_id,
        }
    )
    return result


def replay(
    rows: Iterable[dict[str, Any]], catalog_ids: set[str], mapping: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row.get("pool") == "processing" and row.get("workflow_value_tier") in TIERS
    ]
    identities = {(row.get("record_id"), row.get("source_sha256")) for row in selected}
    if len(identities) != len(selected) or any(not all(identity) for identity in identities):
        raise ValueError("selected tier rows must have unique nonblank source identities")
    output = [replay_row(row, catalog_ids, mapping) for row in selected]
    by_tier = {
        tier: dict(sorted(Counter(row["status"] for row in output if row["workflow_value_tier"] == tier).items()))
        for tier in sorted(TIERS)
    }
    return output, {
        "schema": f"{SCHEMA}.summary",
        "selected_source_rows": len(output),
        "tier_counts": dict(sorted(Counter(row["workflow_value_tier"] for row in output).items())),
        "status_counts": dict(sorted(Counter(row["status"] for row in output).items())),
        "status_counts_by_tier": by_tier,
        "candidate_rows_pending_description": sum(row["status"] == "candidate_pending_description" for row in output),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_structural_replay_only",
        "llm_called": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier-ledger", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise TypeError("mapping must be an object")
    output, summary = replay(read_jsonl(args.tier_ledger), read_catalog(args.catalog), mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "structural_replay_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inputs = {path.name: sha256_file(path) for path in (args.tier_ledger, args.catalog, args.mapping)}
    hashes = {ledger.name: sha256_file(ledger), summary_path.name: sha256_file(summary_path), "inputs": inputs}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
