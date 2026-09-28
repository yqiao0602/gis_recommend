from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gis_recommend.data.qgis_custom_implementation import (  # noqa: E402
    build_implementation_index,
    expand_custom_implementation,
    extract_custom_implementations,
)
from gis_recommend.data.qgis_conversion_features import (  # noqa: E402
    extract_conversion_features,
)
from gis_recommend.data.qgis_conversion_rules import route_candidate  # noqa: E402
from gis_recommend.data.qgis_source_authority import source_authority  # noqa: E402
from gis_recommend.data.qgis_subworkflow_splitter import (  # noqa: E402
    literalize_processing_operator_ids,
)
from build_qgis_direct_description_candidates import build_candidates  # noqa: E402
from build_qgis_recovery_local_dag_units import build_recovery_units  # noqa: E402
from build_qgis_split_subworkflow_units import build_split_units  # noqa: E402
from recover_qgis_legacy_provider_ids import (  # noqa: E402
    canonicalize_operator_id,
    load_catalog_ids,
)
from run_qgis_processing_blocker_batch import (  # noqa: E402
    annotate_dedup,
    build_candidate_pool,
)


SCHEMA = "gis_recommend.qgis_custom_implementation_expansion.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_jsonls(paths: Iterable[Path]) -> list[dict[str, Any]]:
    return [row for path in paths for row in _load_jsonl(path)]


def _unresolved_implementation_targets(
    operator_rows: Iterable[dict[str, Any]],
) -> set[str]:
    return {
        f"script:{str(operator_id).partition(':')[2].strip().lower()}"
        for row in operator_rows
        if row.get("normalization_status") == "partially_normalized"
        for operator_id in row.get("unresolved_operator_ids") or []
        if ":" in str(operator_id) and str(operator_id).partition(":")[2].strip()
    }


def _canonicalize(operator_id: str, catalog_ids: set[str]) -> str | None:
    return canonicalize_operator_id(operator_id, catalog_ids)[0]


