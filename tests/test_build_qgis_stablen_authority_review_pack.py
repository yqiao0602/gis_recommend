import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_stablen_authority_review_pack import build_review_pack


class StableNAuthorityReviewPackTest(unittest.TestCase):
    def _write_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_review_pack_contains_only_four_conservative_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = root / "proposal.json"
            delta = root / "delta.json"
            gate = root / "gate.json"
            impact = root / "impact.json"
            out_dir = root / "out"

            self._write_json(
                proposal,
                {
                    "base_taxonomy": "stable98",
                    "base_class_count": 98,
                    "proposed_taxonomy": "stable101",
                    "proposed_class_count": 101,
                    "restored_l3": [
                        {"l3_code": "L3_01_05_02", "l3_name": "Repair Geometry", "l3_description": "Repair"},
                        {"l3_code": "L3_01_09_03", "l3_name": "Raster-Vector Conversion", "l3_description": "Raster"},
                        {"l3_code": "L3_01_10_01", "l3_name": "Project/Reproject", "l3_description": "CRS"},
                    ],
                },
            )
            self._write_json(
                delta,
                {
                    "operator_count": 4,
                    "excluded_boundary_operator_count": 2,
                    "restored_l3_mappings": {
                        "native:reprojectlayer": "L3_01_10_01",
                        "native:fixgeometries": "L3_01_05_02",
                        "gdal:polygonize": "L3_01_09_03",
                        "gdal:rasterize": "L3_01_09_03",
                    },
                    "excluded_boundary_entries": [
                        {"operator_id": "native:createspatialindex", "candidate_l3_code": "L3_01_07_01"},
                        {"operator_id": "native:saveselectedfeatures", "candidate_l3_code": "L3_07_04_01"},
                    ],
                },
            )
            self._write_json(
                gate,
                {
                    "status": "passed",
                    "accepted_operator_count": 4,
                    "reviewed_operators": {
                        op: {
                            "selected_samples": 3,
                            "unique_layer_hits": index,
                            "sample_refs": [
                                {
                                    "source_path": f"/home/yll/source_{index}_{op}.py",
                                    "line_start": index,
                                    "line_end": index + 1,
                                    "param_keys": ["INPUT"],
                                    "content_sha256": f"hash{index}",
                                }
                            ],
                        }
                        for index, op in enumerate(
                            [
                                "native:reprojectlayer",
                                "native:fixgeometries",
                                "gdal:polygonize",
                                "gdal:rasterize",
                            ],
                            start=1,
                        )
                    },
                },
            )
            self._write_json(
                impact,
                {
                    "stable98_draft": {"complete_records": 802, "complete_unique_chains": 270},
                    "increment_vs_stable98": {"records": 640, "unique_chains": 179},
                },
            )

            manifest = build_review_pack(
                proposal_path=proposal,
                delta_path=delta,
                source_review_gate_path=gate,
                impact_path=impact,
                output_dir=out_dir,
                date="2026-07-24",
            )

            summary = manifest["summary"]
            self.assertEqual(summary["review_row_count"], 4)
            self.assertEqual(summary["boundary_row_count"], 2)
            self.assertEqual(summary["proposed_taxonomy"], "stable101")
            self.assertEqual(summary["taxonomy_admission"], "not_granted")

            review_csv = out_dir / "stable101_authority_review.csv"
            boundary_json = out_dir / "stable101_boundary_sidecar.json"
            self.assertTrue(review_csv.is_file())
            self.assertTrue(boundary_json.is_file())

            with review_csv.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4)
            self.assertEqual(
                [row["operator_id"] for row in rows],
                [
                    "gdal:polygonize",
                    "gdal:rasterize",
                    "native:fixgeometries",
                    "native:reprojectlayer",
                ],
            )
            boundary_rows = json.loads(boundary_json.read_text(encoding="utf-8"))
            self.assertEqual(len(boundary_rows), 2)
            self.assertEqual(boundary_rows[0]["operator_id"], "native:createspatialindex")

    def test_review_pack_rejects_non_stable101_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = root / "proposal.json"
            delta = root / "delta.json"
            gate = root / "gate.json"
            impact = root / "impact.json"
            out_dir = root / "out"
            self._write_json(
                proposal,
                {
                    "base_taxonomy": "stable98",
                    "base_class_count": 98,
                    "proposed_taxonomy": "stable102",
                    "proposed_class_count": 102,
                    "restored_l3": [],
                },
            )
            self._write_json(delta, {"operator_count": 4, "excluded_boundary_operator_count": 2})
            self._write_json(gate, {"status": "passed", "accepted_operator_count": 4, "reviewed_operators": {}})
            self._write_json(impact, {"stable98_draft": {"complete_records": 1, "complete_unique_chains": 1}, "increment_vs_stable98": {"records": 1, "unique_chains": 1}})

            with self.assertRaises(ValueError):
                build_review_pack(
                    proposal_path=proposal,
                    delta_path=delta,
                    source_review_gate_path=gate,
                    impact_path=impact,
                    output_dir=out_dir,
                    date="2026-07-24",
                )


if __name__ == "__main__":
    unittest.main()
