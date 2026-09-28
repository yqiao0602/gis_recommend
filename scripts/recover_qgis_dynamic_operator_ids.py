#!/usr/bin/env python3
"""Recover QGIS operator IDs only when every dynamic call has one static value."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tempfile
import warnings
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from analyze_qgis_processing_resolution_census import (
    _assignment_definitions,
    _is_processing_call,
    _parents,
    _static_strings,
)
from recover_qgis_legacy_provider_ids import (
    _literal_call_sites,
    canonicalize_operator_id,
    load_catalog_ids,
)

from gis_recommend.data.qgis_conversion_features import (
    extract_conversion_features,
)
from gis_recommend.data.qgis_conversion_rules import route_candidate
from gis_recommend.data.qgis_subworkflow_splitter import (
    literalize_processing_operator_ids,
)

SCHEMA = "gis_recommend.qgis_dynamic_operator_recovery.v1"
MATCH_ALGO_CONTRACT_VERSION = "mappy-v0.3.2-matchAlgo-v1"
MATCH_ALGO_PACKAGE_SHA256 = (
    "738c8989c4bf1a4062f53bd8e3519d485c1610d4382b16b7040757774ba32f8a"
)
_MAPPY_V032_HEADER = re.compile(
    r"(?ims)^\s*#?\s*Plugin\s*:\s*mappy\s*$.*?^\s*#?\s*Version\s*:\s*v0\.3\.2\s*$"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _has_frozen_match_algo_provenance(tree: ast.AST, call: ast.Call) -> bool:
    """Require the exact, versioned external wrapper contract before recovery."""

    imported = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level >= 1
            and node.module == "mappy_utils"
            and any(alias.name == "matchAlgo" and alias.asname is None for alias in node.names)
            and node.lineno < call.lineno
        ):
            imported = True
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "matchAlgo" for target in targets):
                return False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and (
            node.name == "matchAlgo"
            or (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(
                    argument.arg == "matchAlgo"
                    for argument in (
                        *node.args.posonlyargs,
                        *node.args.args,
                        *node.args.kwonlyargs,
                    )
                )
            )
        ):
            return False
        if isinstance(node, ast.Import) and any(
            (alias.asname or alias.name) == "matchAlgo" for alias in node.names
        ):
            return False
        if (
            isinstance(node, ast.ImportFrom)
            and not (
                node.level >= 1
                and node.module == "mappy_utils"
                and any(
                    alias.name == "matchAlgo" and alias.asname is None
                    for alias in node.names
                )
            )
            and any((alias.asname or alias.name) == "matchAlgo" for alias in node.names)
        ):
            return False
    return imported


def _frozen_match_algo_values(
    source_text: str,
    tree: ast.AST,
    call: ast.Call,
) -> set[str] | None:
    expression = call.args[0]
    if not _MAPPY_V032_HEADER.search(source_text):
        return None
    if not (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "matchAlgo"
        and len(expression.args) == 1
        and not expression.keywords
        and isinstance(expression.args[0], ast.Constant)
        and isinstance(expression.args[0].value, str)
        and expression.args[0].value.strip()
        and _has_frozen_match_algo_provenance(tree, call)
    ):
        return None
    return {expression.args[0].value.strip()}


def _ordered_calls(
    source_text: str,
    *,
    catalog_ids: set[str] | None = None,
) -> tuple[ast.AST, list[ast.Call], list[dict[str, Any]]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source_text)
    parents = _parents(tree)
    definitions = _assignment_definitions(tree, parents)
    calls = sorted(
        (node for node in ast.walk(tree) if _is_processing_call(node)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    evidence: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        expression = call.args[0]
        literal = (
            expression.value.strip()
            if isinstance(expression, ast.Constant)
            and isinstance(expression.value, str)
            and expression.value.strip()
            else None
        )
        if literal is not None:
            operator_ids = [literal]
            kind = "literal"
        else:
            resolved = _frozen_match_algo_values(source_text, tree, call)
            if resolved is None:
                resolved = _static_strings(
                    expression,
                    context=call,
                    parents=parents,
                    definitions=definitions,
                )
            operator_ids = sorted(
                value.strip() for value in (resolved or set()) if value.strip()
            )
            kind = "dynamic"
        wrapper_contract = None
        if (
            isinstance(expression, ast.Call)
            and expression.func.__class__ is ast.Name
            and expression.func.id == "matchAlgo"
            and _frozen_match_algo_values(source_text, tree, call) is not None
            and operator_ids
        ):
            wrapper_contract = MATCH_ALGO_CONTRACT_VERSION
            if catalog_ids is not None:
                verified: set[str] = set()
                for value in operator_ids:
                    normalized = value.strip().lower()
                    if normalized in catalog_ids:
                        verified.add(normalized)
                    elif ":" in normalized:
                        fallback = "qgis:" + normalized.split(":", 1)[1]
                        if fallback in catalog_ids:
                            verified.add(fallback)
                operator_ids = sorted(verified)
        evidence.append(
            {
                "call_index": index,
                "line": call.lineno,
                "line_end": call.end_lineno or call.lineno,
                "expression_kind": type(expression).__name__,
                "expression": ast.unparse(expression),
                "kind": kind,
                "status": (
                    "resolved_single"
                    if len(operator_ids) == 1
                    else "branch_multi_candidate"
                    if len(operator_ids) > 1
                    else "unresolved"
                ),
                "operator_ids": operator_ids,
                "wrapper_contract": wrapper_contract,
            }
        )
    return tree, calls, evidence


def _resolution_status(evidence: list[dict[str, Any]]) -> str:
    dynamic = [item for item in evidence if item["kind"] == "dynamic"]
    if not dynamic:
        return "exclude_no_dynamic_call"
    if any(not item["operator_ids"] for item in dynamic):
        return "defer_unresolved_dynamic_call"
    if any(len(item["operator_ids"]) > 1 for item in dynamic):
        return "defer_branch_multi_candidate"
    return "fixed_chain_recovered"


def build_literalized_analysis_source(
    source_text: str, catalog_ids: set[str]
) -> tuple[str, list[dict[str, Any]]]:
    _, calls, evidence = _ordered_calls(source_text, catalog_ids=catalog_ids)
    if _resolution_status(evidence) != "fixed_chain_recovered":
        raise ValueError("source does not contain a fully fixed dynamic operator chain")
    original_ids = [item["operator_ids"][0].strip().lower() for item in evidence]
    resolutions = [canonicalize_operator_id(value, catalog_ids) for value in original_ids]
    if any(value is None for value, _ in resolutions):
        raise ValueError("source contains operator IDs outside the verified catalog")
    canonical_ids = [str(value) for value, _ in resolutions]
    call_sites = [
        {
            "operator_id": canonical,
            "line_start": call.lineno,
            "line_end": call.end_lineno or call.lineno,
            "original_expression": item["expression"],
            "resolution_kind": item["kind"],
        }
        for call, item, canonical in zip(calls, evidence, canonical_ids)
    ]
    return (
        literalize_processing_operator_ids(source_text, call_sites=call_sites),
        call_sites,
    )


def _deferred_action(status: str) -> tuple[str, str]:
    return {
        "exclude_no_dynamic_call": (
            "exclude_no_dynamic_call",
            "reject-no-dynamic-call-v1",
        ),
        "defer_unresolved_dynamic_call": (
            "defer_operator_resolution",
            "defer-unresolved-dynamic-id-v1",
        ),
        "defer_branch_multi_candidate": (
            "defer_control_flow_paths",
            "defer-branch-path-enumeration-v1",
        ),
    }[status]


def _base_row(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    digest = str(row.get("content_sha256") or "")
    return {
        "schema": SCHEMA,
        "record_id": digest[:24],
        "content_sha256": digest,
        "source_sha256": digest,
        "source_root_id": row.get("source_root_id"),
        "relative_path": row.get("relative_path"),
        "source_path": str(source_path),
        "training_admission": "not_granted_recovery_rule_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def recover_row(row: dict[str, Any], catalog_ids: set[str]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path") or ""))
    result = _base_row(row, source_path)
    if not source_path.is_file() or _sha256(source_path) != result["content_sha256"]:
        result.update(
            {
                "resolution_status": "exclude_source_authority_failure",
                "normalization_status": "unresolved",
                "canonical_operator_ids": [],
                "unresolved_operator_ids": [],
                "provider_migrations": [],
                "dynamic_call_evidence": [],
                "resolved_dynamic_call_count": 0,
                "unresolved_dynamic_call_count": 0,
                "structure_action": "exclude_source_authority_failure",
                "structure_rule_id": "reject-source-authority-v1",
                "action": "exclude_source_authority_failure",
                "rule_id": "reject-source-authority-v1",
                "operator_ids": [],
                "ordered_operator_ids": [],
                "call_sites": [],
                "dependency_edges": [],
                "structure_evidence": {},
            }
        )
        return result

    source_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        _tree, _calls, evidence = _ordered_calls(source_text, catalog_ids=catalog_ids)
    except SyntaxError:
        result.update(
            {
                "resolution_status": "exclude_source_parse_failure",
                "normalization_status": "unresolved",
                "canonical_operator_ids": [],
                "unresolved_operator_ids": [],
                "provider_migrations": [],
                "dynamic_call_evidence": [],
                "resolved_dynamic_call_count": 0,
                "unresolved_dynamic_call_count": 0,
                "structure_action": "exclude_source_parse_failure",
                "structure_rule_id": "reject-source-parse-v1",
                "action": "exclude_source_parse_failure",
                "rule_id": "reject-source-parse-v1",
                "operator_ids": [],
                "ordered_operator_ids": [],
                "call_sites": [],
                "dependency_edges": [],
                "structure_evidence": {},
            }
        )
        return result

    dynamic_evidence = [item for item in evidence if item["kind"] == "dynamic"]
    resolved_dynamic = sum(bool(item["operator_ids"]) for item in dynamic_evidence)
    unresolved_dynamic = sum(not item["operator_ids"] for item in dynamic_evidence)
    status = _resolution_status(evidence)
    result.update(
        {
            "resolution_status": status,
            "dynamic_call_evidence": dynamic_evidence,
            "resolved_dynamic_call_count": resolved_dynamic,
            "unresolved_dynamic_call_count": unresolved_dynamic,
            "wrapper_contracts": sorted(
                {
                    item["wrapper_contract"]
                    for item in evidence
                    if item.get("wrapper_contract")
                }
            ),
        }
    )
    if status != "fixed_chain_recovered":
        action, rule = _deferred_action(status)
        result.update(
            {
                "normalization_status": "unresolved",
                "canonical_operator_ids": [],
                "unresolved_operator_ids": [],
                "provider_migrations": [],
                "structure_action": action,
                "structure_rule_id": rule,
                "action": action,
                "rule_id": rule,
                "operator_ids": [],
                "ordered_operator_ids": [],
                "call_sites": [],
                "dependency_edges": [],
                "structure_evidence": {},
            }
        )
        return result

    original_ids = [item["operator_ids"][0].strip().lower() for item in evidence]
    resolutions = [canonicalize_operator_id(value, catalog_ids) for value in original_ids]
    canonical_ids = [value for value, _ in resolutions if value]
    unresolved_ids = [
        original
        for original, (canonical, _) in zip(original_ids, resolutions)
        if canonical is None
    ]
    migrations = [
        {"source": original, "target": canonical, "rule": rule}
        for original, (canonical, rule) in zip(original_ids, resolutions)
        if canonical is not None and rule == "qgis_to_native_same_slug"
    ]
    result.update(
        {
            "original_operator_ids": original_ids,
            "canonical_operator_ids": canonical_ids,
            "unresolved_operator_ids": list(dict.fromkeys(unresolved_ids)),
            "provider_migrations": migrations,
            "normalization_status": (
                "fully_normalized"
                if not unresolved_ids
                else "partially_normalized"
                if canonical_ids
                else "unresolved"
            ),
        }
    )
    if unresolved_ids:
        result.update(
            {
                "structure_action": "defer_operator_resolution",
                "structure_rule_id": "defer-unresolved-provider-id-v1",
                "action": "defer_operator_resolution",
                "rule_id": "defer-unresolved-provider-id-v1",
                "operator_ids": canonical_ids,
                "ordered_operator_ids": canonical_ids,
                "call_sites": [],
                "dependency_edges": [],
                "structure_evidence": {},
            }
        )
        return result

    analysis_source, call_sites = build_literalized_analysis_source(
        source_text, catalog_ids
    )
    analysis_sites = _literal_call_sites(analysis_source)
    extracted = extract_conversion_features(analysis_source, call_sites=analysis_sites)
    features = dict(extracted.data)
    if [str(value).lower() for value in features["operator_ids"]] != canonical_ids:
        action = "exclude_candidate_alignment_failure"
        rule = "reject-candidate-alignment-v1"
        decision_evidence = {
            "canonical_operator_ids": canonical_ids,
            "extracted_operator_ids": features["operator_ids"],
        }
    else:
        route_input = {
            "mapped_l3_chain": ["L3_PENDING"] * len(canonical_ids),
            "call_graph_status": (
                "disconnected_candidate_scopes"
                if features.get("workflow_unit_scope") == "cross_scope_candidate"
                else "single_scope"
            ),
            "api_pattern_calls": [],
        }
        decision = route_candidate(route_input, features)
        action = decision.action
        rule = decision.rule_id
        decision_evidence = decision.evidence
    result.update(
        {
            "structure_action": action,
            "structure_rule_id": rule,
            "action": action,
            "rule_id": rule,
            "operator_ids": canonical_ids,
            "ordered_operator_ids": canonical_ids,
            "call_sites": call_sites,
            "dependency_edges": features.get("dependency_edges") or [],
            "dependency_edge_evidence": features.get("dependency_edge_evidence")
            or [],
            "workflow_unit_scope": features.get("workflow_unit_scope"),
            "structure_evidence": decision_evidence,
            "feature_signature_hash": extracted.signature_hash,
            "analysis_source_kind": "in_memory_span_preserving_literalized_source",
        }
    )
    return result


def build_recovery(
    census_path: Path, catalog_ids: set[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs = [
        row
        for row in _load_jsonl(census_path)
        if row.get("primary_layer") == "dynamic_or_blank_processing_id"
    ]
    rows = [recover_row(row, catalog_ids) for row in inputs]
    statuses = Counter(row["resolution_status"] for row in rows)
    normalization = Counter(row["normalization_status"] for row in rows)
    actions = Counter(row["structure_action"] for row in rows)
    fixed = [row for row in rows if row["resolution_status"] == "fixed_chain_recovered"]
    fully = [row for row in fixed if row["normalization_status"] == "fully_normalized"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_dynamic_or_blank_records": len(inputs),
        "resolution_status_counts": dict(sorted(statuses.items())),
        "normalization_status_counts": dict(sorted(normalization.items())),
        "fixed_chain_recovered_records": len(fixed),
        "fully_normalized_fixed_chain_records": len(fully),
        "fully_normalized_multistep_records": sum(
            len(row["canonical_operator_ids"]) >= 2 for row in fully
        ),
        "structure_action_counts": dict(sorted(actions.items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_recovery_rule_only",
        "next_gate": "apply stable101 L3 mapping and source-grounded structure gates",
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    census_path: Path,
    catalog_path: Path,
    output_dir: Path,
) -> None:
    ledger_path = output_dir / "dynamic_operator_recovery_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        ledger_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    report = [
        "# QGIS Dynamic Operator Recovery v1",
        "",
        f"- Input records: {summary['input_dynamic_or_blank_records']}",
        f"- Fixed chains recovered: {summary['fixed_chain_recovered_records']}",
        f"- Fully normalized fixed chains: {summary['fully_normalized_fixed_chain_records']}",
        "- Training rows emitted: 0",
        "",
        "## Resolution Status",
        "",
        "| Status | Records |",
        "|---|---:|",
        *[
            f"| {status} | {count} |"
            for status, count in summary["resolution_status_counts"].items()
        ],
        "",
    ]
    _atomic_write(report_path, "\n".join(report))
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {
                    census_path.name: _sha256(census_path),
                    catalog_path.name: _sha256(catalog_path),
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (ledger_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = build_recovery(args.census, load_catalog_ids(args.catalog))
    write_outputs(
        rows,
        summary,
        census_path=args.census,
        catalog_path=args.catalog,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
