#!/usr/bin/env python3
"""Run an isolated LLM operator-ID extraction pilot with source-backed verification.

This is deliberately not a QGIS conversion driver.  It sends bounded source
excerpts to an OpenAI-compatible endpoint and records only candidate operator
IDs.  A separate AST/catalog verifier makes every admission decision; no L3,
dependency edge, description, deduplication, or training row is emitted here.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_qgis_processing_resolution_census import (
    _assignment_definitions,
    _parents,
    _static_strings,
)
from recover_qgis_legacy_provider_ids import (
    canonicalize_operator_id,
    load_catalog_ids,
)

SCHEMA = "gis_recommend.qgis_llm_candidate_extraction_pilot.v1"
DEFAULT_BASE_URL = "https://tokenrhythm.studio/v1"
DEFAULT_MODEL = "deepseek-v4-flash-0731"
MAX_PROPOSALS_PER_SOURCE = 12


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _load_catalog_ids(path: Path) -> set[str]:
    """Use the frozen JSON catalog when supplied, else reuse the legacy CSV loader."""
    if path.suffix.lower() != ".json":
        return load_catalog_ids(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    operator_ids = {
        str(row.get("operator_id") or "").strip().lower()
        for row in payload.get("operators", [])
        if isinstance(row, dict) and ":" in str(row.get("operator_id") or "")
    }
    if not operator_ids:
        raise ValueError(f"no provider-qualified operator IDs found in {path}")
    return operator_ids


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _is_processing_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in {"run", "runalg"}
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr.lower() in {"run", "runandloadresults", "runalg"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "processing"
    )


def _processing_calls(source_text: str) -> dict[int, ast.Call]:
    tree = ast.parse(source_text)
    return {
        node.lineno: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and node.args and _is_processing_call(node)
    }


def _ast_facts(source_text: str) -> dict[str, Any]:
    """Expose deterministic call sites and string evidence to the proposer."""
    calls = _processing_calls(source_text)
    return {
        "processing_call_sites": [
            {
                "line": line,
                "operator_expression": ast.unparse(call.args[0]),
                "operator_is_literal": isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str),
            }
            for line, call in sorted(calls.items())
            if not (
                isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)
            )
        ]
    }


def _target_symbols(node: ast.AST) -> set[str]:
    symbols: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if child.id not in {"self", "cls"}:
                symbols.add(child.id)
        elif isinstance(child, ast.Attribute):
            symbols.add(ast.unparse(child))
    return symbols


def _model_source_excerpt(source_text: str) -> str:
    """Return line-preserving evidence for dynamic IDs, not a whole source file."""
    tree = ast.parse(source_text)
    lines = source_text.splitlines()
    dynamic_calls = [
        call
        for call in _processing_calls(source_text).values()
        if not (
            isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        )
    ]
    references = {
        symbol
        for call in dynamic_calls
        for symbol in _target_symbols(call.args[0])
    }
    selected_lines = {
        line
        for call in dynamic_calls
        for line in range(call.lineno, (call.end_lineno or call.lineno) + 1)
    }
    referenced_functions = {
        node.id
        for call in dynamic_calls
        for node in ast.walk(call.args[0])
        if isinstance(node, ast.Name)
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if _target_symbols(target) & references:
                selected_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in referenced_functions:
            selected_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    expanded = {
        nearby
        for line in selected_lines
        for nearby in range(max(1, line - 1), min(len(lines), line + 1) + 1)
    }
    return "\n".join(f"{line}: {lines[line - 1]}" for line in sorted(expanded))


def _prompt(source_text: str, retrieval_candidates: list[str] | None = None) -> str:
    facts = json.dumps(_ast_facts(source_text), ensure_ascii=False, sort_keys=True)
    candidates = json.dumps(retrieval_candidates or [], ensure_ascii=False)
    return f"""You are extracting only QGIS Processing algorithm IDs from Python source.
Return one JSON object and no Markdown. Do not infer task semantics, L3 labels,
dependency edges, or missing code. Consider *only* AST call sites where
`operator_is_literal` is false. Literal IDs are already recovered by a
deterministic driver and must never be returned. A proposal is allowed only when
nearby source proves one exact provider-qualified ID for a dynamic call.

Schema:
{{"proposals":[{{"call_line":123,"source_operator_id":"provider:slug","id_evidence_lines":[120,123]}}],"abstain_reason":null}}

Rules:
- `call_line` must be one of the dynamic call lines in the AST facts.
- `source_operator_id` must be the exact ID proven by source, not an alias you invent.
- `id_evidence_lines` must show all parts of the ID or the literal return/assignment.
- Return an empty `proposals` list when a value is dynamic, multi-valued, external,
  custom, or uncertain.

