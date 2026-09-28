from pathlib import Path
import subprocess
import sys
import unittest


def literal(value):
    return {"type": "Literal", "value": value}


def ident(name):
    return {"type": "Identifier", "name": name}


def member(obj, prop):
    return {
        "type": "MemberExpression",
        "object": obj,
        "property": ident(prop),
        "computed": False,
    }


def call(callee, *arguments):
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def var(name, expression, line):
    return {
        "type": "VariableDeclaration",
        "loc": {"start": {"line": line}, "end": {"line": line}},
        "declarations": [
            {"type": "VariableDeclarator", "id": ident(name), "init": expression}
        ],
        "kind": "var",
    }


class BuildGeeMeanClipTaskTextTests(unittest.TestCase):
    def test_maps_only_reviewed_temporal_policies(self):
        from scripts.build_gee_mean_clip_task_text import temporal_phrase

        self.assertEqual(
            temporal_phrase("allow_source_backed_full_year_2000"),
            "for the source-defined 2000 period",
        )
        self.assertEqual(
            temporal_phrase("allow_source_backed_full_year_2010"),
            "for the source-defined 2010 period",
        )
        self.assertEqual(
            temporal_phrase("allow_source_backed_full_year_2021"),
            "for the source-defined 2021 period",
        )
        self.assertEqual(temporal_phrase("allow_source_backed_full_year_2019"), "for 2019")
        self.assertEqual(
            temporal_phrase("allow_source_backed_cross_year_season_2018_2019"),
            "for the source-defined 2018-2019 season",
        )
        self.assertEqual(temporal_phrase("omit_unverified_temporal_facts"), "")
        with self.assertRaisesRegex(ValueError, "unknown temporal description policy"):
            temporal_phrase("allow_unreviewed_guess")

    def test_extracts_only_unique_public_imagecollection_literal_from_closure(self):
        from scripts.build_gee_mean_clip_task_text import (
            extract_dependency_dataset_literals,
        )

        ast = {
            "type": "Program",
            "body": [
                var(
                    "region",
                    call(member(ident("ee"), "FeatureCollection"), literal("users/me/aoi")),
                    1,
                ),
                var(
                    "source",
                    call(member(ident("ee"), "ImageCollection"), literal("COPERNICUS/S2_SR")),
                    2,
                ),
                var(
                    "result",
                    call(
                        member(call(member(ident("source"), "mean")), "clip"),
                        ident("region"),
                    ),
                    3,
                ),
            ],
        }
        row = {
            "definition_id": "result@1",
            "transitive_dependency_ids": ["region@1", "source@1"],
        }

        self.assertEqual(
            extract_dependency_dataset_literals(row, ast), ["COPERNICUS/S2_SR"]
        )

    def test_private_multiple_and_missing_dataset_literals_fall_back(self):
        from scripts.build_gee_mean_clip_task_text import (
            build_chain_faithful_text,
            extract_dependency_dataset_literals,
        )

        private_ast = {
            "type": "Program",
            "body": [
                var(
                    "source",
                    call(
                        member(ident("ee"), "ImageCollection"),
                        literal("users/me/private_collection"),
                    ),
                    1,
                )
            ],
        }
        row = {
            "definition_id": "source@1",
            "transitive_dependency_ids": [],
            "temporal_description_policy": "omit_unverified_temporal_facts_and_ignore_median_name",
            "semantic_facts": {"output_variable": "S1_median"},
        }
        self.assertEqual(extract_dependency_dataset_literals(row, private_ast), [])

        text = build_chain_faithful_text(row, {"dataset_literals": []})

        self.assertEqual(text["task_name"], "Create a clipped mean image composite")
        self.assertEqual(
            text["task_description"],
            "Compute the mean image of the source ImageCollection, then clip the result "
            "to the source-defined region.",
        )
        self.assertNotIn("median", text["task_description"].lower())

        multiple_ast = {
            "type": "Program",
            "body": [
                var(
                    "a",
                    call(member(ident("ee"), "ImageCollection"), literal("A/PUBLIC")),
                    1,
                ),
                var(
                    "b",
                    call(member(ident("ee"), "ImageCollection"), literal("B/PUBLIC")),
                    2,
                ),
            ],
        }
        multi_row = {
            "definition_id": "a@1",
            "transitive_dependency_ids": ["b@1"],
        }
        self.assertEqual(
            extract_dependency_dataset_literals(multi_row, multiple_ast),
            ["A/PUBLIC", "B/PUBLIC"],
        )
        multi_text = build_chain_faithful_text(
            {**row, "temporal_description_policy": "allow_source_backed_full_year_2021"},
            {"dataset_literals": ["A/PUBLIC", "B/PUBLIC"]},
        )
        self.assertNotIn("A/PUBLIC", multi_text["task_description"])
        self.assertNotIn("B/PUBLIC", multi_text["task_description"])

        mixed_ast = {
            "type": "Program",
            "body": [
                var(
                    "public",
                    call(
                        member(ident("ee"), "ImageCollection"),
                        literal("COPERNICUS/S2_SR"),
                    ),
                    1,
                ),
                var(
                    "private",
                    call(
                        member(ident("ee"), "ImageCollection"),
                        literal("users/me/private_collection"),
                    ),
                    2,
                ),
            ],
        }
        mixed_row = {
            "definition_id": "public@1",
            "transitive_dependency_ids": ["private@1"],
        }
        self.assertEqual(
            extract_dependency_dataset_literals(mixed_row, mixed_ast), []
        )

    def test_deduplicates_by_normalized_task_text_and_l3_chain(self):
        from scripts.build_gee_mean_clip_task_text import deduplicate_candidates

        base = {
            "task_name": "Create a clipped mean image composite",
            "task_description": "Compute a mean image, then clip it.",
            "l3_sequence": ["L3_10_02_03", "L3_03_01_01"],
        }
        rows = [
            {**base, "cluster_id": "b", "source_sha256": "b" * 64},
            {
                **base,
                "cluster_id": "a",
                "source_sha256": "a" * 64,
                "task_description": "  Compute a mean image, then clip it.  ",
            },
        ]

        deduplicated, duplicates = deduplicate_candidates(rows)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0]["cluster_id"], "a")
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["duplicate_cluster_id"], "b")


