#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch-convert QGIS chains to the standard workflow JSON format.

Reads a jsonl of chains (e.g. qgis_complete_ALL.jsonl, vector_training_samples_v2.jsonl),
loads the QGIS operator registry (operators-json/qgis_operators.json) for parameter
metadata, and writes one standard workflow JSON per chain, with:
  - task_id, name, description (from the source)
  - metadata (platform, task_type)
  - processes[{id, algorithm_id, inputs/outputs[{id,param_type,required,description}]}]
  - links[{source,output,target,input}]

Parameters: NO 'value' field — abstract tasks carry only the structural signature.
Descriptions: QGIS official original text (English), auto-sourced from the registry.

Usage:
    python scripts/build_workflow_jsons.py
    python scripts/build_workflow_jsons.py --chains ... --out-dir ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.evaluation.qgis_operator_registry import build_algid_io_types
from gis_recommend.evaluation.workflow_json_builder import build_workflow_json

OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
DEFAULT_CHAINS = ROOT / "outputs_v2" / "diagnostics" / "qgis_complete_ALL.jsonl"
DEFAULT_OUT_DIR = ROOT / "outputs_v2" / "diagnostics" / "workflow_jsons"


def load_full_registry(path: Path) -> dict:
    """Load {alg_id: {identifier, name, inputs, outputs}} with full param schema."""
    ops = json.loads(path.read_text(encoding="utf-8"))
    registry = {}
    for op in ops:
        alg_id = (op.get("identifier") or "").strip()
        if not alg_id:
            continue
        registry[alg_id] = op  # keep the full entry (inputs/outputs lists of {name,type,optional,description})
    return registry


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chains", type=Path, default=DEFAULT_CHAINS)
    ap.add_argument("--operators", type=Path, default=OFFICIAL_OPS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()

    registry = load_full_registry(args.operators)
    print(f"registry: {len(registry)} operators with full param schemas")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(args.chains, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            chain = rec.get("chain", []) or rec.get("qgis_ops", [])
            if not chain:
                continue
            task_id = rec.get("task_id") or rec.get("script") or f"wf_{n:04d}"
            name = rec.get("task_name") or rec.get("name") or ""
            desc = rec.get("task_description") or rec.get("description") or ""
            tt = rec.get("task_type") or ""
            wf = build_workflow_json(chain, task_id=str(task_id), name=name, description=desc,
                                     operators=registry,
                                     metadata={"platform": "QGIS", "task_type": tt} if tt else None)
            out_path = args.out_dir / f"{task_id}.json"
            out_path.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
            n += 1
            if args.max and n >= args.max:
                break

    print(f"wrote {n} workflow JSONs -> {args.out_dir}")
    if n > 0:
        ex_path = args.out_dir / f"{json.loads(open(args.chains,encoding='utf-8').readline())['script']}.json"
        ex_str = ex_path.read_text(encoding="utf-8")[:600]
        print(f"example ({ex_path.name}):\n{ex_str}...")


if __name__ == "__main__":
    main()
