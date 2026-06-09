#!/usr/bin/env python3
"""Unseen vector generalization test: DPO v2 vs QGIS-vector SFT.

This evaluates hand-written prompts in configs/unseen_vector_prompts.jsonl.
It intentionally does not read canonical_vector_clean_sft_seed.jsonl, so the
QGIS side is a held-out prompt benchmark rather than a train-source absorption
smoke test.

Important interpretation notes:
  - DPO v2 has only the original 47 task types and no "Vector Analysis" task
    type. For vector and mixed prompts, the DPO baseline therefore falls back
    to task_type_id=0 while SFT uses the new Vector Analysis task type.
  - Expected-family recall is reported in two forms. "Measurable" recall only
    scores families that can be represented by the current 94-L3 vocabulary and
    this script's explicit L3-to-family mapping. "Strict/all" recall keeps the
    prompt file's full expected_families denominator and will be lower when a
    requested QGIS family has no current L3 token.
  - Raster clip is kept distinct from vector clip, so L3_03_01_01 does not
    satisfy vector "clip" on pure vector tasks.

Usage (server):
    python scripts/evaluate_vector_generalization.py

Oversampled SFT example:
    python scripts/evaluate_vector_generalization.py \
        --sft-checkpoint outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/best_model.pth \
        --sft-task-vocab outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_vocabulary_v4_quality_gate_qgis_vector_oversampled.json \
        --sft-length-stats outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_length_stats.json \
        --report-path outputs_v2/diagnostics/vector_generalization_oversampled.json
"""

from __future__ import annotations

import csv
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch
from gis_recommend.config.transformer_config import DEVICE
from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

SFT_CKPT = ROOT / "outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector/best_model.pth"
DPO_CKPT = ROOT / "outputs_v2/transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed/best_preference_model.pth"

PROMPTS = ROOT / "configs" / "unseen_vector_prompts.jsonl"
ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
HIERARCHY = ROOT / "outputs_v2/classification_hierarchy_v2.csv"

SFT_VOCAB = ROOT / "outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_vocabulary_v4_quality_gate_qgis_vector.json"
DPO_VOCAB = ROOT / "outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json"
SFT_LENGTH_STATS = ROOT / "outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_length_stats.json"
DPO_LENGTH_STATS = ROOT / "outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json"

REPORT_PATH = ROOT / "outputs_v2/diagnostics/vector_generalization.json"

VECTOR_TASK_TYPE = "Vector Analysis"

# Raster-ish L1 groups used for leakage diagnostics on vector prompts.
# L1_03 is the strict raster-analysis family; L1_04/L1_08/L1_09/L1_10 catch
# terrain, image-classification, image-enhancement, and image-fusion operations
# that should also be treated as non-vector leakage in this benchmark.
RASTERISH_L1_CODES = {"L1_03", "L1_04", "L1_08", "L1_09", "L1_10"}
RASTERISH_EXTRA_L3 = {
    "L3_01_01_03",  # Create Raster Dataset
    "L3_01_13_01",  # Change Pixel Data Type
    "L3_07_01_05",  # Render Raster
    "L3_07_04_05",  # Export Raster
    "L3_07_04_06",  # Export Raster/Image
}

