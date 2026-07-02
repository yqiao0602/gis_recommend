#!/usr/bin/env python3
"""L3 chain quality diagnostic: multi-dimensional assessment report.

Reads a showcase eval CSV (from run_end_to_end_showcase_eval.py) and
produces a per-dimension quality report:

    ① 可用性 (usable)      — I/O constraint passing rate
    ② 可执行性 (executable)  — QGIS landing rate
    ③ 正确性 (correctness)   — SetF1 vs gold-standard (if references provided)
    ④ 完整性 (completeness)  — critical-step coverage per task_type  🆕
    ⑤ 简洁性 (conciseness)   — redundancy / duplicate rate            🆕
    ⑥ 模态一致性 (modality)  — vector/raster mismatch rate            🆕

Usage:
    python scripts/diagnose_l3_quality.py \
        --eval-csv outputs_v2/diagnostics/open_landing_vec11277_typed/end_to_end_showcase_eval.csv \
        [--references outputs_v2/diagnostics/heldout_vec11277/heldout_references.json] \
        [--output-dir outputs_v2/diagnostics/quality_report/]
"""

from __future__ import annotations

import argparse
import csv
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

SPECIAL_TOKENS = {-1, -2, -3, -4}


# ===========================================================================
# L3 Operator Role Classification (from evaluate_workflow_usability.py)
# ===========================================================================

# These L2 codes define the role taxonomy used by the original usability
# evaluator.  We inline them so this script is self-contained.
# NOTE: For vector tasks, "filter" operations (Clip, Select, Extract) are
# functionally "compute" — they transform data.  We treat them as processing
# steps for completeness assessment.
DATA_SOURCE_L2 = {"L2_01_01", "L2_01_02", "L2_01_03"}
FILTER_L2 = {"L2_02_06"}
COMPUTE_L2 = {"L2_02_01", "L2_02_02", "L2_02_04", "L2_02_05", "L2_03_01",
              "L2_03_02", "L2_03_03", "L2_03_04", "L2_03_05", "L2_03_06",
              "L2_03_07", "L2_03_08", "L2_03_09", "L2_04_01", "L2_05_01"}
AGGREGATION_L2 = {"L2_03_01", "L2_03_09", "L2_01_04", "L2_01_05"}
EXPORT_L2 = {"L2_01_05", "L2_06_01", "L2_06_02"}
BRIDGE_L2 = {"L2_05_03"}
VISUALIZATION_L2 = {"L2_07_01"}
# Vector-specific operations that are "compute" regardless of L2 classification:
# All L2_02_* (vector overlay/analysis), L2_04_* (spatial join), L2_05_* (geometry),
# L2_06_* (selection/extraction), L2_07_* (conversion) are processing steps.
VECTOR_COMPUTE_L2_PREFIXES = ("L2_02_", "L2_04_", "L2_05_", "L2_06_", "L2_07_")
L1_RASTER = "L1_03"
L1_VECTOR = "L1_02"


def _l3_to_l2(l3_code: str) -> str:
    """Map L3 code to its L2 category.

    L3_02_01_01 (Buffer) → L2_02_01
    L3_03_09_01 (Temporal Reducer) → L2_03_09
    """
    parts = l3_code.split("_")
    if len(parts) >= 4 and parts[0] in ("L3", "L3"):
        # parts: ["L3", "02", "01", "01"] → L2: "L2_02_01"
        return f"L2_{parts[1]}_{parts[2]}"
    return l3_code


def _l3_to_l1(l3_code: str) -> str:
    """Map L3 code to its L1 category."""
    parts = l3_code.split("_")
    if len(parts) >= 4 and parts[0] in ("L3",):
        return f"L1_{parts[1]}"
    return l3_code


def _classify_token(l3_code: str) -> dict:
    """Classify a single L3 code into role categories."""
    l2 = _l3_to_l2(l3_code)
    l1 = _l3_to_l1(l3_code)
    is_vec_compute = l2.startswith(VECTOR_COMPUTE_L2_PREFIXES)
    return {
        "is_data_source": l2 in DATA_SOURCE_L2,
        "is_filter": l2 in FILTER_L2,
        "is_compute": l2 in COMPUTE_L2 or is_vec_compute,
        "is_export": l2 in EXPORT_L2,
        "is_aggregation": l2 in AGGREGATION_L2,
        "is_bridge": l2 in BRIDGE_L2,
        "is_visualization": l2 in VISUALIZATION_L2,
        "is_raster": l1 == "L1_03",
        "is_vector": l1 == "L1_02",
        "l1": l1,
        "l2": l2,
    }


# ===========================================================================
# Quality dimensions
# ===========================================================================

@dataclass
class ChainDiagnostic:
    """Per-chain quality scores across 6 dimensions."""
    task_id: str = ""
    group: str = ""
    predicted_codes: list[str] = field(default_factory=list)
    predicted_ops: list[str] = field(default_factory=list)

    # ① Usability
    l3_usable: bool = False
    l3_score: float = 0.0
    # ② Executability
    qgis_valid: bool = False
    l3_bridge_rate: float = 0.0
    # ③ Correctness (requires references)
    set_f1: Optional[float] = None
    lcs: Optional[int] = None
    # ④ Completeness
    critical_coverage: float = 0.0
    missing_critical: list[str] = field(default_factory=list)
    has_compute: bool = False
    has_source: bool = False
    # ⑤ Conciseness
    redundancy_rate: float = 0.0
    consecutive_dups: int = 0
    # ⑥ Modality consistency
    vec_ratio: float = 0.0
    has_modality_mismatch: bool = False


