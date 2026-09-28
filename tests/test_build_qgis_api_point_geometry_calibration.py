from __future__ import annotations

import unittest

from scripts.build_qgis_api_point_geometry_calibration import select_calibration_rows


def _row(index: int, *, signature: str = "a") -> dict:
    return {
        "semantic_family": "point_geometry_construction",
        "source_sha256": f"{index:064x}",
        "unit_id": f"unit-{index}",
        "producer_signature": [f"qgsgeometry.frompoint{signature}"],
        "mutation_signature": ["setgeometry"],
        "sink_signature": "addfeature",
    }


class BuildQgisApiPointGeometryCalibrationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
