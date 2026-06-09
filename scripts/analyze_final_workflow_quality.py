#!/usr/bin/env python3
"""Strict quality audit of final selected workflows.

Reads a selector_report.json and produces:
  - True failure taxonomy (only non-usable samples)
  - Warning taxonomy (usable samples with non-blocking issues)
  - Duplicate & redundancy diagnostics
  - Length distribution
  - 50-sample decoded workflow audit
  - Fallback rate analysis (beam vs retrieval)

Usage:
    python scripts/analyze_final_workflow_quality.py \
        --report outputs_v2/diagnostics/execution_aware_selector/dpo_beam_first_test_3k/selector_report.json \
        --output outputs_v2/diagnostics/execution_aware_selector/dpo_beam_first_test_3k/quality
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ci(rate: float, n: int) -> str:
    if n == 0:
        return "N/A"
    se = math.sqrt(rate * (1 - rate) / max(n, 1))
    lo = max(0.0, rate - 1.96 * se)
    hi = min(1.0, rate + 1.96 * se)
    return f"[{lo:.4f}, {hi:.4f}]"


def _decode_tokens(tokens: list[int], token_to_code: dict, l3_names: dict) -> list[str]:
    return [l3_names.get(token_to_code.get(t, ""), str(t)) for t in tokens]


def _is_train_name(name: str) -> bool:
    return "train" in str(name).lower()


def _is_apply_name(name: str) -> bool:
    return "apply" in str(name).lower()


def _train_apply_cycle_count(names: list[str]) -> tuple[int, list[str]]:
    patterns = []
    for j in range(max(len(names) - 2, 0)):
        a, b, c = names[j:j + 3]
        if (
            _is_train_name(a)
            and _is_apply_name(b)
            and _is_train_name(c)
        ) or (
            _is_apply_name(a)
            and _is_train_name(b)
            and _is_apply_name(c)
        ):
            patterns.append(" → ".join([a, b, c]))
    return len(patterns), patterns


def analyze(report: dict, token_to_code: dict, l3_names: dict) -> dict:
    samples = report.get("per_sample", [])
    n = len(samples)

    # ── Basic tallies ──
    final_usable = [s for s in samples if s.get("final_usable")]
    final_failed = [s for s in samples if not s.get("final_usable")]
    beam_pick = [s for s in samples if s.get("final_source") == "beam"]
    retrieval_fallback = [s for s in samples if s.get("final_source") == "retrieval"]

    # ── Duplicate diagnostics ──
    dup_count = 0
    consec_dup_count = 0
    total_tokens = 0
    total_pairs = 0
    lengths = []
    redundant_loops = 0  # e.g. Train → Apply → Train
    loop_patterns: Counter = Counter()

    for s in final_usable:
        tokens = s.get("final_tokens", [])
        n_tok = len(tokens)
        lengths.append(n_tok)
        total_tokens += n_tok

        if n_tok > 1:
            uniq = len(set(tokens))
            if uniq < n_tok:
                dup_count += 1
            for i in range(n_tok - 1):
                total_pairs += 1
                if tokens[i] == tokens[i + 1]:
                    consec_dup_count += 1
            # Detect true Train/Apply cycles. Sample→Train→Apply is a normal
            # classification workflow and must not be counted as a loop.
            names = _decode_tokens(tokens, token_to_code, l3_names)
            loop_count, patterns = _train_apply_cycle_count(names)
            if loop_count:
                redundant_loops += 1
                loop_patterns[patterns[0]] += 1

    dup_rate = dup_count / max(len(final_usable), 1)
    consec_dup_rate = consec_dup_count / max(total_pairs, 1)
    mean_len = sum(lengths) / max(len(lengths), 1)
    length_bins = Counter()
    for l in lengths:
        if l <= 3:
            length_bins["1-3"] += 1
        elif l <= 5:
            length_bins["4-5"] += 1
        elif l <= 8:
            length_bins["6-8"] += 1
        elif l <= 12:
            length_bins["9-12"] += 1
        else:
            length_bins["13+"] += 1

    # ── Warning taxonomy (usable samples only) ──
    warning_counts: Counter = Counter()
    for s in final_usable:
        for w in s.get("final_warnings", []):
            warning_counts[w] += 1

    # ── Diversity and template concentration diagnostics ──
    chains = [tuple(int(t) for t in s.get("final_tokens", [])) for s in final_usable]
    chain_counts = Counter(chains)
    by_task_chains: dict[str, list[tuple[int, ...]]] = defaultdict(list)
    for s, chain in zip(final_usable, chains):
        by_task_chains[s.get("task_type", "Unknown")].append(chain)

    task_diversity = []
    for task, task_chains in by_task_chains.items():
        c = Counter(task_chains)
        n_task = len(task_chains)
        task_diversity.append({
            "task_type": task,
            "n": n_task,
            "unique": len(c),
            "unique_rate": round(len(c) / max(n_task, 1), 4),
            "top3_concentration": round(
                sum(v for _, v in c.most_common(3)) / max(n_task, 1), 4
            ),
        })
    task_diversity.sort(key=lambda x: x["n"], reverse=True)

    select_band_tokens = {
        int(tid) for tid, code in token_to_code.items()
        if l3_names.get(code, "") == "Select Bands"
    }
    select_presence = sum(1 for ch in chains if any(t in select_band_tokens for t in ch))
    select_repeated = 0
    select_nonconsecutive_repeated = 0
    for ch in chains:
        idxs = [i for i, t in enumerate(ch) if t in select_band_tokens]
        if len(idxs) >= 2:
            select_repeated += 1
            if not any(b == a + 1 for a, b in zip(idxs, idxs[1:])):
                select_nonconsecutive_repeated += 1

    top_repeated_chains = []
    for chain, cnt in chain_counts.most_common(10):
        tasks = {
            s.get("task_type", "Unknown")
            for s, c in zip(final_usable, chains)
            if c == chain
        }
        top_repeated_chains.append({
            "count": cnt,
            "task_type_count": len(tasks),
            "chain": " → ".join(_decode_tokens(list(chain), token_to_code, l3_names)),
        })

    # ── True failure taxonomy (non-usable only) ──
    failure_counts: Counter = Counter()
    for s in final_failed:
        for f in s.get("final_failures", []):
            failure_counts[f] += 1

    # ── Fallback analysis ──
    fallback_usable = [s for s in retrieval_fallback if s.get("final_usable")]
    fallback_reasons: Counter = Counter()
    for s in retrieval_fallback:
        if not s.get("beam_top1_usable"):
            for f in s.get("beam_top1_failures", []):
                fallback_reasons[f] += 1

    # ── Beam success rate by task type ──
    beam_by_task: dict[str, dict] = defaultdict(lambda: {"ok": 0, "fail": 0})
    for s in samples:
        t = s.get("task_type", "Unknown")
        if s.get("final_source") == "beam" and s.get("final_usable"):
            beam_by_task[t]["ok"] += 1
        elif s.get("final_source") == "beam" and not s.get("final_usable"):
            beam_by_task[t]["fail"] += 1

    beam_fail_tasks = [(t, d) for t, d in beam_by_task.items() if d["fail"] > 0]

    # ── 50-sample decoded audit ──
    rng = random.Random(42)
    audit_pool = rng.sample(final_usable, min(50, len(final_usable)))
    audit_rows = []
    for s in audit_pool:
        tokens = s.get("final_tokens", [])
        names = _decode_tokens(tokens, token_to_code, l3_names)
        has_dup = len(set(tokens)) != len(tokens)
        audit_rows.append({
            "task_type": s.get("task_type", ""),
            "source": s.get("final_source", ""),
            "chain": " → ".join(names),
            "n_tokens": len(tokens),
            "has_dup": has_dup,
            "warnings": ";".join(s.get("final_warnings", [])[:5]),
        })

    return {
        "num_samples": n,
        "final_usable": len(final_usable),
        "final_usable_rate": len(final_usable) / max(n, 1),
        "final_failed": len(final_failed),
        "beam_pick_count": len(beam_pick),
        "beam_pick_rate": len(beam_pick) / max(n, 1),
        "retrieval_fallback_count": len(retrieval_fallback),
        "retrieval_fallback_usable": len(fallback_usable),
        "retrieval_fallback_usable_rate": len(fallback_usable) / max(len(retrieval_fallback), 1),
        "fallback_reasons": dict(fallback_reasons.most_common()),
        "beam_fail_tasks": [{"task": t, **d} for t, d in beam_fail_tasks],
        # Quality
        "duplicate_token_rate": round(dup_rate, 4),
        "consecutive_duplicate_rate": round(consec_dup_rate, 4),
        "redundant_loops": redundant_loops,
        "redundant_loop_patterns": dict(loop_patterns.most_common(10)),
        "mean_length": round(mean_len, 2),
        "length_distribution": dict(length_bins),
        # Taxonomy
        "failure_taxonomy": dict(failure_counts.most_common()),
        "warning_taxonomy": dict(warning_counts.most_common()),
        # Diversity / concentration
        "global_unique_chains": len(chain_counts),
        "global_unique_chain_rate": round(len(chain_counts) / max(len(final_usable), 1), 4),
        "select_bands_presence": select_presence,
        "select_bands_presence_rate": round(select_presence / max(len(final_usable), 1), 4),
        "select_bands_repeated": select_repeated,
        "select_bands_repeated_rate": round(select_repeated / max(len(final_usable), 1), 4),
        "select_bands_nonconsecutive_repeated": select_nonconsecutive_repeated,
        "select_bands_nonconsecutive_repeated_rate": round(
            select_nonconsecutive_repeated / max(len(final_usable), 1), 4
        ),
        "task_diversity": task_diversity,
        "top_repeated_chains": top_repeated_chains,
        # Audit
        "audit_samples": audit_rows,
    }


def write_reports(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    (output_dir / "quality_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV audit
    with (output_dir / "quality_audit_samples.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_type", "source", "n_tokens", "has_dup", "warnings", "chain"])
        for r in result["audit_samples"]:
            w.writerow([r["task_type"], r["source"], r["n_tokens"],
                        r["has_dup"], r["warnings"], r["chain"]])

    # Markdown
    n = result["num_samples"]
    u = result["final_usable"]
    ur = result["final_usable_rate"]
    lines = [
        "# Final Workflow Quality Report",
        "",
        f"**Samples**: {n}",
        f"**Final usable**: {u} / {n} ({ur*100:.1f}%)",
        f"**True final failures**: {result['final_failed']}",
        "",
        "---",
        "",
        "## 1. Source Distribution",
        "",
        f"- Beam picked: {result['beam_pick_count']} / {n} ({result['beam_pick_rate']*100:.1f}%)",
        f"- Retrieval fallback: {result['retrieval_fallback_count']} / {n}",
        f"  - of which usable: {result['retrieval_fallback_usable']} / {result['retrieval_fallback_count']} ({result['retrieval_fallback_usable_rate']*100:.1f}%)",
    ]

    if result.get("beam_fail_tasks"):
        lines.append("")
        lines.append("### Beam failure tasks")
        for bt in result["beam_fail_tasks"][:10]:
            lines.append(f"- {bt['task']}: ok={bt['ok']}, fail={bt['fail']}")

    if result.get("fallback_reasons"):
        lines.append("")
        lines.append("### Fallback reasons")
        for reason, cnt in result["fallback_reasons"].items():
            lines.append(f"- {reason}: {cnt}")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Quality Diagnostics (usable samples only)",
        "",
        f"- **Duplicate token rate**: {result['duplicate_token_rate']*100:.1f}% of usable samples have >=1 duplicate",
        f"- **Consecutive duplicate rate**: {result['consecutive_duplicate_rate']*100:.2f}% of adjacent pairs",
        f"- **Redundant loops** (Train→Apply→Train etc.): {result['redundant_loops']} / {u} samples",
        f"- **Mean length**: {result['mean_length']:.1f} tokens",
        "",
        "### Length distribution",
    ])
    for bucket, cnt in sorted(result["length_distribution"].items()):
        lines.append(f"- {bucket}: {cnt}")

    if result.get("redundant_loop_patterns"):
        lines.append("")
        lines.append("### Redundant loop patterns")
        for pat, cnt in result["redundant_loop_patterns"].items():
            lines.append(f"- {pat}: {cnt}")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Diversity / Template Diagnostics",
        "",
        f"- **Global unique chains**: {result['global_unique_chains']} / {u} ({result['global_unique_chain_rate']*100:.1f}%)",
        f"- **Select Bands presence**: {result['select_bands_presence']} / {u} ({result['select_bands_presence_rate']*100:.1f}%)",
        f"- **Repeated Select Bands**: {result['select_bands_repeated']} / {u} ({result['select_bands_repeated_rate']*100:.1f}%)",
        f"- **Non-consecutive repeated Select Bands**: {result['select_bands_nonconsecutive_repeated']} / {u} ({result['select_bands_nonconsecutive_repeated_rate']*100:.1f}%)",
        "",
        "### Largest task families",
    ])
    for row in result["task_diversity"][:8]:
        lines.append(
            f"- {row['task_type']}: n={row['n']}, unique={row['unique']} "
            f"({row['unique_rate']*100:.1f}%), top3={row['top3_concentration']*100:.1f}%"
        )

    lines.extend([
        "",
        "### Top repeated chains",
    ])
    for row in result["top_repeated_chains"]:
        lines.append(
            f"- count={row['count']}, tasks={row['task_type_count']}: {row['chain']}"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Warning Taxonomy (usable samples, non-blocking)",
    ])
    for w, c in result["warning_taxonomy"].items():
        lines.append(f"- {w}: {c}")

    lines.extend([
        "",
        "---",
        "",
        "## 5. True Failure Taxonomy (non-usable only)",
    ])
    if result["failure_taxonomy"]:
        for f, c in result["failure_taxonomy"].items():
            lines.append(f"- {f}: {c}")
    else:
        lines.append("(none — all final failures were empty/invalid chains)")

    lines.extend([
        "",
        "---",
        "",
        "## 6. Manual Audit (50 random usable samples)",
        "",
        "See `quality_audit_samples.csv` for full decoded chains.",
    ])

    (output_dir / "quality_report.md").write_text(
        "\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True,
                        help="Path to selector_report.json")
    parser.add_argument("--output", required=True,
                        help="Output directory for quality report artifacts")
    parser.add_argument("--id-mappings", default="outputs_v2/id_mappings_v2.json")
    parser.add_argument("--hierarchy", default="outputs_v2/classification_hierarchy_v2.csv")
    args = parser.parse_args(argv)

    report = _load_json(Path(args.report))

    # Load vocab for decoding
    idm = _load_json(Path(args.id_mappings))
    token_to_code = {int(v): k for k, v in idm.get("l3", {}).items()}

    l3_names = {}
    with Path(args.hierarchy).open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("l3_code", "").strip()
            name = row.get("l3_name", "").strip()
            if code and name:
                l3_names[code] = name

    result = analyze(report, token_to_code, l3_names)
    write_reports(result, Path(args.output))

    # Quick print
    print(f"Samples: {result['num_samples']}")
    print(f"Final usable: {result['final_usable']}/{result['num_samples']} ({result['final_usable_rate']*100:.1f}%)")
    print(f"True failures: {result['final_failed']}")
    print(f"Duplicate rate: {result['duplicate_token_rate']*100:.1f}%")
    print(f"Consecutive dup: {result['consecutive_duplicate_rate']*100:.2f}%")
    print(f"Redundant loops: {result['redundant_loops']}")
    print(f"Mean length: {result['mean_length']}")
    print(f"Fallback rate: {result['retrieval_fallback_count']}/{result['num_samples']}, usable: {result['retrieval_fallback_usable']}/{result['retrieval_fallback_count']}")
    print(f"\nReports: {args.output}/")


if __name__ == "__main__":
    main()
