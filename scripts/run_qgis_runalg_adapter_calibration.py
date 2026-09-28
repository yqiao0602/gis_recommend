#!/usr/bin/env python3
"""Run an isolated structural calibration for legacy ``processing.runalg``.

The adapter preserves every source line and only changes AST-confirmed
``processing.runalg`` attribute tokens to the same-width ``processing.run``
form. This lets the existing extractor recover call order and variable data
dependencies without pretending that positional legacy parameters provide the
dictionary-based I/O contracts required by the production path.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import sys
import tempfile
import tokenize
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import extract_conversion_features

SCHEMA = "gis_recommend.qgis_processing_runalg_adapter_calibration.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    content = (
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value)
        if isinstance(value, list)
        else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def rewrite_runalg_to_run(source: str) -> tuple[str, list[int]]:
    """Rewrite direct ``processing.runalg`` tokens without changing line shape."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        ast.parse(source)
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    replacements: list[tuple[int, int, int]] = []
    significant = [
        token
        for token in tokens
        if token.type not in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}
    ]
    for index, token in enumerate(significant):
        if token.type != tokenize.NAME or token.string != "runalg" or index < 2:
            continue
        base, dot = significant[index - 2 : index]
        if base.type == tokenize.NAME and base.string == "processing" and dot.string == ".":
            replacements.append((token.start[0], token.start[1], token.end[1]))
    lines = source.splitlines(keepends=True)
    for line, start, end in reversed(replacements):
        text = lines[line - 1]
        if text[start:end] != "runalg":
            raise ValueError("token/source offset mismatch while rewriting runalg")
        lines[line - 1] = text[:start] + "run   " + text[end:]
    return "".join(lines), [line for line, _, _ in replacements]


def _selected_call_sites(row: dict[str, Any]) -> list[dict[str, Any]]:
    sites = []
    for site in row.get("runalg_call_sites") or []:
        operator_id = str(site.get("literal_operator_id") or "")
        if operator_id:
            sites.append(
                {
                    "operator_id": operator_id,
                    "line_start": int(site["line_start"]),
                    "line_end": int(site["line_end"]),
                }
            )
    return sites


def calibrate_row(row: dict[str, Any]) -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "record_id": str(row.get("record_id") or ""),
        "source_sha256": str(row.get("source_sha256") or ""),
        "normalized_source_body_sha256": str(row.get("normalized_source_body_sha256") or ""),
        "source_path": str(row.get("source_path") or ""),
        "source_root_id": str(row.get("source_root_id") or ""),
        "calibration_role": str(row.get("calibration_role") or ""),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_runalg_adapter_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "io_contract_status": "not_recovered_legacy_positional",
    }
    path = Path(result["source_path"])
    if not path.is_file():
        return {**result, "status": "source_missing", "reason": "source_file_missing"}
    if _sha256_file(path) != result["source_sha256"]:
        return {**result, "status": "source_hash_mismatch", "reason": "packet_sha_mismatch"}
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    expected_sites = _selected_call_sites(row)
    if not expected_sites:
        return {**result, "status": "invalid_packet", "reason": "no_literal_runalg_call_sites"}
    try:
        rewritten, rewritten_lines = rewrite_runalg_to_run(source)
    except (SyntaxError, tokenize.TokenError, ValueError) as exc:
        return {**result, "status": "adapter_rewrite_failed", "reason": str(exc)}
    expected_lines = [int(site["line_start"]) for site in expected_sites]
    if rewritten_lines != expected_lines:
        return {
            **result,
            "status": "adapter_rewrite_failed",
            "reason": "rewritten_call_lines_do_not_match_frozen_packet",
            "expected_lines": expected_lines,
            "rewritten_lines": rewritten_lines,
        }
    features = extract_conversion_features(rewritten, call_sites=expected_sites).data
    operator_ids = list(features["operator_ids"])
    expected_operator_ids = [site["operator_id"] for site in expected_sites]
    exact_operator_sequence = operator_ids == expected_operator_ids
    alignment = features["candidate_alignment_status"] == "candidate_alignment_matched"
    if not alignment or not exact_operator_sequence:
        return {
            **result,
            "status": "adapter_alignment_failed",
            "reason": "selected_literal_runalg_sites_not_exactly_recovered",
            "expected_operator_ids": expected_operator_ids,
            "operator_ids": operator_ids,
            "candidate_alignment_status": features["candidate_alignment_status"],
        }
    return {
        **result,
        "status": "adapter_structural_recovered",
        "reason": "exact_literal_call_alignment_only",
        "adapter_rewrite": "direct_processing_runalg_token_to_same_width_run",
        "rewritten_call_lines": rewritten_lines,
        "expected_operator_ids": expected_operator_ids,
        "operator_ids": operator_ids,
        "operator_count": len(operator_ids),
        "candidate_alignment_status": features["candidate_alignment_status"],
        "dependency_edges": features["dependency_edges"],
        "dependency_edge_evidence": features["dependency_edge_evidence"],
        "unresolved_output_references": features["unresolved_output_references"],
        "control_flow_kinds": features["control_flow_kinds"],
        "workflow_unit_scope": features["workflow_unit_scope"],
        "intermediate_data_transform_calls": features["intermediate_data_transform_calls"],
        "downstream_data_transform_calls": features["downstream_data_transform_calls"],
        "io_contract_status": "not_recovered_legacy_positional",
    }


def run(rows: list[dict[str, Any]], *, role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected = [row for row in rows if row.get("calibration_role") == role]
    if not selected:
        raise ValueError(f"no rows with calibration role {role!r}")
    output = [calibrate_row(row) for row in selected]
    recovered = [row for row in output if row["status"] == "adapter_structural_recovered"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "calibration_role": role,
        "input_rows": len(selected),
        "status_counts": dict(sorted(Counter(row["status"] for row in output).items())),
        "exact_literal_call_alignment_rows": len(recovered),
        "recovered_dependency_edge_rows": sum(bool(row.get("dependency_edges")) for row in recovered),
        "recovered_dependency_edge_count": sum(len(row.get("dependency_edges") or []) for row in recovered),
        "io_contract_status": "not_recovered_legacy_positional",
        "rule_promotion": "not_granted_pending_independent_calibration_review",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_runalg_adapter_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--role", choices=("calibration", "holdout"), default="calibration")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    output, summary = run(_read_jsonl(args.packet), role=args.role)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / f"runalg_{args.role}_adapter_ledger_v1.jsonl"
    summary_path = args.output_dir / f"runalg_{args.role}_adapter_summary_v1.json"
    _write(ledger, output)
    _write(summary_path, summary)
    _write(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {"packet": _sha256_file(args.packet)},
            "artifacts": {
                ledger.name: _sha256_file(ledger),
                summary_path.name: _sha256_file(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
