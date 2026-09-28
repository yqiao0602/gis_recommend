"""Fail-closed normalization for Joern QGIS flow evidence."""

# Schema validation intentionally exposes one ValueError contract for bad payloads.
# ruff: noqa: TRY004

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

QUERY_VERSION = "qgis-flow-v1"
EVIDENCE_STATUSES = {
    "complete",
    "partial",
    "insufficient",
    "ambiguous",
    "query_failure",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_QUERY_ID = re.compile(r"^[PA][1-5]$")


@dataclass(frozen=True)
class JoernNode:
    node_id: int
    label: str
    code: str
    source_path: str
    line: int
    column: int


@dataclass(frozen=True)
class JoernQueryEvidence:
    query_id: str
    status: str
    source_node_ids: tuple[int, ...]
    sink_node_ids: tuple[int, ...]
    flow_paths: tuple[tuple[int, ...], ...]
    control_path_node_ids: tuple[int, ...]
    terminal_node_ids: tuple[int, ...]
    evidence_kinds: tuple[str, ...]
    error: str


@dataclass(frozen=True)
class NormalizedJoernRecord:
    record_id: str
    source_sha256: str
    corpus_kind: str
    query_version: str
    evidence_status: str
    nodes: tuple[JoernNode, ...]
    queries: tuple[JoernQueryEvidence, ...]
    query_ids: tuple[str, ...]
    operator_ids: tuple[str, ...]
    semantic_calls: tuple[str, ...]
    dependency_edges: tuple[tuple[int, int], ...]
    terminal_node_ids: tuple[int, ...]
    ambiguity_reasons: tuple[str, ...]
    query_failures: tuple[tuple[str, str], ...]
    evidence_signature_sha256: str


def _sequence(value: Any, *, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence")
    return value


def _strings(value: Any, *, field: str) -> tuple[str, ...]:
    items = _sequence(value, field=field)
    strings = tuple(str(item) for item in items)
    if any(not item for item in strings):
        raise ValueError(f"{field} contains an empty value")
    return strings


def _node_ids(
    value: Any, *, field: str, known: set[int], preserve_order: bool = False
) -> tuple[int, ...]:
    items = _sequence(value, field=field)
    result: list[int] = []
    for item in items:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{field} contains a non-integer node ID")
        if item not in known:
            raise ValueError(f"{field} contains dangling node ID {item}")
        result.append(item)
    if len(result) != len(set(result)):
        raise ValueError(f"{field} contains duplicate node IDs")
    return tuple(result if preserve_order else sorted(result))


def _normalize_nodes(
    value: Any, *, allow_empty: bool = False
) -> tuple[JoernNode, ...]:
    items = _sequence(value, field="nodes")
    nodes: list[JoernNode] = []
    seen: set[int] = set()
    for raw in items:
        if not isinstance(raw, Mapping):
            raise ValueError("nodes contains a non-object")
        node_id = raw.get("node_id")
        line = raw.get("line")
        column = raw.get("column")
        if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id <= 0:
            raise ValueError("node_id must be a positive integer")
        if node_id in seen:
            raise ValueError(f"duplicate node_id {node_id}")
        if not isinstance(line, int) or isinstance(line, bool) or line <= 0:
            raise ValueError(f"node {node_id} lacks a positive source line")
        if not isinstance(column, int) or isinstance(column, bool) or column < 0:
            raise ValueError(f"node {node_id} lacks a source column")
        node = JoernNode(
            node_id=node_id,
            label=str(raw.get("label") or ""),
            code=str(raw.get("code") or ""),
            source_path=str(raw.get("source_path") or ""),
            line=line,
            column=column,
        )
        if not node.label or not node.code or not node.source_path:
            raise ValueError(f"node {node_id} lacks source-grounded evidence")
        seen.add(node_id)
        nodes.append(node)
    if not nodes and not allow_empty:
        raise ValueError("nodes must not be empty")
    stable = sorted(
        nodes,
        key=lambda node: (node.source_path, node.line, node.column, node.node_id),
    )
    if nodes != stable:
        raise ValueError("nodes must be sorted by source position")
    return tuple(nodes)


def _normalize_queries(
    value: Any, *, corpus_kind: str, known_nodes: set[int]
) -> tuple[JoernQueryEvidence, ...]:
    items = _sequence(value, field="queries")
    expected_prefix = "P" if corpus_kind == "processing" else "A"
    queries: list[JoernQueryEvidence] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, Mapping):
            raise ValueError("queries contains a non-object")
        query_id = str(raw.get("query_id") or "")
        if not _QUERY_ID.fullmatch(query_id) or not query_id.startswith(expected_prefix):
            raise ValueError(f"invalid query_id {query_id!r} for {corpus_kind}")
        if query_id in seen:
            raise ValueError(f"duplicate query_id {query_id}")
        status = str(raw.get("status") or "")
        if status not in EVIDENCE_STATUSES:
            raise ValueError(f"invalid query status {status!r}")
        paths: list[tuple[int, ...]] = []
        for raw_path in _sequence(raw.get("flow_paths", []), field="flow_paths"):
            path = _node_ids(
                raw_path,
                field=f"{query_id}.flow_path",
                known=known_nodes,
                preserve_order=True,
            )
            if len(path) < 2:
                raise ValueError(f"{query_id}.flow_path must contain at least two nodes")
            paths.append(path)
        paths = sorted(set(paths))
        error = str(raw.get("error") or "")
        if status == "query_failure" and not error:
            raise ValueError(f"{query_id} query_failure lacks error evidence")
        query = JoernQueryEvidence(
            query_id=query_id,
            status=status,
            source_node_ids=_node_ids(
                raw.get("source_node_ids", []),
                field=f"{query_id}.source_node_ids",
                known=known_nodes,
            ),
            sink_node_ids=_node_ids(
                raw.get("sink_node_ids", []),
                field=f"{query_id}.sink_node_ids",
                known=known_nodes,
            ),
            flow_paths=tuple(paths),
            control_path_node_ids=_node_ids(
                raw.get("control_path_node_ids", []),
                field=f"{query_id}.control_path_node_ids",
                known=known_nodes,
            ),
            terminal_node_ids=_node_ids(
                raw.get("terminal_node_ids", []),
                field=f"{query_id}.terminal_node_ids",
                known=known_nodes,
            ),
            evidence_kinds=tuple(
                sorted(set(_strings(raw.get("evidence_kinds", []), field="evidence_kinds")))
            ),
            error=error,
        )
        seen.add(query_id)
        queries.append(query)
    if not queries:
        raise ValueError("queries must not be empty")
    return tuple(sorted(queries, key=lambda query: query.query_id))


def _normalize_edges(value: Any, *, operator_count: int) -> tuple[tuple[int, int], ...]:
    items = _sequence(value, field="dependency_edges")
    edges: list[tuple[int, int]] = []
    for raw in items:
        pair = _sequence(raw, field="dependency edge")
        if len(pair) != 2 or any(
            not isinstance(item, int) or isinstance(item, bool) for item in pair
        ):
            raise ValueError("dependency edge must contain two integer indexes")
        source, target = int(pair[0]), int(pair[1])
        if not 0 <= source < operator_count or not 0 <= target < operator_count:
            raise ValueError("dependency edge contains a dangling operator index")
        if source == target:
            raise ValueError("dependency edge cannot be self-referential")
        edges.append((source, target))
    if len(edges) != len(set(edges)):
        raise ValueError("dependency_edges contains duplicates")
    return tuple(sorted(edges))


def _query_dict(query: JoernQueryEvidence) -> dict[str, Any]:
    return {
        "query_id": query.query_id,
        "status": query.status,
        "source_node_ids": list(query.source_node_ids),
        "sink_node_ids": list(query.sink_node_ids),
        "flow_paths": [list(path) for path in query.flow_paths],
        "control_path_node_ids": list(query.control_path_node_ids),
        "terminal_node_ids": list(query.terminal_node_ids),
        "evidence_kinds": list(query.evidence_kinds),
        "error": query.error,
    }


def _signature(
    *,
    corpus_kind: str,
    nodes: tuple[JoernNode, ...],
    queries: tuple[JoernQueryEvidence, ...],
    operator_ids: tuple[str, ...],
    semantic_calls: tuple[str, ...],
    dependency_edges: tuple[tuple[int, int], ...],
) -> str:
    node_index = {node.node_id: node for node in nodes}

    def grounded(node_ids: Sequence[int]) -> list[dict[str, Any]]:
        return [
            {
                "label": node_index[node_id].label,
                "code": node_index[node_id].code,
                "source_path": node_index[node_id].source_path,
                "line": node_index[node_id].line,
                "column": node_index[node_id].column,
            }
            for node_id in node_ids
        ]

    payload = {
        "corpus_kind": corpus_kind,
        "operator_ids": list(operator_ids),
        "semantic_calls": list(semantic_calls),
        "dependency_edges": [list(edge) for edge in dependency_edges],
        "queries": [
            {
                "query_id": query.query_id,
                "status": query.status,
                "paths": [grounded(path) for path in query.flow_paths],
                "controls": grounded(query.control_path_node_ids),
                "terminals": grounded(query.terminal_node_ids),
                "evidence_kinds": list(query.evidence_kinds),
            }
            for query in queries
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_joern_record(raw: Mapping[str, Any]) -> NormalizedJoernRecord:
    """Validate one raw Joern export and return stable, fail-closed evidence."""
    record_id = str(raw.get("record_id") or "")
    source_sha256 = str(raw.get("source_sha256") or "").lower()
    corpus_kind = str(raw.get("corpus_kind") or "")
    query_version = str(raw.get("query_version") or "")
    evidence_status = str(raw.get("evidence_status") or "")
    if not record_id:
        raise ValueError("record_id is required")
    if not _SHA256.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be a lowercase 64-character hex digest")
    if corpus_kind not in {"processing", "api"}:
        raise ValueError("corpus_kind must be processing or api")
    if query_version != QUERY_VERSION:
        raise ValueError(f"query_version must be {QUERY_VERSION}")
    if evidence_status not in EVIDENCE_STATUSES:
        raise ValueError(f"invalid evidence_status {evidence_status!r}")

    nodes = _normalize_nodes(
        raw.get("nodes"),
        allow_empty=evidence_status in {"insufficient", "query_failure"},
    )
    known_nodes = {node.node_id for node in nodes}
    queries = _normalize_queries(
        raw.get("queries"), corpus_kind=corpus_kind, known_nodes=known_nodes
    )
    query_ids = tuple(query.query_id for query in queries)
    operator_ids = _strings(raw.get("operator_ids", []), field="operator_ids")
    if len(operator_ids) != len(set(operator_ids)):
        raise ValueError("operator_ids contains duplicates")
    semantic_calls = _strings(raw.get("semantic_calls", []), field="semantic_calls")
    dependency_edges = _normalize_edges(
        raw.get("dependency_edges", []), operator_count=len(operator_ids)
    )
    terminal_node_ids = tuple(
        sorted({node_id for query in queries for node_id in query.terminal_node_ids})
    )
    ambiguity_reasons = tuple(
        sorted(set(_strings(raw.get("ambiguity_reasons", []), field="ambiguity_reasons")))
    )
    query_failures = tuple(
        (query.query_id, query.error)
        for query in queries
        if query.status == "query_failure"
    )

    expected_ids = tuple(
        f"{'P' if corpus_kind == 'processing' else 'A'}{index}"
        for index in range(1, 6)
    )
    if evidence_status == "complete":
        if query_ids != expected_ids:
            raise ValueError("complete evidence requires all five query IDs")
        if any(query.status != "complete" for query in queries):
            raise ValueError("complete evidence contains a non-complete query")
        if not terminal_node_ids:
            raise ValueError("complete evidence requires a terminal")
        if not any(query.flow_paths for query in queries):
            raise ValueError("complete evidence requires a flow path")
    if evidence_status == "ambiguous" and not ambiguity_reasons:
        raise ValueError("ambiguous evidence requires ambiguity reasons")
    if evidence_status == "query_failure" and not query_failures:
        raise ValueError("query_failure evidence requires a failed query")
    if query_failures and evidence_status != "query_failure":
        raise ValueError("failed query requires query_failure evidence status")
    if any(query.status == "ambiguous" for query in queries) and evidence_status not in {
        "ambiguous",
        "query_failure",
    }:
        raise ValueError("ambiguous query cannot produce a complete record")

    return NormalizedJoernRecord(
        record_id=record_id,
        source_sha256=source_sha256,
        corpus_kind=corpus_kind,
        query_version=query_version,
        evidence_status=evidence_status,
        nodes=nodes,
        queries=queries,
        query_ids=query_ids,
        operator_ids=operator_ids,
        semantic_calls=semantic_calls,
        dependency_edges=dependency_edges,
        terminal_node_ids=terminal_node_ids,
        ambiguity_reasons=ambiguity_reasons,
        query_failures=query_failures,
        evidence_signature_sha256=_signature(
            corpus_kind=corpus_kind,
            nodes=nodes,
            queries=queries,
            operator_ids=operator_ids,
            semantic_calls=semantic_calls,
            dependency_edges=dependency_edges,
        ),
    )


def normalized_joern_record_dict(record: NormalizedJoernRecord) -> dict[str, Any]:
    """Return a JSON-serializable normalized sidecar record."""
    return {
        "schema": "gis_recommend.qgis_joern_sidecar.v1",
        "record_id": record.record_id,
        "source_sha256": record.source_sha256,
        "corpus_kind": record.corpus_kind,
        "query_version": record.query_version,
        "evidence_status": record.evidence_status,
        "nodes": [
            {
                "node_id": node.node_id,
                "label": node.label,
                "code": node.code,
                "source_path": node.source_path,
                "line": node.line,
                "column": node.column,
            }
            for node in record.nodes
        ],
        "queries": [_query_dict(query) for query in record.queries],
        "query_ids": list(record.query_ids),
        "operator_ids": list(record.operator_ids),
        "semantic_calls": list(record.semantic_calls),
        "dependency_edges": [list(edge) for edge in record.dependency_edges],
        "terminal_node_ids": list(record.terminal_node_ids),
        "ambiguity_reasons": list(record.ambiguity_reasons),
        "query_failures": [list(failure) for failure in record.query_failures],
        "evidence_signature_sha256": record.evidence_signature_sha256,
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_row_emitted": False,
    }


def normalize_joern_jsonl(input_path: Path, output_path: Path) -> int:
    """Normalize a raw Joern JSONL export and atomically write stable evidence."""
    records: list[NormalizedJoernRecord] = []
    with Path(input_path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, Mapping):
                raise ValueError(f"line {line_number} must contain a JSON object")
            records.append(normalize_joern_record(raw))

    records.sort(
        key=lambda row: (row.corpus_kind, row.record_id, row.source_sha256)
    )
    keys = [(row.corpus_kind, row.record_id, row.source_sha256) for row in records]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate normalized Joern record authority")

    destination = Path(output_path)
    partial = destination.with_suffix(destination.suffix + ".partial")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with partial.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(
                    json.dumps(
                        normalized_joern_record_dict(record),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return len(records)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    normalize_joern_jsonl(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