# Current 94-L3 vocabulary cannot express every QGIS family in the hand-written
# prompts. Keep this mapping explicit so unsupported families are visible.
L3_TO_FAMILIES: dict[str, tuple[str, ...]] = {
    # Vector proximity / overlay / extraction
    "L3_02_01_01": ("buffer",),
    "L3_02_02_01": ("intersection",),
    "L3_02_02_02": ("union",),
    "L3_02_02_04": ("difference",),
    "L3_02_02_05": ("symdiff",),
    "L3_02_02_06": ("clip",),
    "L3_02_03_05": ("dissolve", "point_aggregation"),
    "L3_02_04_01": ("spatial_join", "table_join"),
    "L3_02_06_01": ("attribute_filter",),
    "L3_02_06_02": ("attribute_filter",),
    "L3_02_06_03": ("spatial_filter",),
    "L3_02_06_05": ("spatial_filter",),
    # Geometry and data-management families. Some are intentionally coarse
    # because the current L3 taxonomy collapsed several QGIS vector operations.
    "L3_02_05_06": ("geometry_split",),
    "L3_02_05_11": ("centroid", "geometry_conversion"),
    "L3_02_05_12": ("grid_generation", "convex_hull"),
    "L3_02_07_01": ("geometry_repair", "geometry_cleanup"),
    "L3_01_02_01": ("field_restructure",),
    "L3_01_02_02": ("field_restructure",),
    "L3_01_02_03": ("crs_transform", "field_restructure"),
    "L3_01_02_06": ("field_calculate",),
    "L3_01_03_04": ("merge",),
    "L3_07_04_01": ("data_export",),
    # Raster and mixed operations. Raster clip is not vector clip.
    "L3_03_01_01": ("raster_clip",),
    "L3_03_01_02": ("raster_clip",),
    "L3_03_01_03": ("raster_attribute_filter",),
    "L3_03_02_01": ("zonal_statistics",),
    "L3_03_03_A": ("raster_algebra",),
    "L3_03_03_L": ("raster_algebra",),
    "L3_03_04_01": ("reclassify",),
    "L3_03_04_02": ("reclassify",),
    "L3_03_04_03": ("reclassify",),
    "L3_03_08_01": ("raster_algebra",),
    "L3_04_01_01": ("terrain_analysis",),
    "L3_04_01_02": ("terrain_analysis",),
    "L3_04_01_03": ("terrain_analysis",),
}

OVERLAY_FAMILIES = ("intersection", "union", "difference", "symdiff")


def require_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def load_json(path: Path, label: str) -> Any:
    require_path(path, label)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks() -> list[dict[str, Any]]:
    require_path(PROMPTS, "unseen prompt file")
    tasks: list[dict[str, Any]] = []
    with PROMPTS.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            for key in ("id", "task", "expected_families", "modality"):
                if key not in row:
                    raise ValueError(f"{PROMPTS}:{line_no} missing required key {key!r}")
            if row["modality"] not in {"vector", "mixed", "raster"}:
                raise ValueError(f"{PROMPTS}:{line_no} has unsupported modality {row['modality']!r}")
            if not isinstance(row["expected_families"], list):
                raise ValueError(f"{PROMPTS}:{line_no} expected_families must be a list")
            tasks.append(row)
    if not tasks:
        raise ValueError(f"No tasks found in {PROMPTS}")
    return tasks


def load_token_maps() -> tuple[dict[str, int], dict[int, str]]:
    idm = load_json(ID_MAPPINGS, "94-L3 id mappings")
    l3_to_token = {code: int(idx) for code, idx in idm.get("l3", {}).items()}
    token_to_l3 = {idx: code for code, idx in l3_to_token.items()}
    return l3_to_token, token_to_l3


def load_token_sets(l3_to_token: dict[str, int]) -> dict[str, set[int]]:
    require_path(HIERARCHY, "94-L3 hierarchy")
    vector_l3: set[str] = set()
    rasterish_l3: set[str] = set(RASTERISH_EXTRA_L3)

    with HIERARCHY.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = row["l3_code"]
            if row["l1_code"] == "L1_02":
                vector_l3.add(code)
            if row["l1_code"] in RASTERISH_L1_CODES:
                rasterish_l3.add(code)

    return {
        "vector": {l3_to_token[c] for c in vector_l3 if c in l3_to_token},
        "rasterish": {l3_to_token[c] for c in rasterish_l3 if c in l3_to_token},
    }


def measurable_families() -> set[str]:
    return {fam for families in L3_TO_FAMILIES.values() for fam in families}


