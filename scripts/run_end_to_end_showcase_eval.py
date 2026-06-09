#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run an end-to-end showcase evaluation for the current L3 -> QGIS pipeline.

This script is intentionally demonstration-oriented: it runs curated or
user-provided natural-language GIS tasks through the latest L3 checkpoint, picks
the best rule-usable beam candidate, lands it to a QGIS operator chain, and
writes human-readable artifacts. It does not train or mutate checkpoints.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import (  # noqa: E402
    CLASSIFICATION_HIERARCHY,
    ID_MAPPINGS_PATH,
    OUTPUT_DIR,
    V4_QG_LABELED_WORKFLOWS_PATH,
    V4_QG_SPLITS_PATH,
)
from gis_recommend.inference.infer_l3_candidates_v4 import (  # noqa: E402
    L3SequenceInferencerV4,
)
from gis_recommend.planning.qgis_chain_planner import (  # noqa: E402
    build_qgis_chain_planner,
)

from scripts.evaluate_execution_aware_selector import (  # noqa: E402
    _build_qgis_landing_record,
    _content_tokens,
    _quality_adjusted_score,
    build_selector_artifacts,
)


DEFAULT_CHECKPOINT = (
    OUTPUT_DIR
    / "transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed"
    / "best_preference_model.pth"
)
DEFAULT_SET_PREDICTOR = (
    OUTPUT_DIR / "set_predictor_checkpoints_v3_quality_gate_v4_6" / "best_model.pth"
)
DEFAULT_QGIS_DATASET = OUTPUT_DIR / "qgis_chain_dataset.jsonl"
DEFAULT_QGIS_CATALOG = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "diagnostics" / "end_to_end_showcase_eval"


@dataclass
class ShowcaseTask:
    task_name: str
    task_description: str
    task_type: str
    group: str

    @property
    def task_text(self) -> str:
        return f"{self.task_name} {self.task_description}".strip()


DEFAULT_TASKS: list[ShowcaseTask] = [
    ShowcaseTask(
        "Land cover classification from Sentinel imagery",
        "Classify cropland, forest, water and built-up areas for a study region using multi-band satellite imagery.",
        "Land use/land cover",
        "remote_sensing_classification",
    ),
    ShowcaseTask(
        "Vegetation condition monitoring",
        "Calculate a vegetation index from optical imagery, filter by date, clip to the area of interest, and summarize vegetation condition.",
        "Vegetation",
        "remote_sensing_raster",
    ),
    ShowcaseTask(
        "Precipitation anomaly analysis",
        "Compare monthly precipitation against a baseline period and clip the result to an administrative boundary.",
        "Precipitation",
        "remote_sensing_raster",
    ),
    ShowcaseTask(
        "Surface water extraction",
        "Detect surface water from satellite imagery, apply thresholding, and summarize water extent within a region.",
        "Surface water",
        "remote_sensing_raster",
    ),
    ShowcaseTask(
        "Land surface temperature summary",
        "Use thermal raster data to compute mean land surface temperature inside each district polygon.",
        "Surface thermal properties",
        "remote_sensing_raster",
    ),
    ShowcaseTask(
        "Terrain slope and aspect analysis",
        "Derive slope and aspect from a DEM and clip the terrain products to a watershed boundary.",
        "Topography",
        "raster_terrain",
    ),
    ShowcaseTask(
        "Road buffer and land parcel clipping",
        "Create buffers around road centerlines, clip land parcel polygons by the buffer zone, and dissolve the output by road class.",
        "Infrastructure",
        "qgis_vector",
    ),
    ShowcaseTask(
        "Administrative boundary cleanup and merge",
        "Fix invalid geometries, merge multiple administrative boundary layers, and simplify the resulting boundary layer.",
        "Boundaries",
        "qgis_vector",
    ),
    ShowcaseTask(
        "Point of interest service area",
        "Build buffer zones around schools, intersect them with residential blocks, and calculate affected population attributes.",
        "Human settlements",
        "qgis_vector",
    ),
    ShowcaseTask(
        "Flood exposure overlay",
        "Intersect a flood hazard polygon layer with building footprints and summarize exposed buildings by district.",
        "Natural hazards",
        "qgis_vector",
    ),
    ShowcaseTask(
        "Reproject and join monitoring stations",
        "Reproject air quality monitoring stations to the project CRS, spatially join them to city districts, and export the joined table.",
        "Air quality",
        "qgis_vector",
    ),
    ShowcaseTask(
        "Rasterize zoning polygons",
        "Convert zoning polygons to a raster grid, align the raster with an existing DEM, and clip it to the planning boundary.",
        "Environmental governance/management",
        "mixed_vec_raster",
    ),
    ShowcaseTask(
        "Polygonize classified raster",
        "Convert a classified land cover raster to polygons, fix geometries, and dissolve polygons by class value.",
        "Land use/land cover",
        "mixed_vec_raster",
    ),
    ShowcaseTask(
        "Zonal statistics for crop parcels",
        "Calculate mean NDVI raster values for each crop parcel polygon and append the statistics to the parcel table.",
        "Land surface/agriculture indicators",
        "mixed_vec_raster",
    ),
    ShowcaseTask(
        "Water quality raster clipping",
        "Filter water quality observations by date, select relevant raster bands, clip to lake boundaries, and compute summary statistics.",
        "Water quality",
        "remote_sensing_raster",
    ),
    ShowcaseTask(
        "Snow cover change detection",
        "Compare snow cover rasters between two dates, calculate change areas, and clip results to mountain catchments.",
        "Snow/ice",
        "remote_sensing_raster",
    ),
]


