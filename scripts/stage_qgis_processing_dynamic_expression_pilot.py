#!/usr/bin/env python3
"""Stage a source-disjoint Processing nonliteral-operator pilot from read-only QGIS storage."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import zlib
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_dynamic_expression_pilot_staging.v1"
EXPRESSION_KINDS = {"attribute", "call", "conditional_expression", "dict", "f_string", "string_expression", "subscript"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def select_rows(rows: list[dict[str, Any]], count: int, *, excluded_shas: set[str]) -> list[dict[str, Any]]:
    candidates = sorted(rows, key=lambda row: (str(row.get("source_sha256") or ""), str(row.get("record_id") or "")))
    selected: list[dict[str, Any]] = []
    seen = set(excluded_shas)
    for row in candidates:
        source_sha = str(row.get("source_sha256") or "")
        record_id = str(row.get("record_id") or "")
        if len(source_sha) != 64 or not record_id or source_sha in seen:
            continue
        selected.append(row)
        seen.add(source_sha)
        if len(selected) == count * 2:
            return selected
    raise ValueError(f"unable to select {count} + {count} unique source rows")


def remote_program() -> str:
    return r'''import ast, base64, hashlib, json, sys, zlib
config = json.loads(zlib.decompress(base64.b64decode(sys.stdin.buffer.readline())))
counts = dict(config["counts"])
emitted = {key: 0 for key in counts}
seen = set()
expression_kinds = {"Attribute", "Call", "IfExp", "Dict", "JoinedStr", "BinOp", "Subscript"}
def is_processing_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "processing"
            and node.func.attr.lower() in {"run", "runalg", "runandloadresults"})
for line in sys.stdin:
    row = json.loads(line)
    if row["source_sha256"] in seen:
        continue
    try:
        raw = open(row["source_path"], "rb").read()
        source = raw.decode("utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        continue
    if hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
        continue
    facts = []
    for node in ast.walk(tree):
        if not is_processing_call(node) or not node.args:
            continue
        first = node.args[0]
        if type(first).__name__ not in expression_kinds:
            continue
        facts.append({"call_line": int(node.lineno), "first_argument_kind": type(first).__name__})
    if not facts:
        continue
    cohort = "calibration" if emitted["calibration"] < counts["calibration"] else "holdout"
    if emitted[cohort] >= counts[cohort]:
        continue
    print(json.dumps({**row, "pilot_pool": "processing", "pilot_cohort": cohort, "source_text": source, "source_sha256_verified": True,
                      "dynamic_expression_facts": facts, "training_rows_emitted": False,
                      "training_admission": "not_granted_processing_dynamic_expression_pilot"}, ensure_ascii=False))
    seen.add(row["source_sha256"])
    emitted[cohort] += 1
    if all(emitted[key] >= counts[key] for key in counts):
        break
'''


def stage(manifest: Path, output_dir: Path, *, count: int, ssh_host: str) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    if count < 1:
        raise ValueError("count must be positive")
    rows = load_jsonl(manifest)
    selected = select_rows(rows, len(rows) // 2, excluded_shas=set())
    config = {"counts": {"calibration": count, "holdout": count}}
    encoded = base64.b64encode(remote_program().encode()).decode()
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""
    compressed = base64.b64encode(zlib.compress(json.dumps(config).encode())).decode()
    payload = compressed + "\n" + "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected)
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", ssh_host, command], input=payload.encode(), capture_output=True, check=False, timeout=600)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    staged = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines() if line.strip()]
    counts = {cohort: sum(row.get("pilot_cohort") == cohort for row in staged) for cohort in ("calibration", "holdout")}
    if counts != {"calibration": count, "holdout": count}:
        raise RuntimeError(f"server staged {counts}, expected {count} per cohort")
    if len({row["source_sha256"] for row in staged}) != len(staged):
        raise RuntimeError("staged source SHA values are not unique")
    output_dir.mkdir(parents=True)
    manifest_path = output_dir / "dynamic_expression_source_manifest_v1.jsonl"
    manifest_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in staged), encoding="utf-8")
    summary_path = output_dir / "summary_v1.json"
    summary = {"schema": f"{SCHEMA}.summary", "source_count": len(staged), "calibration_count": count, "holdout_count": count, "source_sha_verified": all(row.get("source_sha256_verified") is True for row in staged), "training_rows_emitted": 0, "training_admission": "not_granted_processing_dynamic_expression_pilot", "yll_mount_mode": "read_only"}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "hash_ledger_v1.json").write_text(json.dumps({"schema": "gis_recommend.hash_ledger.v1", "inputs": {manifest.name: hashlib.sha256(manifest.read_bytes()).hexdigest()}, "artifacts": {manifest_path.name: hashlib.sha256(manifest_path.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}, "training_rows_emitted": 0}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    args = parser.parse_args()
    print(json.dumps(stage(**vars(args)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