def extract_codes_from_l3_chain(l3_chain: str) -> list[str]:
    """Parse 'L3_02_01_01(Buffer) -> L3_02_02_06(Clip)' -> ['L3_02_01_01', ...]"""
    if not l3_chain:
        return []
    codes = []
    for part in l3_chain.split(" -> "):
        code = part.split("(")[0].strip()
        if code:
            codes.append(code)
    return codes


def compute_diagnostics(
    eval_csv: Path,
    references: Optional[dict] = None,
) -> list[ChainDiagnostic]:
    """Parse eval CSV and compute per-chain quality diagnostics."""
    rows = []
    with eval_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    diagnostics: list[ChainDiagnostic] = []
    for i, row in enumerate(rows):
        codes = extract_codes_from_l3_chain(row.get("l3_chain", ""))
        ops = (row.get("qgis_chain", "") or "").split(" -> ") if row.get("qgis_chain") else []

        diag = ChainDiagnostic(
            task_id=str(i),
            group=row.get("group", "unknown"),
            predicted_codes=codes,
            predicted_ops=[o for o in ops if o],
            # ①
            l3_usable=row.get("l3_usable", "False") == "True",
            l3_score=float(row.get("l3_score", 0) or 0),
            # ②
            qgis_valid=row.get("qgis_valid", "False") == "True",
            l3_bridge_rate=float(row.get("l3_bridge_rate", 0) or 0),
        )

        # ③ Correctness (if references)
        if references and str(i) in references:
            ref = references[str(i)]
            ref_set = set(ref.get("l3_codes", []))
            pred_set = set(codes)
            if pred_set or ref_set:
                tp = len(pred_set & ref_set)
                prec = tp / max(len(pred_set), 1)
                rec = tp / max(len(ref_set), 1)
                if prec + rec > 0:
                    diag.set_f1 = 2 * prec * rec / (prec + rec)
                else:
                    diag.set_f1 = 0.0
                # LCS
                m, n = len(codes), len(ref.get("l3_codes", []))
                dp = [[0] * (n + 1) for _ in range(m + 1)]
                for a in range(m):
                    for b in range(n):
                        if codes[a] == ref["l3_codes"][b]:
                            dp[a + 1][b + 1] = dp[a][b] + 1
                        else:
                            dp[a + 1][b + 1] = max(dp[a][b + 1], dp[a + 1][b])
                diag.lcs = dp[m][n]

        # ④ Completeness
        roles = [_classify_token(c) for c in codes]
        diag.has_compute = any(r["is_compute"] or r["is_aggregation"] for r in roles)
        diag.has_source = any(
            r["is_data_source"] or r["is_filter"] for r in roles[: min(3, len(roles))]
        )
        # Any processing step at all (compute/filter/aggregate/export)?
        has_any_processing = any(
            r["is_compute"] or r["is_filter"] or r["is_aggregation"] or r["is_export"]
            for r in roles
        )
        # FP05: compute without source (structural issue)
        if diag.has_compute and not diag.has_source and len(codes) >= 2:
            diag.missing_critical.append("FP05:no_data_source_before_compute")
        # Chain too short for meaningful work
        if len(codes) <= 1:
            diag.missing_critical.append("chain_too_short")
        elif not has_any_processing:
            diag.missing_critical.append("no_processing_steps")

        # ⑤ Conciseness
        if codes:
            dup_count = sum(1 for a in range(1, len(codes)) if codes[a] == codes[a - 1])
            diag.redundancy_rate = dup_count / len(codes)
            diag.consecutive_dups = dup_count

        # ⑥ Modality consistency
        vec_count = sum(1 for r in roles if r["is_vector"])
        rast_count = sum(1 for r in roles if r["is_raster"])
        diag.vec_ratio = vec_count / max(len(roles), 1)
        has_vec = vec_count > 0
        has_rast = rast_count > 0
        has_bridge = any(r["is_bridge"] for r in roles)
        diag.has_modality_mismatch = has_vec and has_rast and not has_bridge

        diagnostics.append(diag)

    return diagnostics


