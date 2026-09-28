#!/usr/bin/env python3
"""Census and freeze a source-disjoint QGIS ``processing.runalg`` packet.

This script is intentionally an intake-only tool.  It reads source files to
verify the manifest hash and inspect AST call shapes, but it does not alter the
extractor, map L3 labels, generate descriptions, or emit training rows.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_runalg_census.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: Any) -> None:
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


def _expression_kind(node: ast.AST | None) -> str:
    if node is None:
        return "missing"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "string_literal"
    if isinstance(node, ast.Name):
        return "name"
    if isinstance(node, ast.Call):
        return "call_expression"
    return type(node).__name__.lower()


def normalized_source_body_sha256(source: str) -> str:
    """Return a formatting/comment-insensitive full-source identity."""

    tree = ast.parse(source)
    normalized = ast.dump(tree, annotate_fields=True, include_attributes=False)
    return _sha256_bytes(normalized.encode())


def inspect_runalg_calls(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "processing"
            and node.func.attr == "runalg"
        ):
            continue
        first = node.args[0] if node.args else None
        operator_id = (
            first.value.strip().lower()
            if isinstance(first, ast.Constant)
            and isinstance(first.value, str)
            and first.value.strip()
            else ""
        )
        calls.append(
            {
                "line_start": int(node.lineno),
                "line_end": int(node.end_lineno or node.lineno),
                "algorithm_argument_kind": _expression_kind(first),
                "literal_operator_id": operator_id,
                "positional_argument_count": len(node.args),
                "keyword_argument_names": sorted(
                    keyword.arg if keyword.arg is not None else "**kwargs" for keyword in node.keywords
                ),
            }
        )
    return sorted(calls, key=lambda row: (row["line_start"], row["line_end"]))


def _rank(seed: int, role: str, body_sha: str) -> str:
    return _sha256_bytes(f"{seed}\x1f{role}\x1f{body_sha}".encode())


def _round_robin_select(rows: Iterable[dict[str, Any]], *, count: int, seed: int) -> list[dict[str, Any]]:
    by_root: dict[str, deque[dict[str, Any]]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["source_root_id"] or "unknown")].append(row)
    for root, group in sorted(grouped.items()):
        by_root[root] = deque(
            sorted(group, key=lambda row: _rank(seed, "runalg", row["normalized_source_body_sha256"]))
        )
    selected: list[dict[str, Any]] = []
    while by_root and len(selected) < count:
        for root in list(by_root):
            selected.append(by_root[root].popleft())
            if not by_root[root]:
                del by_root[root]
            if len(selected) == count:
                break
    return selected


def census(
    manifest_rows: list[dict[str, Any]], authority_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    authority_shas = {
        str(row.get("source_sha256") or "") for row in authority_rows if row.get("source_sha256")
    }
    ledger: list[dict[str, Any]] = []
    for manifest in manifest_rows:
        source_path = Path(str(manifest.get("source_path") or ""))
        expected_sha = str(manifest.get("source_sha256") or manifest.get("content_sha256") or "")
        result: dict[str, Any] = {
            "schema": SCHEMA,
            "source_path": str(source_path),
            "source_root_id": str(manifest.get("source_root_id") or ""),
            "relative_path": str(manifest.get("relative_path") or ""),
            "source_sha256": expected_sha,
            "training_admission": "not_granted_runalg_census_only",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        if not source_path.is_file():
            ledger.append({**result, "status": "source_missing", "reason": "source_file_missing"})
            continue
        if _sha256_file(source_path) != expected_sha:
            ledger.append({**result, "status": "source_hash_mismatch", "reason": "manifest_sha_mismatch"})
            continue
        try:
            source = source_path.read_text(encoding="utf-8-sig", errors="replace")
            calls = inspect_runalg_calls(source)
            body_sha = normalized_source_body_sha256(source)
        except SyntaxError as exc:
            ledger.append({**result, "status": "source_unparseable", "reason": str(exc)})
            continue
        if not calls:
            continue
        result.update(
            {
                "normalized_source_body_sha256": body_sha,
                "runalg_call_sites": calls,
                "runalg_call_count": len(calls),
                "literal_operator_ids": [call["literal_operator_id"] for call in calls if call["literal_operator_id"]],
                "algorithm_argument_kinds": sorted(
                    Counter(call["algorithm_argument_kind"] for call in calls).items()
                ),
            }
        )
        if expected_sha in authority_shas:
            ledger.append({**result, "status": "excluded_existing_authority_source"})
        elif any(call["literal_operator_id"] for call in calls):
            ledger.append({**result, "status": "eligible_literal_runalg"})
        else:
            ledger.append({**result, "status": "deferred_dynamic_or_blank_runalg"})

    # Body keys must come from the SHA-verified source, never from an external
    # approximation.  Only authorities represented by this manifest can yield
    # body-level exclusions; all other authority sources remain SHA-excluded.
    known_authority_bodies = {
        str(row["normalized_source_body_sha256"])
        for row in ledger
        if row["status"] == "excluded_existing_authority_source"
    }
    for row in ledger:
        if (
            row["status"] == "eligible_literal_runalg"
            and str(row["normalized_source_body_sha256"]) in known_authority_bodies
        ):
            row["status"] = "excluded_existing_authority_body"
    summary = {
        "schema": f"{SCHEMA}.summary",
        "manifest_rows": len(manifest_rows),
        "authority_source_sha256_count": len(authority_shas),
        "authority_body_count_resolved_from_manifest": len(known_authority_bodies),
        "authority_source_sha256_without_manifest_body": len(authority_shas) - len(known_authority_bodies),
        "status_counts": dict(sorted(Counter(row["status"] for row in ledger).items())),
        "runalg_source_rows": len(ledger),
        "runalg_call_count": sum(int(row.get("runalg_call_count") or 0) for row in ledger),
        "literal_runalg_call_count": sum(len(row.get("literal_operator_ids") or []) for row in ledger),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_runalg_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return ledger, summary


def freeze_packet(ledger: list[dict[str, Any]], *, target_count: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [row for row in ledger if row["status"] == "eligible_literal_runalg"]
    by_body: dict[str, dict[str, Any]] = {}
    for row in eligible:
        body_sha = str(row["normalized_source_body_sha256"])
        current = by_body.get(body_sha)
        if current is None or _rank(seed, "canonical", str(row["source_sha256"])) < _rank(
            seed, "canonical", str(current["source_sha256"])
        ):
            by_body[body_sha] = row
    canonical = list(by_body.values())
    if len(canonical) < target_count:
        raise ValueError(f"insufficient source-disjoint runalg bodies: {len(canonical)} < {target_count}")
    selected = _round_robin_select(canonical, count=target_count, seed=seed)
    midpoint = target_count // 2
    packet = []
    for index, row in enumerate(selected):
        packet.append(
            {
                **row,
                "schema": "gis_recommend.qgis_processing_runalg_calibration.v1",
                "calibration_role": "calibration" if index < midpoint else "holdout",
                "calibration_seed": seed,
                "adapter_implementation": "not_started",
                "rule_promotion": "not_granted_pending_calibration_holdout",
                "training_admission": "not_granted_calibration_only",
                "training_rows_emitted": 0,
            }
        )
    calibration = packet[:midpoint]
    holdout = packet[midpoint:]
    calibration_sha = {str(row["source_sha256"]) for row in calibration}
    holdout_sha = {str(row["source_sha256"]) for row in holdout}
    calibration_body = {str(row["normalized_source_body_sha256"]) for row in calibration}
    holdout_body = {str(row["normalized_source_body_sha256"]) for row in holdout}
    if calibration_sha & holdout_sha or calibration_body & holdout_body:
        raise AssertionError("calibration/holdout disjointness violated")
    summary = {
        "schema": "gis_recommend.qgis_processing_runalg_calibration.v1.summary",
        "eligible_literal_source_rows": len(eligible),
        "canonical_normalized_source_body_rows": len(canonical),
        "suppressed_internal_body_duplicates": len(eligible) - len(canonical),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha256_zero_overlap": True,
        "calibration_holdout_normalized_body_zero_overlap": True,
        "adapter_implementation": "not_started",
        "rule_promotion": "not_granted_pending_calibration_holdout",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_calibration_only",
        "seed": seed,
    }
    return packet, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--pool",
        default="",
        help="Restrict the census to this source-role pool when the manifest has a pool field.",
    )
    parser.add_argument(
        "--source-root-manifest",
        type=Path,
        help="Optional full manifest used only to restore source-root metadata by source SHA.",
    )
    parser.add_argument("--processing-authority", type=Path, required=True)
    parser.add_argument("--all-qgis-authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260816)
    args = parser.parse_args()
    if args.target_count <= 0 or args.target_count % 2:
        raise ValueError("target-count must be a positive even number")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    manifest = _read_jsonl(args.manifest)
    if args.pool:
        manifest = [row for row in manifest if str(row.get("pool") or "") == args.pool]
    if args.source_root_manifest:
        source_metadata = {
            str(row.get("content_sha256") or row.get("source_sha256") or ""): row
            for row in _read_jsonl(args.source_root_manifest)
        }
        for row in manifest:
            source_sha = str(row.get("source_sha256") or row.get("content_sha256") or "")
            metadata = source_metadata.get(source_sha) or {}
            for field in ("source_root_id", "relative_path"):
                if not row.get(field) and metadata.get(field):
                    row[field] = metadata[field]
    authority = _read_jsonl(args.processing_authority) + _read_jsonl(args.all_qgis_authority)
    ledger, census_summary = census(manifest, authority)
    packet, packet_summary = freeze_packet(ledger, target_count=args.target_count, seed=args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    census_path = args.output_dir / "runalg_census_ledger_v1.jsonl"
    census_summary_path = args.output_dir / "runalg_census_summary_v1.json"
    packet_path = args.output_dir / "runalg_calibration_holdout_v1.jsonl"
    packet_summary_path = args.output_dir / "runalg_calibration_holdout_summary_v1.json"
    _write_json(census_path, ledger)
    _write_json(census_summary_path, census_summary)
    _write_json(packet_path, packet)
    _write_json(packet_summary_path, packet_summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "manifest": _sha256_file(args.manifest),
                "processing_authority": _sha256_file(args.processing_authority),
                "all_qgis_authority": _sha256_file(args.all_qgis_authority),
            },
            "artifacts": {
                path.name: _sha256_file(path)
                for path in (census_path, census_summary_path, packet_path, packet_summary_path)
            },
        },
    )
    print(json.dumps({"census": census_summary, "packet": packet_summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
