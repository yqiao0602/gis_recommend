# -*- coding: utf-8 -*-
"""Shared utilities for the data processing pipeline."""

import os
from pathlib import Path


OUTPUTS_DIR_ENV = "GIS_OUTPUTS_DIR"


def get_project_root() -> Path:
    """Return the project root (directory containing outputs data)."""
    p = Path(__file__).resolve()
    for parent in (p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent):
        if (parent / "outputs_v2").is_dir() or (parent / "outputs").is_dir():
            return parent
    return p.parent


def resolve_under_project(path) -> Path:
    """Resolve a user/env path relative to the project root when needed."""
    p = Path(path)
    if p.is_absolute():
        return p
    return get_project_root() / p


def get_outputs_dir(outputs_dir=None) -> Path:
    """Return the active outputs root.

    The default is ``outputs_v2/``. Set ``GIS_OUTPUTS_DIR=outputs`` or pass
    ``outputs_dir`` explicitly for legacy runs.
    """
    configured = outputs_dir or os.environ.get(OUTPUTS_DIR_ENV) or "outputs_v2"
    d = resolve_under_project(configured)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_pipeline_output_dir(outputs_dir=None) -> Path:
    """Return ``<outputs_dir>/pipeline/`` and create it if needed."""
    d = get_outputs_dir(outputs_dir) / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_step_output_dir(step: int, outputs_dir=None) -> Path:
    """Return ``<outputs_dir>/pipeline/stepN/`` and create it if needed."""
    d = get_pipeline_output_dir(outputs_dir) / f"step{step}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_default_id_mappings_path(outputs_dir=None) -> Path:
    """Return the v2 id mappings file for the active outputs root (94-L3).

    The legacy 350-L3 ``id_mappings.json`` fallback is retired.
    """
    return get_outputs_dir(outputs_dir) / "id_mappings_v2.json"


def get_default_gee_skip_list_path(outputs_dir=None) -> Path | None:
    """Return the GEE skip list for the active outputs root, if present."""
    outputs_root = get_outputs_dir(outputs_dir)
    candidates = [
        outputs_root / "gee_skip_list_v2.json",
        outputs_root / "gee_skip_list.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
