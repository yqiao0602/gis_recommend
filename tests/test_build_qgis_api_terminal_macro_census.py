from __future__ import annotations

import unittest

from scripts.build_qgis_api_terminal_macro_census import (
    build_family_census,
    build_semantic_rollup_census,
    build_terminal_units,
)


def _row(sha: str, producer: str = "geom.combine") -> dict:
    return {
        "record_id": sha,
        "source_path": f"/{sha}.py",
        "source_sha256": sha,
        "source_root_id": "fixture",
        "source_verification": "verified_sha256",
        "status": "pattern_candidate",
        "steps": [
            {"name": producer, "line_start": 10, "line_end": 10},
            {"name": "output.setGeometry", "line_start": 12, "line_end": 12},
            {"name": "sink.addFeature", "line_start": 13, "line_end": 13},
        ],
    }


class BuildQgisApiTerminalMacroCensusTest(unittest.TestCase):
    def test_builds_composite_terminal_macro(self) -> None:
        units = build_terminal_units(_row("a"), maximum_lines=80, maximum_steps=16)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["producer_signature"], ["combine"])
        self.assertEqual(units[0]["mutation_signature"], ["setgeometry"])
        self.assertEqual(units[0]["sink_signature"], "addfeature")
        self.assertFalse(units[0]["training_row_emitted"])

    def test_requires_specific_producer_and_mutation(self) -> None:
        row = _row("a")
        row["steps"][0]["name"] = "feature.geometry"

        self.assertEqual(
            build_terminal_units(row, maximum_lines=80, maximum_steps=16), []
        )

    def test_prioritizes_unfinished_family_at_support_threshold(self) -> None:
        units = [
            build_terminal_units(_row(str(index)), maximum_lines=80, maximum_steps=16)[0]
            for index in range(3)
        ]

        families, priority, summary = build_family_census(units, minimum_support=3)

        self.assertEqual(families[0]["review_priority"], "source_replay_required")
        self.assertEqual(len(priority), 3)
        self.assertEqual(summary["priority_family_count"], 1)

    def test_defers_completed_semantic_overlap(self) -> None:
        units = [
            build_terminal_units(
                _row(str(index), "geom.difference"),
                maximum_lines=80,
                maximum_steps=16,
            )[0]
            for index in range(3)
        ]

        families, priority, _ = build_family_census(units, minimum_support=3)

        self.assertEqual(
            families[0]["review_priority"], "defer_completed_semantic_overlap"
        )
        self.assertEqual(priority, [])

    def test_rolls_point_factory_variants_into_one_semantic_family(self) -> None:
        units = [
            build_terminal_units(
                _row("a", "QgsGeometry.fromPoint"),
                maximum_lines=80,
                maximum_steps=16,
            )[0],
            build_terminal_units(
                _row("b", "QgsGeometry.fromPointXY"),
                maximum_lines=80,
                maximum_steps=16,
            )[0],
        ]

        census, priority = build_semantic_rollup_census(units, minimum_support=2)

        self.assertEqual(len(census), 1)
        self.assertEqual(census[0]["semantic_family"], "point_geometry_construction")
        self.assertEqual(census[0]["source_sha_support"], 2)
        self.assertEqual(len(priority), 2)


if __name__ == "__main__":
    unittest.main()