def _verify_and_extract(
    source_rows: Iterable[dict[str, Any]], target_custom_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    instances: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    verified = 0
    for source in source_rows:
        path = Path(str(source.get("source_path") or ""))
        expected = str(source.get("source_sha256") or source.get("content_sha256") or "")
        if not path.is_file():
            failures.append({**source, "source_path_resolution": "source_file_missing"})
            continue
        actual = _sha256(path)
        if actual != expected:
            failures.append({**source, "source_path_resolution": "source_sha256_mismatch"})
            continue
        verified += 1
        source_text = path.read_text(encoding="utf-8-sig", errors="replace")
        authority = source_authority(path, source_sha256=actual)
        for implementation in extract_custom_implementations(source_text):
            if implementation["algorithm_id"] not in target_custom_ids:
                continue
            instances.append(
                {
                    **implementation,
                    "schema": SCHEMA,
                    "source_path": str(path),
                    "source_sha256": actual,
                    "source_root_id": source.get("source_root_id"),
                    "relative_path": source.get("relative_path"),
                    "source_path_resolution": "verified_exact",
                    **authority,
                    "training_admission": "not_granted_implementation_expansion_only",
                    "training_row_emitted": False,
                }
            )
    return instances, failures, verified


def _apply_semantic_operator_authority(
    instances: list[dict[str, Any]], authority_rows: Iterable[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    authority: dict[tuple[str, int, int, str], dict[str, str]] = {}
    for row in authority_rows:
        body_hash = str(row.get("implementation_body_sha256") or "")
        raw_operator = str(row.get("raw_operator_id") or "").strip().lower()
        resolved_operator = str(row.get("resolved_operator_id") or "").strip().lower()
        rule_id = str(row.get("rule_id") or "")
        line_start = int(row.get("line_start") or 0)
        line_end = int(row.get("line_end") or 0)
        if not all((body_hash, raw_operator, resolved_operator, rule_id, line_start, line_end)):
            continue
        key = (body_hash, line_start, line_end, raw_operator)
        value = {"resolved_operator_id": resolved_operator, "rule_id": rule_id}
        existing = authority.get(key)
        if existing is not None and existing != value:
            raise ValueError(f"conflicting semantic operator authority for {key!r}")
        authority[key] = value

    matched: set[tuple[str, int, int, str]] = set()
    resolved_instances: list[dict[str, Any]] = []
    for instance in instances:
        body_hash = str(instance.get("implementation_body_sha256") or "")
        literal_operators = list(instance.get("literal_operator_ids") or [])
        call_sites: list[dict[str, Any]] = []
        resolutions: list[dict[str, Any]] = []
        for index, raw_call in enumerate(instance.get("call_sites") or []):
            call = dict(raw_call)
            raw_operator = str(call.get("operator_id") or "").strip().lower()
            line_start = int(call.get("line_start") or 0)
            line_end = int(call.get("line_end") or 0)
            key = (body_hash, line_start, line_end, raw_operator)
            decision = authority.get(key)
            if decision is not None:
                resolved_operator = decision["resolved_operator_id"]
                call["operator_id"] = resolved_operator
                if index < len(literal_operators):
                    literal_operators[index] = resolved_operator
                resolutions.append(
                    {
                        "line_start": line_start,
                        "line_end": line_end,
                        "raw_operator_id": raw_operator,
                        "resolved_operator_id": resolved_operator,
                        "rule_id": decision["rule_id"],
                    }
                )
                matched.add(key)
            call_sites.append(call)
        resolved_instances.append(
            {
                **instance,
                "call_sites": call_sites,
                "literal_operator_ids": literal_operators,
                "semantic_operator_resolutions": resolutions,
            }
        )
    return resolved_instances, len(authority), len(matched)


def _variant_rows(
    instances: list[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
    catalog_ids: set[str],
) -> list[dict[str, Any]]:
    sources: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for instance in instances:
        key = (instance["algorithm_id"], instance["implementation_body_sha256"])
        sources[key].append(instance)

    rows: list[dict[str, Any]] = []
    for algorithm_id, variants in sorted(index.items()):
        for variant in variants:
            expansion = expand_custom_implementation(
                algorithm_id,
                index,
                catalog_ids=catalog_ids,
                canonicalize_operator=_canonicalize,
                implementation_body_bindings={
                    algorithm_id: variant["implementation_body_sha256"]
                },
            )
            key = (algorithm_id, variant["implementation_body_sha256"])
            source_instances = sorted(
                sources[key], key=lambda row: (row["source_sha256"], row["source_path"])
            )
            rows.append(
                {
                    **variant,
                    **expansion,
                    "schema": SCHEMA,
                    "source_instance_count": len(source_instances),
                    "source_instances": [
                        {
                            "source_path": row["source_path"],
                            "source_sha256": row["source_sha256"],
                            "source_root_id": row.get("source_root_id"),
                            "relative_path": row.get("relative_path"),
                        }
                        for row in source_instances
                    ],
                    "training_admission": "not_granted_implementation_expansion_only",
                    "training_row_emitted": False,
                }
            )
    return rows


def _component_count(node_count: int, edges: Iterable[Iterable[int]]) -> int:
    adjacency = [set() for _ in range(node_count)]
    for edge in edges:
        source, target = (int(value) for value in edge)
        adjacency[source].add(target)
        adjacency[target].add(source)
    seen: set[int] = set()
    count = 0
    for start in range(node_count):
        if start in seen:
            continue
        count += 1
        seen.add(start)
        pending = [start]
        while pending:
            for neighbour in adjacency[pending.pop()]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    pending.append(neighbour)
    return count


def _scope_replay(
    variants: list[dict[str, Any]],
    mapping: dict[str, str],
    train_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    parents: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for variant in variants:
        operators = list(variant.get("expanded_operator_ids") or [])
        raw_sites = list(variant.get("call_sites") or [])
        if variant.get("expansion_status") != "expanded_complete":
            continue
        if not operators or len(operators) != len(raw_sites):
            continue
        if any(operator not in mapping for operator in operators):
            continue
        instances = sorted(
            variant.get("source_instances") or [],
            key=lambda row: (str(row.get("source_sha256") or ""), str(row.get("source_path") or "")),
        )
        if not instances:
            continue
        source = instances[0]
        path = Path(str(source.get("source_path") or ""))
        expected_sha = str(source.get("source_sha256") or "")
        if not path.is_file() or _sha256(path) != expected_sha:
            failures.append(
                {
                    "implementation_body_sha256": str(
                        variant.get("implementation_body_sha256") or ""
                    ),
                    "reason": "source_replay_failed",
                }
            )
            continue
        call_sites = [
            {**site, "operator_id": operator}
            for site, operator in zip(raw_sites, operators)
        ]
        try:
            analysis_source = literalize_processing_operator_ids(
                path.read_text(encoding="utf-8-sig", errors="replace"),
                call_sites=call_sites,
                require_full_coverage=False,
            )
        except ValueError as exc:
            failures.append(
                {
                    "implementation_body_sha256": str(
                        variant.get("implementation_body_sha256") or ""
                    ),
                    "reason": str(exc),
                }
            )
            continue
        features = extract_conversion_features(
            analysis_source, call_sites=call_sites
        ).data
        body_hash = str(variant["implementation_body_sha256"])
        parent = {
            **source,
            "record_id": f"custom_{body_hash[:24]}",
            "algorithm_id": variant.get("algorithm_id"),
            "implementation_body_sha256": body_hash,
            "source_authority_basis": "implementation_body_sha256",
            "source_authority_key": f"implementation_body_sha256:{body_hash}",
            "call_sites": call_sites,
            "operator_ids": operators,
            "ordered_operator_ids": operators,
            "canonical_operator_ids": operators,
            "mapped_l3_chain": [mapping[operator] for operator in operators],
            "mapping_complete": True,
            "signature_hash": body_hash,
            "provider_migrations": [{"rule": "custom_scope_canonicalization_v1"}],
            "resolution_status": "custom_implementation_scope_recovered",
            "call_graph_status": (
                "disconnected_candidate_scopes"
                if _component_count(len(operators), features["dependency_edges"]) > 1
                else "single_scope"
            ),
            "api_pattern_calls": [],
            **features,
        }
        decision = route_candidate(parent, features)
        parent.update(
            {
                "action": decision.action,
                "rule_id": decision.rule_id,
                "structure_evidence": decision.evidence,
                "training_admission": "not_granted_pending_scope_gates",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        parents.append(parent)

    recovery, recovery_summary = build_recovery_units(parents)
    split, split_summary = build_split_units(parents)
    direct, direct_summary = build_candidates(parents)
    candidates = build_candidate_pool(recovery, split, direct)
    dedup = annotate_dedup(candidates, train_rows)
    return {
        "scope_parents": parents,
        "scope_failures": failures,
        "scope_recovery": recovery,
        "scope_split": split,
        "scope_direct": direct,
        "scope_dedup_ledger": dedup,
        "scope_summary": {
            "scope_parent_rows": len(parents),
            "scope_failure_rows": len(failures),
            "scope_recovery_summary": recovery_summary,
            "scope_split_summary": split_summary,
            "scope_direct_summary": direct_summary,
            "scope_candidate_rows": len(candidates),
            "scope_canonical_rows": sum(
                row.get("dedup_status") == "canonical_candidate" for row in dedup
            ),
            "scope_duplicate_rows": sum(
                row.get("dedup_status") != "canonical_candidate" for row in dedup
            ),
        },
    }


def _expand_caller(
    row: dict[str, Any],
    index: dict[str, list[dict[str, Any]]],
    catalog_ids: set[str],
    mapping: dict[str, str],
    implementation_bindings: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    caller_authority = source_authority(
        Path(str(row.get("source_path") or "")),
        source_sha256=str(row.get("source_sha256") or ""),
    )
    expanded: list[str] = []
    unresolved: list[str] = []
    custom_expansions: list[dict[str, Any]] = []
    bindings = implementation_bindings or {}
    body_bindings = {
        binding["implementation_algorithm_id"]: binding["implementation_body_sha256"]
        for binding in bindings.values()
    }
    aliases = {
        custom_id: binding["implementation_algorithm_id"]
        for custom_id, binding in bindings.items()
    }
    for raw in row.get("original_operator_ids") or []:
        operator_id = str(raw).strip().lower()
        canonical = _canonicalize(operator_id, catalog_ids)
        if canonical is not None:
            expanded.append(canonical)
            continue
        if operator_id.startswith("script:") or operator_id in bindings:
            expansion = expand_custom_implementation(
                operator_id,
                index,
                catalog_ids=catalog_ids,
                canonicalize_operator=_canonicalize,
                implementation_body_bindings=body_bindings,
                implementation_id_aliases=aliases,
            )
            custom_expansions.append({"algorithm_id": operator_id, **expansion})
            if expansion["expansion_status"] == "expanded_complete":
                expanded.extend(expansion["expanded_operator_ids"])
            else:
                unresolved.extend(expansion["unresolved_operator_ids"])
            continue
        unresolved.append(operator_id)

    unresolved = list(dict.fromkeys(unresolved))
    fully_expanded = not unresolved and bool(expanded)
    mapped_l3 = [mapping.get(operator_id) for operator_id in expanded]
    mapping_complete = fully_expanded and all(mapped_l3)
    return {
        **row,
        **caller_authority,
        "schema": SCHEMA,
        "custom_implementation_expansions": custom_expansions,
        "implementation_body_bindings": body_bindings,
        "implementation_id_aliases": aliases,
        "expanded_operator_ids": expanded,
        "unresolved_operator_ids_after_expansion": unresolved,
        "expansion_status": "fully_expanded" if fully_expanded else "deferred_partial_expansion",
        "mapped_l3_chain": mapped_l3 if mapping_complete else [],
        "mapping_complete": mapping_complete,
        "training_admission": "not_granted_pending_structure_description_and_dedup",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def build_expansion(
    source_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
    *,
    catalog_ids: set[str],
    mapping: dict[str, str],
    target_custom_ids: set[str],
    implementation_bindings: list[dict[str, Any]] | None = None,
    semantic_operator_authority: list[dict[str, Any]] | None = None,
    train_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = {value.strip().lower() for value in target_custom_ids}
    binding_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for binding in implementation_bindings or []:
        caller_key = str(binding.get("caller_source_authority_key") or "")
        custom_id = str(binding.get("custom_operator_id") or "").strip().lower()
        body_hash = str(binding.get("implementation_body_sha256") or "")
        implementation_id = str(
            binding.get("implementation_algorithm_id") or custom_id
        ).strip().lower()
        if not (caller_key and custom_id and body_hash and implementation_id):
            continue
        key = (caller_key, custom_id)
        value = {
            "implementation_algorithm_id": implementation_id,
            "implementation_body_sha256": body_hash,
        }
        existing = binding_lookup.get(key)
        if existing is not None and existing != value:
            raise ValueError(f"conflicting implementation binding for {key!r}")
        binding_lookup[key] = value
    extraction_targets = targets | {
        binding["implementation_algorithm_id"] for binding in binding_lookup.values()
    }
    unique_source_rows = list(
        {
            (
                str(row.get("source_sha256") or row.get("content_sha256") or ""),
                str(row.get("source_path") or ""),
            ): row
            for row in source_rows
        }.values()
    )
    effective_catalog_ids = set(catalog_ids) | {
        str(operator_id).strip().lower() for operator_id in mapping
    }
    instances, failures, verified = _verify_and_extract(
        unique_source_rows, extraction_targets
    )
    instances, semantic_authority_rows, semantic_resolved_calls = (
        _apply_semantic_operator_authority(
            instances, semantic_operator_authority or []
        )
    )
    index = build_implementation_index(instances)
    variants = _variant_rows(instances, index, effective_catalog_ids)
    scope = _scope_replay(variants, mapping, train_rows or [])
    callers = [
        _expand_caller(
            row,
            index,
            effective_catalog_ids,
            mapping,
            {
                custom_id: binding
                for (caller_key, custom_id), binding in binding_lookup.items()
                if caller_key
                == source_authority(
                    Path(str(row.get("source_path") or "")),
                    source_sha256=str(row.get("source_sha256") or ""),
                )["source_authority_key"]
            },
        )
        for row in operator_rows
        if targets & {str(value).lower() for value in row.get("unresolved_operator_ids") or []}
    ]
    summary = {
        "schema": SCHEMA,
        "target_custom_ids": sorted(targets),
        "source_input_rows": len(source_rows),
        "source_unique_rows": len(unique_source_rows),
        "source_verified_rows": verified,
        "source_failure_rows": len(failures),
        "implementation_instance_rows": len(instances),
        "implementation_variant_rows": len(variants),
        "implementation_expansion_status_counts": dict(
            Counter(row["expansion_status"] for row in variants)
        ),
        "caller_input_rows": len(callers),
        "fully_expanded_caller_rows": sum(
            row["expansion_status"] == "fully_expanded" for row in callers
        ),
        "mapping_complete_caller_rows": sum(row["mapping_complete"] for row in callers),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_structure_description_and_dedup",
        "binding_rows": len(binding_lookup),
        "semantic_operator_authority_rows": semantic_authority_rows,
        "semantic_operator_resolved_call_rows": semantic_resolved_calls,
        **scope["scope_summary"],
    }
    return {
        "implementation_instances": instances,
        "implementation_variants": variants,
        "caller_expansions": callers,
        "source_failures": failures,
        **{key: value for key, value in scope.items() if key != "scope_summary"},
        "summary": summary,
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )


def _load_mapping(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if all(isinstance(value, str) for value in payload.values()):
        return {str(key).lower(): value for key, value in payload.items()}
    for key in ("operator_to_l3", "mapping", "mappings"):
        value = payload.get(key)
        if isinstance(value, dict):
            return {str(operator).lower(): str(l3) for operator, l3 in value.items()}
    raise ValueError(f"mapping dictionary not found in {path}")


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    paths = {
        "implementation_instances": output_dir / "implementation_instances_v1.jsonl",
        "implementation_variants": output_dir / "implementation_variants_v1.jsonl",
        "caller_expansions": output_dir / "caller_expansions_v1.jsonl",
        "source_failures": output_dir / "source_failures_v1.jsonl",
        "scope_parents": output_dir / "scope_parents_v1.jsonl",
        "scope_failures": output_dir / "scope_failures_v1.jsonl",
        "scope_recovery": output_dir / "scope_recovery_v1.jsonl",
        "scope_split": output_dir / "scope_split_v1.jsonl",
        "scope_direct": output_dir / "scope_direct_v1.jsonl",
        "scope_dedup_ledger": output_dir / "scope_dedup_ledger_v1.jsonl",
        "summary": output_dir / "summary_v1.json",
    }
    for key in (
        "implementation_instances",
        "implementation_variants",
        "caller_expansions",
        "source_failures",
        "scope_parents",
        "scope_failures",
        "scope_recovery",
        "scope_split",
        "scope_direct",
        "scope_dedup_ledger",
    ):
        _write_jsonl(paths[key], result[key])
    _atomic_write(
        paths["summary"],
        json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    ledger = {
        path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in paths.values()
    }
    _atomic_write(
        output_dir / "hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, action="append", required=True)
    parser.add_argument("--operator-ledger", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-custom-id", action="append", default=[])
    parser.add_argument("--include-unresolved-slug-targets", action="store_true")
    parser.add_argument("--binding-authority", type=Path, default=None)
    parser.add_argument("--semantic-operator-authority", type=Path, default=None)
    parser.add_argument("--train-authority", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    binding_rows = []
    if args.binding_authority is not None:
        payload = json.loads(args.binding_authority.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            binding_rows = payload.get("bindings", [])
        elif isinstance(payload, list):
            binding_rows = payload
    semantic_rows = []
    if args.semantic_operator_authority is not None:
        payload = json.loads(
            args.semantic_operator_authority.read_text(encoding="utf-8")
        )
        if isinstance(payload, dict):
            semantic_rows = payload.get("resolutions", [])
        elif isinstance(payload, list):
            semantic_rows = payload
    operator_rows = _load_jsonl(args.operator_ledger)
    target_custom_ids = set(args.target_custom_id)
    if args.include_unresolved_slug_targets:
        target_custom_ids.update(_unresolved_implementation_targets(operator_rows))
    if not target_custom_ids:
        parser.error("at least one custom implementation target is required")
    result = build_expansion(
        _load_jsonls(args.source_manifest),
        operator_rows,
        catalog_ids=load_catalog_ids(args.catalog),
        mapping=_load_mapping(args.mapping),
        target_custom_ids=target_custom_ids,
        implementation_bindings=binding_rows,
        semantic_operator_authority=semantic_rows,
        train_rows=_load_jsonls(args.train_authority),
    )
    write_outputs(args.output_dir, result)
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
