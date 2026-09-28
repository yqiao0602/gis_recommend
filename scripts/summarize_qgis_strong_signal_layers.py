#!/usr/bin/env python3
"""Intersect QGIS corpus layers with the previously audited strong-signal pool."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _load_path_hashes(path: Path) -> dict[str, str]:
    result = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2 or len(parts[0]) != 64:
                raise ValueError(f"invalid hash manifest row {line_number}")
            result[parts[1].strip()] = parts[0]
    return result


def _load_nul_paths(path: Path) -> list[str]:
    return [
        value.decode("utf-8", errors="replace")
        for value in path.read_bytes().split(b"\0")
        if value
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layered-content", type=Path, required=True)
    parser.add_argument("--path-hash-manifest", type=Path, required=True)
    parser.add_argument("--strong-paths-nul", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    path_hashes = _load_path_hashes(args.path_hash_manifest)
    strong_paths = _load_nul_paths(args.strong_paths_nul)
    missing_paths = [path for path in strong_paths if path not in path_hashes]
    strong_hashes = {path_hashes[path] for path in strong_paths if path in path_hashes}

    layers = Counter()
    buckets = Counter()
    sources = Counter()
    source_layers: dict[str, Counter[str]] = defaultdict(Counter)
    matched_hashes = set()
    with args.layered_content.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            digest = str(record.get("content_sha256") or "")
            if digest not in strong_hashes:
                continue
            matched_hashes.add(digest)
            layer = str(record.get("primary_layer") or "unknown")
            layers[layer] += 1
            buckets[str(record.get("broad_bucket") or "unknown")] += 1
            canonical = dict(record.get("canonical_source") or {})
            source = str(canonical.get("source_root_id") or "unknown")
            sources[source] += 1
            source_layers[source][layer] += 1

    summary = {
        "schema_version": "qgis_strong_signal_layer_summary_v1",
        "strong_signal_path_count": len(strong_paths),
        "strong_signal_unique_hash_count": len(strong_hashes),
        "matched_layered_hash_count": len(matched_hashes),
        "missing_strong_paths_in_manifest": len(missing_paths),
        "missing_strong_hashes_in_layers": len(strong_hashes - matched_hashes),
        "primary_layer_counts": dict(sorted(layers.items())),
        "broad_bucket_counts": dict(sorted(buckets.items())),
        "canonical_source_counts": dict(sorted(sources.items())),
        "primary_layer_by_canonical_source": {
            source: dict(sorted(counts.items()))
            for source, counts in sorted(source_layers.items())
        },
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
