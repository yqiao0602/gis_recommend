"""Evidence and governance primitives for the QGIS taxonomy pilot.

This module is intentionally independent from training and runtime defaults.
It produces sidecar manifests, evidence tables, and sampling proposals only.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PILOT_SCHEMA = "gis_recommend.qgis_pilot.v1"


class EvidenceTier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"


_ARTIFACT_PATTERN = re.compile(
    r"^(?P<script_id>.+)_(?P<kind>ast|steps|process_relations|data|edges)\.(?P<suffix>json|csv)$",
    re.IGNORECASE,
)


def classify_description_source(path: str | Path) -> str:
    path = Path(path)
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if name.startswith("facts_summary") and path.suffix.lower() == ".csv":
        return "facts_summary"
    if name == "metadata.txt":
        return "plugin_metadata"
    if name.startswith("readme"):
        return "readme"
    if "qgis_model_tutorial_metadata" in parts and path.suffix.lower() == ".json":
        return "model_tutorial_metadata"
    if "qgis_fine_eval_10" in parts and path.suffix.lower() == ".csv":
        return "fine_eval_review"
    if path.suffix.lower() == ".py":
        return "source_script"
    return "other"


def parse_qgis_artifact_path(path: str | Path, extraction_root: str | Path) -> dict[str, str] | None:
    path = Path(path)
    root = Path(extraction_root)
    match = _ARTIFACT_PATTERN.match(path.name)
    if not match:
        return None
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    return {
        "script_id": match.group("script_id"),
        "artifact_kind": match.group("kind").lower(),
        "extraction_group": relative.parts[0] if len(relative.parts) > 1 else ".",
        "source_path": str(path),
    }


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_write_allowed(path: str | Path, allowed_roots: Sequence[str | Path]) -> Path:
    """Return the resolved path or reject writes outside explicit roots."""
    resolved = Path(path).expanduser().resolve(strict=False)
    roots = [Path(root).expanduser().resolve(strict=False) for root in allowed_roots]
    if not roots:
        raise ValueError("write allowlist is empty")
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise ValueError(f"write path is outside the allowlist: {resolved}")
    return resolved


def build_authority_diff(
    profile_authority: Mapping[str, str | Path | None],
    mainline_authority: Mapping[str, str | Path | None],
) -> list[dict[str, Any]]:
    """Compare authority surfaces without silently selecting either one."""
    roles = sorted(set(profile_authority) | set(mainline_authority))
    rows = []
    for role in roles:
        profile_path = profile_authority.get(role)
        mainline_path = mainline_authority.get(role)
        profile_text = str(profile_path) if profile_path is not None else None
        mainline_text = str(mainline_path) if mainline_path is not None else None
        rows.append(
            {
                "role": role,
                "profile_path": profile_text,
                "mainline_path": mainline_text,
                "matches": profile_text == mainline_text,
                "decision": "matched" if profile_text == mainline_text else "requires_review",
            }
        )
    return rows


def build_artifact_manifest(
    artifacts: Mapping[str, str | Path],
    *,
    authority_name: str,
    git_revision: str | None = None,
) -> dict[str, Any]:
    rows = []
    for role, raw_path in sorted(artifacts.items()):
        path = Path(raw_path).expanduser().resolve(strict=False)
        exists = path.is_file()
        stat = path.stat() if exists else None
        rows.append(
            {
                "role": role,
                "path": str(path),
                "exists": exists,
                "size": stat.st_size if stat else None,
                "mtime_ns": stat.st_mtime_ns if stat else None,
                "sha256": file_sha256(path) if exists else None,
            }
        )
    return {
        "schema": PILOT_SCHEMA,
        "kind": "stable94_artifact_manifest",
        "authority_name": authority_name,
        "git_revision": git_revision,
        "artifacts": rows,
        "complete": all(row["exists"] for row in rows),
    }


def verify_artifact_manifest(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for artifact in manifest.get("artifacts", []):
        role = artifact.get("role", "unknown")
        path = Path(str(artifact.get("path", "")))
        if not path.is_file():
            errors.append(f"missing:{role}:{path}")
            continue
        expected = artifact.get("sha256")
        actual = file_sha256(path)
        if expected != actual:
            errors.append(f"sha256_mismatch:{role}:{path}")
    return errors


def _identity_key(artifact: Mapping[str, Any]) -> tuple[str, str]:
    raw_hash = str(artifact.get("raw_sha256") or "")
    normalized_hash = str(
        artifact.get("normalized_steps_sha256")
        or artifact.get("normalized_ast_sha256")
        or ""
    )
    return raw_hash, normalized_hash


def _basename(record: Mapping[str, Any]) -> str:
    value = str(record.get("source_script") or record.get("source_path") or "")
    return Path(value).name


def resolve_provenance_clusters(
    facts: Iterable[Mapping[str, Any]],
    artifacts: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve basename candidates with content identity and fail closed."""
    by_basename: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for artifact in artifacts:
        by_basename[_basename(artifact)].append(artifact)

    resolved = []
    for fact in facts:
        facts_row_id = str(fact.get("facts_row_id") or fact.get("id") or "")
        candidates = by_basename.get(_basename(fact), [])
        identities = {_identity_key(candidate) for candidate in candidates}
        aliases = sorted({str(candidate.get("source_path") or "") for candidate in candidates})

        if not candidates:
            collision_state = "missing_artifact"
            canonical_source = None
            join_reason = "no_basename_candidate"
            tier = EvidenceTier.T1 if fact.get("task_text") else EvidenceTier.T0
        elif len(identities) == 1 and all(any(value for value in identity) for identity in identities):
            collision_state = "equivalent_mirrors" if len(candidates) > 1 else "resolved"
            canonical_source = aliases[0]
            join_reason = "content_identity"
            tier = EvidenceTier.T2
        elif len(candidates) == 1:
            collision_state = "resolved"
            canonical_source = aliases[0]
            join_reason = "unique_basename_with_record_hashes"
            tier = EvidenceTier.T2 if any(_identity_key(candidates[0])) else EvidenceTier.T1
        else:
            collision_state = "unresolved_collision"
            canonical_source = None
            join_reason = "basename_candidates_have_conflicting_content"
            tier = EvidenceTier.T0

        cluster_material = json.dumps(
            {"facts_row_id": facts_row_id, "aliases": aliases, "identities": sorted(identities)},
            sort_keys=True,
        ).encode("utf-8")
        cluster_id = hashlib.sha256(cluster_material).hexdigest()[:24]
        resolved.append(
            {
                "schema": PILOT_SCHEMA,
                "provenance_cluster_id": cluster_id,
                "facts_row_id": facts_row_id,
                "facts_hash": fact.get("facts_hash"),
                "source_aliases": aliases,
                "canonical_source": canonical_source,
                "collision_state": collision_state,
                "join_reason": join_reason,
                "content_identities": [
                    {"raw_sha256": raw, "normalized_sha256": normalized}
                    for raw, normalized in sorted(identities)
                ],
                "evidence_tier": tier.value,
            }
        )
    return resolved


