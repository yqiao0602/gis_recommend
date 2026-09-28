#!/usr/bin/env python3
"""Join stable101 chain-level candidates back to source snippets.

This is a review-pack builder, not a training exporter. It replays the legacy
QGIS chain dataset scan with file provenance, verifies that replay against the
current immutable chain dataset, then joins the stable101 50-row candidate batch
to source paths, hashes, snippets, and same-chain cluster references.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_qgis_chain_dataset import (  # noqa: E402
    CATALOG_PATH,
    OFFICIAL_OPS_PATH,
    QGIS_DIR,
    SCRIPT_DIRS,
    _build_semantic_tags,
    audit_chain,
    build_l3_lookup,
    extract_processing_calls,
    extract_task_text,
    load_alg_id_crosswalk,
    load_official_qgis_operators,
    load_operator_catalog,
    map_to_l3,
)


SCHEMA_VERSION = "gis_recommend.qgis_stable101_source_review_pack.v1"
TAXONOMY_ADMISSION = "granted_for_four_stable101_mappings"
TRAINING_ADMISSION = "not_granted"
PROCESSING_RUN_RE = re.compile(
    r"processing\.run\(\s*[\"']([a-z0-9_]+:[a-z0-9_]+)[\"']",
    re.IGNORECASE,
)
HUMAN_FIELDS = [
    "human_source_retrieval_ready",
    "human_workflow_boundary_decision",
    "human_operator_identity_order_decision",
    "human_dependency_decision",
    "human_task_text_usable",
    "human_description_generation_ready",
    "human_training_candidate_ready",
    "human_notes",
    "reviewer",
    "reviewed_at",
]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})
    temporary.replace(path)


def _normalize_ops(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def load_default_catalog(
    *,
    official_ops_path: Path = OFFICIAL_OPS_PATH,
    legacy_catalog_path: Path = CATALOG_PATH,
) -> dict[str, dict[str, Any]]:
    """Load the same effective catalog as the legacy chain dataset builder."""
    catalog = load_official_qgis_operators(official_ops_path)
    if legacy_catalog_path.exists():
        legacy = load_operator_catalog(legacy_catalog_path)
        for alg_id, info in catalog.items():
            info["data_type"] = legacy.get(alg_id, {}).get("data_type", "unknown")
    else:
        for info in catalog.values():
            info.setdefault("data_type", "unknown")
    return catalog


def _expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _is_processing_func(node: ast.AST) -> bool:
    name = _expr_name(node)
    return name == "processing.run" or name.endswith(".processing.run")


def _key_repr(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _expr_name(node)
    return type(node).__name__ if node is not None else "None"


def _target_repr(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _expr_name(node)
    if isinstance(node, ast.Subscript):
        return f"{_expr_name(node.value)}[...]"
    if isinstance(node, ast.Tuple):
        return ",".join(_target_repr(item) for item in node.elts)
    return type(node).__name__


def _output_role(call: ast.Call) -> dict[str, Any]:
    parent = getattr(call, "parent", None)
    subscript_key = None
    if isinstance(parent, ast.Subscript):
        slice_node = parent.slice
        if isinstance(slice_node, ast.Constant):
            subscript_key = slice_node.value
        parent = getattr(parent, "parent", None)

    if isinstance(parent, ast.Assign):
        return {
            "role": "assigned",
            "target": ",".join(_target_repr(target) for target in parent.targets),
            "subscript": subscript_key,
        }
    if isinstance(parent, ast.AnnAssign):
        return {
            "role": "assigned",
            "target": _target_repr(parent.target),
            "subscript": subscript_key,
        }
    if isinstance(parent, ast.Return):
        return {"role": "returned", "target": "return", "subscript": subscript_key}
    if isinstance(parent, ast.Expr):
        return {
            "role": "side_effect_or_unassigned",
            "target": "expr",
            "subscript": subscript_key,
        }
    return {
        "role": type(parent).__name__ if parent else "unknown",
        "target": "",
        "subscript": subscript_key,
    }


def _ast_call_infos(text: str) -> list[dict[str, Any]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_processing_func(node.func):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        alg_id = str(node.args[0].value).strip().lower()
        if ":" not in alg_id:
            continue
        param_keys: list[str] = []
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Dict):
            param_keys = [_key_repr(key) for key in node.args[1].keys]
        calls.append(
            {
                "operator_id": alg_id,
                "line_start": int(getattr(node, "lineno", 1)),
                "line_end": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                "param_keys": param_keys,
                "output_role": _output_role(node),
            }
        )
    return sorted(calls, key=lambda row: (row["line_start"], row["line_end"], row["operator_id"]))


def _line_number_at(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _merge_line_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _numbered_snippet(
    lines: list[str],
    ranges: list[tuple[int, int]],
    *,
    context_lines: int,
    max_snippet_lines: int,
) -> tuple[str, str]:
    if not ranges:
        return "", "empty"
    expanded = [
        (max(1, start - context_lines), min(len(lines), end + context_lines))
        for start, end in ranges
    ]
    merged = _merge_line_ranges(expanded)
    total_lines = sum(end - start + 1 for start, end in merged)
    strategy = "contiguous" if len(merged) == 1 else "per_call_compact"

    if total_lines > max_snippet_lines:
        compact: list[tuple[int, int]] = []
        per_range_budget = max(1, max_snippet_lines // max(len(ranges), 1))
        side = max(0, (per_range_budget - 1) // 2)
        for start, end in ranges:
            center = start
            compact.append((max(1, center - side), min(len(lines), center + side)))
        merged = _merge_line_ranges(compact)
        strategy = "per_call_budgeted"

    chunks: list[str] = []
    previous_end = 0
    for start, end in merged:
        if chunks and start > previous_end + 1:
            chunks.append("...")
        for line_no in range(start, end + 1):
            chunks.append(f"{line_no:4d} | {lines[line_no - 1]}")
        previous_end = end
    return "\n".join(chunks), strategy


def extract_call_sites_and_snippet(
    content: str,
    *,
    context_lines: int = 3,
    max_snippet_lines: int = 120,
) -> tuple[list[dict[str, Any]], str, str]:
    """Extract call-site metadata using the legacy regex order plus AST details."""
    lines = content.splitlines()
    ast_infos = _ast_call_infos(content)
    used_ast: set[int] = set()
    call_sites: list[dict[str, Any]] = []

    for ordinal, match in enumerate(PROCESSING_RUN_RE.finditer(content), start=1):
        operator_id = match.group(1).strip().lower()
        line_start = _line_number_at(content, match.start())
        ast_index = next(
            (
                idx
                for idx, info in enumerate(ast_infos)
                if idx not in used_ast
                and info["operator_id"] == operator_id
                and abs(int(info["line_start"]) - line_start) <= 1
            ),
            None,
        )
        ast_info = ast_infos[ast_index] if ast_index is not None else {}
        if ast_index is not None:
            used_ast.add(ast_index)
        line_end = int(ast_info.get("line_end") or line_start)
        call_sites.append(
            {
                "ordinal": ordinal,
                "operator_id": operator_id,
                "line_start": line_start,
                "line_end": line_end,
                "param_keys": ast_info.get("param_keys", []),
                "output_role": ast_info.get("output_role", {}),
            }
        )

    snippet, strategy = _numbered_snippet(
        lines,
        [(int(site["line_start"]), int(site["line_end"])) for site in call_sites],
        context_lines=context_lines,
        max_snippet_lines=max_snippet_lines,
    )
    return call_sites, snippet, strategy


def replay_chain_dataset_with_provenance(
    *,
    qgis_root: Path = QGIS_DIR,
    catalog: dict[str, dict[str, Any]],
    l3_lookup: dict[str, str],
    alg_id_xwalk: dict[str, str] | None = None,
    min_length: int = 2,
    max_length: int = 15,
    require_catalog: bool = True,
    context_lines: int = 3,
    max_snippet_lines: int = 120,
    snippet_record_indices: set[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()

    for dir_name, source_label in SCRIPT_DIRS:
        scripts_dir = qgis_root / dir_name / "downloaded_scripts"
        if not scripts_dir.exists():
            stats[f"missing_source_root_{source_label}"] += 1
            continue

        for file_name in sorted(os.listdir(scripts_dir)):
            file_path = scripts_dir / file_name
            try:
                raw = file_path.read_bytes()
                content = raw.decode("utf-8", errors="ignore")
            except Exception:
                stats["read_error"] += 1
                continue

            calls = extract_processing_calls(content)
            ops = [str(call["alg_id"]).lower() for call in calls]
            if len(ops) < min_length or len(ops) > max_length:
                stats[f"rejected_length_{'short' if len(ops) < min_length else 'long'}"] += 1
                continue
            if require_catalog and not all(op.lower() in catalog for op in ops):
                stats["rejected_missing_catalog"] += 1
                continue

            task_text = extract_task_text(content, file_name, source_label)
            quality = audit_chain(ops, catalog)
            operator_names = [catalog.get(op.lower(), {}).get("name", op) for op in ops]
            dataset_item: dict[str, Any] = {
                "task_text": task_text,
                "qgis_ops": ops,
                "operator_names": operator_names,
                "source": source_label,
                "quality": quality,
            }
            semantic_tags = _build_semantic_tags(ops)
            if semantic_tags:
                dataset_item["qgis_semantic_tags"] = semantic_tags
            l3_seq = map_to_l3(ops, catalog, l3_lookup, alg_id_xwalk)
            if l3_seq is not None:
                dataset_item["optional_l3_sequence"] = l3_seq
                dataset_item["training_targets"] = ["qgis_head", "l3_head"]
            else:
                dataset_item["training_targets"] = ["qgis_head"]

            record_index = len(rows) + 1
            if snippet_record_indices is None or record_index in snippet_record_indices:
                call_sites, source_snippet, snippet_strategy = extract_call_sites_and_snippet(
                    content,
                    context_lines=context_lines,
                    max_snippet_lines=max_snippet_lines,
                )
                snippet_contains_all_ops = all(op in source_snippet.lower() for op in ops)
            else:
                call_sites = []
                source_snippet = ""
                snippet_strategy = "not_extracted_non_selected_record"
                snippet_contains_all_ops = False
            rows.append(
                {
                    "record_index": record_index,
                    "dataset_item": dataset_item,
                    "qgis_ops": ops,
                    "task_text": task_text,
                    "source": source_label,
                    "source_root_id": source_label,
                    "source_root_dir_name": dir_name,
                    "source_root_path": str(scripts_dir.resolve()),
                    "relative_path": file_name,
                    "source_path": str(file_path.resolve()),
                    "source_sha256": hashlib.sha256(raw).hexdigest(),
                    "source_size_bytes": len(raw),
                    "call_sites": call_sites,
                    "source_snippet": source_snippet,
                    "snippet_strategy": snippet_strategy,
                    "source_snippet_contains_all_ops": snippet_contains_all_ops,
                }
            )
            stats["included"] += 1

    stats["total_included"] = len(rows)
    return rows, dict(stats)


def validate_replay_against_chain_dataset(
    provenance_rows: list[dict[str, Any]],
    chain_rows: list[dict[str, Any]],
) -> None:
    if len(provenance_rows) != len(chain_rows):
        raise ValueError(
            "replayed chain dataset mismatch: "
            f"row count {len(provenance_rows)} != {len(chain_rows)}"
        )
    for index, (provenance, chain_row) in enumerate(
        zip(provenance_rows, chain_rows),
        start=1,
    ):
        dataset_item = provenance["dataset_item"]
        checks = {
            "qgis_ops": _normalize_ops(dataset_item.get("qgis_ops")),
            "source": str(dataset_item.get("source") or ""),
            "task_text": str(dataset_item.get("task_text") or ""),
        }
        expected = {
            "qgis_ops": _normalize_ops(chain_row.get("qgis_ops")),
            "source": str(chain_row.get("source") or ""),
            "task_text": str(chain_row.get("task_text") or ""),
        }
        if checks != expected:
            raise ValueError(
                "replayed chain dataset mismatch at record_index "
                f"{index}: got {checks}, expected {expected}"
            )


def _chain_key(row: dict[str, Any]) -> str:
    value = row.get("chain_key")
    if isinstance(value, str) and value:
        return value
    return " -> ".join(_normalize_ops(row.get("qgis_ops", [])))


def _cluster_refs(
    cluster_rows: list[dict[str, Any]],
    provenance_by_index: dict[int, dict[str, Any]],
    *,
    max_refs: int,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for row in sorted(cluster_rows, key=lambda item: int(item.get("record_index", 0))):
        record_index = int(row.get("record_index", 0))
        provenance = provenance_by_index.get(record_index, {})
        refs.append(
            {
                "record_index": record_index,
                "record_sha256": row.get("record_sha256", ""),
                "source_repo": row.get("source_repo", ""),
                "task_seed_text": row.get("task_seed_text", ""),
                "source_root_id": provenance.get("source_root_id", ""),
                "relative_path": provenance.get("relative_path", ""),
                "source_sha256": provenance.get("source_sha256", ""),
            }
        )
        if len(refs) >= max_refs:
            break
    return refs


def build_source_review_rows(
    *,
    candidates: list[dict[str, Any]],
    newly_complete_records: list[dict[str, Any]],
    chain_rows: list[dict[str, Any]],
    provenance_rows: list[dict[str, Any]],
    max_cluster_refs: int = 8,
) -> list[dict[str, Any]]:
    provenance_by_index = {
        int(row["record_index"]): row
        for row in provenance_rows
    }
    cluster_by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in newly_complete_records:
        cluster_by_chain[_chain_key(row)].append(row)

    review_rows: list[dict[str, Any]] = []
    for position, candidate in enumerate(
        sorted(candidates, key=lambda row: int(row.get("review_index", 0))),
        start=1,
    ):
        record_index = int(candidate.get("representative_record_index", 0))
        if record_index < 1 or record_index > len(chain_rows):
            raise ValueError(f"representative_record_index out of range: {record_index}")
        provenance = provenance_by_index.get(record_index)
        if provenance is None:
            raise ValueError(f"missing provenance for record_index {record_index}")

        candidate_ops = _normalize_ops(candidate.get("qgis_ops", []))
        provenance_ops = _normalize_ops(provenance.get("qgis_ops", []))
        chain_ops = _normalize_ops(chain_rows[record_index - 1].get("qgis_ops", []))
        if candidate_ops != provenance_ops or candidate_ops != chain_ops:
            raise ValueError(
                "candidate/source chain mismatch at record_index "
                f"{record_index}: candidate={candidate_ops}, source={provenance_ops}, chain={chain_ops}"
            )

        chain_key = _chain_key(candidate)
        cluster_rows = cluster_by_chain.get(chain_key, [])
        member_indices = [
            int(row.get("record_index", 0))
            for row in sorted(cluster_rows, key=lambda item: int(item.get("record_index", 0)))
        ]
        member_source_repos = sorted(
            {
                str(row.get("source_repo") or "")
                for row in cluster_rows
                if str(row.get("source_repo") or "")
            }
        )
        call_sites = list(provenance.get("call_sites", []))
        row = {
            "review_index": int(candidate.get("review_index") or position),
            "record_id": _stable_hash(
                {
                    "stable101_source_review": record_index,
                    "source_sha256": provenance.get("source_sha256", ""),
                    "qgis_ops": candidate_ops,
                }
            )[:24],
            "selection_stratum": candidate.get("selection_stratum", ""),
            "selection_rationale": candidate.get("selection_rationale", []),
            "representative_record_index": record_index,
            "representative_record_sha256": candidate.get("representative_record_sha256", ""),
            "chain_dataset_record_index": record_index,
            "source_root_id": provenance.get("source_root_id", ""),
            "source_root_dir_name": provenance.get("source_root_dir_name", ""),
            "source_root_path": provenance.get("source_root_path", ""),
            "relative_path": provenance.get("relative_path", ""),
            "source_path": provenance.get("source_path", ""),
            "source_sha256": provenance.get("source_sha256", ""),
            "source_size_bytes": provenance.get("source_size_bytes", 0),
            "joined_source_status": "joined_and_chain_verified",
            "chain_alignment_status": "matched_chain_dataset_by_record_index",
            "chain_key": chain_key,
            "chain_frequency": candidate.get("chain_frequency", len(cluster_rows)),
            "unique_record_sha_count": candidate.get("unique_record_sha_count", ""),
            "cluster_member_count": len(cluster_rows),
            "cluster_member_record_indices": member_indices,
            "cluster_member_source_repos": member_source_repos,
            "cluster_source_refs_sample": _cluster_refs(
                cluster_rows,
                provenance_by_index,
                max_refs=max_cluster_refs,
            ),
            "chain_length": len(candidate_ops),
            "modality": candidate.get("modality", ""),
            "ordered_operator_ids": candidate_ops,
            "qgis_ops": candidate_ops,
            "operator_names": candidate.get("operator_names", []),
            "proposal_ops_present": candidate.get("proposal_ops_present", []),
            "mapped_l3_chain": candidate.get("proposed_l3_sequence", []),
            "proposed_l3_sequence": candidate.get("proposed_l3_sequence", []),
            "stable98_unresolved_ops": candidate.get("stable98_unresolved_ops", []),
            "repeated_operator_ids": candidate.get("repeated_operator_ids", []),
            "risk_flags": candidate.get("risk_flags", []),
            "review_priority_score": candidate.get("review_priority_score", ""),
            "task_text": candidate.get("task_text", chain_rows[record_index - 1].get("task_text", "")),
            "task_seed_text": candidate.get("task_seed_text", ""),
            "task_text_quality": candidate.get("task_text_quality", ""),
            "source_repo": candidate.get("source_repo", ""),
            "dependency_status": "not_recovered_source_join_only",
            "dependency_edges": [],
            "parameter_key_summary": [site.get("param_keys", []) for site in call_sites],
            "call_sites": call_sites,
            "snippet_strategy": provenance.get("snippet_strategy", ""),
            "source_snippet_contains_all_ops": bool(
                provenance.get("source_snippet_contains_all_ops")
            ),
            "source_snippet": provenance.get("source_snippet", ""),
            "taxonomy_admission": candidate.get("taxonomy_admission", TAXONOMY_ADMISSION),
            "training_admission": TRAINING_ADMISSION,
            "training_rows_emitted": 0,
        }
        for field in HUMAN_FIELDS:
            row[field] = ""
        review_rows.append(row)

    return review_rows


def _count_values(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "")) for row in rows).items()))


def summarize(
    *,
    candidates: list[dict[str, Any]],
    newly_complete_records: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    replay_stats: dict[str, int],
    input_sha256: dict[str, str],
    qgis_root: Path,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "status": "source_review_ready",
        "qgis_root": str(qgis_root.resolve()),
        "input_sha256": input_sha256,
        "candidate_count": len(candidates),
        "newly_complete_record_count": len(newly_complete_records),
        "review_row_count": len(review_rows),
        "joined_source_count": sum(
            1 for row in review_rows if row.get("joined_source_status") == "joined_and_chain_verified"
        ),
        "source_snippet_contains_all_ops_count": sum(
            1 for row in review_rows if row.get("source_snippet_contains_all_ops") is True
        ),
        "replay_stats": replay_stats,
        "source_root_counts": _count_values(review_rows, "source_root_id"),
        "selection_stratum_counts": _count_values(review_rows, "selection_stratum"),
        "modality_counts": _count_values(review_rows, "modality"),
        "task_text_quality_counts": _count_values(review_rows, "task_text_quality"),
        "dependency_status_counts": _count_values(review_rows, "dependency_status"),
        "taxonomy_admission": TAXONOMY_ADMISSION,
        "training_admission": TRAINING_ADMISSION,
        "notes": [
            "This package is source-backed human review material, not a training export.",
            "The legacy qgis_chain_dataset scan was replayed and matched by record index before joining.",
            "Dependency edges are not recovered in this source-join pack and must be reviewed or recovered separately.",
            "No production mapping, LLM description generation, training JSONL, or model training is emitted.",
        ],
    }


def _markdown(summary: dict[str, Any], review_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# QGIS stable101 Source Review Pack",
        "",
        "This report joins the stable101 50-row chain-level candidate batch back to source files. It is for human review only and does not grant training admission.",
        "",
        "## Summary",
        "",
        f"- Review rows: {summary['review_row_count']}",
        f"- Joined sources: {summary['joined_source_count']}",
        f"- Snippets containing all ordered operators: {summary['source_snippet_contains_all_ops_count']}",
        f"- Source roots: `{json.dumps(summary['source_root_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Modalities: `{json.dumps(summary['modality_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Text quality: `{json.dumps(summary['task_text_quality_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Taxonomy admission: `{summary['taxonomy_admission']}`",
        f"- Training admission: `{summary['training_admission']}`",
        "",
        "## Review Rows",
        "",
        "| # | source | chain freq | modality | operators | source file | task seed |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for row in review_rows:
        task = str(row.get("task_seed_text", "")).replace("|", "/")[:90]
        operators = " -> ".join(str(op) for op in row.get("ordered_operator_ids", []))
        lines.append(
            f"| {row['review_index']} | {row['source_root_id']} | {row['chain_frequency']} | "
            f"{row['modality']} | `{operators}` | `{row['relative_path']}` | {task} |"
        )
    lines.extend(
        [
            "",
            "## Admission Boundary",
            "",
            "- Use `stable101_source_review_50_v1.csv` for manual adjudication.",
            "- Check workflow boundary, operator identity/order, source snippet validity, dependency plausibility, and task-text usability.",
            "- Keep `training_admission=not_granted` until human review and faithful task-description generation pass.",
            "",
        ]
    )
    return "\n".join(lines)


def build_source_review_pack(
    *,
    candidates_path: Path,
    newly_complete_records_path: Path,
    chain_dataset_path: Path,
    output_dir: Path,
    qgis_root: Path = QGIS_DIR,
    catalog: dict[str, dict[str, Any]] | None = None,
    l3_lookup: dict[str, str] | None = None,
    alg_id_xwalk: dict[str, str] | None = None,
    min_length: int = 2,
    max_length: int = 15,
    require_catalog: bool = True,
    context_lines: int = 3,
    max_snippet_lines: int = 120,
    max_cluster_refs: int = 8,
    artifact_stem: str = "stable101_source_review_50_v1",
) -> dict[str, Any]:
    candidates = _read_jsonl(candidates_path)
    newly_complete_records = _read_jsonl(newly_complete_records_path)
    chain_rows = _read_jsonl(chain_dataset_path)
    if catalog is None:
        catalog = load_default_catalog()
    if l3_lookup is None:
        l3_lookup = build_l3_lookup(ROOT / "outputs_v2" / "id_mappings_v2.json")
    if alg_id_xwalk is None:
        alg_id_xwalk = load_alg_id_crosswalk(ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json")

    snippet_record_indices = {
        int(row.get("representative_record_index", 0))
        for row in candidates
        if int(row.get("representative_record_index", 0)) > 0
    }
    provenance_rows, replay_stats = replay_chain_dataset_with_provenance(
        qgis_root=qgis_root,
        catalog=catalog,
        l3_lookup=l3_lookup,
        alg_id_xwalk=alg_id_xwalk,
        min_length=min_length,
        max_length=max_length,
        require_catalog=require_catalog,
        context_lines=context_lines,
        max_snippet_lines=max_snippet_lines,
        snippet_record_indices=snippet_record_indices,
    )
    validate_replay_against_chain_dataset(provenance_rows, chain_rows)
    review_rows = build_source_review_rows(
        candidates=candidates,
        newly_complete_records=newly_complete_records,
        chain_rows=chain_rows,
        provenance_rows=provenance_rows,
        max_cluster_refs=max_cluster_refs,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    if artifact_stem == "stable101_source_review_50_v1":
        summary_name = "stable101_source_review_50_summary_v1.json"
        report_name = "stable101_source_review_50_report_v1.md"
        manifest_name = "stable101_source_review_50_manifest_v1.json"
    else:
        summary_name = f"{artifact_stem}_summary.json"
        report_name = f"{artifact_stem}_report.md"
        manifest_name = f"{artifact_stem}_manifest.json"
    jsonl_path = output_dir / f"{artifact_stem}.jsonl"
    csv_path = output_dir / f"{artifact_stem}.csv"
    summary_path = output_dir / summary_name
    report_path = output_dir / report_name
    manifest_path = output_dir / manifest_name

    fieldnames = [
        "review_index",
        "record_id",
        "selection_stratum",
        "selection_rationale",
        "representative_record_index",
        "representative_record_sha256",
        "chain_dataset_record_index",
        "source_root_id",
        "source_root_dir_name",
        "source_root_path",
        "relative_path",
        "source_path",
        "source_sha256",
        "source_size_bytes",
        "joined_source_status",
        "chain_alignment_status",
        "chain_key",
        "chain_frequency",
        "unique_record_sha_count",
        "cluster_member_count",
        "cluster_member_record_indices",
        "cluster_member_source_repos",
        "cluster_source_refs_sample",
        "chain_length",
        "modality",
        "ordered_operator_ids",
        "operator_names",
        "proposal_ops_present",
        "mapped_l3_chain",
        "stable98_unresolved_ops",
        "repeated_operator_ids",
        "risk_flags",
        "review_priority_score",
        "task_text",
        "task_seed_text",
        "task_text_quality",
        "source_repo",
        "dependency_status",
        "dependency_edges",
        "parameter_key_summary",
        "call_sites",
        "snippet_strategy",
        "source_snippet_contains_all_ops",
        "source_snippet",
        "taxonomy_admission",
        "training_admission",
        "training_rows_emitted",
        *HUMAN_FIELDS,
    ]
    _write_jsonl(jsonl_path, review_rows)
    _write_csv(csv_path, review_rows, fieldnames)

    input_sha256 = {
        "candidates": _sha256(candidates_path),
        "newly_complete_records": _sha256(newly_complete_records_path),
        "chain_dataset": _sha256(chain_dataset_path),
    }
    summary = summarize(
        candidates=candidates,
        newly_complete_records=newly_complete_records,
        review_rows=review_rows,
        replay_stats=replay_stats,
        input_sha256=input_sha256,
        qgis_root=qgis_root,
    )
    _write_json(summary_path, summary)
    _atomic_write_text(report_path, _markdown(summary, review_rows))

    artifacts = {
        "review_jsonl": jsonl_path,
        "review_csv": csv_path,
        "summary": summary_path,
        "report": report_path,
    }
    manifest = {
        "schema": f"{SCHEMA_VERSION}.manifest",
        "status": "source_review_ready",
        "input_sha256": input_sha256,
        "artifacts": {name: str(path) for name, path in artifacts.items()},
        "artifact_sha256": {name: _sha256(path) for name, path in artifacts.items()},
        "taxonomy_admission": TAXONOMY_ADMISSION,
        "training_admission": TRAINING_ADMISSION,
    }
    _write_json(manifest_path, manifest)
    summary["manifest_sha256"] = _sha256(manifest_path)
    return summary


def main() -> int:
    base_dir = (
        ROOT
        / "docs"
        / "reports"
        / "qgis_mapping_high_impact_blockers_2026-07-24"
        / "stable101_candidate_pool_v1"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        default=str(base_dir / "stable101_next_review_candidates_50_v1.jsonl"),
        type=Path,
    )
    parser.add_argument(
        "--newly-complete-records",
        default=str(base_dir / "stable101_newly_complete_records_v1.jsonl"),
        type=Path,
    )
    parser.add_argument(
        "--chain-dataset",
        default=str(ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"),
        type=Path,
    )
    parser.add_argument(
        "--output-dir",
        default=str(base_dir.parent / "stable101_source_review_50_v1"),
        type=Path,
    )
    parser.add_argument("--qgis-root", default=str(QGIS_DIR), type=Path)
    parser.add_argument("--official-ops", default=str(OFFICIAL_OPS_PATH), type=Path)
    parser.add_argument("--catalog", default=str(CATALOG_PATH), type=Path)
    parser.add_argument(
        "--id-mappings",
        default=str(ROOT / "outputs_v2" / "id_mappings_v2.json"),
        type=Path,
    )
    parser.add_argument(
        "--alg-id-crosswalk",
        default=str(ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"),
        type=Path,
    )
    parser.add_argument("--min-length", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=15)
    parser.add_argument("--no-require-catalog", action="store_true")
    parser.add_argument("--context-lines", type=int, default=3)
    parser.add_argument("--max-snippet-lines", type=int, default=120)
    parser.add_argument("--max-cluster-refs", type=int, default=8)
    parser.add_argument(
        "--artifact-stem",
        default="stable101_source_review_50_v1",
        help="Output filename stem; the default preserves legacy 50-row names.",
    )
    args = parser.parse_args()

    catalog = load_default_catalog(
        official_ops_path=args.official_ops,
        legacy_catalog_path=args.catalog,
    )
    l3_lookup = build_l3_lookup(args.id_mappings)
    alg_id_xwalk = load_alg_id_crosswalk(args.alg_id_crosswalk)
    summary = build_source_review_pack(
        candidates_path=args.candidates,
        newly_complete_records_path=args.newly_complete_records,
        chain_dataset_path=args.chain_dataset,
        output_dir=args.output_dir,
        qgis_root=args.qgis_root,
        catalog=catalog,
        l3_lookup=l3_lookup,
        alg_id_xwalk=alg_id_xwalk,
        min_length=args.min_length,
        max_length=args.max_length,
        require_catalog=not args.no_require_catalog,
        context_lines=args.context_lines,
        max_snippet_lines=args.max_snippet_lines,
        max_cluster_refs=args.max_cluster_refs,
        artifact_stem=args.artifact_stem,
    )
    print(
        "stable101_source_review_pack rows={rows} joined={joined} snippets_all_ops={snippets}".format(
            rows=summary["review_row_count"],
            joined=summary["joined_source_count"],
            snippets=summary["source_snippet_contains_all_ops_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
