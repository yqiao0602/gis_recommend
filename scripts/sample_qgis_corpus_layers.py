#!/usr/bin/env python3
"""Create deterministic source previews for each QGIS corpus layer."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("source root must use NAME=PATH")
    name, raw_path = value.split("=", 1)
    path = Path(raw_path).resolve()
    if not name or not path.is_dir():
        raise ValueError(f"invalid source root: {value}")
    return name, path


def _assert_allowed(path: Path, roots: list[Path]) -> Path:
    resolved = path.resolve(strict=False)
    allowed = [root.resolve(strict=False) for root in roots]
    if not any(resolved == root or resolved.is_relative_to(root) for root in allowed):
        raise ValueError(f"output path is outside allowed roots: {resolved}")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layered-content", type=Path, required=True)
    parser.add_argument("--source-root", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    parser.add_argument("--samples-per-layer", type=int, default=3)
    parser.add_argument("--preview-chars", type=int, default=1600)
    parser.add_argument("--seed", type=int, default=20260721)
    args = parser.parse_args(argv)

    roots = dict(_parse_root(value) for value in args.source_root)
    by_layer = defaultdict(list)
    with args.layered_content.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                by_layer[str(record.get("primary_layer") or "unknown")].append(record)

    rng = random.Random(args.seed)
    samples = []
    for layer, records in sorted(by_layer.items()):
        selected = rng.sample(records, min(args.samples_per_layer, len(records)))
        for record in selected:
            canonical = dict(record.get("canonical_source") or {})
            root_id = str(canonical.get("source_root_id") or "")
            relative_path = str(canonical.get("relative_path") or "")
            root = roots.get(root_id)
            source_path = root / relative_path if root is not None else None
            preview = None
            read_error = None
            if source_path is None:
                read_error = "unknown_source_root"
            else:
                try:
                    preview = source_path.read_text(
                        encoding="utf-8-sig", errors="replace"
                    )[: args.preview_chars]
                except OSError as exc:
                    read_error = type(exc).__name__
            samples.append(
                {
                    "primary_layer": layer,
                    "content_sha256": record.get("content_sha256"),
                    "canonical_source": canonical,
                    "source_path": str(source_path) if source_path is not None else None,
                    "literal_operator_ids": record.get("literal_operator_ids") or [],
                    "reason_codes": record.get("reason_codes") or [],
                    "preview": preview,
                    "read_error": read_error,
                }
            )

    output = _assert_allowed(args.output, args.allowed_write_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "layers": len(by_layer),
                "samples": len(samples),
                "read_errors": sum(sample["read_error"] is not None for sample in samples),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
