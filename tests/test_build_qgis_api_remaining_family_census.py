from __future__ import annotations

import hashlib
import unittest

from scripts.build_qgis_api_remaining_family_census import (
    analyze_source,
    build_summary,
    select_source_disjoint_review,
)


def _row(source: str, authority: str = "body-a") -> dict:
    return {
        "record_id": authority,
        "source_root_id": "fixture",
        "source_path": f"/{authority}.py",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": authority,
        "source_authority_key": f"normalized_source_body_sha256:{authority}",
    }


RASTER_CALCULATOR = """def calculate(layer, output):
    entry = QgsRasterCalculatorEntry()
    entries = [entry]
    calculator = QgsRasterCalculator(
        '(\"band@1\" > 5) * 1', output, 'GTiff',
        layer.extent(), layer.width(), layer.height(), entries,
    )
    calculator.processCalculation()
"""


class RemainingFamilyCensusTest(unittest.TestCase):
    def test_recovers_complete_raster_calculator_macro(self) -> None:
        units = analyze_source(_row(RASTER_CALCULATOR), RASTER_CALCULATOR)

        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertEqual(unit["family_id"], "raster_calculator")
        self.assertEqual(unit["macro_status"], "complete")
        self.assertEqual(unit["candidate_l3_sequence"], ["L3_03_03_A"])
        self.assertEqual(unit["expression_fact"]["status"], "literal")
        self.assertEqual(unit["output_format_fact"]["value"], "GTiff")
        self.assertEqual(unit["constructor_signature"], "without_output_crs")
        self.assertIn("calculator.processCalculation()", unit["source_snippet"])
        self.assertEqual(len(unit["source_region_sha256"]), 64)
        self.assertFalse(unit["training_row_emitted"])

    def test_missing_terminal_remains_deferred(self) -> None:
        source = RASTER_CALCULATOR.replace("    calculator.processCalculation()\n", "")

        unit = analyze_source(_row(source), source)[0]

        self.assertEqual(unit["macro_status"], "deferred")
        self.assertEqual(unit["deferred_reason"], "process_calculation_call_not_found")

    def test_receiver_rebinding_remains_deferred(self) -> None:
        source = RASTER_CALCULATOR.replace(
            "    calculator.processCalculation()",
            "    calculator = other\n    calculator.processCalculation()",
        )

        unit = analyze_source(_row(source), source)[0]

        self.assertEqual(unit["macro_status"], "deferred")
        self.assertEqual(
            unit["deferred_reason"], "calculator_receiver_rebound_before_terminal"
        )

    def test_resolves_local_formula_and_output_crs_overload(self) -> None:
        source = """def calculate(layer, output, context):
    formula = f'(\"{layer.name()}@1\" > 5) * 1'
    entries = []
    calculator = QgsRasterCalculator(
        formula, output, 'GTiff', layer.extent(), layer.crs(),
        layer.width(), layer.height(), entries, context,
    )
    calculator.processCalculation()
"""

        unit = analyze_source(_row(source), source)[0]

        self.assertEqual(unit["macro_status"], "complete")
        self.assertEqual(unit["constructor_signature"], "with_output_crs")
        self.assertEqual(unit["expression_fact"]["status"], "fstring")
        self.assertEqual(unit["expression_fact"]["resolved_from"], "formula")
        self.assertEqual(unit["expression_fact"]["definition_lines"], [2])
        self.assertEqual(unit["evidence_span"], [2, 8])
        self.assertEqual(unit["output_crs_fact"]["source"], "layer.crs()")

    def test_marks_processing_expression_as_runtime_parameter(self) -> None:
        source = """def calculate(self, parameters, layer, output):
    expression = self.parameterAsString(parameters, self.EXPRESSION, None)
    entries = []
    calculator = QgsRasterCalculator(
        expression, output, 'GTiff', layer.extent(),
        layer.width(), layer.height(), entries,
    )
    calculator.processCalculation()
"""

        unit = analyze_source(_row(source), source)[0]

        self.assertEqual(unit["expression_fact"]["status"], "processing_parameter")
        self.assertEqual(unit["expression_fact"]["resolved_from"], "expression")

    def test_raster_export_is_censused_but_mapping_is_not_auto_granted(self) -> None:
        source = """def export(layer, output):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter(output)
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""

        unit = analyze_source(_row(source), source)[0]

        self.assertEqual(unit["family_id"], "raster_file_export")
        self.assertEqual(unit["macro_status"], "complete")
        self.assertEqual(unit["mapping_status"], "stable125_contract_review_required")
        self.assertEqual(unit["candidate_l3_sequence"], [])

    def test_summary_requires_net_new_exact_mapping_support(self) -> None:
        units = []
        for index in range(4):
            row = _row(RASTER_CALCULATOR, f"body-{index}")
            units.extend(analyze_source(row, RASTER_CALCULATOR))

        family_rows, priority, summary = build_summary(
            units,
            input_authorities=10,
            excluded_authorities=2,
            remaining_authorities=8,
            prefiltered_authorities=4,
            existing_train_authorities={
                "normalized_source_body_sha256:body-0"
            },
            minimum_support=3,
        )

        raster = next(row for row in family_rows if row["family_id"] == "raster_calculator")
        self.assertEqual(raster["complete_source_authority_count"], 4)
        self.assertEqual(raster["existing_train_authority_overlap"], 1)
        self.assertEqual(raster["net_new_source_authority_count"], 3)
        self.assertEqual(
            raster["support_gate"], "eligible_for_source_disjoint_calibration"
        )
        self.assertEqual(len(priority), 3)
        self.assertEqual(summary["priority_family_count"], 1)

    def test_review_split_is_authority_disjoint(self) -> None:
        rows = []
        for index in range(6):
            source = RASTER_CALCULATOR.replace(
                "(\"band@1\" > 5)", f"(\"band@1\" > {index})"
            )
            row = _row(source, f"body-{index}")
            rows.extend(analyze_source(row, source))

        calibration, holdout = select_source_disjoint_review(
            rows, per_split=3, seed=7
        )

        self.assertEqual(len(calibration), 3)
        self.assertEqual(len(holdout), 3)
        self.assertFalse(
            {row["source_authority_key"] for row in calibration}
            & {row["source_authority_key"] for row in holdout}
        )

    def test_review_split_samples_dense_source_without_source_leakage(self) -> None:
        dense_source = []
        for index in range(8):
            source = RASTER_CALCULATOR.replace(
                "(\"band@1\" > 5)", f"(\"band@1\" > {index})"
            )
            row = _row(source, "dense-body")
            row["source_sha256"] = "dense-source"
            units = analyze_source(
                {**row, "source_sha256": hashlib.sha256(source.encode()).hexdigest()},
                source,
            )
            units[0]["source_sha256"] = "dense-source"
            dense_source.extend(units)
        singleton_rows = []
        for index in range(12):
            source = RASTER_CALCULATOR.replace(
                "(\"band@1\" > 5)", f"(\"band@1\" >= {index})"
            )
            singleton_rows.extend(analyze_source(_row(source, f"body-{index}"), source))

        calibration, holdout = select_source_disjoint_review(
            [*dense_source, *singleton_rows],
            per_split=7,
            seed=11,
            max_units_per_source=3,
        )

        self.assertEqual(len(calibration), 7)
        self.assertEqual(len(holdout), 7)
        self.assertEqual(
            sum(row["source_sha256"] == "dense-source" for row in calibration), 3
        )
        self.assertFalse(
            {row["source_sha256"] for row in calibration}
            & {row["source_sha256"] for row in holdout}
        )

    def test_source_hash_mismatch_is_rejected(self) -> None:
        row = _row(RASTER_CALCULATOR)
        row["source_sha256"] = "wrong"

        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            analyze_source(row, RASTER_CALCULATOR)


if __name__ == "__main__":
    unittest.main()
