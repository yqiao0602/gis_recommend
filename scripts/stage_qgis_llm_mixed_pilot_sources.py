#!/usr/bin/env python3
"""Stage a mixed Processing/API source sample from read-only QGIS storage."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import zlib
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_llm_mixed_pilot_staging.v1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select_rows(
    rows: list[dict[str, Any]],
    *,
    pool: str,
    count: int,
    excluded_shas: set[str],
    scan_limit: int,
) -> list[dict[str, Any]]:
    candidates = sorted(
        (row for row in rows if row.get("pool") == pool),
        key=lambda row: (str(row.get("source_sha256") or ""), str(row.get("record_id") or "")),
    )
    selected: list[dict[str, Any]] = []
    seen = set(excluded_shas)
    for row in candidates[:scan_limit]:
        source_sha = str(row.get("source_sha256") or row.get("content_sha256") or "")
        record_id = str(row.get("record_id") or "")
        if len(source_sha) != 64 or not record_id or source_sha in seen:
            continue
        selected.append({**row, "source_sha256": source_sha, "pilot_pool": pool})
        seen.add(source_sha)
        if len(selected) == count:
            return selected
    raise ValueError(f"unable to select {count} unique {pool} rows from scan_limit={scan_limit}")


def remote_program() -> str:
    return '''import ast, base64, hashlib, json, sys, zlib
config = json.loads(zlib.decompress(base64.b64decode(sys.stdin.buffer.readline())))
counts = dict(config["counts"])
emitted = {key: 0 for key in counts}
seen = set()
for line in sys.stdin:
    row = json.loads(line)
    pool = row["pilot_pool"]
    if emitted.get(pool, 0) >= counts.get(pool, 0):
        continue
    expected = row["source_sha256"]
    if expected in seen:
        continue
    try:
        raw = open(row["source_path"], "rb").read()
        source = raw.decode("utf-8")
        ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        continue
    if hashlib.sha256(raw).hexdigest() != expected:
        continue
    print(json.dumps({**row, "source_text": source, "source_sha256_verified": True,
                      "training_rows_emitted": False,
                      "training_admission": "not_granted_llm_operator_pilot"}, ensure_ascii=False))
    seen.add(expected)
    emitted[pool] += 1
    if all(emitted[key] >= counts[key] for key in counts):
        break
'''


def stage(
    processing_manifest: Path,
    api_manifest: Path,
    output_dir: Path,
    *,
    processing_count: int,
    api_count: int,
    scan_multiplier: int,
    ssh_host: str,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    if processing_count < 1 or api_count < 1 or scan_multiplier < 1:
        raise ValueError("counts and scan-multiplier must be positive")
    processing = load_jsonl(processing_manifest)
    api = load_jsonl(api_manifest)
    processing_candidates = select_rows(
        processing,
        pool="processing",
        count=processing_count * scan_multiplier,
        excluded_shas=set(),
        scan_limit=processing_count * scan_multiplier,
    )
    excluded = {str(row["source_sha256"]) for row in processing_candidates}
    api_candidates = select_rows(
        api,
        pool="api",
        count=api_count * scan_multiplier,
        excluded_shas=excluded,
        scan_limit=api_count * scan_multiplier,
    )
    request_rows = processing_candidates + api_candidates
    config = {"counts": {"processing": processing_count, "api": api_count}}
    encoded = base64.b64encode(remote_program().encode()).decode()
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""
    compressed = base64.b64encode(zlib.compress(json.dumps(config).encode())).decode()
    payload = compressed + "\n" + "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in request_rows)
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", ssh_host, command],
        input=payload.encode("utf-8"),
        capture_output=True,
        check=False,
        timeout=600,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    staged = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines() if line.strip()]
    if len(staged) != processing_count + api_count:
        counts = {pool: sum(row.get("pilot_pool") == pool for row in staged) for pool in ("processing", "api")}
        raise RuntimeError(f"server staged {counts}, expected processing={processing_count}, api={api_count}")
    if len({row["source_sha256"] for row in staged}) != len(staged):
        raise RuntimeError("staged source SHA values are not unique")
    output_dir.mkdir(parents=True)
    manifest_path = output_dir / "mixed_source_manifest_v1.jsonl"
    manifest_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in staged), encoding="utf-8")
    summary = {
        "schema": f"{SCHEMA}.summary",
        "processing_count": sum(row["pilot_pool"] == "processing" for row in staged),
        "api_count": sum(row["pilot_pool"] == "api" for row in staged),
        "source_count": len(staged),
        "unique_source_sha256_count": len({row["source_sha256"] for row in staged}),
        "source_sha_verified": all(row.get("source_sha256_verified") is True for row in staged),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_llm_operator_pilot",
        "yll_mount_mode": "read_only",
    }
    summary_path = output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hash_ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {processing_manifest.name: hashlib.sha256(processing_manifest.read_bytes()).hexdigest(), api_manifest.name: hashlib.sha256(api_manifest.read_bytes()).hexdigest()},
        "artifacts": {manifest_path.name: hashlib.sha256(manifest_path.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()},
    }
    (output_dir / "hash_ledger_v1.json").write_text(json.dumps(hash_ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processing-manifest", type=Path, required=True)
    parser.add_argument("--api-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--processing-count", type=int, default=50)
    parser.add_argument("--api-count", type=int, default=50)
    parser.add_argument("--scan-multiplier", type=int, default=3)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    args = parser.parse_args()
    print(json.dumps(stage(**vars(args)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
