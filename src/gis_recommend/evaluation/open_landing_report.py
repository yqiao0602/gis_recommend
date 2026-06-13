# -*- coding: utf-8 -*-
"""Open-landing evaluation report: parse graded chains, score, break down.

Turns the manually graded ``open_landing_results.csv`` (task description,
TASK-INTENT modality vec/rast/mixed, the system's top-1 QGIS alg-id chain, and a
human A/B/C grade) into a fixed diagnostic report:

  - overall + per task-intent-modality ①② scores (where is the system weak?)
  - per human-grade ①② scores (do ①② track correctness? — empirically NO)
  - chain diversity per modality (quantifies template collapse: how many
    distinct top-1 chains the system actually produces)

Pure / dependency-injected: scoring uses an injected alg-id ``io_types`` registry
(see qgis_operator_registry). No Neo4j, no model, no global state.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from gis_recommend.evaluation.qgis_chain_metrics import (
    score_chain_records,
    aggregate_by,
)


def parse_open_landing_csv(path) -> list:
    """Parse the graded open-landing CSV into scoring items.

    Each row -> ``{task_id, task, predicted_chain, modality, grade}`` where
    ``predicted_chain`` is ``top1_ops`` split on ' -> ' and ``modality`` is the
    TASK-INTENT column (vec/rast/mixed), not derived from the chain.
    """
    items = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            raw_ops = (row.get("top1_ops") or "").strip()
            chain = [op.strip() for op in raw_ops.split("->") if op.strip()]
            items.append({
                "task_id": f"ol{idx:03d}",
                "task": (row.get("task") or "").strip(),
                "predicted_chain": chain,
                "modality": (row.get("modality") or "").strip(),
                "grade": (row.get("grade") or "").strip(),
            })
    return items


def chain_diversity(records: Sequence[dict], key: str) -> dict:
    """How many DISTINCT top-1 chains the system emits, per group.

    Each record carries ``predicted_chain`` (list) and the grouping ``key``.
    Returns ``{value: {n, unique, unique_ratio}}``. A low unique_ratio is the
    signature of TEMPLATE COLLAPSE — many distinct tasks mapped to one chain.
    """
    groups: dict = defaultdict(list)
    for r in records:
        groups[r.get(key, "unknown")].append(tuple(r.get("predicted_chain") or []))
    out = {}
    for value, chains in groups.items():
        n = len(chains)
        unique = len(set(chains))
        out[value] = {
            "n": n,
            "unique": unique,
            "unique_ratio": unique / n if n else 0.0,
        }
    return out


def build_report(items: Sequence[dict], io_types: dict) -> dict:
    """Score graded open-landing items into a fixed diagnostic report.

    ``items`` come from :func:`parse_open_landing_csv` (each carries
    predicted_chain, task-intent modality, grade). The task-intent modality is
    preserved through scoring (not re-derived from the chain). Returns:

      n, overall, by_modality, by_grade, diversity_by_modality
    """
    records = score_chain_records(items, io_types=io_types)
    # carry human grade + the chain itself back onto each scored record
    for rec, it in zip(records, items):
        rec["grade"] = it.get("grade")
        rec["predicted_chain"] = it.get("predicted_chain")

    by_mod = aggregate_by(records, "modality")
    by_grade = aggregate_by(records, "grade")
    return {
        "n": len(records),
        "overall": by_mod["overall"],
        "by_modality": by_mod["groups"],
        "by_grade": by_grade["groups"],
        "diversity_by_modality": chain_diversity(records, "modality"),
    }


_MOD_ORDER = ["vec", "rast", "mixed"]
_GRADE_ORDER = ["A", "B", "C", "D"]


def _fmt(v) -> str:
    return f"{v:.3f}" if isinstance(v, (int, float)) else "—"


def _ordered(keys, preferred) -> list:
    keys = list(keys)
    pref = [k for k in preferred if k in keys]
    rest = sorted(k for k in keys if k not in preferred)
    return pref + rest


def _agg_row(label, a) -> str:
    return (
        f"| {label} | {a.get('n', 0)} | {_fmt(a.get('operator_validity'))} "
        f"| {_fmt(a.get('io_executability'))} | {_fmt(a.get('executable_rate'))} "
        f"| {_fmt(a.get('operator_set_f1'))} |"
    )


def render_markdown(report: dict) -> str:
    """Render the diagnostic report as a self-explanatory Markdown document."""
    o = report["overall"]
    L = []
    L.append("# Open-Landing QGIS Chain Evaluation")
    L.append("")
    L.append(
        f"System top-1 QGIS chains scored against the QGIS operator registry "
        f"(alg-id namespace, Neo4j-free). n={report['n']}."
    )
    L.append("")
    L.append(
        "Axes — ① **operator_validity**: real ops / total (anti-hallucination); "
        "② **io_executability**: adjacent op-pair I/O type compatibility; "
        "**executable**: ①=②=1; ③ **operator_set_f1**: multiset overlap vs a "
        "reference chain, order-invariant (— when no reference exists yet)."
    )
    L.append("")

    L.append("## Overall")
    L.append("")
    L.append("| | n | ① validity | ② io_exec | executable | ③ set_f1 |")
    L.append("|---|--:|--:|--:|--:|--:|")
    L.append(_agg_row("overall", o))
    L.append("")

    L.append("## By task modality (task-intent: vec / rast / mixed)")
    L.append("")
    L.append(
        "Where the system is weak. Mixed (raster↔vector) chains are where I/O "
        "type breaks concentrate."
    )
    L.append("")
    L.append("| modality | n | ① validity | ② io_exec | executable | ③ set_f1 |")
    L.append("|---|--:|--:|--:|--:|--:|")
    for m in _ordered(report["by_modality"], _MOD_ORDER):
        L.append(_agg_row(m or "(none)", report["by_modality"][m]))
    L.append("")

    L.append("## By human grade (A best → C worst)")
    L.append("")
    L.append(
        "**Probe: do ①② track human-judged correctness?** If validity / "
        "executable do NOT fall monotonically A→C, then ①② measure "
        "*runnability / grounding*, not *correctness* — and ③ (references) + ④ "
        "(human / task-success) are required to measure whether the task was "
        "actually solved."
    )
    L.append("")
    L.append("| grade | n | ① validity | ② io_exec | executable | ③ set_f1 |")
    L.append("|---|--:|--:|--:|--:|--:|")
    for g in _ordered(report["by_grade"], _GRADE_ORDER):
        L.append(_agg_row(g or "(ungraded)", report["by_grade"][g]))
    L.append("")

    L.append("## Chain diversity (template-collapse signature)")
    L.append("")
    L.append(
        "unique_ratio = distinct top-1 chains / tasks. A low ratio means the "
        "system collapses many distinct tasks onto one template — executable "
        "but task-agnostic, the mechanism behind 'executable ≠ correct'."
    )
    L.append("")
    L.append("| modality | n | unique chains | unique_ratio |")
    L.append("|---|--:|--:|--:|")
    div = report["diversity_by_modality"]
    for m in _ordered(div, _MOD_ORDER):
        d = div[m]
        L.append(f"| {m or '(none)'} | {d['n']} | {d['unique']} | {_fmt(d['unique_ratio'])} |")
    L.append("")
    return "\n".join(L)