def _parse_statement_index(value: Any) -> tuple[int, bool]:
    try:
        return int(value), True
    except (TypeError, ValueError):
        return 2**63 - 1, False


def _evidence_channel(row: Mapping[str, Any]) -> str:
    source_type = str(row.get("api_source_type") or "").lower()
    operation = str(row.get("normalized_api_name") or row.get("operation") or "")
    if source_type == "qgis_processing_algorithm":
        return "processing_algorithms"
    if source_type in {"custom_processing_algorithm", "qgis_custom_algorithm"}:
        return "custom_algorithms"
    if source_type in {"qgis_api", "gdal_api", "qgis_cpp_api", "direct_api"}:
        return "direct_api"
    if operation.lower().startswith(("native:", "qgis:", "gdal:", "saga:")):
        return "processing_algorithms"
    return "unresolved_fragments"


def build_ordered_evidence(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Preserve ordered evidence and keep deterministic/inferred channels apart."""
    steps = []
    degraded = False
    for ordinal, row in enumerate(rows):
        statement_index, valid_index = _parse_statement_index(row.get("statement_index"))
        degraded = degraded or not valid_index
        step = {
            "step_id": str(row.get("id") or row.get("step_id") or ordinal),
            "statement_index": statement_index if valid_index else None,
            "scope": row.get("scope"),
            "nesting_depth": row.get("nesting_depth"),
            "relation": row.get("relation") or row.get("process_relation"),
            "operation": str(row.get("normalized_api_name") or row.get("operation") or ""),
            "api_source_type": row.get("api_source_type"),
            "channel": _evidence_channel(row),
            "_sort_index": statement_index,
            "_ordinal": ordinal,
        }
        steps.append(step)

    steps.sort(key=lambda step: (step["_sort_index"], step["step_id"], step["_ordinal"]))
    result: dict[str, Any] = {
        "schema": PILOT_SCHEMA,
        "ordering_confidence": "degraded" if degraded else "deterministic",
        "ordered_steps": [],
        "processing_algorithms": [],
        "direct_api": [],
        "custom_algorithms": [],
        "unresolved_fragments": [],
    }
    for step in steps:
        clean = {key: value for key, value in step.items() if not key.startswith("_")}
        result["ordered_steps"].append(clean)
        result[clean["channel"]].append(clean)
    return result


def normalize_qgis_operation(operation: Any) -> str:
    normalized = str(operation or "").strip().lower()
    while normalized.startswith("processing.run:"):
        normalized = normalized[len("processing.run:") :]
    return normalized


def map_ordered_evidence_to_taxonomy(
    evidence: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    """Map exact QGIS aliases while preserving every ordered source step."""
    aliases = {
        normalize_qgis_operation(alias): code
        for alias, code in taxonomy.get("alias_to_code", {}).items()
    }
    code_to_id = taxonomy.get("code_to_token_id", {})
    mapped_steps = []
    mapped_chain = []
    unmapped = []
    for step in evidence.get("ordered_steps", []):
        mapped = dict(step)
        operation = normalize_qgis_operation(step.get("operation"))
        code = aliases.get(operation)
        if code is not None:
            mapped.update(
                {
                    "normalized_operation": operation,
                    "mapping_status": "exact_alias",
                    "l3_code": code,
                    "l3_token_id": code_to_id[code],
                }
            )
            mapped_chain.append(code)
        else:
            mapped.update(
                {
                    "normalized_operation": operation,
                    "mapping_status": "unmapped",
                    "l3_code": None,
                    "l3_token_id": None,
                }
            )
            unmapped.append(mapped)
        mapped_steps.append(mapped)

    has_steps = bool(mapped_steps)
    completeness = (
        "complete_exact"
        if has_steps and not unmapped
        else "partial_exact"
        if mapped_chain
        else "unmapped"
    )
    return {
        **evidence,
        "taxonomy_profile": taxonomy.get("profile"),
        "ordered_steps": mapped_steps,
        "mapped_l3_chain": mapped_chain,
        "mapped_l3_token_ids": [code_to_id[code] for code in mapped_chain],
        "unmapped_steps": unmapped,
        "chain_completeness": completeness,
        "exact_mapped_step_count": len(mapped_chain),
        "unmapped_step_count": len(unmapped),
    }


_INFRASTRUCTURE_API_PATTERNS = (
    "qgsprocessingalgorithm.addparameter",
    "qgsprocessingparameter",
    "qgsprocessingalgorithm.parameteras",
    "qgsproject.instance",
    "qgsproject.addmaplayer",
    "qgsmessagelog",
    "qgsprocessingfeedback",
    "qgsprocessingexception",
    "self.tr",
)

_SEMANTIC_API_FAMILIES = (
    (("qgsgeometry.buffer",), "buffer"),
    (("qgsgeometry.intersection",), "intersection"),
    (("qgsgeometry.difference",), "difference"),
    (("qgsgeometry.combine", "qgsgeometry.unaryunion"), "union"),
    (("qgsgeometry.simplify",), "simplify"),
    (("qgsgeometry.makevalid", "qgsgeometry.isgeosvalid"), "geometry_validation"),
    (("qgscoordinatetransform", "qgsgeometry.transform"), "crs_transform"),
    (("qgsspatialindex",), "spatial_index"),
    (("qgsrastercalculator",), "raster_calculation"),
    (("qgsvectorfilewriter", "writeasvectorformat"), "vector_export"),
)

_DATA_ACCESS_API_PATTERNS = (
    "qgsvectorlayer",
    "qgsrasterlayer",
    "qgsfeature",
    "qgsfield",
    "qgsmaplayer.dataprovider",
    "getfeatures",
    "setgeometry",
    "setattributes",
    "changeattributevalue",
)


def classify_qgis_api_call(step: Mapping[str, Any]) -> dict[str, Any]:
    operation = normalize_qgis_operation(
        step.get("normalized_operation") or step.get("operation")
    )
    channel = str(step.get("channel") or "")
    mapping_status = str(step.get("mapping_status") or "")
    if mapping_status == "exact_alias" or channel in {
        "processing_algorithms",
        "custom_algorithms",
    } or operation.startswith(("native:", "qgis:", "gdal:", "grass7:", "saga:")):
        return {
            "operation": operation,
            "category": "processing_operator",
            "semantic_family": step.get("l3_code") or "explicit_processing",
        }
    if any(pattern in operation for pattern in _INFRASTRUCTURE_API_PATTERNS):
        return {"operation": operation, "category": "infrastructure", "semantic_family": None}
    for patterns, family in _SEMANTIC_API_FAMILIES:
        if any(pattern in operation for pattern in patterns):
            return {"operation": operation, "category": "semantic_anchor", "semantic_family": family}
    if any(pattern in operation for pattern in _DATA_ACCESS_API_PATTERNS):
        return {"operation": operation, "category": "data_access", "semantic_family": None}
    return {"operation": operation, "category": "unknown", "semantic_family": None}


def repair_evidence_order(steps: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(step) for step in steps]
    parsed = []
    for ordinal, row in enumerate(rows):
        try:
            statement_index = int(row.get("statement_index"))
            valid = True
        except (TypeError, ValueError):
            statement_index = None
            valid = False
        parsed.append((row, ordinal, statement_index, valid))
    if parsed and all(valid for _row, _ordinal, _index, valid in parsed):
        parsed.sort(key=lambda item: (item[2], str(item[0].get("step_id") or ""), item[1]))
        quality = "deterministic_statement_index"
    elif any(valid for _row, _ordinal, _index, valid in parsed):
        quality = "mixed_fallback_order"
    else:
        quality = "fallback_extraction_order"
    ordered = []
    for evidence_order, (row, _ordinal, statement_index, valid) in enumerate(parsed):
        row["statement_index"] = statement_index
        row["evidence_order"] = evidence_order
        row["ordering_source"] = "statement_index" if valid else "extraction_order"
        ordered.append(row)
    return {"ordering_quality": quality, "ordered_steps": ordered}


def compact_api_trace(
    steps: Iterable[Mapping[str, Any]],
    *,
    max_processing_steps: int = 80,
    max_semantic_steps: int = 80,
    max_data_access_steps: int = 40,
    max_unknown_steps: int = 20,
) -> dict[str, Any]:
    repaired = repair_evidence_order(steps)
    infrastructure = Counter()
    category_counts = Counter()
    runs: list[dict[str, Any]] = []
    for step in repaired["ordered_steps"]:
        classification = classify_qgis_api_call(step)
        operation = classification["operation"]
        category = classification["category"]
        category_counts[category] += 1
        if category == "infrastructure":
            infrastructure[operation] += 1
            continue
        evidence_id = str(step.get("step_id") or step["evidence_order"])
        key = (operation, category, classification["semantic_family"])
        if runs and runs[-1]["_key"] == key:
            runs[-1]["run_count"] += 1
            runs[-1]["evidence_ids"].append(evidence_id)
            continue
        runs.append(
            {
                "_key": key,
                "operation": operation,
                "category": category,
                "semantic_family": classification["semantic_family"],
                "run_count": 1,
                "evidence_ids": [evidence_id],
                "first_evidence_order": step["evidence_order"],
                "statement_index": step.get("statement_index"),
                "ordering_source": step["ordering_source"],
                "l3_code": step.get("l3_code"),
            }
        )
    limits = {
        "processing_operator": max_processing_steps,
        "semantic_anchor": max_semantic_steps,
        "data_access": max_data_access_steps,
        "unknown": max_unknown_steps,
    }
    retained_counts = Counter()
    omitted_counts = Counter()
    compact_steps = []
    for run in runs:
        category = run["category"]
        if retained_counts[category] >= limits[category]:
            omitted_counts[category] += run["run_count"]
            continue
        retained_counts[category] += 1
        compact_steps.append({key: value for key, value in run.items() if key != "_key"})
    families = sorted(
        {
            step["semantic_family"]
            for step in compact_steps
            if step["category"] == "semantic_anchor" and step["semantic_family"]
        }
    )
    eligible = any(
        step["category"] in {"processing_operator", "semantic_anchor"}
        for step in compact_steps
    )
    return {
        "ordering_quality": repaired["ordering_quality"],
        "source_step_count": len(repaired["ordered_steps"]),
        "compact_steps": compact_steps,
        "infrastructure_counts": dict(sorted(infrastructure.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "omitted_counts": dict(sorted(omitted_counts.items())),
        "semantic_anchor_families": families,
        "eligible_for_llm": eligible,
    }


def coverage_diagnostic_stratum(record: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(record.get("extraction_group") or "unknown"),
        str(record.get("evidence_source_mode") or "unknown"),
        str(record.get("modality_hint") or "unknown"),
        str(record.get("trace_length_bucket") or "unknown"),
        str(record.get("primary_semantic_family") or "unknown"),
        str(record.get("ordering_quality") or "unknown"),
    )


def build_coverage_diagnostic_sample(
    records: Iterable[Mapping[str, Any]],
    *,
    size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if size < 0:
        raise ValueError("sample size must be non-negative")
    strata: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for raw_record in records:
        record = dict(raw_record)
        if record.get("evidence_tier") not in {"T2", "T3", "T4"}:
            continue
        if record.get("eligible_for_llm") is not True:
            continue
        key = coverage_diagnostic_stratum(record)
        strata[key].append(record)
    queues: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for key, values in sorted(strata.items()):
        queue = sorted(values, key=lambda row: str(row.get("record_id") or ""))
        key_seed = int.from_bytes(hashlib.sha256(repr(key).encode("utf-8")).digest()[:8], "big")
        random.Random(seed ^ key_seed).shuffle(queue)
        queues[key] = queue
    selected = []
    active = list(sorted(queues))
    while active and len(selected) < size:
        next_active = []
        for key in active:
            queue = queues[key]
            if queue and len(selected) < size:
                row = dict(queue.pop())
                row["subset_type"] = "coverage_diagnostic"
                selected.append(row)
            if queue:
                next_active.append(key)
        active = next_active
    return selected


def assign_evidence_tier(record: Mapping[str, Any]) -> EvidenceTier:
    if record.get("collision_state") in {"unresolved_collision", "missing_artifact"}:
        return EvidenceTier.T0
    if record.get("adjudication_state") == "adjudicated" and record.get("reference_complete"):
        return EvidenceTier.T4
    if record.get("deterministic_evidence"):
        return EvidenceTier.T3
    if record.get("canonical_source") and record.get("content_identities"):
        return EvidenceTier.T2
    if record.get("task_text"):
        return EvidenceTier.T1
    return EvidenceTier.T0


def _stable_shuffle(records: Sequence[Mapping[str, Any]], seed: int) -> list[Mapping[str, Any]]:
    ordered = sorted(records, key=lambda row: str(row.get("provenance_cluster_id") or ""))
    random.Random(seed).shuffle(ordered)
    return ordered


def _balanced_select(
    records: Sequence[Mapping[str, Any]],
    size: int,
    *,
    seed: int,
) -> list[dict[str, Any]]:
    strata: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        key = (
            str(record.get("evidence_source") or "unknown"),
            str(record.get("modality") or "unknown"),
            str(record.get("operation_family") or "unknown"),
        )
        strata[key].append(record)
    queues = {
        key: _stable_shuffle(values, seed + index + 1)
        for index, (key, values) in enumerate(sorted(strata.items()))
    }
    selected: list[dict[str, Any]] = []
    keys = list(sorted(queues))
    while len(selected) < size and keys:
        next_keys = []
        for key in keys:
            queue = queues[key]
            if queue and len(selected) < size:
                selected.append(dict(queue.pop()))
            if queue:
                next_keys.append(key)
        keys = next_keys
    return selected


def build_sampling_proposal(
    records: Iterable[Mapping[str, Any]],
    *,
    reference_size: int,
    diagnostic_size: int,
    seed: int,
) -> dict[str, Any]:
    if reference_size < 0 or diagnostic_size < 0:
        raise ValueError("subset sizes must be non-negative")
    rows = [dict(record) for record in records]
    collisions = sorted(
        [row for row in rows if row.get("collision_state") == "unresolved_collision"],
        key=lambda row: str(row.get("provenance_cluster_id") or ""),
    )
    eligible = [row for row in rows if row not in collisions]
    reference_pool = [row for row in eligible if row.get("evidence_tier") == EvidenceTier.T4.value]
    reference = _balanced_select(reference_pool, reference_size, seed=seed)
    reference_ids = {row.get("provenance_cluster_id") for row in reference}
    diagnostic_pool = [
        row
        for row in eligible
        if row.get("evidence_tier") in {EvidenceTier.T2.value, EvidenceTier.T3.value, EvidenceTier.T4.value}
        and row.get("provenance_cluster_id") not in reference_ids
    ]
    diagnostic = _balanced_select(diagnostic_pool, diagnostic_size, seed=seed + 100_003)
    return {
        "schema": PILOT_SCHEMA,
        "kind": "phase4_sampling_proposal",
        "seed": seed,
        "requested_sizes": {
            "estimation_reference_subset": reference_size,
            "coverage_diagnostic_subset": diagnostic_size,
        },
        "estimation_reference_subset": reference,
        "coverage_diagnostic_subset": diagnostic,
        "collision_diagnostic_subset": collisions,
        "shortfalls": {
            "estimation_reference_subset": max(0, reference_size - len(reference)),
            "coverage_diagnostic_subset": max(0, diagnostic_size - len(diagnostic)),
        },
        "metric_policy": "subsets_must_not_be_merged",
    }
