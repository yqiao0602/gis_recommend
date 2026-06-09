#!/usr/bin/env python3
"""Validate whether quality-gate data can support multi-reference labels.

This is evaluation-only. It generates conservative adjacent-swap variants from
train-split commutative-pair candidates, applies automatic validation gates, and
exports a stratified human-review sample. It does not train, mutate checkpoints,
or claim semantic equivalence.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.evaluate_canonicalized_metrics import discover_commutative_pairs  # noqa: E402
from scripts.evaluate_workflow_usability import (  # noqa: E402
    UsabilityEvaluator,
    _content_tokens,
    _load_csv,
    _load_json,
    _load_workflows,
    _task_type,
)
from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.operators.l3_to_platform_mapper import L3ToPlatformMapper  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v4_qg.multiref_validation.v1"
DEFAULT_QG_DIR = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
DEFAULT_DATA_PATH = DEFAULT_QG_DIR / "labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS_PATH = DEFAULT_QG_DIR / "dataset_splits_v4_quality_gate.json"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_multiref_validation"
DEFAULT_HIERARCHY_PATH = OUTPUT_DIR / "classification_hierarchy_v2.csv"
DEFAULT_ID_MAPPINGS_PATH = OUTPUT_DIR / "id_mappings_v2.json"
DEFAULT_L3_VOCAB_PATH = OUTPUT_DIR / "l3_vocab_v2.json"

CRITICAL_FORBIDDEN_PREFIXES = ("FP02", "FP05", "FP09")
SENSITIVE_TERMS = (
    "crs",
    "coordinate reference",
    "projection",
    "project",
    "reproject",
    "resampling",
    "resample",
    "resolution",
    "nodata",
    "no data",
    "mask",
    "alignment",
    "align",
    "temporal",
    "time series",
    "threshold",
    "classification",
    "classifier",
    "zonal",
    "statistics",
    "aggregation",
    "aggregate",
    "export",
)


@dataclass(frozen=True)
class VariantRecord:
    workflow_index: int
    task_type: str
    task_name: str
    task_description: str
    original_tokens: list[int]
    variant_tokens: list[int]
    swap_position: int
    swapped_pair: list[int]
    variant_id: str = ""

    def to_dict(self) -> dict:
        out = asdict(self)
        if not out["variant_id"]:
            out["variant_id"] = make_variant_id(self)
        return out


@dataclass
class ValidationDecision:
    variant_id: str
    auto_label: str
    registry_eligible: bool
    passed_checks: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    landing_passed_checks: list[str] = field(default_factory=list)
    landing_rejection_reasons: list[str] = field(default_factory=list)
    original_usability: dict = field(default_factory=dict)
    variant_usability: dict = field(default_factory=dict)
    original_chain: dict = field(default_factory=dict)
    variant_chain: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _mean(values: Iterable[float]) -> float:
    vals = [float(value) for value in values]
    return round(sum(vals) / len(vals), 8) if vals else 0.0


def _parse_token_list(value: object) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [int(item) for item in parsed]
    return []


def _workflow_text(workflow: dict) -> tuple[str, str]:
    meta = workflow.get("task_metadata") or {}
    return str(meta.get("task_name", "")), str(meta.get("task_description", ""))


def make_variant_id(variant: VariantRecord) -> str:
    a, b = variant.swapped_pair
    return f"wf{variant.workflow_index}_pos{variant.swap_position}_swap{a}_{b}"


def _simple_obj_dict(obj: object) -> dict:
    if hasattr(obj, "to_dict"):
        try:
            payload = obj.to_dict()
            if isinstance(payload, dict):
                return payload
        except TypeError:
            pass
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def usability_to_dict(result: object) -> dict:
    return {
        "required_step_coverage": float(getattr(result, "required_step_coverage", 0.0)),
        "usability_score": float(getattr(result, "usability_score", 0.0)),
        "executable_qgis_mapping_rate": float(getattr(result, "executable_qgis_mapping_rate", 0.0)),
        "missing_critical_step_rate": float(getattr(result, "missing_critical_step_rate", 1.0)),
        "harmful_step_rate": float(getattr(result, "harmful_step_rate", 1.0)),
        "workflow_logic_consistency": float(getattr(result, "workflow_logic_consistency", 0.0)),
        "redundancy_rate": float(getattr(result, "redundancy_rate", 1.0)),
        "forbidden_patterns": list(getattr(result, "forbidden_patterns", []) or []),
    }


def _critical_forbidden_patterns(data: dict) -> list[str]:
    return [
        fp for fp in data["forbidden_patterns"]
        if str(fp).startswith(CRITICAL_FORBIDDEN_PREFIXES)
    ]


def semantic_usable(result: object) -> bool:
    """Workflow-level gate for MRV labels, excluding downstream QGIS landing."""
    data = usability_to_dict(result)
    return (
        not _critical_forbidden_patterns(data)
        and data["missing_critical_step_rate"] <= 0.15
        and data["harmful_step_rate"] <= 0.1
        and data["workflow_logic_consistency"] >= 0.7
        and data["redundancy_rate"] <= 0.25
    )


def strict_qgis_landing_usable(result: object) -> bool:
    """Downstream QGIS-transferability gate; auxiliary for MRV."""
    data = usability_to_dict(result)
    return (
        data["usability_score"] >= 0.75
        and not _critical_forbidden_patterns(data)
        and data["executable_qgis_mapping_rate"] >= 0.7
        and data["missing_critical_step_rate"] <= 0.15
        and data["harmful_step_rate"] <= 0.1
        and data["workflow_logic_consistency"] >= 0.7
    )


def strict_usable(result: object) -> bool:
    """Backward-compatible name for the downstream QGIS usability gate."""
    return strict_qgis_landing_usable(result)


def summarize_toolchain(chain: object) -> dict:
    payload = _simple_obj_dict(chain)
    unknown_count = int(payload.get("unknown_count", getattr(chain, "unknown_count", 0)) or 0)
    io_compatible = bool(payload.get("io_compatible", getattr(chain, "io_compatible", False)))
    confidence = float(payload.get("confidence_score", getattr(chain, "confidence_score", 0.0)) or 0.0)
    compact_steps = []
    for step in payload.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        operators = step.get("operators") or []
        top_operator = operators[0] if operators and isinstance(operators[0], dict) else {}
        compact_steps.append(
            {
                "l3_code": step.get("l3_code", ""),
                "is_unknown": bool(step.get("is_unknown", False)),
                "operator": top_operator.get("identifier") or top_operator.get("name", ""),
                "operator_name": top_operator.get("name", ""),
                "operator_confidence": top_operator.get("confidence", 0.0),
            }
        )
    return {
        "unknown_count": unknown_count,
        "io_compatible": io_compatible,
        "confidence_score": round(confidence, 8),
        "qgis_chain_usable": unknown_count == 0 and io_compatible and confidence >= 0.3,
        "steps": compact_steps,
    }


def _role_text(role: dict) -> str:
    keys = (
        "l3_code",
        "l3_name",
        "l3_description",
        "l2_code",
        "l2_name",
        "l1_code",
        "l1_name",
        "description",
    )
    return " ".join(str(role.get(key, "")) for key in keys).lower()


def is_sensitive_role(role: dict) -> bool:
    if bool(role.get("is_export")):
        return True
    text = _role_text(role)
    normalized = re.sub(r"[_\-]+", " ", text)
    return any(term in normalized for term in SENSITIVE_TERMS)


def generate_adjacent_swap_variants(
    *,
    workflow_index: int,
    workflow: dict,
    commutative_pairs: set[tuple[int, int]],
    max_variants_per_workflow: int,
) -> list[VariantRecord]:
    tokens = _content_tokens(workflow.get("l3_sequence", []))
    task_name, task_description = _workflow_text(workflow)
    variants: list[VariantRecord] = []
    seen: set[tuple[int, ...]] = set()
    for pos, (a, b) in enumerate(zip(tokens, tokens[1:])):
        pair = tuple(sorted((int(a), int(b))))
        if int(a) == int(b) or pair not in commutative_pairs:
            continue
        swapped = list(tokens)
        swapped[pos], swapped[pos + 1] = swapped[pos + 1], swapped[pos]
        key = tuple(swapped)
        if key in seen or key == tuple(tokens):
            continue
        seen.add(key)
        record = VariantRecord(
            workflow_index=int(workflow_index),
            task_type=_task_type(workflow),
            task_name=task_name,
            task_description=task_description,
            original_tokens=list(tokens),
            variant_tokens=swapped,
            swap_position=int(pos),
            swapped_pair=[int(a), int(b)],
        )
        variants.append(record)
        if len(variants) >= max(int(max_variants_per_workflow), 1):
            break
    return variants


def _passes_non_degradation(original: dict, variant: dict) -> tuple[bool, list[str]]:
    reasons = []
    if variant["harmful_step_rate"] > original["harmful_step_rate"]:
        reasons.append("harmful_step_rate_increased")
    if variant["missing_critical_step_rate"] > original["missing_critical_step_rate"]:
        reasons.append("missing_critical_step_rate_increased")
    if variant["workflow_logic_consistency"] + 1e-9 < original["workflow_logic_consistency"] - 0.05:
        reasons.append("logic_consistency_degraded")
    if variant["redundancy_rate"] > original["redundancy_rate"]:
        reasons.append("redundancy_rate_increased")
    return not reasons, reasons


def validate_variant(
    variant: VariantRecord,
    *,
    evaluator: UsabilityEvaluator,
    mapper: L3ToPlatformMapper,
) -> ValidationDecision:
    variant_id = variant.variant_id or make_variant_id(variant)
    passed: list[str] = []
    rejected: list[str] = []
    landing_passed: list[str] = []
    landing_rejected: list[str] = []

    original_eval = evaluator.evaluate(variant.original_tokens, variant.task_type)
    variant_eval = evaluator.evaluate(variant.variant_tokens, variant.task_type)
    original_usability = usability_to_dict(original_eval)
    variant_usability = usability_to_dict(variant_eval)

    swapped_roles = [evaluator._role(token) for token in variant.swapped_pair]
    if any(is_sensitive_role(role) for role in swapped_roles):
        rejected.append("sensitive_swap")
    else:
        passed.append("sensitive_guard")

    original_semantic = semantic_usable(original_eval)
    variant_semantic = semantic_usable(variant_eval)
    if original_semantic and variant_semantic:
        passed.append("semantic_usable")
    else:
        if not original_semantic:
            rejected.append("original_semantic_usable_failed")
        if not variant_semantic:
            rejected.append("variant_semantic_usable_failed")

    original_qgis_landing = strict_qgis_landing_usable(original_eval)
    variant_qgis_landing = strict_qgis_landing_usable(variant_eval)
    if original_qgis_landing and variant_qgis_landing:
        landing_passed.append("qgis_mapping_usable")
    else:
        if not original_qgis_landing:
            landing_rejected.append("original_qgis_mapping_usable_failed")
        if not variant_qgis_landing:
            landing_rejected.append("variant_qgis_mapping_usable_failed")

    original_chain = summarize_toolchain(
        mapper.map_sequence(variant.original_tokens, check_io_compatibility=True, top_k_operators=3)
    )
    variant_chain = summarize_toolchain(
        mapper.map_sequence(variant.variant_tokens, check_io_compatibility=True, top_k_operators=3)
    )
    if original_chain["qgis_chain_usable"] and variant_chain["qgis_chain_usable"]:
        landing_passed.append("qgis_chain_usable")
    else:
        landing_rejected.append("qgis_chain_unusable")

    if variant_chain["unknown_count"] <= original_chain["unknown_count"]:
        landing_passed.append("qgis_unknown_count_not_increased")
    else:
        landing_rejected.append("qgis_unknown_count_increased")

    non_degraded, non_degradation_reasons = _passes_non_degradation(original_usability, variant_usability)
    if non_degraded:
        passed.append("non_degradation")
    else:
        rejected.extend(non_degradation_reasons)

    if len(variant.variant_tokens) == len(variant.original_tokens):
        passed.append("length_preserved")
    else:
        rejected.append("length_changed")

    if not rejected:
        label = "verified_equivalent_candidate"
        eligible = True
    elif (
        "sensitive_swap" in rejected
        or "variant_semantic_usable_failed" in rejected
        or "harmful_step_rate_increased" in rejected
        or "missing_critical_step_rate_increased" in rejected
        or "logic_consistency_degraded" in rejected
        or "redundancy_rate_increased" in rejected
        or "length_changed" in rejected
    ):
        label = "invalid_variant"
        eligible = False
    elif "original_semantic_usable_failed" in rejected:
        label = "unknown"
        eligible = False
    else:
        label = "plausible_variant"
        eligible = False

    return ValidationDecision(
        variant_id=variant_id,
        auto_label=label,
        registry_eligible=eligible,
        passed_checks=passed,
        rejection_reasons=sorted(set(rejected)),
        landing_passed_checks=sorted(set(landing_passed)),
        landing_rejection_reasons=sorted(set(landing_rejected)),
        original_usability=original_usability,
        variant_usability=variant_usability,
        original_chain=original_chain,
        variant_chain=variant_chain,
    )


def _sample_bucket(rows: Sequence[dict], n: int, seed: int) -> list[dict]:
    if n <= 0:
        return []
    rng = random.Random(seed)
    bucket = list(rows)
    rng.shuffle(bucket)
    return bucket[: min(int(n), len(bucket))]


def build_human_review_sample(
    rows: Sequence[dict],
    *,
    auto_verified_n: int,
    plausible_n: int,
    rejected_n: int,
    seed: int,
) -> list[dict]:
    verified = [row for row in rows if row.get("auto_label") == "verified_equivalent_candidate"]
    plausible = [row for row in rows if row.get("auto_label") == "plausible_variant"]
    rejected = [row for row in rows if row.get("auto_label") in {"invalid_variant", "unknown"}]

    sample_rows: list[dict] = []
    for bucket_name, bucket_rows, n, offset in [
        ("auto_verified_equivalent", verified, auto_verified_n, 0),
        ("plausible_variant", plausible, plausible_n, 1),
        ("guard_rejected_control", rejected, rejected_n, 2),
    ]:
        for row in _sample_bucket(bucket_rows, n, seed + offset):
            out = dict(row)
            out["review_bucket"] = bucket_name
            out["human_label"] = ""
            out["human_notes"] = ""
            out["review_flags"] = ""
            sample_rows.append(out)
    return sample_rows


def summarize_registry_entries(rows: Sequence[dict]) -> dict:
    eligible = [row for row in rows if bool(row.get("registry_eligible"))]
    return {
        "registry_entry_count": len(eligible),
        "eligible_auto_label_counts": dict(Counter(str(row.get("auto_label")) for row in eligible)),
    }


def _token_names(
    tokens: Sequence[int],
    evaluator: UsabilityEvaluator,
    role_lookup: dict[int, dict] | None = None,
) -> list[str]:
    names = []
    for token in tokens:
        role = (role_lookup or {}).get(int(token)) or evaluator._role(int(token))
        code = str(role.get("l3_code") or token)
        name = str(role.get("l3_name") or "").strip()
        if name and name != code:
            names.append(f"{code}:{name}")
        else:
            names.append(code)
    return names


def build_hierarchy_role_lookup(
    evaluator: UsabilityEvaluator,
    hierarchy_path: Path,
) -> dict[int, dict]:
    rows = _load_csv(hierarchy_path)
    by_code = {row.get("l3_code", ""): row for row in rows}
    lookup = {}
    for token, role in getattr(evaluator, "token_roles", {}).items():
        merged = dict(role)
        source = by_code.get(merged.get("l3_code", ""))
        if source:
            for key in ("l3_name", "l3_description", "l2_name", "l1_name"):
                if source.get(key):
                    merged[key] = source[key]
        lookup[int(token)] = merged
    return lookup


def enrich_evaluator_roles(evaluator: UsabilityEvaluator, hierarchy_path: Path) -> None:
    """Attach human-readable hierarchy labels to evaluator token roles."""
    lookup = build_hierarchy_role_lookup(evaluator, hierarchy_path)
    for token, role in lookup.items():
        getattr(evaluator, "token_roles", {})[int(token)] = role


def build_equivalence_review_packet(
    rows: Sequence[dict],
    evaluator: UsabilityEvaluator,
    hierarchy_path: Path | None = None,
) -> list[dict]:
    """Build the manual review packet for auto-verified semantic candidates."""
    role_lookup = build_hierarchy_role_lookup(evaluator, hierarchy_path) if hierarchy_path is not None else None
    packet = []
    for row in rows:
        if row.get("auto_label") != "verified_equivalent_candidate" or not bool(row.get("registry_eligible")):
            continue
        original_tokens = _parse_token_list(row.get("original_tokens"))
        variant_tokens = _parse_token_list(row.get("variant_tokens"))
        swapped_pair = _parse_token_list(row.get("swapped_pair"))
        packet.append(
            {
                "variant_id": row.get("variant_id", ""),
                "task_type": row.get("task_type", ""),
                "task_family": row.get("task_family", ""),
                "task_name": row.get("task_name", ""),
                "task_description": row.get("task_description", ""),
                "swap_position": row.get("swap_position", ""),
                "swapped_pair": row.get("swapped_pair", ""),
                "swapped_pair_names": " | ".join(_token_names(swapped_pair, evaluator, role_lookup)),
                "original_tokens": row.get("original_tokens", ""),
                "original_l3_names": " | ".join(_token_names(original_tokens, evaluator, role_lookup)),
                "variant_tokens": row.get("variant_tokens", ""),
                "variant_l3_names": " | ".join(_token_names(variant_tokens, evaluator, role_lookup)),
                "auto_label": row.get("auto_label", ""),
                "passed_checks": ";".join(row.get("passed_checks") or []),
                "landing_rejection_reasons": ";".join(row.get("landing_rejection_reasons") or []),
                "human_label": "",
                "execution_semantics_notes": "",
                "hidden_semantic_drift_notes": "",
                "review_flags": "",
                "human_notes": "",
            }
        )
    return packet


def _task_key(row: dict) -> str:
    return "|".join(
        str(row.get(key, "")).strip().lower()
        for key in ("task_type", "task_name", "task_description")
    )


def build_verified_multiref_registry(review_rows: Sequence[dict]) -> dict:
    """Create a training-eligible registry from manually accepted review rows only."""
    grouped: dict[str, dict] = {}
    for row in review_rows:
        if str(row.get("human_label", "")).strip().lower() not in {"equivalent", "verified_equivalent"}:
            continue
        original_tokens = _parse_token_list(row.get("original_tokens"))
        variant_tokens = _parse_token_list(row.get("variant_tokens"))
        if not original_tokens or not variant_tokens:
            continue
        key = _task_key(row)
        if key not in grouped:
            grouped[key] = {
                "task_type": row.get("task_type", ""),
                "task_name": row.get("task_name", ""),
                "task_description": row.get("task_description", ""),
                "references": [],
                "source_variant_ids": [],
                "review_notes": [],
            }
        entry = grouped[key]
        for tokens in (original_tokens, variant_tokens):
            if tokens not in entry["references"]:
                entry["references"].append(tokens)
        entry["source_variant_ids"].append(row.get("variant_id", ""))
        if row.get("human_notes"):
            entry["review_notes"].append(row.get("human_notes", ""))

    entries = list(grouped.values())
    return {
        "schema_version": "gis_recommend.v4_qg.verified_multiref_registry.v1",
        "created_at": _now(),
        "review_policy": "manual_equivalent_only",
        "reviewed_equivalence_group_count": len(entries),
        "entries": entries,
    }


def _task_family(task_type: str) -> str:
    lowered = str(task_type).lower()
    if "vegetation" in lowered or "ndvi" in lowered:
        return "vegetation_index"
    if "clip" in lowered or "extraction" in lowered:
        return "clipping_extraction"
    if "class" in lowered or "machine" in lowered:
        return "classification"
    if "temporal" in lowered or "time" in lowered:
        return "temporal"
    if "raster" in lowered:
        return "raster_processing"
    if "vector" in lowered:
        return "vector_processing"
    return "other"


def aggregate_metrics(rows: Sequence[dict], commutative_pair_count: int) -> dict:
    labels = Counter(str(row.get("auto_label")) for row in rows)
    n = len(rows)
    return {
        "variant_generation_count": n,
        "commutative_pair_count": int(commutative_pair_count),
        "auto_label_counts": dict(labels),
        "semantic_auto_pass_rate": round(labels.get("verified_equivalent_candidate", 0) / n, 8) if n else 0.0,
        "auto_pass_rate": round(labels.get("verified_equivalent_candidate", 0) / n, 8) if n else 0.0,
        "qgis_mapping_valid_rate": _mean(
            float((row.get("variant_chain") or {}).get("qgis_chain_usable", False)) for row in rows
        ),
        "mapping_valid_rate": _mean(
            float((row.get("variant_chain") or {}).get("qgis_chain_usable", False)) for row in rows
        ),
        "qgis_io_valid_rate": _mean(
            float((row.get("variant_chain") or {}).get("io_compatible", False)) for row in rows
        ),
        "io_valid_rate": _mean(
            float((row.get("variant_chain") or {}).get("io_compatible", False)) for row in rows
        ),
        "semantic_usable_rate": _mean(
            float("semantic_usable" in (row.get("passed_checks") or [])) for row in rows
        ),
        "strict_qgis_landing_usable_rate": _mean(
            float("qgis_mapping_usable" in (row.get("landing_passed_checks") or [])) for row in rows
        ),
        "strict_usable_rate": _mean(
            float("semantic_usable" in (row.get("passed_checks") or [])) for row in rows
        ),
        "guard_pass_rate": _mean(
            float("sensitive_guard" in (row.get("passed_checks") or [])) for row in rows
        ),
        "invalid_variant_rate": round(labels.get("invalid_variant", 0) / n, 8) if n else 0.0,
        "task_family_coverage": len({str(row.get("task_family", "other")) for row in rows}),
        **summarize_registry_entries(rows),
    }


def _flatten_variant_decision(variant: VariantRecord, decision: ValidationDecision) -> dict:
    row = {
        **variant.to_dict(),
        **decision.to_dict(),
        "task_family": _task_family(variant.task_type),
    }
    row["swapped_pair"] = json.dumps(row["swapped_pair"], ensure_ascii=False)
    row["original_tokens"] = json.dumps(row["original_tokens"], ensure_ascii=False)
    row["variant_tokens"] = json.dumps(row["variant_tokens"], ensure_ascii=False)
    row["passed_checks"] = list(decision.passed_checks)
    row["rejection_reasons"] = list(decision.rejection_reasons)
    row["landing_passed_checks"] = list(decision.landing_passed_checks)
    row["landing_rejection_reasons"] = list(decision.landing_rejection_reasons)
    return row


def _review_csv_rows(rows: Sequence[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append(
            {
                "variant_id": row.get("variant_id", ""),
                "review_bucket": row.get("review_bucket", ""),
                "auto_label": row.get("auto_label", ""),
                "task_type": row.get("task_type", ""),
                "task_family": row.get("task_family", ""),
                "task_name": row.get("task_name", ""),
                "swap_position": row.get("swap_position", ""),
                "swapped_pair": row.get("swapped_pair", ""),
                "original_tokens": row.get("original_tokens", ""),
                "variant_tokens": row.get("variant_tokens", ""),
                "rejection_reasons": ";".join(row.get("rejection_reasons") or []),
                "passed_checks": ";".join(row.get("passed_checks") or []),
                "landing_rejection_reasons": ";".join(row.get("landing_rejection_reasons") or []),
                "landing_passed_checks": ";".join(row.get("landing_passed_checks") or []),
                "human_label": row.get("human_label", ""),
                "review_flags": row.get("review_flags", ""),
                "human_notes": row.get("human_notes", ""),
            }
        )
    return out


def run(
    *,
    data_path: Path,
    splits_path: Path,
    hierarchy_path: Path,
    id_mappings_path: Path,
    l3_vocab_path: Path,
    output_dir: Path,
    max_workflows: int,
    max_variants: int,
    max_variants_per_workflow: int,
    review_auto_verified: int,
    review_plausible: int,
    review_rejected: int,
    seed: int,
) -> dict:
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    train_indices = [int(index) for index in splits.get("train_indices", [])]
    if max_workflows > 0:
        train_indices = train_indices[: int(max_workflows)]
    train_workflows = [workflows[index] for index in train_indices if 0 <= index < len(workflows)]
    commutative_pairs = discover_commutative_pairs(workflows, train_indices)

    evaluator = UsabilityEvaluator(hierarchy_path, id_mappings_path, l3_vocab_path, train_workflows)
    mapper = L3ToPlatformMapper(platform="QGIS", min_confidence=0.0)

    variants: list[VariantRecord] = []
    for index in train_indices:
        if index < 0 or index >= len(workflows):
            continue
        variants.extend(
            generate_adjacent_swap_variants(
                workflow_index=index,
                workflow=workflows[index],
                commutative_pairs=commutative_pairs,
                max_variants_per_workflow=max_variants_per_workflow,
            )
        )
        if max_variants > 0 and len(variants) >= int(max_variants):
            variants = variants[: int(max_variants)]
            break

    rows = []
    for variant in variants:
        decision = validate_variant(variant, evaluator=evaluator, mapper=mapper)
        rows.append(_flatten_variant_decision(variant, decision))

    review_sample = build_human_review_sample(
        rows,
        auto_verified_n=review_auto_verified,
        plausible_n=review_plausible,
        rejected_n=review_rejected,
        seed=seed,
    )
    equivalence_review_packet = build_equivalence_review_packet(rows, evaluator, hierarchy_path)
    verified_multiref_registry = build_verified_multiref_registry(equivalence_review_packet)
    aggregate = aggregate_metrics(rows, len(commutative_pairs))
    aggregate["human_review_sample_count"] = len(review_sample)
    aggregate["human_review_sample_by_auto_label"] = dict(Counter(row.get("auto_label", "") for row in review_sample))
    aggregate["equivalence_review_packet_count"] = len(equivalence_review_packet)
    aggregate["reviewed_equivalence_group_count"] = verified_multiref_registry["reviewed_equivalence_group_count"]

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "governance": {
            "evaluation_only": True,
            "no_training": True,
            "no_checkpoint_modification": True,
            "no_runtime_planner_change": True,
            "manual_review_required_before_training": True,
            "semantic_validation_target": "GEE/workflow-level",
            "qgis_landing_auxiliary_only": True,
        },
        "inputs": {
            "data_path": str(data_path),
            "splits_path": str(splits_path),
            "hierarchy_path": str(hierarchy_path),
            "id_mappings_path": str(id_mappings_path),
            "l3_vocab_path": str(l3_vocab_path),
            "max_workflows": int(max_workflows),
            "max_variants": int(max_variants),
            "max_variants_per_workflow": int(max_variants_per_workflow),
            "seed": int(seed),
        },
        "aggregate_metrics": aggregate,
        "sensitive_terms": list(SENSITIVE_TERMS),
    }

    registry_rows = [row for row in rows if bool(row.get("registry_eligible"))]
    _write_json(output_dir / "multiref_validation_report.json", report)
    _write_jsonl(output_dir / "generated_variants.jsonl", rows)
    _write_jsonl(output_dir / "auto_verified_candidates.jsonl", registry_rows)
    _write_json(
        output_dir / "verified_equivalence_registry.json",
        {
            "schema_version": "gis_recommend.v4_qg.verified_equivalence_registry.v1",
            "created_at": _now(),
            "manual_review_status": "not_reviewed",
            "entries": registry_rows,
        },
    )
    _write_csv(
        output_dir / "human_review_sample.csv",
        _review_csv_rows(review_sample),
        [
            "variant_id",
            "review_bucket",
            "auto_label",
            "task_type",
            "task_family",
            "task_name",
            "swap_position",
            "swapped_pair",
            "original_tokens",
            "variant_tokens",
            "rejection_reasons",
            "passed_checks",
            "landing_rejection_reasons",
            "landing_passed_checks",
            "human_label",
            "review_flags",
            "human_notes",
        ],
    )
    review_packet_fields = [
        "variant_id",
        "task_type",
        "task_family",
        "task_name",
        "task_description",
        "swap_position",
        "swapped_pair",
        "swapped_pair_names",
        "original_tokens",
        "original_l3_names",
        "variant_tokens",
        "variant_l3_names",
        "auto_label",
        "passed_checks",
        "landing_rejection_reasons",
        "human_label",
        "execution_semantics_notes",
        "hidden_semantic_drift_notes",
        "review_flags",
        "human_notes",
    ]
    _write_csv(
        output_dir / "equivalence_review_packet.csv",
        equivalence_review_packet,
        review_packet_fields,
    )
    _write_json(output_dir / "verified_multi_reference_registry.json", verified_multiref_registry)
    rejection_rows = [
        {"reason": reason, "count": count}
        for reason, count in Counter(reason for row in rows for reason in (row.get("rejection_reasons") or [])).most_common()
    ]
    _write_csv(output_dir / "guard_rejection_breakdown.csv", rejection_rows, ["reason", "count"])
    landing_rejection_rows = [
        {"reason": reason, "count": count}
        for reason, count in Counter(
            reason for row in rows for reason in (row.get("landing_rejection_reasons") or [])
        ).most_common()
    ]
    _write_csv(
        output_dir / "qgis_landing_rejection_breakdown.csv",
        landing_rejection_rows,
        ["reason", "count"],
    )
    family_rows = [
        {"task_family": family, "count": count}
        for family, count in Counter(str(row.get("task_family", "other")) for row in rows).most_common()
    ]
    _write_csv(output_dir / "task_family_coverage.csv", family_rows, ["task_family", "count"])
    write_markdown_summary(output_dir / "multiref_validation_summary.md", report)
    return report


def write_markdown_summary(path: Path, report: dict) -> None:
    agg = report.get("aggregate_metrics", {})
    lines = [
        "# Multi-Reference Validation Experiment",
        "",
        "This is evaluation-only. It validates whether current quality-gate data can support reliable multi-reference supervision; it does not train a multi-reference model.",
        "",
        "## Aggregate",
        "",
        f"- Variants generated: {agg.get('variant_generation_count', 0)}",
        f"- Commutative pairs discovered: {agg.get('commutative_pair_count', 0)}",
        f"- Semantic auto pass rate: {agg.get('semantic_auto_pass_rate', 0.0):.6f}",
        f"- Semantic usable rate: {agg.get('semantic_usable_rate', 0.0):.6f}",
        f"- Guard pass rate: {agg.get('guard_pass_rate', 0.0):.6f}",
        f"- Invalid variant rate: {agg.get('invalid_variant_rate', 0.0):.6f}",
        f"- Registry eligible entries: {agg.get('registry_entry_count', 0)}",
        f"- Human review sample count: {agg.get('human_review_sample_count', 0)}",
        f"- Equivalence review packet count: {agg.get('equivalence_review_packet_count', 0)}",
        f"- Reviewed equivalence groups: {agg.get('reviewed_equivalence_group_count', 0)}",
        "",
        "## QGIS Landing Auxiliary",
        "",
        f"- QGIS mapping valid rate: {agg.get('qgis_mapping_valid_rate', 0.0):.6f}",
        f"- QGIS IO valid rate: {agg.get('qgis_io_valid_rate', 0.0):.6f}",
        f"- Strict QGIS landing usable rate: {agg.get('strict_qgis_landing_usable_rate', 0.0):.6f}",
        "",
        "## Boundary",
        "",
        "- Auto-verified candidates are not training labels until human review confirms low false-equivalence risk.",
        "- MRV labels target GEE/workflow-level semantic validity, not downstream QGIS landing.",
        "- QGIS IO compatibility and mapping success are auxiliary transferability signals, not semantic equivalence proof.",
        "- The current production strategy remains candidate-based planning plus usability-oriented evaluation.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--splits-path", type=Path, default=DEFAULT_SPLITS_PATH)
    parser.add_argument("--hierarchy", type=Path, default=DEFAULT_HIERARCHY_PATH)
    parser.add_argument("--id-mappings", type=Path, default=DEFAULT_ID_MAPPINGS_PATH)
    parser.add_argument("--l3-vocab", type=Path, default=DEFAULT_L3_VOCAB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-workflows", type=int, default=200)
    parser.add_argument("--max-variants", type=int, default=500)
    parser.add_argument("--max-variants-per-workflow", type=int, default=3)
    parser.add_argument("--review-auto-verified", type=int, default=100)
    parser.add_argument("--review-plausible", type=int, default=30)
    parser.add_argument("--review-rejected", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run(
        data_path=args.data_path,
        splits_path=args.splits_path,
        hierarchy_path=args.hierarchy,
        id_mappings_path=args.id_mappings,
        l3_vocab_path=args.l3_vocab,
        output_dir=args.output_dir,
        max_workflows=args.max_workflows,
        max_variants=args.max_variants,
        max_variants_per_workflow=args.max_variants_per_workflow,
        review_auto_verified=args.review_auto_verified,
        review_plausible=args.review_plausible,
        review_rejected=args.review_rejected,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "schema_version": report["schema_version"],
                "output_dir": str(args.output_dir),
                "aggregate_metrics": report["aggregate_metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
