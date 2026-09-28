from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_stable125 import freeze_stable125


def _stable124() -> dict:
    return {
        "proposed_taxonomy": "stable124",
        "taxonomy_admission": "granted",
        "existing_code_to_id": {f"L3_BASE_{index}": index for index in range(118)},
        "proposed_code_to_id_additions": {
            f"L3_ADDED_{index}": token for index, token in enumerate(range(118, 124))
        },
    }


def _replay(*, verified: int = 52) -> dict:
    return {
        "macro_source_replay_rule_id": "create-feature-class-source-alias-replay-v1",
        "input_rows": 67,
        "verified_source_sha256_rows": 67,
        "verified_complete_macro_alias_chain_rows": verified,
        "source_replay_status_counts": {
            "verified_complete_macro_alias_chain": verified,
            "deferred_no_memory_layer_constructor": 67 - verified,
        },
        "training_rows_emitted": 0,
    }


class AdjudicateQgisApiStable125Test(unittest.TestCase):
    def test_appends_existing_legacy_class_without_changing_old_tokens(self) -> None:
        authority, extension, summary = freeze_stable125(_stable124(), _replay())

        self.assertEqual(authority[0]["operator_id"], "pyqgis:create_feature_class")
        self.assertEqual(authority[0]["l3_token_id"], 124)
        self.assertEqual(
            extension["proposed_code_to_id_additions"]["L3_01_01_01"], 124
        )
        self.assertTrue(extension["existing_token_ids_unchanged"])
        self.assertEqual(summary["content_token_count"], 125)
        self.assertFalse(summary["training_rows_emitted"])

    def test_rejects_support_below_family_gate(self) -> None:
        with self.assertRaisesRegex(ValueError, "support"):
            freeze_stable125(_stable124(), _replay(verified=29))


if __name__ == "__main__":
    unittest.main()
