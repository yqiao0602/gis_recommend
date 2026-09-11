#!/usr/bin/env python3
"""Prediction SHA-256 lock for qgis-planner-benchmark v0.2.1 (M1/M3 final-100 + refusal-12).

Runs AFTER all inference, BEFORE any sealed-gold access. Writes one lock
record per prediction file: row count, sample_id list hash, full-file SHA,
and the frozen-config SHAs it was produced under. Append-only intent — the
lock file is itself hashed into the scoring report.

Usage (server):
  python qgis_planner_prediction_lock.py --pred-dir qgis_planner_eval_v1 \
      --config-freeze INFERENCE_CONFIG_FREEZE_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def sample_id_digest(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update(r["sample_id"].encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred-dir", type=Path, required=True)
    ap.add_argument("--config-freeze", type=Path, required=True)
    args = ap.parse_args()

    freeze = json.loads(args.config_freeze.read_text(encoding="utf-8"))
    files = [
        "m1_final_100_predictions.jsonl",
        "m3_final_100_predictions.jsonl",
        "m1_refusal_12_predictions.jsonl",
        "m3_refusal_12_predictions.jsonl",
    ]

    lock = {
        "schema": "gis_recommend.qgis_planner_prediction_lock.v1",
        "benchmark": freeze["benchmark"],
        "locked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config_freeze_sha256": sha256_file(args.config_freeze),
        "m1_checkpoint_sha256": freeze["m1"]["checkpoint_sha256"],
        "m3_adapter_sha256": freeze["m3"]["adapter_sha256"],
        "bridge_sha256": freeze["bridge"]["sha256"],
        "disclosure_policy": "predictions locked before any sealed-gold access; scoring may only start after this file is written",
        "predictions": {},
    }

    missing = []
    for name in files:
        path = args.pred_dir / name
        if not path.exists():
            missing.append(name)
            continue
        rows = load_rows(path)
        lock["predictions"][name] = {
            "rows": len(rows),
            "sha256": sha256_file(path),
            "sample_ids_sha256": sample_id_digest(rows),
        }
        print(f"  locked {name}: {len(rows)} rows, sha256={lock['predictions'][name]['sha256'][:16]}…")

    if missing:
        print(f"LOCK INCOMPLETE — missing: {missing}")
        return 1

    out = args.pred_dir / "PREDICTION_LOCK_v1.json"
    out.write_text(json.dumps(lock, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nLOCK WRITTEN: {out}")
    print(f"lock file sha256: {sha256_file(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
