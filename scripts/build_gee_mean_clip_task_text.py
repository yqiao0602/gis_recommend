#!/usr/bin/env python3
"""Build source-backed task text for frozen GEE mean/clip candidates.

The exporter describes only the retained ``mean -> clip`` chain. It never
infers dataset, time, region meaning, or preprocessing from variable names and
keeps every resulting row outside training/validation/test admission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_dataflow_slicer import build_backward_slices  # noqa: E402
from gis_recommend.data.gee_raster_core_schema import (  # noqa: E402
    SCHEMA,
    validate_core_train_row,
)
from scripts.adjudicate_gee_mean_clip_clusters import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as REVIEW_DIR,
)
from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _filesystem_path,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


DEFAULT_INPUT = REVIEW_DIR / "gee_mean_clip_exporter_input_manifest_v1.jsonl"
DEFAULT_OUTPUT_DIR = REVIEW_DIR / "task_text_v1"
DEFAULT_SOURCE_ROOTS = (
    ROOT / ".tmp_gee_semantic_census_3106_sources",
    ROOT / ".tmp_gee_semantic_remaining_8291_sources",
)
DEFAULT_AST_DIRS = (
    ROOT / ".tmp_gee_semantic_census_3106_ast",
    ROOT / ".tmp_gee_semantic_remaining_8291_ast",
)
SOURCE_PREFIX = PurePosixPath("/home/yll/GEE/Data")
EXPECTED_OPERATORS = ("ee.imagecollection.mean", "ee.image.clip")
EXPECTED_L3 = ("L3_10_02_03", "L3_03_01_01")

_TEMPORAL_PHRASES = {
    "allow_source_backed_full_year_2000": "for the source-defined 2000 period",
    "allow_source_backed_full_year_2010": "for the source-defined 2010 period",
    "allow_source_backed_full_year_2019": "for 2019",
    "allow_source_backed_full_year_2021": "for the source-defined 2021 period",
    "allow_source_backed_bounded_period_2012": "for the source-defined 2012 period",
    "allow_source_backed_bounded_period_2019": "for the source-defined 2019 period",
    "allow_source_backed_bounded_period_2020": "for the source-defined 2020 period",
    "allow_source_backed_bounded_period_2021": "for the source-defined 2021 period",
    "allow_source_backed_seasonal_2001": "for the source-defined 2001 season",
    "allow_source_backed_seasonal_2019": "for the source-defined 2019 season",
    "allow_source_backed_seasonal_2021": "for the source-defined 2021 season",
    "allow_source_backed_multiyear_seasonal_2013_2022": (
        "for the source-defined 2013-2022 seasonal period"
    ),
    "allow_source_backed_cross_year_bounded_period_2018_2019": (
        "for the source-defined 2018-2019 period"
    ),
    "allow_source_backed_cross_year_season_2018_2019": (
        "for the source-defined 2018-2019 season"
    ),
    "allow_source_backed_single_day_2017_09_and_ignore_variable_name": (
        "for the source-defined day in September 2017"
    ),
    "allow_source_backed_single_day_2021_01_13": "for January 13, 2021",
    "allow_source_backed_target_date_window_2019_07": (
        "for the source-defined July 2019 window"
    ),
    "omit_unverified_temporal_facts": "",
    "omit_unverified_temporal_facts_and_ignore_median_name": "",
}


def temporal_phrase(policy: str) -> str:
    try:
        return _TEMPORAL_PHRASES[policy]
    except KeyError as exc:
        raise ValueError(f"unknown temporal description policy: {policy!r}") from exc


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _callee_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return name if isinstance(name, str) else None
    if node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    root = _callee_name(node.get("object"))
    prop = node.get("property")
    name = prop.get("name") if isinstance(prop, dict) else None
    return f"{root}.{name}" if root and isinstance(name, str) else None


def _definition_node(ast: dict[str, Any], definition: Any) -> dict[str, Any]:
    statement = ast["body"][definition.statement_index]
    if definition.kind == "function_helper":
        return statement
    if statement.get("type") == "VariableDeclaration":
        for declaration in statement.get("declarations", []):
            identifier = declaration.get("id") if isinstance(declaration, dict) else None
            if isinstance(identifier, dict) and identifier.get("name") == definition.target:
                init = declaration.get("init")
                return init if isinstance(init, dict) else declaration
    expression = statement.get("expression")
    candidates = (
        expression.get("expressions", [])
        if isinstance(expression, dict) and expression.get("type") == "SequenceExpression"
        else [expression]
    )
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("type") != "AssignmentExpression":
            continue
        left = candidate.get("left")
        if isinstance(left, dict) and left.get("name") == definition.target:
            right = candidate.get("right")
            return right if isinstance(right, dict) else candidate
    return statement


def extract_dependency_dataset_literals(
    row: dict[str, Any], ast: dict[str, Any]
) -> list[str]:
    """Return public ImageCollection literals in the exact dependency closure."""

    definitions = build_backward_slices(ast, []).definitions
    by_id = {definition.definition_id: definition for definition in definitions}
    dependency_ids = [
        str(value)
        for value in [row.get("definition_id"), *(row.get("transitive_dependency_ids") or [])]
        if value
    ]
    missing = sorted(set(dependency_ids) - set(by_id))
    if missing:
        raise ValueError(f"dependency definitions missing from AST: {missing}")

    literals: set[str] = set()
    for definition_id in dependency_ids:
        node = _definition_node(ast, by_id[definition_id])
        for candidate in _walk(node):
            if candidate.get("type") != "CallExpression":
                continue
            if _callee_name(candidate.get("callee")) != "ee.ImageCollection":
                continue
            arguments = candidate.get("arguments") or []
            first = arguments[0] if arguments else None
            value = first.get("value") if isinstance(first, dict) else None
            if isinstance(value, str) and value:
                literals.add(value)
    if any(value.lower().startswith("users/") for value in literals):
        return []
    return sorted(literals)


def build_chain_faithful_text(
    row: dict[str, Any], facts: dict[str, Any]
) -> dict[str, str]:
    literals = sorted(set(str(value) for value in facts.get("dataset_literals") or []))
    collection = (
        f"the {literals[0]} ImageCollection"
        if len(literals) == 1
        else "the source ImageCollection"
    )
    temporal = temporal_phrase(str(row.get("temporal_description_policy") or ""))
    suffix = f" {temporal}" if temporal else ""
    return {
        "task_name": "Create a clipped mean image composite",
        "task_description": (
            f"Compute the mean image of {collection}{suffix}, then clip the result "
            "to the source-defined region."
        ),
    }


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def deduplicate_candidates(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (str(item.get("cluster_id")), str(item.get("source_sha256")))):
        key = (
            _normalized_text(row.get("task_name")),
            _normalized_text(row.get("task_description")),
            tuple(str(value) for value in row.get("l3_sequence") or []),
        )
        canonical = kept.get(key)
        if canonical is None:
            kept[key] = row
            continue
        duplicates.append(
            {
                "schema": "gis_recommend.gee_mean_clip_task_text_duplicate.v1",
                "canonical_cluster_id": canonical.get("cluster_id"),
                "canonical_source_sha256": canonical.get("source_sha256"),
                "duplicate_cluster_id": row.get("cluster_id"),
                "duplicate_source_sha256": row.get("source_sha256"),
                "dedup_key": "normalized_task_name_description_plus_l3_sequence",
                "training_admission": "not_granted_duplicate",
                "training_rows_emitted": 0,
            }
        )
    return list(kept.values()), duplicates


def _load_ast(path: Path) -> dict[str, Any]:
    with open(_filesystem_path(path), encoding="utf-8") as handle:
        ast = json.load(handle)
    if not isinstance(ast, dict) or ast.get("type") != "Program":
        raise ValueError(f"{path} is not an ESTree Program")
    return ast


def _find_one(paths: list[Path], label: str) -> Path:
    existing = [path for path in paths if path.is_file()]
    if len(existing) != 1:
        raise ValueError(f"expected one {label}; found {len(existing)}")
    return existing[0]


def _source_path(row: dict[str, Any], source_roots: tuple[Path, ...]) -> Path:
    relative = PurePosixPath(str(row["source_path"])).relative_to(SOURCE_PREFIX)
    native = Path(*relative.parts)
    return _find_one([root / native for root in source_roots], "source file")


def _candidate(row: dict[str, Any], ast: dict[str, Any]) -> dict[str, Any]:
    operators = tuple(str(value) for value in row.get("canonical_operator_sequence") or [])
    l3 = tuple(str(value) for value in row.get("l3_code_sequence") or [])
    if operators != EXPECTED_OPERATORS or l3 != EXPECTED_L3:
        raise ValueError(f"unexpected retained chain for cluster {row.get('cluster_id')}")

    literals = extract_dependency_dataset_literals(row, ast)
    text = build_chain_faithful_text(row, {"dataset_literals": literals})
    known_omissions = [
        "preprocessing_not_in_retained_chain",
        "region_domain_meaning_not_inferred",
    ]
    if len(literals) != 1:
        known_omissions.append("dataset_literal_omitted_when_not_unique_public")
    if not temporal_phrase(str(row.get("temporal_description_policy") or "")):
        known_omissions.append("unverified_temporal_facts_omitted")

    candidate = {
        "schema": SCHEMA,
        "review_id": str(row["cluster_id"]),
        "script_id": str(row["sample_id"]),
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "core_subworkflow",
        **text,
        "l3_sequence": list(l3),
        "operator_sequence": list(operators),
        "source_sha256": str(row["source_sha256"]),
        "source_path": str(row["source_path"]),
        "evidence_snippet": str(row["source_snippet"]),
        "admission_tier": "gee_core_p4_reviewed",
        "sample_weight": 0.5,
        "validation_eligible": False,
        "test_eligible": False,
        "description_policy": "template_chain_faithful",
        "known_omissions": known_omissions,
        "review_split": "train_only",
        "cluster_id": str(row["cluster_id"]),
        "source_definition_id": str(row["definition_id"]),
        "source_review_index": int(row["review_index"]),
        "dataset_literal_candidates": literals,
        "dataset_description_status": (
            "unique_public_literal" if len(literals) == 1 else "generic_source_collection"
        ),
        "temporal_description_policy": str(row["temporal_description_policy"]),
        "task_text_status": "generated_gate_passed",
        "training_admission": "not_granted_mean_clip_task_text_candidate",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    validate_core_train_row(candidate)
    if "source-defined region" not in candidate["task_description"]:
        raise ValueError("task text must use the conservative region description")
    return candidate


def build_candidates(
    rows: list[dict[str, Any]],
    source_roots: tuple[Path, ...],
    ast_dirs: tuple[Path, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    candidates: list[dict[str, Any]] = []
    evidence_paths: list[Path] = []
    for row in sorted(rows, key=lambda item: int(item["review_index"])):
        expected_sha = str(row["source_sha256"])
        source = _source_path(row, source_roots)
        if _sha256(source) != expected_sha:
            raise ValueError(f"source hash mismatch for {row.get('cluster_id')}")
        ast_path = _find_one(
            [directory / f"{expected_sha}.ast.json" for directory in ast_dirs],
            "AST cache file",
        )
        candidates.append(_candidate(row, _load_ast(ast_path)))
        evidence_paths.extend((source, ast_path))
    deduplicated, duplicates = deduplicate_candidates(candidates)
    return deduplicated, duplicates, evidence_paths


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return (
        "# GEE Mean/Clip Chain-Faithful Task Text v1\n\n"
        f"- Frozen input rows: {counts['input_rows']}\n"
        f"- Source/hash/AST verified: {counts['source_verified']}\n"
        f"- Unique public dataset literal: {counts['unique_public_dataset']}\n"
        f"- Generic source collection fallback: {counts['generic_dataset_fallback']}\n"
        f"- Deduplicated candidate rows: {counts['candidate_rows']}\n"
        f"- Duplicate rows removed: {counts['duplicates_removed']}\n"
        "- Retained chain: `ee.imagecollection.mean -> ee.image.clip`\n"
        "- Training/validation/test/production admission: not granted\n"
        "- Training rows emitted: 0\n"
    )


def write_outputs(
    candidates: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    input_path: Path,
    evidence_paths: list[Path],
    output_dir: Path,
) -> dict[str, Path]:
    paths = {
        "candidates": output_dir / "gee_mean_clip_task_text_candidate_v1.jsonl",
        "duplicates": output_dir / "gee_mean_clip_task_text_duplicates_v1.jsonl",
        "summary": output_dir / "gee_mean_clip_task_text_candidate_v1_summary.json",
        "report": output_dir / "gee_mean_clip_task_text_candidate_v1_report.md",
        "hash_ledger": output_dir / "gee_mean_clip_task_text_candidate_v1_hash_ledger.json",
    }
    input_rows = _load_jsonl(input_path)
    summary = {
        "schema": "gis_recommend.gee_mean_clip_task_text_candidate_summary.v1",
        "counts": {
            "input_rows": len(input_rows),
            "source_verified": len(input_rows),
            "unique_public_dataset": sum(
                row["dataset_description_status"] == "unique_public_literal"
                for row in candidates
            ),
            "generic_dataset_fallback": sum(
                row["dataset_description_status"] == "generic_source_collection"
                for row in candidates
            ),
            "candidate_rows": len(candidates),
            "duplicates_removed": len(duplicates),
            "schema_valid_rows": len(candidates),
            "training_rows_emitted": 0,
        },
        "task_text_gate": "passed_chain_faithful_source_backed",
        "dedup_key": "normalized_task_name_description_plus_l3_sequence",
        "training_admission": "not_granted_mean_clip_task_text_candidate",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    _atomic_write(paths["candidates"], _jsonl_text(candidates))
    _atomic_write(paths["duplicates"], _jsonl_text(duplicates))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            str(input_path): _sha256(input_path),
            **{str(path): _sha256(path) for path in evidence_paths},
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows = _load_jsonl(args.input_jsonl)
    candidates, duplicates, evidence_paths = build_candidates(
        rows, DEFAULT_SOURCE_ROOTS, DEFAULT_AST_DIRS
    )
    return write_outputs(
        candidates,
        duplicates,
        args.input_jsonl,
        evidence_paths,
        args.output_dir,
    )


if __name__ == "__main__":
    main()
