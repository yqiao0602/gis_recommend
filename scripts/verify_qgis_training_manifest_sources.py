#!/usr/bin/env python3
"""Re-hash every unique source referenced by a QGIS training manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable


HashReader = Callable[[list[str]], dict[str, str]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest_sources(
    rows: list[dict[str, Any]], read_hashes: HashReader
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_by_path: dict[str, str] = {}
    sample_ids_by_path: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        path = str(row.get("source_path") or "")
        expected = str(row.get("source_sha256") or "")
        sample_id = str(row.get("sample_id") or "")
        if not path or len(expected) != 64 or not sample_id:
            raise ValueError(f"invalid source identity for {sample_id or '<missing>'}")
        previous = expected_by_path.setdefault(path, expected)
        if previous != expected:
            raise ValueError(f"conflicting source hashes for {path}")
        sample_ids_by_path[path].append(sample_id)

    actual_by_path = read_hashes(sorted(expected_by_path))
    ledger: list[dict[str, Any]] = []
    for path in sorted(expected_by_path):
        expected = expected_by_path[path]
        actual = str(actual_by_path.get(path) or "")
        if not actual:
            status = "source_missing_or_unreadable"
        elif actual != expected:
            status = "source_sha256_mismatch"
        else:
            status = "verified_sha256"
        ledger.append(
            {
                "schema": "gis_recommend.qgis_training_source_identity_replay.v1",
                "source_path": path,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "source_verification": status,
                "covered_sample_ids": sample_ids_by_path[path],
                "covered_manifest_rows": len(sample_ids_by_path[path]),
            }
        )

    counts = Counter(row["source_verification"] for row in ledger)
    verified_paths = {
        row["source_path"]
        for row in ledger
        if row["source_verification"] == "verified_sha256"
    }
    summary = {
        "schema": "gis_recommend.qgis_training_source_identity_replay.summary.v1",
        "manifest_rows": len(rows),
        "unique_sources": len(ledger),
        "verified_sources": counts["verified_sha256"],
        "covered_manifest_rows": sum(
            len(sample_ids_by_path[path]) for path in verified_paths
        ),
        "source_failures": len(ledger) - counts["verified_sha256"],
        "verification_status_counts": dict(sorted(counts.items())),
        "ast_and_call_span_evidence": "carried_forward_from_hash_bound_input_packages",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    return ledger, summary


def bind_verified_sources(
    rows: list[dict[str, Any]], ledger: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    status_by_path = {
        str(item.get("source_path") or ""): item.get("source_verification")
        for item in ledger
    }
    verified_rows: list[dict[str, Any]] = []
    for row in rows:
        path = str(row.get("source_path") or "")
        if status_by_path.get(path) != "verified_sha256":
            raise ValueError(f"source is not verified: {path}")
        verified = dict(row)
        if verified.get("source_verification"):
            verified["prior_source_verification"] = verified["source_verification"]
        verified["source_verification"] = "verified_sha256"
        if not verified.get("source_authority_key"):
            verified["source_authority_key"] = (
                f"source_sha256:{verified.get('source_sha256')}"
            )
            verified["source_authority_basis"] = "source_sha256"
        verified["source_identity_replay"] = (
            "gis_recommend.qgis_training_source_identity_replay.v1"
        )
        verified_rows.append(verified)
    return verified_rows


def _parse_remote_digest_lines(
    output: bytes, requested_paths: list[str]
) -> dict[str, str]:
    records = output.splitlines()
    if len(records) != len(requested_paths):
        raise ValueError("remote digest output count mismatch")
    return {
        path: record.decode("ascii")
        for path, record in zip(requested_paths, records)
    }


def _run_remote_sha256(paths: list[str], *, host: str) -> tuple[int, bytes, bytes]:
    remote_code = """import hashlib
import json
import sys

for path in json.load(sys.stdin):
    try:
        with open(path, "rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError:
        digest = ""
    print(digest)
"""
    command = "python3 -c " + shlex.quote(remote_code)
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, command],
        input=json.dumps(paths, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _remote_sha256(paths: list[str], *, host: str, batch_size: int = 40) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for offset in range(0, len(paths), batch_size):
        batch = paths[offset : offset + batch_size]
        returncode, stdout, stderr = _run_remote_sha256(batch, host=host)
        if returncode == 255:
            raise RuntimeError(
                f"SSH source verification failed: {stderr.decode('utf-8', errors='replace')}"
            )
        if returncode != 0:
            raise RuntimeError(
                "remote source verification failed: "
                + stderr.decode("utf-8", errors="replace")
            )
        hashes.update(_parse_remote_digest_lines(stdout, batch))
    return hashes


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


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    rows = _read_jsonl(args.manifest)
    ledger, summary = verify_manifest_sources(
        rows, lambda paths: _remote_sha256(paths, host=args.ssh_host)
    )
    summary["ssh_host"] = args.ssh_host
    verified_rows = bind_verified_sources(rows, ledger) if not summary["source_failures"] else []
    ledger_path = args.output_dir / "source_identity_replay_v1.jsonl"
    verified_path = args.output_dir / "source_verified_train_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(ledger_path, ledger)
    _write_jsonl(verified_path, verified_rows)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.manifest.name: {
                    "path": str(args.manifest),
                    "sha256": _sha256(args.manifest),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (ledger_path, verified_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["source_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
