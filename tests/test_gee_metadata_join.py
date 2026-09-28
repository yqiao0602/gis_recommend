from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.data import step7_prepare_v4_data  # noqa: E402


FIELDNAMES = ("File Name", "Task Type", "Task Name", "Task Description")


def _write_facts(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _row(name: str = "Task") -> dict[str, str]:
    return {
        "File Name": "script_1.txt",
        "Task Type": "Analysis",
        "Task Name": name,
        "Task Description": f"{name} description",
    }


def _task_meta(name: str = "Task", **extra: str) -> dict[str, str]:
    return {
        "task_type": "Analysis",
        "task_name": name,
        "task_description": f"{name} description",
        **extra,
    }


class GeeMetadataJoinTests(unittest.TestCase):
    def test_identical_duplicate_facts_are_deduplicated_with_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_facts(root / "facts_summary_a.csv", [_row()])
            _write_facts(root / "facts_summary_b.csv", [_row()])

            facts, diagnostics = step7_prepare_v4_data.load_facts_summary_with_diagnostics(root)

        self.assertEqual(list(facts), ["script_1"])
        self.assertEqual(facts["script_1"]["task_name"], "Task")
        self.assertEqual(diagnostics["input_rows"], 2)
        self.assertEqual(diagnostics["unique_keys"], 1)
        self.assertEqual(diagnostics["identical_duplicate_rows"], 1)
        self.assertEqual(diagnostics["conflicting_keys"], 0)

    def test_conflicting_duplicate_facts_fail_closed_with_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_facts(root / "facts_summary_a.csv", [_row("First")])
            _write_facts(root / "facts_summary_b.csv", [_row("Second")])

            with self.assertRaisesRegex(
                ValueError,
                r"script_1.*facts_summary_a\.csv:2.*facts_summary_b\.csv:2",
            ):
                step7_prepare_v4_data.load_facts_summary_with_diagnostics(root)

    def test_legacy_load_facts_summary_keeps_mapping_return_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_facts(root / "facts_summary.csv", [_row()])

            facts = step7_prepare_v4_data.load_facts_summary(root)

        self.assertIsInstance(facts, dict)
        self.assertEqual(facts["script_1"]["task_type"], "Analysis")

    def test_full_script_id_graft_compares_only_canonical_text_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "metadata.json"
            source.write_text(
                json.dumps({
                    "labeled_workflows": [
                        {
                            "metadata": {"script_id": "Batch_script_1"},
                            "task_metadata": _task_meta(quality_gate_note="first"),
                        },
                        {
                            "metadata": {"script_id": "Batch_script_1"},
                            "task_metadata": _task_meta(quality_gate_note="second"),
                        },
                    ]
                }),
                encoding="utf-8",
            )

            metadata, diagnostics = (
                step7_prepare_v4_data.load_task_metadata_source_with_diagnostics(source)
            )

        self.assertEqual(list(metadata), ["Batch_script_1"])
        self.assertEqual(diagnostics["identical_duplicate_rows"], 1)

    def test_full_script_id_graft_rejects_conflicting_core_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "metadata.json"
            source.write_text(
                json.dumps({
                    "labeled_workflows": [
                        {
                            "metadata": {"script_id": "Batch_script_1"},
                            "task_metadata": {
                                "task_type": "Analysis",
                                "task_name": "First",
                                "task_description": "First description",
                            },
                        },
                        {
                            "metadata": {"script_id": "Batch_script_1"},
                            "task_metadata": {
                                "task_type": "Analysis",
                                "task_name": "Second",
                                "task_description": "Second description",
                            },
                        },
                    ]
                }),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                r"Batch_script_1.*workflow_index:0.*workflow_index:1",
            ):
                step7_prepare_v4_data.load_task_metadata_source_with_diagnostics(source)

    def test_step7_records_per_workflow_join_authority_without_claiming_text_grounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "step6.json"
            input_file.write_text(
                json.dumps({
                    "labeled_workflows": [{
                        "l3_sequence": [-3, 0, 1, 2, -4],
                        "l3_codes": ["<START>", "L3_A", "L3_B", "L3_C", "<END>"],
                        "operator_sequence": ["op.a", "op.b", "op.c"],
                        "confidences": [0.95, 0.95, 0.95],
                        "ambiguity_flags": [False, False, False],
                        "metadata": {"script_id": "Batch_script_1"},
                    }]
                }),
                encoding="utf-8",
            )
            metadata_source = root / "metadata.json"
            metadata_source.write_text(
                json.dumps({
                    "labeled_workflows": [{
                        "metadata": {"script_id": "Batch_script_1"},
                        "task_metadata": {
                            "task_type": "Analysis",
                            "task_name": "Task",
                            "task_description": "Task description",
                        },
                    }]
                }),
                encoding="utf-8",
            )
            output_dir = root / "step7"

            step7_prepare_v4_data.main(SimpleNamespace(
                facts_dir=root,
                input_file=input_file,
                output_dir=output_dir,
                metadata_source_file=metadata_source,
            ))

            output = json.loads(
                (output_dir / "labeled_workflows_l3_v4.json").read_text(encoding="utf-8")
            )

        join = output["labeled_workflows"][0]["metadata"]["task_metadata_join"]
        self.assertEqual(join["match_authority"], "exact_full_script_id")
        self.assertEqual(join["text_provenance_authority"], "legacy_unknown")
        self.assertEqual(join["source_key"], "Batch_script_1")
        self.assertNotIn("source_by_key", output["statistics"]["metadata_join"])

    def test_duplicate_text_with_conflicting_provenance_degrades_to_legacy_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "metadata.json"
            source.write_text(
                json.dumps({
                    "labeled_workflows": [
                        {
                            "metadata": {
                                "script_id": "Batch_script_1",
                                "task_metadata_join": {
                                    "text_provenance_authority": "source_grounded"
                                },
                            },
                            "task_metadata": _task_meta(),
                        },
                        {
                            "metadata": {"script_id": "Batch_script_1"},
                            "task_metadata": _task_meta(),
                        },
                    ]
                }),
                encoding="utf-8",
            )

            _, diagnostics = (
                step7_prepare_v4_data.load_task_metadata_source_with_diagnostics(source)
            )

        self.assertEqual(diagnostics["provenance_conflict_keys"], 1)
        self.assertEqual(
            diagnostics["_text_authority_by_key"]["Batch_script_1"],
            "legacy_unknown",
        )


if __name__ == "__main__":
    unittest.main()
