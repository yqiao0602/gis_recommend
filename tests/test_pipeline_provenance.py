from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.data import pipeline_runner, step6_label_with_l3, step7_prepare_v4_data, step8_clean_v4_data


TEST_TMP_ROOT = PROJECT_ROOT / "codex_tmp" / "unittest_tmp" / "pipeline_provenance"


def _load_audit_module():
    module_path = PROJECT_ROOT / "scripts" / "audit_pipeline_outputs.py"
    spec = importlib.util.spec_from_file_location("audit_pipeline_outputs", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_mapping(path: Path) -> None:
    data = {
        "metadata": {"version": "test-v1", "l3_vocab_size": 3},
        "gee_op": {"ee.Image.add": 0, "ee.Image.subtract": 1, "ee.Image.multiply": 2},
        "qgis_op": {},
        "l3": {"L3_A": 0, "L3_B": 1, "L3_C": 2},
        "l2": {},
        "l1": {},
        "mapping_metadata": {
            "gee_to_l3": {
                "ee.Image.add": {
                    "primary_l3": "L3_A",
                    "all_candidates": [{"l3_code": "L3_A", "confidence": 0.9}],
                },
                "ee.Image.subtract": {
                    "primary_l3": "L3_B",
                    "all_candidates": [{"l3_code": "L3_B", "confidence": 0.8}],
                },
                "ee.Image.multiply": {
                    "primary_l3": "L3_C",
                    "all_candidates": [{"l3_code": "L3_C", "confidence": 0.7}],
                },
            },
            "qgis_to_l3": {
                "qgis:buffer": {"primary_l3": "L3_A"},
            },
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_skip_list(path: Path) -> None:
    path.write_text(
        json.dumps({"version": "skip-test-v1", "skip_operators": ["ee.Image.metadata"]}),
        encoding="utf-8",
    )


def _expected_provenance(mapping_path: Path, skip_path: Path) -> dict:
    return {
        "schema": "gis_recommend.pipeline_provenance.v1",
        "id_mappings": {
            "path": str(mapping_path.resolve()),
            "sha256": _sha256(mapping_path),
            "version": "test-v1",
            "l3_vocab_size": 3,
            "metadata_l3_vocab_size": 3,
            "gee_to_l3_count": 3,
            "gee_to_l3_total": 3,
            "qgis_to_l3_count": 1,
        },
        "gee_skip_list": {
            "path": str(skip_path.resolve()),
            "sha256": _sha256(skip_path),
            "version": "skip-test-v1",
            "skip_operator_count": 1,
        },
    }


def _step8_workflow() -> dict:
    return {
        "l3_sequence": [-3, 0, 1, 2, -4],
        "l3_codes": ["<START>", "L3_A", "L3_B", "L3_C", "<END>"],
        "operator_sequence": ["ee.Image.add", "ee.Image.subtract", "ee.Image.multiply"],
        "confidences": [0.9, 0.8, 0.7],
        "ambiguity_flags": [False, False, False],
        "metadata": {"script_id": "Workflowoutput1_script_1"},
        "task_metadata": {"task_type": "Analysis", "task_name": "Demo", "task_description": ""},
    }


class PipelineProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_TMP_ROOT / self._testMethodName
        self.root.mkdir(parents=True, exist_ok=True)
        self.mapping_path = self.root / "id_mappings_v2.json"
        self.skip_path = self.root / "gee_skip_list_v2.json"
        _write_mapping(self.mapping_path)
        _write_skip_list(self.skip_path)

    def test_step6_writes_mapping_and_skip_list_provenance(self):
        workflow_path = self.root / "workflow_sequences.json"
        workflow_path.write_text(
            json.dumps(
                {
                    "workflow_dags": [
                        {
                            "script_id": "Workflowoutput1_script_1",
                            "nodes": [
                                {"operator": "ee.Image.add"},
                                {"operator": "ee.Image.metadata"},
                                {"operator": "ee.Image.subtract"},
                                {"operator": "ee.Image.multiply"},
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output_dir = self.root / "step6"

        step6_label_with_l3.main(
            SimpleNamespace(
                workflow_sequences=workflow_path,
                id_mappings=self.mapping_path,
                gee_mapping_dir=self.root,
                output_dir=output_dir,
                skip_list=self.skip_path,
                verbose=False,
                quiet=True,
            )
        )

        output = json.loads((output_dir / "labeled_workflows_l3.json").read_text(encoding="utf-8"))

        self.assertEqual(output["provenance"], _expected_provenance(self.mapping_path, self.skip_path))

    def test_step7_preserves_step6_provenance_for_step8_gate(self):
        provenance = _expected_provenance(self.mapping_path, self.skip_path)
        input_file = self.root / "labeled_workflows_l3.json"
        input_file.write_text(
            json.dumps({"labeled_workflows": [_step8_workflow()], "provenance": provenance}, ensure_ascii=False),
            encoding="utf-8",
        )
        metadata_source = self.root / "metadata_source.json"
        metadata_source.write_text(
            json.dumps(
                {
                    "labeled_workflows": [
                        {
                            "metadata": {"script_id": "Workflowoutput1_script_1"},
                            "task_metadata": {
                                "task_type": "Analysis",
                                "task_name": "Demo",
                                "task_description": "",
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output_dir = self.root / "step7"

        step7_prepare_v4_data.main(
            SimpleNamespace(
                facts_dir=self.root,
                input_file=input_file,
                output_dir=output_dir,
                metadata_source_file=metadata_source,
            )
        )

        output = json.loads((output_dir / "labeled_workflows_l3_v4.json").read_text(encoding="utf-8"))
        self.assertEqual(output["provenance"], provenance)

    def test_step8_records_missing_provenance_without_blocking(self):
        input_file = self.root / "labeled_workflows_l3_v4.json"
        input_file.write_text(
            json.dumps({"labeled_workflows": [_step8_workflow()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        output_dir = self.root / "step8"

        step8_clean_v4_data.main(
            SimpleNamespace(
                input_file=input_file,
                output_dir=output_dir,
                id_mappings=self.mapping_path,
                skip_list=self.skip_path,
            )
        )

        output = json.loads((output_dir / "labeled_workflows_l3_v4_cleaned.json").read_text(encoding="utf-8"))
        self.assertEqual(output["statistics"]["provenance_warnings"], ["missing_provenance"])
        self.assertFalse(output["statistics"]["provenance_validated"])

    def test_step8_records_stale_mapping_hash_without_blocking(self):
        input_file = self.root / "labeled_workflows_l3_v4.json"
        stale = _expected_provenance(self.mapping_path, self.skip_path)
        stale["id_mappings"]["sha256"] = "0" * 64
        input_file.write_text(
            json.dumps(
                {"labeled_workflows": [_step8_workflow()], "provenance": stale},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output_dir = self.root / "step8"

        step8_clean_v4_data.main(
            SimpleNamespace(
                input_file=input_file,
                output_dir=output_dir,
                id_mappings=self.mapping_path,
                skip_list=self.skip_path,
            )
        )

        output = json.loads((output_dir / "labeled_workflows_l3_v4_cleaned.json").read_text(encoding="utf-8"))
        self.assertIn("provenance_mismatch:id_mappings.sha256", output["statistics"]["provenance_warnings"])
        self.assertFalse(output["statistics"]["provenance_validated"])

    def test_step8_preserves_validated_provenance_in_output(self):
        provenance = _expected_provenance(self.mapping_path, self.skip_path)
        input_file = self.root / "labeled_workflows_l3_v4.json"
        input_file.write_text(
            json.dumps(
                {"labeled_workflows": [_step8_workflow()], "provenance": provenance},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output_dir = self.root / "step8"

        step8_clean_v4_data.main(
            SimpleNamespace(
                input_file=input_file,
                output_dir=output_dir,
                id_mappings=self.mapping_path,
                skip_list=self.skip_path,
            )
        )

        output = json.loads((output_dir / "labeled_workflows_l3_v4_cleaned.json").read_text(encoding="utf-8"))
        self.assertEqual(output["provenance"], provenance)
        self.assertTrue(output["statistics"]["provenance_validated"])
        self.assertEqual(output["statistics"]["provenance_warnings"], [])

    def test_audit_reports_missing_required_step8_provenance(self):
        audit = _load_audit_module()
        outputs_dir = self.root / "outputs_v2"
        step8_dir = outputs_dir / "pipeline" / "step8"
        step8_dir.mkdir(parents=True, exist_ok=True)
        (step8_dir / "labeled_workflows_l3_v4_cleaned.json").write_text(
            json.dumps({"labeled_workflows": [_step8_workflow()]}, ensure_ascii=False),
            encoding="utf-8",
        )

        report, _ = audit.audit_step(
            outputs_dir,
            8,
            None,
            audit.load_current_mapping(self.mapping_path),
            audit.load_skip_list(self.skip_path),
            mapping_file=self.mapping_path,
            skip_file=self.skip_path,
            require_provenance=True,
        )

        self.assertIn("missing_provenance", report["warnings"])

    def test_audit_fail_on_warning_is_report_only(self):
        audit = _load_audit_module()
        outputs_dir = self.root / "outputs_v2"
        step8_dir = outputs_dir / "pipeline" / "step8"
        step8_dir.mkdir(parents=True, exist_ok=True)
        (step8_dir / "labeled_workflows_l3_v4_cleaned.json").write_text(
            json.dumps({"labeled_workflows": [_step8_workflow()]}, ensure_ascii=False),
            encoding="utf-8",
        )

        argv = [
            "audit_pipeline_outputs.py",
            "--outputs-dir",
            str(outputs_dir),
            "--id-mappings",
            str(self.mapping_path),
            "--skip-list",
            str(self.skip_path),
            "--require-provenance",
            "--fail-on-warning",
        ]
        with patch.object(sys, "argv", argv):
            audit.main()

        report_path = outputs_dir / "pipeline" / "audit" / "pipeline_quality_audit.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(report["warnings"])

    def test_pipeline_runner_passes_selected_mapping_inputs_to_step8(self):
        runner = pipeline_runner.PipelineRunner(
            outputs_dir=self.root / "custom_outputs",
            id_mappings=self.mapping_path,
            skip_list=self.skip_path,
        )

        args = runner._build_args(8)

        self.assertEqual(args.id_mappings, self.mapping_path)
        self.assertEqual(args.skip_list, self.skip_path)


if __name__ == "__main__":
    unittest.main()
