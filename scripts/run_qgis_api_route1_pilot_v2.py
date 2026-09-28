#!/usr/bin/env python3
"""Route-1 pilot v2: AST-extracted call facts, LLM selects, verifier checks.

v1 asked the LLM to locate calls and line numbers itself (generation task;
5% pass).  v2 inverts the protocol: the verifier pre-extracts every call in
the sink scope with real line numbers, argument text and literal status into
a numbered fact list.  The LLM only selects which facts form the data-task
components (core operations, input evidence, attribute handling, output
sink) and confirms argument values against the facts.  The verifier then
checks that every selected index exists, its method is in the whitelist,
and every claimed argument value matches the pre-extracted fact.  No line
number generation, no parameter-name invention.

Checkpoints: partial results are written every 20 rows so an interrupted
run is not fully lost.  Gateway 429/503/504 retries are short (2 attempts)
so a saturated endpoint costs seconds, not hours.
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

SCHEMA = "gis_recommend.qgis_api_route1_pilot_v2.v1"
DEFAULT_BASE_URL = "https://tokenrhythm.studio/v1"
DEFAULT_MODEL = "deepseek-v4-flash-0731"
SINKS = {"addfeature", "addfeatures", "writeraster", "writeasvectorformat", "writeasvectorformatv2", "writeasvectorformatv3"}
CORE_METHODS = {
    "frompoint", "frompointxy", "frompolyline", "frompolylinexy",
    "frompolygon", "frompolygonxy", "fromwkt", "fromrect",
    "frommultipoint", "frommultipointxy", "frommultipolygon", "frommultipolygonxy",
    "frommultipolyline", "frommultipolylinexy", "fromwkb", "fromjson", "fromqpolygonf",
    "buffer", "centroid", "clip", "combine", "convexhull", "densifybycount",
    "difference", "interpolate", "intersection", "intersects", "makevalid",
    "offsetcurve", "pointonsurface", "simplify", "smooth", "symdifference",
    "transform", "translate", "unaryunion",
    "addattribute", "addattributes", "changeattributevalue", "changeattributevalues",
    "setattribute", "setattributes",
    "setgeometry",
}
INPUT_METHODS = {
    "layer_getfeatures": {"getfeatures", "getfeature", "features", "getselectedfeatures"},
    "feature_loop": {"getfeatures", "getfeature"},
    "layer_constructor": {"qgsvectorlayer", "qgsrasterlayer"},
}
ATTRIBUTE_METHODS = {
    "attributes_copy": {"attributes", "setattributes"},
    "setattributes": {"setattributes"},
    "setattribute": {"setattribute"},
}
MAX_SCOPE_LINES = 400
MAX_FACTS = 60
CHECKPOINT_EVERY = 20


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


def _extract_facts(tree: ast.AST, sink_line: int) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Pre-extract every call in the sink scope as numbered facts."""
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
    lines = ast.get_source_segment("", tree) or ""
    # source segment is unavailable without the text; use unparse of args instead
    calls = sorted(
        (
            node
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and int(node.lineno) <= int(sink.lineno)
        ),
        key=lambda node: int(node.lineno),
    )
    facts: list[dict[str, Any]] = []
    for index, node in enumerate(calls):
        if index >= MAX_FACTS:
            break
        method = _method(node)
        if method not in CORE_METHODS and method not in SINKS and method not in {
            "getfeatures", "getfeature", "features", "getselectedfeatures",
            "qgsvectorlayer", "qgsrasterlayer", "attributes",
        }:
            continue
        args = []
        for argument in node.args[:6]:
            args.append(
                {
                    "text": ast.unparse(argument)[:60],
                    "literal": isinstance(argument, ast.Constant),
                    "value": argument.value if isinstance(argument, ast.Constant) else None,
                }
            )
        facts.append(
            {
                "index": len(facts),
                "line": int(node.lineno),
                "method": method,
                "receiver": _name(node.func.value) if isinstance(node.func, ast.Attribute) else "",
                "args": args,
            }
        )
    if len(facts) > MAX_FACTS:
        facts = facts[:MAX_FACTS]
    return facts, {
        "scope_type": type(scope).__name__,
        "scope_line_start": int(getattr(scope, "lineno", 1)),
        "scope_line_end": int(getattr(scope, "end_lineno", 0)),
        "sink_line": int(sink.lineno),
        "sink_method": _method(sink),
    }


