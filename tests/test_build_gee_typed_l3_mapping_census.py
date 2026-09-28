import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from gis_recommend.data.gee_operator_canonicalization import MappingEntry
from gis_recommend.data.gee_source_evidence import CallEvidence, GeeSourceEvidence

from scripts.build_gee_typed_l3_mapping_census import build_typed_l3_mapping_census
from gis_recommend.data.gee_typed_canonicalization import canonicalize_workflow_calls


SOURCE_SHA = "a" * 64


def candidate(**overrides):
    row = {
        "source_sha256": SOURCE_SHA,
        "source_path": "data10000/script_1.txt",
        "workflow_id": "output-workflow-1",
        "calibration_stratum": "linear_export",
        "extractor_version": "gee-source-extractor-v2.3.2",
        "fidelity_status": "passed",
        "fail_closed_reasons": [],
        "normalized_core_call_ordinals": [1],
        "normalized_core_chain": ["image.select"],
        "training_admission": "not_granted_taxonomy_and_task_text_pending",
        "training_rows_emitted": 0,
    }
    row.update(overrides)
    return row


def evidence(*calls, source_sha256=SOURCE_SHA, source_path="data10000/script_1.txt"):
    return GeeSourceEvidence(
        source_path=source_path,
        source_sha256=source_sha256,
        extractor_version="gee-source-extractor-v2.3.2",
        ordered_calls=list(calls),
        core_operator_chain=[call.ordinal for call in calls],
    )


def core_call(
    ordinal=1,
    raw_callee="image.select",
    resolution="receiver_ee_binding",
    receiver_type="ee.image",
    classification="core",
    flags=(),
):
    return CallEvidence(
        ordinal=ordinal,
        raw_callee=raw_callee,
        classification=classification,
        resolution=resolution,
        scope="top_level",
        context="direct",
        receiver_type=receiver_type,
        source_location={"start_line": 2, "end_line": 2},
        flags=flags,
    )


def mapping_entry(*, ambiguity=False):
    return MappingEntry(
        canonical_operator="ee.image.select",
        primary_l3="L3_01_02_01",
        mapping_confidence=0.95,
        has_ambiguity=ambiguity,
    )


def ident(name):
    return {"type": "Identifier", "name": name}


def literal(value):
    return {"type": "Literal", "value": value}


def member(obj, prop):
    return {
        "type": "MemberExpression",
        "computed": False,
        "object": obj,
        "property": ident(prop),
    }


def call(callee, *arguments):
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def simple_ast():
    image = call(member(ident("ee"), "Image"), literal(1))
    selected = call(member(image, "select"), literal("B1"))
    return {
        "type": "Program",
        "body": [
            {
                "type": "VariableDeclaration",
                "declarations": [
                    {"type": "VariableDeclarator", "id": ident("result"), "init": selected}
                ],
            }
        ],
    }


