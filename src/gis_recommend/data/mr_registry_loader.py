"""Load the verified MR registry v2 and build a task-key lookup.

Read-only: does not mutate the registry, training labels, or checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence


def _make_task_key(
    task_type: str = "",
    task_name: str = "",
    task_description: str = "",
) -> str:
    return json.dumps(
        {
            "task_type": task_type or "",
            "task_name": task_name or "",
            "task_description": task_description or "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def load_mr_registry(path: Optional[Path] = None) -> dict[str, dict]:
    """Return {task_key: {references: [[tokens], ...]}} from registry v2 JSON."""
    if path is None:
        path = (
            Path(__file__).resolve().parents[3]
            / "outputs_v2"
            / "v4_qg_multiref_validation"
            / "verified_multi_reference_registry_v2.json"
        )
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    lookup: dict[str, dict] = {}
    for entry in raw.get("entries", []):
        key = _make_task_key(
            entry.get("task_type", ""),
            entry.get("task_name", ""),
            entry.get("task_description", ""),
        )
        references = entry.get("references", [])
        if len(references) > 1:
            lookup[key] = {"references": references}
    return lookup
