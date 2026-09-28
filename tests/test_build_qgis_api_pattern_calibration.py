from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_api_pattern_calibration import (
    build_candidate_authorities,
    enrich_source_authorities,
    select_source_disjoint_packet,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(record_id: str, path: Path, patterns: list[str]) -> dict[str, object]:
    return {
        "record_id": record_id,
        "source_path": str(path),
        "source_sha256": _sha(path),
        "source_root_id": "fixture",
        "relative_path": path.name,
        "status": "pattern_candidate",
        "pattern_names": patterns,
        "step_count": 2,
        "steps": [
            {
                "name": "qgsvectorlayer",
                "line_start": 6,
                "line_end": 6,
                "pattern_names": ["vector_layer_io"],
            },
            {
                "name": "sink.addfeature",
                "line_start": 7,
                "line_end": 7,
                "pattern_names": ["sink_output"],
            },
        ],
        "candidate_l3_sequence": [],
        "training_admission": "not_granted",
        "training_row_emitted": False,
    }


class QgisApiPatternCalibrationTest(unittest.TestCase):
    def test_authority_enrichment_collapses_harvest_header_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = "layer = QgsVectorLayer(path)\nsink.addFeature(feature)\n"
            first = root / "first.py"
            second = root / "second.py"
            first.write_text(
                "# Source repo: owner/repo\n# Source path: workflow.py\n"
                "# Query used: first\n# Harvested at: t1\n\n" + body,
                encoding="utf-8",
            )
            second.write_text(
                "# Source repo: owner/repo\n# Source path: workflow.py\n"
                "# Query used: second\n# Harvested at: t2\n\n" + body,
                encoding="utf-8",
            )

            enriched, summary = enrich_source_authorities(
                [
                    _row("first", first, ["sink_output", "vector_layer_io"]),
                    _row("second", second, ["sink_output", "vector_layer_io"]),
                ],
                expected_rows=2,
            )

            self.assertEqual(summary["verified_source_sha256"], 2)
            self.assertEqual(summary["unique_normalized_source_bodies"], 1)
            self.assertEqual(
                enriched[0]["source_authority_key"],
                enriched[1]["source_authority_key"],
            )

    def test_candidate_cluster_and_packet_are_source_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows: list[dict[str, object]] = []
            families = ["sink_output", "vector_layer_io"]
            for index in range(8):
                path = root / f"source_{index}.py"
                path.write_text(
                    f"value_{index} = QgsVectorLayer(path)\n"
                    f"sink.addFeature(feature_{index})\n",
                    encoding="utf-8",
                )
                row = _row(str(index), path, families)
                row["steps"] = [
                    {
                        "name": "qgsvectorlayer",
                        "line_start": 1,
                        "line_end": 1,
                        "pattern_names": ["vector_layer_io"],
                    },
                    {
                        "name": "sink.addfeature",
                        "line_start": 2,
                        "line_end": 2,
                        "pattern_names": ["sink_output"],
                    },
                ]
                rows.append(row)

            enriched, _ = enrich_source_authorities(rows, expected_rows=8)
            authorities, cluster_summary = build_candidate_authorities(enriched)
            calibration, holdout, packet_summary = select_source_disjoint_packet(
                authorities,
                quota_per_family=2,
                risk_quota=0,
                seed=17,
            )

            calibration_keys = {row["source_authority_key"] for row in calibration}
            holdout_keys = {row["source_authority_key"] for row in holdout}
            self.assertFalse(calibration_keys & holdout_keys)
            self.assertEqual(cluster_summary["candidate_rows"], 8)
            self.assertEqual(packet_summary["authority_overlap"], 0)
            self.assertTrue(
                all(row["training_row_emitted"] is False for row in calibration + holdout)
            )
            self.assertTrue(
                all(row["candidate_l3_sequence"] == [] for row in calibration + holdout)
            )

    def test_source_sha_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text("sink.addFeature(feature)\n", encoding="utf-8")
            row = _row("bad", path, ["sink_output", "vector_layer_io"])
            row["source_sha256"] = "0" * 64

            with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
                enrich_source_authorities([row], expected_rows=1)


if __name__ == "__main__":
    unittest.main()