DETERMINISTIC AST FACTS (do not invent call lines beyond these):
{facts}

SOURCE EVIDENCE EXCERPT (line numbers are authoritative; do not use facts not shown):
{_model_source_excerpt(source_text)}

RETRIEVAL CANDIDATES (non-evidence suggestions; do not return one unless the
source evidence and independent verifier prove it):
{candidates}"""


def _parse_response_object(content: str) -> tuple[dict[str, Any], str]:
    candidate = content.strip()
    response_format = "direct_json"
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ValueError("LLM response has an incomplete JSON code fence")
        candidate = "\n".join(lines[1:-1]).strip()
        response_format = "json_code_fence"
    try:
        proposal = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response is not a JSON object") from exc
    if not isinstance(proposal, dict):
        raise TypeError("LLM response JSON must be an object")
    return proposal, response_format


def _call_model(
    *, api_key: str, base_url: str, model: str, source_text: str,
    retrieval_candidates: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _prompt(source_text, retrieval_candidates)}],
        "temperature": 0,
        "max_tokens": 4096,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {detail[:800]}") from exc

    content = str(body["choices"][0]["message"]["content"] or "").strip()
    if body["choices"][0].get("finish_reason") == "length" and not content:
        raise ValueError("LLM response truncated before final JSON")
    proposal, response_format = _parse_response_object(content)
    metadata = {
        "http_status": status,
        "response_model": body.get("model"),
        "trace_id": body.get("traceId") or body.get("trace_id"),
        "usage": body.get("usage") or {},
        "response_sha256": _sha256_text(content),
        "response_format": response_format,
    }
    return proposal, metadata


def _has_source_evidence(
    source_operator_id: str, evidence_lines: list[int], lines: list[str]
) -> bool:
    normalized = source_operator_id.lower()
    provider, separator, slug = normalized.partition(":")
    if not separator or not provider or not slug:
        return False
    evidence = "\n".join(
        lines[index - 1].lower() for index in evidence_lines if 1 <= index <= len(lines)
    )
    return provider in evidence and slug in evidence


def _prove_single_operator_value(source_text: str, call_line: int) -> str | None:
    """Accept only an independently static single value for the dynamic expression."""
    tree = ast.parse(source_text)
    parents = _parents(tree)
    definitions = _assignment_definitions(tree, parents)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and node.args
        and node.lineno == call_line
        and _is_processing_call(node)
    ]
    if len(calls) != 1:
        return None
    resolved = _static_strings(
        calls[0].args[0], context=calls[0], parents=parents, definitions=definitions
    )
    normalized = {value.strip().lower() for value in resolved or set() if value.strip()}
    return next(iter(normalized)) if len(normalized) == 1 else None


def verify_proposals(
    *, source_text: str, proposals: Any, catalog_ids: set[str]
) -> tuple[list[dict[str, Any]], str]:
    """Validate model IDs against AST call sites, literal source evidence, and catalog."""
    try:
        calls = _processing_calls(source_text)
    except SyntaxError:
        return [], "excluded_unparseable"
    if not isinstance(proposals, list):
        return [], "deferred_llm_response_schema_invalid"
    if len(proposals) > MAX_PROPOSALS_PER_SOURCE:
        return [], "deferred_llm_proposal_limit_exceeded"

    lines = source_text.splitlines()
    verified: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_lines: set[int] = set()
    for index, item in enumerate(proposals):
        if not isinstance(item, dict):
            errors.append(f"proposal_{index}:not_object")
            continue
        call_line = item.get("call_line")
        source_operator_id = item.get("source_operator_id")
        evidence_lines = item.get("id_evidence_lines")
        if (
            not isinstance(call_line, int)
            or not isinstance(source_operator_id, str)
            or not isinstance(evidence_lines, list)
            or not all(isinstance(line, int) for line in evidence_lines)
        ):
            errors.append(f"proposal_{index}:invalid_fields")
            continue
        if call_line in seen_lines or call_line not in calls:
            errors.append(f"proposal_{index}:call_site_not_verified")
            continue
        if isinstance(calls[call_line].args[0], ast.Constant) and isinstance(
            calls[call_line].args[0].value, str
        ):
            errors.append(f"proposal_{index}:not_a_dynamic_gap_call")
            continue
        if not _has_source_evidence(source_operator_id, [call_line, *evidence_lines], lines):
            errors.append(f"proposal_{index}:id_not_present_in_source_evidence")
            continue
        independently_proven = _prove_single_operator_value(source_text, call_line)
        if independently_proven != source_operator_id.strip().lower():
            errors.append(f"proposal_{index}:operator_value_not_independently_proven")
            continue
        canonical, rule = canonicalize_operator_id(source_operator_id, catalog_ids)
        if canonical is None:
            errors.append(f"proposal_{index}:catalog_miss")
            continue
        seen_lines.add(call_line)
        call = calls[call_line]
        verified.append(
            {
                "call_line": call_line,
                "source_operator_id": source_operator_id.strip().lower(),
                "canonical_operator_id": canonical,
                "provider_resolution_rule": rule,
                "operator_value_proof": "static_single_value",
                "id_evidence_lines": sorted({call_line, *evidence_lines}),
                "call_expression": ast.unparse(call),
            }
        )
    return verified, "verified_operator_candidate" if verified and not errors else (
        "deferred_llm_proposal_unverified" if errors else "deferred_llm_abstained"
    )


def run_pilot(
    *, samples: list[dict[str, Any]], catalog_ids: set[str], api_key: str,
    base_url: str, model: str,
    retrieval_candidates_by_id: dict[str, list[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    for sample in samples:
        source_text = sample.get("source_text")
        expected_sha = str(sample.get("source_sha256") or "")
        row = {
            "schema": SCHEMA,
            "record_id": sample.get("record_id"),
            "source_sha256": expected_sha,
            "source_path": sample.get("source_path"),
            "source_excerpt_sha256": _sha256_text(source_text) if isinstance(source_text, str) else None,
            "training_admission": "not_granted_llm_pilot_only",
            "training_row_emitted": False,
            "production_merge": "not_granted",
        }
        if not isinstance(source_text, str):
            row.update({"status": "excluded_source_text_missing", "verified_proposals": []})
        elif expected_sha and sample.get("source_text_sha256") and sample["source_text_sha256"] != _sha256_text(source_text):
            row.update({"status": "excluded_excerpt_integrity_failure", "verified_proposals": []})
        else:
            try:
                proposal, metadata = _call_model(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    source_text=source_text,
                    retrieval_candidates=(retrieval_candidates_by_id or {}).get(
                        str(sample.get("record_id")), []
                    ),
                )
                verified, status = verify_proposals(
                    source_text=source_text,
                    proposals=proposal.get("proposals"),
                    catalog_ids=catalog_ids,
                )
                row.update({
                    "status": status,
                    "model_metadata": metadata,
                    "proposal_sha256": _sha256_text(json.dumps(proposal, ensure_ascii=False, sort_keys=True)),
                    "proposal_count": len(proposal.get("proposals") or []) if isinstance(proposal.get("proposals"), list) else None,
                    "verified_proposals": verified,
                })
            except (RuntimeError, ValueError, KeyError) as exc:
                row.update({"status": "deferred_llm_request_or_schema_failure", "reason": str(exc), "verified_proposals": []})
        statuses[str(row["status"])] += 1
        rows.append(row)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "source_count": len(rows),
        "status_counts": dict(sorted(statuses.items())),
        "verified_operator_proposal_count": sum(len(row["verified_proposals"]) for row in rows),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_llm_pilot_only",
        "next_gate": "manual source-disjoint review and independent dataflow verification",
        "retrieval_candidates_provided": bool(retrieval_candidates_by_id),
    }
    return rows, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True, help="JSONL with source_text excerpts")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default="TOKENRHYTHM_API_KEY")
    parser.add_argument("--retrieval-results", type=Path)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise ValueError(f"missing API key environment variable: {args.api_key_env}")
    samples = list(_load_jsonl(args.samples))
    retrieval_candidates_by_id: dict[str, list[str]] = {}
    if args.retrieval_results:
        for row in _load_jsonl(args.retrieval_results):
            retrieval_candidates_by_id[str(row.get("query_id"))] = [
                str(item["operator_id"])
                for item in row.get("operator_candidates", [])
                if isinstance(item, dict) and item.get("operator_id")
            ]
    rows, summary = run_pilot(
        samples=samples,
        catalog_ids=_load_catalog_ids(args.catalog),
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        retrieval_candidates_by_id=retrieval_candidates_by_id,
    )
    ledger = args.output_dir / "llm_candidate_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _atomic_write(ledger, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(hash_path, json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.samples.name: _sha256_bytes(args.samples.read_bytes()),
            args.catalog.name: _sha256_bytes(args.catalog.read_bytes()),
            **(
                {args.retrieval_results.name: _sha256_bytes(args.retrieval_results.read_bytes())}
                if args.retrieval_results
                else {}
            ),
        },
        "artifacts": {ledger.name: _sha256_bytes(ledger.read_bytes()), summary_path.name: _sha256_bytes(summary_path.read_bytes())},
        "model": args.model,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