def generate_report(
    diagnostics: list[ChainDiagnostic],
    output_dir: Optional[Path] = None,
) -> str:
    """Generate a multi-dimensional quality report."""
    lines: list[str] = []
    lines.append("# L3 Chain Quality — Multi-Dimensional Assessment")
    lines.append("")
    lines.append(f"Total chains evaluated: {len(diagnostics)}")
    lines.append("")

    # Overall scores
    n = len(diagnostics)
    usable_n = sum(1 for d in diagnostics if d.l3_usable)
    valid_n = sum(1 for d in diagnostics if d.qgis_valid)
    complete_n = sum(1 for d in diagnostics if not d.missing_critical and d.has_compute)
    has_ref_n = sum(1 for d in diagnostics if d.set_f1 is not None)

    lines.append("## Overall")
    lines.append("")
    lines.append(f"| Dimension | Score |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| ① Usability (L3 usable) | {usable_n}/{n} ({100*usable_n/max(n,1):.0f}%) |")
    lines.append(f"| ② Executability (QGIS valid) | {valid_n}/{n} ({100*valid_n/max(n,1):.0f}%) |")
    lines.append(f"| ④ Completeness (no missing critical) | {complete_n}/{n} ({100*complete_n/max(n,1):.0f}%) |")
    if has_ref_n > 0:
        mean_f1 = sum(d.set_f1 for d in diagnostics if d.set_f1 is not None) / max(has_ref_n, 1)
        lines.append(f"| ③ Correctness (SetF1) | {mean_f1:.3f} (n={has_ref_n}) |")

    mean_red = sum(d.redundancy_rate for d in diagnostics) / max(n, 1)
    mismatch_n = sum(1 for d in diagnostics if d.has_modality_mismatch)
    lines.append(f"| ⑤ Conciseness (mean redundancy) | {mean_red:.3f} |")
    lines.append(f"| ⑥ Modality (mismatch rate) | {mismatch_n}/{n} ({100*mismatch_n/max(n,1):.0f}%) |")
    lines.append("")

    # By group
    for group in ["vec", "rast", "mixed"]:
        grp = [d for d in diagnostics if d.group == group]
        if not grp:
            continue
        gn = len(grp)
        g_usable = sum(1 for d in grp if d.l3_usable)
        g_valid = sum(1 for d in grp if d.qgis_valid)
        g_complete = sum(1 for d in grp if not d.missing_critical and d.has_compute)
        g_mismatch = sum(1 for d in grp if d.has_modality_mismatch)
        g_red = sum(d.redundancy_rate for d in grp) / max(gn, 1)

        lines.append(f"## {group} (n={gn})")
        lines.append("")
        lines.append(f"| Dimension | Value |")
        lines.append(f"|-----------|-------|")
        lines.append(f"| ① Usable | {g_usable}/{gn} ({100*g_usable/max(gn,1):.0f}%) |")
        lines.append(f"| ② Executable | {g_valid}/{gn} ({100*g_valid/max(gn,1):.0f}%) |")
        lines.append(f"| ④ Complete | {g_complete}/{gn} ({100*g_complete/max(gn,1):.0f}%) |")
        lines.append(f"| ⑤ Redundancy | {g_red:.3f} |")
        lines.append(f"| ⑥ Mismatch | {g_mismatch}/{gn} ({100*g_mismatch/max(gn,1):.0f}%) |")

        # Missing critical details
        missing_counts: Counter = Counter()
        for d in grp:
            for m in d.missing_critical:
                missing_counts[m] += 1
        if missing_counts:
            lines.append("")
            lines.append("**Missing critical steps:**")
            for reason, cnt in missing_counts.most_common():
                lines.append(f"- {reason}: {cnt}/{gn} ({100*cnt/max(gn,1):.0f}%)")
        lines.append("")

    # Top-5 worst chains by completeness
    lines.append("## Worst chains (by completeness)")
    lines.append("")
    sorted_by_critical = sorted(diagnostics, key=lambda d: len(d.missing_critical), reverse=True)
    for d in sorted_by_critical[:10]:
        if not d.missing_critical:
            break
        codes_str = " -> ".join(d.predicted_codes[:6])
        if len(d.predicted_codes) > 6:
            codes_str += f" ... (+{len(d.predicted_codes)-6})"
        lines.append(f"- **[{d.group}]** {codes_str}")
        lines.append(f"  Missing: {', '.join(d.missing_critical)}")
        lines.append("")

    report = "\n".join(lines)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / "l3_quality_report.md"
        md_path.write_text(report, encoding="utf-8")
        json_path = output_dir / "l3_quality_diagnostics.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump([{
                "task_id": d.task_id,
                "group": d.group,
                "codes": d.predicted_codes,
                "usable": d.l3_usable,
                "valid": d.qgis_valid,
                "set_f1": d.set_f1,
                "missing_critical": d.missing_critical,
                "redundancy": d.redundancy_rate,
                "modality_mismatch": d.has_modality_mismatch,
            } for d in diagnostics], f, ensure_ascii=False, indent=2)
        print(f"Report written to {output_dir}")

    return report


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-csv", required=True,
                        help="Path to end_to_end_showcase_eval.csv")
    parser.add_argument("--references", default=None,
                        help="Optional JSON references file for ③ correctness")
    parser.add_argument("--output-dir", default="outputs_v2/diagnostics/quality_report",
                        help="Directory for report artifacts")
    args = parser.parse_args(argv)

    refs = None
    if args.references:
        with open(args.references, "r", encoding="utf-8") as f:
            refs = json.load(f)

    diags = compute_diagnostics(Path(args.eval_csv), refs)
    report = generate_report(diags, Path(args.output_dir))
    print(report)


if __name__ == "__main__":
    main()
