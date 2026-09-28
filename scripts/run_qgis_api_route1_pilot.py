#!/usr/bin/env python3
"""Route-1 pilot: LLM proposes task components; a deterministic AST verifier
admits every claim.

For each sink-anchored API source the LLM is asked to propose the data-task
components (core operator calls, input evidence, attribute handling, output
sink) with exact line numbers.  Every claim is then verified against the real
AST: method name, line number, and literal argument values must match.  Only
claims that pass verification may feed description/L3/export downstream; the
LLM never writes a description, L3 label, or training row itself.

Pilot scope: 200 source-disjoint rows from the T2 pool (core call + literal
key argument provable, not mined by the deterministic macro rules).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_qgis_api_mutation_upstream import (  # noqa: E402
    _name,
    _parents,
    _scope_node,
)

SCHEMA = "gis_recommend.qgis_api_route1_pilot.v1"
DEFAULT_BASE_URL = "https://tokenrhythm.studio/v1"
DEFAULT_MODEL = "deepseek-v4-flash-0731"
SINKS = {"addfeature", "addfeatures", "writeraster", "writeasvectorformat", "writeasvectorformatv2", "writeasvectorformatv3"}
CORE_METHODS = {
    # geometry construction
    "frompoint", "frompointxy", "frompolyline", "frompolylinexy",
    "frompolygon", "frompolygonxy", "fromwkt", "fromrect",
    "frommultipoint", "frommultipointxy", "frommultipolygon", "frommultipolygonxy",
    "frommultipolyline", "frommultipolylinexy", "fromwkb", "fromjson", "fromqpolygonf",
    # geometry processing
    "buffer", "centroid", "clip", "combine", "convexhull", "densifybycount",
    "difference", "interpolate", "intersection", "intersects", "makevalid",
    "offsetcurve", "pointonsurface", "simplify", "smooth", "symdifference",
    "transform", "translate", "unaryunion",
    # attribute mutation
    "addattribute", "addattributes", "changeattributevalue", "changeattributevalues",
    "setattribute", "setattributes",
    # output construction (structural step, not a standalone L3)
    "setgeometry",
}
MAX_SCOPE_LINES = 400


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _prompt(source_text: str, sink_line: int) -> str:
    return (
        "你是 QGIS 低层 PyQGIS API 源码分析器。给定一段带行号前缀的 Python 源码，"
        f"已知第 {sink_line} 行是数据输出锚点（addFeature/writeAsVectorFormat/writeRaster 等）。\n"
        "请提取该源码中的'数据任务成分'，只输出一个 JSON 对象（不要输出任何其他文本）：\n"
        "{\n"
        '  "core_operations": [{"method": "<方法名小写>", "line": <行号>, '
        '"key_arguments": {"<参数名>": "<源码中的值或变量名>"}, '
        '"literal_arguments": ["<值确为常量(数字/字符串)的参数名>"]}],\n'
        '  "input_evidence": {"line": <行号>, "kind": "layer_getfeatures|feature_loop|layer_constructor|none"},\n'
        '  "attribute_handling": {"line": <行号>, "kind": "attributes_copy|setattributes|setattribute|none"},\n'
        '  "output_sink": {"line": <行号>, "method": "<sink 方法名>"}\n'
        "}\n"
        "规则：\n"
        "- core_operations 只列有明确数据操作语义的方法（buffer/centroid/fromWkt/fromPolygon/setAttribute/transform 等），"
        "不含只读访问器（geometry()/attributes()/getName/type 等）。\n"
        "- line 必须精确等于源码行号前缀。\n"
        "- key_arguments 每个参数写源码中的实际写法：字面量写值，变量写变量名。\n"
        "- literal_arguments 只列参数值确为常量（数字/字符串）的参数名。\n"
        "- 没有的成分用 {\"line\": 0, \"kind\": \"none\"} 或 []。\n"
        "源码如下：\n"
        + source_text
    )


def _call_model(
    *, api_key: str, base_url: str, model: str, source_text: str, sink_line: int
) -> tuple[Any, dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": _prompt(source_text, sink_line)}
        ],
        "temperature": 0,
        "max_tokens": 16000,
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
    # Gateway overload (429/503/504) gets deep exponential backoff retries.
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
                status = response.status
            break
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 503, 504} and attempt < 4:
                time.sleep(5 * (4 ** attempt))
                continue
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail[:800]}") from exc
    content = str(body["choices"][0]["message"]["content"] or "").strip()
    if body["choices"][0].get("finish_reason") == "length" and not content:
        raise ValueError("LLM response truncated before final JSON")
    proposal = _parse_response_object(content)
    metadata = {
        "http_status": status,
        "response_model": body.get("model"),
        "trace_id": body.get("traceId") or body.get("trace_id"),
        "usage": body.get("usage") or {},
        "response_sha256": _sha256_text(content),
    }
    return proposal, metadata


def _parse_response_object(content: str) -> Any:
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in LLM response")
    return json.loads(content[start : end + 1])


def _build_scope(source_text: str, sink_line: int) -> tuple[str, dict[str, Any]] | None:
    """Return (scoped source with line numbers, scope facts) or None (deferred)."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return None
    parents = _parents(tree)
    sinks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _method(node) in SINKS
        and int(node.lineno) == sink_line
    ]
    if len(sinks) != 1:
        return None
    sink = sinks[0]
    scope = _scope_node(sink, parents)
    lines = source_text.splitlines()
    scope_start = int(getattr(scope, "lineno", 1))
    scope_end = int(getattr(scope, "end_lineno", len(lines)))
    if scope_end - scope_start + 1 > MAX_SCOPE_LINES:
        return None
    scoped = "\n".join(
        f"{index} | {line}" for index, line in enumerate(lines, start=1) if scope_start <= index <= scope_end
    )
    return scoped, {
        "scope_type": type(scope).__name__,
        "scope_line_start": scope_start,
        "scope_line_end": scope_end,
        "sink_call": _method(sink),
        "sink_line": int(sink.lineno),
    }


