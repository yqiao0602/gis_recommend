#!/usr/bin/env python3
"""Summarize unique QGIS source records into mutually exclusive workflow layers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


_TEST_PATH = re.compile(
    r"(^|[/\\])(tests?|testing)([/\\]|$)|(^|[/\\])test_[^/\\]+\.py$|_test\.py$",
    re.IGNORECASE,
)
_SOURCE_PATH_HEADER = re.compile(
    r"^\s*#\s*Source path:\s*(?P<path>.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
_STRONG_TEST_CODE = re.compile(
    r"pytest\.importorskip\(|^\s*pytestmark\s*=|@pytest\.fixture|"
    r"\b(?:unittest\.TestCase|QgisTestCase)\b|from\s+qgis\.testing\s+import",
    re.IGNORECASE | re.MULTILINE,
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_allowed(path: Path, roots: list[Path]) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    allowed = [root.expanduser().resolve(strict=False) for root in roots]
    if not any(resolved == root or resolved.is_relative_to(root) for root in allowed):
        raise ValueError(f"output path is outside allowed roots: {resolved}")
    return resolved


def _hidden_test_evidence(source_path: str, source_text: str | None) -> bool:
    if _TEST_PATH.search(source_path):
        return True
    if not source_text:
        return False
    header = _SOURCE_PATH_HEADER.search(source_text)
    if header and _TEST_PATH.search(header.group("path")):
        return True
    return bool(_STRONG_TEST_CODE.search(source_text))


def classify_layer(
    record: Mapping[str, Any],
    *,
    source_text: str | None = None,
) -> tuple[str, str, list[str]]:
    reasons = {str(value) for value in record.get("reason_codes") or []}
    tier = str(record.get("screening_tier") or "quarantine")
    parse_status = str(record.get("parse_status") or "unknown")
    literal_ids = list(record.get("literal_operator_ids") or [])
    dynamic_count = int(record.get("dynamic_processing_call_count") or 0)
    blank_count = int(record.get("blank_literal_processing_call_count") or 0)
    catalog_misses = list(record.get("catalog_miss_ids") or [])
    is_algorithm = bool(record.get("is_processing_algorithm"))

    flags = []
    if literal_ids:
        flags.append("literal_processing")
        flags.append("literal_multistep" if len(literal_ids) >= 2 else "literal_single_step")
    if dynamic_count:
        flags.append("dynamic_processing")
    if blank_count:
        flags.append("blank_processing_id")
    if catalog_misses:
        flags.append("catalog_miss")
    if is_algorithm:
        flags.append("processing_algorithm_subclass")
    if record.get("has_qgis_api_evidence"):
        flags.append("qgis_api_evidence")

    canonical = dict(record.get("canonical_source") or {})
    relative_path = str(canonical.get("relative_path") or "")
    hidden_test = _hidden_test_evidence(relative_path, source_text)
    if hidden_test and "hard_test_source" not in reasons:
        flags.append("hidden_test_source")

    if "hard_test_source" in reasons or hidden_test:
        return "excluded_test_source", "excluded_or_quarantine", flags
    if parse_status in {"read_error", "syntax_error", "empty"}:
        return f"quarantine_{parse_status}", "excluded_or_quarantine", flags
    if tier == "A":
        if len(literal_ids) >= 2:
            return (
                "explicit_processing_multistep_catalog_exact",
                "ready_for_chain_validation",
                flags,
            )
        return (
            "explicit_processing_single_catalog_exact",
            "single_step_reference",
            flags,
        )
    if tier == "B":
        if catalog_misses:
            return (
                "explicit_processing_catalog_miss",
                "processing_needs_resolution",
                flags,
            )
        if dynamic_count or blank_count:
            return (
                "dynamic_or_blank_processing_id",
                "processing_needs_resolution",
                flags,
            )
        if is_algorithm and literal_ids:
            return (
                "processing_algorithm_with_explicit_subchain",
                "processing_needs_resolution",
                flags,
            )
        if is_algorithm:
            return (
                "processing_algorithm_implementation_or_custom",
                "processing_needs_resolution",
                flags,
            )
        return "processing_review_other", "processing_needs_resolution", flags
    if tier == "C":
        return "low_level_pyqgis_api_candidate", "deferred_low_level_api", flags
    if "no_qgis_evidence" in reasons:
        return "no_operational_qgis_evidence", "excluded_or_quarantine", flags
    return "quarantine_other", "excluded_or_quarantine", flags


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            yield value


def _source_preview(record: Mapping[str, Any], roots: Mapping[str, Path]) -> str | None:
    canonical = dict(record.get("canonical_source") or {})
    root = roots.get(str(canonical.get("source_root_id") or ""))
    relative_path = str(canonical.get("relative_path") or "")
    if root is None or not relative_path:
        return None
    try:
        with (root / relative_path).open(
            "r", encoding="utf-8-sig", errors="replace"
        ) as handle:
            return handle.read(128 * 1024)
    except OSError:
        return None


def build_summary(
    records: Iterable[Mapping[str, Any]],
    *,
    source_roots: Mapping[str, Path] | None = None,
) -> tuple[list[dict], dict]:
    layered = []
    layers = Counter()
    buckets = Counter()
    flags = Counter()
    canonical_sources = Counter()
    source_presence = Counter()
    canonical_by_layer: dict[str, Counter[str]] = defaultdict(Counter)
    presence_by_layer: dict[str, Counter[str]] = defaultdict(Counter)
    operators = Counter()
    catalog_misses = Counter()

    for raw_record in records:
        record = dict(raw_record)
        source_text = _source_preview(record, source_roots or {})
        primary_layer, broad_bucket, secondary_flags = classify_layer(
            record, source_text=source_text
        )
        canonical = dict(record.get("canonical_source") or {})
        canonical_source = str(canonical.get("source_root_id") or "unknown")
        observed_sources = {
            str(item.get("source_root_id") or "unknown")
            for item in record.get("observed_sources") or []
        }
        layers[primary_layer] += 1
        buckets[broad_bucket] += 1
        canonical_sources[canonical_source] += 1
        canonical_by_layer[canonical_source][primary_layer] += 1
        for source in observed_sources:
            source_presence[source] += 1
            presence_by_layer[source][primary_layer] += 1
        flags.update(secondary_flags)
        operators.update(str(value) for value in record.get("literal_operator_ids") or [])
        catalog_misses.update(str(value) for value in record.get("catalog_miss_ids") or [])
        layered.append(
            {
                "content_sha256": record.get("content_sha256"),
                "canonical_source": canonical,
                "observed_sources": record.get("observed_sources") or [],
                "duplicate_count": record.get("duplicate_count"),
                "screening_tier": record.get("screening_tier"),
                "primary_layer": primary_layer,
                "broad_bucket": broad_bucket,
                "secondary_flags": secondary_flags,
                "literal_operator_ids": record.get("literal_operator_ids") or [],
                "dynamic_processing_call_count": record.get(
                    "dynamic_processing_call_count", 0
                ),
                "catalog_miss_ids": record.get("catalog_miss_ids") or [],
                "is_processing_algorithm": bool(record.get("is_processing_algorithm")),
                "parse_status": record.get("parse_status"),
                "reason_codes": record.get("reason_codes") or [],
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )

    summary = {
        "schema_version": "qgis_corpus_layer_summary_v1",
        "total_unique_records": len(layered),
        "primary_layer_counts": dict(sorted(layers.items())),
        "broad_bucket_counts": dict(sorted(buckets.items())),
        "secondary_flag_counts": dict(sorted(flags.items())),
        "canonical_source_counts": dict(sorted(canonical_sources.items())),
        "source_presence_counts": dict(sorted(source_presence.items())),
        "primary_layer_by_canonical_source": {
            source: dict(sorted(counts.items()))
            for source, counts in sorted(canonical_by_layer.items())
        },
        "primary_layer_by_source_presence": {
            source: dict(sorted(counts.items()))
            for source, counts in sorted(presence_by_layer.items())
        },
        "top_literal_operators": [
            {"operator_id": operator_id, "mentions": count}
            for operator_id, count in operators.most_common(100)
        ],
        "top_catalog_misses": [
            {"operator_id": operator_id, "mentions": count}
            for operator_id, count in catalog_misses.most_common(100)
        ],
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }
    return layered, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unique-content", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    parser.add_argument("--source-root", action="append", default=[])
    args = parser.parse_args(argv)

    output_dir = _assert_allowed(args.output_dir, args.allowed_write_root)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_roots = {}
    for value in args.source_root:
        if "=" not in value:
            raise ValueError("source root must use NAME=PATH")
        name, raw_path = value.split("=", 1)
        path = Path(raw_path).resolve()
        if not name or not path.is_dir():
            raise ValueError(f"invalid source root: {value}")
        source_roots[name] = path
    layered, summary = build_summary(
        _load_jsonl(args.unique_content), source_roots=source_roots
    )
    records_path = output_dir / "layered_unique_content.jsonl"
    summary_path = output_dir / "layer_summary.json"
    with records_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in layered:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    ledger = {
        "input": {
            "path": str(args.unique_content.resolve()),
            "sha256": _file_sha256(args.unique_content),
        },
        "outputs": {
            path.name: {"sha256": _file_sha256(path), "size": path.stat().st_size}
            for path in (records_path, summary_path)
        },
    }
    (output_dir / "hash_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
