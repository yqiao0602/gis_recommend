#!/usr/bin/env python3
"""Build normalized-body-disjoint QGIS API task-boundary calibration packets."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from gis_recommend.data.qgis_source_authority import source_authority


FAMILIES = (
    "crs_transform",
    "feature_geometry",
    "field_attribute_edit",
    "raster_io_pixel",
    "sink_output",
    "spatial_index_query",
    "vector_layer_io",
)
HUMAN_FIELDS = (
    "task_boundary_decision",
    "boundary_line_start",
    "boundary_line_end",
    "boundary_failure_labels",
    "reviewer_notes",
)
STATIC_RISK_STRATA = (
    "single_step_multi_pattern",
    "overlap_sink_vector_step",
    "sink_vector_only_signature",
    "generic_sink_only",
    "no_sink_family",
    "no_explicit_gis_sink",
    "wide_call_span_gt_100",
    "wide_adjacent_gap_gt_100",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_rank(seed: int, split: str, key: str) -> str:
    return hashlib.sha256(f"{seed}|{split}|{key}".encode("utf-8")).hexdigest()


def _step_metrics(row: dict[str, Any]) -> dict[str, Any]:
    steps = list(row.get("steps") or [])
    lines = sorted(int(step.get("line_start") or 0) for step in steps)
    overlap = [
        step
        for step in steps
        if {"sink_output", "vector_layer_io"}
        <= set(step.get("pattern_names") or [])
    ]
    multi_pattern = [
        step for step in steps if len(set(step.get("pattern_names") or [])) > 1
    ]
    sink_steps = [
        step for step in steps if "sink_output" in (step.get("pattern_names") or [])
    ]
    generic_sink = [
        step
        for step in sink_steps
        if ".write" in str(step.get("name") or "")
        or ".output" in str(step.get("name") or "")
    ]
    explicit_sink = [
        step
        for step in sink_steps
        if any(
            token in str(step.get("name") or "")
            for token in (
                "qgsfeaturesink.addfeature",
                "qgsfeaturesink.addfeatures",
                "qgsvectorfilewriter.writeasvector",
                "qgsrasterfilewriter.write",
            )
        )
    ]
    span = max(lines) - min(lines) if lines else 0
    max_gap = max((right - left for left, right in zip(lines, lines[1:])), default=0)
    patterns = set(row.get("pattern_names") or [])
    risks = []
    if len(steps) == 1 and multi_pattern:
        risks.append("single_step_multi_pattern")
    if overlap:
        risks.append("overlap_sink_vector_step")
    if patterns == {"sink_output", "vector_layer_io"}:
        risks.append("sink_vector_only_signature")
    if sink_steps and len(generic_sink) == len(sink_steps):
        risks.append("generic_sink_only")
    if "sink_output" not in patterns:
        risks.append("no_sink_family")
    if not explicit_sink:
        risks.append("no_explicit_gis_sink")
    if span > 100:
        risks.append("wide_call_span_gt_100")
    if max_gap > 100:
        risks.append("wide_adjacent_gap_gt_100")
    return {
        "multi_pattern_step_count": len(multi_pattern),
        "overlap_sink_vector_step_count": len(overlap),
        "generic_sink_step_count": len(generic_sink),
        "explicit_gis_sink_step_count": len(explicit_sink),
        "call_line_span": span,
        "max_adjacent_call_gap": max_gap,
        "risk_strata": sorted(risks),
    }


def enrich_source_authorities(
    rows: list[dict[str, Any]], *, expected_rows: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) != expected_rows:
        raise ValueError(f"manifest row count {len(rows)} != expected {expected_rows}")
    record_ids = [str(row.get("record_id") or "") for row in rows]
    source_shas = [str(row.get("source_sha256") or "") for row in rows]
    if not all(record_ids) or len(set(record_ids)) != len(record_ids):
        raise ValueError("record_id values must be non-empty and unique")
    if not all(source_shas) or len(set(source_shas)) != len(source_shas):
        raise ValueError("source_sha256 values must be non-empty and unique")

    enriched: list[dict[str, Any]] = []
    basis_counts: Counter[str] = Counter()
    for row in rows:
        path = Path(str(row.get("source_path") or ""))
        if not path.is_file():
            raise ValueError(f"source file missing: {path}")
        actual_sha = _sha256(path)
        declared_sha = str(row["source_sha256"])
        if actual_sha != declared_sha:
            raise ValueError(f"source SHA mismatch: {path}")
        authority = source_authority(path, source_sha256=declared_sha)
        if authority["source_authority_basis"] != "normalized_source_body_sha256":
            raise ValueError(f"normalized source authority unavailable: {path}")
        basis_counts[authority["source_authority_basis"]] += 1
        enriched.append(
            {
                **row,
                **authority,
                **_step_metrics(row),
                "schema": "gis_recommend.qgis_api_source_authority.v1",
                "source_verification": "verified_sha256",
                "candidate_l3_sequence": [],
                "description_fidelity": "not_started",
                "deduplication": "not_started",
                "training_admission": "not_granted_authority_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    summary = {
        "schema": "gis_recommend.qgis_api_source_authority_summary.v1",
        "source_rows": len(enriched),
        "verified_source_sha256": len(enriched),
        "unique_record_ids": len(set(record_ids)),
        "unique_source_sha256": len(set(source_shas)),
        "unique_normalized_source_bodies": len(
            {row["normalized_source_body_sha256"] for row in enriched}
        ),
        "source_authority_basis_counts": dict(sorted(basis_counts.items())),
        "status_counts": dict(sorted(Counter(row["status"] for row in enriched).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_authority_only",
    }
    return enriched, summary


def build_candidate_authorities(
    enriched_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = [row for row in enriched_rows if row.get("status") == "pattern_candidate"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[str(row["source_authority_key"])].append(row)

    authorities: list[dict[str, Any]] = []
    for authority_key, members in grouped.items():
        canonical = min(
            members,
            key=lambda row: (
                str(row.get("source_root_id") or ""),
                str(row.get("relative_path") or ""),
                str(row.get("source_sha256") or ""),
                str(row.get("record_id") or ""),
            ),
        )
        patterns = sorted(
            {pattern for member in members for pattern in member.get("pattern_names") or []}
        )
        risks = sorted(
            {risk for member in members for risk in member.get("risk_strata") or []}
        )
        authorities.append(
            {
                **canonical,
                "schema": "gis_recommend.qgis_api_candidate_authority.v1",
                "cluster_id": hashlib.sha256(authority_key.encode("utf-8")).hexdigest(),
                "cluster_member_count": len(members),
                "cluster_record_ids": sorted(str(member["record_id"]) for member in members),
                "pattern_names": patterns,
                "risk_strata": risks,
                "canonical_record_id": canonical["record_id"],
                "training_admission": "not_granted_task_boundary_pending",
                "training_row_emitted": False,
            }
        )
    authorities.sort(key=lambda row: str(row["source_authority_key"]))
    summary = {
        "schema": "gis_recommend.qgis_api_candidate_cluster_summary.v1",
        "candidate_rows": len(candidates),
        "candidate_authorities": len(authorities),
        "duplicate_candidate_rows": len(candidates) - len(authorities),
        "cluster_member_rows": sum(int(row["cluster_member_count"]) for row in authorities),
        "family_row_support": dict(
            sorted(Counter(p for row in candidates for p in row.get("pattern_names") or []).items())
        ),
        "family_authority_support": dict(
            sorted(Counter(p for row in authorities for p in row.get("pattern_names") or []).items())
        ),
        "training_rows_emitted": 0,
    }
    return authorities, summary


def _select(
    authorities: list[dict[str, Any]],
    *,
    required_families: tuple[str, ...],
    quota_per_family: int,
    risk_quota: int,
    source_root_quota: int,
    seed: int,
    split: str,
    excluded: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = set(excluded)
    family_counts: Counter[str] = Counter()

    while any(
        family_counts[family] < quota_per_family for family in required_families
    ):
        deficits = {
            family
            for family in required_families
            if family_counts[family] < quota_per_family
        }
        eligible = [
            row
            for row in authorities
            if row["source_authority_key"] not in used
            and deficits.intersection(row.get("pattern_names") or [])
        ]
        if not eligible:
            missing = {family: quota_per_family - family_counts[family] for family in deficits}
            raise ValueError(f"insufficient source-disjoint family support for {split}: {missing}")
        eligible.sort(
            key=lambda row: (
                -len(deficits.intersection(row.get("pattern_names") or [])),
                _stable_rank(seed, split, str(row["source_authority_key"])),
            )
        )
        chosen = eligible[0]
        selected.append(chosen)
        used.add(str(chosen["source_authority_key"]))
        family_counts.update(chosen.get("pattern_names") or [])

    coverage_targets = [
        ("risk", risk, risk_quota) for risk in STATIC_RISK_STRATA if risk_quota > 0
    ]
    coverage_targets.extend(
        ("root", root, source_root_quota)
        for root in sorted({str(row.get("source_root_id") or "") for row in authorities})
        if root and source_root_quota > 0
    )
    for kind, value, quota in coverage_targets:
        def matches(row: dict[str, Any]) -> bool:
            return (
                value in (row.get("risk_strata") or [])
                if kind == "risk"
                else str(row.get("source_root_id") or "") == value
            )

        have = sum(1 for row in selected if matches(row))
        available = [
            row
            for row in authorities
            if str(row["source_authority_key"]) not in used and matches(row)
        ]
        available.sort(
            key=lambda row: _stable_rank(seed, f"{split}:{kind}:{value}", str(row["source_authority_key"]))
        )
        for row in available[: max(0, min(quota - have, len(available)))]:
            selected.append(row)
            used.add(str(row["source_authority_key"]))

    packet = []
    for row in selected:
        review = {
            **row,
            "schema": "gis_recommend.qgis_api_task_boundary_review.v1",
            "review_split": split,
            "review_status": "pending_human_review",
            "candidate_l3_sequence": [],
            "description_fidelity": "not_started",
            "deduplication": "not_started",
            "training_admission": "not_granted_task_boundary_review_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        review.update({field: "" for field in HUMAN_FIELDS})
        packet.append(review)
    return sorted(packet, key=lambda row: str(row["source_authority_key"]))


def select_source_disjoint_packet(
    authorities: list[dict[str, Any]],
    *,
    quota_per_family: int = 35,
    risk_quota: int = 15,
    source_root_quota: int = 1,
    seed: int = 20260729,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    supported = {pattern for row in authorities for pattern in row.get("pattern_names") or []}
    required_families = tuple(family for family in FAMILIES if family in supported)
    if not required_families:
        raise ValueError("candidate authorities contain no recognized pattern families")
    calibration = _select(
        authorities,
        required_families=required_families,
        quota_per_family=quota_per_family,
        risk_quota=risk_quota,
        source_root_quota=source_root_quota,
        seed=seed,
        split="calibration",
        excluded=set(),
    )
    calibration_keys = {str(row["source_authority_key"]) for row in calibration}
    holdout = _select(
        authorities,
        required_families=required_families,
        quota_per_family=quota_per_family,
        risk_quota=risk_quota,
        source_root_quota=source_root_quota,
        seed=seed,
        split="holdout",
        excluded=calibration_keys,
    )
    holdout_keys = {str(row["source_authority_key"]) for row in holdout}
    overlap = calibration_keys & holdout_keys
    if overlap:
        raise ValueError("calibration and holdout authority overlap")
    summary = {
        "schema": "gis_recommend.qgis_api_task_boundary_packet_summary.v1",
        "candidate_authorities": len(authorities),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "quota_per_family": quota_per_family,
        "risk_quota": risk_quota,
        "source_root_quota": source_root_quota,
        "required_families": list(required_families),
        "calibration_family_counts": dict(
            sorted(Counter(p for row in calibration for p in row["pattern_names"]).items())
        ),
        "holdout_family_counts": dict(
            sorted(Counter(p for row in holdout for p in row["pattern_names"]).items())
        ),
        "calibration_risk_counts": dict(
            sorted(Counter(risk for row in calibration for risk in row["risk_strata"]).items())
        ),
        "holdout_risk_counts": dict(
            sorted(Counter(risk for row in holdout for risk in row["risk_strata"]).items())
        ),
        "calibration_source_root_counts": dict(
            sorted(Counter(str(row["source_root_id"]) for row in calibration).items())
        ),
        "holdout_source_root_counts": dict(
            sorted(Counter(str(row["source_root_id"]) for row in holdout).items())
        ),
        "authority_overlap": len(overlap),
        "seed": seed,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_task_boundary_review_only",
    }
    return calibration, holdout, summary


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, (ast.Call, ast.Subscript)):
        return _call_name(node.func if isinstance(node, ast.Call) else node.value)
    return ""


def _review_context(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row["source_path"]))
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    windows: list[tuple[int, int]] = []
    for step in row.get("steps") or []:
        start = max(1, int(step["line_start"]) - 3)
        end = min(len(lines), int(step.get("line_end") or step["line_start"]) + 3)
        if windows and start <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))
    source_windows = [
        {"line_start": start, "line_end": end, "text": "\n".join(lines[start - 1 : end])}
        for start, end in windows
    ]

    scopes = []
    try:
        tree = ast.parse(text)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        seen: set[tuple[str, int, int]] = set()
        step_lines = {int(step["line_start"]) for step in row.get("steps") or []}
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            if int(call.lineno) not in step_lines:
                continue
            current: ast.AST | None = call
            names = []
            scope_node: ast.AST = tree
            while current is not None:
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.append(current.name)
                    scope_node = current
                current = parents.get(current)
            key = (
                ".".join(reversed(names)) or "<module>",
                int(getattr(scope_node, "lineno", 1)),
                int(getattr(scope_node, "end_lineno", len(lines)) or len(lines)),
            )
            if key not in seen:
                seen.add(key)
                scopes.append(
                    {
                        "qualname": key[0],
                        "line_start": key[1],
                        "line_end": key[2],
                        "matched_call": _call_name(call.func),
                    }
                )
    except SyntaxError:
        scopes = []
    return {**row, "source_windows": source_windows, "matched_scope_summaries": scopes}


def _structural_audit(authorities: list[dict[str, Any]]) -> dict[str, Any]:
    risks = Counter(risk for row in authorities for risk in row.get("risk_strata") or [])
    return {
        "schema": "gis_recommend.qgis_api_old_boundary_structural_audit.v1",
        "old_rule_id": "two-or-more-file-level-patterns-with-sink-or-three-steps-v1",
        "candidate_authorities": len(authorities),
        "risk_authority_counts": dict(sorted(risks.items())),
        "rule_admission": "failed_structural_precheck",
        "precision_status": "not_estimable_until_source_disjoint_labels_complete",
        "failure_reasons": [
            "shared tokens can create two families from one call",
            "generic .write/.output tokens are not GIS sink evidence",
            "file-level aggregation does not establish one lexical task boundary",
        ],
        "next_gate": "label calibration, repair boundary extractor, replay full pool, evaluate frozen holdout",
        "training_rows_emitted": 0,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=39386)
    parser.add_argument("--expected-candidates", type=int, default=13554)
    parser.add_argument("--quota-per-family", type=int, default=35)
    parser.add_argument("--risk-quota", type=int, default=15)
    parser.add_argument("--source-root-quota", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260729)
    args = parser.parse_args()

    rows = _read_jsonl(args.manifest)
    enriched, authority_summary = enrich_source_authorities(
        rows, expected_rows=args.expected_rows
    )
    authorities, cluster_summary = build_candidate_authorities(enriched)
    if cluster_summary["candidate_rows"] != args.expected_candidates:
        raise ValueError(
            f"candidate row count {cluster_summary['candidate_rows']} != expected "
            f"{args.expected_candidates}"
        )
    calibration, holdout, packet_summary = select_source_disjoint_packet(
        authorities,
        quota_per_family=args.quota_per_family,
        risk_quota=args.risk_quota,
        source_root_quota=args.source_root_quota,
        seed=args.seed,
    )
    calibration = [_review_context(row) for row in calibration]
    holdout = [_review_context(row) for row in holdout]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "authority": args.output_dir / "api_normalized_source_authority_v1.jsonl",
        "clusters": args.output_dir / "candidate_authorities_v1.jsonl",
        "calibration": args.output_dir / "calibration_review_v1.jsonl",
        "calibration_csv": args.output_dir / "calibration_review_v1.csv",
        "holdout": args.output_dir / "frozen_holdout_v1.jsonl",
        "authority_summary": args.output_dir / "authority_summary_v1.json",
        "cluster_summary": args.output_dir / "cluster_summary_v1.json",
        "packet_summary": args.output_dir / "packet_summary_v1.json",
        "structural_audit": args.output_dir / "old_rule_structural_audit_v1.json",
    }
    _write_jsonl(paths["authority"], enriched)
    _write_jsonl(paths["clusters"], authorities)
    _write_jsonl(paths["calibration"], calibration)
    _write_csv(paths["calibration_csv"], calibration)
    _write_jsonl(paths["holdout"], holdout)
    _atomic_write(
        paths["authority_summary"],
        json.dumps(authority_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        paths["cluster_summary"],
        json.dumps(cluster_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        paths["packet_summary"],
        json.dumps(packet_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        paths["structural_audit"],
        json.dumps(_structural_audit(authorities), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )
    artifacts = {name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for name, path in paths.items()}
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "manifest": {
                "path": str(args.manifest),
                "sha256": _sha256(args.manifest),
                "bytes": args.manifest.stat().st_size,
            }
        },
        "artifacts": artifacts,
    }
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps({**authority_summary, **cluster_summary, **packet_summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
