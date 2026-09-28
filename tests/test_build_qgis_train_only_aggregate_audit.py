from __future__ import annotations

import unittest

from scripts.build_qgis_train_only_aggregate_audit import (
    assign_source_disjoint_splits,
    build_summary,
    classify_risk,
    select_stratified_audit,
)


def _row(pool: str, key: str, n: int = 1) -> dict:
    return {
        "aggregate_source_pool": pool,
        "sample_id": f"{pool}-{key}",
        "source_sha256": f"source-{pool}-{key}",
        "source_authority_key": f"body-{pool}-{key}",
        "operator_sequence": [f"op-{key}-{index}" for index in range(n)],
        "l3_code_sequence": [f"l3-{key}-{index}" for index in range(n)],
        "n": n,
        "whole_function_semantics_admission": (
            "not_granted" if n == 1 else "granted_source_workflow"
        ),
    }


class BuildQgisTrainOnlyAggregateAuditTest(unittest.TestCase):
    def test_selects_frozen_pool_quotas_and_high_risk_rows(self) -> None:
        rows = [
            _row("processing", "a", 12),
            _row("processing", "b", 6),
            _row("processing", "c", 3),
            _row("processing", "d", 1),
            _row("api", "a"),
            _row("api", "b"),
        ]

        selected = select_stratified_audit(
            rows, quotas={"processing": 3, "api": 1}, seed=7
        )

        self.assertEqual(len(selected), 4)
        self.assertIn("very_long_chain_ge_10", {row["audit_risk_stratum"] for row in selected})
        self.assertEqual(
            sum(row["aggregate_source_pool"] == "processing" for row in selected), 3
        )

    def test_split_is_deterministic_and_source_disjoint(self) -> None:
        rows = [_row("processing", str(index), index + 1) for index in range(4)]
        rows += [_row("api", str(index)) for index in range(4)]
        selected = select_stratified_audit(
            rows, quotas={"processing": 4, "api": 4}, seed=11
        )

        first = assign_source_disjoint_splits(selected, 11)
        second = assign_source_disjoint_splits(selected, 11)
        summary = build_summary(
            rows, first, {"processing": 4, "api": 4}, 11
        )

        self.assertEqual(first, second)
        self.assertEqual(summary["calibration_rows"], 4)
        self.assertEqual(summary["holdout_rows"], 4)
        self.assertEqual(summary["source_sha_overlap"], 0)
        self.assertEqual(summary["source_authority_overlap"], 0)

    def test_rejects_insufficient_source_disjoint_support(self) -> None:
        first = _row("api", "a")
        duplicate_source = {
            **_row("api", "b"),
            "source_sha256": first["source_sha256"],
        }

        with self.assertRaisesRegex(ValueError, "insufficient source-disjoint support"):
            select_stratified_audit(
                [first, duplicate_source], quotas={"api": 2}, seed=3
            )

    def test_classifies_local_macro_boundary(self) -> None:
        self.assertEqual(classify_risk(_row("api", "a")), "local_macro_boundary")


if __name__ == "__main__":
    unittest.main()
