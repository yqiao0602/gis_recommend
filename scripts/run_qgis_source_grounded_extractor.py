#!/usr/bin/env python3
"""Run the deterministic source-grounded QGIS extractor on review selections."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_source_grounded_extractor import (
    compile_source_grounded_record,
)


class ExtractorCliError(RuntimeError):
    """Raised when an input violates the extractor run contract."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _assert_allowed(path: Path, roots: list[Path], label: str) -> Path:
    resolved = path.resolve()
    if not roots:
        raise ExtractorCliError(f"no allowed root configured for {label}")
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise ExtractorCliError(f"{label} is outside allowed roots: {resolved}")
    return resolved


def _parse_remaps(values: list[str]) -> list[tuple[str, str]]:
    remaps = []
    for value in values:
        if "=" not in value:
            raise ExtractorCliError(
                f"invalid --source-root-remap {value!r}; expected OLD=NEW"
            )
        old, new = value.split("=", 1)
        old = old.strip()
        new = new.strip()
        if old not in {"/", "\\"}:
            old = old.rstrip("/\\")
        if not old or not new:
            raise ExtractorCliError(f"invalid --source-root-remap {value!r}")
        remaps.append((old, new))
    return remaps


def _remap_source_path(path: str, remaps: list[tuple[str, str]]) -> Path:
    for old, new in remaps:
        if path == old:
            return Path(new)
        for separator in ("/", "\\"):
            prefix = old + separator
            if path.startswith(prefix):
                suffix = path[len(prefix) :].replace("\\", "/")
                return Path(new) / Path(suffix)
    return Path(path)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ExtractorCliError(
                    f"expected object at {path}:{line_number}"
                )
            rows.append(value)
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _require_fields(
    rows: list[dict[str, Any]], required: set[str], label: str
) -> None:
    if not rows:
        raise ExtractorCliError(f"{label} is empty")
    for row_number, row in enumerate(rows, start=1):
        missing = sorted(
            field
            for field in required
            if field not in row or row.get(field) is None or row.get(field) == ""
        )
        if missing:
            raise ExtractorCliError(
                f"{label} missing required fields at row {row_number}: {', '.join(missing)}"
            )


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        result = {}
        for row in _read_csv(path):
            operator_id = next(
                (
                    row.get(key)
                    for key in ("alg_id", "operator_id", "id")
                    if row.get(key)
                ),
                None,
            )
            if operator_id and ":" in operator_id:
                result[operator_id.strip().lower()] = row
        if result:
            return result
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row_number, columns in enumerate(csv.reader(handle), start=1):
                if len(columns) <= 5:
                    continue
                operator_id = columns[5].strip().lower()
                if ":" in operator_id and " " not in operator_id:
                    result[operator_id] = {
                        "provider": columns[0],
                        "display_name": columns[2],
                        "operator_id": operator_id,
                        "source_row": row_number,
                    }
        return result

    value = _read_json(path)
    if isinstance(value, dict) and all(":" in str(key) for key in value):
        return {str(key).lower(): item for key, item in value.items()}
    candidates = value.get("operators", []) if isinstance(value, dict) else value
    if not isinstance(candidates, list):
        raise ExtractorCliError(f"unsupported catalog schema: {path}")
    result = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        operator_id = item.get("alg_id") or item.get("operator_id") or item.get("id")
        if isinstance(operator_id, str) and ":" in operator_id:
            result[operator_id.strip().lower()] = item
    return result


def _artifact_paths_and_hashes(
    artifact_hashes: dict[str, Any], group: str
) -> list[tuple[str, str | None]]:
    paths = list(artifact_hashes.get(f"{group}_paths") or [])
    hashes = list(artifact_hashes.get(f"{group}_hashes") or [])
    if not hashes and len(paths) == 1:
        singular_hash = artifact_hashes.get(f"{group}_sha256")
        hashes = [singular_hash] if singular_hash else []
    if hashes and len(paths) != len(hashes):
        raise ExtractorCliError(
            f"{group} path/hash count mismatch: {len(paths)} paths, {len(hashes)} hashes"
        )
    return [
        (str(path), str(hashes[index]) if hashes else None)
        for index, path in enumerate(paths)
    ]


def _step_channel(row: dict[str, Any]) -> str:
    source_type = str(row.get("api_source_type") or "").strip().lower()
    operation = str(
        row.get("normalized_api_name") or row.get("operation") or ""
    ).strip().lower()
    if source_type == "qgis_processing_algorithm":
        return "processing_algorithms"
    if source_type in {"custom_processing_algorithm", "qgis_custom_algorithm"}:
        return "custom_algorithms"
    if source_type in {"qgis_api", "gdal_api", "qgis_cpp_api", "direct_api"}:
        return "direct_api"
    if operation.startswith(("qgs", "gdal.", "ogr.")):
        return "direct_api"
    if operation.startswith(("native:", "qgis:", "gdal:", "grass7:", "saga:")):
        return "processing_algorithms"
    return "unresolved_fragments"


