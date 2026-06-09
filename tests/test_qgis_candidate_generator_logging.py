from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.operators.qgis_candidate_generator import (  # noqa: E402
    L3ToQGISMapping,
    QGISCandidateGenerator,
)


def _fake_load_semantic_scores(self):
    self.semantic_scores = {}
    self.discovered_mappings = {}


def _fake_load_io_types(self):
    self.io_types = {}
    self.io_types_path = PROJECT_ROOT / "outputs_v2" / "qgis_operator_io_types.json"
    self.io_metadata_profile = {
        "version_family": "v2",
        "path": str(self.io_types_path),
        "exists": False,
        "fallback_status": "missing",
    }


class QGISCandidateGeneratorLoggingTests(unittest.TestCase):
    def test_generate_candidates_is_quiet_when_verbose_disabled(self):
        with patch.object(
            QGISCandidateGenerator,
            "_load_mappings",
            return_value={"L3_A": [L3ToQGISMapping("L3_A", "native:buffer", 0.9, "Buffer")]},
        ), patch.object(QGISCandidateGenerator, "_load_semantic_scores", _fake_load_semantic_scores), patch.object(
            QGISCandidateGenerator, "_load_io_types", _fake_load_io_types
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                generator = QGISCandidateGenerator(mapping_dir=".", beam_width=1, verbose=False)
                candidates = generator.generate_candidates(["L3_A"], top_k=1)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(output.getvalue().strip(), "")

    def test_generate_candidates_emits_detailed_logs_when_verbose_enabled(self):
        with patch.object(
            QGISCandidateGenerator,
            "_load_mappings",
            return_value={"L3_A": [L3ToQGISMapping("L3_A", "native:buffer", 0.9, "Buffer")]},
        ), patch.object(QGISCandidateGenerator, "_load_semantic_scores", _fake_load_semantic_scores), patch.object(
            QGISCandidateGenerator, "_load_io_types", _fake_load_io_types
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                generator = QGISCandidateGenerator(mapping_dir=".", beam_width=1, verbose=True)
                candidates = generator.generate_candidates(["L3_A"], top_k=1)

        self.assertEqual(len(candidates), 1)
        text = output.getvalue()
        self.assertIn("[生成候选]", text)
        self.assertIn("步骤 1/1", text)

    def test_candidate_exposes_score_components_for_decision_trace(self):
        with patch.object(
            QGISCandidateGenerator,
            "_load_mappings",
            return_value={"L3_A": [L3ToQGISMapping("L3_A", "native:buffer", 0.9, "Buffer")]},
        ), patch.object(QGISCandidateGenerator, "_load_semantic_scores", _fake_load_semantic_scores), patch.object(
            QGISCandidateGenerator, "_load_io_types", _fake_load_io_types
        ):
            generator = QGISCandidateGenerator(mapping_dir=".", beam_width=1, verbose=False)
            candidates = generator.generate_candidates(["L3_A"], top_k=1)

        self.assertEqual(len(candidates), 1)
        components = candidates[0].score_components
        self.assertEqual(components["final_score"], candidates[0].score)
        self.assertEqual(components["mean_mapping_score"], 0.9)
        self.assertEqual(components["mean_io_factor"], 1.0)
        self.assertEqual(components["io_metadata_profile"]["version_family"], "v2")


if __name__ == "__main__":
    unittest.main()