class GeeTypedCanonicalizationTests(unittest.TestCase):
    def test_proven_receiver_type_maps_call_without_family_guessing(self):
        decision = canonicalize_workflow_calls(
            candidate(),
            evidence(core_call()),
            {"ee.image.select": mapping_entry()},
            frozenset({"ee.image.select"}),
        )

        self.assertEqual(decision.mapping_status, "mapping_complete")
        self.assertEqual(decision.canonical_operator_sequence, ("ee.image.select",))
        self.assertEqual(decision.l3_sequence, ("L3_01_02_01",))
        self.assertEqual(decision.fail_closed_reasons, ())
        self.assertEqual(decision.call_decisions[0].ordinal, 1)
        self.assertEqual(decision.call_decisions[0].receiver_type, "ee.image")

    def test_proven_receiver_type_overrides_stale_chain_namespace_after_mosaic(self):
        raw = "ee.ImageCollection.filterDate.mosaic.clip"
        image_clip = MappingEntry("ee.image.clip", "L3_IMAGE_CLIP", 0.95, False)
        collection_clip = MappingEntry(
            "ee.imagecollection.clip", "L3_COLLECTION_CLIP", 0.95, False
        )

        decision = canonicalize_workflow_calls(
            candidate(normalized_core_chain=[raw]),
            evidence(core_call(raw_callee=raw, receiver_type="ee.image")),
            {
                "ee.image.clip": image_clip,
                "ee.imagecollection.clip": collection_clip,
            },
            frozenset({"ee.image.clip", "ee.imagecollection.clip"}),
        )

        self.assertEqual(decision.canonical_operator_sequence, ("ee.image.clip",))
        self.assertEqual(decision.l3_sequence, ("L3_IMAGE_CLIP",))

    def test_unknown_receiver_does_not_use_method_family_guessing(self):
        decision = canonicalize_workflow_calls(
            candidate(),
            evidence(core_call(resolution="unknown", receiver_type=None)),
            {"ee.image.select": mapping_entry()},
            frozenset({"ee.image.select"}),
        )

        self.assertEqual(decision.mapping_status, "unmapped_raw_call")
        self.assertIn("unmapped_raw_call:image.select", decision.fail_closed_reasons)

    def test_invalid_ordinals_fail_closed_before_call_mapping(self):
        cases = (
            ([-1], ["negative_normalized_core_call_ordinal"]),
            ([1, 1], ["duplicate_normalized_core_call_ordinal"]),
            ([2, 1], ["non_increasing_normalized_core_call_ordinals"]),
            ([1, 2], ["normalized_ordinal_chain_length_mismatch"]),
        )
        for ordinals, expected in cases:
            with self.subTest(ordinals=ordinals):
                decision = canonicalize_workflow_calls(
                    candidate(normalized_core_call_ordinals=ordinals),
                    evidence(core_call()),
                    {"ee.image.select": mapping_entry()},
                    frozenset({"ee.image.select"}),
                )
                self.assertEqual(decision.mapping_status, "evidence_mismatch")
                self.assertTrue(set(expected).issubset(decision.fail_closed_reasons))

    def test_missing_noncore_and_raw_mismatch_calls_fail_closed(self):
        scenarios = (
            (evidence(), "missing_call_ordinal:1"),
            (
                evidence(core_call(classification="support")),
                "call_not_core:1:support",
            ),
            (
                evidence(core_call(raw_callee="image.rename")),
                "raw_callee_mismatch:1",
            ),
        )
        for source_evidence, expected in scenarios:
            with self.subTest(expected=expected):
                decision = canonicalize_workflow_calls(
                    candidate(),
                    source_evidence,
                    {"ee.image.select": mapping_entry()},
                    frozenset({"ee.image.select"}),
                )
                self.assertEqual(decision.mapping_status, "evidence_mismatch")
                self.assertIn(expected, decision.fail_closed_reasons)

    def test_catalog_operator_without_l3_is_separate_gap(self):
        decision = canonicalize_workflow_calls(
            candidate(),
            evidence(core_call()),
            {},
            frozenset({"ee.image.select"}),
        )

        self.assertEqual(decision.mapping_status, "canonical_l3_gap")
        self.assertIn("canonical_l3_gap:ee.image.select", decision.fail_closed_reasons)

    def test_ambiguous_mapping_is_not_mapping_complete(self):
        decision = canonicalize_workflow_calls(
            candidate(),
            evidence(core_call()),
            {"ee.image.select": mapping_entry(ambiguity=True)},
            frozenset({"ee.image.select"}),
        )

        self.assertEqual(decision.mapping_status, "ambiguous_mapping")
        self.assertIn("ambiguous_mapping:ee.image.select", decision.fail_closed_reasons)

    def test_mapping_alias_absent_from_catalog_is_rejected(self):
        decision = canonicalize_workflow_calls(
            candidate(),
            evidence(core_call()),
            {"ee.image.select": mapping_entry()},
            frozenset(),
        )

        self.assertEqual(decision.mapping_status, "evidence_mismatch")
        self.assertIn(
            "canonical_operator_not_in_catalog:ee.image.select",
            decision.fail_closed_reasons,
        )

    def test_retained_core_support_call_is_not_silently_skipped(self):
        retained = candidate(
            normalized_core_call_ordinals=[3],
            normalized_core_chain=["image.sort"],
        )
        decision = canonicalize_workflow_calls(
            retained,
            evidence(core_call(ordinal=3, raw_callee="image.sort")),
            {},
            frozenset(),
        )

        self.assertEqual(decision.mapping_status, "support_classified_retained_call")
        self.assertIn(
            "support_classified_retained_call:image.sort",
            decision.fail_closed_reasons,
        )

    def test_image_collection_sort_is_a_mapped_output_relevant_operator(self):
        retained = candidate(
            normalized_core_call_ordinals=[3],
            normalized_core_chain=["collection.sort"],
        )
        sort_mapping = MappingEntry(
            canonical_operator="ee.imagecollection.sort",
            primary_l3="L3_03_09_07",
            mapping_confidence=0.8375,
            has_ambiguity=False,
        )

        decision = canonicalize_workflow_calls(
            retained,
            evidence(
                core_call(
                    ordinal=3,
                    raw_callee="collection.sort",
                    receiver_type="ee.imagecollection",
                )
            ),
            {"ee.imagecollection.sort": sort_mapping},
            frozenset({"ee.imagecollection.sort"}),
        )

        self.assertEqual(decision.mapping_status, "mapping_complete")
        self.assertEqual(
            decision.canonical_operator_sequence,
            ("ee.imagecollection.sort",),
        )
        self.assertEqual(decision.l3_sequence, ("L3_03_09_07",))

    def test_skip_authority_precedes_stale_property_get_mapping(self):
        stale_get = candidate(
            normalized_core_call_ordinals=[1, 4],
            normalized_core_chain=["image.select", "annualmetrics.get"],
        )
        wrong_mapping = MappingEntry(
            canonical_operator="ee.image.get",
            primary_l3="L3_03_09_05",
            mapping_confidence=0.73,
            has_ambiguity=False,
        )

        decision = canonicalize_workflow_calls(
            stale_get,
            evidence(
                core_call(),
                core_call(
                    ordinal=4,
                    raw_callee="annualmetrics.get",
                    receiver_type="ee.image",
                )
            ),
            {"ee.image.select": mapping_entry(), "ee.image.get": wrong_mapping},
            frozenset({"ee.image.select", "ee.image.get"}),
            skip_operators=frozenset({"ee.image.get"}),
        )

        self.assertEqual(decision.mapping_status, "mapping_complete")
        self.assertEqual(decision.canonical_operator_sequence, ("ee.image.select",))
        self.assertEqual(decision.l3_sequence, ("L3_01_02_01",))
        self.assertEqual(decision.fail_closed_reasons, ())
        self.assertEqual(decision.call_decisions[1].call_status, "skipped_support")
        self.assertIsNone(decision.call_decisions[1].canonical_operator)

    def test_filter_predicate_constructors_never_become_operator_labels(self):
        collection_filter = MappingEntry(
            "ee.imagecollection.filter", "L3_03_09_05", 0.95, False
        )
        false_predicate_mappings = {
            "ee.filter.lessthan": MappingEntry(
                "ee.filter.lessthan", "L3_FALSE_PREDICATE", 0.95, False
            ),
            "ee.filter.equals": MappingEntry(
                "ee.filter.equals", "L3_FALSE_PREDICATE", 0.95, False
            ),
        }
        decision = canonicalize_workflow_calls(
            candidate(
                normalized_core_call_ordinals=[1, 2, 3],
                normalized_core_chain=[
                    "ee.Filter.lessThan",
                    "collection.filter",
                    "ee.Filter.equals",
                ],
            ),
            evidence(
                core_call(
                    ordinal=1,
                    raw_callee="ee.Filter.lessThan",
                    resolution="ee_namespace",
                    receiver_type=None,
                ),
                core_call(
                    ordinal=2,
                    raw_callee="collection.filter",
                    receiver_type="ee.imagecollection",
                ),
                core_call(
                    ordinal=3,
                    raw_callee="ee.Filter.equals",
                    resolution="ee_namespace",
                    receiver_type=None,
                ),
            ),
            {
                "ee.imagecollection.filter": collection_filter,
                **false_predicate_mappings,
            },
            frozenset(
                {
                    "ee.imagecollection.filter",
                    "ee.filter.lessthan",
                    "ee.filter.equals",
                }
            ),
        )

        self.assertEqual(decision.mapping_status, "mapping_complete")
        self.assertEqual(
            decision.canonical_operator_sequence,
            ("ee.imagecollection.filter",),
        )
        self.assertEqual(decision.l3_sequence, ("L3_03_09_05",))
        self.assertEqual(decision.fail_closed_reasons, ())
        self.assertEqual(
            [call.call_status for call in decision.call_decisions],
            ["skipped_support", "mapped", "skipped_support"],
        )

    def test_nested_date_predicate_rewrites_collection_filter_semantics(self):
        generic = MappingEntry(
            "ee.imagecollection.filter", "L3_03_09_05", 0.95, False
        )
        date = MappingEntry(
            "ee.imagecollection.filterdate", "L3_03_09_01", 0.95, False
        )
        decision = canonicalize_workflow_calls(
            candidate(normalized_core_chain=["collection.filter"]),
            evidence(
                core_call(
                    raw_callee="collection.filter",
                    receiver_type="ee.imagecollection",
                    flags=("filter_predicate:date",),
                )
            ),
            {
                "ee.imagecollection.filter": generic,
                "ee.imagecollection.filterdate": date,
            },
            frozenset(
                {"ee.imagecollection.filter", "ee.imagecollection.filterdate"}
            ),
            skip_operators=frozenset({"ee.filter.date"}),
        )

        self.assertEqual(decision.mapping_status, "mapping_complete")
        self.assertEqual(
            decision.canonical_operator_sequence,
            ("ee.imagecollection.filterdate",),
        )
        self.assertEqual(decision.l3_sequence, ("L3_03_09_01",))


