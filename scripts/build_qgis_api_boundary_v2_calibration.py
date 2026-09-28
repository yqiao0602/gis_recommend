#!/usr/bin/env python3
"""Freeze source-disjoint calibration and holdout packets for API boundary v2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

HUMAN_FIELDS = (
    "task_boundary_decision",
    "dependency_decision",
    "terminal_decision",
    "boundary_line_start",
    "boundary_line_end",
    "failure_labels",
    "reviewer_notes",
)


def _rank(seed: int, split: str, key: str) -> str:
    return hashlib.sha256(f"{seed}|{split}|{key}".encode()).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strata(row: dict[str, Any]) -> list[str]:
    count = len(row.get("steps") or [])
    bucket = "steps_2" if count == 2 else "steps_3" if count == 3 else "steps_4_6" if count <= 6 else "steps_7_plus"
    strata = [bucket]
    if row.get("lexical_scope") == "<module>":
        strata.append("module_scope")
    if int(row.get("terminal_evidence_count") or 0) > 1:
        strata.append("multiple_terminals")
    span = row.get("source_span") or [0, 0]
    if int(span[1]) - int(span[0]) > 100:
        strata.append("span_gt_100")
    patterns = set(row.get("pattern_names") or []) - {"sink_output"}
    if len(patterns) > 1:
        strata.append("multi_family")
    return sorted(strata)


def canonicalize_units(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(row.get("source_authority_key") or "")
        if not key:
            raise ValueError("candidate unit lacks source authority")
        grouped[key].append(row)
    canonical = []
    for key, members in grouped.items():
        selected = min(members, key=lambda row: str(row["candidate_id"]))
        canonical.append(
            {
                **selected,
                "schema": "gis_recommend.qgis_api_boundary_v2_authority.v1",
                "authority_unit_count": len(members),
                "authority_candidate_ids": sorted(str(row["candidate_id"]) for row in members),
                "review_strata": _strata(selected),
                "candidate_l3_sequence": [],
                "training_admission": "not_granted_boundary_calibration_only",
                "training_row_emitted": False,
            }
        )
    canonical.sort(key=lambda row: str(row["source_authority_key"]))
    summary = {
        "candidate_units": len(rows),
        "candidate_authorities": len(canonical),
        "duplicate_units_within_authority": len(rows) - len(canonical),
        "family_authority_support": dict(
            sorted(Counter(p for row in canonical for p in row["pattern_names"]).items())
        ),
        "stratum_authority_support": dict(
            sorted(Counter(s for row in canonical for s in row["review_strata"]).items())
        ),
        "training_rows_emitted": 0,
    }
    return canonical, summary


def _select_one(
    rows: list[dict[str, Any]],
    *,
    split: str,
    packet_size: int,
    quota_per_family: int,
    shape_quota: int,
    source_root_quota: int,
    seed: int,
    excluded: set[str],
    gated_families: tuple[str, ...],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = set(excluded)
    family_counts: Counter[str] = Counter()
    while any(family_counts[family] < quota_per_family for family in gated_families):
        deficits = {family for family in gated_families if family_counts[family] < quota_per_family}
        eligible = [
            row for row in rows
            if str(row["source_authority_key"]) not in used
            and deficits.intersection(row["pattern_names"])
        ]
        if not eligible:
            raise ValueError(f"insufficient family support for {split}: {sorted(deficits)}")
        eligible.sort(
            key=lambda row: (
                -len(deficits.intersection(row["pattern_names"])),
                _rank(seed, split, str(row["source_authority_key"])),
            )
        )
        chosen = eligible[0]
        selected.append(chosen)
        used.add(str(chosen["source_authority_key"]))
        family_counts.update(chosen["pattern_names"])

    shape_support = Counter(s for row in rows for s in row["review_strata"])
    for shape in sorted(shape for shape, support in shape_support.items() if support >= 2 * shape_quota):
        have = sum(shape in row["review_strata"] for row in selected)
        eligible = [
            row for row in rows
            if str(row["source_authority_key"]) not in used and shape in row["review_strata"]
        ]
        eligible.sort(key=lambda row: _rank(seed, f"{split}:{shape}", str(row["source_authority_key"])))
        for row in eligible[: max(0, shape_quota - have)]:
            selected.append(row)
            used.add(str(row["source_authority_key"]))

    root_support = Counter(str(row["source_root_id"]) for row in rows)
    for root in sorted(root for root, support in root_support.items() if support >= 2 * source_root_quota):
        have = sum(str(row["source_root_id"]) == root for row in selected)
        eligible = [
            row for row in rows
            if str(row["source_authority_key"]) not in used and str(row["source_root_id"]) == root
        ]
        eligible.sort(key=lambda row: _rank(seed, f"{split}:root:{root}", str(row["source_authority_key"])))
        for row in eligible[: max(0, source_root_quota - have)]:
            selected.append(row)
            used.add(str(row["source_authority_key"]))

    if len(selected) > packet_size:
        raise ValueError(f"coverage quotas exceed packet size for {split}: {len(selected)} > {packet_size}")
    remaining = [row for row in rows if str(row["source_authority_key"]) not in used]
    remaining.sort(key=lambda row: _rank(seed, f"{split}:fill", str(row["source_authority_key"])))
    selected.extend(remaining[: packet_size - len(selected)])
    if len(selected) != packet_size:
        raise ValueError(f"insufficient authorities for {split}: {len(selected)} < {packet_size}")
    packet = []
    for row in selected:
        review = {
            **row,
            "schema": "gis_recommend.qgis_api_boundary_v2_review.v1",
            "review_split": split,
            "review_status": "pending_human_review",
            "candidate_l3_sequence": [],
            "description_fidelity": "not_started",
            "deduplication": "not_started",
            "training_admission": "not_granted_boundary_review_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        review.update({field: "" for field in HUMAN_FIELDS})
        packet.append(review)
    return sorted(packet, key=lambda row: str(row["source_authority_key"]))


def select_packets(
    rows: list[dict[str, Any]],
    *,
    packet_size: int = 100,
    quota_per_family: int = 35,
    shape_quota: int = 10,
    source_root_quota: int = 2,
    seed: int = 20260729,
    excluded_authority_keys: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    preexcluded = set(excluded_authority_keys or set())
    support = Counter(p for row in rows for p in row["pattern_names"] if p != "sink_output")
    gated_families = tuple(sorted(family for family, count in support.items() if count >= 2 * quota_per_family))
    calibration = _select_one(
        rows,
        split="calibration",
        packet_size=packet_size,
        quota_per_family=quota_per_family,
        shape_quota=shape_quota,
        source_root_quota=source_root_quota,
        seed=seed,
        excluded=preexcluded,
        gated_families=gated_families,
    )
    calibration_keys = {str(row["source_authority_key"]) for row in calibration}
    holdout = _select_one(
        rows,
        split="holdout",
        packet_size=packet_size,
        quota_per_family=quota_per_family,
        shape_quota=shape_quota,
        source_root_quota=source_root_quota,
        seed=seed,
        excluded=preexcluded | calibration_keys,
        gated_families=gated_families,
    )
    holdout_keys = {str(row["source_authority_key"]) for row in holdout}
    overlap = calibration_keys & holdout_keys
    if overlap:
        raise ValueError("calibration and holdout share source authority")
    summary = {
        "schema": "gis_recommend.qgis_api_boundary_v2_packet_summary.v1",
        "candidate_authorities": len(rows),
        "preexcluded_authorities": len(preexcluded),
        "preexcluded_candidate_authorities": sum(
            str(row["source_authority_key"]) in preexcluded for row in rows
        ),
        "packet_size": packet_size,
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "gated_families": list(gated_families),
        "noncalibratable_family_support": dict(sorted((family, count) for family, count in support.items() if family not in gated_families)),
        "calibration_family_counts": dict(sorted(Counter(p for row in calibration for p in row["pattern_names"]).items())),
        "holdout_family_counts": dict(sorted(Counter(p for row in holdout for p in row["pattern_names"]).items())),
        "calibration_stratum_counts": dict(sorted(Counter(s for row in calibration for s in row["review_strata"]).items())),
        "holdout_stratum_counts": dict(sorted(Counter(s for row in holdout for s in row["review_strata"]).items())),
        "authority_overlap": len(overlap),
        "seed": seed,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_boundary_review_only",
    }
    return calibration, holdout, summary


def _context(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row["source_path"]))
    source_lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    windows = []
    for step in row["steps"]:
        start = max(1, int(step["line_start"]) - 3)
        end = min(len(source_lines), int(step["line_end"]) + 3)
        if windows and start <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))
    span = row["source_span"]
    full_boundary = ""
    if int(span[1]) - int(span[0]) <= 240:
        full_boundary = "\n".join(source_lines[int(span[0]) - 1 : int(span[1])])
    return {
        **row,
        "source_windows": [
            {"line_start": start, "line_end": end, "text": "\n".join(source_lines[start - 1 : end])}
            for start, end in windows
        ],
        "boundary_source": full_boundary,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--packet-size", type=int, default=100)
    parser.add_argument("--quota-per-family", type=int, default=35)
    parser.add_argument("--shape-quota", type=int, default=10)
    parser.add_argument("--source-root-quota", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--exclude-reviews", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--exclude-source-sha",
        type=Path,
        nargs="*",
        default=[],
        help="JSONL review packets whose source_sha256 values must be excluded",
    )
    args = parser.parse_args()
    units = _read_jsonl(args.candidate_units)
    exclusion_rows = [
        row for path in args.exclude_reviews for row in _read_jsonl(path)
    ]
    excluded_source_shas = {
        str(row.get("source_sha256") or "")
        for path in args.exclude_source_sha
        for row in _read_jsonl(path)
    }
    if "" in excluded_source_shas:
        raise ValueError("excluded source-SHA packet contains a row without source_sha256")
    excluded_authority_keys = {
        str(row.get("source_authority_key") or "") for row in exclusion_rows
    }
    if "" in excluded_authority_keys:
        raise ValueError("excluded review row lacks source_authority_key")
    canonical, canonical_summary = canonicalize_units(units)
    excluded_authority_keys.update(
        str(row["source_authority_key"])
        for row in canonical
        if str(row.get("source_sha256") or "") in excluded_source_shas
    )
    calibration, holdout, packet_summary = select_packets(
        canonical,
        packet_size=args.packet_size,
        quota_per_family=args.quota_per_family,
        shape_quota=args.shape_quota,
        source_root_quota=args.source_root_quota,
        seed=args.seed,
        excluded_authority_keys=excluded_authority_keys,
    )
    calibration = [_context(row) for row in calibration]
    holdout = [_context(row) for row in holdout]
    selected_source_shas = {
        str(row.get("source_sha256") or "") for row in calibration + holdout
    }
    if selected_source_shas & excluded_source_shas:
        raise ValueError("new calibration/holdout overlaps excluded source SHA")
    packet_summary["excluded_source_sha_count"] = len(excluded_source_shas)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = args.output_dir / "candidate_authorities_v1.jsonl"
    calibration_path = args.output_dir / f"calibration_review_{args.packet_size}_v1.jsonl"
    csv_path = args.output_dir / f"calibration_review_{args.packet_size}_v1.csv"
    holdout_path = args.output_dir / f"frozen_holdout_{args.packet_size}_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(canonical_path, canonical)
    _write_jsonl(calibration_path, calibration)
    _write_jsonl(holdout_path, holdout)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", dir=args.output_dir, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(calibration[0]))
        writer.writeheader()
        for row in calibration:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})
        temporary = Path(handle.name)
    temporary.replace(csv_path)
    summary = {**canonical_summary, **packet_summary}
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    input_paths = [args.candidate_units, *args.exclude_reviews, *args.exclude_source_sha]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            str(path): {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in input_paths
        },
        "artifacts": {path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for path in (canonical_path, calibration_path, csv_path, holdout_path, summary_path)},
    }
    _atomic_write(args.output_dir / "hash_ledger_v1.json", json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
