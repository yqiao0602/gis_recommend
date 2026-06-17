# -*- coding: utf-8 -*-
"""Convert an alg-id operator chain into a structured workflow JSON.

Produces the standard QGIS-chain output format:
  {task_id, name, description, metadata, processes[{id, algorithm_id,
   inputs/outputs[{id, param_type, required, description}]}], links}

Parameter metadata is sourced from the QGIS official operators file
(operators-json/qgis_operators.json, 1291 ops) — no manual entry needed.
Parameters NEVER carry a 'value' field (the system handles abstract tasks
without concrete data / file paths).

Pure / dependency-injected: callers pass the operator registry dict keyed by
alg-id, or None for fallback.
"""
from __future__ import annotations

from typing import Optional, Sequence


def _param_entry(param_def: dict) -> dict:
    """Convert one parameter definition from the QGIS registry into our schema.

    No 'value' — abstract tasks carry only the structural signature.
    """
    entry: dict = {
        "id": str(param_def.get("name", "")),
    }
    ptype = str(param_def.get("type", "") or "")
    if ptype:
        entry["param_type"] = ptype
    desc = str(param_def.get("description", "") or "")
    if desc:
        entry["description"] = desc
    # optional / required: the registry sometimes uses 'optional', sometimes 'required'
    opt = param_def.get("optional")
    req = param_def.get("required")
    if opt is True or opt == "True":
        entry["required"] = False
    elif opt is False or opt == "False":
        entry["required"] = True
    elif req is False or req == "False":
        entry["required"] = False
    else:
        entry["required"] = True  # default: required
    return entry


def _op_params(alg_id: str, operators: Optional[dict]) -> tuple[list, list]:
    """Lookup inputs / outputs parameter schemas for an alg-id."""
    empty_i, empty_o = [], []
    if not operators:
        return empty_i, empty_o
    info = operators.get(alg_id) or operators.get(alg_id.lower())
    if not info:
        return empty_i, empty_o
    inputs = [_param_entry(p) for p in (info.get("inputs") or [])]
    outputs = [_param_entry(p) for p in (info.get("outputs") or [])]
    return inputs, outputs


def build_workflow_json(
    chain: Sequence[str],
    *,
    task_id: str = "",
    name: str = "",
    description: str = "",
    metadata: Optional[dict] = None,
    operators: Optional[dict] = None,
) -> dict:
    """Build the standard workflow JSON from an alg-id chain.

    ``operators`` is ``{alg_id: {identifier, name, inputs, outputs}}``,
    e.g., the output of ``load_algid_io_types()`` from qgis_operator_registry
    enriched with ``name`` + ``inputs``/``outputs`` parameter lists.
    """
    processes = []
    links = []
    for i, alg_id in enumerate(chain, start=1):
        pid = f"proc_{i}"
        inputs, outputs = _op_params(alg_id, operators)
        processes.append({
            "id": pid,
            "algorithm_id": alg_id,
            "inputs": inputs,
            "outputs": outputs,
        })
        if i > 1:
            prev_output = "OUTPUT"  # convention: default output of previous op
            links.append({
                "source": f"proc_{i - 1}",
                "output": prev_output,
                "target": pid,
                "input": "INPUT",  # convention: default input of next op
            })

    result: dict = {
        "task_id": task_id,
        "name": name,
        "description": description,
        "processes": processes,
        "links": links,
    }
    if metadata:
        result["metadata"] = metadata
    return result


class WorkflowJsonBatchBuilder:
    """Batch-convert chains using a pre-loaded operator registry (lazy, reusable)."""

    def __init__(self, operators: Optional[dict] = None):
        self.operators = operators

    def build(self, task_id: str, chain: Sequence[str], name: str = "",
              description: str = "", metadata: Optional[dict] = None) -> dict:
        return build_workflow_json(chain, task_id=task_id, name=name,
                                   description=description, metadata=metadata,
                                   operators=self.operators)
