#!/usr/bin/env python3
"""Evaluate deterministic QGIS routing rules against the frozen calibration ledger."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import extract_conversion_features
from gis_recommend.data.qgis_conversion_rules import route_candidate


DEFAULT_LEDGER = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1/calibration_v1/ledger.jsonl"
DEFAULT_CONFIG = ROOT / "config/qgis_conversion_rules_v1.json"


def _label(decision: str) -> str:
    if decision == "accepted":
        return "accepted"
    if decision.startswith("rejected"):
        return "rejected"
    return "deferred"


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if not total:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def evaluate(ledger_path: Path, config_path: Path) -> dict:
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    by_rule: dict[str, Counter] = defaultdict(Counter)
    routing: Counter = Counter()
    signatures: Counter = Counter()
    for row in rows:
        source = Path(row["source_path"]).read_text(encoding="utf-8", errors="replace")
        features = extract_conversion_features(source, call_sites=row.get("call_sites")).data
        decision = route_candidate(row, features)
        label = _label(row["final_decision"])
        by_rule[decision.rule_id][label] += 1
        routing[decision.action] += 1
        signatures[extract_conversion_features(source, call_sites=row.get("call_sites")).signature_hash] += 1

    gate = config["auto_accept_gate"]
    rule_metrics: dict[str, dict] = {}
    allowlisted: list[str] = []
    for rule_id, counts in sorted(by_rule.items()):
        support = sum(counts.values())
        accepted = counts["accepted"]
        precision = accepted / support if support else 0.0
        lower = _wilson_lower(accepted, support)
        eligible = (
            rule_id == "direct-explicit-dag-v1"
            and precision >= gate["minimum_observed_precision"]
            and support >= gate["minimum_reviewed_support"]
            and lower >= gate["minimum_wilson_lower_bound"]
        )
        if eligible:
            allowlisted.append(rule_id)
        rule_metrics[rule_id] = {
            "support": support,
            "accepted": accepted,
            "deferred": counts["deferred"],
            "rejected": counts["rejected"],
            "accepted_precision": precision,
            "wilson_lower_95": lower,
            "auto_accept_eligible": eligible,
        }
    return {
        "schema": "gis_recommend.qgis_conversion_rule_metrics.v1",
        "calibration_rows": len(rows),
        "routing_counts": dict(sorted(routing.items())),
        "unique_structural_signatures": len(signatures),
        "rule_metrics": rule_metrics,
        "auto_accept_allowlist": allowlisted,
        "decision": {
            "auto_accept_granted": bool(allowlisted),
            "next_gate": "sample at least 30 full-corpus matches per candidate rule and re-evaluate precision",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        },
    }


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_LEDGER.parent / "rule_metrics_v1.json")
    args = parser.parse_args(argv)
    report = evaluate(args.ledger, args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return args.output


if __name__ == "__main__":
    main()
