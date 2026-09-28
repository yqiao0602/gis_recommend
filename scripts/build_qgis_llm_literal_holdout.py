#!/usr/bin/env python3
"""Stage a source-disjoint literal-QGIS holdout through read-only SSH.

The output is an isolated LLM-pilot input manifest, never a training artifact.
Each source body is fetched from its manifest path, SHA-verified, AST-parsed,
and required to contain at least one literal Processing ID in the frozen catalog.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import subprocess
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from recover_qgis_legacy_provider_ids import canonicalize_operator_id

SCHEMA = "gis_recommend.qgis_llm_literal_holdout.v1"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def _catalog_ids(path: Path) -> set[str]:
    return {
        str(row["operator_id"]).lower()
        for row in json.loads(path.read_text(encoding="utf-8"))["operators"]
    }


def _literal_catalog_ids(source: str, catalog: set[str]) -> set[str]:
    tree = ast.parse(source)
    values: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "processing"
            and node.func.attr.lower() in {"run", "runalg", "runandloadresults"}
        ):
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        canonical, _ = canonicalize_operator_id(node.args[0].value, catalog)
        if canonical:
            values.add(canonical)
    return values


def _remote_program() -> str:
    return '''import ast, base64, hashlib, json, sys, zlib
config = json.loads(zlib.decompress(base64.b64decode(sys.stdin.buffer.readline())))
catalog = set(config["catalog"])
excluded = set(config["excluded_shas"])

def processing_literal_ids(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "processing" and node.func.attr.lower() in {"run", "runalg", "runandloadresults"}):
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        value = node.args[0].value.lower()
        if value in catalog:
            found.add(value)
        elif value.startswith("qgis:") and "native:" + value.split(":", 1)[1] in catalog:
            found.add("native:" + value.split(":", 1)[1])
    return found

selected = 0
for line in sys.stdin:
    row = json.loads(line)
    expected = row.get("source_sha256", "")
    if expected in excluded:
        continue
    try:
        raw = open(row["source_path"], "rb").read()
    except OSError:
        continue
    if hashlib.sha256(raw).hexdigest() != expected:
        continue
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        continue
    ids = processing_literal_ids(source)
    if not ids:
        continue
    print(json.dumps({"record_id": row["record_id"], "source_path": row["source_path"], "source_sha256": expected, "source_text": source, "remote_literal_catalog_ids": sorted(ids)}, ensure_ascii=False))
    selected += 1
    if selected >= config["source_count"]:
        break
'''


def stage_holdout(
    manifest: Path,
    catalog_path: Path,
    excluded_sample_paths: list[Path],
    source_count: int,
    ssh_host: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    catalog = _catalog_ids(catalog_path)
    excluded_shas = {
        str(row["source_sha256"])
        for path in excluded_sample_paths
        for row in _load_jsonl(path)
    }
    encoded = base64.b64encode(_remote_program().encode()).decode()
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""
    remote_config = base64.b64encode(
        zlib.compress(
            json.dumps(
                {"catalog": sorted(catalog), "excluded_shas": sorted(excluded_shas), "source_count": source_count}
            ).encode()
        )
    ).decode()
    response = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", ssh_host, command],
        input=(remote_config + "\n" + manifest.read_text(encoding="utf-8")).encode("utf-8"),
        capture_output=True,
        check=False,
        timeout=300,
    )
    if response.returncode:
        raise RuntimeError(
            f"read-only SSH staging failed: {response.stderr.decode('utf-8', errors='replace').strip()}"
        )
    rows: list[dict[str, Any]] = []
    for raw in response.stdout.decode("utf-8").splitlines():
        row = json.loads(raw)
        source = str(row["source_text"])
        if hashlib.sha256(source.encode()).hexdigest() != row["source_sha256"]:
            raise ValueError(f"source hash mismatch after SSH staging: {row['record_id']}")
        literal_ids = _literal_catalog_ids(source, catalog)
        if not literal_ids:
            raise ValueError(f"remote candidate has no local literal catalog ID: {row['record_id']}")
        rows.append({**row, "local_literal_catalog_ids": sorted(literal_ids), "selection_reason": "source_disjoint_literal_catalog_holdout"})
    if len(rows) != source_count:
        raise ValueError(f"requested {source_count} holdout sources, staged {len(rows)}")
    summary = {
        "schema": f"{SCHEMA}.summary",
        "source_count": len(rows),
        "unique_source_sha256_count": len({row["source_sha256"] for row in rows}),
        "excluded_source_sha256_count": len(excluded_shas),
        "catalog_operator_count": len(catalog),
        "source_sha_verified": len(rows),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_llm_catalog_extraction_pilot",
        "yll_mount_mode": "read_only",
    }
    if summary["unique_source_sha256_count"] != len(rows):
        raise ValueError("holdout source SHA values are not unique")
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--exclude-samples", type=Path, action="append", default=[])
    parser.add_argument("--source-count", type=int, default=10)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.source_count < 1:
        raise ValueError("source-count must be positive")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("output directory is not empty")
    rows, summary = stage_holdout(args.manifest, args.catalog, args.exclude_samples, args.source_count, args.ssh_host)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "holdout_sources_v1.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