def _prompt(facts: list[dict[str, Any]], scope_facts: dict[str, Any]) -> str:
    fact_lines = []
    for fact in facts:
        args = "; ".join(
            f"arg{i}={item['text']}" + ("(LITERAL)" if item["literal"] else "")
            for i, item in enumerate(fact["args"])
        )
        fact_lines.append(
            f"[{fact['index']}] line {fact['line']} {fact['method']}"
            + (f" receiver={fact['receiver']}" if fact["receiver"] else "")
            + (f" | {args}" if args else "")
        )
    return (
        "你是 QGIS 低层 PyQGIS API 源码分析器。下面是源码中一个数据任务 scope 的"
        "预提取调用清单（index/行号/方法/参数，LITERAL 标记常量参数）。\n"
        "请从清单中选择构成'数据任务成分'的项，只输出一个 JSON 对象（不要输出其他文本）：\n"
        "{\n"
        '  "core_operations": [{"index": <清单index>, "literal_argument_indexes": [<常量参数的arg序号>], "argument_values": [{"index": <arg序号>, "value": "<清单中的参数文本>"}]}],\n'
        '  "input_evidence": {"index": <清单index> 或 null, "kind": "layer_getfeatures|feature_loop|layer_constructor|none"},\n'
        '  "attribute_handling": {"index": <清单index> 或 null, "kind": "attributes_copy|setattributes|setattribute|none"},\n'
        '  "output_sink": {"index": <清单index>}\n'
        "}\n"
        "规则：\n"
        "- index 必须是清单中的序号；index 为 null 表示该成分不存在。\n"
        "- core_operations 只选有数据操作语义的方法（buffer/centroid/fromWkt/fromPolygon/setAttribute/transform/setGeometry 等），"
        "不含纯访问器。\n"
        "- literal_argument_indexes 和 argument_values 中的 value 必须与清单完全一致（不用改写）。\n"
        "- input_evidence 的 kind 与所选方法匹配：getfeatures→layer_getfeatures 或 feature_loop；"
        "qgsvectorlayer/qgsrasterlayer→layer_constructor。\n"
        "- attribute_handling 的 kind 与所选方法匹配：attributes/setattributes→attributes_copy 或 setattributes；"
        "setattribute→setattribute。\n"
        "- output_sink 必须选 addFeature/addFeatures/writeAsVectorFormat/writeRaster 之一。\n"
        "调用清单：\n"
        + "\n".join(fact_lines)
        + f"\n（sink 锚点行：{scope_facts['sink_line']}，方法：{scope_facts['sink_method']}）"
    )


def _call_model(
    *, api_key: str, base_url: str, model: str, facts: list[dict[str, Any]], scope_facts: dict[str, Any]
) -> tuple[Any, dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _prompt(facts, scope_facts)}],
        "temperature": 0,
        "max_tokens": 16000,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
                status = response.status
            break
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(15 * (3 ** attempt))
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


