# -*- coding: utf-8 -*-
"""Runtime consistency checks for the active data/vocab/model contract.

Pure, dependency-injected validation: callers pass the resolved asset paths and
the active vocab sizes; this module loads only those assets and reports
inconsistencies. It NEVER mutates state and NEVER decides to raise — the caller
chooses whether a report is advisory (warn-only) or fatal.

Motivation: VOCAB_SIZE, the data root, the id_mappings, and the transition
matrix are resolved independently elsewhere with no cross-check, so a 94-vocab
model can be silently paired with 350-L3 assets. This module makes that
mismatch observable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConsistencyIssue:
    code: str
    severity: str  # "error" | "warning"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class ConsistencyReport:
    issues: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def check_runtime_consistency(
    *,
    vocab_size: int,
    total_vocab_size: int,
    id_mappings_path,
    transition_matrix_path=None,
) -> ConsistencyReport:
    issues: list[ConsistencyIssue] = []

    id_mappings_path = Path(id_mappings_path)
    if not id_mappings_path.exists():
        issues.append(ConsistencyIssue(
            code="id_mappings_missing",
            severity="error",
            message=f"id_mappings file not found: {id_mappings_path}",
            details={"id_mappings_path": str(id_mappings_path)},
        ))
    else:
        data = json.loads(id_mappings_path.read_text(encoding="utf-8"))
        l3_count = len(data.get("l3", {}))
        if l3_count != vocab_size:
            issues.append(ConsistencyIssue(
                code="vocab_count_mismatch",
                severity="error",
                message=(
                    f"id_mappings declares {l3_count} L3 codes but VOCAB_SIZE={vocab_size}"
                ),
                details={"l3_count": l3_count, "vocab_size": vocab_size,
                         "id_mappings_path": str(id_mappings_path)},
            ))

    if transition_matrix_path is not None:
        transition_matrix_path = Path(transition_matrix_path)
        if not transition_matrix_path.exists():
            issues.append(ConsistencyIssue(
                code="transition_matrix_missing",
                severity="warning",
                message=f"transition matrix not found (decoding will be unconstrained): {transition_matrix_path}",
                details={"transition_matrix_path": str(transition_matrix_path)},
            ))
        else:
            tdata = json.loads(transition_matrix_path.read_text(encoding="utf-8"))
            out_of_range = set()
            for a_str, nxt in tdata.get("allowed_next", {}).items():
                for tok in [a_str, *nxt.keys()]:
                    t = int(tok)
                    if t < 0 or t >= total_vocab_size:
                        out_of_range.add(t)
            if out_of_range:
                issues.append(ConsistencyIssue(
                    code="transition_token_out_of_range",
                    severity="error",
                    message=(
                        f"transition matrix contains {len(out_of_range)} token id(s) "
                        f"outside the valid range [0, {total_vocab_size})"
                    ),
                    details={"out_of_range_tokens": sorted(out_of_range),
                             "total_vocab_size": total_vocab_size,
                             "transition_matrix_path": str(transition_matrix_path)},
                ))

    return ConsistencyReport(issues=issues)