def _load_tasks(path: Path | None) -> list[ShowcaseTask]:
    if path is None:
        return list(DEFAULT_TASKS)
    tasks: list[ShowcaseTask] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            try:
                tasks.append(
                    ShowcaseTask(
                        task_name=str(item["task_name"]),
                        task_description=str(item.get("task_description", "")),
                        task_type=str(item.get("task_type", "Unknown")),
                        group=str(item.get("group", "custom")),
                    )
                )
            except KeyError as exc:
                raise ValueError(f"{path}:{line_no} missing required key {exc}") from exc
    return tasks


def _l3_parts(tokens: Sequence[int], id_to_code: dict[int, str], token_names: dict[int, str]) -> list[dict]:
    parts = []
    for tok in _content_tokens(tokens):
        code = id_to_code.get(int(tok), f"?{tok}")
        parts.append({
            "token": int(tok),
            "code": code,
            "name": str(token_names.get(int(tok), "")),
        })
    return parts


def _format_l3(parts: list[dict]) -> str:
    return " -> ".join(
        f"{p['code']}({p['name']})" if p.get("name") else str(p.get("code"))
        for p in parts
    )


def _pick_best_candidate(candidates, usability_evaluator, task_type: str, token_names: dict[int, str]):
    best = None
    details = []
    for idx, cand in enumerate(candidates[:5]):
        tokens = _content_tokens(cand.tokens)
        ev = usability_evaluator.evaluate(tokens, task_type)
        warnings = list(getattr(ev, "warnings", []) or [])
        if not warnings:
            warnings = list(getattr(ev, "forbidden_patterns", []) or [])
        if not warnings:
            warnings = [
                f for f in list(getattr(ev, "failure_taxonomy", []) or [])
                if f not in {"usable_no_failure", "unusable_marginal"}
            ]
        score = _quality_adjusted_score(ev.usability_score, tokens, warnings, token_names)
        row = {
            "rank": idx + 1,
            "tokens": tokens,
            "usable": bool(ev.usable),
            "usability_score": float(ev.usability_score),
            "quality_adjusted_score": float(score),
            "warnings": warnings,
            "failures": list(ev.failure_taxonomy),
            "model_score": float(getattr(cand, "final_score", 0.0)),
        }
        details.append(row)
        if ev.usable:
            if best is None or row["quality_adjusted_score"] > best["quality_adjusted_score"]:
                best = row
    if best is None and details:
        best = max(details, key=lambda r: r["quality_adjusted_score"])
    return best, details


