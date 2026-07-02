"""Load environment configuration from a .env file.

Usage (call once at application startup)::

    from gis_recommend.config.env import load_env
    load_env()                        # looks for .env in project root
    load_env(".env.production")       # explicit path

``load_env`` is idempotent — it never overwrites an already-set
environment variable, so shell-exported values always win.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_project_root() -> Path:
    """Find the project root by looking for .env.example or src/gis_recommend."""
    # Walk up from this file's location
    current = Path(__file__).resolve().parent  # .../src/gis_recommend/config
    for _ in range(5):
        if (current / ".env.example").exists():
            return current
        if (current / "src" / "gis_recommend").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()


def load_env(path: str | Path | None = None) -> dict[str, str]:
    """Load key=value pairs from a ``.env`` file into ``os.environ``.

    - Lines starting with ``#`` are ignored.
    - Blank lines are ignored.
    - Values are stripped of surrounding quotes.
    - Variables already present in ``os.environ`` are **never** overwritten.

    Args:
        path: Path to the env file.  Defaults to ``<project_root>/.env``.

    Returns:
        dict of the variables that were actually loaded (only newly set ones).
    """
    if path is None:
        root = _find_project_root()
        path = root / ".env"
    else:
        path = Path(path)

    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")

            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value

    return loaded
