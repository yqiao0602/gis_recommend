import unittest

from scripts.build_qgis_stable98_draft import (
    analyze_mapping_impact,
    build_extension_proposal,
    build_mapping_delta,
    compare_embedded_l3_sequences,
    mapping_from_crosswalk,
)


class Stable98DraftTest(unittest.TestCase):
    def test_extension_appends_restored_codes_without_changing_existing_tokens(self) -> None:
        stable_rows = [
            {"l3_code": "L3_A", "l3_name": "A"},
            {"l3_code": "L3_B", "l3_name": "B"},
        ]
        legacy_rows = stable_rows + [{"l3_code": "L3_C", "l3_name": "C"}]
        vocab = {
            "special_tokens": {"<PAD>": -1},
            "code_to_id": {"L3_A": 0, "L3_B": 1},
            "id_to_code": {"0": "L3_A", "1": "L3_B"},
        }

        proposal = build_extension_proposal(
            stable_rows=stable_rows,
            legacy_rows=legacy_rows,
            vocab=vocab,
            restored_codes=["L3_C"],
        )

        self.assertEqual(proposal["base_class_count"], 2)
        self.assertEqual(proposal["proposed_class_count"], 3)
        self.assertEqual(proposal["existing_code_to_id"], {"L3_A": 0, "L3_B": 1})
        self.assertEqual(proposal["proposed_code_to_id_additions"], {"L3_C": 2})
        self.assertEqual(proposal["restored_l3"][0]["l3_name"], "C")
        self.assertEqual(proposal["taxonomy_admission"], "not_granted")

    def test_mapping_delta_keeps_alias_and_restoration_proposals_separate(self) -> None:
        adjudications = [
            {
                "operator_id": "native:alias",
                "candidate_l3_codes": ["L3_A"],
                "mapping_kind": "alias_existing_stable94",
                "review_decision": "accepted_mapping_proposal",
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            },
            {
                "operator_id": "native:restored",
                "candidate_l3_codes": ["L3_C"],
                "mapping_kind": "restore_old350_l3",
                "review_decision": "accepted_mapping_proposal",
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            },
        ]

        delta = build_mapping_delta(
            adjudications,
            stable_codes={"L3_A", "L3_B"},
            restored_codes={"L3_C"},
        )

        self.assertEqual(delta["alias_mappings"], {"native:alias": "L3_A"})
        self.assertEqual(delta["restored_l3_mappings"], {"native:restored": "L3_C"})
        self.assertEqual(delta["taxonomy_admission"], "not_granted")
        self.assertEqual(delta["training_admission"], "not_granted")

    def test_impact_counts_records_and_unique_chains_separately(self) -> None:
        crosswalk = {
            "entries": {
                "native:a": {
                    "l3_code": "L3_A",
                    "bridge_type": "l3_bridge",
                    "status": "accepted",
                },
                "native:native-only": {
                    "l3_code": "qgis_native:native_only",
                    "bridge_type": "native_bridge",
                    "status": "accepted",
                },
            }
        }
        records = [
            {"task_text": "base", "qgis_ops": ["native:a"]},
            {"task_text": "alias one", "qgis_ops": ["native:a", "native:b"]},
            {"task_text": "alias duplicate", "qgis_ops": ["native:a", "native:b"]},
            {"task_text": "restored", "qgis_ops": ["native:a", "native:c"]},
            {"task_text": "both", "qgis_ops": ["native:b", "native:c"]},
            {"task_text": "blocked", "qgis_ops": ["native:b", "native:x"]},
        ]

        summary, details = analyze_mapping_impact(
            records,
            baseline_mapping=mapping_from_crosswalk(crosswalk),
            alias_mappings={"native:b": "L3_B"},
            restored_mappings={"native:c": "L3_C"},
        )

        self.assertEqual(summary["baseline"], {"complete_records": 1, "complete_unique_chains": 1})
        self.assertEqual(summary["alias_only"], {"complete_records": 3, "complete_unique_chains": 2})
        self.assertEqual(summary["stable98_draft"], {"complete_records": 5, "complete_unique_chains": 4})
        self.assertEqual(summary["newly_complete_by_alias"], {"records": 2, "unique_chains": 1})
        self.assertEqual(summary["newly_complete_by_restored_l3"], {"records": 2, "unique_chains": 2})
        self.assertEqual(summary["affected_records"], 5)
        self.assertEqual(summary["affected_unique_chains"], 4)
        self.assertEqual(summary["affected_still_incomplete_records"], 1)
        self.assertEqual(
            [row["impact_stage"] for row in details],
            ["alias_only", "alias_only", "stable98_restoration", "stable98_restoration", "still_incomplete"],
        )
        self.assertEqual(details[-1]["stable98_unresolved_ops"], ["native:x"])

    def test_embedded_l3_comparison_exposes_legacy_only_rows(self) -> None:
        records = [
            {"qgis_ops": ["native:a"], "optional_l3_sequence": ["L3_A"]},
            {"qgis_ops": ["native:x"], "optional_l3_sequence": ["L3_OLD"]},
            {"qgis_ops": ["native:a"]},
        ]

        comparison = compare_embedded_l3_sequences(records, {"native:a": "L3_A"})

        self.assertEqual(comparison["embedded_optional_l3_records"], 2)
        self.assertEqual(comparison["strict_baseline_complete_records"], 2)
        self.assertEqual(comparison["overlap_records"], 1)
        self.assertEqual(comparison["embedded_only_records"], 1)
        self.assertEqual(comparison["strict_only_records"], 1)
        self.assertEqual(comparison["embedded_only_unresolved_operator_counts"], {"native:x": 1})


if __name__ == "__main__":
    unittest.main()
