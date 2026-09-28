#!/usr/bin/env python3
"""Replay parameter-dependent QGIS Processing families from full source."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from evaluate_qgis_stable118_structure_increment import (
    _fetch_ssh_source,
    materialize_sources,
)
from resolve_qgis_geometry_expression import resolve_source_expressions
from resolve_qgis_vclean_tool_enum import resolve_source as resolve_vclean_source


DEFAULT_REPLAY = (
    ROOT
    / "docs/reports/qgis_processing_stable118_replay_v1"
    / "l3_gated_manifest_v1.jsonl"
)
DEFAULT_ENUM = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "vclean_tool_enum_v1/provider_enum_manifest_v1.json"
)
TARGET_FAMILIES = {"grass7:v.clean", "native:geometrybyexpression"}


def select_target_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    identities = set()
    for source in rows:
        families = sorted(
            TARGET_FAMILIES.intersection(source.get("unmapped_operator_ids") or [])
        )
        if not families:
            continue
        key = (str(source.get("record_id") or ""), str(source.get("source_sha256") or ""))
        if not all(key) or key in identities:
            raise ValueError(f"blank or duplicate target identity: {key!r}")
        identities.add(key)
        row = dict(source)
        row["parameter_semantic_families"] = families
        selected.append(row)
    return sorted(selected, key=lambda row: str(row["record_id"]))


def resolve_target_rows(
    rows: list[dict[str, Any]], enum_manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    output = []
    for source in rows:
        row = dict(source)
        source_text = str(row.pop("source_text", ""))
        families = set(row["parameter_semantic_families"])
        resolved = True
        if "grass7:v.clean" in families:
            vclean = resolve_vclean_source(source_text, enum_manifest)
            row["vclean_resolution"] = vclean
            resolved = resolved and vclean["status"] == "resolved"
        if "native:geometrybyexpression" in families:
            geometry = resolve_source_expressions(source_text)
            row["geometry_expression_resolution"] = geometry
            resolved = resolved and bool(geometry) and all(
                item["status"] == "resolved_candidate" for item in geometry
            )
        row["row_resolution_status"] = "resolved" if resolved else "deferred"
        row["mapping_admission"] = "not_granted_parameter_semantics_only"
        row["training_admission"] = "not_granted"
        row["training_row_emitted"] = False
        output.append(row)
    return output


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--enum-manifest", type=Path, default=DEFAULT_ENUM)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--remote-prefix-alias", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    aliases = []
    for value in args.remote_prefix_alias:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid remote prefix alias: {value!r}")
        aliases.append((old, new))
    selected = select_target_rows(_read_jsonl(args.replay))
    enum_manifest = json.loads(args.enum_manifest.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="qgis_parameter_semantics_") as temp:
        materialized = materialize_sources(
            selected,
            Path(temp),
            lambda path: _fetch_ssh_source(args.ssh_host, path),
            path_aliases=aliases,
        )
        for row in materialized:
            row["source_text"] = Path(row["source_path"]).read_text(
                encoding="utf-8-sig", errors="replace"
            )
        ledger = resolve_target_rows(materialized, enum_manifest)
    for row in ledger:
        row["source_path"] = row.pop("source_path_original")

    vclean_tools = Counter()
    geometry_codes = Counter()
    for row in ledger:
        for call in (row.get("vclean_resolution") or {}).get("calls") or []:
            for tool in call.get("tools") or []:
                if tool.get("status") == "resolved":
                    vclean_tools[str(tool["tool_name"])] += 1
        for expression in row.get("geometry_expression_resolution") or []:
            if expression.get("status") == "resolved_candidate":
                geometry_codes[str(expression["candidate_l3_code"])] += 1
    summary = {
        "schema": "gis_recommend.qgis_parameter_semantic_family_replay.summary.v1",
        "input_replay_rows": len(_read_jsonl(args.replay)),
        "target_parent_rows": len(ledger),
        "target_family_parent_counts": dict(
            Counter(family for row in ledger for family in row["parameter_semantic_families"])
        ),
        "source_sha_verified_rows": len(ledger),
        "row_resolution_status_counts": dict(Counter(row["row_resolution_status"] for row in ledger)),
        "resolved_vclean_tool_counts": dict(vclean_tools),
        "resolved_geometry_l3_counts": dict(geometry_codes),
        "mapping_admission": "not_granted_parameter_semantics_only",
        "training_rows_emitted": 0,
        "llm_called": False,
    }
    ledger_path = args.output_dir / "resolution_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write(ledger_path, _jsonl(ledger))
    _write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    str(args.replay): _sha256(args.replay),
                    str(args.enum_manifest): _sha256(args.enum_manifest),
                },
                "artifacts": {
                    ledger_path.name: _sha256(ledger_path),
                    summary_path.name: _sha256(summary_path),
                },
                "remote_prefix_aliases": [
                    {"from": old, "to": new} for old, new in aliases
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
