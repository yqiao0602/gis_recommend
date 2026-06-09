#!/usr/bin/env python3
"""Audit downloaded GitHub QGIS workflow corpora before training integration.

This script does not train a model or mutate existing datasets. It builds a
QGIS processing algorithm catalog, aligns algorithm ids to the current L3
taxonomy through existing QGIS display-name mappings, and reports which scraped
workflow rows can become high-confidence QGIS->L3 training/evaluation samples.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import ID_MAPPINGS_PATH, OUTPUT_DIR

DEFAULT_QGIS_ROOT = ROOT / "爬取GithubQGIS"
DEFAULT_OUTPUT = OUTPUT_DIR / "diagnostics" / "qgis_corpus_audit"


INDEX_SPECS = [
    ("standard", "QGIS_standard_multi_operator_workflows_v2/github_qgis_standard_processing_index.csv", "standard_processing_algs"),
    ("workflow_a", "github_qgis_workflow_A类/github_qgis_workflow_index.csv", "unique_tools"),
    ("workflow", "github_qgis_workflow/github_qgis_workflow_index.csv", "unique_tools"),
    ("rs_workflow", "Github_QGIS_RS_Workflows_201509/github_qgis_rs_workflow_index.csv", "unique_tools"),
    ("platform_related", "Github_QGIS_RS_QGISPlatform_Related_201509/github_qgis_rs_qgis_platform_related_index.csv", "unique_tools"),
]

STANDARD_PROVIDERS = {"native", "qgis", "gdal", "3d", "saga", "grass", "grass7"}


def _read_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _norm_text(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _norm_alg_id(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.removeprefix("processing.")
    return text


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _split_tools(value: str) -> list[str]:
    tools = []
    for item in str(value or "").split(";"):
        item = _norm_alg_id(item)
        if not item:
            continue
        if ":" not in item:
            continue
        if item.startswith(("pyqgis.", "qgis.")):
            continue
        tools.append(item)
    return tools


def _load_qgis_catalog(path: Path) -> dict[str, dict]:
    """Load QGIS_Input.csv.

    The file is headerless in the current corpus. Positions observed:
    provider, tags, display_name, numeric_id, description, alg_id, ...
    """
    catalog: dict[str, dict] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue
            alg_id = _norm_alg_id(row[5])
            if ":" not in alg_id:
                continue
            display_name = row[2].strip()
            provider = row[0].strip()
            catalog[alg_id] = {
                "provider": provider,
                "display_name": display_name,
                "description": row[4].strip(),
                "normalized_name": _norm_text(display_name),
            }
    return catalog


def _load_qgis_display_l3(id_mappings_path: Path) -> dict[str, dict]:
    idm = _read_json(id_mappings_path)
    q2l3 = (idm.get("mapping_metadata") or {}).get("qgis_to_l3") or {}
    out: dict[str, dict] = {}
    for display, info in q2l3.items():
        if not isinstance(info, dict):
            continue
        primary = info.get("primary_l3", "")
        if not primary:
            continue
        out[_norm_text(display)] = {
            "display_name": display,
            "primary_l3": primary,
            "all_candidates": info.get("all_candidates", []),
        }
    return out


def _build_alg_l3_crosswalk(catalog: dict[str, dict], display_l3: dict[str, dict]) -> dict[str, dict]:
    crosswalk = {}
    for alg_id, info in catalog.items():
        match = display_l3.get(info["normalized_name"])
        if match:
            crosswalk[alg_id] = {
                "alg_id": alg_id,
                "display_name": info["display_name"],
                "provider": info["provider"],
                "primary_l3": match["primary_l3"],
                "match_type": "display_name_exact_normalized",
                "mapped_display_name": match["display_name"],
            }
    return crosswalk


def _iter_index_rows(qgis_root: Path) -> Iterable[tuple[str, Path, str, dict]]:
    for source, rel, tool_col in INDEX_SPECS:
        path = qgis_root / rel
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                yield source, path, tool_col, row


def _audit_workflows(qgis_root: Path, crosswalk: dict[str, dict]) -> tuple[dict, list[dict]]:
    source_stats = defaultdict(lambda: {
        "rows": 0,
        "rows_with_processing_tools": 0,
        "high_confidence_rows": 0,
        "tool_mentions": 0,
        "mapped_mentions": 0,
        "unique_tools": Counter(),
        "mapped_tools": Counter(),
        "workflow_levels": Counter(),
        "platform_families": Counter(),
    })
    high_conf: list[dict] = []
    seen_keys: set[tuple[str, ...]] = set()

    for source, path, tool_col, row in _iter_index_rows(qgis_root):
        stats = source_stats[source]
        stats["rows"] += 1
        stats["workflow_levels"][row.get("workflow_level", "")] += 1
        stats["platform_families"][row.get("platform_family", "")] += 1

        tools = _split_tools(row.get(tool_col, ""))
        if not tools:
            continue
        stats["rows_with_processing_tools"] += 1

        mapped_l3: list[str] = []
        mapped_tools: list[str] = []
        for tool in tools:
            stats["tool_mentions"] += 1
            stats["unique_tools"][tool] += 1
            match = crosswalk.get(tool)
            if match:
                stats["mapped_mentions"] += 1
                stats["mapped_tools"][tool] += 1
                mapped_tools.append(tool)
                mapped_l3.append(match["primary_l3"])

        coverage = len(mapped_l3) / max(len(tools), 1)
        standard_count = sum(1 for t in tools if t.split(":", 1)[0] in STANDARD_PROVIDERS)
        has_io_signal = _parse_bool(row.get("has_input_signal")) and _parse_bool(row.get("has_output_signal"))
        keep_main = row.get("keep_main_corpus", "True")
        keep_ok = _parse_bool(keep_main) if keep_main != "" else True
        length_ok = 2 <= len(tools) <= 15
        high_confidence = (
            keep_ok
            and has_io_signal
            and length_ok
            and standard_count > 0
            and coverage >= 0.80
        )

        if high_confidence:
            key = tuple(mapped_l3)
            if key not in seen_keys:
                seen_keys.add(key)
                stats["high_confidence_rows"] += 1
                high_conf.append({
                    "schema": "gis_recommend.qgis_workflow_l3.v1",
                    "source": source,
                    "script_id": row.get("script_id"),
                    "repo_full_name": row.get("repo_full_name"),
                    "repo_html_url": row.get("repo_html_url"),
                    "file_path": row.get("file_path"),
                    "workflow_level": row.get("workflow_level"),
                    "platform_family": row.get("platform_family"),
                    "tool_count": len(tools),
                    "mapped_count": len(mapped_l3),
                    "coverage": round(coverage, 4),
                    "qgis_alg_ids": tools,
                    "mapped_qgis_alg_ids": mapped_tools,
                    "l3_sequence_codes": mapped_l3,
                })

    summary = {}
    for source, stats in source_stats.items():
        tool_mentions = stats["tool_mentions"]
        rows_with = stats["rows_with_processing_tools"]
        summary[source] = {
            "rows": stats["rows"],
            "rows_with_processing_tools": rows_with,
            "high_confidence_unique_l3_sequences": stats["high_confidence_rows"],
            "tool_mentions": tool_mentions,
            "mapped_mentions": stats["mapped_mentions"],
            "mapped_mention_rate": round(stats["mapped_mentions"] / max(tool_mentions, 1), 4),
            "unique_tools": len(stats["unique_tools"]),
            "mapped_unique_tools": len(stats["mapped_tools"]),
            "workflow_levels": dict(stats["workflow_levels"].most_common()),
            "platform_families": dict(stats["platform_families"].most_common()),
            "top_unmapped_tools": [
                {"tool": tool, "count": count}
                for tool, count in (stats["unique_tools"] - stats["mapped_tools"]).most_common(25)
            ],
        }
    return summary, high_conf


def _write_outputs(output_dir: Path, catalog: dict, crosswalk: dict, workflow_summary: dict, high_conf: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "qgis_alg_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (output_dir / "qgis_alg_id_to_l3_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["alg_id", "display_name", "provider", "primary_l3", "match_type", "mapped_display_name"])
        for alg_id, row in sorted(crosswalk.items()):
            writer.writerow([
                alg_id,
                row["display_name"],
                row["provider"],
                row["primary_l3"],
                row["match_type"],
                row["mapped_display_name"],
            ])

    report = {
        "schema": "gis_recommend.qgis_corpus_audit.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "qgis_alg_catalog_size": len(catalog),
        "alg_id_to_l3_size": len(crosswalk),
        "alg_id_to_l3_rate": round(len(crosswalk) / max(len(catalog), 1), 4),
        "workflow_summary": workflow_summary,
        "high_confidence_unique_l3_sequences": len(high_conf),
    }
    (output_dir / "qgis_workflow_l3_coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (output_dir / "qgis_high_confidence_workflows.jsonl").open("w", encoding="utf-8") as f:
        for row in high_conf:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        "# QGIS Workflow Corpus Audit",
        "",
        f"- QGIS alg catalog: {len(catalog)}",
        f"- alg_id -> L3 mapped: {len(crosswalk)} ({len(crosswalk) / max(len(catalog), 1) * 100:.1f}%)",
        f"- high-confidence unique L3 workflows: {len(high_conf)}",
        "",
        "## Source Summary",
        "",
        "| Source | Rows | Rows with processing | Mapped mentions | Unique tools | Mapped unique | High-conf unique |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for source, stats in workflow_summary.items():
        lines.append(
            f"| {source} | {stats['rows']} | {stats['rows_with_processing_tools']} | "
            f"{stats['mapped_mentions']}/{stats['tool_mentions']} ({stats['mapped_mention_rate']*100:.1f}%) | "
            f"{stats['unique_tools']} | {stats['mapped_unique_tools']} | {stats['high_confidence_unique_l3_sequences']} |"
        )
    lines.extend(["", "## Top Unmapped Tools", ""])
    for source, stats in workflow_summary.items():
        lines.append(f"### {source}")
        for item in stats["top_unmapped_tools"][:15]:
            lines.append(f"- {item['tool']}: {item['count']}")
        lines.append("")
    (output_dir / "qgis_corpus_audit.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qgis-root", default=str(DEFAULT_QGIS_ROOT))
    parser.add_argument("--qgis-input", default=None)
    parser.add_argument("--id-mappings", default=str(ID_MAPPINGS_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    qgis_root = Path(args.qgis_root)
    qgis_input = Path(args.qgis_input) if args.qgis_input else qgis_root / "QGIS_Input.csv"
    catalog = _load_qgis_catalog(qgis_input)
    display_l3 = _load_qgis_display_l3(Path(args.id_mappings))
    crosswalk = _build_alg_l3_crosswalk(catalog, display_l3)
    workflow_summary, high_conf = _audit_workflows(qgis_root, crosswalk)
    _write_outputs(Path(args.output_dir), catalog, crosswalk, workflow_summary, high_conf)

    summary = {
        "qgis_alg_catalog_size": len(catalog),
        "alg_id_to_l3_size": len(crosswalk),
        "high_confidence_unique_l3_sequences": len(high_conf),
        "output_dir": str(args.output_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    main()
