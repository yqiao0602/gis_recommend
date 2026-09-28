#!/usr/bin/env python3
"""Select source-disjoint GEE pilot candidates and generate isolated ESTree ASTs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable


PILOT_FEATURES = (
    "dynamic_unresolved",
    "arrow_callback",
    "function_callback",
    "helper",
    "branch_loop",
    "io_presentation",
    "direct_chain",
)
DEFAULT_QUOTAS = {feature: 30 for feature in PILOT_FEATURES}


def classify_source_features(source: str) -> set[str]:
    features: set[str] = set()
    if re.search(r"\.map\s*\(\s*function\b", source):
        features.add("function_callback")
    if re.search(r"\.map\s*\([^\n;]{0,300}=>", source):
        features.add("arrow_callback")
    if re.search(r"(?:^|[;{}\n])\s*function\s+[A-Za-z_$][\w$]*\s*\(", source):
        features.add("helper")
    if re.search(r"\b(?:if|for|switch|while)\s*\(", source):
        features.add("branch_loop")
    if re.search(r"\b(?:Export\.|Map\.|ui\.|print\s*\()", source):
        features.add("io_presentation")
    if re.search(r"\[[^\]]+\]\s*\(", source):
        features.add("dynamic_unresolved")
    return features


def select_candidates(
    records: Iterable[dict[str, Any]],
    *,
    quotas: dict[str, int] | None = None,
    required_record_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    quotas = dict(DEFAULT_QUOTAS if quotas is None else quotas)
    unknown = set(quotas).difference(PILOT_FEATURES)
    if unknown:
        raise ValueError(f"unknown pilot features: {sorted(unknown)}")
    required_record_ids = set(required_record_ids or ())

    groups: dict[str, list[dict[str, Any]]] = {}
    seen_ids: set[str] = set()
    for record in records:
        record_id = record.get("record_id")
        source_hash = record.get("source_sha256")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be a non-empty string")
        if record_id in seen_ids:
            raise ValueError(f"duplicate record_id: {record_id}")
        seen_ids.add(record_id)
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            raise ValueError(f"invalid source_sha256 for {record_id}")
        groups.setdefault(source_hash, []).append(record)

    canonical: list[dict[str, Any]] = []
    for source_hash, members in sorted(groups.items()):
        ordered = sorted(
            members,
            key=lambda item: (item["record_id"] not in required_record_ids, item["record_id"]),
        )
        row = dict(ordered[0])
        row["source_sha256"] = source_hash
        row["source_features"] = sorted(classify_source_features(str(row.get("source_text", ""))))
        canonical.append(row)

    selected: list[dict[str, Any]] = []
    selected_hashes: set[str] = set()
    for record in sorted(canonical, key=lambda item: item["record_id"]):
        if record["record_id"] in required_record_ids:
            row = dict(record)
            row["pilot_feature"] = "required_regression"
            selected.append(row)
            selected_hashes.add(row["source_sha256"])

    for feature in PILOT_FEATURES:
        quota = quotas.get(feature, 0)
        available = []
        for record in canonical:
            if record["source_sha256"] in selected_hashes:
                continue
            record_features = set(record["source_features"])
            if feature == "direct_chain":
                matches = not record_features
            else:
                matches = feature in record_features
            if matches:
                available.append(record)
        available.sort(key=lambda item: (item["source_sha256"], item["record_id"]))
        for record in available[:quota]:
            row = dict(record)
            row["pilot_feature"] = feature
            selected.append(row)
            selected_hashes.add(row["source_sha256"])

    order = {name: index for index, name in enumerate(("required_regression", *PILOT_FEATURES))}
    selected.sort(key=lambda item: (order[item["pilot_feature"]], item["source_sha256"], item["record_id"]))
    return selected


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _jsonl(values: Iterable[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values).encode("utf-8")


def _load_replay_records(manifest_dir: Path) -> list[dict[str, Any]]:
    records = []
    for manifest_path in sorted(manifest_dir.glob("*.jsonl")):
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("status") not in {"processed", "resumed"}:
                continue
            source_path = Path(item["source_path"])
            if not source_path.is_file():
                raise ValueError(f"source_path does not exist: {source_path}")
            actual_hash = _sha256(source_path)
            if actual_hash != item.get("source_sha256"):
                raise ValueError(
                    f"source_sha256 mismatch for {source_path}: expected {item.get('source_sha256')}, got {actual_hash}"
                )
            records.append({
                "record_id": f"{manifest_path.stem}:{item['script_name']}",
                "source_path": str(source_path),
                "source_sha256": item["source_sha256"],
                "source_text": source_path.read_text(encoding="utf-8", errors="replace"),
                "steps_path": item.get("steps_path"),
            })
    return records


def _legacy_operations(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [row.get("name", "").strip() for row in csv.DictReader(handle) if row.get("name", "").strip()]


def build_pilot_manifest(
    *,
    manifest_dir: Path,
    output_dir: Path,
    parser_path: Path,
    node_executable: str,
    quotas: dict[str, int],
    required_script_names: set[str],
) -> dict[str, Any]:
    records = _load_replay_records(manifest_dir)
    required_ids = {
        record["record_id"] for record in records
        if Path(record["source_path"]).name in required_script_names
    }
    selected = select_candidates(records, quotas=quotas, required_record_ids=required_ids)
    ast_dir = output_dir / "ast"
    ast_dir.mkdir(parents=True, exist_ok=True)
    successful = []
    failures = []
    for record in selected:
        ast_path = ast_dir / f"{record['source_sha256']}.json"
        result = subprocess.run(
            [node_executable, str(parser_path), record["source_path"], str(ast_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not ast_path.is_file():
            failures.append({
                "record_id": record["record_id"],
                "source_sha256": record["source_sha256"],
                "returncode": result.returncode,
                "stderr": result.stderr[-2000:],
            })
            continue
        successful.append({
            "record_id": record["record_id"],
            "source_path": record["source_path"],
            "source_sha256": record["source_sha256"],
            "ast_path": str(ast_path),
            "legacy_operations": _legacy_operations(record.get("steps_path")),
            "pilot_feature": record["pilot_feature"],
            "source_features": record["source_features"],
        })

    summary = {
        "schema": "gis_recommend.gee_extractor_pilot_manifest.v1",
        "replay_record_count": len(records),
        "selected_source_count": len(selected),
        "ast_success_count": len(successful),
        "ast_failure_count": len(failures),
        "required_record_ids": sorted(required_ids),
        "training_admission": "not_granted",
    }
    payloads = {
        "input_manifest.jsonl": _jsonl(successful),
        "parse_failures.jsonl": _jsonl(failures),
        "selection.jsonl": _jsonl([{key: value for key, value in row.items() if key != "source_text"} for row in selected]),
        "summary.json": (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "artifacts": {
            name: {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(
        output_dir / "hash_ledger.json",
        (json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return summary


def _parse_quota(value: str) -> tuple[str, int]:
    try:
        name, count = value.split("=", 1)
        return name, int(count)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("quota must use FEATURE=COUNT") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--parser", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--quota", type=_parse_quota, action="append", default=[])
    parser.add_argument("--required-script-name", action="append", default=[])
    args = parser.parse_args(argv)
    quotas = dict(DEFAULT_QUOTAS)
    quotas.update(dict(args.quota))
    summary = build_pilot_manifest(
        manifest_dir=args.manifest_dir,
        output_dir=args.output_dir,
        parser_path=args.parser,
        node_executable=args.node,
        quotas=quotas,
        required_script_names=set(args.required_script_name),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
