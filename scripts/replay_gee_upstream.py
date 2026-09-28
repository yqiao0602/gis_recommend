#!/usr/bin/env python3
"""Replay the legacy raw-GEE extractor into an isolated, resumable steps tree."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from typing import Callable, Iterable


ProcessScript = Callable[[str, str], tuple[str, str, str]]
SCRIPT_ID_RE = re.compile(r"^script_(\d+)\.txt$")


def validate_output_dir(output_dir: Path, forbidden_roots: Iterable[Path]) -> Path:
    resolved = Path(output_dir).resolve()
    for root in forbidden_roots:
        forbidden = Path(root).resolve()
        if resolved == forbidden or forbidden in resolved.parents:
            raise ValueError(f"forbidden output root: {forbidden}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_paths(script: Path, output_dir: Path) -> dict[str, Path]:
    base = script.stem
    return {
        "ast": output_dir / f"{base}_ast.json",
        "edges": output_dir / f"{base}_edges.csv",
        "steps": output_dir / f"{base}_steps.csv",
        "data": output_dir / f"{base}_data.csv",
    }


def _remove_intermediates(paths: dict[str, Path], *, include_steps: bool) -> None:
    keys = ("ast", "edges", "data", "steps") if include_steps else ("ast", "edges", "data")
    for key in keys:
        path = paths[key]
        if path.is_file():
            path.unlink()


def run_batch(
    *,
    scripts: Iterable[Path],
    output_dir: Path,
    process_script: ProcessScript,
    manifest_path: Path,
    jobs: int,
    keep_intermediates: bool,
    forbidden_roots: Iterable[Path] = (),
) -> list[dict]:
    output_dir = validate_output_dir(output_dir, forbidden_roots)
    output_dir.mkdir(parents=True, exist_ok=True)
    ordered_scripts = sorted((Path(path).resolve() for path in scripts), key=lambda path: path.name)

    def process(path: Path) -> dict:
        artifacts = _artifact_paths(path, output_dir)
        base = {
            "script_name": path.name,
            "source_path": str(path),
            "source_sha256": _sha256(path),
            "steps_path": str(artifacts["steps"]),
        }
        if artifacts["steps"].is_file() and artifacts["steps"].stat().st_size > 0:
            return {**base, "status": "resumed", "error": None}
        try:
            process_script(str(path), str(output_dir))
            if not artifacts["steps"].is_file() or artifacts["steps"].stat().st_size == 0:
                raise RuntimeError("extractor returned without a non-empty steps CSV")
            if not keep_intermediates:
                _remove_intermediates(artifacts, include_steps=False)
            return {**base, "status": "processed", "error": None}
        except Exception as exc:  # preserve legacy per-script failure semantics
            _remove_intermediates(artifacts, include_steps=True)
            return {**base, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    if jobs == 1:
        records = [process(path) for path in ordered_scripts]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            records = list(executor.map(process, ordered_scripts))
    records.sort(key=lambda record: record["script_name"])

    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return records


def _load_extractor(path: Path) -> ProcessScript:
    path = path.resolve()
    spec = importlib.util.spec_from_file_location("legacy_gee_workflow", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load extractor: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    process_script = getattr(module, "process_script", None)
    if not callable(process_script):
        raise RuntimeError(f"extractor has no process_script(): {path}")
    return process_script


def _select_scripts(data_dir: Path, minimum: int | None, maximum: int | None) -> list[Path]:
    selected = []
    for path in data_dir.glob("script_*.txt"):
        match = SCRIPT_ID_RE.match(path.name)
        if not match:
            continue
        script_id = int(match.group(1))
        if minimum is not None and script_id < minimum:
            continue
        if maximum is not None and script_id > maximum:
            continue
        selected.append(path)
    return sorted(selected, key=lambda path: int(SCRIPT_ID_RE.match(path.name).group(1)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-manifest", type=Path, required=True)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--keep-intermediates", action="store_true")
    parser.add_argument("--forbidden-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    batches = json.loads(args.batch_manifest.read_text(encoding="utf-8"))
    if not isinstance(batches, list):
        raise ValueError("batch manifest must contain a JSON list")
    process_script = _load_extractor(args.extractor)
    os.chdir(args.extractor.resolve().parent)

    summaries = []
    for batch in batches:
        name = batch["name"]
        scripts = _select_scripts(
            Path(batch["data_dir"]),
            batch.get("min_script_id"),
            batch.get("max_script_id"),
        )
        records = run_batch(
            scripts=scripts,
            output_dir=args.output_root / name,
            process_script=process_script,
            manifest_path=args.manifest_dir / f"{name}.jsonl",
            jobs=args.jobs,
            keep_intermediates=args.keep_intermediates,
            forbidden_roots=args.forbidden_root,
        )
        counts = {status: sum(record["status"] == status for record in records)
                  for status in ("processed", "resumed", "failed")}
        summary = {"name": name, "input_scripts": len(scripts), **counts}
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)

    summary_path = args.manifest_dir / "summary.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if any(summary["failed"] for summary in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())

