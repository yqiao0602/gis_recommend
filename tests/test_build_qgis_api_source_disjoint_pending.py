from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.build_qgis_api_source_disjoint_pending import _with_context, build_pending


class BuildQgisApiSourceDisjointPendingTest(unittest.TestCase):
    def test_source_window_includes_upstream_evidence_and_terminal_steps(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(
                "".join(f"line_{index}\n" for index in range(1, 13)),
                encoding="utf-8",
            )
            contextual = _with_context(
                {
                    "source_path": str(path),
                    "upstream_calls": [{"line_start": 2, "line_end": 2}],
                    "steps": [{"line_start": 10, "line_end": 10}],
                }
            )

        text = "\n".join(window["text"] for window in contextual["source_windows"])
        self.assertIn("line_2", text)
        self.assertIn("line_10", text)

    def test_rebases_harvest_aliases_and_freezes_disjoint_pending_splits(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for index, body in enumerate(("value = 1\n", "value = 2\n", "value = 3\n")):
                path = root / f"source-{index}.py"
                path.write_text(body, encoding="utf-8")
                rows.append(
                    {
                        "candidate_id": f"candidate-{index}",
                        "unit_id": f"unit-{index}",
                        "source_authority_key": f"declared-{index}",
                        "normalized_source_body_sha256": f"declared-{index}",
                        "source_path": str(path),
                        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "source_root_id": "fixture",
                        "training_row_emitted": False,
                    }
                )

            calibration, holdout, summary = build_pending(rows, seed=7)

        self.assertEqual(len(calibration) + len(holdout), 3)
        self.assertTrue(
            all(
                row["review_status"] == "pending_human_boundary_review"
                for row in calibration + holdout
            )
        )
        self.assertEqual(summary["split"]["source_authority_overlap"], 0)
        self.assertEqual(summary["split"]["unit_id_overlap"], 0)
        self.assertEqual(summary["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
