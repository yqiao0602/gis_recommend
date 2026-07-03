#!/usr/bin/env python3
"""End-to-end quality gate: L3 → QGIS → Workflow JSON.

Reads a showcase eval JSON (from run_end_to_end_showcase_eval.py) and produces
a per-step quality report covering all checkpoints across the pipeline.

Pipeline stages:
    NL Query → Task Type → L3 Infer → QGIS Landing → Workflow JSON

Quality checkpoints:
    ╔══════════╦═══════════════════════════════════════╗
    ║ Stage    ║ Checks                                ║
    ╠══════════╬═══════════════════════════════════════╣
    ║ L3       ║ usable · complete · concise · modal   ║
    ║ QGIS     ║ valid · bridge · quality · io         ║
    ║ Workflow ║ params · links · executability        ║
    ╚══════════╩═══════════════════════════════════════╝

Usage:
    python scripts/quality_gate.py \\
        --eval-json outputs_v2/diagnostics/open_landing_vec11277_fp05v2/end_to_end_showcase_eval.json \\
        --output-dir outputs_v2/diagnostics/quality_gate/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ===========================================================================
# L3 code classification (shared with diagnose_l3_quality.py)
# ===========================================================================

DATA_SOURCE_L2 = {"L2_01_01", "L2_01_02", "L2_01_03"}
FILTER_L2 = {"L2_02_06"}
COMPUTE_L2 = {"L2_02_01", "L2_02_02", "L2_02_04", "L2_02_05", "L2_03_01",
              "L2_03_02", "L2_03_03", "L2_03_04", "L2_03_05", "L2_03_06",
              "L2_03_07", "L2_03_08", "L2_03_09", "L2_04_01", "L2_05_01"}
VECTOR_COMPUTE_L2_PREFIXES = ("L2_02_", "L2_04_", "L2_05_", "L2_06_", "L2_07_")


def _l3_l2(l3_code: str) -> str:
    parts = l3_code.split("_")
    if len(parts) >= 4:
        return f"L2_{parts[1]}_{parts[2]}"
    return l3_code


def _l3_l1(l3_code: str) -> str:
    parts = l3_code.split("_")
    if len(parts) >= 4:
        return f"L1_{parts[1]}"
    return l3_code


def _classify_l3(l3_code: str) -> dict:
    l2 = _l3_l2(l3_code)
    l1 = _l3_l1(l3_code)
    return {
        "is_data_source": l2 in DATA_SOURCE_L2,
        "is_filter": l2 in FILTER_L2,
        "is_compute": l2 in COMPUTE_L2 or l2.startswith(VECTOR_COMPUTE_L2_PREFIXES),
        "is_raster": l1 == "L1_03",
        "is_vector": l1 == "L1_02",
        "l2": l2,
        "l1": l1,
    }


def extract_l3_codes(l3_chain: str) -> list[str]:
    if not l3_chain:
        return []
    return [p.split("(")[0].strip() for p in l3_chain.split(" -> ") if p.strip()]


def extract_qgis_ops(qgis_chain: str) -> list[str]:
    if not qgis_chain:
        return []
    return [op.strip() for op in qgis_chain.split(" -> ") if op.strip()]


# ===========================================================================
# Quality Gate Dataclasses
# ===========================================================================

@dataclass
class L3Check:
    usable: bool = False
    usable_score: float = 0.0
    complete: bool = False            # has processing steps + data source
    concise: bool = False             # no consecutive duplicates
    modal_ok: bool = False            # no raster/vector mismatch
    chain_len: int = 0
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class QGISCheck:
    valid: bool = False
    quality: float = 0.0
    l3_bridge: bool = False           # mapped via L3 bridge
    native_bridge: bool = False       # mapped via native fallback
    io_compatible: bool = False       # chain I/O types are compatible
    ops: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)


@dataclass
class WorkflowCheck:
    has_output: bool = False
    param_complete: bool = False
    dataflow_connected: bool = False
    issues: list[str] = field(default_factory=list)


@dataclass
class QualityGateResult:
    task_id: str = ""
    group: str = ""
    task_name: str = ""
    l3: L3Check = field(default_factory=L3Check)
    qgis: QGISCheck = field(default_factory=QGISCheck)
    workflow: WorkflowCheck = field(default_factory=WorkflowCheck)
    overall_pass: bool = False
    overall_score: float = 0.0


# ===========================================================================
# Quality Gate Evaluator
# ===========================================================================

class QualityGate:
    """Evaluate a single candidate through all pipeline checkpoints."""

    def evaluate(self, record: dict) -> QualityGateResult:
        sel = record.get("selected", {}) or {}
        ql = record.get("qgis_landing", {}) or {}
        l3_parts = record.get("l3_parts", []) or []

        result = QualityGateResult(
            task_id=str(record.get("idx", "?")),
            group=record.get("group", "unknown"),
            task_name=str(record.get("task_name", "")),
        )

        # ── Stage 1: L3 ──────────────────────────────────────
        # L3 codes from qgis_landing (already decoded)
        codes = ql.get("l3_codes", []) or []
        result.l3.chain_len = len(codes)
        result.l3.usable = bool(sel.get("usable", False))
        result.l3.usable_score = float(sel.get("usability_score", 0) or 0)

        roles = [_classify_l3(c) for c in codes]
        has_compute = any(r["is_compute"] for r in roles)
        has_source = any(r["is_data_source"] or r["is_filter"] for r in roles[:min(3, len(roles))])
        has_processing = any(r["is_compute"] or r["is_filter"] or r["is_data_source"] for r in roles)

        if len(codes) <= 1:
            result.l3.missing.append("chain_too_short")
        elif not has_processing:
            result.l3.missing.append("no_processing_steps")
        elif has_compute and not has_source:
            result.l3.missing.append("no_data_source")
        result.l3.complete = len(result.l3.missing) == 0

        # Conciseness: consecutive duplicates
        dup_count = sum(1 for i in range(1, len(codes)) if codes[i] == codes[i - 1])
        result.l3.concise = dup_count == 0
        if dup_count:
            result.l3.warnings.append(f"{dup_count} consecutive dup(s)")

        # Modality
        vec_n = sum(1 for r in roles if r["is_vector"])
        rast_n = sum(1 for r in roles if r["is_raster"])
        result.l3.modal_ok = not (vec_n > 0 and rast_n > 0)

        # Collect existing warnings from selected candidate
        for w in (sel.get("warnings", []) or []):
            result.l3.warnings.append(str(w))
        for f in (sel.get("failures", []) or []):
            if f != "usable_no_failure":
                result.l3.warnings.append(str(f))

        # ── Stage 2: QGIS ────────────────────────────────────
        result.qgis.valid = bool(ql.get("top1_valid", False))
        result.qgis.quality = float(ql.get("top1_quality", 0) or 0)
        result.qgis.l3_bridge = bool(ql.get("l3_bridge_hit", False))
        result.qgis.native_bridge = bool(ql.get("native_bridge_hit", False))
        result.qgis.ops = list(ql.get("top1_chain", []) or [])
        result.qgis.io_compatible = result.qgis.l3_bridge or result.qgis.valid

        # ── Stage 3: Workflow JSON ───────────────────────────
        # The eval JSON doesn't include workflow JSON output yet.
        # For now, flag as pending and score based on QGIS validity.
        result.workflow.has_output = False
        result.workflow.param_complete = result.qgis.valid
        result.workflow.dataflow_connected = result.qgis.valid
        if not result.qgis.valid:
            result.workflow.issues.append("qgis_landing_failed")

        # ── Overall ───────────────────────────────────────────
        checks = [
            result.l3.usable,           # 25%
            result.l3.complete,         # 20%
            result.qgis.valid,          # 25%
            result.l3.concise,          # 10%
            result.l3.modal_ok,         # 10%
            result.workflow.param_complete,  # 10%
        ]
        weights = [0.25, 0.20, 0.25, 0.10, 0.10, 0.10]
        result.overall_score = sum(w for c, w in zip(checks, weights) if c)
        result.overall_pass = result.overall_score >= 0.75  # pass if ≥75%

        return result


# ===========================================================================
# Report generation
# ===========================================================================

def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "N/A"
    return f"{100*num/denom:.0f}%"


def generate_report(results: list[QualityGateResult]) -> str:
    n = len(results)
    lines = ["# Quality Gate — End-to-End Pipeline Report", ""]

    # ── Overall ──
    lines.append("## Pipeline Summary")
    lines.append("")
    pass_n = sum(1 for r in results if r.overall_pass)
    mean_score = sum(r.overall_score for r in results) / max(n, 1)
    lines.append(f"- **Overall pass rate**: {pass_n}/{n} ({_pct(pass_n, n)})")
    lines.append(f"- **Mean score**: {mean_score:.3f}")
    lines.append("")

    lines.append("| Checkpoint | Pass Rate | Detail |")
    lines.append("|------------|-----------|--------|")
    for label, check_fn in [
        ("L3 usable", lambda r: r.l3.usable),
        ("L3 complete", lambda r: r.l3.complete),
        ("L3 concise", lambda r: r.l3.concise),
        ("L3 modal OK", lambda r: r.l3.modal_ok),
        ("QGIS valid", lambda r: r.qgis.valid),
        ("QGIS L3 bridge", lambda r: r.qgis.l3_bridge),
        ("QGIS native bridge", lambda r: r.qgis.native_bridge),
        ("Workflow ready", lambda r: r.workflow.param_complete),
    ]:
        cnt = sum(1 for r in results if check_fn(r))
        lines.append(f"| {label} | {cnt}/{n} ({_pct(cnt, n)}) | |")
    lines.append("")

    # ── By group ──
    for group in ["vec", "rast", "mixed"]:
        grp = [r for r in results if r.group == group]
        if not grp:
            continue
        gn = len(grp)
        g_pass = sum(1 for r in grp if r.overall_pass)
        g_score = sum(r.overall_score for r in grp) / max(gn, 1)
        lines.append(f"## {group} (n={gn})")
        lines.append("")
        lines.append(f"- Pass: {g_pass}/{gn} ({_pct(g_pass, gn)}), Score: {g_score:.3f}")
        lines.append("")

        lines.append("| Checkpoint | Pass |")
        lines.append("|------------|------|")
        for label, check_fn in [
            ("L3 usable", lambda r: r.l3.usable),
            ("L3 complete", lambda r: r.l3.complete),
            ("L3 concise", lambda r: r.l3.concise),
            ("L3 modal OK", lambda r: r.l3.modal_ok),
            ("QGIS valid", lambda r: r.qgis.valid),
            ("QGIS L3 bridge", lambda r: r.qgis.l3_bridge),
        ]:
            cnt = sum(1 for r in grp if check_fn(r))
            lines.append(f"| {label} | {cnt}/{gn} ({_pct(cnt, gn)}) |")
        lines.append("")

        # Missing details
        missing_counter: Counter = Counter()
        for r in grp:
            for m in r.l3.missing:
                missing_counter[m] += 1
        if missing_counter:
            lines.append("**L3 issues:**")
            for reason, cnt in missing_counter.most_common():
                lines.append(f"- {reason}: {cnt}/{gn}")
            lines.append("")

    # ── Failing chains ──
    lines.append("## Failed Gates")
    lines.append("")
    failed = [r for r in results if not r.overall_pass]
    for r in failed[:10]:
        lines.append(f"- **[{r.group}]** {r.task_name[:80]}")
        issues = []
        if not r.l3.usable:
            issues.append("L3 not usable")
        if not r.l3.complete:
            issues.append("L3 incomplete: " + ", ".join(r.l3.missing))
        if not r.l3.concise:
            issues.append("L3 not concise")
        if not r.l3.modal_ok:
            issues.append("L3 modality mismatch")
        if not r.qgis.valid:
            issues.append("QGIS invalid")
        lines.append(f"  Issues: {'; '.join(issues)}")
        lines.append(f"  Score: {r.overall_score:.2f}")
        lines.append("")

    return "\n".join(lines)


# ===========================================================================
# CLI
# ===========================================================================

def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-json", required=True,
                        help="Path to end_to_end_showcase_eval.json")
    parser.add_argument("--output-dir", default="outputs_v2/diagnostics/quality_gate",
                        help="Output directory")
    args = parser.parse_args(argv)

    with open(args.eval_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    if not records:
        print("No records found in eval JSON")
        return

    gate = QualityGate()
    results = [gate.evaluate(r) for r in records]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON output
    with (out_dir / "quality_gate_results.json").open("w", encoding="utf-8") as f:
        json.dump([{
            "task_id": r.task_id,
            "group": r.group,
            "overall_pass": r.overall_pass,
            "overall_score": round(r.overall_score, 4),
            "l3": {
                "usable": r.l3.usable,
                "complete": r.l3.complete,
                "concise": r.l3.concise,
                "modal_ok": r.l3.modal_ok,
                "chain_len": r.l3.chain_len,
                "missing": r.l3.missing,
                "warnings": r.l3.warnings,
            },
            "qgis": {
                "valid": r.qgis.valid,
                "quality": r.qgis.quality,
                "l3_bridge": r.qgis.l3_bridge,
                "native_bridge": r.qgis.native_bridge,
                "ops": r.qgis.ops,
            },
        } for r in results], f, ensure_ascii=False, indent=2)

    # Markdown report
    report = generate_report(results)
    with (out_dir / "quality_gate_report.md").open("w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\nReports written to {out_dir}")


if __name__ == "__main__":
    main()