def predict_families(codes: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for code in codes:
        for family in L3_TO_FAMILIES.get(code, ()):
            seen.setdefault(family, None)
    return list(seen)


def infer_raster_task_type(task: dict[str, Any]) -> str:
    text = f"{task.get('task', '')} {' '.join(task.get('expected_families', []))}".lower()
    if any(word in text for word in ("hillshade", "slope", "aspect", "dem", "terrain", "surface model")):
        return "Topography"
    if any(word in text for word in ("vegetation", "ndvi", "nir", "red band")):
        return "Vegetation"
    if any(word in text for word in ("land cover", "classified", "classification")):
        return "Land use/land cover"
    return "Unknown"


def task_type_for(task: dict[str, Any]) -> str:
    if task["modality"] == "raster":
        return infer_raster_task_type(task)
    return VECTOR_TASK_TYPE


def build_inferencer(ckpt: Path, vocab: Path, length_stats: Path) -> L3SequenceInferencerV4:
    return L3SequenceInferencerV4(
        checkpoint_path=ckpt,
        device=DEVICE,
        task_vocab_path=vocab,
        length_stats_path=length_stats,
    )


def run_prediction(
    inferencer: L3SequenceInferencerV4,
    task: dict[str, Any],
    token_to_l3: dict[int, str],
) -> dict[str, Any]:
    task_type = task_type_for(task)
    inferencer.set_complexity_profile(task_type)
    candidates = inferencer.infer(
        task_name="",
        task_description=str(task["task"])[:240],
        task_type=task_type,
    )
    tokens = [int(tok) for tok in candidates[0].tokens if int(tok) >= 0] if candidates else []
    codes = [token_to_l3.get(tok, f"UNKNOWN_{tok}") for tok in tokens]
    families = predict_families(codes)
    return {
        "task_type": task_type,
        "tokens": tokens,
        "codes": codes,
        "families": families,
        "length": len(codes),
    }


def score_prediction(
    expected: list[str],
    prediction: dict[str, Any],
    token_sets: dict[str, set[int]],
    measurable: set[str],
) -> dict[str, Any]:
    expected_set = set(expected)
    pred_set = set(prediction["families"])
    measurable_expected = [fam for fam in expected if fam in measurable]
    measurable_expected_set = set(measurable_expected)
    tokens = prediction["tokens"]

    return {
        "recall_all": len(expected_set & pred_set) / max(len(expected_set), 1),
        "recall_measurable": (
            len(measurable_expected_set & pred_set) / len(measurable_expected_set)
            if measurable_expected_set
            else None
        ),
        "measurable_expected": measurable_expected,
        "raster_token_rate": (
            sum(1 for tok in tokens if tok in token_sets["rasterish"]) / len(tokens)
            if tokens
            else 0.0
        ),
        "vector_token_rate": (
            sum(1 for tok in tokens if tok in token_sets["vector"]) / len(tokens)
            if tokens
            else 0.0
        ),
        "length": prediction["length"],
    }


def mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        "dpo_recall_measurable": mean([r["dpo"]["recall_measurable"] for r in rows]),
        "sft_recall_measurable": mean([r["sft"]["recall_measurable"] for r in rows]),
        "dpo_recall_all": mean([r["dpo"]["recall_all"] for r in rows]),
        "sft_recall_all": mean([r["sft"]["recall_all"] for r in rows]),
        "dpo_raster_token_rate": mean([r["dpo"]["raster_token_rate"] for r in rows]),
        "sft_raster_token_rate": mean([r["sft"]["raster_token_rate"] for r in rows]),
        "dpo_vector_token_rate": mean([r["dpo"]["vector_token_rate"] for r in rows]),
        "sft_vector_token_rate": mean([r["sft"]["vector_token_rate"] for r in rows]),
        "dpo_mean_length": mean([r["dpo"]["length"] for r in rows]),
        "sft_mean_length": mean([r["sft"]["length"] for r in rows]),
        "measurable_task_count": sum(1 for r in rows if r["dpo"]["recall_measurable"] is not None),
    }


