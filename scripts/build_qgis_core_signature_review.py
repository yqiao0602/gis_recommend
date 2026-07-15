#!/usr/bin/env python3
"""Build a review-only QGIS Core Processing operator-signature package.

The source traces describe Processing algorithm implementations. They are
operator anchors, not independent workflow training examples. This builder
never emits training rows and never resolves an ambiguous catalog match.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "qgis_core_signature_review_v1"
CLASS_SCOPE_RE = re.compile(r"(?:^|/)class_(?P<name>[A-Za-z0-9_]+)_\d+(?:/|$)")
PARAMETER_RE = re.compile(r"(?:QgsProcessing)?Parameter(?P<kind>[A-Za-z0-9_]+)$")
OUTPUT_PARAMETER_MARKERS = ("destination", "sink", "output")
OUTPUT_IDENTIFIERS = {"OUTPUT", "RESULT", "DESTINATION"}
PROVIDER_GROUP_BY_PREFIX = {
    "3d": "qgis",
    "gdal": "gdal",
    "grass": "grass",
    "grass7": "grass",
    "native": "qgis",
    "otb": "otb",
    "qgis": "qgis",
    "saga": "saga",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _name_tokens(value: str) -> set[str]:
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|\d+", value)
    if not words:
        words = re.findall(r"[a-z0-9]+", value.lower())
    return {word.lower() for word in words if len(word) >= 3}


def _operator_provider_group(operator_id: str) -> str:
    prefix = operator_id.split(":", 1)[0].lower()
    return PROVIDER_GROUP_BY_PREFIX.get(prefix, prefix)


def _catalog_parameter_direction(identifier: str, data_type: str) -> str:
    identifier_upper = identifier.upper()
    non_literal_output = data_type.lower() != "literaldata" and (
        identifier_upper.startswith("OUTPUT") or identifier_upper.endswith("_OUTPUT")
    )
    if identifier_upper in OUTPUT_IDENTIFIERS or "DESTINATION" in identifier_upper or non_literal_output:
        return "output"
    return "input"


def load_qgis_catalog(path: str | Path) -> list[dict[str, Any]]:
    """Parse the fixed-width catalog with the CSV parser, including multiline cells."""
    path = Path(path)
    operators: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.reader(handle), start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) < 6:
                raise ValueError(f"catalog row {row_number} has fewer than six columns")
            operator_id = row[5].strip()
            if ":" not in operator_id:
                raise ValueError(f"catalog row {row_number} has invalid operator id: {operator_id!r}")
            parameters = []
            remainder = row[6:]
            for offset in range(0, len(remainder), 7):
                chunk = remainder[offset : offset + 7]
                chunk += [""] * (7 - len(chunk))
                if not any(cell.strip() for cell in chunk):
                    continue
                identifier, label, source_name, minimum, maximum, data_type, formats = (
                    cell.strip() for cell in chunk
                )
                parameters.append(
                    {
                        "identifier": identifier,
                        "label": label,
                        "source_name": source_name,
                        "minimum_occurs": minimum,
                        "maximum_occurs": maximum,
                        "data_type": data_type,
                        "formats": formats,
                        "direction": _catalog_parameter_direction(identifier, data_type),
                    }
                )
            slug = operator_id.split(":", 1)[1]
            operators.append(
                {
                    "operator_id": operator_id,
                    "provider": row[0].strip(),
                    "provider_version": row[1].strip(),
                    "official_name": row[2].strip(),
                    "catalog_record_id": row[3].strip(),
                    "description": row[4],
                    "provider_group": _operator_provider_group(operator_id),
                    "normalized_slug": _normalize_name(slug),
                    "normalized_name": _normalize_name(row[2]),
                    "parameters": parameters,
                }
            )
    return operators


def _walk_json(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_json(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_json(value)


def _ast_name(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "Name":
        return str(node.get("id") or "")
    if node_type == "Attribute":
        prefix = _ast_name(node.get("value"))
        suffix = str(node.get("attr") or "")
        return ".".join(part for part in (prefix, suffix) if part)
    return str(node.get("id") or node.get("name") or "")


def _read_ast_evidence(path: Path | None) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    if path is None or not path.is_file():
        return [], {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    imports: list[dict[str, Any]] = []
    class_bases: dict[str, list[str]] = {}
    for node in _walk_json(payload):
        node_type = node.get("type")
        if node_type == "ImportFrom":
            names = [
                {"name": item.get("name", ""), "asname": item.get("asname")}
                for item in node.get("names", [])
                if isinstance(item, dict)
            ]
            imports.append(
                {
                    "kind": "from",
                    "module": str(node.get("module") or ""),
                    "names": names,
                }
            )
        elif node_type == "Import":
            for item in node.get("names", []):
                if isinstance(item, dict):
                    imports.append(
                        {
                            "kind": "import",
                            "module": str(item.get("name") or ""),
                            "names": [],
                            "asname": item.get("asname"),
                        }
                    )
        elif node_type == "ClassDef":
            class_name = str(node.get("name") or "")
            if class_name:
                class_bases[class_name] = [
                    name for name in (_ast_name(base) for base in node.get("bases", [])) if name
                ]
    imports.sort(key=lambda item: (item["module"], _json_dump(item.get("names", []))))
    return imports, class_bases


def _class_name_from_scope(scope: str) -> str:
    match = CLASS_SCOPE_RE.search(scope)
    return match.group("name") if match else ""


def _parse_args(raw_args: str) -> tuple[Any, bool]:
    if not raw_args.strip():
        return [], False
    try:
        return json.loads(raw_args), False
    except json.JSONDecodeError:
        return raw_args, True


def _iter_argument_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_argument_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_argument_nodes(child)


def _extract_parameter_identity(args: Any) -> tuple[str, str]:
    identifier = ""
    label = ""
    for node in _iter_argument_nodes(args):
        if not identifier and node.get("type") == "MemberExpression":
            expression = str(node.get("expr") or "")
            if expression.startswith("self."):
                identifier = expression.split(".", 1)[1]
        if node.get("type") == "CallExpression" and str(node.get("callee") or "").endswith(".tr"):
            for child in _iter_argument_nodes(node.get("args", [])):
                value = child.get("value")
                if isinstance(value, str) and value.strip():
                    label = value.strip()
                    break
        if identifier and label:
            break
    return identifier, label


def _statement_index(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parameter_direction(parameter_type: str, identifier: str) -> str:
    text = parameter_type.lower()
    if any(marker in text for marker in OUTPUT_PARAMETER_MARKERS):
        return "output"
    if identifier.upper() in OUTPUT_IDENTIFIERS or "OUTPUT" in identifier.upper():
        return "output"
    return "input"


def _providers_from_text(value: str) -> set[str]:
    lowered = value.lower()
    providers = set()
    if re.search(r"\b(?:gdal|ogr)", lowered):
        providers.add("gdal")
    if "grass" in lowered:
        providers.add("grass")
    if "saga" in lowered:
        providers.add("saga")
    if "orfeo" in lowered or re.search(r"(?:^|[._/])otb(?:[._/]|$)", lowered):
        providers.add("otb")
    if "processing.algs.qgis" in lowered or "qgisalgorithm" in lowered:
        providers.add("qgis")
    return providers


def _build_provider_evidence(
    imports: list[dict[str, Any]],
    bases: list[str],
    calls: list[dict[str, Any]],
) -> dict[str, Any]:
    signals: list[dict[str, str]] = []
    for item in imports:
        text = " ".join(
            [item.get("module", "")]
            + [name.get("name", "") for name in item.get("names", [])]
        )
        for provider in sorted(_providers_from_text(text)):
            signals.append({"provider": provider, "source": "import", "value": text})
    for base in bases:
        for provider in sorted(_providers_from_text(base)):
            signals.append({"provider": provider, "source": "class_base", "value": base})
    for call in calls:
        text = " ".join(
            str(call.get(key) or "")
            for key in ("operation", "semantic_role", "description")
        )
        for provider in sorted(_providers_from_text(text)):
            signals.append(
                {
                    "provider": provider,
                    "source": "trace_call",
                    "value": str(call.get("operation") or ""),
                }
            )
    unique = {
        (signal["provider"], signal["source"], signal["value"]): signal
        for signal in signals
    }
    ordered = [unique[key] for key in sorted(unique)]
    return {
        "providers": sorted({signal["provider"] for signal in ordered}),
        "signals": ordered,
    }


def _source_path(path: Path, source_root: Path) -> str:
    try:
        return path.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def extract_trace_record(
    trace_path: str | Path,
    *,
    ast_path: str | Path | None = None,
    source_root: str | Path | None = None,
) -> dict[str, Any]:
    trace_path = Path(trace_path)
    source_root = Path(source_root) if source_root is not None else trace_path.parent
    if ast_path is None:
        candidate = trace_path.with_name(trace_path.name.replace("_steps.csv", "_ast.json"))
        ast_path = candidate if candidate.is_file() else None
    else:
        ast_path = Path(ast_path)
    imports, class_bases = _read_ast_evidence(ast_path)

    with trace_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    calls_by_class: dict[str, list[dict[str, Any]]] = {}
    parameters_by_class: dict[str, dict[tuple[str, str, str, str], dict[str, Any]]] = {}
    for source_order, row in enumerate(rows):
        scope = str(row.get("scope") or "")
        class_name = _class_name_from_scope(scope)
        if not class_name:
            continue
        raw_args = str(row.get("args") or "")
        structured_args, args_parse_error = _parse_args(raw_args)
        operation = str(row.get("normalized_api_name") or row.get("name") or "")
        call = {
            "evidence_id": str(row.get("id") or f"row_{source_order}"),
            "operation": operation,
            "structured_args": structured_args,
            "args_parse_error": args_parse_error,
            "api_source_type": str(row.get("api_source_type") or ""),
            "semantic_role": str(row.get("semantic_role") or ""),
            "input_type": str(row.get("input_type") or ""),
            "output_type": str(row.get("output_type") or ""),
            "description": str(row.get("description") or ""),
            "scope": scope,
            "statement_index": _statement_index(str(row.get("statement_index") or "")),
            "source_order": source_order,
        }
        calls_by_class.setdefault(class_name, []).append(call)

        parameter_match = PARAMETER_RE.search(operation)
        if not parameter_match or operation.startswith("QgsProcessingAlgorithm."):
            continue
        parameter_type = parameter_match.group("kind")
        identifier, label = _extract_parameter_identity(structured_args)
        direction = _parameter_direction(parameter_type, identifier)
        key = (identifier, label, parameter_type, direction)
        class_parameters = parameters_by_class.setdefault(class_name, {})
        if key not in class_parameters:
            class_parameters[key] = {
                "identifier": identifier,
                "label": label,
                "parameter_type": parameter_type,
                "direction": direction,
                "trace_input_type": call["input_type"],
                "trace_output_type": call["output_type"],
                "first_statement_index": call["statement_index"],
                "evidence_ids": [],
                "structured_args": structured_args,
            }
        class_parameters[key]["evidence_ids"].append(call["evidence_id"])

    signatures = []
    for class_name in sorted(calls_by_class):
        calls = sorted(
            calls_by_class[class_name],
            key=lambda call: (
                call["statement_index"] is None,
                call["statement_index"] if call["statement_index"] is not None else 0,
                call["source_order"],
                call["evidence_id"],
            ),
        )
        parameters = list(parameters_by_class.get(class_name, {}).values())
        parameters.sort(
            key=lambda item: (
                item["first_statement_index"] is None,
                item["first_statement_index"] if item["first_statement_index"] is not None else 0,
                item["identifier"],
                item["label"],
            )
        )
        signatures.append(
            {
                "class_name": class_name,
                "normalized_class_name": _normalize_name(class_name),
                "class_bases": class_bases.get(class_name, []),
                "scopes": sorted({call["scope"] for call in calls}),
                "parameters": parameters,
                "input_parameters": [item for item in parameters if item["direction"] == "input"],
                "output_parameters": [item for item in parameters if item["direction"] == "output"],
                "ordered_calls": calls,
                "provider_evidence": _build_provider_evidence(
                    imports,
                    class_bases.get(class_name, []),
                    calls,
                ),
            }
        )

    record_id = trace_path.name.removesuffix("_steps.csv")
    source = {
        "trace_path": _source_path(trace_path, source_root),
        "trace_sha256": _sha256(trace_path),
        "trace_rows": len(rows),
        "ast_path": _source_path(ast_path, source_root) if ast_path is not None else "",
        "ast_sha256": _sha256(ast_path) if ast_path is not None and ast_path.is_file() else "",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "source": source,
        "imports": imports,
        "class_signatures": signatures,
        "training_admission": "forbidden_until_human_review",
    }


def _candidate_score(signature: dict[str, Any], operator: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    signals = []
    class_normalized = signature["normalized_class_name"]
    if class_normalized in {operator["normalized_slug"], operator["normalized_name"]}:
        score += 1000
        signals.append("exact_class_name")
    else:
        class_tokens = _name_tokens(signature["class_name"])
        operator_tokens = _name_tokens(operator["official_name"])
        overlap = sorted(class_tokens & operator_tokens)
        if overlap:
            score += 30 * len(overlap)
            signals.append("class_tokens:" + ",".join(overlap))
        if class_normalized and (
            class_normalized in operator["normalized_slug"]
            or operator["normalized_slug"] in class_normalized
        ):
            score += 80
            signals.append("class_substring")

    search_text = " ".join(
        [operator["official_name"], operator["description"]]
        + [item["label"] for item in operator["parameters"]]
    ).lower()
    for parameter in signature.get("parameters", []):
        label = parameter.get("label", "").strip().lower()
        if label and label in search_text:
            score += 12
            signals.append(f"parameter_label:{label}")
    signature_types = {
        parameter.get("parameter_type", "").lower()
        for parameter in signature.get("parameters", [])
        if parameter.get("parameter_type")
    }
    catalog_types = {
        parameter.get("data_type", "").lower()
        for parameter in operator.get("parameters", [])
        if parameter.get("data_type")
    }
    type_overlap = sorted(signature_types & catalog_types)
    if type_overlap:
        score += 4 * len(type_overlap)
        signals.append("schema_types:" + ",".join(type_overlap))
    return score, signals


def _public_candidate(operator: dict[str, Any], score: int, signals: list[str]) -> dict[str, Any]:
    return {
        "operator_id": operator["operator_id"],
        "official_name": operator["official_name"],
        "provider": operator["provider"],
        "provider_group": operator["provider_group"],
        "score": score,
        "match_signals": signals,
        "parameters": operator["parameters"],
    }


def build_catalog_candidates(
    signature: dict[str, Any],
    catalog: list[dict[str, Any]],
    *,
    limit: int = 15,
) -> dict[str, Any]:
    scored = []
    exact = []
    for operator in catalog:
        score, signals = _candidate_score(signature, operator)
        if score <= 0:
            continue
        candidate = _public_candidate(operator, score, signals)
        scored.append(candidate)
        if "exact_class_name" in signals:
            exact.append(candidate)
    scored.sort(key=lambda item: (-item["score"], item["operator_id"]))
    exact.sort(key=lambda item: item["operator_id"])

    provider_evidence = set(signature.get("provider_evidence", {}).get("providers", []))
    provider_consistent = [
        item
        for item in exact
        if not provider_evidence or item["provider_group"] in provider_evidence
    ]
    auto_proposed = ""
    if exact and len(provider_evidence) > 1:
        status = "unresolved_provider_evidence_ambiguous"
        reason = "multiple_provider_groups_in_evidence"
    elif len(provider_consistent) == 1:
        auto_proposed = provider_consistent[0]["operator_id"]
        status = "auto_proposed_pending_review"
        reason = ""
    elif not exact:
        status = "unresolved_no_exact_match"
        reason = "no_exact_class_match"
    elif not provider_consistent:
        status = "unresolved_provider_conflict"
        reason = "exact_matches_conflict_with_provider_evidence"
    else:
        status = "unresolved_ambiguous_exact_match"
        reason = "multiple_provider_consistent_exact_matches"
    return {
        "exact_class_candidates": exact,
        "provider_consistent_exact_candidates": provider_consistent,
        "ranked_candidates": scored[:limit],
        "auto_proposed_operator_id": auto_proposed,
        "resolution_status": status,
        "ambiguity_reason": reason,
    }


def _review_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    def compact_parameters(parameters: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "identifier": str(item.get("identifier") or ""),
                "label": str(item.get("label") or ""),
                "parameter_type": str(item.get("parameter_type") or ""),
                "direction": str(item.get("direction") or ""),
            }
            for item in parameters
        ]

    def compact_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "operator_id": item["operator_id"],
                "official_name": item["official_name"],
                "provider_group": item["provider_group"],
                "score": item["score"],
                "match_signals": item["match_signals"],
            }
            for item in candidates
        ]

    rows = []
    for record in records:
        signatures = record["class_signatures"] or [None]
        for signature in signatures:
            if signature is None:
                match = {
                    "exact_class_candidates": [],
                    "ranked_candidates": [],
                    "auto_proposed_operator_id": "",
                    "resolution_status": "unresolved_no_class_scope",
                    "ambiguity_reason": "no_class_scope_in_trace",
                }
                class_name = ""
                provider_evidence = {}
                parameters = []
            else:
                match = signature["catalog_match"]
                class_name = signature["class_name"]
                provider_evidence = signature["provider_evidence"]
                parameters = signature["parameters"]
            rows.append(
                {
                    "record_id": record["record_id"],
                    "class_name": class_name,
                    "trace_path": record["source"]["trace_path"],
                    "trace_sha256": record["source"]["trace_sha256"],
                    "provider_evidence_json": _json_dump(provider_evidence),
                    "parameters_json": _json_dump(compact_parameters(parameters)),
                    "exact_candidates_json": _json_dump(
                        compact_candidates(match["exact_class_candidates"])
                    ),
                    "ranked_candidates_json": _json_dump(
                        compact_candidates(match["ranked_candidates"])
                    ),
                    "auto_proposed_operator_id": match["auto_proposed_operator_id"],
                    "resolution_status": match["resolution_status"],
                    "ambiguity_reason": match["ambiguity_reason"],
                    "review_status": "pending",
                    "human_decision": "",
                    "accepted_operator_id": "",
                    "reviewer": "",
                    "review_notes": "",
                    "training_admission": "forbidden_until_reviewed",
                }
            )
    return rows


def build_review_package(
    source_dir: str | Path,
    catalog_path: str | Path,
    output_dir: str | Path,
    *,
    expected_count: int | None = 110,
    candidate_limit: int = 15,
) -> dict[str, Any]:
    source_dir = Path(source_dir)
    catalog_path = Path(catalog_path)
    output_dir = Path(output_dir)
    source_resolved = source_dir.resolve()
    output_resolved = output_dir.resolve()
    if output_resolved == source_resolved or source_resolved in output_resolved.parents:
        raise ValueError("output directory must be outside source directory")
    trace_paths = sorted(source_dir.glob("*_steps.csv"), key=lambda path: path.name)
    if expected_count is not None and len(trace_paths) != expected_count:
        raise ValueError(
            f"expected {expected_count} Core Processing traces, found {len(trace_paths)}"
        )
    catalog = load_qgis_catalog(catalog_path)
    records = []
    input_hashes = {catalog_path.as_posix(): _sha256(catalog_path)}
    for trace_path in trace_paths:
        ast_path = trace_path.with_name(trace_path.name.replace("_steps.csv", "_ast.json"))
        record = extract_trace_record(
            trace_path,
            ast_path=ast_path if ast_path.is_file() else None,
            source_root=source_dir,
        )
        for signature in record["class_signatures"]:
            signature["catalog_match"] = build_catalog_candidates(
                signature,
                catalog,
                limit=candidate_limit,
            )
        records.append(record)
        input_hashes[trace_path.as_posix()] = record["source"]["trace_sha256"]
        if ast_path.is_file():
            input_hashes[ast_path.as_posix()] = record["source"]["ast_sha256"]

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "signature_records.jsonl"
    with records_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(_json_dump(record) + "\n")

    review_rows = _review_rows(records)
    review_path = output_dir / "signature_review.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0]) if review_rows else [])
        if review_rows:
            writer.writeheader()
            writer.writerows(review_rows)

    status_counts = Counter(row["resolution_status"] for row in review_rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_files": len(records),
        "catalog_operators": len(catalog),
        "class_signatures": sum(len(record["class_signatures"]) for record in records),
        "files_without_class_scope": sum(not record["class_signatures"] for record in records),
        "files_with_ast": sum(bool(record["source"]["ast_sha256"]) for record in records),
        "files_with_parameter_schema": sum(
            any(signature["parameters"] for signature in record["class_signatures"])
            for record in records
        ),
        "files_with_provider_evidence": sum(
            any(signature["provider_evidence"]["providers"] for signature in record["class_signatures"])
            for record in records
        ),
        "review_rows": len(review_rows),
        "resolution_status_counts": dict(sorted(status_counts.items())),
        "auto_proposed_pending_review": status_counts["auto_proposed_pending_review"],
        "unresolved_review_rows": sum(
            count for status, count in status_counts.items() if status != "auto_proposed_pending_review"
        ),
        "human_review_completed": 0,
        "accepted_anchor_mappings": 0,
        "training_rows_emitted": 0,
        "training_admission": "forbidden_until_human_review",
    }
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)

    ambiguities = [
        row
        for row in review_rows
        if row["resolution_status"] != "auto_proposed_pending_review"
    ]
    ambiguities_path = output_dir / "ambiguities.json"
    _write_json(ambiguities_path, ambiguities)

    ambiguity_report_path = output_dir / "ambiguity_report.md"
    report_lines = [
        "# QGIS Core Signature Ambiguity Report",
        "",
        f"Unresolved review rows: {len(ambiguities)} of {len(review_rows)}.",
        "",
        "| Record | Class | Status | Reason | Top candidate IDs |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in ambiguities:
        candidates = json.loads(row["ranked_candidates_json"])
        candidate_ids = ", ".join(item["operator_id"] for item in candidates[:5])
        report_lines.append(
            "| {record} | {class_name} | {status} | {reason} | {candidates} |".format(
                record=row["record_id"],
                class_name=row["class_name"],
                status=row["resolution_status"],
                reason=row["ambiguity_reason"],
                candidates=candidate_ids,
            )
        )
    ambiguity_report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    instructions_path = output_dir / "REVIEW_INSTRUCTIONS.md"
    instructions_path.write_text(
        "# QGIS Core Signature Review\n\n"
        "Each row represents an operator implementation signature, not a workflow.\n"
        "Review the trace evidence and bounded catalog candidates. An automatic proposal\n"
        "is only a review aid and is not accepted until `review_status=reviewed` and\n"
        "`human_decision=accept` are recorded. Ambiguous or unsupported rows must remain\n"
        "unresolved. No row in this package is admitted to training.\n",
        encoding="utf-8",
    )

    output_paths = [
        records_path,
        review_path,
        summary_path,
        ambiguities_path,
        ambiguity_report_path,
        instructions_path,
    ]
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "inputs": dict(sorted(input_hashes.items())),
        "outputs": {path.name: _sha256(path) for path in sorted(output_paths)},
    }
    _write_json(output_dir / "hash_ledger.json", ledger)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=110)
    parser.add_argument("--candidate-limit", type=int, default=15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_review_package(
        args.source_dir,
        args.catalog,
        args.output_dir,
        expected_count=args.expected_count,
        candidate_limit=args.candidate_limit,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