def _semantic_step_id(row: dict[str, Any], ordinal: int) -> str:
    step_id = str(row.get("id") or row.get("step_id") or ordinal)
    for prefix in ("macro_", "micro_"):
        if step_id.startswith(prefix):
            return step_id[len(prefix) :]
    return step_id


def _parse_step_arguments(value: Any) -> Any:
    if not isinstance(value, str):
        return value if value is not None else []
    if not value.strip():
        return []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return [{"type": "unparsed", "value": value}]


def _ordered_steps_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps = []
    all_statement_indices_valid = True
    for ordinal, row in enumerate(rows):
        try:
            statement_index = int(row.get("statement_index"))
        except (TypeError, ValueError):
            statement_index = None
            all_statement_indices_valid = False
        step_id = str(row.get("id") or row.get("step_id") or ordinal)
        steps.append(
            {
                "step_id": step_id,
                "evidence_id": step_id,
                "statement_index": statement_index,
                "source_line": next(
                    (
                        int(row[key])
                        for key in ("source_line", "lineno", "line")
                        if str(row.get(key) or "").isdigit()
                    ),
                    None,
                ),
                "operation": str(
                    row.get("normalized_api_name") or row.get("operation") or ""
                ),
                "channel": _step_channel(row),
                "semantic_step_id": _semantic_step_id(row, ordinal),
                "arguments": _parse_step_arguments(
                    row.get("args", row.get("arguments"))
                ),
                "input_roles": _parse_step_arguments(row.get("input_roles")),
                "output_roles": _parse_step_arguments(row.get("output_roles")),
                "dependencies": _parse_step_arguments(
                    row.get("dependencies", row.get("dependency_ids"))
                ),
                "scope": row.get("scope") or row.get("function_name"),
                "step_level": row.get("step_level"),
                "parent_step_id": row.get("parent_step_id"),
                "extraction_order": ordinal,
            }
        )
    if all_statement_indices_valid:
        steps.sort(key=lambda item: (item["statement_index"], item["extraction_order"]))
    return steps


