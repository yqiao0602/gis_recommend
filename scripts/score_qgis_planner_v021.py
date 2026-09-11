#!/usr/bin/env python3
"""Score M1/M3 locked predictions against the assembled v0.2.1 gold.

Imports the frozen benchmark scorer's metric functions verbatim
(scripts/score_qgis_planner_benchmark_v01.py @ 358bdea) — zero metric
reimplementation. Only the gold loading is v0.2.1-compositional (handled by
assemble_qgis_planner_v021_gold.py, already run).

Usage:
  python score_qgis_planner_v021.py \
      --gold-dir docs/reports/qgis_planner_eval_v1/gold \
      --pred-dir docs/reports/qgis_planner_eval_v1/predictions \
      --out docs/reports/qgis_planner_eval_v1/SCORES_v1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from score_qgis_planner_benchmark_v01 import score_benchmark  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-dir", type=Path, required=True)
    ap.add_argument("--pred-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    graph_gold = read_jsonl(args.gold_dir / "final_100.gold.jsonl")
    refusal_gold = read_jsonl(args.gold_dir / "refusal_12.gold.jsonl")

    results = {}
    for route in ("m1", "m3"):
        graph_pred = read_jsonl(args.pred_dir / f"{route}_final_100_predictions.jsonl")
        refusal_pred = read_jsonl(args.pred_dir / f"{route}_refusal_12_predictions.jsonl")
        scored = score_benchmark(graph_gold, graph_pred, refusal_gold, refusal_pred)
        # diagnostics kept separate from the frozen metric block
        results[route] = {
            "graph": scored["graph"],
            "refusal": scored["refusal"],
            "graph_samples": scored["graph_samples"],
            "refusal_samples": scored["refusal_samples"],
        }
        print(f"\n===== {route.upper()} — qgis-planner-benchmark v0.2.1 final =====")
        print(json.dumps({"graph": scored["graph"], "refusal": scored["refusal"]},
                         indent=2, ensure_ascii=False))

    out = {
        "schema": "gis_recommend.qgis_planner_v021_scores.v1",
        "benchmark": "qgis-planner-benchmark-v0.2.1 @ 6006e49",
        "scorer": "score_qgis_planner_benchmark_v01.py score_benchmark (frozen, verbatim)",
        "gold_assembly": "assemble_qgis_planner_v021_gold.py (87 sealed + 13 authority DAGs, 11/11 gates)",
        "prediction_lock": "PREDICTION_LOCK_v1.json sha 4c0492cb… (verified before gold access)",
        "results": results,
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