def _verify_claims(facts: list[dict[str, Any]], proposal: Any, scope_facts: dict[str, Any]) -> dict[str, Any]:
    by_index = {fact["index"]: fact for fact in facts}
    errors: list[str] = []
    verified_cores: list[dict[str, Any]] = []
    for item in (proposal.get("core_operations") or [])[:8]:
        if not isinstance(item, dict):
            errors.append("non-dict core_operation")
            continue
        index = int(item.get("index") or -1)
        fact = by_index.get(index)
        if fact is None:
            errors.append(f"core index {index} not in fact list")
            continue
        if fact["method"] not in CORE_METHODS:
            errors.append(f"method {fact['method']} not in core whitelist")
            continue
        verified_args: dict[str, Any] = {}
        arg_errors: list[str] = []
        for claim in item.get("argument_values") or []:
            arg_index = int(claim.get("index") or -1)
            claimed_value = str(claim.get("value") or "")
            if not 0 <= arg_index < len(fact["args"]):
                arg_errors.append(f"arg index {arg_index} out of range")
                continue
            actual = fact["args"][arg_index]
            if claimed_value != str(actual["text"]):
                arg_errors.append(f"arg {arg_index} claimed {claimed_value} != fact {actual['text']}")
                continue
            verified_args[f"arg{arg_index}"] = {
                "value": actual["value"] if actual["literal"] else actual["text"],
                "kind": "literal" if actual["literal"] else "dynamic",
            }
        for lit_index in item.get("literal_argument_indexes") or []:
            if not 0 <= int(lit_index) < len(fact["args"]):
                arg_errors.append(f"literal arg index {lit_index} out of range")
            elif not fact["args"][int(lit_index)]["literal"]:
                arg_errors.append(f"arg {lit_index} claimed literal but fact is dynamic")
        if arg_errors:
            errors.append(f"core {fact['method']}@{fact['line']} args: {'; '.join(arg_errors)}")
            continue
        verified_cores.append(
            {
                "method": fact["method"],
                "line": fact["line"],
                "key_arguments": verified_args,
            }
        )
    input_evidence = proposal.get("input_evidence") or {}
    verified_input: dict[str, Any] | None = None
    if input_evidence.get("index") is not None:
        index = int(input_evidence.get("index") or -1)
        fact = by_index.get(index)
        kind = str(input_evidence.get("kind") or "none")
        if fact is None:
            errors.append(f"input index {index} not in fact list")
        elif fact["method"] not in INPUT_METHODS.get(kind, set()):
            errors.append(f"input kind {kind} method {fact['method']} not allowed")
        else:
            verified_input = {"index": index, "line": fact["line"], "kind": kind, "method": fact["method"]}
    attribute = proposal.get("attribute_handling") or {}
    verified_attribute: dict[str, Any] | None = None
    if attribute.get("index") is not None:
        index = int(attribute.get("index") or -1)
        fact = by_index.get(index)
        kind = str(attribute.get("kind") or "none")
        if fact is None:
            errors.append(f"attribute index {index} not in fact list")
        elif fact["method"] not in ATTRIBUTE_METHODS.get(kind, set()):
            errors.append(f"attribute kind {kind} method {fact['method']} not allowed")
        else:
            verified_attribute = {"index": index, "line": fact["line"], "kind": kind, "method": fact["method"]}
    sink = proposal.get("output_sink") or {}
    sink_ok = False
    if sink.get("index") is not None:
        index = int(sink.get("index") or -1)
        fact = by_index.get(index)
        if fact is not None and fact["method"] in SINKS and fact["line"] == scope_facts["sink_line"]:
            sink_ok = True
    if not sink_ok:
        errors.append("output_sink missing or not the anchored sink")
    return {
        "verified_core_operations": verified_cores,
        "verified_input_evidence": verified_input,
        "verified_attribute_handling": verified_attribute,
        "verified_output_sink": sink_ok,
        "verification_status": (
            "verified"
            if verified_cores and sink_ok and not errors
            else "deferred"
        ),
        "deferred_reasons": sorted(set(errors)),
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
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "source_ast_unparseable", "llm_called": False}
    extracted = _extract_facts(tree, sink_line)
    if extracted is None:
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "sink_not_unique_in_scope", "llm_called": False}
    facts, scope_facts = extracted
    if scope_facts["scope_line_end"] - scope_facts["scope_line_start"] + 1 > MAX_SCOPE_LINES:
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "scope_too_large", "llm_called": False, **scope_facts}
    if not facts:
        return {**row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": "no_facts_in_scope", "llm_called": False, **scope_facts}
    try:
        proposal, llm_metadata = _call_model(
            api_key=api_key, base_url=base_url, model=model, facts=facts, scope_facts=scope_facts
        )
    except (ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            **row, "schema": SCHEMA, "llm_status": "deferred", "deferred_reason": f"llm_call_failed:{type(error).__name__}",
            "llm_called": True, "llm_error": str(error)[:300], **scope_facts,
        }
    verification = _verify_claims(facts, proposal, scope_facts)
    result = {
        **row, "schema": SCHEMA, "llm_status": verification["verification_status"],
        "llm_called": True, "llm_proposal": proposal, "facts": facts, **scope_facts,
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
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        results.append(process_source(row, api_key=api_key, base_url=args.base_url, model=args.model))
        if (index + 1) % CHECKPOINT_EVERY == 0:
            _atomic_write(
                args.output_dir / "checkpoint_partial_v1.jsonl",
                "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in results),
            )
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
        "schema": "gis_recommend.qgis_api_route1_pilot_v2.summary.v1",
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
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    paths.append(summary_path)
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
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