def _write_csv(path: Path, records: list[dict]) -> None:
    cols = [
        "idx", "group", "task_type", "task_name", "l3_usable", "l3_score",
        "qgis_valid", "qgis_quality", "combined_bridge", "l3_bridge",
        "native_bridge", "l3_chain", "qgis_chain", "warnings", "failures",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in records:
            landing = r.get("qgis_landing", {})
            writer.writerow({
                "idx": r["idx"],
                "group": r["group"],
                "task_type": r["task_type"],
                "task_name": r["task_name"],
                "l3_usable": r["selected"].get("usable", False),
                "l3_score": round(r["selected"].get("quality_adjusted_score", 0.0), 4),
                "qgis_valid": landing.get("top1_valid", False),
                "qgis_quality": landing.get("top1_quality", 0.0),
                "combined_bridge": landing.get("combined_bridge_hit", False),
                "l3_bridge": landing.get("l3_bridge_hit", False),
                "native_bridge": landing.get("native_bridge_hit", False),
                "l3_chain": _format_l3(r["l3_parts"]),
                "qgis_chain": " -> ".join(landing.get("top1_chain", [])),
                "warnings": "; ".join(r["selected"].get("warnings", [])),
                "failures": "; ".join(r["selected"].get("failures", [])),
            })


def _write_markdown(path: Path, report: dict, records: list[dict]) -> None:
    s = report["summary"]
    lines = [
        "# End-to-End Showcase Evaluation",
        "",
        "This is a demonstration/probe evaluation, not a supervised semantic-accuracy benchmark.",
        "",
        "## Summary",
        "",
        f"- Tasks: {s['num_tasks']}",
        f"- L3 rule-usable: {s['l3_usable']}/{s['num_tasks']} ({s['l3_usable_rate']:.1%})",
        f"- QGIS top-1 valid: {s['qgis_valid']}/{s['num_tasks']} ({s['qgis_valid_rate']:.1%})",
        f"- QGIS combined bridge: {s['combined_bridge']}/{s['num_tasks']} ({s['combined_bridge_rate']:.1%})",
        f"- QGIS L3 bridge: {s['l3_bridge']}/{s['num_tasks']} ({s['l3_bridge_rate']:.1%})",
        f"- QGIS native bridge: {s['native_bridge']}/{s['num_tasks']} ({s['native_bridge_rate']:.1%})",
        f"- Mean QGIS quality: {s['mean_qgis_quality']:.4f}",
        "",
        "## Interpretation Boundary",
        "",
        "- This proves the current checkpoint can be run end-to-end through rule checks and QGIS landing on these probes.",
        "- It does not prove parameter-level execution in QGIS or strict semantic optimality.",
        "- Native bridge is a landing-only bridge for QGIS-native operations; it is not a new L3 class.",
        "",
        "## Cases",
        "",
    ]
    for r in records:
        landing = r.get("qgis_landing", {})
        lines.extend([
            f"### {r['idx']}. {r['task_name']}",
            "",
            f"- Group: `{r['group']}`",
            f"- Task type: `{r['task_type']}`",
            f"- Description: {r['task_description']}",
            f"- L3 usable: `{r['selected'].get('usable')}`; score `{r['selected'].get('quality_adjusted_score', 0.0):.4f}`",
            f"- L3 chain: {_format_l3(r['l3_parts'])}",
            f"- QGIS valid: `{landing.get('top1_valid')}`; quality `{landing.get('top1_quality', 0.0):.4f}`",
            f"- Bridge: L3 `{landing.get('l3_bridge_hit')}`, native `{landing.get('native_bridge_hit')}`, combined `{landing.get('combined_bridge_hit')}`",
            f"- QGIS chain: {' -> '.join(landing.get('top1_chain', []))}",
        ])
        warnings = r["selected"].get("warnings", [])
        failures = r["selected"].get("failures", [])
        if warnings:
            lines.append(f"- Warnings: {'; '.join(warnings)}")
        if failures:
            lines.append(f"- Failures: {'; '.join(failures)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = _load_tasks(Path(args.task_file) if args.task_file else None)
    if args.max_tasks is not None:
        tasks = tasks[: args.max_tasks]
    if not tasks:
        raise ValueError("No tasks to evaluate")

    print("[1] Loading selector/usability metadata...")
    artifacts = build_selector_artifacts(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        hierarchy_path=Path(args.hierarchy),
        id_mappings_path=Path(args.id_mappings),
        io_types_path=OUTPUT_DIR / "qgis_operator_io_types.json",
        transition_path=OUTPUT_DIR / "transition_allowed_next.json",
        length_stats_path=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "task_type_length_stats.json",
    )
    id_to_code = artifacts["id_to_code"]
    token_names = artifacts.get("token_names", {})
    usability_evaluator = artifacts["usability_evaluator"]

    print("[2] Loading model checkpoint...")
    inferencer = L3SequenceInferencerV4(
        checkpoint_path=Path(args.checkpoint),
        set_predictor_path=Path(args.set_predictor) if args.set_predictor else None,
        task_vocab_path=Path(args.task_vocab),
    )

    print("[3] Loading QGIS landing planner...")
    qgis_retriever, qgis_evaluator = build_qgis_chain_planner(
        dataset_path=Path(args.qgis_chain_dataset),
        catalog_path=Path(args.qgis_catalog),
    )

    print(f"[4] Running {len(tasks)} showcase tasks...")
    records = []
    for idx, task in enumerate(tasks, start=1):
        print(f"  [{idx}/{len(tasks)}] {task.task_name} ({task.task_type})")
        candidates = inferencer.infer(
            task_name=task.task_name,
            task_description=task.task_description,
            task_type=task.task_type,
            mode="beam",
        )
        selected, candidate_details = _pick_best_candidate(
            candidates=candidates,
            usability_evaluator=usability_evaluator,
            task_type=task.task_type,
            token_names=token_names,
        )
        if selected is None:
            selected = {
                "tokens": [],
                "usable": False,
                "usability_score": 0.0,
                "quality_adjusted_score": 0.0,
                "warnings": [],
                "failures": ["no_candidates"],
            }

        landing = _build_qgis_landing_record(
            retriever=qgis_retriever,
            evaluator=qgis_evaluator,
            task_text=task.task_text,
            final_tokens=selected["tokens"],
            id_to_code=id_to_code,
            k=args.qgis_landing_k,
        )
        records.append({
            "idx": idx,
            "group": task.group,
            "task_name": task.task_name,
            "task_description": task.task_description,
            "task_type": task.task_type,
            "selected": selected,
            "l3_parts": _l3_parts(selected["tokens"], id_to_code, token_names),
            "beam_candidates": candidate_details,
            "qgis_landing": landing,
        })

    n = len(records)
    l3_usable = sum(1 for r in records if r["selected"].get("usable", False))
    qgis_valid = sum(1 for r in records if r["qgis_landing"].get("top1_valid", False))
    combined_bridge = sum(1 for r in records if r["qgis_landing"].get("combined_bridge_hit", False))
    l3_bridge = sum(1 for r in records if r["qgis_landing"].get("l3_bridge_hit", False))
    native_bridge = sum(1 for r in records if r["qgis_landing"].get("native_bridge_hit", False))
    mean_qgis_quality = (
        sum(float(r["qgis_landing"].get("top1_quality", 0.0)) for r in records) / max(n, 1)
    )

    report = {
        "schema": "gis_recommend.end_to_end_showcase_eval.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "checkpoint": str(Path(args.checkpoint)),
        "set_predictor": str(Path(args.set_predictor)) if args.set_predictor else None,
        "qgis_chain_dataset": str(Path(args.qgis_chain_dataset)),
        "qgis_catalog": str(Path(args.qgis_catalog)),
        "summary": {
            "num_tasks": n,
            "l3_usable": l3_usable,
            "l3_usable_rate": l3_usable / max(n, 1),
            "qgis_valid": qgis_valid,
            "qgis_valid_rate": qgis_valid / max(n, 1),
            "combined_bridge": combined_bridge,
            "combined_bridge_rate": combined_bridge / max(n, 1),
            "l3_bridge": l3_bridge,
            "l3_bridge_rate": l3_bridge / max(n, 1),
            "native_bridge": native_bridge,
            "native_bridge_rate": native_bridge / max(n, 1),
            "mean_qgis_quality": mean_qgis_quality,
        },
        "records": records,
    }

    json_path = out_dir / "end_to_end_showcase_eval.json"
    csv_path = out_dir / "end_to_end_showcase_eval.csv"
    md_path = out_dir / "end_to_end_showcase_eval.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, records)
    _write_markdown(md_path, report, records)

    print("\nSummary:")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\nReports written to {out_dir}")
    print(f"  {json_path.name}")
    print(f"  {csv_path.name}")
    print(f"  {md_path.name}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--set-predictor", default=str(DEFAULT_SET_PREDICTOR))
    parser.add_argument("--task-file", default=None, help="Optional JSONL with task_name/task_description/task_type/group")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--qgis-chain-dataset", default=str(DEFAULT_QGIS_DATASET))
    parser.add_argument("--qgis-catalog", default=str(DEFAULT_QGIS_CATALOG))
    parser.add_argument("--qgis-landing-k", type=int, default=5)
    parser.add_argument("--data", default=str(V4_QG_LABELED_WORKFLOWS_PATH))
    parser.add_argument("--splits", default=str(V4_QG_SPLITS_PATH))
    parser.add_argument("--hierarchy", default=str(CLASSIFICATION_HIERARCHY))
    parser.add_argument("--id-mappings", default=str(ID_MAPPINGS_PATH))
    parser.add_argument(
        "--task-vocab",
        default=str(OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
