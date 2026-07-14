import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from gis_recommend.data.qgis_pilot import (
    build_coverage_diagnostic_sample,
    classify_qgis_api_call,
    compact_api_trace,
    repair_evidence_order,
)
from scripts.build_qgis_api_aggregation_pilot import build_pilot
from scripts.run_qgis_api_aggregation_pilot import (
    AggregationContractError,
    aggregate_record,
    build_aggregation_prompt,
    build_request_fingerprint,
    require_api_key,
    run_batch,
    select_bounded_operator_catalog,
    validate_aggregation_response,
)


class QgisApiAggregationTests(unittest.TestCase):
    def setUp(self):
        self.compact_record = {
            "record_id": "pilot-1",
            "task_name": "Buffer roads",
            "task_description": "Create a 100 metre buffer around roads.",
            "ordering_quality": "fallback_extraction_order",
            "compact_steps": [
                {
                    "operation": "qgsvectorlayer.getfeatures",
                    "category": "data_access",
                    "semantic_family": None,
                    "evidence_ids": ["e1"],
                    "run_count": 1,
                },
                {
                    "operation": "qgsgeometry.buffer",
                    "category": "semantic_anchor",
                    "semantic_family": "buffer",
                    "evidence_ids": ["e2"],
                    "run_count": 1,
                },
            ],
            "infrastructure_counts": {"qgsproject.instance": 1},
        }
        self.operator_catalog = {
            "native:buffer": {
                "operator_id": "native:buffer",
                "official_name": "Buffer",
                "l3_code": "L3_02_01_01",
                "definition": "Creates a buffer around vector features.",
            }
        }
        self.taxonomy_codes = {"L3_02_01_01"}

    def _accepted_payload(self):
        return {
            "decision": "accept",
            "candidate_operators": [
                {
                    "operator_id": "native:buffer",
                    "l3_code": "L3_02_01_01",
                    "evidence_ids": ["e2"],
                    "confidence": 0.91,
                }
            ],
            "rejected_infrastructure": ["qgsproject.instance"],
            "unsupported_evidence_ids": ["e1"],
            "conflict_flags": [],
            "rationale": "The geometry buffer call directly supports the Buffer operator.",
        }

    def test_prompt_marks_text_untrusted_and_lists_bounded_evidence_and_operators(self):
        prompt = build_aggregation_prompt(
            self.compact_record,
            operator_catalog=self.operator_catalog,
        )

        self.assertIn("UNTRUSTED_TASK_CONTEXT", prompt)
        self.assertIn('"evidence_ids":["e2"]', prompt)
        self.assertIn("native:buffer", prompt)
        self.assertIn("Return reject instead of guessing", prompt)

    def test_validates_evidence_grounded_accepted_response(self):
        result = validate_aggregation_response(
            self._accepted_payload(),
            record=self.compact_record,
            operator_catalog=self.operator_catalog,
            taxonomy_codes=self.taxonomy_codes,
        )

        self.assertEqual(result["candidate_operators"][0]["operator_id"], "native:buffer")
        self.assertEqual(result["candidate_operators"][0]["evidence_ids"], ["e2"])

    def test_rejects_low_confidence_and_supported_unsupported_overlap(self):
        low_confidence = self._accepted_payload()
        low_confidence["candidate_operators"][0]["confidence"] = 0.69
        overlap = self._accepted_payload()
        overlap["unsupported_evidence_ids"] = ["e2"]

        for payload in (low_confidence, overlap):
            with self.subTest(payload=payload):
                with self.assertRaises(AggregationContractError):
                    validate_aggregation_response(
                        payload,
                        record=self.compact_record,
                        operator_catalog=self.operator_catalog,
                        taxonomy_codes=self.taxonomy_codes,
                    )

    def test_rejects_unknown_operator_evidence_and_forbidden_reasoning(self):
        cases = []
        unknown_operator = self._accepted_payload()
        unknown_operator["candidate_operators"][0]["operator_id"] = "native:invented"
        cases.append(unknown_operator)
        unknown_evidence = self._accepted_payload()
        unknown_evidence["candidate_operators"][0]["evidence_ids"] = ["not-present"]
        cases.append(unknown_evidence)
        forbidden_reasoning = self._accepted_payload()
        forbidden_reasoning["reasoning_content"] = "hidden chain of thought"
        cases.append(forbidden_reasoning)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(AggregationContractError):
                    validate_aggregation_response(
                        payload,
                        record=self.compact_record,
                        operator_catalog=self.operator_catalog,
                        taxonomy_codes=self.taxonomy_codes,
                    )

    def test_reject_decision_cannot_smuggle_candidate_operators(self):
        payload = self._accepted_payload()
        payload["decision"] = "reject"

        with self.assertRaises(AggregationContractError):
            validate_aggregation_response(
                payload,
                record=self.compact_record,
                operator_catalog=self.operator_catalog,
                taxonomy_codes=self.taxonomy_codes,
            )

        payload["candidate_operators"] = []
        payload["rejected_infrastructure"] = []
        validated = validate_aggregation_response(
            payload,
            record=self.compact_record,
            operator_catalog=self.operator_catalog,
            taxonomy_codes=self.taxonomy_codes,
        )
        self.assertEqual(validated["decision"], "reject")

    def test_request_fingerprint_is_stable_and_model_sensitive(self):
        prompt = build_aggregation_prompt(self.compact_record, operator_catalog=self.operator_catalog)
        first = build_request_fingerprint(record_id="pilot-1", prompt=prompt, model="gpt-5.6-luna")
        second = build_request_fingerprint(record_id="pilot-1", prompt=prompt, model="gpt-5.6-luna")
        changed = build_request_fingerprint(record_id="pilot-1", prompt=prompt, model="different-model")

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_bounded_candidates_prioritize_semantic_family_and_respect_limit(self):
        full_catalog = {
            **self.operator_catalog,
            "native:difference": {
                "operator_id": "native:difference",
                "official_name": "Difference",
                "l3_code": "L3_02_02_04",
                "definition": "Subtracts overlay features.",
            },
        }

        selected = select_bounded_operator_catalog(self.compact_record, full_catalog, limit=1)

        self.assertEqual(list(selected), ["native:buffer"])

    def test_bounded_candidates_cover_non_literal_semantic_family_names(self):
        full_catalog = {
            "native:fixgeometries": {
                "operator_id": "native:fixgeometries",
                "official_name": "Fix geometries",
                "l3_code": "L3_FIX",
            },
            "qgis:rastercalculator": {
                "operator_id": "qgis:rastercalculator",
                "official_name": "Raster calculator",
                "l3_code": "L3_RASTER_CALC",
            },
            "native:savefeatures": {
                "operator_id": "native:savefeatures",
                "official_name": "Save vector features",
                "l3_code": "L3_EXPORT",
            },
        }
        cases = {
            "geometry_validation": "native:fixgeometries",
            "raster_calculation": "qgis:rastercalculator",
            "vector_export": "native:savefeatures",
        }

        for family, expected in cases.items():
            record = {
                "compact_steps": [
                    {
                        "operation": "direct.api",
                        "category": "semantic_anchor",
                        "semantic_family": family,
                    }
                ]
            }
            with self.subTest(family=family):
                selected = select_bounded_operator_catalog(record, full_catalog, limit=5)
                self.assertIn(expected, selected)

    def test_api_key_has_no_fallback_to_other_provider_variables(self):
        with self.assertRaises(RuntimeError):
            require_api_key({"DEEPSEEK_API_KEY": "wrong", "OPENROUTER_API_KEY": "wrong"})
        self.assertEqual(require_api_key({"GGUUAI_API_KEY": "expected"}), "expected")

    def test_aggregate_record_persists_only_validated_contract_and_hashes(self):
        message = SimpleNamespace(content=json.dumps(self._accepted_payload()), refusal=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: response)
            )
        )

        result = aggregate_record(
            client,
            self.compact_record,
            operator_catalog=self.operator_catalog,
            taxonomy_codes=self.taxonomy_codes,
            model="gpt-5.6-luna",
        )

        self.assertEqual(result["proposal"]["decision"], "accept")
        self.assertEqual(len(result["request_fingerprint"]), 64)
        self.assertEqual(len(result["response_sha256"]), 64)
        self.assertNotIn("raw_response", result)
        self.assertNotIn("reasoning_content", json.dumps(result))

    def test_aggregate_record_rejects_refusal_malformed_json_and_reasoning_field(self):
        messages = [
            SimpleNamespace(content="{}", refusal="cannot comply"),
            SimpleNamespace(content="not-json", refusal=None),
            SimpleNamespace(
                content=json.dumps(self._accepted_payload()),
                refusal=None,
                reasoning_content="private reasoning",
            ),
        ]
        for message in messages:
            response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
            client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=lambda **kwargs: response)
                )
            )
            with self.subTest(message=message):
                with self.assertRaises(AggregationContractError):
                    aggregate_record(
                        client,
                        self.compact_record,
                        operator_catalog=self.operator_catalog,
                        taxonomy_codes=self.taxonomy_codes,
                        model="gpt-5.6-luna",
                    )

    def test_batch_resume_skips_an_existing_request_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "proposals.jsonl"
            prompt = build_aggregation_prompt(
                self.compact_record,
                operator_catalog=self.operator_catalog,
            )
            fingerprint = build_request_fingerprint(
                record_id="pilot-1",
                prompt=prompt,
                model="gpt-5.6-luna",
            )
            output_path.write_text(
                json.dumps({"request_fingerprint": fingerprint}) + "\n",
                encoding="utf-8",
            )
            calls = []
            client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs))
                )
            )

            summary = run_batch(
                client=client,
                records=[self.compact_record],
                full_catalog=self.operator_catalog,
                taxonomy_codes=self.taxonomy_codes,
                output_path=output_path,
                model="gpt-5.6-luna",
                candidate_limit=30,
                max_records=None,
            )

        self.assertEqual(calls, [])
        self.assertEqual(summary["outcomes"]["already_completed"], 1)

    def test_batch_retries_provider_exception_then_persists_validated_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "proposals.jsonl"
            message = SimpleNamespace(content=json.dumps(self._accepted_payload()), refusal=None)
            response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
            calls = []

            def create(**kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    raise TimeoutError("temporary provider timeout")
                return response

            client = SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=create))
            )

            summary = run_batch(
                client=client,
                records=[self.compact_record],
                full_catalog=self.operator_catalog,
                taxonomy_codes=self.taxonomy_codes,
                output_path=output_path,
                model="gpt-5.6-luna",
                candidate_limit=30,
                max_records=None,
                max_attempts=2,
            )
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(calls), 2)
        self.assertEqual(summary["validated_proposals"], 1)
        self.assertEqual(len(rows), 1)

    def test_coverage_sample_is_reproducible_balanced_and_excludes_t0(self):
        records = []
        for index in range(360):
            records.append(
                {
                    "record_id": f"r{index:03d}",
                    "evidence_tier": "T2" if index % 2 else "T3",
                    "eligible_for_llm": True,
                    "extraction_group": f"source_{index % 3}",
                    "primary_semantic_family": ["buffer", "difference", "crs_transform"][index % 3],
                    "ordering_quality": ["deterministic_statement_index", "fallback_extraction_order"][index % 2],
                }
            )
        records.append(
            {
                "record_id": "blocked",
                "evidence_tier": "T0",
                "eligible_for_llm": True,
                "extraction_group": "source_0",
                "primary_semantic_family": "buffer",
                "ordering_quality": "fallback_extraction_order",
            }
        )

        first = build_coverage_diagnostic_sample(records, size=300, seed=42)
        second = build_coverage_diagnostic_sample(records, size=300, seed=42)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 300)
        self.assertEqual(len({row["record_id"] for row in first}), 300)
        self.assertNotIn("blocked", {row["record_id"] for row in first})
        self.assertTrue(all(row["subset_type"] == "coverage_diagnostic" for row in first))

    def test_classifies_infrastructure_data_access_and_semantic_anchors(self):
        cases = {
            "qgsprocessingalgorithm.addparameter": ("infrastructure", None),
            "qgsproject.instance": ("infrastructure", None),
            "qgsmessagelog.logmessage": ("infrastructure", None),
            "qgsvectorlayer.getfeatures": ("data_access", None),
            "qgsfeature.setgeometry": ("data_access", None),
            "qgsgeometry.buffer": ("semantic_anchor", "buffer"),
            "qgsgeometry.difference": ("semantic_anchor", "difference"),
            "qgscoordinatetransform.transform": ("semantic_anchor", "crs_transform"),
            "qgsspatialindex": ("semantic_anchor", "spatial_index"),
        }
        for operation, expected in cases.items():
            with self.subTest(operation=operation):
                result = classify_qgis_api_call({"normalized_operation": operation})
                self.assertEqual((result["category"], result["semantic_family"]), expected)

    def test_repair_order_never_promotes_fallback_to_deterministic(self):
        steps = [
            {"step_id": "b", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
            {"step_id": "a", "statement_index": None, "normalized_operation": "qgsfeature.setgeometry"},
        ]

        result = repair_evidence_order(steps)

        self.assertEqual(result["ordering_quality"], "fallback_extraction_order")
        self.assertEqual([step["step_id"] for step in result["ordered_steps"]], ["b", "a"])
        self.assertTrue(all(step["ordering_source"] == "extraction_order" for step in result["ordered_steps"]))

    def test_repair_order_sorts_complete_statement_indices(self):
        steps = [
            {"step_id": "late", "statement_index": 20, "normalized_operation": "qgsfeature.setgeometry"},
            {"step_id": "early", "statement_index": 10, "normalized_operation": "qgsgeometry.buffer"},
        ]

        result = repair_evidence_order(steps)

        self.assertEqual(result["ordering_quality"], "deterministic_statement_index")
        self.assertEqual([step["step_id"] for step in result["ordered_steps"]], ["early", "late"])

    def test_compaction_run_length_encodes_and_summarizes_infrastructure(self):
        steps = [
            {"step_id": "1", "statement_index": None, "normalized_operation": "qgsprocessingalgorithm.addparameter"},
            {"step_id": "2", "statement_index": None, "normalized_operation": "qgsprocessingalgorithm.addparameter"},
            {"step_id": "3", "statement_index": None, "normalized_operation": "qgsvectorlayer.getfeatures"},
            {"step_id": "4", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
            {"step_id": "5", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
            {"step_id": "6", "statement_index": None, "normalized_operation": "qgsfeature.setgeometry"},
        ]

        compact = compact_api_trace(steps)

        self.assertEqual(compact["ordering_quality"], "fallback_extraction_order")
        self.assertEqual(compact["infrastructure_counts"]["qgsprocessingalgorithm.addparameter"], 2)
        self.assertNotIn(
            "qgsprocessingalgorithm.addparameter",
            [step["operation"] for step in compact["compact_steps"]],
        )
        buffer = next(step for step in compact["compact_steps"] if step["operation"] == "qgsgeometry.buffer")
        self.assertEqual(buffer["run_count"], 2)
        self.assertEqual(buffer["evidence_ids"], ["4", "5"])
        self.assertEqual(compact["semantic_anchor_families"], ["buffer"])
        self.assertTrue(compact["eligible_for_llm"])

    def test_infrastructure_only_trace_is_not_eligible(self):
        compact = compact_api_trace(
            [
                {"step_id": "1", "statement_index": None, "normalized_operation": "qgsproject.instance"},
                {"step_id": "2", "statement_index": None, "normalized_operation": "qgsmessagelog.logmessage"},
            ]
        )

        self.assertFalse(compact["eligible_for_llm"])
        self.assertEqual(compact["compact_steps"], [])

    def test_pilot_builder_streams_compacts_and_writes_bounded_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "readonly" / "ordered.jsonl"
            output = root / "writable" / "pilot"
            source.parent.mkdir(parents=True)
            rows = [
                {
                    "record_id": "eligible",
                    "evidence_tier": "T2",
                    "collision_state": "resolved",
                    "extraction_group": "source_a",
                    "task_name": "Buffer roads",
                    "task_description": "Create buffers",
                    "mapped_l3_chain": [],
                    "ordered_steps": [
                        {"step_id": "1", "statement_index": None, "normalized_operation": "qgsproject.instance"},
                        {"step_id": "2", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
                    ],
                },
                {
                    "record_id": "infrastructure",
                    "evidence_tier": "T2",
                    "collision_state": "resolved",
                    "extraction_group": "source_b",
                    "task_name": "Plugin setup",
                    "task_description": "Register parameters",
                    "mapped_l3_chain": [],
                    "ordered_steps": [
                        {"step_id": "1", "statement_index": None, "normalized_operation": "qgsprocessingalgorithm.addparameter"}
                    ],
                },
                {
                    "record_id": "collision",
                    "evidence_tier": "T0",
                    "collision_state": "unresolved_collision",
                    "extraction_group": "source_c",
                    "ordered_steps": [
                        {"step_id": "1", "statement_index": None, "normalized_operation": "qgsgeometry.difference"}
                    ],
                },
            ]
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            summary = build_pilot(
                ordered_evidence=source,
                output_dir=output,
                allowed_write_roots=[root / "writable"],
                sample_size=300,
                seed=42,
            )
            pilot_rows = [json.loads(line) for line in (output / "pilot_coverage_300.jsonl").read_text().splitlines()]

        self.assertEqual(summary["source_records"], 3)
        self.assertEqual(summary["eligible_records"], 1)
        self.assertEqual(summary["pilot_records"], 1)
        self.assertEqual(summary["shortfall"], 299)
        self.assertEqual(pilot_rows[0]["record_id"], "eligible")
        self.assertEqual(pilot_rows[0]["primary_semantic_family"], "buffer")


if __name__ == "__main__":
    unittest.main()