def _load_verified_sources(
    selection: dict[str, Any],
    *,
    allowed_read_roots: list[Path],
    remaps: list[tuple[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    artifact_hashes = dict(selection.get("artifact_hashes") or {})
    source_ledger = {"ast": [], "steps": []}

    ast_records = []
    ast_actual_hashes = set()
    for original_path, expected_hash in _artifact_paths_and_hashes(
        artifact_hashes, "ast"
    ):
        path = _assert_allowed(
            _remap_source_path(original_path, remaps),
            allowed_read_roots,
            "AST source",
        )
        if not path.is_file():
            raise ExtractorCliError(f"AST source does not exist: {path}")
        actual_hash = _sha256(path)
        ast_actual_hashes.add(actual_hash)
        if expected_hash and actual_hash != expected_hash:
            raise ExtractorCliError(f"AST SHA256 mismatch: {path}")
        value = _read_json(path)
        if isinstance(value, list):
            value = {"type": "Module", "body": value}
        if not isinstance(value, dict):
            raise ExtractorCliError(f"AST source is not an object/list: {path}")
        ast_records.append(value)
        source_ledger["ast"].append(
            {"original_path": original_path, "resolved_path": str(path), "sha256": actual_hash}
        )

    step_tables = []
    step_actual_hashes = set()
    for original_path, expected_hash in _artifact_paths_and_hashes(
        artifact_hashes, "steps"
    ):
        path = _assert_allowed(
            _remap_source_path(original_path, remaps),
            allowed_read_roots,
            "steps source",
        )
        if not path.is_file():
            raise ExtractorCliError(f"steps source does not exist: {path}")
        actual_hash = _sha256(path)
        step_actual_hashes.add(actual_hash)
        if expected_hash and actual_hash != expected_hash:
            raise ExtractorCliError(f"steps SHA256 mismatch: {path}")
        step_tables.append(_read_csv(path))
        source_ledger["steps"].append(
            {"original_path": original_path, "resolved_path": str(path), "sha256": actual_hash}
        )

    if not ast_records:
        raise ExtractorCliError(
            f"selection {selection.get('record_id')} has no AST source"
        )
    if len(ast_actual_hashes) > 1:
        raise ExtractorCliError(
            f"selection {selection.get('record_id')} has multiple distinct AST sources"
        )
    if len(step_actual_hashes) > 1:
        raise ExtractorCliError(
            f"selection {selection.get('record_id')} has multiple distinct steps sources"
        )
    ast_record = ast_records[0]
    step_rows = step_tables[0] if step_tables else []
    ordered_steps = _ordered_steps_from_rows(step_rows)
    return ast_record, ordered_steps, source_ledger


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "review_order",
        "record_id",
        "source_script",
        "operator_chain_json",
        "parallel_ast_operator_chain_json",
        "supporting_operator_chain_json",
        "custom_components_json",
        "unsupported_evidence_count",
        "evidence_tiers_json",
        "cross_source_ordering",
        "reviewer_status",
        "taxonomy_admission",
        "training_admission",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "review_order": row["review_order"],
                    "record_id": row["record_id"],
                    "source_script": row.get("source_script", ""),
                    "operator_chain_json": _canonical_json(row["operator_chain"]),
                    "parallel_ast_operator_chain_json": _canonical_json(
                        row["parallel_ast_operator_chain"]
                    ),
                    "supporting_operator_chain_json": _canonical_json(
                        row["supporting_operator_chain"]
                    ),
                    "custom_components_json": _canonical_json(
                        row["custom_components"]
                    ),
                    "unsupported_evidence_count": len(row["unsupported_evidence"]),
                    "evidence_tiers_json": _canonical_json(row["evidence_tiers"]),
                    "cross_source_ordering": row["cross_source_ordering"],
                    "reviewer_status": row["reviewer_status"],
                    "taxonomy_admission": row["taxonomy_admission"],
                    "training_admission": row["training_admission"],
                }
            )


def _evaluate_regression(
    extraction: dict[str, Any], adjudication: dict[str, Any]
) -> dict[str, Any]:
    primary_chain = list(extraction.get("operator_chain") or [])
    grounded_chain = primary_chain + list(
        extraction.get("parallel_ast_operator_chain") or []
    )
    grounded_ids = set(grounded_chain)
    expected_ids = [str(value) for value in adjudication.get("expected_operator_ids") or []]
    adjudication_failure_tags = {
        str(tag) for tag in adjudication.get("failure_tags") or []
    }
    expected_custom = bool(adjudication.get("expected_custom")) or (
        "custom_operator_not_in_catalog" in adjudication_failure_tags
    )
    top1_correct = adjudication.get("top1_correct")
    top1_operator_id = str(adjudication.get("top1_operator_id") or "")

    checks = []
    failure_tags = []
    evidence_tags = [
        f"evidence_tier:{tier}"
        for tier in extraction.get("evidence_tiers", [])
    ]
    evidence_tags.append(
        f"cross_source_ordering:{extraction.get('cross_source_ordering', 'unknown')}"
    )
    evidence_tags.extend(
        f"unsupported_category:{category}"
        for category in sorted(
            {
                str(item.get("category") or "unknown")
                for item in extraction.get("unsupported_evidence", [])
            }
        )
    )
    if extraction.get("custom_components"):
        evidence_tags.append("custom_components_present")
    forbidden_top1_avoided = None
    correct_top1_recovered = None
    if top1_correct is False and top1_operator_id:
        forbidden_top1_avoided = top1_operator_id not in primary_chain
        checks.append("forbidden_top1_avoidance")
        if not forbidden_top1_avoided:
            failure_tags.append(f"forbidden_top1_selected:{top1_operator_id}")
    elif top1_correct is True and top1_operator_id:
        correct_top1_recovered = top1_operator_id in grounded_ids
        checks.append("correct_top1_recovery")
        if not correct_top1_recovered:
            failure_tags.append(f"correct_top1_missing:{top1_operator_id}")

    expected_recovered = [
        operator_id for operator_id in expected_ids if operator_id in grounded_ids
    ]
    if expected_ids:
        checks.append("expected_operator_recovery")
        failure_tags.extend(
            f"missing_expected_operator:{operator_id}"
            for operator_id in expected_ids
            if operator_id not in grounded_ids
        )

    custom_recovered = None
    if expected_custom:
        custom_recovered = bool(extraction.get("custom_components"))
        checks.append("custom_recovery")
        if not custom_recovered:
            failure_tags.append("expected_custom_not_recovered")

    if not checks:
        failure_tags.append("not_measurable_incomplete_adjudication")

    return {
        "review_order": extraction["review_order"],
        "record_id": extraction["record_id"],
        "measurement_status": "measurable" if checks else "not_measurable",
        "measured_checks": checks,
        "failure_tags": sorted(failure_tags),
        "evidence_tags": sorted(set(evidence_tags)),
        "top1_operator_id": top1_operator_id or None,
        "top1_correct": top1_correct,
        "forbidden_top1_avoided": forbidden_top1_avoided,
        "correct_top1_recovered": correct_top1_recovered,
        "expected_operator_ids": expected_ids,
        "expected_operator_ids_recovered": expected_recovered,
        "all_expected_operator_ids_recovered": (
            len(expected_recovered) == len(expected_ids) if expected_ids else None
        ),
        "expected_custom": expected_custom,
        "custom_recovered": custom_recovered,
        "operator_chain": primary_chain,
        "parallel_ast_operator_chain": extraction.get(
            "parallel_ast_operator_chain", []
        ),
        "evidence_tiers": extraction.get("evidence_tiers", []),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-jsonl", required=True)
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--adjudications")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--source-root-remap", action="append", default=[])
    parser.add_argument("--allowed-read-root", action="append", default=[])
    parser.add_argument("--allowed-output-root", action="append", default=[])
    parser.add_argument("--review-order-start", type=int, default=1)
    parser.add_argument("--review-order-end", type=int)
    parser.add_argument("--output-dir", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--regression-mode", action="store_true")
    mode.add_argument("--blind-mode", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.blind_mode and args.adjudications:
        parser.error("blind mode forbids --adjudications and must not read labels")
    if args.regression_mode and not args.adjudications:
        parser.error("regression mode requires --adjudications")

    try:
        allowed_read_roots = [_resolved(value) for value in args.allowed_read_root]
        allowed_output_roots = [
            _resolved(value) for value in args.allowed_output_root
        ]
        remaps = _parse_remaps(args.source_root_remap)
        selection_path = _assert_allowed(
            _resolved(args.selection_jsonl), allowed_read_roots, "selection JSONL"
        )
        review_path = _assert_allowed(
            _resolved(args.review_csv), allowed_read_roots, "review CSV"
        )
        catalog_path = _assert_allowed(
            _resolved(args.catalog), allowed_read_roots, "catalog"
        )
        adjudications_path = None
        if args.adjudications:
            adjudications_path = _assert_allowed(
                _resolved(args.adjudications),
                allowed_read_roots,
                "adjudications",
            )
        output_dir = _assert_allowed(
            _resolved(args.output_dir), allowed_output_roots, "output directory"
        )
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ExtractorCliError(
                f"output directory is not empty; use a new versioned path: {output_dir}"
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        selections = _read_jsonl(selection_path)
        review_rows = _read_csv(review_path)
        _require_fields(
            selections,
            {"record_id", "artifact_hashes"},
            "selection JSONL",
        )
        _require_fields(
            review_rows,
            {"review_order", "record_id"},
            "review CSV",
        )
        review_by_id = {row["record_id"]: row for row in review_rows}
        selected = []
        for selection in selections:
            review = review_by_id.get(str(selection.get("record_id")))
            if review is None:
                continue
            review_order = int(review["review_order"])
            if review_order < args.review_order_start:
                continue
            if args.review_order_end is not None and review_order > args.review_order_end:
                continue
            selected.append((review_order, selection, review))
        selected.sort(key=lambda item: (item[0], str(item[1].get("record_id"))))
        if not selected:
            raise ExtractorCliError("no records selected for the requested review range")

        catalog = _load_catalog(catalog_path)
        if not catalog:
            raise ExtractorCliError(f"catalog contains no provider-qualified IDs: {catalog_path}")

        extractions = []
        for review_order, selection, review in selected:
            ast_record, ordered_steps, source_ledger = _load_verified_sources(
                selection,
                allowed_read_roots=allowed_read_roots,
                remaps=remaps,
            )
            extracted = compile_source_grounded_record(
                ast_record,
                ordered_steps,
                catalog,
                task_text_provenance={
                    "source": "selection_jsonl",
                    "task_name_present": bool(selection.get("task_name")),
                    "task_description_present": bool(
                        selection.get("task_description")
                    ),
                },
            )
            extractions.append(
                {
                    "schema_version": "qgis_source_grounded_extraction_v1",
                    "review_order": review_order,
                    "record_id": str(selection.get("record_id")),
                    "source_script": selection.get("source_script"),
                    "task_name": selection.get("task_name"),
                    "task_description": selection.get("task_description"),
                    "candidate_status": review.get("candidate_status"),
                    "source_artifacts": source_ledger,
                    **extracted,
                }
            )

        regression_rows = []
        labels_read = False
        if args.regression_mode:
            adjudications = _read_jsonl(adjudications_path)
            _require_fields(
                adjudications,
                {"review_order", "record_id"},
                "adjudications JSONL",
            )
            labels_read = True
            adjudications_by_id = {
                str(row.get("record_id")): row for row in adjudications
            }
            for extraction in extractions:
                adjudication = adjudications_by_id.get(extraction["record_id"])
                if adjudication is None:
                    raise ExtractorCliError(
                        f"missing adjudication for {extraction['record_id']}"
                    )
                regression_rows.append(
                    _evaluate_regression(extraction, adjudication)
                )

        tier_counts = Counter(
            tier for row in extractions for tier in row.get("evidence_tiers", [])
        )
        measurable_rows = sum(
            row["measurement_status"] == "measurable" for row in regression_rows
        )
        expected_total = sum(
            len(row["expected_operator_ids"]) for row in regression_rows
        )
        expected_recovered = sum(
            len(row["expected_operator_ids_recovered"])
            for row in regression_rows
        )
        summary = {
            "schema_version": "qgis_source_grounded_extractor_summary_v1",
            "mode": "blind"
            if args.blind_mode
            else "regression",
            "review_order_start": args.review_order_start,
            "review_order_end": args.review_order_end,
            "records_extracted": len(extractions),
            "labels_read": labels_read,
            "measurable_rows": measurable_rows,
            "not_measurable_rows": len(regression_rows) - measurable_rows,
            "expected_operator_count": expected_total,
            "expected_operator_recovered_count": expected_recovered,
            "expected_operator_recall": (
                expected_recovered / expected_total if expected_total else None
            ),
            "forbidden_top1_checks": sum(
                row["forbidden_top1_avoided"] is not None
                for row in regression_rows
            ),
            "forbidden_top1_avoided": sum(
                row["forbidden_top1_avoided"] is True
                for row in regression_rows
            ),
            "correct_top1_checks": sum(
                row["correct_top1_recovered"] is not None
                for row in regression_rows
            ),
            "correct_top1_recovered": sum(
                row["correct_top1_recovered"] is True
                for row in regression_rows
            ),
            "custom_checks": sum(
                row["custom_recovered"] is not None for row in regression_rows
            ),
            "custom_recovered": sum(
                row["custom_recovered"] is True for row in regression_rows
            ),
            "evidence_tier_record_counts": dict(sorted(tier_counts.items())),
            "failure_tag_counts": dict(
                sorted(
                    Counter(
                        tag for row in regression_rows for tag in row["failure_tags"]
                    ).items()
                )
            ),
            "evidence_tag_counts": dict(
                sorted(
                    Counter(
                        tag for row in regression_rows for tag in row["evidence_tags"]
                    ).items()
                )
            ),
            "taxonomy_admission": "not_granted",
            "training_admission": "not_granted",
            "training_rows_emitted": 0,
        }

        _write_jsonl(output_dir / "extractions.jsonl", extractions)
        if args.regression_mode:
            _write_jsonl(
                output_dir / "regression_results.jsonl", regression_rows
            )
        _write_review_csv(output_dir / "review_workbook.csv", extractions)
        _write_json(output_dir / "summary.json", summary)

        input_paths = [selection_path, review_path, catalog_path]
        if adjudications_path is not None:
            input_paths.append(adjudications_path)
        output_paths = sorted(
            path for path in output_dir.iterdir() if path.name != "hash_ledger.json"
        )
        source_inputs_by_identity = {}
        for extraction in extractions:
            for group in ("ast", "steps"):
                for item in extraction["source_artifacts"].get(group, []):
                    identity = (item["resolved_path"], item["sha256"])
                    source_inputs_by_identity[identity] = {
                        "group": group,
                        **item,
                    }
        ledger = {
            "schema_version": "qgis_source_grounded_hash_ledger_v1",
            "inputs": {
                str(path): {"sha256": _sha256(path), "size": path.stat().st_size}
                for path in input_paths
            },
            "outputs": {
                path.name: {"sha256": _sha256(path), "size": path.stat().st_size}
                for path in output_paths
            },
            "source_inputs": [
                source_inputs_by_identity[key]
                for key in sorted(source_inputs_by_identity)
            ],
            "extractor_code": {
                "cli_sha256": _sha256(Path(__file__).resolve()),
                "module_sha256": _sha256(
                    SRC
                    / "gis_recommend"
                    / "data"
                    / "qgis_source_grounded_extractor.py"
                ),
            },
            "labels_read": labels_read,
            "taxonomy_admission": "not_granted",
            "training_rows_emitted": 0,
        }
        _write_json(output_dir / "hash_ledger.json", ledger)
        print(_canonical_json(summary))
        return 0
    except (ExtractorCliError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
