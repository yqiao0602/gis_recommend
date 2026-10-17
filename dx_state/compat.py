"""Single compatibility seam to the flat-script DX recorder.

dx_recorder_v1.py lives in scripts/ as a flat module (no package); every
dx_state module that needs verify_item loads it through this loader so the
dependency edge stays in exactly one place.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_RECORDER = _REPO / "scripts" / "dx_recorder_v1.py"

_loaded = None


def load_recorder():
    """Return the dx_recorder_v1 module (loaded once per process)."""
    global _loaded
    if _loaded is None:
        spec = importlib.util.spec_from_file_location("dx_recorder_v1", _RECORDER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded = module
    return _loaded
