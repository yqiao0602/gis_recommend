#!/usr/bin/env python3
"""Dump real deferred helper source snippets for v1.2 pattern design.

Runs the v1.1 pass over a reproducible sample of the corpus and emits, for the
three leading deferred reasons, up to N real helper snippets each.  This is a
pattern-design input (what the real helpers actually look like), not a census
and not an authority change.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

TARGET_REASONS = (
    "helper_requires_one_processing_assignment",
    "helper_body_not_linear_whitelisted",
    "helper_linear_statement_not_static_dict_assignment",
)


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snippet_lines(source_text: str, node: ast.AST, width: int = 22) -> str:
    lines = source_text.splitlines()
    start = max(0, int(node.lineno) - 1)
    end = min(len(lines), int(getattr(node, "end_lineno", node.lineno)))
    head = max(0, start - 2)
    return "\n".join(f"{i + 1:>5} | {line}" for i, line in enumerate(lines[head:end], head))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("/home/yll"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--sample-size", type=int, default=400)
    parser.add_argument("--per-reason", type=int, default=4)
    args = parser.parse_args(argv)

    helper_inline = _load_module(
        Path(__file__).resolve().parent / "src/gis_recommend/data/qgis_processing_helper_inline.py",
        "qgis_processing_helper_inline",
    )
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    catalog_ids = {row["operator_id"] for row in catalog["operators"]}
    manifest = [
        json.loads(line) for line in args.manifest.open(encoding="utf-8-sig") if line.strip()
    ]
    rng = random.Random(args.seed)
    sample = rng.sample(manifest, min(args.sample_size, len(manifest)))
    root = str(args.source_root).rstrip("/")

    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for row in sample:
        raw = str(row["source_path"])
        path = Path(raw) if raw.startswith(root) else args.source_root / raw.lstrip("/")
        if not path.is_file():
            continue
        source_text = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            continue
        result = helper_inline.expand_cross_function_helpers(
            source_text,
            record_id=str(row["record_id"]),
            source_sha256=str(row["source_sha256"]),
            catalog_operator_ids=catalog_ids,
        )
        for deferred in result["deferred"]:
            reason = str(deferred.get("reason") or "unknown")
            counts[reason] += 1
            if reason not in TARGET_REASONS or len(samples[reason]) >= args.per_reason:
                continue
            helper = deferred.get("helper")
            snippet = ""
            if isinstance(helper, ast.AST):
                snippet = _snippet_lines(source_text, helper)
            elif deferred.get("helper_span"):
                span = deferred["helper_span"]
                lines = source_text.splitlines()
                snippet = "\n".join(
                    f"{i + 1:>5} | {lines[i - 1]}"
                    for i in range(int(span["line_start"]), min(int(span["line_end"]), len(lines)) + 1)
                )
            samples[reason].append(
                {
                    "source_path": str(path),
                    "helper_name": deferred.get("helper_name"),
                    "snippet": snippet,
                }
            )
    payload = {
        "schema": "gis_recommend.qgis_helper_deferred_samples.v1",
        "pass_version": helper_inline.PASS_VERSION,
        "sampled_rows": len(sample),
        "deferred_counts": dict(counts),
        "samples": {reason: samples[reason] for reason in TARGET_REASONS},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sampled_rows": len(sample), "counts": dict(counts)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
