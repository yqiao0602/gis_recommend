from __future__ import annotations

import unittest

from scripts.build_qgis_v4_128_no_truncation_package import (
    ADMISSION,
    SCHEMA,
    SPLIT,
    build_no_truncation_package,
)


class _Tokenizer:
    def __call__(
        self, prompt: str, *, add_special_tokens: bool, truncation: bool
    ) -> dict:
        assert add_special_tokens is True
        assert truncation is False
        return {"input_ids": [101, *range(len(prompt.split())), 102]}


def _row(sample_id: str, description: str) -> dict:
    metadata = {
        "task_type": "QGIS task",
        "task_name": "Run workflow",
        "task_description": description,
    }
    return {
        "sample_id": sample_id,
        "aggregate_source_pool": "pool",
        "source_authority_key": f"authority:{sample_id}",
        "n": 2,
        "schema_version": "old_schema",
        "split": "old_split",
        "training_admission": "old_admission",
        "task_name": metadata["task_name"],
        "task_description": metadata["task_description"],
        "task_metadata": metadata,
    }


class BuildQgisV4128NoTruncationPackageTest(unittest.TestCase):
    def test_routes_only_nontruncated_rows_and_preserves_provenance(self) -> None:
        short = _row("short", "short goal")
        long = _row("long", " ".join(f"word-{index}" for index in range(20)))

        eligible, ledger, summary = build_no_truncation_package(
            [short, long], _Tokenizer(), max_text_length=18
        )

        self.assertEqual([row["sample_id"] for row in eligible], ["short"])
        self.assertEqual(eligible[0]["schema_version"], SCHEMA)
        self.assertEqual(eligible[0]["split"], SPLIT)
        self.assertEqual(eligible[0]["training_admission"], ADMISSION)
        self.assertEqual(eligible[0]["prior_schema_version"], "old_schema")
        self.assertEqual(eligible[0]["prior_split"], "old_split")
        self.assertEqual(eligible[0]["prior_training_admission"], "old_admission")
        self.assertEqual(summary["eligible_rows"], 1)
        self.assertEqual(summary["deferred_rows"], 1)
        self.assertEqual(ledger[1]["decision"], "deferred_text_truncation")
        self.assertEqual(ledger[1]["training_rows_emitted"], 0)

    def test_rejects_task_metadata_drift(self) -> None:
        row = _row("sample", "goal")
        row["task_name"] = "different"

        with self.assertRaisesRegex(ValueError, "task metadata mismatch"):
            build_no_truncation_package([row], _Tokenizer(), max_text_length=128)

    def test_preserves_existing_prior_lineage_on_replay(self) -> None:
        row = _row("sample", "goal")
        row["prior_schema_version"] = "original_schema"
        row["prior_split"] = "original_split"
        row["prior_training_admission"] = "original_admission"

        eligible, _, _ = build_no_truncation_package(
            [row], _Tokenizer(), max_text_length=128
        )

        self.assertEqual(eligible[0]["prior_schema_version"], "original_schema")
        self.assertEqual(eligible[0]["prior_split"], "original_split")
        self.assertEqual(
            eligible[0]["prior_training_admission"], "original_admission"
        )


if __name__ == "__main__":
    unittest.main()