def _verify_claims(tree: ast.AST, proposal: Any, sink_line: int) -> dict[str, Any]:
    calls_by_line = {
        node.lineno: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    verified_cores: list[dict[str, Any]] = []
    core_errors: list[str] = []
    for item in (proposal.get("core_operations") or [])[:8]:
        if not isinstance(item, dict):
            core_errors.append("non-dict core_operation")
            continue
        method = str(item.get("method") or "").strip().lower()
        line = int(item.get("line") or 0)
        call = calls_by_line.get(line)
        if call is None:
            core_errors.append(f"line {line} not a call")
            continue
        if _method(call) != method:
            core_errors.append(f"line {line} method {_method(call)} != {method}")
            continue
        if method not in CORE_METHODS:
            core_errors.append(f"method {method} not in core whitelist")
            continue
        key_arguments = item.get("key_arguments") or {}
        literal_arguments = item.get("literal_arguments") or []
        verified_args: dict[str, Any] = {}
        arg_errors: list[str] = []
        for arg_name, claimed in key_arguments.items():
            if arg_name in literal_arguments:
                # claimed value must match a literal constant among the call args
                constants = [
                    argument.value
                    for argument in call.args
                    if isinstance(argument, ast.Constant)
                ]
                if not any(str(value) == str(claimed) for value in constants):
                    arg_errors.append(f"arg {arg_name} claimed literal {claimed} not found")
                else:
                    verified_args[arg_name] = {"value": claimed, "kind": "literal"}
            else:
                # claimed must be a variable name among the call args
                names = [
                    argument.id
                    for argument in call.args
                    if isinstance(argument, ast.Name)
                ]
                if str(claimed) not in names and str(claimed) not in {"", "0"}:
                    arg_errors.append(f"arg {arg_name} claimed variable {claimed} not found")
                else:
                    verified_args[arg_name] = {"value": claimed, "kind": "dynamic"}
        if arg_errors:
            core_errors.append(f"line {line} args: {'; '.join(arg_errors)}")
            continue
        verified_cores.append(
            {
                "method": method,
                "line": line,
                "key_arguments": verified_args,
                "literal_arguments": [
                    name
                    for name in literal_arguments
                    if name in verified_args and verified_args[name]["kind"] == "literal"
                ],
            }
        )
    input_evidence = proposal.get("input_evidence") or {}
    input_line = int(input_evidence.get("line") or 0)
    input_kind = str(input_evidence.get("kind") or "none")
    verified_input: dict[str, Any] | None = None
    if input_kind != "none" and input_line:
        call = calls_by_line.get(input_line)
        if call is None:
            input_errors = ["input line not a call"]
        else:
            method = _method(call)
            allowed = {
                "layer_getfeatures": {"getfeatures", "getfeature", "features", "getselectedfeatures"},
                "feature_loop": {"getfeatures", "getfeature"},
                "layer_constructor": {"qgsvectorlayer", "qgsrasterlayer"},
            }.get(input_kind, set())
            if method not in allowed:
                input_errors = [f"input kind {input_kind} method {method} not allowed"]
            else:
                verified_input = {"line": input_line, "kind": input_kind, "method": method}
                input_errors = []
    else:
        input_errors = []
    attribute = proposal.get("attribute_handling") or {}
    attr_line = int(attribute.get("line") or 0)
    attr_kind = str(attribute.get("kind") or "none")
    verified_attribute: dict[str, Any] | None = None
    if attr_kind != "none" and attr_line:
        call = calls_by_line.get(attr_line)
        if call is None:
            attr_errors = ["attribute line not a call"]
        else:
            method = _method(call)
            allowed = {
                "attributes_copy": {"attributes", "setattributes"},
                "setattributes": {"setattributes"},
                "setattribute": {"setattribute"},
            }.get(attr_kind, set())
            if method not in allowed:
                attr_errors = [f"attribute kind {attr_kind} method {method} not allowed"]
            else:
                verified_attribute = {"line": attr_line, "kind": attr_kind, "method": method}
                attr_errors = []
    else:
        attr_errors = []
    sink = proposal.get("output_sink") or {}
    sink_line_claimed = int(sink.get("line") or 0)
    sink_method = str(sink.get("method") or "").lower()
    sink_ok = sink_line_claimed == sink_line and calls_by_line.get(sink_line) is not None
    sink_errors = [] if sink_ok else ["output_sink line/method mismatch"]
    return {
        "verified_core_operations": verified_cores,
        "verified_input_evidence": verified_input,
        "verified_attribute_handling": verified_attribute,
        "verified_output_sink": sink_ok,
        "verification_status": (
            "verified"
            if verified_cores and sink_ok and not input_errors and not attr_errors and not core_errors
            else "deferred"
        ),
        "deferred_reasons": sorted(
            set(core_errors + input_errors + attr_errors + sink_errors)
        ),
    }


def process_source(row: dict[str, Any], *, api_key: str, base_url: str, model: str) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "source_file_missing", "llm_called": False}
    raw = path.read_bytes()
    if _sha256_bytes(raw) != str(row.get("source_sha256") or ""):
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "source_sha256_mismatch", "llm_called": False}
    source_text = raw.decode("utf-8-sig", errors="replace")
    sink_line = int(row.get("sink_line") or 0)
    scoped = _build_scope(source_text, sink_line)
    if scoped is None:
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "scope_not_unique_or_too_large", "llm_called": False}
    scoped_text, scope_facts = scoped
    try:
        proposal, llm_metadata = _call_model(
            api_key=api_key, base_url=base_url, model=model,
            source_text=scoped_text, sink_line=sink_line,
        )
    except (ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            **row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": f"llm_call_failed:{type(error).__name__}",
            "llm_called": True, "llm_error": str(error)[:300], **scope_facts,
        }
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        tree = None
    verification = _verify_claims(tree, proposal, sink_line) if tree is not None else {
        "verification_status": "deferred", "deferred_reasons": ["source_ast_unparseable"],
    }
    result = {
        **row, "schema": SCHEMA, "llm_status": verification["verification_status"],
        "llm_called": True, "llm_proposal": proposal, **scope_facts,
    }
    result.update(verification)
    result["llm_metadata"] = llm_metadata
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=200)
    parser.add_argument("--api-key-env", default="TOKENRHYTHM_API_KEY")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise ValueError(f"missing API key environment variable: {args.api_key_env}")
    rows = _read_jsonl(args.manifest)
    if len(rows) != args.expected_rows:
        raise ValueError(f"manifest rows {len(rows)} != {args.expected_rows}")
    results = [
        process_source(row, api_key=api_key, base_url=args.base_url, model=args.model)
        for row in rows
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    statuses = Counter(str(row.get("llm_status") or "unknown") for row in results)
    verified = [row for row in results if row.get("llm_status") == "verified"]
    paths: list[Path] = []
    for name, rows_out in {
        "route1_pilot_replay_v1.jsonl": results,
        "route1_verified_v1.jsonl": verified,
        "route1_deferred_v1.jsonl": [row for row in results if row.get("llm_status") != "verified"],
    }.items():
        path = args.output_dir / name
        _write_jsonl(path, rows_out)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    summary = {
        "schema": "gis_recommend.qgis_api_route1_pilot_summary.v1",
        "model": args.model,
        "input_rows": len(rows),
        "status_counts": dict(sorted(statuses.items())),
        "verified_rows": len(verified),
        "verified_unique_sources": len({row["source_sha256"] for row in verified}),
        "verified_core_methods": dict(
            sorted(
                Counter(
                    op["method"] for row in verified for op in row.get("verified_core_operations") or []
                ).items()
            )
        ),
        "llm_usage_total": sum(
            int((row.get("llm_metadata") or {}).get("usage", {}).get("total_tokens") or 0)
            for row in results
            if row.get("llm_called")
        ),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pilot_verification_only",
        "llm_called": True,
    }
    _atomic_write(
        str(summary_path),
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    paths.append(summary_path)
    _atomic_write(
        str(args.output_dir / "hash_ledger_v1.json"),
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {"manifest": {"path": str(args.manifest), "sha256": _sha256_bytes(args.manifest.read_bytes())}},
                "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": _sha256_bytes(path.read_bytes())} for path in paths},
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
