#!/usr/bin/env python3
"""Experiment master ledger: one registry for every model experiment.

Every training or evaluation run gets an experiment ID with its checkpoint SHA,
data version, hyperparameters, memory, GPU time, and metrics attached — so no
result can later be orphaned from its provenance. Entries are append-only:
re-running an ID requires an explicit supersede note, never silent overwrite.

This module only defines the ledger mechanics; individual experiments (M3-P0,
M3-P1, M2-C0/P1/P2, M1) append entries through their run scripts.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.model_experiment_ledger.v1"

# Route definitions frozen 2026-09-07 (see task_plan "Model-experiment route definitions").
ROUTES = {
    "M1": "in-house planning model (BERT encoder -> task conditioning -> decoder -> L3), continued training",
    "M2": "Qwen3.5-9B-Base -> DAPT -> task SFT (domain specialization)",
    "M2-C0": "M2 control: Base -> task SFT only (no DAPT)",
    "M2-P1": "Base -> DAPT only (intermediate check)",
    "M2-P2": "Base -> DAPT -> SFT (main M2 line)",
    "M3": "post-trained Qwen3.5-9B -> task QLoRA/SFT only",
    "M3-P0": "post-trained Qwen3.5-9B zero-shot, no training",
    "M3-P1": "post-trained Qwen3.5-9B + QLoRA/SFT",
    "B0": "external strong LLM baseline",
}

STATUS = ("planned", "running", "done", "failed", "superseded")


class ExperimentLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _write(self, entries: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in entries), encoding="utf-8")
        tmp.replace(self.path)

    def register(
        self,
        experiment_id: str,
        route: str,
        *,
        data_version: str,
        model_path: str | None = None,
        checkpoint_sha256: str | None = None,
        params: dict[str, Any] | None = None,
        prompt_config_sha256: str | None = None,
        gpu_seconds: float | None = None,
        peak_memory_gb: float | None = None,
        metrics: dict[str, Any] | None = None,
        status: str = "done",
        notes: str = "",
    ) -> dict[str, Any]:
        entries = self._read()
        existing = {e["experiment_id"] for e in entries}
        if experiment_id in existing:
            raise ValueError(f"experiment_id {experiment_id} already registered; supersede explicitly")
        if route not in ROUTES:
            raise ValueError(f"unknown route {route}; known: {sorted(ROUTES)}")
        entry = {
            "schema": SCHEMA,
            "experiment_id": experiment_id,
            "route": route,
            "route_definition": ROUTES[route],
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": status,
            "data_version": data_version,
            "model_path": model_path,
            "checkpoint_sha256": checkpoint_sha256,
            "params": params or {},
            "prompt_config_sha256": prompt_config_sha256,
            "gpu_seconds": gpu_seconds,
            "peak_memory_gb": peak_memory_gb,
            "metrics": metrics or {},
            "notes": notes,
        }
        entries.append(entry)
        self._write(entries)
        return entry

    def supersede(self, experiment_id: str, reason: str) -> dict[str, Any]:
        entries = self._read()
        for e in entries:
            if e["experiment_id"] == experiment_id:
                e["status"] = "superseded"
                e["notes"] = (e.get("notes", "") + f" | superseded: {reason}").strip(" |")
                self._write(entries)
                return e
        raise KeyError(experiment_id)

    def summary(self) -> dict[str, Any]:
        entries = self._read()
        return {
            "schema": f"{SCHEMA}.summary",
            "total_experiments": len(entries),
            "by_route": {r: sum(1 for e in entries if e["route"] == r) for r in sorted({e["route"] for e in entries})},
            "by_status": {s: sum(1 for e in entries if e["status"] == s) for s in sorted({e["status"] for e in entries})},
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