class GeeTypedL3MappingBuilderTests(unittest.TestCase):
    def test_builder_emits_deterministic_partition_and_hash_bound_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ast_dir = root / "ast"
            ast_dir.mkdir()
            ast_payload = json.dumps(simple_ast(), sort_keys=True).encode("utf-8")
            (ast_dir / f"{SOURCE_SHA}.json").write_bytes(ast_payload)

            accepted_path = root / "accepted.jsonl"
            accepted_path.write_text(
                json.dumps(
                    candidate(
                        normalized_core_call_ordinals=[1],
                        normalized_core_chain=["ee.Image.select"],
                    ),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            mappings_path = root / "id_mappings.json"
            mappings_path.write_text(
                json.dumps(
                    {
                        "mapping_metadata": {
                            "gee_to_l3": {
                                "ee.Image.select": {
                                    "primary_l3": "L3_01_02_01",
                                    "mapping_confidence": 0.95,
                                    "has_ambiguity": False,
                                }
                            }
                        },
                        "gee_op": {"ee.Image.select": {}},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            skip_path = root / "gee_skip_list.json"
            skip_path.write_text(
                json.dumps(
                    {"version": "test", "skip_operators": ["ee.image.get"]},
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            outputs = []
            for name in ("out-a", "out-b"):
                output_dir = root / name
                summary = build_typed_l3_mapping_census(
                    accepted_candidates_path=accepted_path,
                    ast_dir=ast_dir,
                    id_mappings_path=mappings_path,
                    skip_list_path=skip_path,
                    output_dir=output_dir,
                )
                self.assertEqual(summary["decision_count"], 1)
                self.assertEqual(summary["mapping_complete_count"], 1)
                self.assertEqual(summary["fail_closed_count"], 0)
                self.assertEqual(summary["training_rows_emitted"], 0)
                outputs.append(output_dir)

            names = {
                "typed_mapping_decisions.jsonl",
                "mapping_complete_candidates.jsonl",
                "mapping_fail_closed.jsonl",
                "summary.json",
                "report.md",
                "hash_ledger.json",
            }
            self.assertEqual({path.name for path in outputs[0].iterdir()}, names)
            for name in names:
                self.assertEqual(
                    (outputs[0] / name).read_bytes(),
                    (outputs[1] / name).read_bytes(),
                )

            ledger = json.loads((outputs[0] / "hash_ledger.json").read_text())
            self.assertEqual(
                ledger["inputs"]["accepted_candidates"]["sha256"],
                hashlib.sha256(accepted_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(len(ledger["inputs"]["ast_files"]), 1)
            self.assertEqual(
                ledger["inputs"]["skip_list"]["sha256"],
                hashlib.sha256(skip_path.read_bytes()).hexdigest(),
            )
            row = json.loads(
                (outputs[0] / "mapping_complete_candidates.jsonl")
                .read_text(encoding="utf-8")
                .strip()
            )
            self.assertEqual(row["mapping_status"], "mapping_complete")
            self.assertEqual(
                row["training_admission"],
                "not_granted_task_text_and_final_dedup_pending",
            )
            self.assertEqual(row["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
