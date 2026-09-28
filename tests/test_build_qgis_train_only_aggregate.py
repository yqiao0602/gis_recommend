from __future__ import annotations

import unittest

from scripts.build_qgis_train_only_aggregate import (
    ADMISSION,
    SCHEMA,
    SPLIT,
    build_aggregate,
)


def _row(key: str) -> dict:
    return {
        "sample_id": key,
        "source_authority_key": f"body:{key}",
        "source_region_key": f"region:{key}",
        "call_graph_key": f"graph:{key}",
        "source_verification": "verified_sha256",
        "schema_version": "source_schema_v1",
        "training_admission": "granted_train_only_source_v1",
        "split": "train_only_source_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "operator_sequence": ["native:buffer"],
        "l3_code_sequence": ["L3_02_03_01"],
        "l3_token_ids": [7],
        "l3_sequence": [-3, 7, -4],
        "task_name": f"task {key}",
        "task_description": f"description {key}",
    }


class BuildQgisTrainOnlyAggregateTest(unittest.TestCase):
    def test_wraps_source_contracts_without_opening_other_splits(self) -> None:
        aggregate, ledger, summary = build_aggregate(
            [("processing", [_row("a")]), ("api", [_row("b")])]
        )

        self.assertEqual(len(aggregate), 2)
        self.assertEqual(aggregate[0]["schema_version"], SCHEMA)
        self.assertEqual(aggregate[0]["training_admission"], ADMISSION)
        self.assertEqual(aggregate[0]["split"], SPLIT)
        self.assertEqual(aggregate[0]["source_schema_version"], "source_schema_v1")
        self.assertEqual(len(ledger), 2)
        self.assertEqual(summary["unique_training_pairs"], 2)

    def test_rejects_duplicate_cross_pool_training_pair(self) -> None:
        duplicate = _row("b")
        duplicate["task_name"] = "task a"
        duplicate["task_description"] = "description a"

        with self.assertRaisesRegex(ValueError, "duplicate exact training pair"):
            build_aggregate([("processing", [_row("a")]), ("api", [duplicate])])

    def test_rejects_non_train_source_row(self) -> None:
        row = _row("a")
        row["validation_eligible"] = True

        with self.assertRaisesRegex(ValueError, "validation/test eligibility"):
            build_aggregate([("processing", [row])])

    def test_allows_a_versioned_aggregate_contract(self) -> None:
        aggregate, _, summary = build_aggregate(
            [("api", [_row("a")])],
            aggregate_schema="qgis_train_only_495_sample_v1",
            aggregate_admission="granted_train_only_qgis_aggregate_495_v1",
            aggregate_split="train_only_qgis_aggregate_495_v1",
        )

        self.assertEqual(aggregate[0]["schema_version"], "qgis_train_only_495_sample_v1")
        self.assertEqual(summary["split"], "train_only_qgis_aggregate_495_v1")


if __name__ == "__main__":
    unittest.main()
