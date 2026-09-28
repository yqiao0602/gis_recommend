#!/usr/bin/env python3
"""Census source-backed uses of the frozen mappy ``matchAlgo`` contract."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scripts.recover_qgis_dynamic_operator_ids import (
    _frozen_match_algo_values,
    recover_row,
)

SCHEMA = "gis_recommend.qgis_mappy_match_algo_contract_census.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _is_direct_processing_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and bool(node.args)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "processing"
    )


def contract_calls(source_text: str) -> list[dict[str, Any]]:
    """Return only calls that satisfy every source-side contract predicate."""

    tree = ast.parse(source_text)
    matches: list[dict[str, Any]] = []
    for call in sorted(
        (node for node in ast.walk(tree) if _is_direct_processing_call(node)),
        key=lambda node: (node.lineno, node.col_offset),
    ):
        values = _frozen_match_algo_values(source_text, tree, call)
        if values:
            matches.append(
                {
                    "call_line": call.lineno,
                    "call_line_end": call.end_lineno or call.lineno,
                    "input_operator_id": next(iter(values)).lower(),
                }
            )
    return matches


def _remote_program() -> str:
    """A dependency-free equivalent of ``contract_calls`` for the read-only host."""

    return r'''import ast, hashlib, json, re, sys
header = re.compile(r"(?ims)^\s*#?\s*Plugin\s*:\s*mappy\s*$.*?^\s*#?\s*Version\s*:\s*v0\.3\.2\s*$")
counts = {"source_file_missing": 0, "source_sha256_mismatch": 0, "source_parse_failure": 0, "verified_sources": 0, "contract_sources": 0, "contract_calls": 0}
def direct(node):
    return (isinstance(node, ast.Call) and bool(node.args) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "processing")
def has_provenance(tree, call):
    imported = False
    for node in ast.walk(tree):
        if (isinstance(node, ast.ImportFrom) and node.level >= 1 and node.module == "mappy_utils"
                and any(alias.name == "matchAlgo" and alias.asname is None for alias in node.names)
                and node.lineno < call.lineno):
            imported = True
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "matchAlgo" for target in targets):
                return False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "matchAlgo": return False
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    arg.arg == "matchAlgo" for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)):
                return False
        if isinstance(node, ast.Import) and any((a.asname or a.name) == "matchAlgo" for a in node.names): return False
        if isinstance(node, ast.ImportFrom) and not (node.level >= 1 and node.module == "mappy_utils" and any(a.name == "matchAlgo" and a.asname is None for a in node.names)) and any((a.asname or a.name) == "matchAlgo" for a in node.names): return False
    return imported
for line in sys.stdin:
    row = json.loads(line)
    try:
        raw = open(row["source_path"], "rb").read()
    except OSError:
        counts["source_file_missing"] += 1
        continue
    if hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
        counts["source_sha256_mismatch"] += 1
        continue
    try:
        source = raw.decode("utf-8-sig", errors="replace")
        tree = ast.parse(source)
    except SyntaxError:
        counts["source_parse_failure"] += 1
        continue
    counts["verified_sources"] += 1
    if not header.search(source):
        continue
    calls = []
    for call in sorted((n for n in ast.walk(tree) if direct(n)), key=lambda n: (n.lineno, n.col_offset)):
        expr = call.args[0]
        if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "matchAlgo" and len(expr.args) == 1 and not expr.keywords and isinstance(expr.args[0], ast.Constant) and isinstance(expr.args[0].value, str) and expr.args[0].value.strip() and has_provenance(tree, call)):
            continue
        calls.append({"call_line": call.lineno, "call_line_end": call.end_lineno or call.lineno, "input_operator_id": expr.args[0].value.strip().lower()})
    if calls:
        counts["contract_sources"] += 1
        counts["contract_calls"] += len(calls)
        print(json.dumps({"record_id": row["record_id"], "source_sha256": row["source_sha256"], "source_path": row["source_path"], "relative_path": row.get("relative_path"), "contract_calls": calls}, ensure_ascii=False, sort_keys=True))
print(json.dumps({"_summary": counts}, sort_keys=True))
'''


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def census(manifest: Path, output_dir: Path, ssh_host: str) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    rows = _load_jsonl(manifest)
    encoded = base64.b64encode(_remote_program().encode()).decode()
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", ssh_host, command],
        input=("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)).encode(),
        capture_output=True,
        check=False,
        timeout=1800,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    contract_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] | None = None
    for line in result.stdout.decode("utf-8", errors="strict").splitlines():
        value = json.loads(line)
        if "_summary" in value:
            summary = value["_summary"]
        else:
            contract_rows.append(value)
    if summary is None:
        raise RuntimeError("remote census did not return a summary")
    if len({row["source_sha256"] for row in contract_rows}) != len(contract_rows):
        raise RuntimeError("contract census emitted duplicate source SHA256 values")
    if summary["contract_sources"] != len(contract_rows):
        raise RuntimeError("remote contract source count does not match emitted ledger")
    total_calls = sum(len(row["contract_calls"]) for row in contract_rows)
    if summary["contract_calls"] != total_calls:
        raise RuntimeError("remote contract call count does not match emitted ledger")
    result_summary = {
        "schema": f"{SCHEMA}.summary",
        "input_authority_sources": len(rows),
        **summary,
        "contract_input_operator_counts": dict(
            sorted(
                Counter(
                    call["input_operator_id"]
                    for row in contract_rows
                    for call in row["contract_calls"]
                ).items()
            )
        ),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_contract_census_only",
        "production_merge": "not_granted",
        "yll_mount_mode": "read_only",
    }
    ledger_path = output_dir / "mappy_match_algo_contract_sources_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    _atomic_write(
        ledger_path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in contract_rows),
    )
    _atomic_write(summary_path, json.dumps(result_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        report_path,
        "# QGIS mappy matchAlgo Contract Census v1\n\n"
        f"- Authority sources: {len(rows)}\n"
        f"- SHA-verified sources: {summary['verified_sources']}\n"
        f"- Contract sources: {summary['contract_sources']}\n"
        f"- Contract calls: {summary['contract_calls']}\n"
        "- Training rows emitted: 0\n",
    )
    _atomic_write(
        output_dir / "hash_ledger_v1.json",
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {manifest.name: _sha256(manifest)},
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (ledger_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return result_summary


def fetch_contract_sources(
    ledger_path: Path, output_dir: Path, ssh_host: str
) -> dict[str, Any]:
    """Fetch only the three already-verified contract sources for local replay."""

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    rows = _load_jsonl(ledger_path)
    program = r'''import hashlib, json, sys
for line in sys.stdin:
    row = json.loads(line)
    try:
        raw = open(row["source_path"], "rb").read()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != row["source_sha256"]:
            raise ValueError("sha256 mismatch")
        source = raw.decode("utf-8-sig", errors="replace")
        print(json.dumps({**row, "source_text": source, "source_bytes_base64": __import__("base64").b64encode(raw).decode(), "source_sha256_verified": True}, ensure_ascii=False))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(json.dumps({**row, "source_text": "", "source_sha256_verified": False, "fetch_error": str(exc)}, ensure_ascii=False))
'''
    encoded = base64.b64encode(program.encode()).decode()
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", ssh_host, command],
        input=("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)).encode(),
        capture_output=True,
        check=False,
        timeout=600,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    fetched = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines() if line.strip()]
    if len(fetched) != len(rows):
        raise RuntimeError("server returned an incomplete source staging response")
    if not all(row.get("source_sha256_verified") for row in fetched):
        raise RuntimeError("contract source staging failed SHA verification")
    staged_path = output_dir / "mappy_match_algo_contract_sources_with_text_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    _atomic_write(staged_path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in fetched))
    summary = {
        "schema": f"{SCHEMA}.staging_summary",
        "source_count": len(fetched),
        "source_sha256_verified": True,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_contract_replay_only",
        "production_merge": "not_granted",
    }
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        output_dir / "hash_ledger_v1.json",
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {ledger_path.name: _sha256(ledger_path)},
                "artifacts": {path.name: _sha256(path) for path in (staged_path, summary_path)},
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return summary


def _load_catalog_ids(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    operators = payload.get("operators") if isinstance(payload, dict) else None
    if not isinstance(operators, list):
        raise TypeError("catalog must contain an operators list")
    ids = {
        str(row.get("operator_id") or "").strip().lower()
        for row in operators
        if isinstance(row, dict) and ":" in str(row.get("operator_id") or "")
    }
    if not ids:
        raise ValueError("catalog contains no provider-qualified IDs")
    return ids


def replay_contract_sources(
    staged_path: Path,
    catalog_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Rerun local dynamic recovery on byte-preserving staged contract sources."""

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    staged = _load_jsonl(staged_path)
    catalog_ids = _load_catalog_ids(catalog_path)
    recovered: list[dict[str, Any]] = []
    for row in staged:
        raw = base64.b64decode(str(row.get("source_bytes_base64") or ""), validate=True)
        source_sha = str(row.get("source_sha256") or "")
        if hashlib.sha256(raw).hexdigest() != source_sha:
            raise ValueError(f"staged bytes do not match source SHA256: {row.get('record_id')}")
        with tempfile.TemporaryDirectory(prefix="qgis_mappy_contract_") as directory:
            source_path = Path(directory) / f"{source_sha}.py"
            source_path.write_bytes(raw)
            replay = recover_row(
                {
                    **row,
                    "content_sha256": source_sha,
                    "source_path": str(source_path),
                    "primary_layer": "dynamic_or_blank_processing_id",
                },
                catalog_ids,
            )
        replay["source_path"] = str(row["source_path"])
        replay["staged_source_sha256_verified"] = True
        recovered.append(replay)
    summary = {
        "schema": f"{SCHEMA}.replay_summary",
        "input_contract_sources": len(staged),
        "source_sha256_verified": all(
            row["resolution_status"] != "exclude_source_authority_failure"
            for row in recovered
        ),
        "resolution_status_counts": dict(
            sorted(Counter(row["resolution_status"] for row in recovered).items())
        ),
        "structure_action_counts": dict(
            sorted(Counter(row["structure_action"] for row in recovered).items())
        ),
        "canonical_candidate_count": sum(
            row["structure_action"] == "auto_accept_candidate" for row in recovered
        ),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_contract_replay_only",
        "production_merge": "not_granted",
    }
    ledger_path = output_dir / "mappy_match_algo_dynamic_recovery_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    _atomic_write(ledger_path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in recovered))
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        report_path,
        "# QGIS mappy matchAlgo Contract Replay v1\n\n"
        f"- Contract sources replayed: {len(staged)}\n"
        f"- Canonical candidates: {summary['canonical_candidate_count']}\n"
        "- Training rows emitted: 0\n",
    )
    _atomic_write(
        output_dir / "hash_ledger_v1.json",
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {
                    staged_path.name: _sha256(staged_path),
                    catalog_path.name: _sha256(catalog_path),
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (ledger_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--fetch-ledger", type=Path)
    parser.add_argument("--fetch-output-dir", type=Path)
    parser.add_argument("--replay-staged", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--replay-output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.replay_staged:
        if args.catalog is None or args.replay_output_dir is None:
            raise ValueError("--catalog and --replay-output-dir are required with --replay-staged")
        result = replay_contract_sources(
            args.replay_staged, args.catalog, args.replay_output_dir
        )
    elif args.fetch_ledger:
        if args.fetch_output_dir is None:
            raise ValueError("--fetch-output-dir is required with --fetch-ledger")
        result = fetch_contract_sources(args.fetch_ledger, args.fetch_output_dir, args.ssh_host)
    else:
        result = census(args.manifest, args.output_dir, args.ssh_host)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
