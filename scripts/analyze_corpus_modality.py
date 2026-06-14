#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic: modality skew of the L3 training corpus + per task_type lean.

The V4.6 model collapses VECTOR tasks to raster/remote-sensing L3 (Phase A
finding). The task_type vocabulary is 47 THEMATIC earth-science categories with
no vector/raster modality axis — so the model cannot be *told* "do vector". This
script quantifies whether the corpus even contains vector signal, and whether any
thematic task_type leans vector enough to act as a proxy cue.

L3 family by code prefix (L3_<FAM>_..):
  02 -> vector (Buffer, Union, Clip vector, Spatial join, geometry ops)
  03 -> raster / image (Clip Raster, Select Bands, Zonal Stats, Arithmetic, Temporal)
  04 -> terrain/surface (raster DEM derivatives)
  10 -> temporal / image-collection (raster)
  others (01 mgmt, 07 export, ...) -> neutral
Vector-leaning workflow := more L3_02 content tokens than raster (03/04/10).

Usage:
    python scripts/analyze_corpus_modality.py
    python scripts/analyze_corpus_modality.py --top 20
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP8 = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate"
DEFAULT_DATA = STEP8 / "labeled_workflows_l3_v4_quality_gate.json"

_MARKERS = {"<START>", "<END>", "<PAD>", "<UNK>"}
VECTOR_FAMS = {"02"}
RASTER_FAMS = {"03", "04", "10"}


def _family(code: str) -> str:
    parts = code.split("_")
    return parts[1] if len(parts) > 1 else "??"


def _content_codes(wf: dict) -> list:
    return [str(c) for c in (wf.get("l3_codes") or []) if str(c) not in _MARKERS]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    workflows = data.get("labeled_workflows") if isinstance(data, dict) else data

    fam_tokens = Counter()                 # family -> total content tokens
    lean = Counter()                       # vector / raster / mixed / neutral (workflow-level)
    by_tt_n = Counter()                    # task_type -> n workflows
    by_tt_vec = defaultdict(int)           # task_type -> vector-leaning count
    by_tt_ras = defaultdict(int)           # task_type -> raster-leaning count
    by_tt_vtok = defaultdict(int)          # task_type -> vector tokens
    by_tt_rtok = defaultdict(int)          # task_type -> raster tokens

    n = 0
    for wf in workflows:
        codes = _content_codes(wf)
        if not codes:
            continue
        n += 1
        tt = (wf.get("task_metadata", {}) or {}).get(
            "task_type_normalized", (wf.get("task_metadata", {}) or {}).get("task_type", "Unknown"))
        v = r = 0
        for c in codes:
            f = _family(c)
            fam_tokens[f] += 1
            if f in VECTOR_FAMS:
                v += 1
            elif f in RASTER_FAMS:
                r += 1
        by_tt_n[tt] += 1
        by_tt_vtok[tt] += v
        by_tt_rtok[tt] += r
        if v > r:
            lean["vector"] += 1; by_tt_vec[tt] += 1
        elif r > v:
            lean["raster"] += 1; by_tt_ras[tt] += 1
        elif v == r == 0:
            lean["neutral"] += 1
        else:
            lean["mixed"] += 1

    total_tok = sum(fam_tokens.values())
    print(f"=== Corpus modality skew (n={n} workflows) ===\n")
    print("Workflow-level lean (by vector vs raster content tokens):")
    for k in ("vector", "raster", "mixed", "neutral"):
        print(f"  {k:<8} {lean[k]:>6}  ({100*lean[k]/max(n,1):5.1f}%)")

    print("\nL3 family token share (02=vector, 03/04/10=raster):")
    fam_name = {"01": "mgmt", "02": "VECTOR", "03": "raster/image", "04": "terrain",
                "05": "?", "06": "?", "07": "export", "08": "?", "09": "?", "10": "temporal"}
    for f, c in sorted(fam_tokens.items(), key=lambda kv: -kv[1]):
        print(f"  L3_{f}_* {fam_name.get(f,'?'):<13} {c:>8}  ({100*c/max(total_tok,1):5.1f}%)")

    print(f"\n=== Per task_type lean (top {args.top} by n; %vec = vector-leaning workflows) ===")
    print(f"{'task_type':<38} {'n':>5} {'%vec_wf':>8} {'%vec_tok':>9}")
    for tt, cnt in by_tt_n.most_common(args.top):
        vec_wf = 100 * by_tt_vec[tt] / max(cnt, 1)
        tok = by_tt_vtok[tt] + by_tt_rtok[tt]
        vec_tok = 100 * by_tt_vtok[tt] / max(tok, 1)
        print(f"{tt[:37]:<38} {cnt:>5} {vec_wf:>7.1f}% {vec_tok:>8.1f}%")

    # highlight any vector-leaning task_type
    vec_types = [(tt, by_tt_vec[tt] / max(by_tt_n[tt], 1)) for tt in by_tt_n
                 if by_tt_vec[tt] / max(by_tt_n[tt], 1) >= 0.5 and by_tt_n[tt] >= 20]
    print(f"\nTask_types that are >=50% vector-leaning (n>=20): "
          f"{sorted(vec_types, key=lambda x:-x[1]) if vec_types else 'NONE'}")


if __name__ == "__main__":
    main()
