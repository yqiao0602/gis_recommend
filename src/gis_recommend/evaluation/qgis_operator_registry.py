# -*- coding: utf-8 -*-
"""Alg-ID-keyed QGIS operator I/O registry, built from the official operators file.

The canonical ``operators-json/qgis_operators.json`` (1291 ops) carries, per
operator, both ``identifier`` (alg ID, e.g. ``native:buffer``) and ``name``
(display name), plus parameter-level ``inputs``/``outputs``. This module re-keys
that registry by alg ID and normalizes I/O types to {vector, raster}.

Why: real QGIS chains (open_landing) and external LLMs (GPT-4o) speak alg IDs,
while the legacy ``qgis_operator_io_types.json`` is keyed by display name. Keying
by alg ID gives the single common namespace for system-agnostic scoring — and it
is built statically from this file, with no Neo4j dependency.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence


def _normalize_type(t) -> set:
    """Map a raw QGIS parameter type to spatial-data classes {vector, raster}.

    Non-spatial parameters (LiteralData, scalars, MIME blobs) map to {} — they
    are not data-layer flow and must not affect I/O compatibility.
    """
    t = (str(t) if t is not None else "").strip().lower()
    if t == "vector":
        return {"vector"}
    if t in ("raster", "image/tiff"):
        return {"raster"}
    if t == "geographicdata":
        return {"vector", "raster"}  # generic spatial: compatible with either
    return set()


def _normalize_params(params) -> list:
    out: set = set()
    for p in params or []:
        raw = p.get("type") if isinstance(p, dict) else None
        out |= _normalize_type(raw)
    return sorted(out)


def build_algid_io_types(operators: Sequence[dict]) -> dict:
    """Re-key official operator entries by alg ID with normalized I/O types."""
    io: dict = {}
    for op in operators or []:
        alg_id = (op.get("identifier") or "").strip()
        if not alg_id:
            continue
        io[alg_id] = {
            "inputs": _normalize_params(op.get("inputs")),
            "outputs": _normalize_params(op.get("outputs")),
            "name": op.get("name", ""),
        }
    return io


# operators-json lives one level above the repo root (Algorithm_classification/).
DEFAULT_OPERATORS_PATH = (
    Path(__file__).resolve().parents[4] / "operators-json" / "qgis_operators.json"
)


def load_algid_io_types(path: Optional[Path] = None) -> dict:
    """Load the official operators file and build the alg-ID I/O registry."""
    path = Path(path) if path else DEFAULT_OPERATORS_PATH
    with open(path, "r", encoding="utf-8") as f:
        operators = json.load(f)
    return build_algid_io_types(operators)
