from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.open_landing_report import (
    parse_open_landing_csv,
    chain_diversity,
    build_report,
    render_markdown,
)


IO_TYPES = {
    "native:buffer": {"inputs": ["vector"], "outputs": ["vector"], "name": "Buffer"},
    "native:clip": {"inputs": ["vector"], "outputs": ["vector"], "name": "Clip"},
    "gdal:warpreproject": {"inputs": ["raster"], "outputs": ["raster"], "name": "Warp"},
}


# Mimics the real outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv header.
CSV_TEXT = (
    "task,modality,modality_match,top1_ops,top1_names,top1_quality,n_unique,grade,notes\n"
    "Buffer roads and clip,vec,V,native:buffer -> native:clip,Buffer -> Clip,0.65,5,A,ok\n"
    '"Clip raster, then sample",rast,V,gdal:warpreproject -> gdal:cliprasterbymasklayer,W -> C,0.65,5,C,needs zonal\n'
)


def _write_csv(tmpdir: str) -> Path:
    p = Path(tmpdir) / "open_landing_results.csv"
    p.write_text(CSV_TEXT, encoding="utf-8")
    return p


class ParseOpenLandingCsvTests(unittest.TestCase):
    def test_parse_extracts_chain_task_intent_modality_and_grade(self):
        """Each row -> item with predicted_chain (top1_ops split on ' -> '),
        TASK-INTENT modality (vec/rast/mixed column, not chain-derived), grade,
        and a unique task_id."""
        with tempfile.TemporaryDirectory() as d:
            items = parse_open_landing_csv(_write_csv(d))

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["predicted_chain"], ["native:buffer", "native:clip"])
        self.assertEqual(items[0]["modality"], "vec")
        self.assertEqual(items[0]["grade"], "A")
        # csv quoting respected (comma inside the quoted task field)
        self.assertEqual(items[1]["task"], "Clip raster, then sample")
        self.assertEqual(items[1]["predicted_chain"], ["gdal:warpreproject", "gdal:cliprasterbymasklayer"])
        self.assertEqual(items[1]["modality"], "rast")
        self.assertEqual(items[1]["grade"], "C")
        # task_id present and unique
        self.assertNotEqual(items[0]["task_id"], items[1]["task_id"])


class ChainDiversityTests(unittest.TestCase):
    def test_chain_diversity_quantifies_template_collapse(self):
        """Per group: how many DISTINCT top-1 chains the system emits. A low
        unique_ratio = template collapse (many tasks -> identical chain)."""
        records = [
            {"modality": "vec", "predicted_chain": ["a", "b"]},
            {"modality": "vec", "predicted_chain": ["a", "b"]},   # dup
            {"modality": "vec", "predicted_chain": ["c"]},
            {"modality": "rast", "predicted_chain": ["d"]},
        ]
        div = chain_diversity(records, "modality")
        self.assertEqual(div["vec"]["n"], 3)
        self.assertEqual(div["vec"]["unique"], 2)
        self.assertAlmostEqual(div["vec"]["unique_ratio"], 2 / 3)
        self.assertEqual(div["rast"]["n"], 1)
        self.assertAlmostEqual(div["rast"]["unique_ratio"], 1.0)


class BuildReportTests(unittest.TestCase):
    def test_build_report_breaks_down_by_modality_grade_and_diversity(self):
        """build_report scores items (task-intent modality preserved) and returns
        overall + by_modality + by_grade + diversity_by_modality."""
        items = [
            {"task_id": "ol001", "task": "t1", "predicted_chain": ["native:buffer", "native:clip"], "modality": "vec", "grade": "A"},
            {"task_id": "ol002", "task": "t2", "predicted_chain": ["native:buffer", "native:clip"], "modality": "vec", "grade": "C"},  # dup chain
            {"task_id": "ol003", "task": "t3", "predicted_chain": ["gdal:warpreproject"], "modality": "rast", "grade": "B"},
        ]
        rep = build_report(items, IO_TYPES)

        self.assertEqual(rep["n"], 3)
        # task-intent modality preserved (not chain-derived)
        self.assertEqual(rep["by_modality"]["vec"]["n"], 2)
        self.assertEqual(rep["by_modality"]["rast"]["n"], 1)
        self.assertAlmostEqual(rep["by_modality"]["vec"]["operator_validity"], 1.0)
        # grade view present (the correctness-tracking probe)
        self.assertEqual(set(rep["by_grade"]), {"A", "B", "C"})
        # template collapse quantified: vec = 2 tasks, 1 unique chain -> 0.5
        self.assertAlmostEqual(rep["diversity_by_modality"]["vec"]["unique_ratio"], 0.5)


class RenderMarkdownTests(unittest.TestCase):
    def test_render_markdown_has_modality_grade_and_diversity_sections(self):
        items = [
            {"task_id": "ol001", "task": "t1", "predicted_chain": ["native:buffer", "native:clip"], "modality": "vec", "grade": "A"},
            {"task_id": "ol002", "task": "t2", "predicted_chain": ["gdal:warpreproject"], "modality": "rast", "grade": "C"},
        ]
        md = render_markdown(build_report(items, IO_TYPES))
        self.assertIsInstance(md, str)
        low = md.lower()
        self.assertIn("modality", low)
        self.assertIn("grade", low)
        self.assertIn("diversity", low)
        self.assertIn("vec", md)


if __name__ == "__main__":
    unittest.main()
