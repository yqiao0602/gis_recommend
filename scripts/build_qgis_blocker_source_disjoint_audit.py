"""Freeze a bounded, source-disjoint audit packet for Processing blockers."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


LANES = ("recover_call_graph", "review_api_sidecar")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rank(seed: int, lane: str, role: str, row: dict[str, Any]) -> str:
    return hashlib.sha256(f"{seed}\x1f{lane}\x1f{role}\x1f{row.get('source_sha256','')}".encode()).hexdigest()


def build_packet(rows: list[dict[str, Any]], *, per_lane_per_split: int = 15, seed: int = 20260902) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if per_lane_per_split <= 0:
        raise ValueError("per_lane_per_split must be positive")
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for row in rows:
        lane = str(row.get("action") or "")
        source = str(row.get("source_sha256") or "")
        if lane not in LANES:
            continue
        if len(source) != 64:
            raise ValueError(f"invalid source SHA for {row.get('record_id')}")
        if source in seen:
            raise ValueError(f"duplicate source SHA in blocker pool: {source}")
        seen.add(source)
        by_lane[lane].append(dict(row))
    packet: list[dict[str, Any]] = []
    selected_by_lane: dict[str, dict[str, int]] = {}
    for lane in LANES:
        ordered = sorted(by_lane[lane], key=lambda row: rank(seed, lane, "audit", row))
        required = per_lane_per_split * 2
        if len(ordered) < required:
            raise ValueError(f"insufficient rows for {lane}: {len(ordered)} < {required}")
        chosen = ordered[:required]
        selected_by_lane[lane] = {"calibration": per_lane_per_split, "holdout": per_lane_per_split}
        for index, row in enumerate(chosen):
            output = dict(row)
            output.update({
                "schema": "gis_recommend.qgis_processing_blocker_audit.v1",
                "audit_lane": lane,
                "audit_role": "calibration" if index < per_lane_per_split else "holdout",
                "audit_seed": seed,
                "source_disjoint_status": "frozen_by_source_sha256",
                "source_verification": "pending_source_replay",
                "semantic_review_status": "pending",
                "training_admission": "not_granted_blocker_audit",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            })
            packet.append(output)
    calibration = {str(row["source_sha256"]) for row in packet if row["audit_role"] == "calibration"}
    holdout = {str(row["source_sha256"]) for row in packet if row["audit_role"] == "holdout"}
    if calibration & holdout:
        raise ValueError("calibration/holdout source overlap")
    return packet, {
        "schema": "gis_recommend.qgis_processing_blocker_audit.v1.summary",
        "input_rows": len(rows),
        "eligible_lane_rows": {lane: len(by_lane[lane]) for lane in LANES},
        "selected_by_lane": selected_by_lane,
        "packet_rows": len(packet),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha256_zero_overlap": True,
        "source_replay": "pending",
        "semantic_review": "pending",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_blocker_audit",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-lane-per-split", type=int, default=15)
    parser.add_argument("--seed", type=int, default=20260902)
    args = parser.parse_args()
    packet, summary = build_packet(read_jsonl(args.replay), per_lane_per_split=args.per_lane_per_split, seed=args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit_packet_v1.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in packet), encoding="utf-8")
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
