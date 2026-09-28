#!/usr/bin/env python3
"""Run an isolated, catalog-constrained QGIS operator extraction pilot.

Each source is parsed locally before any model call.  The model receives one
Processing-relevant AST scope at a time, with original line numbers, never a
whole source file.  Its output is only a candidate operator set: no L3,
workflow, description, deduplication, or training artifact is emitted here.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import textwrap
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_qgis_legacy_provider_ids import canonicalize_operator_id

SCHEMA = "gis_recommend.qgis_llm_catalog_extraction_pilot.v3"
DEFAULT_MODEL = "deepseek-v4-flash-0731"

API_OPERATOR_ALIASES = {
    "buffer": "api:geometry.buffer",
    "centroid": "api:geometry.centroid",
    "combine": "api:geometry.combine",
    "convexhull": "api:geometry.convexhull",
    "difference": "api:geometry.difference",
    "intersection": "api:geometry.intersection",
    "interpolate": "api:geometry.interpolate",
    "makevalid": "api:geometry.makevalid",
    "offsetcurve": "api:geometry.offsetcurve",
    "simplify": "api:geometry.simplify",
    "smooth": "api:geometry.smooth",
    "symdifference": "api:geometry.symdifference",
    "unaryunion": "api:geometry.unaryunion",
    "setgeometry": "api:feature.setgeometry",
    "setattribute": "api:feature.setattributes",
    "setattributes": "api:feature.setattributes",
    "addfeature": "api:sink.addfeature",
    "addfeatures": "api:sink.addfeature",
    "writeasvectorformat": "api:sink.writeasvectorformat",
    "writeasvectorformatv2": "api:sink.writeasvectorformat",
    "writeasvectorformatv3": "api:sink.writeasvectorformat",
    "getfeatures": "api:layer.getfeatures",
    "dataprovider": "api:layer.dataprovider",
    "nearestneighbor": "api:spatial_index.nearestneighbor",
    "processcalculation": "api:raster.processcalculation",
}
API_CONSTRUCTOR_ALIASES = {
    "qgscoordinatetransform": "api:crs.transform",
}
PROCESSING_EXPRESSION_KINDS = (ast.Attribute, ast.Call, ast.IfExp, ast.Dict, ast.JoinedStr, ast.BinOp, ast.Subscript)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def parse_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise TypeError("response must be a JSON object")
    return value


def _is_processing_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in {"run", "runalg"}
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "processing"
        and node.func.attr.lower() in {"run", "runalg", "runandloadresults"}
    )


def _has_processing_call(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Call) and child.args and _is_processing_call(child) for child in ast.walk(node))


def _has_local_processing_call(node: ast.AST) -> bool:
    """Find calls owned by a function, excluding nested function definitions."""
    def visit(current: ast.AST, *, is_root: bool = False) -> bool:
        if not is_root and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return False
        if isinstance(current, ast.Call) and current.args and _is_processing_call(current):
            return True
        return any(visit(child) for child in ast.iter_child_nodes(current))

    return visit(node, is_root=True)


def _api_operator_for_call(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return API_CONSTRUCTOR_ALIASES.get(node.func.id.lower())
    if not isinstance(node.func, ast.Attribute):
        return None
    method = node.func.attr.lower()
    if method == "transform":
        receiver = ast.unparse(node.func.value).lower()
        if "coordinate" in receiver or receiver in {"ct", "coord_transform", "transform"}:
            return "api:crs.transform"
        return "api:geometry.transform"
    operator = API_OPERATOR_ALIASES.get(method)
    if operator == "api:spatial_index.nearestneighbor":
        receiver = ast.unparse(node.func.value).lower()
        if not any(token in receiver for token in ("index", "idx", "spatial")):
            return None
    if method == "intersects":
        receiver = ast.unparse(node.func.value).lower()
        return "api:spatial_index.intersects" if any(token in receiver for token in ("index", "idx", "spatial")) else None
    return operator


def _has_local_api_call(node: ast.AST) -> bool:
    def visit(current: ast.AST, *, is_root: bool = False) -> bool:
        if not is_root and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return False
        if isinstance(current, ast.Call) and _api_operator_for_call(current):
            return True
        return any(visit(child) for child in ast.iter_child_nodes(current))

    return visit(node, is_root=True)


def _node_end_line(node: ast.AST) -> int:
    return int(node.end_lineno or node.lineno)


def relevant_scopes(source: str, pool: str = "processing") -> list[dict[str, Any]]:
    """Return non-overlapping QGIS-relevant function/method/top-level scopes.

    The original source lines are retained in the resulting evidence text.  A
    class is not itself a unit: its relevant methods are considered separately.
    """
    tree = ast.parse(source)
    lines = source.splitlines()
    scopes: list[dict[str, Any]] = []
    definitions: list[tuple[ast.AST, str]] = []
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions.append((child, child.name))
    selected_ranges: list[tuple[int, int]] = []
    for node, name in sorted(definitions, key=lambda item: (item[0].lineno, _node_end_line(item[0]))):
        # Nested helpers are represented only through their own scope, never
        # duplicated inside a containing method payload.
        has_call = _has_local_processing_call(node) if pool == "processing" else _has_local_api_call(node)
        if not has_call:
            continue
        start, end = node.lineno, _node_end_line(node)
        selected_ranges.append((start, end))
        scopes.append({"scope_name": name, "scope_kind": "function", "start_line": start, "end_line": end})

    for statement in tree.body:
        has_call = _has_processing_call(statement) if pool == "processing" else _has_local_api_call(statement)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or not has_call:
            continue
        start, end = statement.lineno, _node_end_line(statement)
        scopes.append({"scope_name": "<module>", "scope_kind": "module_statement", "start_line": start, "end_line": end})

    output: list[dict[str, Any]] = []
    for scope in sorted(scopes, key=lambda item: (item["start_line"], item["end_line"], item["scope_name"])):
        start, end = scope["start_line"], scope["end_line"]
        evidence = "\n".join(f"{line}: {lines[line - 1]}" for line in range(start, end + 1))
        output.append({
            **scope,
            "evidence_text": evidence,
            "scope_source": textwrap.dedent("\n".join(lines[start - 1 : end])),
        })
    return output


def direct_literal_facts(
    source: str,
    catalog: set[str],
    start_line: int = 1,
    end_line: int | None = None,
) -> list[tuple[str, str, int]]:
    """Return catalog-backed literal Processing IDs with their original call lines."""
    tree = ast.parse(source)
    result: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args or not _is_processing_call(node):
            continue
        if node.lineno < start_line or (end_line is not None and node.lineno > end_line):
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        canonical, _ = canonicalize_operator_id(node.args[0].value, catalog)
        if canonical:
            result.append(
                {
                    "catalog_operator_id": canonical,
                    "source_operator_id": node.args[0].value,
                    "call_line": node.lineno,
                }
            )
    return sorted(
        {(
            row["catalog_operator_id"],
            row["source_operator_id"],
            row["call_line"],
        ) for row in result},
        key=lambda item: (item[2], item[0], item[1]),
    )


def direct_gold(source: str, catalog: set[str], start_line: int = 1, end_line: int | None = None) -> set[str]:
    return {
        item[0]
        for item in direct_literal_facts(source, catalog, start_line, end_line)
    }


def direct_api_facts(
    source: str,
    catalog: set[str],
    start_line: int = 1,
    end_line: int | None = None,
) -> list[tuple[str, str, int]]:
    """Return locally observed semantic API calls; this is measurement gold only."""
    tree = ast.parse(source)
    facts: set[tuple[str, str, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not (operator_id := _api_operator_for_call(node)):
            continue
        if node.lineno < start_line or (end_line is not None and node.lineno > end_line):
            continue
        if operator_id not in catalog:
            continue
        call_name = ast.unparse(node.func)
        facts.add((operator_id, call_name, int(node.lineno)))
    return sorted(facts, key=lambda item: (item[2], item[0], item[1]))


def dynamic_expression_facts(
    source: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> list[dict[str, Any]]:
    """Return Processing calls whose first argument is an expression, not a Name or literal."""
    tree = ast.parse(source)
    facts: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_processing_call(node) or not node.args:
            continue
        if node.lineno < start_line or (end_line is not None and node.lineno > end_line):
            continue
        first = node.args[0]
        if not isinstance(first, PROCESSING_EXPRESSION_KINDS):
            continue
        facts.append({"call_line": int(node.lineno), "first_argument_kind": type(first).__name__, "first_argument_source": ast.unparse(first)})
    return sorted(facts, key=lambda item: (item["call_line"], item["first_argument_kind"]))


def static_operator_binding_facts(source: str, scope: dict[str, Any], catalog: set[str]) -> list[dict[str, Any]]:
    """Prove module-visible string aliases consumed by a Processing call in scope.

    This only recovers one unambiguous string assignment before a call. It does
    not evaluate expressions, attributes, parameters, or cross-file state.
    """
    tree = ast.parse(source)
    assignments: dict[str, list[tuple[int, str]]] = {}
    calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append((node.lineno, node.value.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            assignments.setdefault(node.target.id, []).append((node.lineno, node.value.value))
        elif (
            isinstance(node, ast.Call)
            and node.args
            and _is_processing_call(node)
            and scope["start_line"] <= node.lineno <= scope["end_line"]
            and isinstance(node.args[0], ast.Name)
        ):
            calls.append((node.lineno, node.args[0].id))
    facts: list[dict[str, Any]] = []
    for call_line, name in sorted(calls):
        prior = [(line, value) for line, value in assignments.get(name, []) if line < call_line]
        if len(prior) != 1:
            continue
        assignment_line, source_operator_id = prior[0]
        canonical, _ = canonicalize_operator_id(source_operator_id, catalog)
        if canonical:
            facts.append({
                "variable_name": name,
                "assignment_line": assignment_line,
                "call_line": call_line,
                "source_operator_id": source_operator_id,
                "catalog_operator_id": canonical,
            })
    return facts


def candidates(
    scope: dict[str, Any],
    documents: list[dict[str, Any]],
    embeddings: np.ndarray,
    encoder: Any,
    top_k: int,
    catalog: set[str],
    known_catalog_ids: list[str] | None = None,
    pool: str = "processing",
) -> list[str]:
    evidence_text = scope["evidence_text"]
    lowered = evidence_text.lower()
    lexical = [row["operator_id"] for row in documents if row["kind"] == "operator" and row["operator_id"] in lowered]
    ast_literal = (
        sorted(direct_gold(scope["scope_source"], catalog))
        if pool == "processing"
        else sorted(item[0] for item in direct_api_facts(scope["scope_source"], catalog))
    )
    query = encoder.encode([evidence_text], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)[0]
    scores = query @ embeddings.T
    ranked = [documents[index]["operator_id"] for index in np.argsort(-scores) if documents[index]["kind"] == "operator"]
    return list(dict.fromkeys((known_catalog_ids or []) + ast_literal + lexical + ranked))[:top_k]


def prompt(
    scope: dict[str, Any],
    options: list[str],
    literal_facts: list[tuple[str, str, int]],
    binding_facts: list[dict[str, Any]],
    pool: str = "processing",
) -> str:
    observed = [
        {"catalog_operator_id": item[0], "source_operator_id": item[1], "call_line": item[2]}
        for item in literal_facts
    ]
    domain = "QGIS Processing" if pool == "processing" else "low-level PyQGIS semantic"
    return f'''Extract only {domain} operator IDs that are supported by this one Python scope.
Return JSON only: {{"operators":[{{"catalog_operator_id":"provider:slug","source_lines":[1]}}]}}.
Choose only from CATALOG OPTIONS. source_lines must be original lines in SCOPE SOURCE.
Do not infer L3, task descriptions, workflow edges, or training data. For API IDs, use only the
semantic API catalog IDs supplied in CATALOG OPTIONS. Return [] when none.
LOCALLY OBSERVED LITERAL CALL FACTS: {json.dumps(observed)}
Every LOCALLY OBSERVED LITERAL CALL FACT is a verified Processing call in this scope. Include each
of its catalog_operator_id once and cite its call_line. These facts are deterministic local evidence,
not a request to infer any additional operator.
LOCALLY PROVED STATIC BINDING FACTS: {json.dumps(binding_facts)}
For each binding fact, the variable's string assignment is proven to be the only earlier assignment
and is consumed as the first argument of processing.run at call_line. Use it as source evidence.
CATALOG OPTIONS: {json.dumps(options)}
SCOPE: {scope["scope_name"]} ({scope["start_line"]}-{scope["end_line"]})
SCOPE SOURCE:\n{scope["evidence_text"]}'''


def call(
    api_key: str,
    model: str,
    scope: dict[str, Any],
    options: list[str],
    literal_facts: list[tuple[str, str, int]],
    binding_facts: list[dict[str, Any]],
    max_tokens: int,
    pool: str = "processing",
) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"model": model, "messages": [{"role": "user", "content": prompt(scope, options, literal_facts, binding_facts, pool)}], "temperature": 0, "max_tokens": max_tokens, "stream": False}
    request = urllib.request.Request("https://tokenrhythm.studio/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode())
    content = str(data["choices"][0]["message"].get("content") or "")
    choice = data["choices"][0]
    return parse_object(content), {
        "model": data.get("model"),
        "trace_id": data.get("traceId"),
        "response_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "response_character_count": len(content),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
    }


def _validated_proposals(output: dict[str, Any], catalog: set[str], options: list[str], scope: dict[str, Any]) -> tuple[dict[str, list[int]], list[str]]:
    proposed: dict[str, list[int]] = {}
    errors: list[str] = []
    for item in output.get("operators", []):
        operator_id = str(item.get("catalog_operator_id") or "").lower()
        source_lines = item.get("source_lines")
        valid_lines = isinstance(source_lines, list) and all(isinstance(line, int) and scope["start_line"] <= line <= scope["end_line"] for line in source_lines)
        if operator_id not in catalog or operator_id not in options or not valid_lines:
            errors.append("invalid_operator_or_scope_span")
            continue
        proposed[operator_id] = sorted(set(source_lines))
    return proposed, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True, help="JSONL with record_id, source_sha256, source_text")
    parser.add_argument("--pool", choices=("processing", "api", "auto"), default="auto")
    parser.add_argument("--source-pool", choices=("processing", "api"), help="Filter a mixed staged manifest before max-sources.")
    parser.add_argument("--dynamic-expression-only", action="store_true", help="Send only scopes containing nonliteral Processing call arguments.")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=16)
    parser.add_argument("--max-scope-chars", type=int, default=12000)
    parser.add_argument("--max-sources", type=int, default=25)
    parser.add_argument("--max-model-scopes", type=int, default=25)
    parser.add_argument("--max-model-scopes-per-source", type=int, default=25)
    parser.add_argument(
        "--calibration-literal-gold-only",
        action="store_true",
        help="Send only scopes with deterministic literal operator calls for measured calibration.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--only-record-id", action="append", default=[])
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("output directory is not empty")
    if args.max_scope_chars < 1 or args.max_sources < 1 or args.max_model_scopes < 1 or args.max_model_scopes_per_source < 1 or args.top_k < 1 or args.max_tokens < 1:
        raise ValueError("limits must be positive")
    api_key = os.environ.get("TOKENRHYTHM_API_KEY")
    if not api_key:
        raise ValueError("TOKENRHYTHM_API_KEY is required")
    catalog_rows = json.loads(args.catalog.read_text(encoding="utf-8"))["operators"]
    catalog = {str(row["operator_id"]).lower() for row in catalog_rows}
    documents = load_jsonl(args.index_dir / "documents_v1.jsonl")
    embeddings = np.load(args.index_dir / "embeddings_v1.npy")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer
    encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)

    rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    model_scope_attempts = 0
    samples = load_jsonl(args.samples)
    if args.source_pool:
        samples = [sample for sample in samples if sample.get("pilot_pool") == args.source_pool]
    if args.only_record_id:
        requested_ids = set(args.only_record_id)
        samples = [sample for sample in samples if sample["record_id"] in requested_ids]
        if len({sample["record_id"] for sample in samples}) != len(requested_ids):
            raise ValueError("one or more --only-record-id values are absent from samples")
    for sample in samples[:args.max_sources]:
        source = sample["source_text"]
        source_identity = {"record_id": sample["record_id"], "source_sha256": sample["source_sha256"]}
        if hashlib.sha256(source.encode()).hexdigest() != sample["source_sha256"]:
            source_rows.append({**source_identity, "source_status": "deferred_source_sha_mismatch", "emitted_scope_count": 0})
            continue
        pool = str(sample.get("pilot_pool") or sample.get("pool") or "processing") if args.pool == "auto" else args.pool
        try:
            scopes = relevant_scopes(source, pool=pool)
        except SyntaxError:
            source_rows.append({**source_identity, "source_status": "excluded_unparseable", "emitted_scope_count": 0})
            continue
        if args.dynamic_expression_only:
            scopes = [scope for scope in scopes if dynamic_expression_facts(source, scope["start_line"], scope["end_line"])]
        emitted = 0
        source_model_attempts = 0
        if not scopes:
            source_rows.append({**source_identity, "pool": pool, "source_status": "no_supported_scope", "relevant_scope_count": 0, "model_call_scope_count": 0})
            continue
        for scope in scopes:
            base = {"record_id": sample["record_id"], "source_sha256": sample["source_sha256"], "pool": pool, "scope_name": scope["scope_name"], "scope_kind": scope["scope_kind"], "scope_span": [scope["start_line"], scope["end_line"]], "scope_source_sha256": hashlib.sha256(scope["evidence_text"].encode()).hexdigest(), "training_rows_emitted": False, "training_admission": "not_granted_llm_catalog_extraction_pilot"}
            literal_facts = (
                direct_literal_facts(source, catalog, scope["start_line"], scope["end_line"])
                if pool == "processing"
                else direct_api_facts(source, catalog, scope["start_line"], scope["end_line"])
            )
            gold = {item[0] for item in literal_facts}
            binding_facts = static_operator_binding_facts(source, scope, catalog) if pool == "processing" else []
            proved_ids = gold | {str(item["catalog_operator_id"]) for item in binding_facts}
            measurable = {
                "direct_gold_operator_ids": sorted(gold),
                "locally_proved_operator_ids": sorted(proved_ids),
                "local_literal_call_facts": [
                    {"catalog_operator_id": item[0], "source_operator_id": item[1], "call_line": item[2]}
                    for item in literal_facts
                ],
                "local_api_call_facts": [
                    {"catalog_operator_id": item[0], "source_call": item[1], "call_line": item[2]}
                    for item in literal_facts
                ] if pool == "api" else [],
                "local_dynamic_expression_facts": dynamic_expression_facts(source, scope["start_line"], scope["end_line"]) if pool == "processing" else [],
                "local_static_operator_binding_facts": binding_facts,
            }
            if args.calibration_literal_gold_only and not gold:
                rows.append({**base, **measurable, "status": "deferred_outside_literal_calibration", "reason": "scope has no deterministic literal catalog operator", "scope_character_count": len(scope["evidence_text"])})
                continue
            if len(scope["evidence_text"]) > args.max_scope_chars:
                rows.append({**base, **measurable, "false_negative": len(gold), "status": "deferred_scope_too_large", "reason": "scope exceeds max_scope_chars; source was not truncated or sent", "scope_character_count": len(scope["evidence_text"])})
                continue
            if model_scope_attempts >= args.max_model_scopes:
                rows.append({**base, **measurable, "false_negative": len(gold), "status": "deferred_outside_scope_budget", "reason": "scope not sent because the bounded pilot request budget was reached", "scope_character_count": len(scope["evidence_text"])})
                continue
            if source_model_attempts >= args.max_model_scopes_per_source:
                rows.append({**base, **measurable, "false_negative": len(gold), "status": "deferred_per_source_scope_budget", "reason": "scope not sent because the per-source pilot request budget was reached", "scope_character_count": len(scope["evidence_text"])})
                continue
            options = candidates(
                scope,
                documents,
                embeddings,
                encoder,
                args.top_k,
                catalog,
                sorted(proved_ids),
                pool,
            )
            model_scope_attempts += 1
            source_model_attempts += 1
            try:
                output, metadata = call(api_key, args.model, scope, options, literal_facts, binding_facts, args.max_tokens, pool)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                rows.append({**base, **measurable, "catalog_options": options, "false_negative": len(gold), "status": "deferred_llm_request_failure", "reason": type(error).__name__, "scope_character_count": len(scope["evidence_text"])})
                continue
            proposed, errors = _validated_proposals(output, catalog, options, scope)
            proposed_ids = set(proposed)
            unverified_ids = proposed_ids - proved_ids
            rows.append({**base, **measurable, "catalog_options": options, "proposed_operator_ids": sorted(proposed_ids), "proposed_operator_source_lines": proposed, "true_positive": len(proposed_ids & proved_ids), "false_positive": len(unverified_ids) if args.calibration_literal_gold_only else 0, "unverified_candidate_ids": sorted(unverified_ids), "false_negative": len(proved_ids - proposed_ids), "status": "deferred_llm_candidate_only", "validation_errors": errors, "model_metadata": metadata})
            emitted += 1
        source_rows.append({**source_identity, "pool": pool, "source_status": "processed", "relevant_scope_count": len(scopes), "model_call_scope_count": emitted})
    tp = sum(row.get("true_positive", 0) for row in rows)
    fp = sum(row.get("false_positive", 0) for row in rows)
    fn = sum(row.get("false_negative", 0) for row in rows)
    successful = [row for row in rows if row["status"] == "deferred_llm_candidate_only"]
    successful_tp = sum(row.get("true_positive", 0) for row in successful)
    successful_fn = sum(row.get("false_negative", 0) for row in successful)
    summary = {"schema": f"{SCHEMA}.summary", "pool": args.pool, "source_count": min(len(samples), args.max_sources), "source_status_counts": {status: sum(row.get("source_status") == status for row in source_rows) for status in sorted({row.get("source_status") for row in source_rows})}, "scope_count": len(rows), "model_call_scope_count": len(successful), "deferred_scope_too_large": sum(row["status"] == "deferred_scope_too_large" for row in rows), "deferred_llm_request_failure": sum(row["status"] == "deferred_llm_request_failure" for row in rows), "tp": tp, "fp": fp, "fn": fn, "precision": tp / (tp + fp) if tp + fp else 0, "end_to_end_recall": tp / (tp + fn) if tp + fn else 0, "successful_response_recall": successful_tp / (successful_tp + successful_fn) if successful_tp + successful_fn else 0, "unverified_candidate_count": sum(len(row.get("unverified_candidate_ids", [])) for row in successful), "metric_scope": "literal_catalog_gold" if args.calibration_literal_gold_only else "locally_proved_ids_only; unverified candidates require independent verification", "training_rows_emitted": 0, "training_admission": "not_granted_llm_catalog_extraction_pilot"}
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "source_ledger_v2.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in source_rows), encoding="utf-8")
    (args.output_dir / "scope_ledger_v2.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (args.output_dir / "summary_v2.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