def overlay_recall(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for family in OVERLAY_FAMILIES:
        expected_rows = [r for r in rows if family in r["expected"]]
        n = len(expected_rows)
        dpo_hits = sum(1 for r in expected_rows if family in r["dpo_prediction"]["families"])
        sft_hits = sum(1 for r in expected_rows if family in r["sft_prediction"]["families"])
        out[family] = {
            "n": n,
            "dpo": dpo_hits / n if n else None,
            "sft": sft_hits / n if n else None,
            "dpo_hits": dpo_hits,
            "sft_hits": sft_hits,
        }
    return out


def fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def fmt_delta(a: float | None, b: float | None, pct: bool = True) -> str:
    if a is None or b is None:
        return "n/a"
    delta = b - a
    return f"{delta * 100:+.1f}pp" if pct else f"{delta:+.1f}"


def print_aggregate(title: str, agg: dict[str, Any]) -> None:
    print(f"\n{title} ({agg['n']} tasks, measurable={agg['measurable_task_count']}):")
    print(f"{'Metric':34s} {'DPO v2':>10s} {'SFT':>10s} {'Delta':>10s}")
    print("-" * 70)
    print(
        f"{'Expected recall (measurable)':34s} "
        f"{fmt_pct(agg['dpo_recall_measurable']):>10s} "
        f"{fmt_pct(agg['sft_recall_measurable']):>10s} "
        f"{fmt_delta(agg['dpo_recall_measurable'], agg['sft_recall_measurable']):>10s}"
    )
    print(
        f"{'Expected recall (strict/all)':34s} "
        f"{fmt_pct(agg['dpo_recall_all']):>10s} "
        f"{fmt_pct(agg['sft_recall_all']):>10s} "
        f"{fmt_delta(agg['dpo_recall_all'], agg['sft_recall_all']):>10s}"
    )
    print(
        f"{'Raster-ish token rate':34s} "
        f"{fmt_pct(agg['dpo_raster_token_rate']):>10s} "
        f"{fmt_pct(agg['sft_raster_token_rate']):>10s} "
        f"{fmt_delta(agg['dpo_raster_token_rate'], agg['sft_raster_token_rate']):>10s}"
    )
    print(
        f"{'Vector token rate':34s} "
        f"{fmt_pct(agg['dpo_vector_token_rate']):>10s} "
        f"{fmt_pct(agg['sft_vector_token_rate']):>10s} "
        f"{fmt_delta(agg['dpo_vector_token_rate'], agg['sft_vector_token_rate']):>10s}"
    )
    print(
        f"{'Mean chain length':34s} "
        f"{fmt_num(agg['dpo_mean_length']):>10s} "
        f"{fmt_num(agg['sft_mean_length']):>10s} "
        f"{fmt_delta(agg['dpo_mean_length'], agg['sft_mean_length'], pct=False):>10s}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sft-checkpoint", type=Path, default=SFT_CKPT)
    parser.add_argument("--dpo-checkpoint", type=Path, default=DPO_CKPT)
    parser.add_argument("--prompts", type=Path, default=PROMPTS)
    parser.add_argument("--id-mappings", type=Path, default=ID_MAPPINGS)
    parser.add_argument("--hierarchy", type=Path, default=HIERARCHY)
    parser.add_argument("--sft-task-vocab", type=Path, default=SFT_VOCAB)
    parser.add_argument("--dpo-task-vocab", type=Path, default=DPO_VOCAB)
    parser.add_argument("--sft-length-stats", type=Path, default=SFT_LENGTH_STATS)
    parser.add_argument("--dpo-length-stats", type=Path, default=DPO_LENGTH_STATS)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    global SFT_CKPT, DPO_CKPT, PROMPTS, ID_MAPPINGS, HIERARCHY
    global SFT_VOCAB, DPO_VOCAB, SFT_LENGTH_STATS, DPO_LENGTH_STATS, REPORT_PATH

    args = parse_args(argv)
    SFT_CKPT = args.sft_checkpoint
    DPO_CKPT = args.dpo_checkpoint
    PROMPTS = args.prompts
    ID_MAPPINGS = args.id_mappings
    HIERARCHY = args.hierarchy
    SFT_VOCAB = args.sft_task_vocab
    DPO_VOCAB = args.dpo_task_vocab
    SFT_LENGTH_STATS = args.sft_length_stats
    DPO_LENGTH_STATS = args.dpo_length_stats
    REPORT_PATH = args.report_path

    random.seed(42)
    torch.manual_seed(42)

    for path, label in [
        (SFT_CKPT, "SFT checkpoint"),
        (DPO_CKPT, "DPO checkpoint"),
        (SFT_VOCAB, "48-task SFT vocab"),
        (DPO_VOCAB, "47-task DPO vocab"),
        (SFT_LENGTH_STATS, "48-task SFT length stats"),
        (DPO_LENGTH_STATS, "47-task DPO length stats"),
    ]:
        require_path(path, label)

    tasks = load_tasks()
    counts = Counter(task["modality"] for task in tasks)
    print(
        f"Tasks: {len(tasks)} "
        f"(vector={counts['vector']}, mixed={counts['mixed']}, raster={counts['raster']})"
    )

    l3_to_token, token_to_l3 = load_token_maps()
    token_sets = load_token_sets(l3_to_token)
    measurable = measurable_families()
    expected_counts = Counter(fam for task in tasks for fam in task["expected_families"])
    unsupported = {fam: n for fam, n in sorted(expected_counts.items()) if fam not in measurable}
    if unsupported:
        print("\nUnsupported expected families under current 94-L3 family map:")
        for fam, count in unsupported.items():
            print(f"  {fam}: {count}")

    print(f"\nStrict vector tokens: {len(token_sets['vector'])}")
    print(f"Raster-ish leakage tokens: {len(token_sets['rasterish'])}")

    print(f"\nLoading SFT model ({SFT_CKPT}) ...")
    inf_sft = build_inferencer(SFT_CKPT, SFT_VOCAB, SFT_LENGTH_STATS)
    print(f"Loading DPO v2 model ({DPO_CKPT}) ...")
    inf_dpo = build_inferencer(DPO_CKPT, DPO_VOCAB, DPO_LENGTH_STATS)

    results: list[dict[str, Any]] = []
    print("\nRunning unseen prompts ...")
    for task in tasks:
        sft_prediction = run_prediction(inf_sft, task, token_to_l3)
        dpo_prediction = run_prediction(inf_dpo, task, token_to_l3)
        sft_score = score_prediction(task["expected_families"], sft_prediction, token_sets, measurable)
        dpo_score = score_prediction(task["expected_families"], dpo_prediction, token_sets, measurable)
        results.append(
            {
                "id": task["id"],
                "task": task["task"],
                "modality": task["modality"],
                "expected": task["expected_families"],
                "dpo_prediction": dpo_prediction,
                "sft_prediction": sft_prediction,
                "dpo": dpo_score,
                "sft": sft_score,
            }
        )

    by_modality = {
        modality: [row for row in results if row["modality"] == modality]
        for modality in ("vector", "mixed", "raster")
    }
    aggregates = {modality: aggregate(rows) for modality, rows in by_modality.items()}

    print("\n" + "=" * 80)
    print_aggregate("Vector prompts", aggregates["vector"])
    print_aggregate("Mixed prompts", aggregates["mixed"])
    print_aggregate("Raster controls", aggregates["raster"])

    overlay = overlay_recall(by_modality["vector"])
    print("\nOverlay subtype recall on vector prompts:")
    for family, stats in overlay.items():
        n = stats["n"]
        if n == 0:
            print(f"  {family:15s}: n=0")
        else:
            print(
                f"  {family:15s}: "
                f"DPO={fmt_pct(stats['dpo'])} ({stats['dpo_hits']}/{n}), "
                f"SFT={fmt_pct(stats['sft'])} ({stats['sft_hits']}/{n})"
            )

    print("\n" + "=" * 80)
    print("Sample predictions (10 vector prompts):")
    vector_rows = by_modality["vector"]
    for row in random.sample(vector_rows, min(10, len(vector_rows))):
        new_families = sorted(set(row["sft_prediction"]["families"]) - set(row["dpo_prediction"]["families"]))
        suffix = f" +{new_families}" if new_families else ""
        print(f"\n  [{row['id']}] {row['task'][:110]}")
        print(f"    Expected: {row['expected']}")
        print(
            f"    DPO: ({fmt_pct(row['dpo']['recall_measurable'])} measurable) "
            f"{' -> '.join(row['dpo_prediction']['codes'][:8])}"
        )
        print(
            f"    SFT: ({fmt_pct(row['sft']['recall_measurable'])} measurable) "
            f"{' -> '.join(row['sft_prediction']['codes'][:8])}{suffix}"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "paths": {
                    "prompts": str(PROMPTS),
                    "sft_checkpoint": str(SFT_CKPT),
                    "dpo_checkpoint": str(DPO_CKPT),
                    "sft_task_vocab": str(SFT_VOCAB),
                    "dpo_task_vocab": str(DPO_VOCAB),
                    "sft_length_stats": str(SFT_LENGTH_STATS),
                    "dpo_length_stats": str(DPO_LENGTH_STATS),
                    "id_mappings": str(ID_MAPPINGS),
                    "hierarchy": str(HIERARCHY),
                },
                "task_counts": dict(counts),
                "unsupported_expected_families": unsupported,
                "measurable_families": sorted(measurable),
                "token_set_sizes": {
                    "vector": len(token_sets["vector"]),
                    "rasterish": len(token_sets["rasterish"]),
                },
                "aggregates": aggregates,
                "overlay_recall": overlay,
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
