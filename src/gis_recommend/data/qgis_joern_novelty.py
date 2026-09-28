"""Validate Joern novelty claims against lexical Python function scopes."""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

NOVELTY_KIND = "cross_function_parameter_return_dataflow"


class _FunctionScopes(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.scopes: list[tuple[int, int, str]] = []

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        qualified = ".".join((*self.stack, node.name))
        self.scopes.append(
            (node.lineno, int(node.end_lineno or node.lineno), qualified)
        )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_function(node)


def _lexical_scopes(source_text: str) -> list[tuple[int, int, str]]:
    visitor = _FunctionScopes()
    visitor.visit(ast.parse(source_text))
    return visitor.scopes


def _scope_at_line(line: int, scopes: Sequence[tuple[int, int, str]]) -> str:
    matches = [scope for scope in scopes if scope[0] <= line <= scope[1]]
    if not matches:
        return "<module>"
    return min(matches, key=lambda scope: scope[1] - scope[0])[2]


def analyze_cross_function_novelty(
    joern_row: Mapping[str, Any], source_text: str
) -> dict[str, Any]:
    """Return only paths proven to cross lexical Python function scopes."""
    corpus_kind = str(joern_row.get("corpus_kind") or "")
    query_id = "P4" if corpus_kind == "processing" else "A3"
    nodes = {
        int(node["node_id"]): node
        for node in joern_row.get("nodes", [])
        if isinstance(node, Mapping) and "node_id" in node
    }
    queries = [
        query
        for query in joern_row.get("queries", [])
        if isinstance(query, Mapping) and query.get("query_id") == query_id
    ]
    if len(queries) != 1:
        raise ValueError(f"expected exactly one {query_id} query")
    scopes = _lexical_scopes(source_text)
    proof_paths: list[dict[str, Any]] = []
    for path in queries[0].get("flow_paths", []):
        lexical_scopes: list[str] = []
        lines: list[int] = []
        for raw_node_id in path:
            node = nodes.get(int(raw_node_id))
            if node is None or node.get("line") is None:
                continue
            line = int(node["line"])
            lines.append(line)
            scope = _scope_at_line(line, scopes)
            if not lexical_scopes or lexical_scopes[-1] != scope:
                lexical_scopes.append(scope)
        if len(set(lexical_scopes)) <= 1:
            continue
        proof_paths.append(
            {
                "node_ids": [int(node_id) for node_id in path],
                "source_lines": lines,
                "lexical_scopes": lexical_scopes,
            }
        )
    return {
        "record_id": str(joern_row["record_id"]),
        "corpus_kind": corpus_kind,
        "query_id": query_id,
        "candidate_path_count": len(queries[0].get("flow_paths", [])),
        "cross_function_path_count": len(proof_paths),
        "novelty_kinds": [NOVELTY_KIND] if proof_paths else [],
        "proof_paths": proof_paths,
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_row_emitted": False,
    }


def build_novelty_report(
    joern_rows: Sequence[Mapping[str, Any]],
    *,
    authorities: Mapping[str, Mapping[str, Any]],
    source_texts: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    complete = [
        row for row in joern_rows if row.get("evidence_status") == "complete"
    ]
    audits = [
        analyze_cross_function_novelty(row, source_texts[str(row["record_id"])])
        for row in complete
    ]
    novelty = [row for row in audits if row["cross_function_path_count"] > 0]
    family_bodies: dict[str, set[str]] = defaultdict(set)
    for row in novelty:
        record_id = str(row["record_id"])
        authority = authorities[record_id]
        family_id = f"{row['corpus_kind']}:{NOVELTY_KIND}"
        family_bodies[family_id].add(
            str(authority["normalized_source_body_sha256"])
        )
    families = [
        {
            "family_id": family_id,
            "previously_unresolved": True,
            "support": len(family_bodies[family_id]),
            "source_disjoint": False,
            "calibration_false_positives": None,
            "holdout_false_positives": None,
        }
        for family_id in sorted(family_bodies)
    ]
    report = {
        "schema": "gis_recommend.qgis_joern_novelty_report.v1",
        "complete_rows": len(complete),
        "cross_function_novelty_rows": len(novelty),
        "local_only_complete_rows": len(complete) - len(novelty),
        "rows": audits,
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_rows_emitted": 0,
    }
    promotion = {
        "schema": "gis_recommend.qgis_external_pilot_promotion_families.v1",
        "families": families,
        "training_rows_emitted": 0,
    }
    return report, promotion
