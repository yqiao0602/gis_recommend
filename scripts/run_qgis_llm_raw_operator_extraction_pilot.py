#!/usr/bin/env python3
"""Extract QGIS operators from complete source files with a catalog-constrained LLM.

This isolated pilot sends one complete, SHA-verified Python source file per
request. The model emits operator candidates only; local AST/catalog checks
make no L3, training, or authority decisions.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_llm_raw_operator_extraction_pilot.v1"
MODEL = "deepseek-v4-flash-0731"
ENDPOINT = "https://tokenrhythm.studio/v1/chat/completions"
MAX_SOURCE_CHARS = 120_000
MAX_OPTIONS = 64


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("operators") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise TypeError("catalog must contain an operators list")
    catalog: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or ":" not in str(row.get("operator_id") or ""):
            continue
        operator_id = str(row["operator_id"]).strip().lower()
        aliases = [
            operator_id.split(":", 1)[1],
            *[str(a).lower() for a in row.get("aliases", [])],
            *[str(row.get(key) or "").lower() for key in ("official_name", "name", "display_name")],
        ]
        catalog[operator_id] = {**row, "operator_id": operator_id, "aliases": sorted(set(aliases))}
    if not catalog:
        raise ValueError("catalog has no provider-qualified operators")
    return catalog


def source_sha256(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _processing_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in {"run", "runalg"}
    return isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "processing" and node.func.attr.lower() in {"run", "runalg", "runandloadresults"}


def _api_alias(node: ast.Call, catalog: dict[str, dict[str, Any]]) -> str | None:
    if not isinstance(node.func, ast.Attribute):
        return None
    method = node.func.attr.lower()
    receiver = ast.unparse(node.func.value).lower()
    matches = [operator_id for operator_id, row in catalog.items() if operator_id.startswith("api:") and method in {str(alias).lower() for alias in row.get("aliases", [])}]
    if len(matches) == 1:
        return matches[0]
    if method == "transform" and any(token in receiver for token in ("coordinate", "ct", "transform")):
        return "api:crs.transform" if "api:crs.transform" in catalog else None
    return None


def local_facts(source_text: str, pool: str, catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    tree = ast.parse(source_text)
    facts = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        operator_id = None
        call_expression = ast.unparse(node)
        if pool == "processing" and _processing_call(node) and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                raw = argument.value.strip().lower()
                operator_id = raw if raw in catalog else None
        elif pool == "api":
            operator_id = _api_alias(node, catalog)
        if operator_id:
            facts.append({"operator_id": operator_id, "line": int(node.lineno), "call_expression": call_expression, "evidence_type": "literal_processing_id" if pool == "processing" else "api_method_call"})
    return sorted(facts, key=lambda row: (row["line"], row["operator_id"]))


def shortlist(source_text: str, catalog: dict[str, dict[str, Any]], pool: str, limit: int = MAX_OPTIONS) -> list[str]:
    lowered = source_text.lower()
    scored = []
    for operator_id, row in catalog.items():
        if pool == "processing" and not operator_id.startswith(("native:", "qgis:", "gdal:", "grass:", "saga:", "otb:")):
            continue
        if pool == "api" and not operator_id.startswith("api:"):
            continue
        aliases = set(row.get("aliases", [])) | {operator_id}
        score = sum(len(re.findall(rf"(?<![a-z0-9_]){re.escape(alias)}(?![a-z0-9_])", lowered)) for alias in aliases if alias)
        if score:
            scored.append((score, operator_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    options = [operator_id for _, operator_id in scored[:limit]]
    options = list(dict.fromkeys([fact["operator_id"] for fact in local_facts(source_text, pool, catalog)] + options))[:limit]
    if options:
        return options
    # Do not silently drop a raw source because lexical prefiltering found no
    # alias. This is an explicitly weaker, auditable fallback shortlist.
    pool_ids = [operator_id for operator_id in sorted(catalog) if (operator_id.startswith("api:") if pool == "api" else not operator_id.startswith("api:"))]
    return pool_ids[:limit]


def numbered_source(source_text: str) -> str:
    return "\n".join(f"{index}: {line}" for index, line in enumerate(source_text.splitlines(), 1))


def build_prompt(source_text: str, pool: str, options: list[str]) -> str:
    return (
        "You are extracting QGIS operators from ONE COMPLETE Python SOURCE FILE. Return JSON only. "
        "Do not produce L3 labels, descriptions, workflow boundaries, or training data. List every "
        "call that can be matched to one CATALOG OPTION, in source order. For Processing, use the exact "
        "provider:algorithm ID; a dynamic ID may be proposed only when this complete source proves one "
        "exact value. For API, use the semantic catalog ID matching the concrete method call. Abstain "
        "rather than inventing an ID. Every item needs call_line and evidence_lines. Return "
        "{operators:[{catalog_operator_id,source_operator_id,call_line,evidence_lines}],abstain_reason}.\n"
        f"POOL: {pool}\nCATALOG OPTIONS: {json.dumps(options, ensure_ascii=False)}\n"
        "COMPLETE SOURCE (original line numbers):\n" + numbered_source(source_text)
    )


def parse_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise TypeError("response must be an object")
    return value


def call_model(api_key: str, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {"model": MODEL, "temperature": 0, "max_tokens": 4096, "stream": False, "messages": [{"role": "user", "content": prompt}]}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP_{exc.code}:{detail}") from exc
    content = str(payload["choices"][0]["message"].get("content") or "")
    return parse_response(content), {"http_status": status, "response_sha256": source_sha256(content), "response_model": payload.get("model"), "usage": payload.get("usage") or {}}


def validate_response(source_text: str, pool: str, output: Any, catalog: dict[str, dict[str, Any]], options: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(output, dict) or not isinstance(output.get("operators"), list):
        return [], ["invalid_response_schema"]
    lines = source_text.splitlines()
    facts = local_facts(source_text, pool, catalog)
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return [], ["source_unparseable"]
    calls_by_line: dict[int, list[ast.Call]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls_by_line.setdefault(int(node.lineno), []).append(node)
    by_line: dict[int, list[dict[str, Any]]] = {}
    for fact in facts:
        by_line.setdefault(fact["line"], []).append(fact)
    verified, errors = [], []
    for item in output["operators"]:
        if not isinstance(item, dict):
            errors.append("operator_not_object")
            continue
        operator_id = str(item.get("catalog_operator_id") or "").strip().lower()
        call_line, evidence = item.get("call_line"), item.get("evidence_lines")
        if operator_id not in catalog or operator_id not in options:
            errors.append("operator_not_in_catalog_shortlist")
            continue
        if not isinstance(call_line, int) or call_line not in calls_by_line:
            errors.append("call_line_not_locally_verified")
            continue
        if not isinstance(evidence, list) or not all(isinstance(line, int) and 1 <= line <= len(lines) for line in evidence):
            errors.append("invalid_evidence_lines")
            continue
        # A raw-source pilot must allow candidates that the deterministic
        # extractor did not know. Verify the source call shape locally, then
        # distinguish locally-confirmed facts from LLM-only proposals.
        matches = [fact for fact in by_line.get(call_line, []) if fact["operator_id"] == operator_id]
        if matches:
            fact = matches[0]
            verified.append({**fact, "verification": "locally_confirmed", "catalog_operator_id": operator_id, "evidence_lines": sorted({call_line, *evidence}), "source_operator_id": item.get("source_operator_id")})
            continue
        call_nodes = calls_by_line.get(call_line, [])
        compatible = False
        for node in call_nodes:
            if pool == "processing":
                if not _processing_call(node):
                    continue
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    # A literal call is locally known when present in catalog;
                    # an incorrect LLM label must not pass validation.
                    compatible = node.args[0].value.strip().lower() == operator_id
                else:
                    # Dynamic first arguments cannot be proven locally. The
                    # candidate remains auditable but is explicitly unverified.
                    compatible = True
            else:
                method = node.func.attr.lower() if isinstance(node.func, ast.Attribute) else ""
                aliases = {str(alias).lower() for alias in catalog[operator_id].get("aliases", [])}
                compatible = method in aliases
            if compatible:
                break
        if not compatible:
            errors.append("operator_call_mismatch")
            continue
        verified.append({"operator_id": operator_id, "catalog_operator_id": operator_id, "line": call_line, "call_expression": ast.unparse(call_nodes[0]) if call_nodes else "", "evidence_type": "llm_raw_source_candidate", "verification": "call_site_only", "evidence_lines": sorted({call_line, *evidence}), "source_operator_id": item.get("source_operator_id")})
    return verified, sorted(set(errors))


def process_row(row: dict[str, Any], catalog: dict[str, dict[str, Any]], api_key: str, max_chars: int) -> dict[str, Any]:
    source = row.get("source_text")
    base = {"schema": SCHEMA, "record_id": row.get("record_id"), "source_sha256": row.get("source_sha256"), "pool": row.get("pilot_pool"), "training_rows_emitted": 0, "training_admission": "not_granted_raw_operator_pilot"}
    if not isinstance(source, str) or source_sha256(source) != str(row.get("source_sha256")):
        return {**base, "status": "deferred_source_integrity"}
    if len(source) > max_chars:
        return {**base, "status": "deferred_source_too_large", "source_chars": len(source)}
    pool = str(row.get("pilot_pool") or "api")
    options = shortlist(source, catalog, pool)
    facts = local_facts(source, pool, catalog)
    lowered_source = source.lower()
    lexical_hit = any(
        re.search(rf"(?<![a-z0-9_]){re.escape(alias)}(?![a-z0-9_])", lowered_source)
        for operator_id in options
        for alias in catalog[operator_id].get("aliases", [])
        if alias
    )
    shortlist_mode = "lexical_or_local_facts" if facts or lexical_hit else "catalog_fallback"
    try:
        output, metadata = call_model(api_key, build_prompt(source, pool, options))
        verified, errors = validate_response(source, pool, output, catalog, options)
        return {**base, "status": "validated_candidate" if verified and not errors else "deferred_invalid_proposal", "source_chars": len(source), "catalog_options": options, "shortlist_mode": shortlist_mode, "local_facts": facts, "proposed": output.get("operators"), "verified": verified, "validation_errors": errors, "model_metadata": metadata}
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
        return {**base, "status": "deferred_request_failure", "source_chars": len(source), "catalog_options": options, "shortlist_mode": shortlist_mode, "local_facts": facts, "reason": str(exc)[:600]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, help="single catalog for legacy packets")
    parser.add_argument("--processing-catalog", type=Path)
    parser.add_argument("--api-catalog", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=20)
    parser.add_argument("--max-source-chars", type=int, default=MAX_SOURCE_CHARS)
    args = parser.parse_args()
    api_key = os.environ.get("TOKENRHYTHM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("TOKENRHYTHM_API_KEY or DEEPSEEK_API_KEY is required")
    rows = load_jsonl(args.samples)[: args.max_rows]
    if len(rows) != args.max_rows:
        raise ValueError(f"expected {args.max_rows} rows, got {len(rows)}")
    if len({str(row.get("source_sha256")) for row in rows}) != len(rows):
        raise ValueError("source SHA overlap in raw pilot")
    if args.catalog:
        shared_catalog = load_catalog(args.catalog)
        catalogs = {"processing": shared_catalog, "api": shared_catalog}
    elif args.processing_catalog and args.api_catalog:
        catalogs = {"processing": load_catalog(args.processing_catalog), "api": load_catalog(args.api_catalog)}
    else:
        raise ValueError("provide --catalog or both --processing-catalog and --api-catalog")
    output = [process_row(row, catalogs.get(str(row.get("pilot_pool") or "api"), catalogs["api"]), api_key, args.max_source_chars) for row in rows]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "raw_operator_ledger_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    summary = {"schema": f"{SCHEMA}.summary", "rows": len(output), "status_counts": dict(sorted(Counter(row["status"] for row in output).items())), "verified_operator_count": sum(len(row.get("verified", [])) for row in output), "training_rows_emitted": 0, "training_admission": "not_granted_raw_operator_pilot"}
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