class AdjudicateGeeMeanClipTaskTextTests(unittest.TestCase):
    def test_review_requires_identity_complete_coverage_and_keeps_training_closed(self):
        from scripts.adjudicate_gee_mean_clip_task_text import summarize_review

        candidates = [
            {"source_review_index": 1, "cluster_id": "a", "source_sha256": "a" * 64},
            {"source_review_index": 2, "cluster_id": "b", "source_sha256": "b" * 64},
        ]
        decisions = [
            {
                "review_index": 1,
                "cluster_id": "a",
                "source_sha256": "a" * 64,
                "dataset_fidelity": "pass",
                "temporal_fidelity": "pass",
                "chain_fidelity": "pass",
                "final_decision": "pass",
            },
            {
                "review_index": 2,
                "cluster_id": "b",
                "source_sha256": "b" * 64,
                "dataset_fidelity": "pass",
                "temporal_fidelity": "pass_after_correction",
                "chain_fidelity": "pass",
                "final_decision": "pass",
            },
        ]

        rollup, summary = summarize_review(candidates, decisions)

        self.assertEqual(len(rollup), 2)
        self.assertTrue(summary["exporter_replay_eligible"])
        self.assertEqual(summary["training_admission"], "not_granted_task_text_review")
        self.assertEqual(summary["training_rows_emitted"], 0)

        decisions[1]["final_decision"] = "needs_edit"
        _, blocked = summarize_review(candidates, decisions)
        self.assertFalse(blocked["exporter_replay_eligible"])

        decisions[1]["cluster_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            summarize_review(candidates, decisions)


class ExportGeeMeanClipRepairedBatchTests(unittest.TestCase):
    def test_cli_help_starts_from_script_path(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "export_gee_mean_clip_repaired_batch.py"),
                "--help",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_prepares_reviewed_and_fail_closed_temporal_rows_and_risk_sample(self):
        from scripts.export_gee_mean_clip_repaired_batch import (
            prepare_batch_rows,
            select_audit_sample,
        )

        base = {
            "pattern": "annual_mean_clip",
            "semantic_status": "accepted_proposal",
            "canonical_operator_sequence": [
                "ee.imagecollection.mean",
                "ee.image.clip",
            ],
            "l3_code_sequence": ["L3_10_02_03", "L3_03_01_01"],
        }
        repaired = [
            {**base, "source_sha256": "a" * 64, "definition_id": "a@1"},
            {**base, "source_sha256": "b" * 64, "definition_id": "b@1"},
            {**base, "source_sha256": "c" * 64, "definition_id": "c@1"},
        ]
        reviewed = [
            {
                "source_sha256": "a" * 64,
                "definition_id": "a@1",
                "temporal_description_policy": "allow_source_backed_full_year_2019",
            }
        ]

        rows, coverage = prepare_batch_rows(repaired, reviewed)

        self.assertEqual(len(rows), 3)
        self.assertEqual(coverage["reviewed_temporal_policy"], 1)
        self.assertEqual(coverage["omit_unreviewed_temporal_facts"], 2)
        self.assertEqual(rows[0]["temporal_description_policy"], "allow_source_backed_full_year_2019")
        self.assertEqual(rows[1]["temporal_description_policy"], "omit_unverified_temporal_facts")
        self.assertNotEqual(rows[0]["cluster_id"], rows[1]["cluster_id"])

        candidates = [
            {
                "cluster_id": "reviewed",
                "dataset_description_status": "unique_public_literal",
                "temporal_description_policy": "allow_source_backed_full_year_2019",
            },
            {
                "cluster_id": "generic",
                "dataset_description_status": "generic_source_collection",
                "temporal_description_policy": "omit_unverified_temporal_facts",
            },
            {
                "cluster_id": "unreviewed",
                "dataset_description_status": "unique_public_literal",
                "temporal_description_policy": "omit_unverified_temporal_facts",
            },
        ]
        sample = select_audit_sample(candidates, 2)

        self.assertEqual({row["cluster_id"] for row in sample}, {"generic", "unreviewed"})
        self.assertTrue(all(row["audit_final_decision"] == "" for row in sample))

    def test_requires_a_complete_task_text_review_before_replay(self):
        from scripts.export_gee_mean_clip_repaired_batch import validate_replay_gate

        summary = {
            "reviewed_candidates": 21,
            "passed": 21,
            "needs_edit": 0,
            "exporter_replay_eligible": True,
            "training_rows_emitted": 0,
        }

        validate_replay_gate(summary)

        summary["exporter_replay_eligible"] = False
        with self.assertRaisesRegex(ValueError, "technical review gate"):
            validate_replay_gate(summary)

        summary.update(
            {
                "reviewed_candidates": 20,
                "passed": 20,
                "exporter_replay_eligible": True,
            }
        )
        with self.assertRaisesRegex(ValueError, "technical review gate"):
            validate_replay_gate(summary)

    def test_summarizes_batch_without_granting_training_admission(self):
        from scripts.export_gee_mean_clip_repaired_batch import build_batch_summary

        prepared = [
            {"source_sha256": "a" * 64},
            {"source_sha256": "a" * 64},
            {"source_sha256": "b" * 64},
        ]
        candidates = [
            {"dataset_description_status": "unique_public_literal"},
            {"dataset_description_status": "generic_source_collection"},
        ]

        summary = build_batch_summary(
            prepared,
            candidates,
            duplicates=[{}],
            audit_sample=[{}, {}],
            temporal_coverage={
                "reviewed_temporal_policy": 1,
                "omit_unreviewed_temporal_facts": 2,
            },
        )

        self.assertEqual(summary["counts"]["input_definitions"], 3)
        self.assertEqual(summary["counts"]["source_authorities"], 2)
        self.assertEqual(summary["counts"]["candidate_rows"], 2)
        self.assertEqual(summary["counts"]["duplicates_removed"], 1)
        self.assertEqual(summary["counts"]["audit_sample_rows"], 2)
        self.assertEqual(summary["training_admission"], "not_granted_repaired_batch_audit")
        self.assertFalse(summary["validation_eligible"])
        self.assertFalse(summary["test_eligible"])
        self.assertEqual(summary["production_merge"], "not_granted")
        self.assertEqual(summary["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
