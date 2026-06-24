from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_record(
    *,
    task_name: str,
    task_description: str,
    l3_codes: list[str],
    confidence: float,
    reasoning: str = "clear spatial operations",
    source: str = "llm_api_trace_to_l3",
    source_original: str = "llm_api_trace_to_l3",
) -> dict:
    content = [code for code in l3_codes if code not in {"<START>", "<END>"}]
    return {
        "l3_sequence": [-3, *range(1, len(content) + 1), -4],
        "l3_codes": ["<START>", *content, "<END>"],
        "operator_sequence": [],
        "task_metadata": {
            "task_type": "Unknown",
            "task_name": task_name,
            "task_description": task_description,
        },
        "source": source,
        "source_original": source_original,
        "_script_name": task_name.replace("QGIS script: ", ""),
        "_llm_reasoning": reasoning,
        "_llm_confidence": confidence,
    }


class ApiTraceL3CleaningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cleaner = _load_module(
            PROJECT_ROOT / "scripts" / "clean_api_trace_l3_training_data.py",
            "clean_api_trace_l3_training_data",
        )
        self.source_batch = _load_module(
            PROJECT_ROOT / "scripts" / "server_batch_source_to_l3.py",
            "server_batch_source_to_l3",
        )
        self.api_batch = _load_module(
            PROJECT_ROOT / "scripts" / "server_batch_api_to_l3.py",
            "server_batch_api_to_l3",
        )
        self.api_local = _load_module(
            PROJECT_ROOT / "scripts" / "llm_generate_l3_from_api_traces.py",
            "llm_generate_l3_from_api_traces",
        )

    def test_cleaner_rejects_placeholder_prompt_and_weak_trace(self) -> None:
        rows = [
            _make_record(
                task_name="QGIS script: script_56392",
                task_description="QGIS script: script_56392",
                l3_codes=["<START>", "L3_02_06_02", "<END>"],
                confidence=0.50,
                reasoning="no actual spatial operations are executed",
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["weak_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertIn("placeholder_prompt", result["rejected"][0]["reject_reason"])

    def test_cleaner_keeps_high_confidence_non_placeholder_rows(self) -> None:
        rows = [
            _make_record(
                task_name="Detect water boundaries",
                task_description="Detect water boundaries from raster and clip to extent",
                l3_codes=["<START>", "L3_03_01_01", "L3_02_02_06", "<END>"],
                confidence=0.94,
                reasoning="raster clip followed by vector clip is visible",
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 1)
        self.assertEqual(result["summary"]["rejected_count"], 0)
        self.assertEqual(result["clean"][0]["_training_quality"]["tier"], "clean")
        self.assertGreater(result["clean"][0]["_training_quality"]["sample_weight"], 0.0)

    def test_cleaner_marks_same_prompt_multi_label_as_conflict(self) -> None:
        rows = [
            _make_record(
                task_name="Clip parcel map",
                task_description="Clip parcel map to extent",
                l3_codes=["<START>", "L3_02_02_06", "<END>"],
                confidence=0.92,
                reasoning="clear clip operation",
            ),
            _make_record(
                task_name="Clip parcel map",
                task_description="Clip parcel map to extent",
                l3_codes=["<START>", "L3_02_01_01", "<END>"],
                confidence=0.91,
                reasoning="clear buffer operation",
            ),
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["conflict_count"], 2)
        self.assertEqual(len(result["conflicts"]), 2)

    def test_cleaner_rejects_task_description_code_mismatch(self) -> None:
        rows = [
            _make_record(
                task_name="Generate urban blocks by polygonizing networks",
                task_description="Generate urban blocks by polygonizing transportation networks",
                l3_codes=["<START>", "L3_01_02_03", "<END>"],
                confidence=0.95,
                reasoning=(
                    "The task description mentions polygonizing networks, "
                    "but the actual code only performs reprojection."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_incomplete_code_inferred_from_description(self) -> None:
        rows = [
            _make_record(
                task_name="Clip rooftop polygons",
                task_description="Reproject rooftop polygons, filter fields, and clip buildings to a boundary",
                l3_codes=["<START>", "L3_01_02_03", "L3_02_06_02", "L3_02_02_06", "<END>"],
                confidence=0.85,
                reasoning=(
                    "The provided code snippet is incomplete and does not show these operations, "
                    "but the task description is clear and consistent with these L3 codes."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_task_description_actual_code_disagreement(self) -> None:
        rows = [
            _make_record(
                task_name="Map match GPS tracks to road network",
                task_description="Map match GPS point trajectories to OpenStreetMap road networks",
                l3_codes=["<START>", "L3_02_06_02", "L3_02_01_01", "L3_03_01_02", "<END>"],
                confidence=0.95,
                reasoning=(
                    "The task description mentions map matching and reprojection, "
                    "but the actual code does not contain those steps; it performs a "
                    "buffer-based raster clipping workflow instead."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_workflow_inferred_from_task_description_only(self) -> None:
        rows = [
            _make_record(
                task_name="Calculate building heat load",
                task_description="Add fields and calculate heat load attributes for selected buildings",
                l3_codes=["<START>", "L3_01_02_01", "L3_01_02_06", "L3_07_04_01", "<END>"],
                confidence=0.85,
                reasoning=(
                    "The script processes building footprints by adding new fields and calculating "
                    "heat loads. The workflow is inferred from the task description and the presence "
                    "of field calculation and attribute names."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_source_from_different_script(self) -> None:
        rows = [
            _make_record(
                task_name="Convert OBJ to shapefiles",
                task_description="Convert a 3D OBJ file into georeferenced shapefiles",
                l3_codes=["<START>", "L3_07_04_05", "L3_01_02_03", "L3_07_04_01", "<END>"],
                confidence=0.75,
                reasoning=(
                    "The provided code snippet is incomplete and from a different tool, "
                    "but the task description clearly indicates these three high-level steps."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_based_on_task_description_alone(self) -> None:
        rows = [
            _make_record(
                task_name="Find most isolated point",
                task_description="Find the point with maximum nearest-neighbor distance and buffer it",
                l3_codes=["<START>", "L3_02_06_03", "L3_02_01_01", "<END>"],
                confidence=0.75,
                reasoning=(
                    "The provided code appears to be a line drawing command and does not match "
                    "the described algorithm. However, based on the task description alone, "
                    "the workflow would involve extracting an isolated point and buffering it."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_task_description_for_different_script(self) -> None:
        rows = [
            _make_record(
                task_name="Calculate polygon adjacency",
                task_description="Calculate adjacency between polygon features by shared boundaries",
                l3_codes=["<START>", "L3_02_05_06", "L3_01_02_06", "L3_07_04_01", "<END>"],
                confidence=0.95,
                reasoning=(
                    "The script creates points along each line and writes the output to a new vector file. "
                    "No buffering, intersection, or network graph construction is present in this code; "
                    "the task description appears to describe a different script."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_misleading_task_description_vs_actual_code(self) -> None:
        rows = [
            _make_record(
                task_name="Compute valley-floor width",
                task_description="Compute valley-floor width and valley centerline metrics",
                l3_codes=["<START>", "L3_02_07_01", "<END>"],
                confidence=0.95,
                reasoning=(
                    "The task description about valley-floor width computation is misleading "
                    "and does not match the actual script code, which is a simple geometry fix utility."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_unrelated_code_forcing_description_reliance(self) -> None:
        rows = [
            _make_record(
                task_name="Identify hydrological keypoints",
                task_description="Classify landforms and extract hollow keypoints from a DEM",
                l3_codes=["<START>", "L3_05_03_03", "L3_02_06_02", "L3_03_02_01", "<END>"],
                confidence=0.70,
                reasoning=(
                    "The script code provided is for network analysis and does not match the task. "
                    "Given the mismatch, I infer the likely steps from the task description. "
                    "The provided script code is unrelated to the task description, forcing reliance "
                    "on the description alone."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_different_script_or_context(self) -> None:
        rows = [
            _make_record(
                task_name="Topologise and optimise line ordering",
                task_description="Topologise lines and compute octilinear layouts",
                l3_codes=["<START>", "L3_01_02_03", "L3_01_03_04", "<END>"],
                confidence=0.85,
                reasoning=(
                    "No topological, ordering, or octilinear operations are present despite the task "
                    "description mentioning them; those appear to be from a different script or context."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_rejects_appears_to_be_different_script(self) -> None:
        rows = [
            _make_record(
                task_name="Filter and buffer population points",
                task_description="Filter population points, reproject, and create fixed-distance buffers",
                l3_codes=["<START>", "L3_02_06_02", "L3_01_02_03", "L3_02_01_01", "<END>"],
                confidence=0.90,
                reasoning=(
                    "The code snippet provided is incomplete and appears to be from a different script "
                    "(clip_raster.py), but the task description is clear and consistent with these L3 operations."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_code_mismatch")

    def test_cleaner_keeps_incomplete_code_when_operations_are_visible(self) -> None:
        rows = [
            _make_record(
                task_name="Reproject two point layers",
                task_description="Reproject supply POIs and study area layers to a metric CRS",
                l3_codes=["<START>", "L3_01_02_03", "L3_01_02_03", "<END>"],
                confidence=0.95,
                reasoning=(
                    "The script is incomplete but clearly shows these two reproject operations "
                    "as the primary workflow steps."
                ),
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 1)
        self.assertEqual(result["summary"]["rejected_count"], 0)

    def test_cleaner_rejects_text_l3_modality_mismatch(self) -> None:
        rows = [
            _make_record(
                task_name="Snap point features to nearest road network",
                task_description="Snap input point features to the nearest road segment in a vector network",
                l3_codes=["<START>", "L3_03_01_01", "<END>"],
                confidence=0.95,
                reasoning="clear raster clip operation",
            )
        ]

        result = self.cleaner.clean_api_trace_training_data(rows)

        self.assertEqual(result["summary"]["clean_count"], 0)
        self.assertEqual(result["summary"]["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reject_reason"], "task_l3_modality_mismatch")

    def test_server_prompt_no_longer_asks_for_guessing(self) -> None:
        self.assertIn("Do not guess", self.source_batch.SYSTEM_PROMPT)
        self.assertIn("return empty", self.source_batch.SYSTEM_PROMPT.lower())
        self.assertIn("Do not guess", self.api_batch.SYSTEM_PROMPT)
        self.assertIn("return empty", self.api_batch.SYSTEM_PROMPT.lower())

    def test_quality_gate_rejects_low_confidence_single_code(self) -> None:
        obj = {"l3_codes": ["L3_01_02_03"], "confidence": 0.55, "reasoning": "clear reproject"}

        source_ok, source_reason = self.source_batch.quality_gate(obj)
        api_ok, api_reason = self.api_batch.quality_gate(obj)

        self.assertFalse(source_ok, source_reason)
        self.assertFalse(api_ok, api_reason)

    def test_local_api_quality_gate_handles_string_confidence(self) -> None:
        obj = {
            "l3_codes": ["L3_02_06_01", "L3_02_06_02", "L3_02_06_03"],
            "confidence": "0.66",
            "reasoning": "attribute selection and extraction operations",
        }

        ok, reason = self.api_local.quality_gate(obj)

        self.assertFalse(ok, reason)
        self.assertIn("confidence", reason)

    def test_task_code_mismatch_patterns_are_tuples(self) -> None:
        for pattern in self.cleaner.TASK_CODE_MISMATCH_PATTERNS:
            self.assertIsInstance(pattern, tuple)
            self.assertTrue(pattern)
            for phrase in pattern:
                self.assertIsInstance(phrase, str)
                self.assertGreater(len(phrase.strip()), 1)

    def test_cleaner_cli_writes_report_and_outputs(self) -> None:
        rows = [
            _make_record(
                task_name="Clip parcel map",
                task_description="Clip parcel map to extent",
                l3_codes=["<START>", "L3_02_02_06", "<END>"],
                confidence=0.95,
                reasoning="clear clip operation",
            ),
            _make_record(
                task_name="QGIS script: script_90001",
                task_description="QGIS script: script_90001",
                l3_codes=["<START>", "L3_02_06_02", "<END>"],
                confidence=0.50,
                reasoning="no actual spatial operations are executed",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "API_trace_to_L3_TRAINING_FINAL.jsonl"
            input_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            out_dir = root / "cleaned"

            report = self.cleaner.clean_api_trace_file(input_path, out_dir)

            self.assertEqual(report["summary"]["clean_count"], 1)
            self.assertTrue((out_dir / "API_trace_to_L3_TRAINING_CLEAN.jsonl").exists())
            self.assertTrue((out_dir / "API_trace_to_L3_TRAINING_WEAK.jsonl").exists())
            self.assertTrue((out_dir / "API_trace_to_L3_TRAINING_REJECTED.jsonl").exists())
            self.assertTrue((out_dir / "api_trace_l3_cleaning_report.json").exists())


if __name__ == "__main__":
    unittest.main()
