"""Run the confirmed GEE semantic-pattern census over strict candidates.

The input manifest is only used for source identity and candidate ordering.
Operators and dependencies are rebuilt from the source AST; task text is never
read. Missing source, hash mismatch, parse errors, extractor errors and
unresolved units are retained in a fail-closed sidecar.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gis_recommend.data.gee_dataflow_slicer import (  # noqa: E402
    build_backward_slices,
    build_local_subworkflow_units,
)
from gis_recommend.data.gee_source_extractor import extract_gee_source_evidence  # noqa: E402
from scripts.audit_gee_repeated_subworkflow_semantic_completeness import (  # noqa: E402
    review_semantic_rows,
)
from scripts.build_gee_p4_l3_canonicalization_gate import (  # noqa: E402
    load_gee_l3_mapping,
    load_gee_operator_catalog,
)
from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _filesystem_path,
    _json_text,
    _jsonl_text,
    _sha256,
)
from scripts.review_gee_repeated_subworkflow_structure import (  # noqa: E402
    _pattern_for,
    _semantic_context,
    _source_snippet,
)
from scripts.split_gee_repeated_subworkflows import _canonicalize_unit  # noqa: E402


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
)
DEFAULT_CANDIDATE_JSON = PACKAGE_DIR / "gee_strict_candidate_v1_train3106.json"
DEFAULT_SOURCE_ROOT = ROOT / ".tmp_gee_semantic_census_3106_sources"
DEFAULT_AST_DIR = ROOT / ".tmp_gee_semantic_census_3106_ast"
DEFAULT_PARSER = ROOT / "scripts/parse_gee_js_with_locations.js"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "semantic_pattern_census_3106_v1"
OUTPUT_PREFIX = "gee_semantic_pattern_census_3106_v1"
SOURCE_PREFIX = PurePosixPath("/home/yll/GEE/Data")


def load_candidate_rows(
    candidate_json: Path, *, expected_count: int = 3106
) -> list[dict[str, Any]]:
    with open(_filesystem_path(Path(candidate_json)), encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("labeled_workflows") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError(
            f"candidate manifest must contain exactly {expected_count} rows"
        )
    shas = [str(row.get("source_sha256") or "") for row in rows]
    paths = [str(row.get("source_path") or "") for row in rows]
    if any(not sha or len(sha) != 64 for sha in shas):
        raise ValueError("every candidate must have a 64-character source SHA")
    if len(set(shas)) != len(shas) or len(set(paths)) != len(paths):
        raise ValueError("strict candidate sources must be source/path unique")
    if any(not path.startswith(str(SOURCE_PREFIX) + "/") for path in paths):
        raise ValueError("candidate source path is outside /home/yll/GEE/Data")
    return rows


def source_path_for(row: dict[str, Any], source_root: Path) -> Path:
    source_path = PurePosixPath(str(row["source_path"]))
    relative = source_path.relative_to(SOURCE_PREFIX)
    return Path(source_root) / Path(*relative.parts)


def _ensure_ast(source_path: Path, ast_path: Path, parser: Path, node: str) -> None:
    if ast_path.is_file() and ast_path.stat().st_size > 0:
        return
    ast_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [node, str(parser), str(source_path), str(ast_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or not ast_path.is_file() or ast_path.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "AST parser failed").strip()
        raise RuntimeError(detail[:500])


def _candidate_rows_for_source(
    candidate: dict[str, Any],
    *,
    source_path: Path,
    ast_path: Path,
    mapping: dict[str, Any],
    catalog: frozenset[str],
) -> list[dict[str, Any]]:
    with open(_filesystem_path(ast_path), encoding="utf-8") as handle:
        ast = json.load(handle)
    source_text = Path(source_path).read_text(encoding="utf-8")
    evidence = extract_gee_source_evidence(
        ast,
        source_path=str(candidate["source_path"]),
        source_sha256=str(candidate["source_sha256"]),
    )
    evidence_dict = evidence.to_dict()
    all_calls = evidence_dict.get("ordered_calls", [])
    calls_by_ordinal = {
        int(call["ordinal"]): call
        for call in all_calls
        if isinstance(call, dict) and isinstance(call.get("ordinal"), int)
    }
    core_calls = [
        calls_by_ordinal[ordinal]
        for ordinal in evidence.core_operator_chain
        if ordinal in calls_by_ordinal
    ]
    local = build_local_subworkflow_units(ast, core_calls)
    dataflow = build_backward_slices(ast, core_calls)
    canonical_by_id = {
        unit.definition_id: _canonicalize_unit(
            unit,
            {int(call["ordinal"]): call for call in core_calls},
            mapping,
            catalog,
        )
        for unit in local.units
    }
    candidate_units: list[tuple[Any, str]] = []
    for unit in local.units:
        canonical = canonical_by_id[unit.definition_id]
        try:
            pattern = _pattern_for(canonical["canonical_operator_sequence"])
        except ValueError:
            continue
        candidate_units.append((unit, pattern))
    candidate_ids = {unit.definition_id for unit, _ in candidate_units}
    rows: list[dict[str, Any]] = []
    for unit, pattern in candidate_units:
        canonical = canonical_by_id[unit.definition_id]
        call_sites = []
        for index, ordinal in enumerate(unit.core_call_ordinals):
            call = calls_by_ordinal.get(ordinal)
            if call is None:
                continue
            call_sites.append(
                {
                    "ordinal": ordinal,
                    "source_location": call.get("source_location"),
                    "raw_callee": call.get("raw_callee"),
                    "canonical_operator": canonical["canonical_operator_sequence"][index],
                    "l3_code": canonical["l3_code_sequence"][index],
                }
            )
        rows.append(
            {
                "schema": "gis_recommend.gee_repeated_subworkflow_census_proposal.v1",
                "sample_id": candidate.get("sample_id"),
                "script_id": candidate.get("script_id"),
                "source_path": candidate.get("source_path"),
                "source_sha256": candidate.get("source_sha256"),
                "definition_id": unit.definition_id,
                "definition_kind": unit.kind,
                "start_line": unit.start_line,
                "end_line": unit.end_line,
                "dependency_ids": list(unit.dependency_ids),
                "selected_dependency_ids": [
                    value for value in unit.dependency_ids if value in candidate_ids
                ],
                "core_call_ordinals": list(unit.core_call_ordinals),
                **canonical,
                "unresolved_identifiers": list(unit.unresolved_identifiers),
                "pattern": pattern,
                **_semantic_context(unit.target, pattern),
                "source_snippet": _source_snippet(source_text, unit.start_line, unit.end_line),
                "call_site_evidence": call_sites,
                "local_quality_flags": list(local.quality_flags),
                **_dependency_closure_evidence(
                    dataflow.definitions,
                    calls_by_ordinal,
                    unit.definition_id,
                ),
                "source_backed": True,
                "training_admission": "not_granted_gee_semantic_pattern_census",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )
    return rows


def _dependency_closure_evidence(
    definitions: Any,
    calls_by_ordinal: dict[int, dict[str, Any]],
    definition_id: str,
) -> dict[str, list[Any]]:
    by_id = {definition.definition_id: definition for definition in definitions}
    if definition_id not in by_id:
        return {
            "transitive_dependency_ids": [],
            "transitive_unresolved_identifiers": [definition_id],
            "transitive_core_call_ordinals": [],
            "transitive_call_flags": [],
        }

    closure: set[str] = set()
    unresolved: set[str] = set()

    def visit(current_id: str) -> None:
        if current_id in closure:
            return
        definition = by_id.get(current_id)
        if definition is None:
            unresolved.add(current_id.split("@", 1)[0])
            return
        closure.add(current_id)
        unresolved.update(definition.unresolved_identifiers)
        for dependency_id in definition.dependency_ids:
            visit(dependency_id)

    visit(definition_id)
    ordered_ids = sorted(
        closure - {definition_id},
        key=lambda value: (
            by_id[value].start_line,
            by_id[value].statement_index,
            value,
        ),
    )
    ordinals: set[int] = set()
    flags: set[str] = set()
    for ordinal, call in calls_by_ordinal.items():
        location = call.get("source_location") or {}
        start_line = location.get("start_line")
        end_line = location.get("end_line")
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            continue
        if not any(
            by_id[value].start_line <= start_line
            and end_line <= by_id[value].end_line
            for value in closure
        ):
            continue
        ordinals.add(ordinal)
        flags.update(str(flag) for flag in call.get("flags") or [])
    return {
        "transitive_dependency_ids": ordered_ids,
        "transitive_unresolved_identifiers": sorted(unresolved),
        "transitive_core_call_ordinals": sorted(ordinals),
        "transitive_call_flags": sorted(flags),
    }


def source_authority_counts(
    candidates: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
) -> dict[str, int]:
    def count(rows: list[dict[str, Any]]) -> int:
        return len(
            {
                str(row.get("source_sha256"))
                for row in rows
                if str(row.get("source_sha256") or "")
            }
        )

    return {
        "verified_candidate_source_authorities": count(candidates),
        "proposal_source_authorities": count(proposals),
        "accepted_source_authorities": count(accepted),
    }


def run_census(
    *,
    candidate_json: Path,
    source_root: Path,
    ast_dir: Path,
    parser: Path,
    id_mappings_json: Path,
    node: str = "node",
    expected_candidate_count: int = 3106,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = load_candidate_rows(
        Path(candidate_json), expected_count=expected_candidate_count
    )
    mapping = load_gee_l3_mapping(Path(id_mappings_json))
    catalog = load_gee_operator_catalog(Path(id_mappings_json))
    proposals: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    source_hashes: set[str] = set()
    for index, candidate in enumerate(candidates, start=1):
        source_path = source_path_for(candidate, Path(source_root))
        expected_sha = str(candidate["source_sha256"])
        failure_base = {
            "sample_id": candidate.get("sample_id"),
            "script_id": candidate.get("script_id"),
            "source_path": candidate.get("source_path"),
            "source_sha256": expected_sha,
            "candidate_index": index,
            "training_rows_emitted": 0,
        }
        if not source_path.is_file():
            failures.append({**failure_base, "failure_reason": "source_missing"})
            continue
        actual_sha = _sha256(source_path)
        if actual_sha != expected_sha:
            failures.append(
                {**failure_base, "failure_reason": "source_hash_mismatch", "actual_sha256": actual_sha}
            )
            continue
        source_hashes.add(actual_sha)
        ast_path = Path(ast_dir) / f"{expected_sha}.ast.json"
        try:
            _ensure_ast(source_path, ast_path, Path(parser), node)
            rows = _candidate_rows_for_source(
                candidate,
                source_path=source_path,
                ast_path=ast_path,
                mapping=mapping,
                catalog=catalog,
            )
            proposals.extend(rows)
        except Exception as exc:
            failures.append(
                {
                    **failure_base,
                    "failure_reason": "ast_or_extractor_error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    reviewed, semantic_summary = review_semantic_rows(proposals)
    reason_counts = Counter(
        reason for row in reviewed for reason in row.get("semantic_reasons", [])
    )
    failure_counts = Counter(str(row["failure_reason"]) for row in failures)
    pattern_counts = Counter(str(row.get("pattern") or "") for row in reviewed)
    accepted_pattern_counts = Counter(
        str(row.get("pattern") or "")
        for row in reviewed
        if row.get("semantic_status") == "accepted_proposal"
    )
    accepted_rows = [
        row for row in reviewed if row.get("semantic_status") == "accepted_proposal"
    ]
    authority_counts = source_authority_counts(candidates, proposals, accepted_rows)
    summary = {
        "schema": f"gis_recommend.gee_semantic_pattern_census_{len(candidates)}_summary.v1",
        "inputs": {
            "candidate_json": str(candidate_json),
            "candidate_json_sha256": _sha256(Path(candidate_json)),
            "id_mappings_json": str(id_mappings_json),
            "id_mappings_json_sha256": _sha256(Path(id_mappings_json)),
            "source_root": str(source_root),
            "parser": str(parser),
        },
        "counts": {
            "candidate_rows": len(candidates),
            "source_hash_verified_candidates": len(source_hashes),
            "failure_rows": len(failures),
            "signature_proposals": len(proposals),
            "semantic_accepted_proposals": semantic_summary["counts"]["accepted_proposal"],
            "semantic_fail_closed": semantic_summary["counts"]["fail_closed"],
            "hash_verified_candidate_source_authorities": authority_counts[
                "verified_candidate_source_authorities"
            ],
            "proposal_source_authorities": authority_counts["proposal_source_authorities"],
            "accepted_source_authorities": authority_counts["accepted_source_authorities"],
            "matched_independent_authorities": authority_counts["proposal_source_authorities"],
            "training_rows_emitted": 0,
        },
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "accepted_pattern_counts": dict(sorted(accepted_pattern_counts.items())),
        "semantic_reason_counts": dict(sorted(reason_counts.items())),
        "failure_reason_counts": dict(sorted(failure_counts.items())),
        "decision": {
            "status": "census_only",
            "training_admission": "not_granted_gee_semantic_pattern_census",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "next_gate": "review support and fail-closed reasons before any batch export",
        },
    }
    return reviewed, failures, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Semantic Pattern Census 3106 v1",
            "",
            f"- Candidate rows: {counts['candidate_rows']}",
            f"- Source hash verified: {counts['source_hash_verified_candidates']}",
            f"- Failure rows: {counts['failure_rows']}",
            f"- Signature proposals: {counts['signature_proposals']}",
            f"- Semantic accepted proposals: {counts['semantic_accepted_proposals']}",
            f"- Semantic fail-closed: {counts['semantic_fail_closed']}",
            f"- Hash-verified candidate source authorities: {counts['hash_verified_candidate_source_authorities']}",
            f"- Proposal source authorities: {counts['proposal_source_authorities']}",
            f"- Accepted source authorities: {counts['accepted_source_authorities']}",
            f"- Pattern counts: {summary['pattern_counts']}",
            f"- Failure reasons: {summary['failure_reason_counts']}",
            "- Training rows emitted: 0",
            "- Training/validation/test/production admission: not granted",
            "",
        ]
    )


def write_outputs(
    rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "failures": output_dir / f"{output_prefix}_failures.jsonl",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hash_ledger.json",
    }
    _atomic_write(paths["jsonl"], _jsonl_text(rows))
    _atomic_write(paths["failures"], _jsonl_text(failures))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": summary["inputs"],
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json", type=Path, default=DEFAULT_CANDIDATE_JSON)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--ast-dir", type=Path, default=DEFAULT_AST_DIR)
    parser.add_argument("--parser", type=Path, default=DEFAULT_PARSER)
    parser.add_argument("--id-mappings-json", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--node", default="node")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-candidate-count", type=int, default=3106)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    rows, failures, summary = run_census(
        candidate_json=args.candidate_json,
        source_root=args.source_root,
        ast_dir=args.ast_dir,
        parser=args.parser,
        id_mappings_json=args.id_mappings_json,
        node=args.node,
        expected_candidate_count=args.expected_candidate_count,
    )
    return write_outputs(
        rows,
        failures,
        summary,
        args.output_dir,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
