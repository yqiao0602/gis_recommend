#!/usr/bin/env python3
"""Cluster strict GEE authority gaps without changing dataset admission."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _filesystem_path,
    _load_jsonl,
    _sha256,
)


DEFAULT_AUTHORITY_DIR = ROOT / (
    "docs/reports/gee_raster_core_v1_review_split_2026-07-24/"
    "gee_raster_core_batch_training_package_v1/strict_candidate_v1/"
    "source_audit_60_v1/authority_v2_2_0"
)
DEFAULT_REPLAY = DEFAULT_AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_AUTHORITY_DIR / "gap_clusters_v1"
OUTPUT_PREFIX = "strict_candidate_authority_gap_clusters_v1"


@dataclass(slots=True)
class AuthorityGapAnalysis:
    raw_method_clusters: list[dict[str, Any]]
    l3_operator_clusters: list[dict[str, Any]]
    summary: dict[str, Any]


def _gap_category(call: dict[str, Any], raw_operator: str) -> str:
    if str(call.get("receiver_type") or "").startswith("ee."):
        return "typed_receiver_operator_gap"
    resolution = str(call.get("resolution") or "")
    if resolution == "receiver_ee_binding":
        return "proven_ee_type_unresolved"
    if resolution == "receiver_untyped":
        return "untyped_receiver"
    if resolution == "ee_namespace" or raw_operator.startswith("ee."):
        return "ee_namespace_operator_gap"
    return "other_unresolved_operator"


def analyze_authority_gaps(*, replay_jsonl_path: Path) -> AuthorityGapAnalysis:
    rows = _load_jsonl(Path(replay_jsonl_path))
    raw_occurrences: list[dict[str, str]] = []
    l3_occurrences: list[dict[str, str]] = []

    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        if not sample_id:
            raise ValueError("every replay row must have a sample_id")
        calls_by_raw: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for call in row.get("core_call_evidence") or []:
            if isinstance(call, dict):
                calls_by_raw[str(call.get("raw_callee") or "").strip().lower()].append(call)
        call_offsets: Counter[str] = Counter()
        for raw_value in row.get("unmapped_raw_operators") or []:
            raw = str(raw_value).strip().lower()
            if not raw:
                continue
            candidates = calls_by_raw.get(raw, [])
            offset = call_offsets[raw]
            call = candidates[min(offset, len(candidates) - 1)] if candidates else {}
            call_offsets[raw] += 1
            raw_occurrences.append(
                {
                    "sample_id": sample_id,
                    "raw_operator": raw,
                    "method": raw.rsplit(".", 1)[-1],
                    "receiver_type": str(call.get("receiver_type") or "<unknown>"),
                    "resolution": str(call.get("resolution") or "<missing>"),
                    "category": _gap_category(call, raw),
                }
            )
        for operator_value in row.get("canonical_unmapped_l3_operators") or []:
            operator = str(operator_value).strip().lower()
            if operator:
                l3_occurrences.append({"sample_id": sample_id, "operator": operator})

    raw_groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for item in raw_occurrences:
        key = (
            item["category"],
            item["receiver_type"],
            item["method"],
            item["resolution"],
        )
        raw_groups[key].append(item)
    raw_clusters = []
    for (category, receiver_type, method, resolution), items in raw_groups.items():
        raw_clusters.append(
            {
                "category": category,
                "receiver_type": receiver_type,
                "method": method,
                "resolution": resolution,
                "occurrences": len(items),
                "unique_rows": len({item["sample_id"] for item in items}),
                "examples": sorted({item["raw_operator"] for item in items})[:5],
            }
        )
    raw_clusters.sort(
        key=lambda item: (-item["occurrences"], -item["unique_rows"], item["category"], item["method"])
    )

    l3_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in l3_occurrences:
        l3_groups[item["operator"]].append(item)
    l3_clusters = [
        {
            "operator": operator,
            "occurrences": len(items),
            "unique_rows": len({item["sample_id"] for item in items}),
        }
        for operator, items in l3_groups.items()
    ]
    l3_clusters.sort(key=lambda item: (-item["occurrences"], -item["unique_rows"], item["operator"]))

    category_counts = Counter(item["category"] for item in raw_occurrences)
    canonicalization_rows = {
        str(row["sample_id"])
        for row in rows
        if row.get("unmapped_raw_operators")
    }
    l3_rows = {
        str(row["sample_id"])
        for row in rows
        if row.get("canonical_unmapped_l3_operators")
    }
    summary = {
        "schema": "gis_recommend.gee_strict_authority_gap_clusters.v1",
        "inputs": {
            "replay_jsonl": str(Path(replay_jsonl_path)),
            "replay_jsonl_sha256": _sha256(Path(replay_jsonl_path)),
        },
        "counts": {
            "replay_rows": len(rows),
            "canonicalization_gap_rows": len(canonicalization_rows),
            "unmapped_raw_occurrences": len(raw_occurrences),
            "raw_method_clusters": len(raw_clusters),
            "l3_mapping_gap_rows": len(l3_rows),
            "canonical_unmapped_l3_occurrences": len(l3_occurrences),
            "l3_operator_clusters": len(l3_clusters),
            "training_rows_emitted": 0,
        },
        "canonicalization_category_counts": dict(sorted(category_counts.items())),
        "canonicalization_category_unique_rows": {
            category: len({item["sample_id"] for item in raw_occurrences if item["category"] == category})
            for category in sorted(category_counts)
        },
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "next_gate": "improve receiver return-type propagation before reviewing independent L3 mapping gaps",
        },
    }
    return AuthorityGapAnalysis(
        raw_method_clusters=raw_clusters,
        l3_operator_clusters=l3_clusters,
        summary=summary,
    )


def _render_report(result: AuthorityGapAnalysis) -> str:
    counts = result.summary["counts"]
    lines = [
        "# GEE Strict Authority Gap Clusters v1",
        "",
        f"- Canonicalization-gap rows: {counts['canonicalization_gap_rows']}",
        f"- Unmapped raw occurrences: {counts['unmapped_raw_occurrences']}",
        f"- L3-mapping-gap rows: {counts['l3_mapping_gap_rows']}",
        f"- Canonical L3-gap occurrences: {counts['canonical_unmapped_l3_occurrences']}",
        "- Training admission: not granted",
        "",
        "## Canonicalization Categories",
        "",
    ]
    for category, count in result.summary["canonicalization_category_counts"].items():
        rows = result.summary["canonicalization_category_unique_rows"][category]
        lines.append(f"- `{category}`: {count} occurrences / {rows} rows")
    lines.extend(["", "## Top Raw Method Clusters", ""])
    for item in result.raw_method_clusters[:30]:
        lines.append(
            f"- `{item['category']} | {item['receiver_type']} | {item['method']}`: "
            f"{item['occurrences']} occurrences / {item['unique_rows']} rows; "
            f"examples={', '.join(item['examples'])}"
        )
    lines.extend(["", "## L3 Mapping Gaps", ""])
    for item in result.l3_operator_clusters:
        lines.append(
            f"- `{item['operator']}`: {item['occurrences']} occurrences / {item['unique_rows']} rows"
        )
    return "\n".join(lines) + "\n"


def write_outputs(
    result: AuthorityGapAnalysis,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "json": output_dir / f"{output_prefix}.json",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hash_ledger.json",
    }
    payload = {
        "schema": "gis_recommend.gee_strict_authority_gap_cluster_artifact.v1",
        "raw_method_clusters": result.raw_method_clusters,
        "l3_operator_clusters": result.l3_operator_clusters,
    }
    _atomic_write(paths["json"], json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write(paths["summary"], json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write(paths["report"], _render_report(result))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "replay_jsonl": {
                "path": result.summary["inputs"]["replay_jsonl"],
                "sha256": result.summary["inputs"]["replay_jsonl_sha256"],
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": os.path.getsize(_filesystem_path(path)),
            }
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-jsonl", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    result = analyze_authority_gaps(replay_jsonl_path=args.replay_jsonl)
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
