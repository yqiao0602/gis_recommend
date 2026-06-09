#!/usr/bin/env python3
"""Build a bounded execution-aware ontology inventory for GIS workflow planning.

This is an inventory/governance construction script only. It does not
implement semantic retrieval, train models, mutate checkpoints, add vector
search, redesign runtime retrieval, or infer autonomous semantic plans.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.bounded_ontology_inventory.v1"

SAFE_MAPPING_TYPES = {
    "direct",
    "manual_override",
    "audit_v2_override",
    "manual_tail_fix",
    "manual_25_override",
}

REQUESTED_PLATFORMS = ("gee", "qgis", "gdal", "arcgis")
SUPPORTED_MAPPING_KEYS = {"gee": "gee_to_l3", "qgis": "qgis_to_l3"}

FORBIDDEN_PATTERNS = [
    r"\bimport\s+sentence_transformers\b",
    r"\bfrom\s+sentence_transformers\b",
    r"\bimport\s+faiss\b",
    r"\bfrom\s+faiss\b",
    r"\bimport\s+openai\b",
    r"\bfrom\s+openai\b",
    r"\bopenai\.",
    r"\btransformers\.",
    r"\btorch\.",
    r"\.backward\(",
    r"optimizer\.step\(",
    r"strict\s*=\s*False",
    r"weights_only\s*=\s*False",
    r"learned[_ -]?gamma",
    r"gated[_ -]?write",
    r"graph[_ -]?loss",
    r"entropy[_ -]?regular",
]

STOP_TERMS = {
    "ee",
    "qgis",
    "gdal",
    "arcgis",
    "image",
    "images",
    "feature",
    "features",
    "featurecollection",
    "collection",
    "geometry",
    "layer",
    "layers",
    "vector",
    "vectors",
    "raster",
    "rasters",
    "grid",
    "grids",
    "table",
    "tool",
    "tools",
    "algorithm",
    "algorithms",
    "processing",
    "to",
    "from",
    "by",
    "with",
    "and",
    "or",
    "the",
    "a",
    "an",
    "of",
    "for",
    "in",
    "on",
    "at",
    "new",
}

WEAK_ACTION_TERMS = STOP_TERMS | {
    "band",
    "bands",
    "field",
    "fields",
    "data",
    "type",
    "types",
    "value",
    "values",
    "property",
    "properties",
    "information",
    "basic",
    "line",
    "lines",
    "point",
    "points",
    "classifier",
    "classifiers",
    "imagery",
}

SPECIALIZED_MODIFIER_TERMS = {
    "single",
    "sided",
    "bulk",
    "virtual",
    "random",
    "constant",
}


def classify_platform_pair(left: dict, right: dict, l3_info: dict, qgis_io_types: Optional[dict] = None) -> dict:
    """Classify one bounded platform mapping pair.

    The classification is deliberately conservative. A same-L3 mapping is not
    automatically exact; it needs safe source mappings, compatible IO, and
    direct action-term evidence. Same-L2/different-L3 pairs remain ambiguous.
    """

    left_l3 = str(left.get("primary_l3") or "")
    right_l3 = str(right.get("primary_l3") or "")
    platform_pair = _platform_pair(left.get("platform"), right.get("platform"))
    risk_flags: list[str] = []

    same_l3 = bool(left_l3 and right_l3 and left_l3 == right_l3)
    if not same_l3:
        risk_flags.append("different_l3")

    left_safe = _mapping_safe(left)
    right_safe = _mapping_safe(right)
    if not left_safe:
        risk_flags.append(f"{left.get('platform')}_mapping_not_safe")
    if not right_safe:
        risk_flags.append(f"{right.get('platform')}_mapping_not_safe")

    if _mapping_composite(left) or _mapping_composite(right):
        risk_flags.append("composite_or_multi_candidate_mapping")

    constraints = build_execution_constraints(left, right, l3_info, qgis_io_types or {})
    if not constraints["io_compatibility"]["compatible"]:
        risk_flags.append("io_uncertain_or_incompatible")

    l3_terms = _action_terms(str(l3_info.get("l3_name") or left_l3))
    l3_core_terms = _core_action_terms(str(l3_info.get("l3_name") or left_l3))
    left_terms = _action_terms(str(left.get("operator") or ""))
    right_terms = _action_terms(str(right.get("operator") or ""))
    action_evidence = bool(l3_terms and (l3_terms & left_terms) and (l3_terms & right_terms))
    exact_action_evidence = bool(l3_core_terms and (l3_core_terms & left_terms & right_terms))
    specialized_modifiers = sorted((left_terms | right_terms) & SPECIALIZED_MODIFIER_TERMS)
    if specialized_modifiers:
        risk_flags.append("specialized_operator_variant")
    if not action_evidence:
        risk_flags.append("weak_action_evidence")

    if not same_l3:
        classification = "ambiguous"
    elif _mapping_composite(left) or _mapping_composite(right):
        classification = "composite"
    elif not (left_safe and right_safe):
        classification = "ambiguous"
    elif constraints["crs_sensitivity"] or not constraints["io_compatibility"]["compatible"]:
        classification = "execution-sensitive"
    elif specialized_modifiers:
        classification = "execution-sensitive"
    elif exact_action_evidence:
        classification = "exact"
    else:
        classification = "partial"

    safe_for_equivalence = classification == "exact"
    return {
        "schema_version": f"{SCHEMA_VERSION}.mapping_row",
        "platform_pair": platform_pair,
        "left_platform": str(left.get("platform") or ""),
        "right_platform": str(right.get("platform") or ""),
        "left_operator": str(left.get("operator") or ""),
        "right_operator": str(right.get("operator") or ""),
        "left_l3_code": left_l3,
        "right_l3_code": right_l3,
        "l3_code": left_l3 if same_l3 else "",
        "l3_name": str(l3_info.get("l3_name") or ""),
        "l2_code": str(l3_info.get("l2_code") or ""),
        "l2_name": str(l3_info.get("l2_name") or ""),
        "l1_code": str(l3_info.get("l1_code") or ""),
        "l1_name": str(l3_info.get("l1_name") or ""),
        "classification": classification,
        "safe_for_equivalence_claim": bool(safe_for_equivalence),
        "risk_flags": sorted(set(risk_flags)),
        "evidence": {
            "left_mapping_type": str(left.get("mapping_type") or ""),
            "right_mapping_type": str(right.get("mapping_type") or ""),
            "left_mapping_confidence": _as_float(left.get("mapping_confidence")),
            "right_mapping_confidence": _as_float(right.get("mapping_confidence")),
            "same_l3": same_l3,
            "left_mapping_safe": left_safe,
            "right_mapping_safe": right_safe,
            "action_evidence": action_evidence,
            "exact_action_evidence": exact_action_evidence,
            "specialized_modifiers": specialized_modifiers,
            "l3_action_terms": sorted(l3_terms),
            "l3_core_action_terms": sorted(l3_core_terms),
            "left_action_terms": sorted(left_terms),
            "right_action_terms": sorted(right_terms),
            "source": "id_mappings_v2.mapping_metadata + classification_hierarchy_v2",
        },
        "execution_constraints": constraints,
        "governance": _row_governance(),
    }


def build_execution_constraints(left: dict, right: dict, l3_info: dict, qgis_io_types: dict) -> dict:
    left_domain = _operator_domain(left, l3_info, qgis_io_types)
    right_domain = _operator_domain(right, l3_info, qgis_io_types)
    shared_inputs = sorted(set(left_domain["inputs"]) & set(right_domain["inputs"]))
    shared_outputs = sorted(set(left_domain["outputs"]) & set(right_domain["outputs"]))
    compatible = bool(shared_inputs or shared_outputs)
    text = " ".join(
        [
            str(left.get("operator") or ""),
            str(right.get("operator") or ""),
            str(l3_info.get("l3_name") or ""),
            str(l3_info.get("l3_description") or ""),
            str(l3_info.get("l2_name") or ""),
            str(l3_info.get("l1_name") or ""),
        ]
    ).lower()
    return {
        "io_compatibility": {
            "compatible": compatible,
            "left_inputs": left_domain["inputs"],
            "left_outputs": left_domain["outputs"],
            "right_inputs": right_domain["inputs"],
            "right_outputs": right_domain["outputs"],
            "shared_inputs": shared_inputs,
            "shared_outputs": shared_outputs,
            "note": "Compatibility is inventory-level only; platform execution still requires parameter grounding.",
        },
        "raster_vector_constraints": {
            "left_domain": left_domain["domain"],
            "right_domain": right_domain["domain"],
            "shared_domain": sorted(set(left_domain["domain"]) & set(right_domain["domain"])),
        },
        "crs_sensitivity": _has_any(text, ["crs", "projection", "project", "reproject", "coordinate", "datum", "transform"]),
        "topology_constraints": _has_any(text, ["topology", "geometry", "overlay", "intersect", "union", "buffer", "clip", "erase", "dissolve", "spatial join"]),
        "parameter_preservation": _parameter_requirements(text),
        "bridge_requirements": _bridge_requirements(left, right),
    }


def build_platform_pair_inventory(
    mappings: dict,
    hierarchy: dict[str, dict],
    qgis_io_types: Optional[dict] = None,
    *,
    requested_platforms: Sequence[str] = REQUESTED_PLATFORMS,
) -> list[dict]:
    platform_rows = {
        platform: _operator_rows_for_platform(mappings, platform)
        for platform in requested_platforms
        if platform in SUPPORTED_MAPPING_KEYS
    }
    rows: list[dict] = []
    for left_platform, right_platform in (("gee", "qgis"), ("gee", "gdal"), ("qgis", "gdal"), ("gee", "arcgis"), ("qgis", "arcgis")):
        if left_platform not in platform_rows or right_platform not in platform_rows:
            continue
        rows.extend(
            _pair_rows_for_platforms(
                platform_rows[left_platform],
                platform_rows[right_platform],
                hierarchy,
                qgis_io_types or {},
            )
        )
    rows.extend(build_unsupported_platform_pair_rows(platform_rows.keys(), requested_platforms=requested_platforms))
    return rows


def build_unsupported_platform_pair_rows(available_platforms: Iterable[str], requested_platforms: Sequence[str] = REQUESTED_PLATFORMS) -> list[dict]:
    available = {str(platform) for platform in available_platforms}
    requested = [str(platform) for platform in requested_platforms]
    rows = []
    for left, right in (("gee", "gdal"), ("qgis", "gdal"), ("gee", "arcgis"), ("qgis", "arcgis"), ("gdal", "arcgis")):
        if left in available and right in available:
            continue
        if left not in requested or right not in requested:
            continue
        rows.append(
            {
                "schema_version": f"{SCHEMA_VERSION}.mapping_row",
                "platform_pair": _platform_pair(left, right),
                "left_platform": left,
                "right_platform": right,
                "left_operator": "",
                "right_operator": "",
                "left_l3_code": "",
                "right_l3_code": "",
                "l3_code": "",
                "l3_name": "",
                "l2_code": "",
                "l2_name": "",
                "l1_code": "",
                "l1_name": "",
                "classification": "unsupported",
                "safe_for_equivalence_claim": False,
                "source_status": "not_available_in_current_artifacts",
                "risk_flags": ["missing_platform_mapping_asset"],
                "evidence": {
                    "source": "id_mappings_v2.mapping_metadata",
                    "available_platforms": sorted(available),
                    "requested_platforms": requested,
                },
                "execution_constraints": {
                    "io_compatibility": {"compatible": False, "note": "No mapping asset available."},
                    "raster_vector_constraints": {"shared_domain": []},
                    "crs_sensitivity": False,
                    "topology_constraints": False,
                    "parameter_preservation": [],
                    "bridge_requirements": ["unsupported_platform_mapping_asset"],
                },
                "governance": _row_governance(),
            }
        )
    return rows


def build_unsafe_mapping_registry(safe_table: dict, ambiguous_pairs: Sequence[dict]) -> dict:
    unsafe_rows = []
    for row in safe_table.get("rows", []):
        decision = str(row.get("decision") or "")
        if decision in {"stable", "platform-transfer-safe"}:
            continue
        unsafe_rows.append(
            {
                "equivalence_type": str(row.get("equivalence_type") or "unknown"),
                "subtype": str(row.get("subtype") or "unknown"),
                "decision": decision,
                "reason": _unsafe_reason(row),
                "evidence_metrics": {
                    key: row.get(key)
                    for key in (
                        "n",
                        "false_equivalence_rate",
                        "execution_invalid_equivalence_rate",
                        "workflow_corruption_rate",
                        "lcs_preservation_delta",
                        "set_f1_preservation_delta",
                        "token_accuracy_delta",
                    )
                    if key in row
                },
                "governance": "must_not_be_used_as_safe_equivalence",
            }
        )
    for row in ambiguous_pairs:
        unsafe_rows.append(
            {
                "equivalence_type": "operator_mapping_pair",
                "subtype": str(row.get("classification") or "unknown"),
                "decision": str(row.get("classification") or "unknown"),
                "platform_pair": row.get("platform_pair"),
                "left_operator": row.get("left_operator"),
                "right_operator": row.get("right_operator"),
                "l3_code": row.get("l3_code") or row.get("left_l3_code"),
                "reason": ",".join(row.get("risk_flags") or []) or "not_exact",
                "governance": "inventory_warning_only",
            }
        )
    return {
        "schema_version": f"{SCHEMA_VERSION}.unsafe_mapping_registry",
        "created_at": _now(),
        "unsafe_mappings": unsafe_rows,
        "interpretation_boundary": {
            "unsafe_rows_do_not_block_runtime": True,
            "unsafe_rows_must_not_be_promoted_to_equivalence_without_new_evidence": True,
        },
    }


def build_workflow_equivalence_registry() -> dict:
    return {
        "schema_version": f"{SCHEMA_VERSION}.workflow_equivalence_registry",
        "created_at": _now(),
        "safe_equivalence_examples": [
            {
                "name": "operator_identity_sequence",
                "definition": "The same ordered L3/operator token sequence with no operator substitution, insertion, deletion, or reorder.",
                "allowed_scope": "sequence identity only",
                "execution_constraints": ["all original IO and parameters preserved"],
            },
            {
                "name": "case_only_operator_alias_sequence",
                "definition": "Operator-name display casing differs but canonical mapping key and L3 sequence are identical.",
                "allowed_scope": "operator display alias only",
                "execution_constraints": ["canonical operator and parameters unchanged"],
            },
        ],
        "unsafe_or_unproven_examples": [
            {
                "name": "adjacent_reorder",
                "decision": "unsafe",
                "evidence": "controlled_equivalence_stress found high workflow corruption for adjacent reorder variants",
            },
            {
                "name": "bridge_expansion",
                "decision": "unsafe",
                "evidence": "controlled_equivalence_stress found high workflow corruption for bridge-expanded variants",
            },
            {
                "name": "same_l2_operator_substitution",
                "decision": "execution-breaking",
                "evidence": "controlled_equivalence_stress found same-L2 substitutions are not safe equivalence",
            },
            {
                "name": "broad_semantic_bucket_equivalence",
                "decision": "unsafe",
                "evidence": "semantic_indexing_simulation showed false-equivalence risk from broad grouping",
            },
        ],
        "claim_boundary": "This registry is documentation only. It does not redefine evaluation failures or mutate selected workflows.",
    }


def build_bounded_ontology_inventory(
    *,
    mappings_path: Path,
    hierarchy_path: Path,
    qgis_io_path: Optional[Path],
    controlled_equivalence_table_path: Optional[Path],
    output_dir: Path,
    dry_run: bool = False,
) -> dict:
    mappings = _load_json(mappings_path)
    hierarchy = _load_hierarchy(hierarchy_path)
    qgis_io = _load_qgis_io(qgis_io_path)
    safe_table = _load_json(controlled_equivalence_table_path) if controlled_equivalence_table_path and controlled_equivalence_table_path.exists() else {"rows": []}
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = build_platform_pair_inventory(mappings, hierarchy, qgis_io)
    counts = Counter(str(row.get("classification") or "unknown") for row in rows)
    safe_rows = [row for row in rows if row.get("classification") == "exact" and row.get("safe_for_equivalence_claim")]
    ambiguous_pairs = [
        row
        for row in rows
        if row.get("classification") in {"ambiguous", "composite", "execution-sensitive", "partial"}
    ][:500]
    created_at = _now()

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": bool(dry_run),
        "runtime_contract": _runtime_contract(),
        "input_artifacts": {
            "mappings": str(mappings_path),
            "hierarchy": str(hierarchy_path),
            "qgis_io": str(qgis_io_path) if qgis_io_path else None,
            "controlled_equivalence_table": str(controlled_equivalence_table_path) if controlled_equivalence_table_path else None,
        },
        "summary": {
            "operator_pair_count": len(rows),
            "classification_counts": dict(sorted(counts.items())),
            "safe_exact_mapping_count": len(safe_rows),
            "supported_platform_pairs": sorted({row.get("platform_pair") for row in rows if row.get("classification") != "unsupported"}),
            "unsupported_platform_pairs": sorted({row.get("platform_pair") for row in rows if row.get("classification") == "unsupported"}),
            "claim_boundary": "Exact rows are inventory candidates only; they are not active runtime retrieval or repair rules.",
        },
        "artifact_files": {
            "operator_mapping_inventory": str(output_dir / "operator_mapping_inventory.json"),
            "mapping_classification_table": str(output_dir / "mapping_classification_table.csv"),
            "execution_constraints_inventory": str(output_dir / "execution_constraints_inventory.json"),
            "unsafe_mapping_registry": str(output_dir / "unsafe_mapping_registry.json"),
            "workflow_equivalence_registry": str(output_dir / "workflow_equivalence_registry.json"),
            "summary": str(output_dir / "bounded_ontology_summary.md"),
            "forbidden_pattern_scan": str(output_dir / "forbidden_pattern_scan_bounded_ontology.json"),
        },
    }

    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", report)
        return report

    inventory = {
        "schema_version": f"{SCHEMA_VERSION}.operator_mapping_inventory",
        "created_at": created_at,
        "rows": rows,
        "safe_exact_mappings": safe_rows,
        "classification_counts": dict(sorted(counts.items())),
        "interpretation_boundary": _interpretation_boundary(),
    }
    constraints = {
        "schema_version": f"{SCHEMA_VERSION}.execution_constraints",
        "created_at": created_at,
        "rows": [
            {
                "platform_pair": row.get("platform_pair"),
                "left_operator": row.get("left_operator"),
                "right_operator": row.get("right_operator"),
                "classification": row.get("classification"),
                "safe_for_equivalence_claim": row.get("safe_for_equivalence_claim"),
                "l3_code": row.get("l3_code"),
                "l3_name": row.get("l3_name"),
                "execution_constraints": row.get("execution_constraints"),
            }
            for row in rows
        ],
    }
    unsafe_registry = build_unsafe_mapping_registry(safe_table, ambiguous_pairs)
    workflow_registry = build_workflow_equivalence_registry()
    scan = forbidden_pattern_scan([Path("scripts") / "build_bounded_ontology_inventory.py", Path("tests") / "test_bounded_ontology_inventory.py"])

    _write_json(output_dir / "operator_mapping_inventory.json", inventory)
    _write_classification_csv(output_dir / "mapping_classification_table.csv", rows)
    _write_json(output_dir / "execution_constraints_inventory.json", constraints)
    _write_json(output_dir / "unsafe_mapping_registry.json", unsafe_registry)
    _write_json(output_dir / "workflow_equivalence_registry.json", workflow_registry)
    _write_json(output_dir / "forbidden_pattern_scan_bounded_ontology.json", scan)
    _write_markdown(output_dir / "bounded_ontology_summary.md", report, inventory, unsafe_registry, workflow_registry)
    _write_json(output_dir / "bounded_ontology_report.json", report)
    return report


def _pair_rows_for_platforms(left_rows: Sequence[dict], right_rows: Sequence[dict], hierarchy: dict[str, dict], qgis_io_types: dict) -> list[dict]:
    by_l3_right: dict[str, list[dict]] = defaultdict(list)
    for row in right_rows:
        by_l3_right[str(row.get("primary_l3") or "")].append(row)
    rows = []
    for left in left_rows:
        l3_code = str(left.get("primary_l3") or "")
        for right in by_l3_right.get(l3_code, []):
            l3_info = hierarchy.get(l3_code, {"l3_code": l3_code, "l3_name": l3_code})
            rows.append(classify_platform_pair(left, right, l3_info, qgis_io_types))
    return rows


def _operator_rows_for_platform(mappings: dict, platform: str) -> list[dict]:
    metadata = mappings.get("mapping_metadata") or {}
    platform_key = SUPPORTED_MAPPING_KEYS.get(platform)
    if not platform_key:
        return []
    rows = []
    for operator, payload in sorted((metadata.get(platform_key) or {}).items()):
        if not isinstance(payload, dict):
            continue
        rows.append(
            {
                "platform": platform,
                "operator": str(operator),
                "primary_l3": str(payload.get("primary_l3") or ""),
                "mapping_type": str(payload.get("mapping_type") or ""),
                "mapping_confidence": _as_float(payload.get("mapping_confidence")),
                "has_ambiguity": bool(payload.get("has_ambiguity")),
                "num_candidates": int(payload.get("num_candidates") or 0),
                "source": str(payload.get("source") or ""),
                "rationale": str(payload.get("rationale") or ""),
                "all_candidates": payload.get("all_candidates") or [],
            }
        )
    return rows


def _operator_domain(operator_row: dict, l3_info: dict, qgis_io_types: dict) -> dict:
    operator = str(operator_row.get("operator") or "")
    platform = str(operator_row.get("platform") or "")
    if platform == "qgis" and operator in qgis_io_types:
        payload = qgis_io_types[operator]
        inputs = _normalize_types(payload.get("inputs") or [])
        outputs = _normalize_types(payload.get("outputs") or [])
    else:
        text = " ".join([operator, str(l3_info.get("l3_name") or ""), str(l3_info.get("l3_description") or ""), str(l3_info.get("l1_name") or "")]).lower()
        domain = _infer_domain_from_text(text)
        inputs = list(domain)
        outputs = list(domain)
    domain = sorted(set(inputs) | set(outputs))
    return {"inputs": sorted(set(inputs)), "outputs": sorted(set(outputs)), "domain": domain}


def _infer_domain_from_text(text: str) -> list[str]:
    domains = set()
    if _has_any(text, ["raster", "image", "pixel", "band", "grid", "terrain", "dem", "ndvi"]):
        domains.add("raster")
    if _has_any(text, ["vector", "feature", "geometry", "point", "line", "polygon", "attribute", "field", "table"]):
        domains.add("vector")
    if _has_any(text, ["classifier", "model", "training"]):
        domains.add("model")
    if not domains:
        domains.add("unknown")
    return sorted(domains)


def _normalize_types(values: Sequence[str]) -> list[str]:
    out = []
    for value in values:
        text = str(value).lower()
        if "raster" in text or "grid" in text:
            out.append("raster")
        elif "vector" in text or "feature" in text or "table" in text:
            out.append("vector")
        elif "model" in text or "classifier" in text:
            out.append("model")
        elif text:
            out.append(text)
    return sorted(set(out)) or ["unknown"]


def _parameter_requirements(text: str) -> list[str]:
    requirements = []
    checks = [
        (["buffer"], "distance/radius"),
        (["projection", "project", "reproject", "crs", "coordinate"], "CRS definition and transform parameters"),
        (["resample", "resolution"], "target resolution and resampling method"),
        (["clip", "mask"], "clip geometry/mask and extent"),
        (["band", "select"], "selected bands/fields"),
        (["field", "attribute", "calculate"], "field names and expressions"),
        (["expression", "arithmetic", "math"], "formula and operand bands"),
        (["statistic", "statistics", "reducer", "zonal"], "statistic/reducer and zone definition"),
        (["classify", "classifier", "train"], "classifier type, features, and label field"),
        (["join", "spatial relationship"], "spatial predicate and join cardinality"),
        (["intersect", "union", "erase", "overlay"], "overlay mode and geometry handling"),
    ]
    for terms, requirement in checks:
        if _has_any(text, terms):
            requirements.append(requirement)
    return sorted(set(requirements))


def _bridge_requirements(left: dict, right: dict) -> list[str]:
    left_platform = str(left.get("platform") or "")
    right_platform = str(right.get("platform") or "")
    if not left_platform or not right_platform:
        return ["unknown_platform_bridge"]
    if left_platform == right_platform:
        return []
    return [
        "platform data export/import bridge",
        "parameter translation bridge",
        "provider-specific execution validation",
    ]


def _mapping_safe(row: dict) -> bool:
    return (
        str(row.get("mapping_type") or "") in SAFE_MAPPING_TYPES
        and not bool(row.get("has_ambiguity"))
        and int(row.get("num_candidates") or 0) == 1
        and bool(row.get("primary_l3"))
    )


def _mapping_composite(row: dict) -> bool:
    return int(row.get("num_candidates") or 0) > 1 or bool(row.get("has_ambiguity")) or str(row.get("mapping_type") or "") in {"multi_output", "composite"}


def _action_terms(text: str) -> set[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    pieces = re.findall(r"[A-Za-z0-9]+", text.lower())
    return {piece for piece in pieces if len(piece) > 1 and piece not in STOP_TERMS}


def _core_action_terms(text: str) -> set[str]:
    terms = _action_terms(text)
    core = {term for term in terms if term not in WEAK_ACTION_TERMS}
    return core or terms


def _has_any(text: str, terms: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _unsafe_reason(row: dict) -> str:
    decision = str(row.get("decision") or "")
    if decision == "execution-breaking":
        return "execution-invalid or transition-breaking equivalence stress result"
    if decision == "unsafe":
        return "false equivalence or workflow corruption observed"
    if decision == "ambiguous":
        return "insufficient evidence for execution-preserving equivalence"
    return "not safe"


def _row_governance() -> dict:
    return {
        "runtime_authority": "inventory_only",
        "semantic_retrieval_implemented": False,
        "runtime_mutation_allowed": False,
        "equivalence_claim_requires_parameter_and_execution_validation": True,
    }


def _runtime_contract() -> dict:
    return {
        "inventory_only": True,
        "evaluation_only": True,
        "training_run": False,
        "checkpoint_mutated": False,
        "embedding_learning": False,
        "vector_search_added": False,
        "semantic_retrieval_implemented": False,
        "ontology_inference_implemented": False,
        "runtime_deployment_change": False,
    }


def _interpretation_boundary() -> dict:
    return {
        "exact_rows_are_candidates_for_future_reference": True,
        "exact_rows_are_not_runtime_rules": True,
        "partial_rows_must_not_be_treated_as_equivalent": True,
        "unsupported_platforms_must_not_be_inferred": True,
        "l2_validated": False,
        "semantic_retrieval_solved": False,
        "autonomous_semantic_planning": False,
    }


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    matches = []
    for file_path in files:
        path = ROOT / file_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                matches.append({"file": str(file_path), "line": text.count("\n", 0, match.start()) + 1, "pattern": pattern, "match": match.group(0)})
    return {
        "schema_version": "gis_recommend.v5_final.forbidden_pattern_scan.v1",
        "files": [str(path) for path in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "result": "pass" if not matches else "fail",
    }


def _load_json(path: Optional[Path]) -> dict:
    if path is None:
        return {}
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_hierarchy(path: Path) -> dict[str, dict]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {str(row.get("l3_code") or ""): row for row in rows if row.get("l3_code")}


def _load_qgis_io(path: Optional[Path]) -> dict:
    if path is None or not Path(path).exists():
        return {}
    payload = _load_json(path)
    return payload.get("operators") if isinstance(payload.get("operators"), dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_classification_csv(path: Path, rows: Sequence[dict]) -> None:
    fields = [
        "platform_pair",
        "left_platform",
        "right_platform",
        "left_operator",
        "right_operator",
        "l3_code",
        "l3_name",
        "l2_code",
        "classification",
        "safe_for_equivalence_claim",
        "risk_flags",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {field: row.get(field) for field in fields}
            out["risk_flags"] = "|".join(row.get("risk_flags") or [])
            writer.writerow(out)


def _write_markdown(path: Path, report: dict, inventory: dict, unsafe_registry: dict, workflow_registry: dict) -> None:
    summary = report.get("summary", {})
    lines = [
        "# Bounded Ontology Inventory",
        "",
        "This artifact is an inventory/governance layer only. It does not implement semantic retrieval or runtime ontology inference.",
        "",
        "## Summary",
        "",
        f"- Operator pair rows: `{summary.get('operator_pair_count')}`",
        f"- Safe exact mapping rows: `{summary.get('safe_exact_mapping_count')}`",
        f"- Supported platform pairs: `{', '.join(summary.get('supported_platform_pairs') or [])}`",
        f"- Unsupported platform pairs: `{', '.join(summary.get('unsupported_platform_pairs') or [])}`",
        "",
        "## Classification Counts",
        "",
        "```json",
        json.dumps(summary.get("classification_counts") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Interpretation Boundary",
        "",
        "Exact mappings are bounded inventory candidates. They are not deployed retrieval, repair, or planning rules. Partial, ambiguous, composite, execution-sensitive, and unsupported rows must not be promoted to equivalence without new execution evidence.",
        "",
        "## Unsafe Registry Count",
        "",
        f"- Unsafe or warning rows: `{len(unsafe_registry.get('unsafe_mappings') or [])}`",
        "",
        "## Workflow Equivalence Boundary",
        "",
        "Safe examples:",
        "",
    ]
    for row in workflow_registry.get("safe_equivalence_examples", []):
        lines.append(f"- `{row.get('name')}`: {row.get('definition')}")
    lines.extend(["", "Unsafe or unproven examples:", ""])
    for row in workflow_registry.get("unsafe_or_unproven_examples", []):
        lines.append(f"- `{row.get('name')}`: {row.get('decision')} ({row.get('evidence')})")
    lines.extend(["", "## Artifact Files", "", "```json", json.dumps(report.get("artifact_files"), ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _platform_pair(left: object, right: object) -> str:
    return f"{left}<->{right}"


def _as_float(value: object) -> float:
    try:
        return round(float(value), 8)
    except (TypeError, ValueError):
        return 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mappings", type=Path, default=OUTPUT_DIR / "id_mappings_v2.json")
    parser.add_argument("--hierarchy", type=Path, default=OUTPUT_DIR / "classification_hierarchy_v2.csv")
    parser.add_argument("--qgis-io", type=Path, default=ROOT / "outputs" / "qgis_operator_io_types.json")
    parser.add_argument(
        "--controlled-equivalence-table",
        type=Path,
        default=OUTPUT_DIR / "v5_final_reports" / "controlled_equivalence_stress" / "safe_unsafe_equivalence_table.json",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "bounded_ontology_inventory")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = build_bounded_ontology_inventory(
        mappings_path=args.mappings,
        hierarchy_path=args.hierarchy,
        qgis_io_path=args.qgis_io,
        controlled_equivalence_table_path=args.controlled_equivalence_table,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
