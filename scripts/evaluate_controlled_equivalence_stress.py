#!/usr/bin/env python3
"""Controlled equivalence stress evaluation for retrieval-centered planning.

This script is evaluation-only. It does not implement semantic retrieval,
train models, mutate checkpoints, add vector search, or replace runtime
retrieval. It tests predefined equivalence stress variants against retrieved
workflow anchors and reports safety, corruption, and platform-transfer risk.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.evaluation import empirical as empirical_eval  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.controlled_equivalence_stress.v1"

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

SAFE_MAPPING_TYPES = {
    "direct",
    "manual_override",
    "audit_v2_override",
    "manual_tail_fix",
    "manual_25_override",
}


@dataclass(frozen=True)
class RetrievalItem:
    index: int
    task_type: str
    terms: frozenset[str]
    seq: tuple[int, ...]


def build_equivalence_taxonomy(mappings: dict) -> dict:
    """Build evaluation-local equivalence classes from existing mapping metadata."""

    l3_to_token = {str(code): int(token) for code, token in (mappings.get("l3") or {}).items()}
    token_to_l3_code = {int(token): str(code) for code, token in l3_to_token.items()}
    metadata = mappings.get("mapping_metadata") or {}
    grouped: dict[str, dict] = defaultdict(lambda: {"gee": [], "qgis": []})
    for platform_key, platform_name in (("gee_to_l3", "gee"), ("qgis_to_l3", "qgis")):
        for operator_name, payload in (metadata.get(platform_key) or {}).items():
            l3_code = str(payload.get("primary_l3") or "")
            if l3_code not in l3_to_token:
                continue
            grouped[l3_code][platform_name].append(_mapping_operator_row(operator_name, platform_name, payload))

    alias_classes = []
    cross_platform_classes = []
    for l3_code, by_platform in sorted(grouped.items()):
        operators = [*by_platform.get("gee", []), *by_platform.get("qgis", [])]
        if len(operators) >= 2:
            alias_classes.append(
                {
                    "l3_code": l3_code,
                    "token_id": l3_to_token[l3_code],
                    "operator_count": len(operators),
                    "platforms": sorted({row["platform"] for row in operators}),
                    "safe_operator_count": sum(1 for row in operators if row["mapping_safe"]),
                    "ambiguous_operator_count": sum(1 for row in operators if not row["mapping_safe"]),
                    "operators": operators[:20],
                }
            )
        if by_platform.get("gee") and by_platform.get("qgis"):
            safe = any(row["mapping_safe"] for row in by_platform["gee"]) and any(row["mapping_safe"] for row in by_platform["qgis"])
            composite = any(row["composite_or_ambiguous"] for row in operators)
            cross_platform_classes.append(
                {
                    "l3_code": l3_code,
                    "token_id": l3_to_token[l3_code],
                    "gee_operator_count": len(by_platform["gee"]),
                    "qgis_operator_count": len(by_platform["qgis"]),
                    "platform_transfer_safe": bool(safe and not composite),
                    "composite_or_ambiguous": bool(composite),
                    "operators": operators[:20],
                }
            )

    family_to_tokens: dict[str, list[int]] = defaultdict(list)
    for token, l3_code in token_to_l3_code.items():
        family_to_tokens[_l2_family(l3_code)].append(int(token))
    operator_family_classes = [
        {
            "family": family,
            "tokens": sorted(tokens),
            "token_count": len(tokens),
            "claim_boundary": "Same L2 family is not exact equivalence; it is a stress class for similar-intent/different-semantics substitutions.",
        }
        for family, tokens in sorted(family_to_tokens.items())
        if len(tokens) >= 2
    ]
    return {
        "schema_version": f"{SCHEMA_VERSION}.taxonomy",
        "alias_equivalence": {"classes": alias_classes},
        "operator_family_equivalence": {"classes": operator_family_classes},
        "workflow_equivalence": {
            "classes": [
                {"name": "adjacent_reorder", "claim_boundary": "Execution-valid adjacent swaps are only a proxy for reorder equivalence."},
                {"name": "bridge_expansion", "claim_boundary": "Bridge insertion can preserve transitions while still changing reference metrics."},
                {"name": "parameter_preserving_substitution", "claim_boundary": "At L3 token level this is represented by unchanged exact-alias tokens only."},
            ]
        },
        "cross_platform_mapping": {"classes": cross_platform_classes},
        "token_to_l3_code": token_to_l3_code,
        "family_to_tokens": {family: sorted(tokens) for family, tokens in family_to_tokens.items()},
    }


def build_operator_family_variant(
    *,
    base_tokens: Sequence[int],
    token_to_l3_code: dict[int, str],
    family_to_tokens: dict[str, Sequence[int]],
) -> Optional[dict]:
    for pos, token in enumerate([int(value) for value in base_tokens]):
        l3_code = token_to_l3_code.get(token)
        if not l3_code:
            continue
        family = _l2_family(l3_code)
        alternatives = [int(value) for value in family_to_tokens.get(family, []) if int(value) != token]
        if not alternatives:
            continue
        replacement = sorted(alternatives)[0]
        tokens = [int(value) for value in base_tokens]
        tokens[pos] = replacement
        return {
            "equivalence_type": "operator_family_equivalence",
            "subtype": "same_l2_family_substitution",
            "tokens": tokens,
            "position": pos,
            "source_token": token,
            "replacement_token": replacement,
            "family": family,
            "claimed_exact_equivalence": False,
            "platform_transfer_safe": False,
        }
    return None


def classify_equivalence_outcome(
    *,
    lcs_delta: float,
    set_f1_delta: float,
    token_accuracy_delta: float,
    retrieval_preservation: float,
    execution_invalid: bool,
    false_equivalence: bool,
    platform_transfer_safe: bool,
) -> str:
    if execution_invalid:
        return "execution-breaking"
    if platform_transfer_safe and not false_equivalence and lcs_delta >= 0.0 and set_f1_delta >= 0.0 and token_accuracy_delta >= 0.0:
        return "platform-transfer-safe"
    if false_equivalence or lcs_delta < -0.05 or set_f1_delta < -0.05 or token_accuracy_delta < -0.05:
        return "unsafe"
    if retrieval_preservation >= 0.95 and lcs_delta >= -0.01 and set_f1_delta >= -0.01:
        return "stable"
    return "ambiguous"


def summarize_equivalence_rows(rows: Sequence[dict]) -> dict:
    rows = list(rows)
    by_type = {}
    for eq_type in sorted({str(row.get("equivalence_type") or "unknown") for row in rows}):
        by_type[eq_type] = _summary_block([row for row in rows if str(row.get("equivalence_type") or "unknown") == eq_type])
    by_outcome = Counter(str(row.get("outcome") or "unknown") for row in rows)
    return {
        "equivalence_count": len(rows),
        "overall": _summary_block(rows),
        "by_equivalence_type": by_type,
        "outcome_counts": dict(sorted(by_outcome.items())),
        "interpretation_boundary": _interpretation_boundary(),
    }


def evaluate_controlled_equivalence_stress(
    *,
    data_path: Path,
    splits_path: Path,
    mappings_path: Path,
    transition_matrix_path: Optional[Path],
    output_dir: Path,
    eval_samples: int,
    retrieval_top_k: int,
    trace_top_n: int,
    dry_run: bool = False,
) -> dict:
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    mappings = _load_json(mappings_path)
    taxonomy = build_equivalence_taxonomy(mappings)
    train_indices = _validated_indices(splits.get("train_indices", []), len(workflows))
    test_indices = _validated_indices(splits.get("test_indices", []), len(workflows))
    selected_test_indices = test_indices[: max(int(eval_samples), 0)]
    output_dir.mkdir(parents=True, exist_ok=True)

    dry_summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "dry_run": True,
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "mappings_path": str(mappings_path),
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "selected_eval_samples": len(selected_test_indices),
        "runtime_contract": _runtime_contract(),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    train_items = _build_retrieval_items(workflows, train_indices)
    retrieval_index = _build_lexical_index(train_items)
    transition_allowed = _load_transition_allowed(transition_matrix_path)
    token_to_l3_code = {int(k): v for k, v in (taxonomy.get("token_to_l3_code") or {}).items()}
    family_to_tokens = {str(k): [int(value) for value in values] for k, values in (taxonomy.get("family_to_tokens") or {}).items()}
    alias_safe_tokens = {int(row["token_id"]) for row in taxonomy["alias_equivalence"]["classes"] if row.get("ambiguous_operator_count", 0) == 0}
    cross_safe_tokens = {int(row["token_id"]) for row in taxonomy["cross_platform_mapping"]["classes"] if row.get("platform_transfer_safe")}
    cross_ambiguous_tokens = {int(row["token_id"]) for row in taxonomy["cross_platform_mapping"]["classes"] if row.get("composite_or_ambiguous") or not row.get("platform_transfer_safe")}

    rows: list[dict] = []
    corruption_traces: list[dict] = []
    for local_index, test_index in enumerate(selected_test_indices):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        retrieval_pool = rank_lexical(_raw_task_text(workflow), sample.get("task_type") or "Unknown", train_items, retrieval_index, top_k=retrieval_top_k)
        if not retrieval_pool:
            continue
        source = retrieval_pool[0]
        source_tokens = [int(token) for token in source.get("tokens", [])]
        variants = build_equivalence_variants(
            source_tokens=source_tokens,
            alias_safe_tokens=alias_safe_tokens,
            cross_safe_tokens=cross_safe_tokens,
            cross_ambiguous_tokens=cross_ambiguous_tokens,
            token_to_l3_code=token_to_l3_code,
            family_to_tokens=family_to_tokens,
            transition_allowed_next=transition_allowed,
        )
        for variant in variants:
            row = evaluate_variant(
                variant=variant,
                source_tokens=source_tokens,
                reference_tokens=reference,
                retrieval_pool=retrieval_pool,
                transition_allowed_next=transition_allowed,
            )
            row.update(
                {
                    "sample_id": local_index,
                    "source_test_index": int(test_index),
                    "task_type": sample.get("task_type"),
                    "source_train_index": source.get("train_index"),
                    "source_retrieval_score": source.get("score"),
                }
            )
            rows.append(row)
            if row["workflow_corruption"] or row["execution_invalid_equivalence"] or row["false_equivalence"]:
                trace = dict(row)
                trace["retrieval_pool_top"] = [_candidate_trace(candidate) for candidate in retrieval_pool[: int(trace_top_n)]]
                corruption_traces.append(trace)

    created_at = _now()
    summary = summarize_equivalence_rows(rows)
    safe_table = build_safe_unsafe_table(rows)
    scan = forbidden_pattern_scan([Path(__file__).relative_to(ROOT), Path("tests") / "test_controlled_equivalence_stress.py"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "mappings_path": str(mappings_path),
        "transition_matrix_path": str(transition_matrix_path) if transition_matrix_path else None,
        "eval_samples": len(selected_test_indices),
        "retrieval_top_k": int(retrieval_top_k),
        "equivalence_variant_count": len(rows),
        "metrics": summary,
        "runtime_contract": _runtime_contract(),
        "artifact_files": {
            "report": str(output_dir / "controlled_equivalence_stress_report.json"),
            "taxonomy": str(output_dir / "equivalence_taxonomy.json"),
            "safe_unsafe_table_json": str(output_dir / "safe_unsafe_equivalence_table.json"),
            "safe_unsafe_table_csv": str(output_dir / "safe_unsafe_equivalence_table.csv"),
            "corruption_traces": str(output_dir / "corruption_traces.json"),
            "summary": str(output_dir / "controlled_equivalence_stress_summary.md"),
            "forbidden_pattern_scan": str(output_dir / "forbidden_pattern_scan_controlled_equivalence.json"),
        },
    }
    _write_json(output_dir / "controlled_equivalence_stress_report.json", report)
    _write_json(output_dir / "equivalence_taxonomy.json", taxonomy)
    _write_json(output_dir / "safe_unsafe_equivalence_table.json", safe_table)
    _write_json(output_dir / "corruption_traces.json", {"schema_version": f"{SCHEMA_VERSION}.corruption_traces", "created_at": created_at, "traces": corruption_traces})
    _write_json(output_dir / "forbidden_pattern_scan_controlled_equivalence.json", scan)
    _write_safe_unsafe_csv(output_dir / "safe_unsafe_equivalence_table.csv", safe_table["rows"])
    _write_markdown(output_dir / "controlled_equivalence_stress_summary.md", report, safe_table)
    return report


def build_equivalence_variants(
    *,
    source_tokens: Sequence[int],
    alias_safe_tokens: set[int],
    cross_safe_tokens: set[int],
    cross_ambiguous_tokens: set[int],
    token_to_l3_code: dict[int, str],
    family_to_tokens: dict[str, Sequence[int]],
    transition_allowed_next: Optional[dict],
) -> list[dict]:
    variants: list[dict] = []
    source = [int(token) for token in source_tokens]
    for token in source:
        if token in alias_safe_tokens:
            variants.append(
                {
                    "equivalence_type": "alias_equivalence",
                    "subtype": "exact_alias_or_naming_variant",
                    "tokens": list(source),
                    "claimed_exact_equivalence": True,
                    "platform_transfer_safe": False,
                    "anchor_token": int(token),
                }
            )
            break
    for token in source:
        if token in cross_safe_tokens:
            variants.append(
                {
                    "equivalence_type": "cross_platform_mapping",
                    "subtype": "exact_cross_platform_mapping",
                    "tokens": list(source),
                    "claimed_exact_equivalence": True,
                    "platform_transfer_safe": True,
                    "anchor_token": int(token),
                }
            )
            break
    for token in source:
        if token in cross_ambiguous_tokens:
            variants.append(
                {
                    "equivalence_type": "cross_platform_mapping",
                    "subtype": "ambiguous_or_composite_mapping",
                    "tokens": list(source),
                    "claimed_exact_equivalence": False,
                    "platform_transfer_safe": False,
                    "anchor_token": int(token),
                }
            )
            break
    family = build_operator_family_variant(base_tokens=source, token_to_l3_code=token_to_l3_code, family_to_tokens=family_to_tokens)
    if family:
        variants.append(family)
    reorder = build_reorder_variant(source, transition_allowed_next)
    if reorder:
        variants.append(reorder)
    bridge = build_bridge_expansion_variant(source, transition_allowed_next)
    if bridge:
        variants.append(bridge)
    return variants


def build_reorder_variant(source_tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> Optional[dict]:
    source = [int(token) for token in source_tokens]
    for pos in range(len(source) - 1):
        if source[pos] == source[pos + 1]:
            continue
        tokens = list(source)
        tokens[pos], tokens[pos + 1] = tokens[pos + 1], tokens[pos]
        return {
            "equivalence_type": "workflow_equivalence",
            "subtype": "adjacent_reorder",
            "tokens": tokens,
            "position": pos,
            "claimed_exact_equivalence": _transition_io_validity(tokens, transition_allowed_next) >= 1.0,
            "platform_transfer_safe": False,
        }
    return None


def build_bridge_expansion_variant(source_tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> Optional[dict]:
    source = [int(token) for token in source_tokens]
    allowed = (transition_allowed_next or {}).get("allowed_next", transition_allowed_next or {})
    if not allowed:
        return None
    for pos in range(len(source) - 1):
        left = source[pos]
        right = source[pos + 1]
        left_next = set(str(token) for token in (allowed.get(str(left)) or {}).keys())
        bridges = []
        for candidate in sorted(left_next, key=lambda value: int(value)):
            if candidate == str(right):
                continue
            if str(right) in (allowed.get(candidate) or {}):
                bridges.append(int(candidate))
        if bridges:
            bridge = bridges[0]
            return {
                "equivalence_type": "workflow_equivalence",
                "subtype": "bridge_expansion",
                "tokens": source[: pos + 1] + [bridge] + source[pos + 1 :],
                "position": pos + 1,
                "bridge_token": bridge,
                "claimed_exact_equivalence": False,
                "platform_transfer_safe": False,
            }
    return None


def evaluate_variant(
    *,
    variant: dict,
    source_tokens: Sequence[int],
    reference_tokens: Sequence[int],
    retrieval_pool: Sequence[dict],
    transition_allowed_next: Optional[dict],
) -> dict:
    source = [int(token) for token in source_tokens]
    candidate = [int(token) for token in variant.get("tokens", [])]
    source_metrics = _sequence_metrics(source, reference_tokens, transition_allowed_next)
    candidate_metrics = _sequence_metrics(candidate, reference_tokens, transition_allowed_next)
    retrieval_best = _best_candidate_metrics(retrieval_pool, reference_tokens, transition_allowed_next)
    retrieval_preservation = _lcs_length(source, candidate) / max(len(source), len(candidate), 1)
    topk_retention = float(tuple(candidate) in {tuple(int(token) for token in row.get("tokens", [])) for row in retrieval_pool})
    lcs_delta = round(candidate_metrics["lcs_ratio"] - source_metrics["lcs_ratio"], 8)
    set_delta = round(candidate_metrics["set_f1"] - source_metrics["set_f1"], 8)
    token_delta = round(candidate_metrics["token_accuracy"] - source_metrics["token_accuracy"], 8)
    execution_invalid = candidate_metrics["io_validity"] < 1.0
    workflow_corruption = lcs_delta < 0.0 or set_delta < 0.0 or token_delta < 0.0
    metadata_false = variant.get("subtype") == "ambiguous_or_composite_mapping"
    false_equivalence = bool(workflow_corruption or metadata_false)
    source_saturation = float(source_metrics["lcs_ratio"] < retrieval_best["lcs_ratio"] - 1e-9)
    candidate_saturation = float(candidate_metrics["lcs_ratio"] < retrieval_best["lcs_ratio"] - 1e-9)
    outcome = classify_equivalence_outcome(
        lcs_delta=lcs_delta,
        set_f1_delta=set_delta,
        token_accuracy_delta=token_delta,
        retrieval_preservation=retrieval_preservation,
        execution_invalid=execution_invalid,
        false_equivalence=false_equivalence,
        platform_transfer_safe=bool(variant.get("platform_transfer_safe")),
    )
    return {
        "equivalence_type": variant.get("equivalence_type"),
        "subtype": variant.get("subtype"),
        "outcome": outcome,
        "source_tokens": source,
        "candidate_tokens": candidate,
        "retrieval_preservation": round(retrieval_preservation, 8),
        "false_equivalence": float(false_equivalence),
        "execution_invalid_equivalence": float(execution_invalid),
        "workflow_corruption": float(workflow_corruption),
        "topk_retention": topk_retention,
        "lcs_preservation_delta": lcs_delta,
        "set_f1_preservation_delta": set_delta,
        "token_accuracy_delta": token_delta,
        "retrieval_saturation_change": round(candidate_saturation - source_saturation, 8),
        "source_metrics": source_metrics,
        "candidate_metrics": candidate_metrics,
        "retrieval_best_metrics": retrieval_best,
        "claimed_exact_equivalence": bool(variant.get("claimed_exact_equivalence")),
        "platform_transfer_safe": bool(variant.get("platform_transfer_safe")),
        "variant_metadata": {key: value for key, value in variant.items() if key not in {"tokens"}},
    }


def rank_lexical(query_text: str, task_type: str, items: Sequence[RetrievalItem], index: dict, *, top_k: int, max_candidates: int = 5000) -> list[dict]:
    query_terms = empirical_eval._terms(query_text)
    counts = Counter()
    for term in query_terms:
        counts.update(index.get("inverted", {}).get(term, []))
    if not counts:
        for pos in index.get("by_task", {}).get(task_type, [])[:max_candidates]:
            counts[pos] += 1
    if not counts:
        for pos in list(index.get("by_position", {}).keys())[:max_candidates]:
            counts[pos] += 1
    by_position = index.get("by_position", {})
    rows = []
    positions = [
        pos
        for pos, _ in sorted(
            counts.items(),
            key=lambda item: (-item[1], by_position[item[0]].index if item[0] in by_position else item[0]),
        )[:max_candidates]
    ]
    for pos in positions:
        item = by_position.get(pos)
        if item is None:
            continue
        lexical = empirical_eval._jaccard(query_terms, item.terms)
        task_match = item.task_type == task_type
        score = lexical + (0.05 if task_match else 0.0)
        rows.append(
            {
                "train_index": int(item.index),
                "task_type": item.task_type,
                "score": round(float(score), 8),
                "lexical_score": round(float(lexical), 8),
                "task_type_match": bool(task_match),
                "tokens": list(item.seq),
            }
        )
    rows.sort(key=lambda row: (-float(row.get("score", 0.0)), -float(row.get("lexical_score", 0.0)), int(row.get("train_index", 0))))
    for rank, row in enumerate(rows[: max(int(top_k), 1)]):
        row["retrieval_rank"] = rank
        row["retrieval_score"] = row["score"]
    return rows[: max(int(top_k), 1)]


def build_safe_unsafe_table(rows: Sequence[dict]) -> dict:
    table_rows = []
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("equivalence_type") or "unknown"), str(row.get("subtype") or "unknown"))].append(row)
    for (eq_type, subtype), group in sorted(grouped.items()):
        summary = _summary_block(group)
        if summary["execution_invalid_equivalence_rate"] > 0.0:
            decision = "execution-breaking"
        elif summary["false_equivalence_rate"] >= 0.20 or summary["workflow_corruption_rate"] >= 0.20:
            decision = "unsafe"
        elif summary["false_equivalence_rate"] > 0.0 or summary["workflow_corruption_rate"] > 0.0:
            decision = "ambiguous"
        elif eq_type == "cross_platform_mapping" and "exact" in subtype:
            decision = "platform-transfer-safe"
        else:
            decision = "stable"
        table_rows.append({"equivalence_type": eq_type, "subtype": subtype, "decision": decision, **summary})
    return {"schema_version": f"{SCHEMA_VERSION}.safe_unsafe_table", "rows": table_rows}


def _summary_block(rows: Sequence[dict]) -> dict:
    rows = list(rows)
    return {
        "n": len(rows),
        "retrieval_preservation": _mean(row.get("retrieval_preservation", 0.0) for row in rows),
        "false_equivalence_rate": _mean(row.get("false_equivalence", 0.0) for row in rows),
        "execution_invalid_equivalence_rate": _mean(row.get("execution_invalid_equivalence", 0.0) for row in rows),
        "workflow_corruption_rate": _mean(row.get("workflow_corruption", 0.0) for row in rows),
        "topk_retention": _mean(row.get("topk_retention", 0.0) for row in rows),
        "lcs_preservation_delta": _mean(row.get("lcs_preservation_delta", 0.0) for row in rows),
        "set_f1_preservation_delta": _mean(row.get("set_f1_preservation_delta", 0.0) for row in rows),
        "token_accuracy_delta": _mean(row.get("token_accuracy_delta", 0.0) for row in rows),
        "retrieval_saturation_change": _mean(row.get("retrieval_saturation_change", 0.0) for row in rows),
    }


def _mapping_operator_row(operator_name: str, platform: str, payload: dict) -> dict:
    mapping_type = str(payload.get("mapping_type") or "")
    composite = int(payload.get("num_candidates") or 0) > 1 or bool(payload.get("has_ambiguity")) or mapping_type in {"multi_output", "unknown"}
    return {
        "operator": str(operator_name),
        "platform": str(platform),
        "mapping_type": mapping_type,
        "num_candidates": int(payload.get("num_candidates") or 0),
        "has_ambiguity": bool(payload.get("has_ambiguity")),
        "mapping_safe": bool(mapping_type in SAFE_MAPPING_TYPES and not composite),
        "composite_or_ambiguous": bool(composite),
    }


def _build_retrieval_items(workflows: list[dict], indices: Sequence[int]) -> list[RetrievalItem]:
    items = []
    for idx in indices:
        workflow = workflows[int(idx)]
        text = empirical_eval._workflow_text(workflow)
        items.append(
            RetrievalItem(
                index=int(idx),
                task_type=empirical_eval._task_type(workflow),
                terms=empirical_eval._terms(text),
                seq=tuple(empirical_eval._content_seq(workflow)),
            )
        )
    return items


def _build_lexical_index(items: Sequence[RetrievalItem]) -> dict:
    inverted: dict[str, list[int]] = defaultdict(list)
    by_task: dict[str, list[int]] = defaultdict(list)
    by_position = {}
    for pos, item in enumerate(items):
        by_position[pos] = item
        by_task[item.task_type].append(pos)
        for term in item.terms:
            inverted[term].append(pos)
    return {"inverted": dict(inverted), "by_task": dict(by_task), "by_position": by_position}


def _sequence_metrics(tokens: Sequence[int], reference_tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> dict:
    pred = [int(token) for token in tokens]
    ref = [int(token) for token in reference_tokens]
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    lcs = _lcs_length(pred, ref)
    positional = sum(1 for left, right in zip(pred, ref) if left == right) / max(len(ref), 1) if ref else 0.0
    io_validity = _transition_io_validity(pred, transition_allowed_next)
    return {
        "lcs_ratio": round(lcs / max(len(pred), len(ref), 1), 8),
        "set_f1": round(set_f1, 8),
        "token_accuracy": round(positional, 8),
        "io_validity": round(io_validity, 8),
    }


def _best_candidate_metrics(candidates: Sequence[dict], reference_tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> dict:
    if not candidates:
        return _sequence_metrics([], reference_tokens, transition_allowed_next)
    scored = [_sequence_metrics(row.get("tokens", []), reference_tokens, transition_allowed_next) for row in candidates]
    scored.sort(key=lambda row: (row["lcs_ratio"], row["set_f1"], row["token_accuracy"]), reverse=True)
    return scored[0]


def _transition_io_validity(tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> float:
    if len(tokens) <= 1:
        return 1.0
    allowed = (transition_allowed_next or {}).get("allowed_next", transition_allowed_next or {})
    if not allowed:
        return 1.0
    for previous, current in zip(tokens, tokens[1:]):
        next_map = allowed.get(str(int(previous)), {})
        if str(int(current)) not in next_map:
            return 0.0
    return 1.0


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            cur[idx] = prev[idx - 1] + 1 if int(token) == int(other) else max(prev[idx], cur[idx - 1])
        prev = cur
    return prev[-1]


def _l2_family(l3_code: str) -> str:
    parts = str(l3_code).split("_")
    if len(parts) >= 3:
        return "_".join(["L2", parts[1], parts[2]])
    return "L2_unknown"


def _candidate_trace(row: dict) -> dict:
    return {
        "train_index": row.get("train_index"),
        "retrieval_rank": row.get("retrieval_rank"),
        "score": row.get("score"),
        "lexical_score": row.get("lexical_score"),
        "task_type_match": row.get("task_type_match"),
        "tokens": [int(token) for token in row.get("tokens", [])],
    }


def _mean(values) -> float:
    vals = [float(value) for value in values]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 8)


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


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", payload)
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid workflows payload: {path}")
    return workflows


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_transition_allowed(path: Optional[Path]) -> dict:
    if path is None or not Path(path).exists():
        return {}
    return _load_json(Path(path))


def _validated_indices(indices: Sequence[int], total: int) -> list[int]:
    out = [int(index) for index in indices]
    for index in out:
        if index < 0 or index >= total:
            raise IndexError(f"Split index {index} out of range for {total} workflows")
    return out


def _raw_task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return re.sub(r"\s+", " ", f"{meta.get('task_name') or ''} {meta.get('task_description') or ''}").strip() or "unknown task"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_safe_unsafe_csv(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "equivalence_type",
        "subtype",
        "decision",
        "n",
        "retrieval_preservation",
        "false_equivalence_rate",
        "execution_invalid_equivalence_rate",
        "workflow_corruption_rate",
        "topk_retention",
        "lcs_preservation_delta",
        "set_f1_preservation_delta",
        "token_accuracy_delta",
        "retrieval_saturation_change",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _write_markdown(path: Path, report: dict, safe_table: dict) -> None:
    metrics = report.get("metrics", {})
    lines = [
        "# Controlled Equivalence Stress Evaluation",
        "",
        "This is evaluation-only. It measures controlled equivalence stress variants without implementing semantic retrieval.",
        "",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Variant count: `{report.get('equivalence_variant_count')}`",
        "",
        "## Overall Metrics",
        "",
        "```json",
        json.dumps(metrics.get("overall", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## By Equivalence Type",
        "",
        "```json",
        json.dumps(metrics.get("by_equivalence_type", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Safe vs Unsafe Table",
        "",
        "```json",
        json.dumps(safe_table.get("rows", []), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Governance Boundary",
        "",
        "```json",
        json.dumps(metrics.get("interpretation_boundary", {}), ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _runtime_contract() -> dict:
    return {
        "evaluation_only": True,
        "training_run": False,
        "checkpoint_mutated": False,
        "embedding_learning": False,
        "semantic_encoder_training": False,
        "retrieval_redesign": False,
        "runtime_deployment_change": False,
        "semantic_retrieval_implemented": False,
    }


def _interpretation_boundary() -> dict:
    return {
        "stable_equivalence_types_can_be_reported": True,
        "unsafe_equivalence_types_can_be_reported": True,
        "platform_transfer_safe_requires_exact_unambiguous_mapping": True,
        "semantic_retrieval_solved": False,
        "l2_validated": False,
        "deployment_ready_equivalence_policy": False,
        "execution_preserving_semantic_equivalence_proven_globally": False,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--mappings", type=Path, default=OUTPUT_DIR / "id_mappings_v2.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "controlled_equivalence_stress")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--trace-top-n", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_controlled_equivalence_stress(
        data_path=args.data,
        splits_path=args.splits,
        mappings_path=args.mappings,
        transition_matrix_path=args.transition_matrix,
        output_dir=args.output_dir,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        trace_top_n=args.trace_top_n,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
