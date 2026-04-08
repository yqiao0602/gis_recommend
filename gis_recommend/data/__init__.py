# -*- coding: utf-8 -*-
"""Shared utilities for the data processing pipeline."""

from pathlib import Path


def get_project_root() -> Path:
    """Return the project root (directory containing ``outputs/``)."""
    p = Path(__file__).resolve()
    for parent in (p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent):
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


def get_pipeline_output_dir() -> Path:
    """Return ``outputs/pipeline/`` and create it if needed."""
    d = get_project_root() / "outputs" / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_step_output_dir(step: int) -> Path:
    """Return ``outputs/pipeline/stepN/`` and create it if needed."""
    d = get_pipeline_output_dir() / f"step{step}"
    d.mkdir(parents=True, exist_ok=True)
    return d
