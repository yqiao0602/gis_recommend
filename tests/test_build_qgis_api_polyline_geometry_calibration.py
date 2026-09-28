from __future__ import annotations

import unittest

from scripts.build_qgis_api_polyline_geometry_calibration import (
    build_full_population,
    select_calibration_rows,
)


def _row(index: int, *, signature: str = "a") -> dict:
    return {
        "semantic_family": "polyline_geometry_construction",
        "source_sha256": f"{index:064x}",
        "unit_id": f"unit-{index}",
        "producer_signature": [f"qgsgeometry.frompolyline{signature}"],
        "mutation_signature": ["setgeometry"],
        "sink_signature": "addfeature",
    }


class BuildQgisApiPolylineGeometryCalibrationTest(unittest.TestCase):
    def test_selects_unique_source_shas_and_round_robins_signatures(self) -> None:
        rows = [_row(index, signature="a" if index % 2 else "b") for index in range(8)]
        rows.append({**rows[0], "unit_id": "duplicate-copy"})

        result = select_calibration_rows(rows, sample_size=6, seed=7)

        self.assertEqual(len(result), 6)
        self.assertEqual(len({row["source_sha256"] for row in result}), 6)
        self.assertEqual([row["target_index"] for row in result], list(range(1, 7)))
        self.assertTrue(all(not row["training_row_emitted"] for row in result))

    def test_rejects_insufficient_source_support(self) -> None:
        with self.assertRaisesRegex(ValueError, "source support"):
            select_calibration_rows([_row(1)], sample_size=2, seed=7)

    def test_full_population_keeps_distinct_terminal_units_from_one_source(self) -> None:
        rows = [_row(1), {**_row(1), "unit_id": "second-unit"}]

        result = build_full_population(rows)

        self.assertEqual(len(result), 2)
        self.assertEqual(len({row["source_sha256"] for row in result}), 1)
        self.assertTrue(all("full_population" in row["schema"] for row in result))

    def test_supports_another_geometry_family_without_source_leakage(self) -> None:
        rows = [
            {**_row(index), "semantic_family": "polygon_geometry_construction"}
            for index in range(6)
        ]

        result = select_calibration_rows(
            rows, sample_size=4, seed=7, family="polygon_geometry_construction"
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(len({row["source_sha256"] for row in result}), 4)
        self.assertIn("polygon_geometry_calibration", result[0]["schema"])


if __name__ == "__main__":
    unittest.main()
