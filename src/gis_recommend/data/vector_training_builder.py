# -*- coding: utf-8 -*-
"""Convert described QGIS vector chains into L3 training samples.

Bridges the QGIS landing corpus (vector chains that carry an
``optional_l3_sequence``) into the labeled_workflows schema the L3 transformer
trains on, so vector workflows can be added to a corpus that is currently 99.3%
raster (the root cause of V4.6's vector->raster collapse).

Pure / dependency-injected: callers pass the L3 ``code_to_id`` map and special
tokens (from l3_vocab_v2.json) and the task_type vocabulary. No I/O, no globals.
"""
from __future__ import annotations

from typing import Optional, Sequence


def _derive_task_name(description: str, operator_names: Sequence[str]) -> str:
    desc = (description or "").strip()
    if desc:
        words = desc.split()
        return " ".join(words[:8])
    names = [n for n in (operator_names or []) if n]
    return " + ".join(names[:3]) if names else "QGIS vector workflow"


def to_training_sample(
    described: dict,
    *,
    code_to_id: dict,
    special_tokens: dict,
    task_type: str,
    task_type_to_id: dict,
) -> Optional[dict]:
    """Turn one described vector chain into a labeled_workflows-schema sample.

    Returns None (drop) if the chain has no L3 sequence or any L3 code is out of
    the 94-code vocabulary — keep training data clean rather than inject <UNK>.
    """
    codes = [str(c) for c in (described.get("optional_l3_sequence") or [])]
    if not codes:
        return None
    ids = []
    for c in codes:
        if c not in code_to_id:
            return None  # out-of-vocab L3 code -> not clean training data
        ids.append(int(code_to_id[c]))

    start, end = special_tokens["<START>"], special_tokens["<END>"]
    description = (described.get("task_description_en") or "").strip()
    qgis_ops = list(described.get("qgis_ops") or [])

    return {
        "l3_sequence": [start] + ids + [end],
        "l3_codes": ["<START>"] + codes + ["<END>"],
        "operator_sequence": qgis_ops,
        "task_metadata": {
            "task_type": task_type,
            "task_name": _derive_task_name(description, described.get("operator_names") or []),
            "task_description": description,
        },
        "source": "qgis_vector_augment",
        "source_original": described.get("source", ""),
        # carry task_type id resolution responsibility to the trainer (matches
        # labeled_workflows, which stores the string and maps at train time)
        "_task_type_id_hint": int(task_type_to_id.get(task_type, 0)),
    }
